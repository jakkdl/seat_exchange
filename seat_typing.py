"""Defines data types used for typing in the rest of the project."""
from __future__ import annotations
import typing
from typing import cast

import discord  # type: ignore

# Seat = typing.NewType("Seat", int)
PrivateNumber = typing.NewType("PrivateNumber", int)

DiscordChannel = typing.Union[discord.TextChannel,
                              discord.DMChannel]


class SeatException(Exception):
    pass


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
            await self._channel.send(
                start + sep.join(str(arg) for arg in args) + end,
                wait=False)
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


class Seat(int):
    def __str__(self) -> str:
        return chr(ord('A') + int(self))

    def __add__(self, other: int) -> Seat:
        return cast(Seat, super().__add__(other))

    def __sub__(self, other: int) -> Seat:
        return cast(Seat, super().__sub__(other))

    def __mod__(self, other: int) -> Seat:
        return cast(Seat, super().__mod__(other))
