# pragma pylint: disable=missing-docstring
from __future__ import annotations

import math
import random
import typing
from typing import Any

from seat_game import SeatPlayer
from seat_typing import (Seat, PrivateNumber, SeatChannel, DiscordUser,
                         Findable, GenF)

if typing.TYPE_CHECKING:
    # pylint: disable=cyclic-import
    from discord_game import DiscordGame, DiscordGameException


class CommonPlayer(SeatPlayer, Findable):
    def __init__(self,
                 garnets: int = 0):
        super().__init__()
        self.garnets = garnets
        self.public_seat: Seat = Seat(-1)

        self.proposals: ListProposals = []
        self.botswaps: typing.List[BotSwap] = []

    @property
    def incoming_proposals(self) -> ListProposals:
        return [p for p in self.proposals
                if p.target == self]

    @property
    def outgoing_proposals(self) -> ListProposals:
        return [p for p in self.proposals
                if p.source == self]

    async def send(self, *args: Any, **kwargs: str) -> None:
        raise NotImplementedError('Pure virtual method')

    async def received_garnets(self, donater: CommonPlayer,
                               amount: int) -> None:
        pass

    def new_round(self) -> None:
        super().new_round()
        for proposal in self.proposals:
            proposal.cancel()
        self.proposals.clear()

        for botswap in self.botswaps:
            botswap.cancel()
        self.botswaps.clear()

        self.public_seat = self.seat

    def matches(self, search_key: str) -> bool:
        raise NotImplementedError('Virtual method matches.')

    @classmethod
    def find(cls: typing.Type[GenF], search_key: str, **kwargs: Any) -> GenF:
        assert 'game' in kwargs
        game: DiscordGame = kwargs['game']  # DiscordGame?

        for player in game.players:
            if player.matches(search_key):
                if isinstance(player, cls):
                    return player
                raise DiscordGameException(
                    'Error: Found {} which is a {} and not a {}.'.format(
                        player, type(player).__name__, cls.__name__))
        raise DiscordGameException(
            'Error: Found no {} matching `{}`.'.format(
                cls.__name__, search_key))


class DiscordPlayer(CommonPlayer):
    def __init__(self,
                 discord_user: DiscordUser,
                 garnets: int = 0) -> None:
        super().__init__(garnets)
        self.user = discord_user
        self._channel: typing.Optional[SeatChannel] = None
        self.ready = False
        self._assigned_numbers: typing.Dict[SeatPlayer, PrivateNumber] = {}

    def __str__(self) -> str:
        return self.user.display_name

    def matches(self, search_key: str) -> bool:
        if search_key.lower() in (self.user.name.lower(),
                                  self.user.display_name.lower()):
            return True
        if search_key.isdigit():
            if (int(search_key) == self.user.discord_id
                    or int(search_key) == self.seat):
                return True
        return False

    async def send(self, *args: Any, **kwargs: str) -> None:
        if self._channel is None:
            self._channel = await SeatChannel.from_user(self.user)
        return await self._channel.send(*args, **kwargs)

    @property
    def assigned_numbers(self) -> typing.Dict[SeatPlayer, PrivateNumber]:
        if self not in self._assigned_numbers:
            self._assigned_numbers[self] = self.number
        return self._assigned_numbers

    def add_proposal_to(self,
                        target: CommonPlayer,
                        garnets: int = 0) -> Proposal[CommonPlayer]:
        for prop in self.outgoing_proposals:
            if prop.target == target:
                raise DiscordGameException(
                    'You already have a proposal to {}'.format(target))

        proposal = Proposal(self, target, garnets)

        self.proposals.append(proposal)
        target.proposals.append(proposal)

        return proposal

    def add_botswap(self, botswap: BotSwap) -> None:
        for party in self, botswap.source, botswap.target:
            party.botswaps.append(botswap)

    # TODO: Move to Proposal, so there is only one visible entry point
    # having both Player.accept_proposal and proposal.accept it's not
    # intuitive which one should be called from the outside.

    def accept_proposal(self, proposal: Proposal[CommonPlayer]) -> None:
        proposal.accept()
        for party in self, proposal.source:
            party.proposals.remove(proposal)

    def cancel_proposal(self, proposal: Proposal[CommonPlayer]) -> None:
        proposal.cancel()
        self.proposals.remove(proposal)
        if proposal.source == self:
            proposal.target.proposals.remove(proposal)
        else:
            proposal.source.proposals.remove(proposal)

    def cancel_botswap(self, botswap: BotSwap) -> None:
        botswap.cancel()
        for party in self, botswap.source, botswap.target:
            party.botswaps.remove(botswap)

    async def donate_garnets(self, target: CommonPlayer, amount: int) -> None:
        if amount > self.garnets:
            raise DiscordGameException(
                'Error: cannot donate more garnets than you have.')
        if amount <= 0:
            raise DiscordGameException(
                'Error: invalid garnet amount')
        self.garnets -= amount
        target.garnets += amount

        await target.received_garnets(self, amount)


class BotPlayer(CommonPlayer):
    def __init__(self,
                 name: str,
                 garnets: int = 0) -> None:
        super().__init__(garnets)
        self.name = name

    def __str__(self) -> str:
        return self.name.title()

    def matches(self, search_key: str) -> bool:
        return search_key.lower() == self.name.lower()

    async def send(self, *args: Any, **kwargs: str) -> None:
        # The return value should never be used, so we're fine with an
        # error if somebody tries to.
        return None

    async def received_garnets(self, donater: CommonPlayer,
                               amount: int) -> None:
        if amount > 0:
            await donater.send(
                '{} thanks you for the kind donation, '
                'their secret number is {}'.format(
                    self.name, self.number))


CP = typing.TypeVar('CP', bound=CommonPlayer)
ListProposals = typing.List['Proposal[CommonPlayer]']


class Proposal(Findable, typing.Generic[CP]):
    def __init__(self,
                 source: CP,
                 target: CP,
                 garnets: int = 0):
        self.source = source
        self.target = target
        self.garnets = garnets

        self._lock_up_garnets()

    @classmethod
    def find(cls: typing.Type[GenF], search_key: str, **kwargs: Any) -> GenF:
        assert 'player' in kwargs
        player: DiscordPlayer = kwargs['player']

        for proposal in player.proposals:
            if (proposal.source.matches(search_key)
                    or proposal.target.matches(search_key)):
                if not isinstance(proposal, cls):
                    raise DiscordGameException(
                        'Expected type {}, found {}'.format(
                            cls, type(proposal)))
                return proposal
        raise DiscordGameException(
            'Error: Found no {} with a player matching `{}`.'.format(
                cls.__name__.lower(), search_key))

    def __contains__(self, player: CP) -> bool:
        return player in (self.source, self.target)

    def _lock_up_garnets(self) -> None:
        # lock up garnets until canceled
        if self.garnets < 0:
            raise DiscordGameException(
                'Garnet amount must be non-negative')
        if self.source.garnets < self.garnets:
            raise DiscordGameException(
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
            raise DiscordGameException(
                'You have already swapped.')

        if self.source.swapped:
            raise DiscordGameException(
                'target {} already swapped'.format(self.source))

        self.target.swap(self.source)

        self._award_garnets()

    def cancel(self) -> None:
        self._release_garnets()


class BotSwap(Proposal[BotPlayer]):
    """A proposal between two bots, sponsored by a player.

    We pass 0 garnets into Proposal to avoid lockup (better solution?).
    """

    def __init__(self,
                 source: BotPlayer,
                 target: BotPlayer,
                 guarantor: DiscordPlayer,
                 garnets: int = 0):
        self.guarantor = guarantor
        super().__init__(source, target, garnets)

    def __repr__(self) -> str:
        return ('BotSwap(source={}, target={}, guarantor={}, garnets={})'
                ''.format(self.source, self.target,
                          self.guarantor, self.garnets))

    def __str__(self) -> str:
        return ('Botswap between {} and {} '
                'guaranteed by {} with {} garnets.'.format(
                    self.source, self.target,
                    self.guarantor, self.garnets))

    def __keys(self) -> typing.Tuple[BotPlayer, BotPlayer, DiscordPlayer, int]:
        return (self.source, self.target, self.guarantor, self.garnets)

    def __eq__(self, other: typing.Any) -> bool:
        # pylint: disable=protected-access
        return (isinstance(other, BotSwap)
                and self.__keys() == other.__keys())

    def __hash__(self) -> int:
        return hash(self.__keys())

    def _lock_up_garnets(self) -> None:
        if self.garnets < 0:
            raise DiscordGameException(
                'Garnet amount must be non-negative.')

        if self.guarantor.garnets < self.garnets:
            raise DiscordGameException(
                "Can't create proposal, insufficient garnets.")

        self.guarantor.garnets -= self.garnets

    def _award_garnets(self) -> None:
        rewards = [math.ceil(self.garnets/2), math.floor(self.garnets/2)]
        random.shuffle(rewards)
        self.source.garnets += rewards[0]
        self.target.garnets += rewards[1]

    def _release_garnets(self) -> None:
        self.guarantor.garnets += self.garnets
