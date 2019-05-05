# pragma pylint: disable=missing-docstring
from __future__ import annotations
from typing import List
from typing import Set
from typing import Dict

import random

import discord # type: ignore

import game

class DiscordGameException(Exception):
    pass

class Proposal:
    def __init__(self, source: Player, target: Player, discord_game: DiscordGame, garnets: int = 0):
        self._source: 'Player' = source
        self._target: 'Player' = target
        self._garnets: int = garnets
        self._game = discord_game

        #lock up garnets until canceled
        if garnets < 0:
            raise DiscordGameException(
                'Garnet amount must be non-negative')
        if self._source.garnets < garnets:
            raise DiscordGameException(
                "Can't create proposal, insufficient garnets")
        self._source.garnets -= garnets
        self._game.proposals.add(self)

    def __str__(self):
        return 'Proposal from {} to {} offering {} garnets'.format(
            self._source,
            self._target,
            self._garnets)

    @property
    def source(self) -> Player:
        return self._source

    @property
    def target(self) -> Player:
        return self._target

    @property
    def garnets(self) -> int:
        return self._garnets

    def accept(self):
        self._target.garnets += self._garnets
        self._game.proposals.remove(self)

    def cancel(self):
        self._source.garnets += self._garnets
        self._game.proposals.remove(self)





class Player:
    def __init__(self,
                 discord_game: DiscordGame,
                 user: discord.User,
                 seat: int,
                 garnets: int = 0):

        self._game = discord_game
        self.user = user
        self._seat = seat
        self._swapped: bool = False
        self.garnets = garnets

    def __str__(self):
        return self.user.display_name

    @property
    def seat(self):
        return self._seat

    @property
    def number(self):
        return self._game.number_in_seat(self._seat)

    @property
    def swapped(self):
        return self._swapped

    async def send(self, *args, **kwargs):
        #don't send to ourselves
        if self.user.id == 573077970445402113:
            return

        try:
            await self.user.send(*args, **kwargs)
        except discord.errors.Forbidden:
            print('blocked by {}'.format(self))



    def matches(self, search_key: str) -> bool:
        if search_key.lower() in (self.user.name.lower(), self.user.display_name.lower()):
            return True
        if search_key.isdigit():
            if int(search_key) == self.user.id or int(search_key) == self._seat:
                return True
        return False

    @property
    def outgoing_proposals(self) -> List[Proposal]:
        return [p for p in self._game.proposals if p.source == self]

    @property
    def incoming_proposals(self) -> List[Proposal]:
        return [p for p in self._game.proposals if p.target == self]

    def add_proposal_to(self, target: Player, garnets: int = 0) -> Proposal:
        for prop in self.outgoing_proposals:
            if prop.target == target:
                raise DiscordGameException(
                    'You already have a proposal to {}'.format(target))

        return Proposal(self, target, self._game, garnets)

    #returns a list of all proposals canceled, to let the bot notify
    #the involved players.
    def cancel_all_proposals(self):
        proposals = [p for p in self._game.proposals if self in (p.source, p.target)]
        for proposal in proposals:
            proposal.cancel()

        if not self._game.public_swaps:
            return []

        return proposals

    def accept_incoming_proposal(self, proposal: Proposal) -> List[Proposal]:
        if self.swapped:
            raise DiscordGameException(
                'You have already swapped.')

        if proposal.source.swapped:
            raise DiscordGameException(
                'target {} already swapped'.format(proposal.source))

        self._swap(proposal.source)
        proposal.accept()

        if not self._game.public_swaps:
            return []

        return (self.cancel_all_proposals()
                + proposal.source.cancel_all_proposals())

    def _swap(self, target, force=False):
        self._game.swap_seats(self, target, force)

    def swap_seat(self, seat):
        self._seat = seat
        self._swapped = True

    def set_seat(self, seat):
        self._seat = seat

    def reset_swapped(self):
        self._swapped = False

    def send_garnets(self, target: Player, amount: int):
        self.garnets -= amount
        target.garnets += amount

class DiscordGame:
    def __init__(self, options: Dict = {}): #pylint: disable=dangerous-default-value
        super().__init__()
        self._seating_to_player: List[Player] = []
        self.proposals: Set[Proposal] = set()
        self._game: game.Game = game.Game()

        self._game_running: bool = False
        self._public_swaps: bool = True

        self.options: Dict = {
            'public_swaps': True,
            'win_garnets': 10,
            'x_garnets': -10,
            'start_garnets': 10,
            #'x_count': len(self._game.current_x),
            'round_length': 120
        }
        for option in options:
            if option in self.options:
                self.options[option] = options[option]


    @property
    def players(self):
        return self._seating_to_player

    def swap_seats(self, source: Player, target: Player, force=False):
        if not force:
            if source.swapped or target.swapped:
                raise DiscordGameException('swapping swapped players without force')
        self._game.swap_seats(source.seat, target.seat)
        self._seating_to_player[source.seat], self._seating_to_player[target.seat] = (
            self._seating_to_player[target.seat], self._seating_to_player[source.seat])

        tmp = source.seat
        source.swap_seat(target.seat)
        target.swap_seat(tmp)

    def player_in_seat(self, seat) -> Player:
        return self._seating_to_player[seat]

    def number_in_seat(self, seat) -> int:
        return self._game.number_in_seat(seat)

    @property
    def current_x_players(self) -> List[Player]:
        return [self.player_in_seat(x) for x in self._game.current_x_seats]

    @property
    def current_x(self) -> List[int]:
        return self._game.current_x

    @property
    def running(self):
        return self._game_running

    @property
    def longest_streak(self):
        return self._game.longest_streak().longest_streak

    @property
    def winners(self):
        return [self._seating_to_player[seat]
                for seat in self._game.winners]

    @property
    def win_streak_length(self):
        return self._game.win_streak_length

    @property
    def current_round(self):
        return self._game.game_round

    @property
    def table_layout(self):
        return self._seating_to_player

    # game management

    def add_player(self, user: discord.User) -> Player:
        """Add a discord.User to the game with a random seat & number"""
        if self.running:
            raise DiscordGameException('unimplemented')
        seat = self._game.add_seat()
        player = Player(seat=seat, user=user, discord_game=self)
        if seat < len(self._seating_to_player):
            self._seating_to_player.append(
                self._seating_to_player[seat])
            self._seating_to_player[seat] = player
        else:
            self._seating_to_player.append(player)
        return player



    def remove_player(self, player: Player):
        self._game.remove_seat(player.seat)

        self._seating_to_player.pop(player.seat)
        for i in self._seating_to_player[player.seat:]:
            i.set_seat(i.seat - 1)


    def start_game(self):
        for player in self._seating_to_player:
            player.garnets = self.options['start_garnets']
        self._shuffle_players_in_seats()
        self._game.shuffle()
        self._game_running = True

    def stop_game(self):
        self._game_running = False

    def _shuffle_players_in_seats(self):
        random.shuffle(self._seating_to_player)

        players = self._seating_to_player.copy()

        for player in players:
            player.set_seat(self._seating_to_player.index(player))

    def new_round(self) -> bool:
        old_proposals = self.proposals.copy()
        for proposal in old_proposals:
            proposal.cancel()
        self.proposals = set()
        for player in self._seating_to_player:
            player.reset_swapped()

        if not self._game.game_over:
            self._game.new_round()
            return True

        for player in self.winners:
            player.garnets += self.options['win_garnets']
        for player in self.current_x_players:
            player.garnets += self.options['x_garnets']
        self._game_running = False
        return False
