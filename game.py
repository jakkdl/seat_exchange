# pragma pylint: disable=missing-docstring
import random
import math
from typing import List
from collections import namedtuple

##TODO: multiple x's

class GameException(Exception):
    pass


StreakResult = namedtuple('StreakResult', 'longest_streak instances starting_seat direction')

class Game:
    #self._seat_numbers is a seat-to-number mapping, where the index is the seat
    #and the value is the number in that seat

    def __init__(self, player_count: int = 0):
        #self.player_count = player_count

        self.game_round = 1
        self._current_x: List[int] = []
        self._seat_numbers: List[int] = []
        self._win_streak_length = 0

        if player_count != 0:
            self._seat_numbers = list(range(0, player_count))
            self._update_x()
            self._update_win_streak_length()
            self.shuffle()


    #swaps the numbers in two seats
    def swap_seats(self, a, b): #pylint: disable=invalid-name
        self._seat_numbers[a], self._seat_numbers[b] = self._seat_numbers[b], self._seat_numbers[a]


    def number_in_seat(self, seat) -> int:
        return self._seat_numbers[seat]

    @property
    def current_x_seats(self) -> List[int]:
        return [self._seat_numbers.index(x) for x in self._current_x]

    @property
    def player_count(self) -> int:
        return len(self._seat_numbers)

    def new_round(self):
        self.game_round += 1
        self._current_x = [(x+1)%self.player_count for x in self._current_x]

    def add_seat(self) -> int:
        """Take a random number, giving the seat with that number last.
        Take a random seat, moving the number in that seat last.
        Increase current X by 1. Recalculate win_streak_length"""
        old_player_count = self.player_count

        seat = random.randint(0, old_player_count)

        number = random.randint(0, old_player_count)

        # give previous owner of the number the last number
        if number != old_player_count:
            index = self._seat_numbers.index(number)
            self._seat_numbers[index] = old_player_count

        if seat != self.player_count:
            #move the number in our chosen seat last
            self._seat_numbers.append(self._seat_numbers[seat])
            #and put ourselves there
            self._seat_numbers[seat] = number
        else:
            #put ourselves last
            self._seat_numbers.append(number)

        self._update_x()
        self._update_win_streak_length()
        return seat

    def _update_x(self):
        if self.player_count < 6:
            self._current_x = []
            return
        #self._current_x = random.randint(0, self.player_count-1)
        self._current_x = [self.player_count-1]

        #if player count is real high, add X

    def _update_win_streak_length(self):
        count = self.player_count

        if count < 5:
            self._win_streak_length = count
            return

        if count < 7:
            self._win_streak_length = 3
            return

        self._win_streak_length = math.floor((self.player_count-1)/2)


    def remove_seat(self, seat):
        removed_number = self._seat_numbers[seat]

        #remove seat, does not give IndexError
        self._seat_numbers[seat:] = self._seat_numbers[seat+1:]

        #decrement all latter numbers by 1
        self._seat_numbers = [x-1 if x > removed_number else x for x in self._seat_numbers]

        for i in range(len(self._current_x)):
            if self._current_x[i] >= removed_number:
                self._current_x[i] -= 1
        self._update_win_streak_length()

    @property
    def win_streak_length(self) -> int:
        return self._win_streak_length

    def is_x(self, number: int) -> bool:
        return number in self._current_x

    def seat_is_x(self, seat) -> bool:
        return self.is_x(self._seat_numbers[seat])

    @property
    def current_x(self) -> List[int]:
        return self._current_x

    @property
    def game_over(self) -> bool:
        if self.player_count < 4:
            return True
        res = self.longest_streak()

        if (self.player_count == self._win_streak_length
                and res.longest_streak == self._win_streak_length):
            return True

        return res.longest_streak == self._win_streak_length and res.instances == 1

    def _adjacent_numbers(self, first, second, delta) -> bool:
        if self.is_x(first) or self.is_x(second):
            return False

        #step from first, if we only encounter x before hitting second, we're adjacent_numbers's
        #This is due to game rules where 4 & 6 are adjacent_numberss if 5 is x
        #generalized to multiple x
        for i in range(1, self.player_count):
            number = (first + i*delta) % self.player_count
            if number == second:
                return True
            if not self.is_x(number):
                return False
        return False

    def longest_streak(self) -> StreakResult:
        # Go over all the seats in two different directions, reversing the second for loop.
        player_count = self.player_count


        longest_streak = 0
        instances = 0
        starting_seat = 0
        direction = 0
        for start, end, delta in (0, player_count, +1), (player_count-1, -1, -1):

            for i in range(start, end, delta):
                if self.is_x(self._seat_numbers[i]):
                    continue
                streak = 1

                while (streak < player_count
                       and self._adjacent_numbers(
                           self._seat_numbers[(i+delta*(streak-1)) % player_count],
                           self._seat_numbers[(i+delta*(streak))   % player_count],
                           1)):
                    streak += 1

                if streak > longest_streak:
                    longest_streak = streak
                    instances = 1
                    starting_seat = i
                    direction = delta
                elif streak == longest_streak:
                    instances += 1


        return StreakResult(longest_streak, instances, starting_seat, direction)

    @property
    def winners(self) -> List[int]:
        res = self.longest_streak()

        return [
            (res.starting_seat + i*res.direction) % self.player_count
            for i in range(res.longest_streak)
        ]


    def shuffle(self):
        """algorithm always works on n > 8. Never works on n < 6.
        n=6 - 9.5% fail rate. n=7 1.8%, n=8 0.3%.
        so on those we retry until succesful."""
        def consecutive(first, second):
            first_number = self._seat_numbers[first % self.player_count]
            second_number = self._seat_numbers[second % self.player_count]

            return (self._adjacent_numbers(first_number, second_number, 1)
                    or self._adjacent_numbers(first_number, second_number, -1))

        count = self.player_count

        if count < 6:
            random.shuffle(self._seat_numbers)
            return

        if count < 9:
            self._seat_numbers = self._build_valid_numbers()
            return


        random.shuffle(self._seat_numbers)

        for i in range(self.player_count):
            if consecutive(i, i+1):
                #offset = random.randint(0, count-1)
                offset = 0

                for j in range(offset, count+offset):
                    #don't swap with ourselves, or the one we're consecutive with,
                    #or the one after that.
                    if (j - i)%count < 2:
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

    def _build_valid_numbers(self) -> List[int]:
        """Generate a list with non-adjacent numbers up to count-1.
        Then offset all numbers depending on X,
        and insert X at random index.
        Good for 6 to 8."""
        count = self.player_count - 1

        def _rec(result):
            #if we only have one number left to insert, check that it
            #doesn't collide with first or last element.
            if len(result) == count-1:
                number = (set(range(count)) - set(result)).pop()
                if (abs(number - result[-1]) not in (1, count-1)
                        and abs(number - result[0]) not in (1, count-1)):
                    return result + [number]

                return []

            #branch with each number not already in the list,
            #and doesn't collide with last element
            numbers = list(range(count))
            random.shuffle(numbers)
            for i in numbers:
                if i not in result and abs(i - result[-1]) not in (1, count-1):
                    ret = _rec(result + [i])
                    if ret:
                        return ret
            return []

        res = []
        res.append(random.randint(0, count-2))

        res = _rec(res)

        #on these counts there should be one x
        current_x = self._current_x[0]

        for i in range(count):
            if res[i] >= current_x:
                res[i] += 1

        res.insert(random.randint(0, count), current_x)
        return res
