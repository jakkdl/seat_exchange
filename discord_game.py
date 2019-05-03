# pragma pylint: disable=missing-docstring
from dataclasses import dataclass

import random
import game


class DiscordGameException(Exception):
    pass

@dataclass
class Proposal:
    source_id: int
    target_id: int
    #garnets

@dataclass
class Player:
    seat: int
    swapped: bool = False
    #garnets


class DiscordGame:
    def __init__(self):
        self._seating_to_discord_id = []

        self._players = {}
        self.player_count = 0
        self._game_running = False
        self._game = None
        self._public_swaps = True

        self._proposals = set()


    def get_seat(self, user_id):
        return self._players[user_id].seat

    def get_number(self, user_id):
        return self._game.number_in_seat(self.get_seat(user_id))

    def get_player_in_seat(self, seat):
        return self._seating_to_discord_id[seat]

    @property
    def current_x_player(self):
        return self.get_player_in_seat(self._game.current_x_seat)

    @property
    def current_x(self):
        return self._game.current_x

    @property
    def game_running(self):
        return self._game_running

    def have_swapped(self, user_id):
        return self._players[user_id].swapped

    @property
    def longest_loop(self):
        return self._game.highest_streak[0]

    @property
    def winners(self):
        return [(winner.seat, winner.number, self._seating_to_discord_id[winner.seat])
                for winner in self._game.winners]

    @property
    def public_swaps(self):
        return self._public_swaps

    @property
    def current_round(self):
        return self._game.game_round

    @property
    def game_over(self):
        return self._game.game_over

    @property
    def table_layout(self):
        return self._seating_to_discord_id

    # game management

    def add_player(self, user_id):
        player_count = len(self._players)
        self._seating_to_discord_id.append(user_id)
        self._players[user_id] = Player(seat=player_count)



    def remove_player(self, user_id):
        seat = self._players[user_id].seat
        if self._game_running:
            self._game.remove_seat(seat)

        self._seating_to_discord_id.pop(seat)
        for i in self._seating_to_discord_id[seat:]:
            self._players[i].seat -= 1


    def start_game(self):
        self._shuffle_seats()
        self._game = game.Game(len(self._players))

    def _shuffle_seats(self):
        random.shuffle(self._seating_to_discord_id)

        for user_id, player in self._players.items():
            player.seat = self._seating_to_discord_id.index(user_id)

    def new_round(self):
        self._proposals = set()
        self._game.new_round()


    # proposal and swapping functions

    def get_outgoing_proposals(self, user_id):
        if user_id not in self._players:
            raise DiscordGameException('invalid user_id')
        return [p.target for p in self._proposals if p.source == user_id]

    def get_incoming_proposals(self, user_id):
        if user_id not in self._players:
            raise DiscordGameException('invalid user_id')
        return [p.source for p in self._proposals if p.target == user_id]

    def add_outgoing_proposal(self, source, target):
        if source not in self._players:
            raise DiscordGameException('invalid source')

        if target not in self._players:
            raise DiscordGameException('invalid target')

        proposal = Proposal(source, target)

        if proposal in self._proposals:
            raise DiscordGameException(
                'proposal {} already in _proposals'.format(
                    proposal))

        self._proposals.add(proposal)

    def cancel_proposal(self, source_id, target_id):
        if source_id not in self._players:
            raise DiscordGameException(
                'invalid source_id')

        proposal = Proposal(source_id, target_id)

        if proposal not in self._proposals:
            raise DiscordGameException(
                'cannot find proposal {}'.format(
                    proposal))

        self._proposals.remove(proposal)

    #returns a list of all proposals canceled, to let the bot notify
    #the involved players.
    def cancel_all_proposals(self, user_id):
        proposals = [p for p in self._proposals if user_id in (p.source, p.target)]
        for proposal in proposals:
            self._proposals.remove(proposal)

        if not self.public_swaps:
            return []

        return proposals

    def accept_incoming_proposal(self, source, target):
        if source not in self._players:
            raise DiscordGameException('invalid source {}'.format(source))

        if target not in self._players:
            raise DiscordGameException('invalid target {}'.format(target))

        if self._players[source].swapped:
            raise DiscordGameException(
                'target {} already swapped'.format(target))

        if self._players[target].swapped:
            raise DiscordGameException(
                'target {} already swapped'.format(target))

        proposal = Proposal(source, target)

        if proposal not in self._proposals:
            raise DiscordGameException(
                'proposal {} not in _proposals'.format(
                    proposal))

        self._swap_players(source, target)
        self._proposals.remove(proposal)

        if not self.public_swaps:
            return []

        return (self.cancel_all_proposals(source)
                + self.cancel_all_proposals(target))

    def _swap_players(self, source_user_id, target_user_id, force=False):
        source = self._players[source_user_id]
        target = self._players[target_user_id]
        if not force:
            if source.swapped or target.swapped:
                raise DiscordGameException('swapping swapped players without force')
        self._game.swap_seats(source.seat, target.seat)
        source.seat, target.seat = target.seat, source.seat

        source.swapped = True
        target.swapped = True
