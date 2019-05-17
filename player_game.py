# pragma pylint: disable=missing-docstring
from __future__ import annotations
import typing
from typing import List, Set, Dict, Optional, Tuple, Any, cast

import random

import seat_game

from seat_typing import PrivateNumber, Seat, SeatException


class PlayerGameException(SeatException):
    pass


class Proposal:
    def __init__(self,
                 source: Player,
                 target: Player,
                 garnets: int = 0):
        self.source: Player = source
        self.target: Player = target
        self.garnets: int = garnets

        self.__lock_up_garnets()

    def __lock_up_garnets(self) -> None:
        # lock up garnets until canceled
        if self.garnets < 0:
            raise PlayerGameException(
                'Garnet amount must be non-negative')
        if self.source.garnets < self.garnets:
            raise PlayerGameException(
                "Can't create proposal, insufficient garnets")
        self.source.garnets -= self.garnets

    def __str__(self) -> str:
        return 'Proposal from {} to {} offering {} garnets'.format(
            self.source,
            self.target,
            self.garnets)

    def accept(self) -> None:
        if self.target.swapped:
            raise PlayerGameException(
                'You have already swapped.')

        if self.source.swapped:
            raise PlayerGameException(
                'target {} already swapped'.format(self.source))

        self.target.swap(self.source)

        self.target.garnets += self.garnets

    def cancel(self) -> None:
        self.source.garnets += self.garnets


class Findable:  # pylint: disable=too-few-public-methods
    @classmethod
    def find(cls, search_key: str, game: PlayerGame) -> Findable:
        raise NotImplementedError('Virtual method matches.')


class Player(Findable):
    """A player in a discord game.

    Much of the commands interface directly with the public methods,
    and there's frequent cross-communication with PlayerGame and Proposal."""
    def __init__(self,
                 player_game: PlayerGame,
                 # discord_user: discord.User,
                 seat: Seat = cast(Seat, -1),
                 garnets: int = 0):

        self.game: PlayerGame = player_game
        self._seat: Seat = seat
        self._swapped: bool = False
        self.garnets = garnets

    @classmethod
    def find(cls, search_key: str, game: PlayerGame) -> Player:
        for player in game.players:
            if player.matches(search_key):
                if isinstance(player, cls):
                    return player
                raise PlayerGameException(
                    'Error: Found {} which is a {} and not a {}.'.format(
                        player, type(player).__name__, cls.__name__))
        raise PlayerGameException(
            'Error: Found no player matching `{}`.'.format(search_key))

    @property
    def seat(self) -> Seat:
        return self._seat

    @property
    def number(self) -> PrivateNumber:
        return self.game.number_in_seat(self._seat)

    @property
    def swapped(self) -> bool:
        return self._swapped

    @property
    def proposals(self) -> List[Proposal]:
        return [p for p in self.game.proposals
                if self in (p.source, p.target)]

    @property
    def outgoing_proposals(self) -> List[Proposal]:
        return [p for p in self.game.proposals if p.source == self]

    @property
    def incoming_proposals(self) -> List[Proposal]:
        return [p for p in self.game.proposals if p.target == self]

    def add_proposal_to(self,
                        target: 'Player',
                        garnets: int = 0) -> Proposal:
        for prop in self.outgoing_proposals:
            if prop.target == target:
                raise PlayerGameException(
                    'You already have a proposal to {}'.format(target))

        return Proposal(self, target, garnets)

    def swap(self, target: Player, force: bool = False) -> None:
        self.game.swap_seats(self, target, force)

    def swap_seat(self, seat: Seat) -> None:
        self._seat = seat
        self._swapped = True

    def set_seat(self, seat: Seat) -> None:
        self._seat = seat

    def new_round(self) -> None:
        pass

    def reset_swapped(self) -> None:
        self._swapped = False

    async def donate_garnets(self, target: 'Player', amount: int) -> None:
        self.garnets -= amount
        target.garnets += amount

        await target.received_garnets(self, amount)

    async def received_garnets(self, donater: 'Player', amount: int) -> None:
        pass

    # I'm not sure about these functions. A Player really doesn't need these,
    # and they make no sense in the context of this class, but when
    # discord_game handles BotPlayers and DiscordPlayers we would need to do
    # constant casting to not get mypy to scream at us.
    async def send(self, *args: str, sep: str = ' ', end: str = '',
                   **kwargs: Tuple[str, str]) -> None:
        raise PlayerGameException('Pure virtual method')

    # Subclasses uses self so can't make it a function
    def matches(self, search_key: str) -> bool:
        raise NotImplementedError('Virtual method matches.')


class PlayerGame:
    def __init__(self,
                 options: Optional[Dict[str, Any]] = None):
        super().__init__()
        self._seating_to_player: List[Player] = []
        self.proposals: Set[Proposal] = set()
        self._game: seat_game.SeatGame = seat_game.SeatGame(
            options=options)

        self.options: Dict[str, Any] = {
            'public_swaps': False,  # TODO: Move up
            'win_garnets': 10,
            'x_garnets': -10,
            'start_garnets': 20,
            # 'x_count': len(self._game.current_x), # TODO: Move down
            'round_length': 600  # TODO: Move up
        }
        if options:
            for option in options:
                if option in self.options:
                    self.options[option] = options[option]

    # Translations of SeatGame in new context
    @property
    def players(self) -> List[Player]:
        return self._seating_to_player

    def player_in_seat(self, seat: Seat) -> Player:
        return self._seating_to_player[seat]

    @property
    def current_x_players(self) -> List[Player]:
        return [self.player_in_seat(x) for x in self._game.current_x_seats]

    @property
    def winners(self) -> List[Player]:
        return [self._seating_to_player[seat]
                for seat in self._game.winners]

    @property
    def table_layout(self) -> List[Player]:
        return self._seating_to_player

    # Straight up copies upwards
    def number_in_seat(self, seat: Seat) -> PrivateNumber:
        return self._game.number_in_seat(seat)

    @property
    def current_x(self) -> List[PrivateNumber]:
        return self._game.current_x

    @property
    def longest_streak(self) -> int:
        return self._game.longest_streak().longest_streak

    @property
    def win_streak_length(self) -> int:
        return self._game.win_streak_length

    @property
    def current_round(self) -> int:
        return self._game.game_round

    # game management

    def swap_seats(self,
                   source: Player,
                   target: Player,
                   force: bool = False) -> None:
        if not force:
            if source.swapped or target.swapped:
                raise PlayerGameException(
                    'swapping swapped players without force')
        self._game.swap_seats(source.seat, target.seat)
        (self._seating_to_player[source.seat],
         self._seating_to_player[target.seat]) = (
             self._seating_to_player[target.seat],
             self._seating_to_player[source.seat])

        tmp = source.seat
        source.swap_seat(target.seat)
        target.swap_seat(tmp)

    def add_player(self, player: Player) -> None:
        """Add a Player to the game with a random seat & number"""
        seat = self._game.add_seat()
        player.set_seat(seat)
        # player = Player(seat=seat, user=user, discord_game=self)

        if seat < len(self._seating_to_player):
            self._seating_to_player.append(
                self._seating_to_player[seat])
            self._seating_to_player[seat] = player
        else:
            self._seating_to_player.append(player)

    def remove_player(self, player: Player) -> None:
        self._game.remove_seat(player.seat)

        self._seating_to_player.pop(player.seat)
        for i in self._seating_to_player[player.seat:]:
            i.set_seat(i.seat - 1)

    def accept_proposal(self, proposal: Proposal) -> None:
        proposal.accept()
        self.proposals.remove(proposal)

    def cancel_proposal(self, proposal: Proposal) -> None:
        proposal.cancel()
        self.proposals.remove(proposal)

    def start_game(self) -> None:
        for player in self._seating_to_player:
            player.garnets = self.options['start_garnets']
        self._shuffle_players_in_seats()
        self._game.shuffle()

    def _shuffle_players_in_seats(self) -> None:
        random.shuffle(self._seating_to_player)

        players = self._seating_to_player.copy()

        for player in players:
            player.set_seat(
                typing.cast(Seat, self._seating_to_player.index(player)))

    def new_round(self) -> bool:

        for player in self._seating_to_player:
            player.new_round()
        for player in self._seating_to_player:
            player.reset_swapped()
            # player.botswaps = []

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
