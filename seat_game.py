# pragma pylint: disable=missing-docstring
"""Defines the class Game, which implements core seat and number logic.

Only handles seats and numbers, has no concept of players, garnets, etc.
as these depend on setting (e.g. players need not be simulated IRL).

Is probably *severely* overtyped, because I wanted to try it out.
Do not think it's recommended to subclass/NewType int when modifying them
so much, using them as index and generating with range,
but hopefully it pays off in the rest of the project."""
from __future__ import annotations

import math
import copy
import typing
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from seat_typing import Seat, PrivateNumber, SeatException


@dataclass
class StreakResult:
    longest_streak: int
    instances: int
    starting_seat: Seat
    direction: int

    def __lt__(self, other: typing.Any) -> bool:
        if isinstance(other, StreakResult):
            return self.longest_streak < other.longest_streak
        if isinstance(other, int):
            return self.longest_streak < other
        return NotImplemented

    def __le__(self, other: typing.Any) -> bool:
        if isinstance(other, StreakResult):
            return self.longest_streak <= other.longest_streak
        if isinstance(other, int):
            return self.longest_streak <= other
        return NotImplemented


class SeatPlayer:
    """A player in a seat game."""
    def __init__(self) -> None:
        self.number = PrivateNumber(-1)
        self.seat = Seat(-1)
        self.swapped = False

    def swap(self, target: SeatPlayer, force: bool = False) -> None:
        if not force:
            for player in self, target:
                raise SeatException('{} has already swapped.'.format(player))

        self.seat, target.seat = target.seat, self.seat
        self.swapped = True
        target.swapped = True

    def new_round(self) -> None:
        self.swapped = False


GenP = typing.TypeVar('GenP', bound=SeatPlayer)


class SeatGame(typing.Generic[GenP]):
    """Implements the lowest abstraction of a seat game with only the concepts
    seats, numbers and X's.

    self._seat_numbers is a seat-to-number mapping,
    where the index is the seat
    and the value is the number in that seat."""

    def __init__(self,
                 options: Optional[Dict[str, Any]] = None) -> None:

        self._options: Dict[str, Any] = {}

        if options:
            self._options = options

        self.current_round = 1
        self.players: List[GenP] = []
        self.current_x: List[PrivateNumber] = []
        self.__cached_streak_result: Optional[StreakResult] = None

    @property
    def x_count(self) -> int:
        if 'x_count' in self._options:
            assert isinstance(self._options['x_count'], int)
            return self._options['x_count']

        if len(self.players) < 6:
            return 0

        return 1

    @property
    def win_streak_length(self) -> int:
        if 'win_streak_length' in self._options:
            assert isinstance(self._options['win_streak_length'], int)
            return self._options['win_streak_length']

        count = self.player_count

        if count < 5:
            return count

        if count < 7:
            return 3

        if count == 8:
            return 4

        return math.floor((self.player_count-1)/2)

    def player_in_seat(self, seat: Seat) -> GenP:
        for player in self.players:
            if player.seat == seat:
                return player
        raise SeatException('Found no player in seat {}'.format(seat))

    @property
    def current_x_players(self) -> List[GenP]:
        return [p for p in self.players if p.number in self.current_x]

    def _init_x(self) -> List[PrivateNumber]:
        res = []

        # Divide the series of numbers into x_count parts, take the beginning
        # of each part and offset by number of rounds-1, mod player count
        for i in range(self.x_count):
            res.append(PrivateNumber((i//self.x_count + self.current_round-1)
                                     % self.player_count))
        return res

    @property
    def player_count(self) -> int:
        return len(self.players)

    def new_round(self) -> None:
        self.__cached_streak_result = None
        self.current_round += 1
        self.current_x = [(x+1) % self.player_count
                          for x in self.current_x]

    def add_player(self, player: GenP) -> None:
        """Add a player with a random number and seat, that doesn't increase
        the streak length."""
        valid_numbers = [*PrivateNumber.range(self.player_count)]
        valid_seats = [*Seat.range(self.player_count)]

        number: PrivateNumber
        seat: Seat

        longest_streak = self.longest_streak
        current_players = copy.deepcopy(self.players)

        for number in valid_numbers:
            for seat in valid_seats:
                player.seat = seat
                player.number = number

                for other in self.players:
                    if other.seat >= seat:
                        other.seat += 1
                    if other.number >= number:
                        other.number += 1

                self.players.append(player)

                self.current_x = self._init_x()
                self.__cached_streak_result = None

                if (self.longest_streak <= longest_streak
                        or self.longest_streak < 3
                        or len(self.players) < 4):
                    return

                self.players = copy.deepcopy(current_players)

        raise SeatException('Unable to add player. Weird?')

    def remove_player(self, player: GenP) -> None:
        self.__cached_streak_result = None

        for other in self.players:
            if other.seat >= player.seat:
                other.seat -= 1
            if other.number >= player.number:
                other.number -= 1

        for i in range(len(self.current_x)):
            if self.current_x[i] > player.number:
                self.current_x[i] -= 1

    def is_x(self, number: int) -> bool:
        return number in self.current_x

    @property
    def game_over(self) -> bool:
        if self.player_count < 4:
            return True

        res = self.longest_streak

        streak_length = self.win_streak_length

        if (self.player_count == streak_length
                and res.longest_streak == streak_length):
            return True

        return res.longest_streak == streak_length and res.instances == 1

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

    @property
    def longest_streak(self) -> StreakResult:
        if self.__cached_streak_result is None:
            self.__cached_streak_result = self._longest_streak()

        return self.__cached_streak_result

    def _longest_streak(self) -> StreakResult:
        # Go over all the seats in two different directions,
        # reversing the second for loop.

        # Wait a second this shit is dumb
        # 1. Don't need to reverse the list, just check both directions from
        # each seat.
        # Oh nevermind, that's because I wanted it sorted in some way.

        # 2. Even better is to start at a seat that is not neighbor with it's
        # previous seat, go forward conting the streak length, when finished
        # counting streak length, *continue from there* for next check.
        # This one does a bunch of extra checks (although not that many)
        player_count = self.player_count
        seat_numbers: List[PrivateNumber] = [PrivateNumber(0)] * player_count

        for other in self.players:
            seat_numbers[other.seat] = other.number

        longest_streak = 0
        instances = 0
        starting_seat = 0
        direction = 0
        for start, end, delta in ((0, player_count, +1),
                                  (player_count-1, -1, -1)):

            for i in range(start, end, delta):
                if self.is_x(seat_numbers[i]):
                    continue
                streak = 1

                while (streak < player_count
                       and self._adjacent_numbers(
                           seat_numbers[
                               (i+delta*(streak-1)) % player_count],
                           seat_numbers[
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
                            Seat(starting_seat), direction)

    @property
    def winners(self) -> List[GenP]:
        res = self.longest_streak

        return [
            self.player_in_seat(
                (res.starting_seat + i*res.direction) % self.player_count)
            for i in Seat.range(res.longest_streak)
        ]

    @property
    def table_layout(self) -> List[GenP]:
        res = self.players.copy()
        res.sort(key=lambda x: x.seat, reverse=True)
        return res
