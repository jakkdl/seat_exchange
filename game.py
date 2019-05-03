# pragma pylint: disable=missing-docstring
import random
import math

##TODO: multiple x's

class GameException(Exception):
    pass

class Game:
    #self.numbers is a seat-to-number mapping, where the index is the seat
    #and the value is the number in that seat

    def __init__(self, player_count):
        self.player_count = player_count

        self.game_round = 1
        self._current_x = player_count
        self._streak_win_length = math.floor((player_count-1)/2)

        self.numbers = list(range(1, player_count+1))
        self.shuffle()


    #swaps the numbers in two seats
    def swap_seats(self, a, b): #pylint: disable=invalid-name
        self.numbers[a], self.numbers[b] = self.numbers[b], self.numbers[a]


    def number_in_seat(self, seat):
        return self.numbers[seat]

    @property
    def current_x_seat(self):
        return self.numbers.index(self._current_x)



    def new_round(self):
        self.game_round += 1
        self._current_x = self._current_x % self.player_count + 1



    def remove_seat(self, seat):
        removed_number = self.numbers[seat]

        #remove seat, does not give IndexError
        self.numbers[seat:] = self.numbers[seat+1:]

        #decrement all latter numbers by 1
        self.numbers = [x-1 if x > removed_number else x for x in self.numbers]

        self.player_count -= 1
        if self._current_x > removed_number:
            self._current_x -= 1
        self._streak_win_length = math.floor((self.player_count-1)/2)

    @property
    def streak_win_length(self):
        return self._streak_win_length

    def is_x(self, number):
        return number == self._current_x

    def seat_is_x(self, seat):
        return self.is_x(self.numbers[seat])

    @property
    def current_x(self):
        return self._current_x

    @property
    def game_over(self):
        highest_streak, instances, _ = self.highest_streak

        return highest_streak == self._streak_win_length and instances == 1

    @property
    def highest_streak(self):
        # To end on the starting seat, in increasing order of numbers, we check for
        # a negative difference inside the loop.
        # We also go over all the seats in two different directions, reversing the second for loop.

        highest_streak = 0
        instances = 0
        starting_seat = 0
        for start, end, delta in (0, self.player_count, +1), (self.player_count-1, -1, -1):

            for i in range(start, end, delta):
                streak = 0

                while (self.numbers[(i+streak) % self.player_count]
                       - self.numbers[(i+streak+1) % self.player_count] == -1
                       and not self.is_x(i+streak)
                       and streak < self.player_count):
                    streak += 1

                if streak > highest_streak:
                    highest_streak = streak
                    instances = 1
                    starting_seat = i + streak - 1
                elif streak == highest_streak:
                    instances += 1


        return highest_streak, instances, starting_seat

    @property
    def winners(self):
        highest_streak, instances, starting_seat = self.highest_streak
        if highest_streak != self._streak_win_length or instances != 1:
            raise GameException('Winners called in a non-winning state')

        result = []
        for i in range(self._streak_win_length):
            seat = (starting_seat + i) % self.player_count
            result.append((seat, self.numbers[seat]))
        return result


    def shuffle(self):
        def consecutive(first, second):
            diff = abs(self.numbers[first % self.player_count]
                       - self.numbers[second % self.player_count])
            return diff in (1, self.player_count - 1)

        count = self.player_count


        random.shuffle(self.numbers)

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
