# pragma pylint: disable=missing-docstring
from __future__ import annotations
from typing import List
from typing import Set

import random

import discord # type: ignore

import game


class DiscordGameException(Exception):
    pass

class Proposal:
    def __init__(self, source, target, garnets=0):
        self._source: 'Player' = source
        self._target: 'Player' = target
        self._garnets: int = garnets

    @property
    def source(self):
        return self._source

    @property
    def target(self):
        return self._target

    @property
    def garnets(self):
        return self._garnets

    def involves(self, player):
        return player in (self.source, self.target)


class Player:
    def __init__(self,
                 discord_game: DiscordGame,
                 user: discord.User,
                 seat: int,
                 garnets: int = 0):

        self._game = discord_game
        self._user = user
        self._seat = seat
        self._swapped: bool = False
        self._garnets = garnets

    def __str__(self):
        return self._user.display_name

    @property
    def seat(self):
        return self._seat

    @property
    def garnets(self):
        return self._garnets

    @property
    def number(self):
        return self._game.number_in_seat(self._seat)

    @property
    def swapped(self):
        return self._swapped

    async def send(self, *args, **kwargs):
        if self._user.id == 573077970445402113:
            return
        try:
            await self._user.send(*args, **kwargs)
        except discord.errors.Forbidden:
            print('blocked by {}'.format(self))



    def matches(self, search_key: str) -> bool:
        if search_key in (self._user.name, self._user.display_name):
            return True
        if search_key.isdigit():
            if int(search_key) == self._user.id or int(search_key) == self._seat:
                return True
        return False

    @property
    def outgoing_proposals(self) -> List[Proposal]:
        return [p for p in self._game.proposals if p.source == self]

    @property
    def incoming_proposals(self) -> List[Proposal]:
        return [p for p in self._game.proposals if p.target == self]

   # @property
   # def proposals(self) -> List[Proposal]:
   #     return [p for p in self._game.proposals if p.involves(self)]

    def add_proposal_to(self, target: Player, garnets: int = 0):
        for prop in self.outgoing_proposals:
            if prop.target == target:
                raise DiscordGameException(
                    'You already have a proposal to {}'.format(target))

        proposal = Proposal(self, target, garnets)

        self._game.add_proposal(proposal)

    def reject_proposal(self, proposal: Proposal):
        self._game.remove_proposal(proposal)

    def cancel_proposal(self, proposal: Proposal):
        self._game.remove_proposal(proposal)

    #returns a list of all proposals canceled, to let the bot notify
    #the involved players.
    def cancel_all_proposals(self):
        proposals = [p for p in self._game.proposals if self in (p.source, p.target)]
        for proposal in proposals:
            self._game.remove_proposal(proposal)

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

        self._garnets += proposal.garnets
        proposal.source._garnets -= proposal.garnets
        self._swap(proposal.source)
        self._game.remove_proposal(proposal)

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
    def __init__(self):
        super().__init__()
        self._seating_to_player: List[Player] = []
        self._game: game.Game = game.Game()
        self._proposals: Set[Proposal] = set()

        self._game_running: bool = False
        self._public_swaps: bool = True


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
    def proposals(self):
        return self._proposals

    def add_proposal(self, proposal: Proposal):
        self._proposals.add(proposal)

    def remove_proposal(self, proposal: Proposal):
        self._proposals.remove(proposal)

    @property
    def current_x_player(self) -> Player:
        return self.player_in_seat(self._game.current_x_seat)

    @property
    def current_x(self):
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
        return self._seating_to_player

    # game management

    def add_player(self, user: discord.User) -> Player:
        """Add a discord.User to the game with a random seat & number"""
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
        if self._game_running:
            self._game.remove_seat(player.seat)

        self._seating_to_player.pop(player.seat)
        for i in self._seating_to_player[player.seat:]:
            i.set_seat(i.seat - 1)


    def start_game(self):
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

    def new_round(self):
        self._proposals = set()
        self._game.new_round()
        for player in self._seating_to_player:
            player.reset_swapped()
