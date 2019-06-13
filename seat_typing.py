"""Defines data types used for typing in the rest of the project."""
from __future__ import annotations

import asyncio
import typing
import discord  # type: ignore

DiscordChannel = typing.Union[discord.TextChannel,
                              discord.DMChannel]


class SeatException(Exception):
    pass


# mypy-annotation-for-classmethod-returning-instance
# https://stackoverflow.com/questions/44640479/

GenF = typing.TypeVar('GenF', bound='Findable')


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


class SeatChannel:
    def __init__(self,
                 channel: DiscordChannel):
        self._channel = channel
        self.is_public = isinstance(channel, discord.TextChannel)
        self.is_dm = isinstance(channel, discord.DMChannel)

    @classmethod
    async def from_user(cls, user: discord.User) -> SeatChannel:
        if user.dm_channel is None:
            await user.create_dm()

        return SeatChannel(user.dm_channel)

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
