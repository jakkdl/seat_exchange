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
        self.source: 'Player' = source
        self.target: 'Player' = target
        self.garnets: int = garnets
        self._game = discord_game

        #lock up garnets until canceled
        if garnets < 0:
            raise DiscordGameException(
                'Garnet amount must be non-negative')
        if self.source.garnets < garnets:
            raise DiscordGameException(
                "Can't create proposal, insufficient garnets")
        self.source.garnets -= garnets
        self._game.proposals.add(self)

    def __str__(self):
        return 'Proposal from {} to {} offering {} garnets'.format(
            self.source,
            self.target,
            self.garnets)

    def accept(self):
        if self.target.swapped:
            raise DiscordGameException(
                'You have already swapped.')

        if self.source.swapped:
            raise DiscordGameException(
                'target {} already swapped'.format(self.source))

        self.target.swap(self.source)
        self.target.garnets += self.garnets
        self._game.proposals.remove(self)

    def cancel(self):
        self.source.garnets += self.garnets
        self._game.proposals.remove(self)





class Player:
    def __init__(self,
                 discord_game: DiscordGame,
                 discord_user: discord.User,
                 seat: int = -1,
                 garnets: int = 0):

        self._game = discord_game
        self.user = discord_user
        self._seat = seat
        self._swapped: bool = False
        self.garnets = garnets
        self.assigned_numbers: Dict[Player, int] = {}

        self.botswaps: List[Proposal] = []

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
    def proposals(self) -> List[Proposal]:
        return [p for p in self._game.proposals if self in (p.source, p.target)]

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

    def swap(self, target, force=False):
        self._game.swap_seats(self, target, force)

    def swap_seat(self, seat):
        self._seat = seat
        self._swapped = True

    def set_seat(self, seat):
        self._seat = seat

    def new_round(self):
        pass

    def reset_swapped(self):
        self._swapped = False

    async def donate_garnets(self, target: Player, amount: int):
        self.garnets -= amount
        target.garnets += amount

        await target.received_garnets(self, amount)

    async def received_garnets(self, donater: Player, amount: int):
        pass

class BotPlayer(Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def send(self, *args, **kwargs):
        pass

    def new_round(self):
        print('botplayer new round called')
        proposals = self.incoming_proposals


        if proposals:
            random.shuffle(proposals)

            proposal = max(proposals, key=lambda x: x.garnets)

            try:
                proposal.accept()
            except DiscordGameException:
                pass

        super().new_round()

    async def received_garnets(self, donater: Player, amount: int):
        await donater.send('{} thanks you for your kind donation, their number is {}.'
                           ''.format(self, self.number))

class DiscordGame:
    def __init__(self, options: Dict = {}): #pylint: disable=dangerous-default-value
        super().__init__()
        self._seating_to_player: List[Player] = []
        self.proposals: Set[Proposal] = set()
        self._game: game.Game = game.Game()

        self.options: Dict = {
            'public_swaps': False,
            'win_garnets': 10,
            'x_garnets': -10,
            'start_garnets': 20,
            #'x_count': len(self._game.current_x),
            'round_length': 600
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

    def add_player(self, player: Player):
        """Add a Player to the game with a random seat & number"""
        seat = self._game.add_seat()
        player.set_seat(seat)
        #player = Player(seat=seat, user=user, discord_game=self)

        if seat < len(self._seating_to_player):
            self._seating_to_player.append(
                self._seating_to_player[seat])
            self._seating_to_player[seat] = player
        else:
            self._seating_to_player.append(player)



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

    def _shuffle_players_in_seats(self):
        random.shuffle(self._seating_to_player)

        players = self._seating_to_player.copy()

        for player in players:
            player.set_seat(self._seating_to_player.index(player))

    def new_round(self) -> bool:

        for player in self._seating_to_player:
            player.new_round()
        for player in self._seating_to_player:
            player.reset_swapped()
            player.botswaps = []

        old_proposals = self.proposals.copy()
        for proposal in old_proposals:
            proposal.cancel()
        self.proposals = set()

        if not self._game.game_over:
            self._game.new_round()
            return True

        for player in self.winners:
            player.garnets += self.options['win_garnets']
        for player in self.current_x_players:
            player.garnets += self.options['x_garnets']
        return False
