#!/usr/bin/python3
# pragma pylint: disable=missing-docstring
from typing import Dict, List
import datetime

import discord  # type: ignore

from discord_game import DiscordGame

import seat_commands as commands

from seat_typing import SeatException, SeatChannel

# TODO: police nickname changes


class DiscordBotException(SeatException):
    pass


class DiscordUser():
    """Wrapper around discord.User"""
    def __init__(user: discord.User):
        self.user = user


class DiscordBot(discord.Client):  # type: ignore
    def __init__(self) -> None:
        super().__init__()
        self.games: Dict[SeatChannel, DiscordGame] = {}
        self.users: Dict[discord.user, DiscordUser] = {}

        self.command_list: List[commands.CommandType] = []
        self.command_dict: Dict[str, List[commands.CommandType]] = {}

        self._initialize_commands()

    def _initialize_commands(self) -> None:
        self.command_list += [
            # General info
            commands.Help(self.command_dict),
            commands.Rules(),
            commands.Commands(self.command_list),
            commands.Source(),

            commands.Create(self.games),
            commands.CreateJoin(self.games),
            commands.CreateRealLifeGame(self.games),
            commands.Shutdown(self),
        ]

        for command in self.command_list:
            for command_name in command.command_name_list:
                if command_name not in self.command_dict:
                    self.command_dict[command_name] = [command]
                else:
                    self.command_dict[command_name].append(command)

    async def on_ready(self) -> None:
        print('Logged in as {0.user} at {1}'.format(
            self, datetime.datetime.now()))
        # for guild in self.guilds:
        #     for channel in guild.channels:
        #         if channel.name == 'testing':
        #             await channel.send('Seat Exchange Bot v0.1')

    async def on_message(self, message: discord.message) -> None:
        if message.author == self.user:
            return

        if not message.content.startswith('!'):
            return

        command = message.content.split(' ')[0][1:]
        channel = SeatChannel(message.channel)

        if message.author not in self.users:
            self.users[message.author] = DiscordUser(message.author)
        user = self.users[message.author]
        # parameters = message.content.split(' ')[1:]

        if command in self.command_dict:
            command_message = commands.CommandMessage(
                message, channel, user)
            errors = []
            for matching_command in self.command_dict[command]:
                try:
                    await matching_command.execute(command_message)
                    return
                except SeatException as error:
                    errors.append(error)
            print(errors)
            await message.channel.send('\n'.join(str(x) for x in errors))

    async def on_reaction_add(self,
                              reaction: discord.Reaction,
                              user: discord.User) -> None:
        message = reaction.message
        channel = SeatChannel(message.channel)

        if channel not in self.games:
            return

        game = self.games[channel]

        if message.id not in game.reactable_messages:
            print(message, '\n', game.reactable_messages)
            return

        await game.reactable_messages[message.id].on_react(
            reaction, user)


def main() -> None:
    with open('discord_token') as f:  # pylint: disable=invalid-name
        token = f.read().strip()

    bot = DiscordBot()
    bot.run(token)


if __name__ == '__main__':
    main()
