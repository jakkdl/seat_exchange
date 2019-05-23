# pragma pylint: disable=missing-docstring
from __future__ import annotations
import typing
from typing import List, Any, cast

import random

import seat_game

import strings

from seat_typing import PrivateNumber, Seat, SeatException


class PlayerGameException(SeatException):
    pass


class Findable:  # pylint: disable=too-few-public-methods
    @classmethod
    def find(cls, search_key: str, **kwargs: Any) -> Findable:
        raise NotImplementedError('Virtual method matches.')


class Proposal(Findable):
    def __init__(self,
                 source: Player,
                 target: Player,
                 garnets: int = 0):
        self.source: Player = source
        self.target: Player = target
        self.garnets: int = garnets

        self._lock_up_garnets()

    @classmethod
    def find(cls, search_key: str, **kwargs: Any) -> Proposal:
        assert 'player' in kwargs
        player: Player = kwargs['player']

        for proposal in player.proposals:
            if (proposal.source.matches(search_key)
                    or proposal.target.matches(search_key)):
                return proposal
        raise PlayerGameException(
            'Error: Found no {} with a player matching `{}`.'.format(
                cls.__name__.lower(), search_key))

    def __contains__(self, player: Player) -> bool:
        return player in (self.source, self.target)

    def _lock_up_garnets(self) -> None:
        # lock up garnets until canceled
        if self.garnets < 0:
            raise PlayerGameException(
                'Garnet amount must be non-negative')
        if self.source.garnets < self.garnets:
            raise PlayerGameException(
                "Can't create proposal, insufficient garnets")
        self.source.garnets -= self.garnets

    def _release_garnets(self) -> None:
        self.source.garnets += self.garnets

    def _award_garnets(self) -> None:
        self.target.garnets += self.garnets

    def __str__(self) -> str:
        return 'Proposal from {} to {} offering {} garnets.'.format(
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

        self._award_garnets()

    def cancel(self) -> None:
        self._release_garnets()


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
    def find(cls, search_key: str, **kwargs: Any) -> Player:
        assert 'game' in kwargs
        game: PlayerGame = kwargs['game']

        for player in game.players:
            if player.matches(search_key):
                if isinstance(player, cls):
                    return player
                raise PlayerGameException(
                    'Error: Found {} which is a {} and not a {}.'.format(
                        player, type(player).__name__, cls.__name__))
        raise PlayerGameException(
            'Error: Found no {} matching `{}`.'.format(
                cls.__name__, search_key))

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

        proposal = Proposal(self, target, garnets)

        self.game.proposals.add(proposal)

        return proposal

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
        if amount > self.garnets:
            raise PlayerGameException(
                'Error: cannot donate more garnets than you have.')
        if amount <= 0:
            raise PlayerGameException(
                'Error: invalid garnet amount')
        self.garnets -= amount
        target.garnets += amount

        await target.received_garnets(self, amount)

    async def received_garnets(self, donater: 'Player', amount: int) -> None:
        pass

    # I'm not sure about these functions. A Player really doesn't need these,
    # and they make no sense in the context of this class, but when
    # discord_game handles BotPlayers and DiscordPlayers we would need to do
    # constant casting to not get mypy to scream at us.
    async def send(self, *args: Any, **kwargs: str) -> None:
        raise NotImplementedError('Pure virtual method')

    # Subclasses uses self so can't make it a function
    def matches(self, search_key: str) -> bool:
        raise NotImplementedError('Virtual method matches.')


class PlayerGame:
    default_options: typing.Dict[str, Any] = strings.DEFAULT_OPTIONS

    def __init__(self,
                 options: typing.Optional[typing.Dict[str, Any]] = None):
        self.options = options if options is not None else {}
        for key in self.default_options:
            if key not in self.options:
                self.options[key] = self.default_options[key]

        # TODO super()
        self._game: seat_game.SeatGame = seat_game.SeatGame(
            options=self.options)

        self._seating_to_player: List[Player] = []
        self.proposals: typing.Set[Proposal] = set()

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

        old_proposals = self.proposals.copy()
        for proposal in old_proposals:
            proposal.cancel()
        self.proposals = set()

        if not self._game.game_over:
            self._game.new_round()
            return True

        self._award_win_garnets()

        return False

    def _award_win_garnets(self) -> None:
        for player in self.winners:
            player.garnets += self.options['win_garnets']
        for player in self.current_x_players:
            player.garnets += self.options['x_garnets']

        streak_length = self._game.win_streak_length
        middle_garnets = self.options['middle_garnets']
        if streak_length % 2 == 0:
            self.winners[streak_length//2] += middle_garnets//2
            self.winners[streak_length//2-1] += middle_garnets//2
        else:
            self.winners[(streak_length-1)//2] += middle_garnets
