"""Heavily inspired by incnone's necrobot for racing crypt of the necrodancer.
"""
from __future__ import annotations

from typing import Dict, Container, Optional, Union
from dataclasses import dataclass

import discord  # type: ignore

from discord_game import DiscordPlayer, DiscordGame, GameState
from seat_typing import SeatException

GameDict = Dict[discord.TextChannel, DiscordGame]


class CommandException(SeatException):
    def __init__(self, command: CommandType, message: str):
        super().__init__('Error running `{}`: {}'.format(
            command.command_name, message))


class CommandMessage:
    """Wrapper for discord.message"""
    def __init__(self, message: discord.message) -> None:
        self._message = message

        self.author = message.author
        self.channel = message.channel
        self.command = message.content.split(' ')[0][1:]
        self.args = message.content.split(' ')[1:]

    @property
    def author_is_admin(self) -> bool:
        for role in self.author.roles:
            if role.name.lower() == 'game admin':
                return True
        return False


@dataclass
class Requirements:
    public_only: bool = False
    private_only: bool = False
    admin_only: bool = False
    game_only: bool = False
    not_active_player: bool = False

    # implies game_only
    valid_game_states: Container[GameState] = GameState
    player_only: bool = False


class CommandType():
    def __init__(self,
                 command_name: str,
                 *command_names: str,
                 games: Optional[GameDict] = None,
                 requirements: Requirements = Requirements(),
                 help_text: str = 'This command has no help text.'
                 ) -> None:
        self.command_name_list = (command_name,) + command_names
        self.games = games
        self.help_text = help_text
        self.requirements = requirements

    @property
    def command_name(self) -> str:
        return self.command_name_list[0]

    @property
    def game_only(self) -> bool:
        return (self.requirements.game_only
                or self.requirements.player_only
                or self.requirements.valid_game_states != GameState)

    @property
    def player_only(self) -> bool:
        return self.requirements.player_only

    def _validate_channel(self,
                          channel: Union[discord.TextChannel,
                                         discord.DMChannel]) -> None:
        # channel can also be group dm
        if (self.requirements.public_only
                and not isinstance(channel, discord.TextChannel)):
            raise CommandException(self, 'Not a public channel.')
        if (self.requirements.private_only
                and not isinstance(channel, discord.DMChannel)):
            raise CommandException(self, 'Not a private channel.')

    def matches(self, key: str) -> bool:
        return key in self.command_name_list

    # def valid / fills requirements
    # that way we can have several commands matching the same commandmessage
    # but only execute the one that's valid.

    async def execute(self, command: CommandMessage) -> None:
        if self.requirements.admin_only and not command.author_is_admin:
            raise CommandException(self,
                                   'Called by non-admin {}'.format(
                                       command.author.display_name))

        self._validate_channel(command.channel)

        if self.requirements.not_active_player and self.games:
            for other_game in self.games.values():
                if (command.author in other_game and other_game.state not in
                        (GameState.GAME_OVER, GameState.STOPPED)):
                    raise CommandException(
                        self, 'You are a player in an active game.')

        if not self.game_only:
            await self._do_execute(command)
            return

        game = self._find_game(command)

        if not game:
            raise CommandException(self, 'Found no game.')

        self._validate_game_state(game.state)

        if not self.player_only:
            await self._do_game_execute(command, game)
            return

        player = self._find_player(command.author)

        if not player:
            raise CommandException(self,
                                   'You are not a player in this game.')

        if (player not in game and game.state not in
                (GameState.GAME_OVER, GameState.STOPPED)):
            raise CommandException(
                self,
                'You are already a player in a different active game')

        await self._do_game_player_execute(
            command, game,
            game.discord_players[command.author])

    def _find_game(self, command: CommandMessage) -> Optional[DiscordGame]:
        assert self.games is not None

        if isinstance(command.channel, discord.TextChannel):
            if command.channel in self.games:
                return self.games[command.channel]
        else:
            for game in self.games.values():
                if command.author in game:
                    return game
        return None

    def _find_player(self, author: discord.User,
                     game: Optional[DiscordGame] = None
                     ) -> Optional[DiscordPlayer]:
        assert self.games is not None
        if game:
            if author in game:
                return game.discord_players[author]
        for other_game in self.games.values():
            if author in other_game:
                return other_game.discord_players[author]
        return None

    def _validate_game_state(self, state: GameState) -> None:
        if state not in self.requirements.valid_game_states:
            raise CommandException(self, 'Invalid game state.')

    async def _do_execute(self, command: CommandMessage) -> None:
        raise CommandException(self,
                               'Called execute in the abstract base class.')

    async def _do_game_execute(self, command: CommandMessage,
                               game: DiscordGame) -> None:
        raise CommandException(self,
                               'Called execute in the abstract base class.')

    async def _do_game_player_execute(self, command: CommandMessage,
                                      game: DiscordGame,
                                      player: DiscordPlayer) -> None:
        raise CommandException(self,
                               'Called execute in the abstract base class.')


# Player commands
class Ready(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            player_only=True,
            public_only=True,
            valid_game_states=[GameState.CREATED])

        help_text = ('Indicates that you are ready to begin the game. '
                     'The game begins when all players are ready.')

        super().__init__(
            'ready', 'r',
            games=games,
            requirements=requirements,
            help_text=help_text
        )

    async def _do_game_player_execute(self,
                                      command: CommandMessage,
                                      game: DiscordGame,
                                      player: DiscordPlayer) -> None:
        if player.ready:
            raise CommandException(self,
                                   '{} already ready.'.format(player))
        await game.ready(player)


class Unready(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = (
            'Indicates that you are no longer ready to begin the game. '
            'If the game is starting due to all players being ready, game '
            'start is canceled until all players are ready again.')
        requirements = Requirements(
            player_only=True,
            public_only=True,
            valid_game_states=[GameState.CREATED,
                               GameState.STARTING])
        super().__init__('unready',
                         games=games,
                         requirements=requirements,
                         help_text=help_text
                         )

    async def _do_game_player_execute(self,
                                      command: CommandMessage,
                                      game: DiscordGame,
                                      player: DiscordPlayer) -> None:
        if not player.ready:
            raise CommandException(self,
                                   '{} already unready.'.format(
                                       player))
        await game.unready(player)


# Join commands
class CreateJoin(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            public_only=True,
            not_active_player=True)
        help_text = ('Creates and joins a game if there is none.')
        super().__init__('createjoin', 'join',
                         games=games,
                         requirements=requirements,
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert self.games is not None

        if self._find_game(command):
            raise CommandException(self, 'game already running.')

        game = DiscordGame(command.channel, {})
        self.games[command.channel] = game
        await game.add_player(command.author)


class RecreateJoin(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            public_only=True,
            game_only=True,
            not_active_player=True,
            valid_game_states=(
                GameState.GAME_OVER,
                GameState.STOPPED))
        help_text = ("Recreates and joins a game if it's finished")
        super().__init__('recreatejoin', 'join',
                         games=games,
                         requirements=requirements,
                         help_text=help_text)

    async def _do_game_execute(self, command: CommandMessage,
                               game: DiscordGame) -> None:
        assert self.games is not None

        game = DiscordGame(command.channel, game.game.options)
        self.games[command.channel] = game
        await game.add_player(command.author)


class Join(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            public_only=True,
            game_only=True,
            not_active_player=True,
            valid_game_states=(
                GameState.CREATED,
                GameState.STARTING))
        help_text = 'Join a created game.'
        super().__init__('join',
                         games=games,
                         requirements=requirements,
                         help_text=help_text)

    async def _do_game_execute(self, command: CommandMessage,
                               game: DiscordGame) -> None:
        await game.add_player(command.author)


# General commands
class Shutdown(CommandType):
    def __init__(self, client: discord.Client):
        help_text = ('Turns off the bot.')
        requirements = Requirements(admin_only=True)
        super().__init__('shutdown', 'forcequit',
                         requirements=requirements,
                         help_text=help_text)
        self.client = client

    async def _do_execute(self, command: CommandMessage) -> None:
        await command.channel.send('Shutting down.')
        await self.client.close()


# Game commands
class ForceStart(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            public_only=True,
            admin_only=True,
            valid_game_states=(GameState.CREATED,))
        help_text = 'Start a game, regardless of ready state of players.'
        super().__init__('forcestart',
                         games=games,
                         requirements=requirements,
                         help_text=help_text)

    async def _do_game_execute(self, command: CommandMessage,
                               game: DiscordGame) -> None:
        await game.start()


class ListPlayers(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(game_only=True)
        help_text = ('List players that have joined.')
        super().__init__('players', 'listplayers',
                         games=games,
                         requirements=requirements,
                         help_text=help_text)

    async def _do_game_execute(self, command: CommandMessage,
                               game: DiscordGame) -> None:
        await game.send('```', *game.players,
                        sep='\n', end='```')
