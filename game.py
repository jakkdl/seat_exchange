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
        self._current_x = player_count
        self._seat_numbers: List[int] = []
        self._win_streak_length = 0

        if player_count != 0:
            self._win_streak_length = math.floor((player_count-1)/2)
            self._seat_numbers = list(range(1, player_count+1))
            self.shuffle()


    #swaps the numbers in two seats
    def swap_seats(self, a, b): #pylint: disable=invalid-name
        self._seat_numbers[a], self._seat_numbers[b] = self._seat_numbers[b], self._seat_numbers[a]


    def number_in_seat(self, seat):
        return self._seat_numbers[seat]

    @property
    def current_x_seat(self):
        return self._seat_numbers.index(self._current_x)

    @property
    def player_count(self) -> int:
        return len(self._seat_numbers)

    def new_round(self):
        self.game_round += 1
        self._current_x = self._current_x % self.player_count + 1

    def add_seat(self) -> int:
        """Take a random number, giving the seat with that number last.
        Take a random seat, moving the number in that seat last.
        Increase current X by 1. Recalculate win_streak_length"""

        seat = random.randint(0, self.player_count)

        number = random.randint(1, self.player_count+1)

        # give previous owner of the number the last number
        if number != self.player_count+1:
            index = self._seat_numbers.index(number)
            self._seat_numbers[index] = self.player_count+1

        if seat != self.player_count:
            #move the number in our chosen seat last
            self._seat_numbers.append(self._seat_numbers[seat])
            #and put ourselves there
            self._seat_numbers[seat] = number
        else:
            #put ourselves last
            self._seat_numbers.append(number)

        self._current_x += 1
        self._win_streak_length = math.floor((self.player_count-1)/2)
        return seat



    def remove_seat(self, seat):
        removed_number = self._seat_numbers[seat]

        #remove seat, does not give IndexError
        self._seat_numbers[seat:] = self._seat_numbers[seat+1:]

        #decrement all latter numbers by 1
        self._seat_numbers = [x-1 if x > removed_number else x for x in self._seat_numbers]

        self.player_count -= 1
        if self._current_x > removed_number:
            self._current_x -= 1
        self._win_streak_length = math.floor((self.player_count-1)/2)

    @property
    def win_streak_length(self):
        return self._win_streak_length

    def is_x(self, number):
        return number == self._current_x

    def seat_is_x(self, seat):
        return self.is_x(self._seat_numbers[seat])

    @property
    def current_x(self):
        return self._current_x

    @property
    def game_over(self):
        res = self.longest_streak()

        return res.longest_streak == self._win_streak_length and res.instances == 1

    def longest_streak(self):
        # To end on the starting seat, in increasing order of numbers, we check for
        # a negative difference inside the loop.
        # We also go over all the seats in two different directions, reversing the second for loop.
        player_count = self.player_count
        def neighbour(first, second, delta):
            if self.is_x(first) or self.is_x(second):
                return False
            if second - first in (delta, delta-player_count):
                return True

            #step from first, if we only encounter x before hitting second, we're neighbour's
            #This is due to game rules where 4 & 6 are neighbours if 5 is x
            #generalized to multiple x
            for i in range(1, player_count):
                number = (first + i*delta - 1) % player_count + 1
                if not self.is_x(number):
                    return False
                if number == second:
                    return True
            return False


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
                       and neighbour(self._seat_numbers[(i+delta*(streak-1)) % player_count],
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
        def consecutive(first, second):
            diff = abs(self._seat_numbers[first % self.player_count]
                       - self._seat_numbers[second % self.player_count])
            return diff in (1, self.player_count - 1)

        count = self.player_count


        random.shuffle(self._seat_numbers)

        for i in range(self.player_count):
            if consecutive(i, i+1):
                offset = random.randint(0, count-1)

                for j in range(offset, count+offset):
                    swappable = True
                    deltas = ((0, +1), (0, -1), (-1, 0), (+1, 0))

                    for i_delta, j_delta in deltas:
                        if consecutive(i+i_delta, j+j_delta):
                            swappable = False
                            break

                    if swappable:
                        self.swap_seats(i, j % count)
