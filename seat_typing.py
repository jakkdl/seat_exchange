"""Defines data types used for typing in the rest of the project."""
from __future__ import annotations

import asyncio
import typing

from enum import Enum, auto
import discord  # type: ignore

DiscordChannel = typing.Union[discord.TextChannel,
                              discord.DMChannel]


class SeatException(Exception):
    pass


# mypy-annotation-for-classmethod-returning-instance
# https://stackoverflow.com/questions/44640479/

GenF = typing.TypeVar('GenF', bound='Findable')
OWNER_ID = 84627464709472256


class Findable:  # pylint: disable=too-few-public-methods
    @classmethod
    def find(cls: typing.Type[GenF],
             search_key: str, **kwargs: typing.Any) -> GenF:
        raise NotImplementedError('Virtual method matches.')


class PrivateNumber(int):
    def __add__(self, other: typing.Any) -> PrivateNumber:
        return PrivateNumber(super().__add__(other))

    def __sub__(self, other: typing.Any) -> PrivateNumber:
        return PrivateNumber(super().__sub__(other))

    def __mul__(self, other: typing.Any) -> PrivateNumber:
        return PrivateNumber(super().__mul__(other))

    def __floordiv__(self, other: typing.Any) -> PrivateNumber:
        return PrivateNumber(super().__floordiv__(other))

    def __mod__(self, other: typing.Any) -> PrivateNumber:
        return PrivateNumber(super().__mod__(other))

    @classmethod
    def range(cls, end: int
              ) -> typing.Generator[PrivateNumber, None, None]:
        for i in range(end):
            yield cls(i)


class Seat(int):
    def __str__(self) -> str:
        return chr(ord('A') + self)

    def __repr__(self) -> str:
        return self.__str__()

    def __add__(self, other: typing.Any) -> Seat:
        return Seat(super().__add__(other))

    def __sub__(self, other: typing.Any) -> Seat:
        return Seat(super().__sub__(other))

    def __mod__(self, other: typing.Any) -> Seat:
        return Seat(super().__mod__(other))

    @classmethod
    def range(cls, end: int
              ) -> typing.Generator[Seat, None, None]:
        for i in range(end):
            yield cls(i)


class GameState(Enum):
    CREATED = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSED = auto()
    GAME_OVER = auto()
    STOPPED = auto()

    def __str__(self) -> str:
        state_strs = {
            GameState.CREATED: 'newly created',
            GameState.STARTING: 'starting',
            GameState.RUNNING: 'running',
            GameState.PAUSED: 'paused',
            GameState.GAME_OVER: 'finished',
            GameState.STOPPED: 'stopped',
        }
        return state_strs[self]


class SeatChannel:
    def __init__(self,
                 channel: DiscordChannel):
        self._channel = channel
        self.is_public = isinstance(channel, discord.TextChannel)
        self.is_dm = isinstance(channel, discord.DMChannel)

    @classmethod
    async def from_user(cls, user: DiscordUser) -> SeatChannel:
        if user.user.dm_channel is None:
            await user.user.create_dm()

        return SeatChannel(user.user.dm_channel)

    def __str__(self) -> str:
        return str(self._channel)

    def __hash__(self) -> int:
        """Default hash function takes the id (memory address) of the instance
        and we want different instances of SeatChannel with the same channel
        to have the same hash."""
        return self._channel.id  # type: ignore # discord untyped

    def __eq__(self, other: object) -> bool:
        """And if we define __hash__ we should also define __eq__"""
        if not isinstance(other, SeatChannel):
            return False

        # pylint: disable=protected-access # we know other is SeatChannel
        # discord is untyped, so mypy also doesn't know == returns a bool.
        return self._channel == other._channel  # type: ignore

    async def send(self,
                   *args: typing.Any,
                   sep: str = ' ',
                   start: str = '',
                   end: str = '') -> None:
        try:
            asyncio.create_task(
                self._channel.send(
                    start + sep.join(str(arg) for arg in args) + end)
            )
        except discord.errors.Forbidden:
            print('blocked by {}'.format(self._channel))
            raise SeatException(
                "Error: The bot needs to be able to DM you to fully "
                "function.\n"
                "Please allow direct messages from server "
                'members, under "Privacy Settings", for this server.')

    async def wait_send(self,
                        *args: typing.Any,
                        sep: str = ' ',
                        start: str = '',
                        end: str = '') -> discord.Message:
        # TODO: return wrapped message?
        try:
            return await self._channel.send(
                start + sep.join(str(arg) for arg in args) + end)
        except discord.errors.Forbidden:
            print('blocked by {}'.format(self._channel))
            raise SeatException(
                "Error: The bot needs to be able to DM you to fully "
                "function.\n"
                "Please allow direct messages from server "
                'members, under "Privacy Settings", for this server.')


class DiscordUser:
    """Wrapper around discord.User"""
    def __init__(self, user: discord.User):
        self.user = user
        self.games: typing.List[typing.Any] = []  # TODO TODO TODO TODO

    def __str__() -> str:
        return self.user.__str__  # type: ignore

    @property
    def name(self) -> str:
        return self.user.name  # type: ignore

    @property
    def discord_id(self) -> int:
        return self.user.id  # type: ignore

    @property
    def display_name(self) -> str:
        return self.user.display_name  # type: ignore

    async def send(self, message: str) -> None:
        await self.user.send(message)

    @property
    def is_admin(self) -> bool:
        if self.user.id == OWNER_ID:
            return True
        if not isinstance(self.user, discord.Member):
            return False
        for role in self.user.roles:
            if role.name.lower() == 'game admin':
                return True
        return False
