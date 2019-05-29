# pragma pylint: disable=missing-docstring
"""Defines the class Game, which implements core seat and number logic.

Only handles seats and numbers, has no concept of players, garnets, etc.
as these depend on setting (e.g. players need not be simulated IRL).

Is probably *severely* overtyped, because I wanted to try it out.
Do not think it's recommended to subclass/NewType int when modifying them
so much, using them as index and generating with range,
but hopefully it pays off in the rest of the project."""
from __future__ import annotations

import random
import math
from typing import List, Iterable, Dict, Optional, Any, cast
from dataclasses import dataclass

from seat_typing import Seat, PrivateNumber


@dataclass
class StreakResult:
    longest_streak: int
    instances: int
    starting_seat: Seat
    direction: int


class SeatGame:
    """Implements the lowest abstraction of a seat game with only the concepts
    seats, numbers and X's.

    self._seat_numbers is a seat-to-number mapping,
    where the index is the seat
    and the value is the number in that seat."""

    def __init__(self,
                 player_count: int = 0,
                 options: Optional[Dict[str, Any]] = None):

        self._options: Dict[str, Any] = {}

        if options:
            self._options = options

        self.game_round = 1
        self._seat_numbers: List[PrivateNumber] = []
        self.current_x: List[PrivateNumber] = self._init_x()
        self.__cached_game_over: Optional[bool] = None

        if player_count != 0:
            self._seat_numbers = cast(List[PrivateNumber],
                                      list(range(0, player_count)))
            self.shuffle()

    # swaps the numbers in two seats
    def swap_seats(self, first: Seat, second: Seat) -> None:
        self.__cached_game_over = None
        self._seat_numbers[first], self._seat_numbers[second] = (
            self._seat_numbers[second], self._seat_numbers[first])

    def number_in_seat(self, seat: Seat) -> PrivateNumber:
        return self._seat_numbers[seat]

    @property
    def x_count(self) -> int:
        if 'x_count' in self._options:
            return cast(int, self._options['x_count'])

        if len(self._seat_numbers) < 6:
            return 0

        return 1

    @property
    def win_streak_length(self) -> int:
        if 'win_streak_length' in self._options:
            return cast(int, self._options['win_streak_length'])

        count = self.player_count

        if count < 5:
            return count

        if count < 7:
            return 3

        if count == 8:
            return 4

        return math.floor((self.player_count-1)/2)

    @property
    def current_x_seats(self) -> List[Seat]:
        return [cast(Seat, self._seat_numbers.index(x))
                for x in self.current_x]

    def _init_x(self) -> List[PrivateNumber]:
        res = []

        for i in range(self.x_count):
            res.append((i//self.x_count + self.game_round-1) % self.player_count)
        return cast(List[PrivateNumber], res)

    @property
    def player_count(self) -> int:
        return len(self._seat_numbers)

    def new_round(self) -> None:
        self.__cached_game_over = None
        self.game_round += 1
        self.current_x = [cast(PrivateNumber, (x+1) % self.player_count)
                          for x in self.current_x]

    def add_seat(self) -> Seat:
        """Take a random number between 0 and old number of players, inclusive.
        Increment all old numbers higher or equal by 1.
        Take a random seat between 0 and old number of players (inclusive).
        Increment all old seats higher or equal to that by 1.

        We also increment X by 1 if it's higher than the added number. This
        to avoid the same player being X twice.

        Previous algorithm was:
        Take a random number, giving the seat with that number last.
        Take a random seat, moving the number in that seat last.
        Increase current X by 1. Recalculate win_streak_length.

        This was changed:
        1. to be consistent with seat removal
        2. Number-wise, not to screw up a specific player.
        2.1 If the game has
        started all higher numbers will know the new player has a lower number
        than them, and all lower numbers will know the new player has a higher
        number. This gives a minor information advantage to all old players.
        (although crucially if your two neighbours are communicating they can
        figure it out). This is maybe outweighed by their streak & alliances
        being screwed with. Maybe better simply to announce the new players
        number.
        2.2 But in the other case only the old owner of the number
        will know the new players number, and the new player will know the old
        players number, which is very unfair to the old player, who not only
        has to find new friends, his secret number was also revealed.
        3. Seat-wise, not to screw up specific players.
        3.1 There's no info being given out, but if the old owner of the seat
        had fought hard for it he's now randomly last in the circle.
        Players arranging around the end of the circle is now also at a
        disadvantage, and therefore have a stake against new player joining.
        3.2 In the new circle one team may be screwed if the new player
        randomly takes a spot within their streak. This is unfortunate, but at
        least the risk of this is fairly spread amongst all players.
        Players curently owning a series of chairs have an incentive to
        campaign against new players joining, but if you're late into the game
        you probably shouldn't add new players.
        """
        self.__cached_game_over = None
        old_player_count = self.player_count

        new_seat: Seat = cast(Seat,
                              random.randint(0, old_player_count))

        new_number: PrivateNumber = cast(PrivateNumber,
                                         random.randint(0, old_player_count))

        # Increment all higher or equal numbers by 1
        self._seat_numbers = [cast(PrivateNumber, x+1)
                              if x >= new_number else x
                              for x in self._seat_numbers]

        # add seat
        self._seat_numbers.insert(new_seat, new_number)

        # TODO: Hrmmmmmmm
        self.current_x = self._init_x()

        return new_seat

    def remove_seat(self, seat: Seat) -> None:
        self.__cached_game_over = None
        removed_number = self._seat_numbers.pop(seat)

        # decrement all latter numbers by 1
        self._seat_numbers = [cast(PrivateNumber, x-1)
                              if x > removed_number else x
                              for x in self._seat_numbers]

        for i in range(len(self.current_x)):
            if self.current_x[i] > removed_number:
                self.current_x[i] = cast(PrivateNumber,
                                         self.current_x[i] + 1)

    def is_x(self, number: int) -> bool:
        return number in self.current_x

    def seat_is_x(self, seat: Seat) -> bool:
        return self.is_x(self._seat_numbers[seat])

    @property
    def game_over(self) -> bool:
        if self.__cached_game_over is not None:
            return self.__cached_game_over

        if self.player_count < 4:
            self.__cached_game_over = True
        else:
            res = self.longest_streak()

            streak_length = self.win_streak_length

            if (self.player_count == streak_length
                    and res.longest_streak == streak_length):
                self.__cached_game_over = True
            else:

                self.__cached_game_over = (res.longest_streak == streak_length
                                           and res.instances == 1)
        return self.__cached_game_over

    def _adjacent_numbers(self, first: PrivateNumber,
                          second: PrivateNumber,
                          delta: int) -> bool:
        if self.is_x(first) or self.is_x(second):
            return False

        # step from first, if we only encounter x before hitting second,
        # we're adjacent_numbers's
        # This is due to game rules where 4 & 6 are adjacent_numberss if 5 is x
        # generalized to multiple x
        for i in range(1, self.player_count):
            number = (first + i*delta) % self.player_count
            if number == second:
                return True
            if not self.is_x(number):
                return False
        return False

    def longest_streak(self) -> StreakResult:
        # Go over all the seats in two different directions,
        # reversing the second for loop.
        player_count = self.player_count

        longest_streak = 0
        instances = 0
        starting_seat = 0
        direction = 0
        for start, end, delta in ((0, player_count, +1),
                                  (player_count-1, -1, -1)):

            for i in range(start, end, delta):
                if self.is_x(self._seat_numbers[i]):
                    continue
                streak = 1

                while (streak < player_count
                       and self._adjacent_numbers(
                           self._seat_numbers[
                               (i+delta*(streak-1)) % player_count],
                           self._seat_numbers[
                               (i+delta*(streak)) % player_count],
                           1)):
                    streak += 1

                if streak > longest_streak:
                    longest_streak = streak
                    instances = 1
                    starting_seat = i
                    direction = delta
                elif streak == longest_streak:
                    instances += 1

        return StreakResult(longest_streak, instances,
                            cast(Seat, starting_seat), direction)

    @property
    def winners(self) -> List[int]:
        res = self.longest_streak()

        return [
            (res.starting_seat + i*res.direction) % self.player_count
            for i in range(res.longest_streak)
        ]

    def shuffle(self) -> None:
        """algorithm always works on n > 8. Never works on n < 6.
        n=6 - 9.5% fail rate. n=7 1.8%, n=8 0.3%.
        We *could* just retry until we succeed, but instead I wrote an
        entirely new function to build the seating."""
        def consecutive(first: Seat, second: Seat) -> bool:
            first_number = self._seat_numbers[first % self.player_count]
            second_number = self._seat_numbers[second % self.player_count]

            return (self._adjacent_numbers(first_number, second_number, 1)
                    or self._adjacent_numbers(first_number, second_number, -1))

        self.__cached_game_over = None
        count = self.player_count

        if count < 6:
            random.shuffle(self._seat_numbers)
            return

        if count < 9:
            self._seat_numbers = self._build_valid_numbers()
            return

        random.shuffle(self._seat_numbers)

        for i in cast(Iterable[Seat], range(self.player_count)):
            if consecutive(i, i+1):
                # offset = random.randint(0, count-1)
                offset = 0

                for j in cast(Iterable[Seat], range(offset, count+offset)):
                    # don't swap with ourselves,
                    # or the one we're consecutive with,
                    # or the one after that.
                    if (j - i) % count < 2:
                        continue

                    swappable = True
                    deltas = ((0, +1), (0, -1), (-1, 0), (+1, 0))

                    for i_delta, j_delta in deltas:
                        if consecutive(i+i_delta, j+j_delta):
                            swappable = False
                            break

                    if swappable:
                        self.swap_seats(i, j % count)
                        break

    def _build_valid_numbers(self) -> List[PrivateNumber]:
        """Generate a list with non-adjacent numbers up to count-1.
        Then offset all numbers depending on X,
        and insert X at random index.
        Good for 6 to 8."""
        count = self.player_count - 1

        def _rec(result: List[PrivateNumber]) -> List[PrivateNumber]:
            # if we only have one number left to insert, check that it
            # doesn't collide with first or last element.
            if len(result) == count-1:
                number = cast(PrivateNumber,
                              (set(range(count)) - set(result)).pop())
                if (abs(number - result[-1]) not in (1, count-1)
                        and abs(number - result[0]) not in (1, count-1)):
                    return result + [number]

                return []

            # branch with each number not already in the list,
            # and doesn't collide with last element
            numbers: List[PrivateNumber] = list(cast(Iterable[PrivateNumber],
                                                     range(count)))
            random.shuffle(numbers)
            for i in numbers:
                if i not in result and abs(i - result[-1]) not in (1, count-1):
                    ret = _rec(result + [i])
                    if ret:
                        return ret
            return []

        res: List[PrivateNumber] = []
        res.append(cast(PrivateNumber, random.randint(0, count-2)))

        res = _rec(res)

        # on these counts there should be one x
        current_x = self.current_x[0]

        for i in range(count):
            if res[i] >= current_x:
                res[i] = cast(PrivateNumber, res[i] + 1)

        res.insert(random.randint(0, count), current_x)
        return res
