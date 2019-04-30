import random
import math

##TODO: multiple x's
##TODO: remove seat

class Seats:

    def __init__(self, player_count, options={}):
        self.player_count = player_count

        self.game_round = 1
        self.x = player_count
        self.streak_win_length = math.floor((player_count-1)/2)

        self.numbers = list(range(1, player_count+1))
        self.shuffle()

    
    #swaps the numbers in two seats
    def swap_seats(self, a, b):
        self.numbers[a], self.numbers[b] = self.numbers[b], self.numbers[a]


    def number_in_seat(seat):
        return self.numbers[seat]



    def new_round(self):
        self.round += 1
        self.x = self.x % self.player_count + 1

    #TODO
    def game_over(self):
        pass


    #TODO
    def remove_seat(self):
        pass

    def get_streak_win_length(self):
        return self.streak_win_length

    def is_x(self, number):
        return number == self.x

    def consecutive(self, first, second):
        diff = abs(self.numbers[first % self.player_count]
                   - self.numbers[second % self.player_count])
        return diff == 1 or diff == self.player_count - 1


    #TODO: incorrectly can go up and down. Can't use consecutive.
    def highest_streak(self):

        highest_streak = 0
        for i in range(self.player_count):
            streak = 1
            if self.is_x(self.numbers[i]):
                continue

            while self.consecutive(i+streak-1, i+streak) and not self.is_x(i+streak):
                streak += 1

            if streak > highest_streak:
                highest_streak = streak
            

        return highest_streak



    def shuffle(self):
        count = self.player_count


        random.shuffle(self.numbers)

        for i in range(self.player_count):
            if (self.consecutive(i, i+1) or
                (self.is_x(i+1) and self.consecutive(i, i+2))
                or (self.is_x(i) and self.is_x(i+1))):

                offset = random.randint(0, count-1)
                for j in range(offset, count+offset):

                    swappable = True
                    deltas = ((0, +1), (0, -1), (-1, 0), (+1, 0))

                    for i_delta, j_delta in deltas:
                        if (self.consecutive(i+i_delta, j+j_delta) or
                            ((self.is_x(i+i_delta) or self.is_x(j+j_delta)) and
                             self.consecutive(i+2*i_delta, j+2*j_delta))):
                            swappable = False
                            break

                    if swappable:
                        self.swap_seats(i, j % count)


