"""Heavily inspired by incnone's necrobot for racing crypt of the necrodancer.
"""
from __future__ import annotations

import itertools
import typing
from typing import Container, Optional, List, Any, Sequence, cast
from dataclasses import dataclass

import discord  # type: ignore

from discord_game import DiscordPlayer, DiscordGame, GameState, BotPlayer
from player_game import Findable, PlayerGame, Player
from seat_typing import SeatException

from strings import RULES_STR, WIKIPEDIA_URL

GameDict = typing.Dict[discord.TextChannel, DiscordGame]


class CommandException(SeatException):
    def __init__(self, command: typing.Union[CommandType, CommandMessage],
                 message: str):
        super().__init__('Error running `{}`: {}'.format(
            command, message))


class ArgType:
    def __init__(self, arg_type: type,
                 optional: bool = False) -> None:
        self.arg_type: type = arg_type
        self.optional: bool = optional

    def __str__(self) -> str:
        if self.optional:
            return '[{}]'.format(self.arg_type)
        return str(self.arg_type)

    def convert(self, arg: str, game: Optional[PlayerGame] = None) -> Any:
        if arg == '' and self.optional:
            return None

        if issubclass(self.arg_type, Findable):
            assert game
            return self.arg_type.find(arg, game)

        # Gives "Too many arguments for "object" without cast
        return cast(type, self.arg_type)(arg)


class CommandMessage:
    """Wrapper for discord.message"""
    def __init__(self, message: discord.message) -> None:
        self._message = message

        self.author: discord.User = message.author
        self.channel = message.channel
        self.command: str = message.content.split(' ')[0][1:]
        self.args: List[Any] = message.content.split(' ')[1:]

        self.game: Optional[DiscordGame] = None
        self.player: Optional[DiscordPlayer] = None

    def __str__(self) -> str:
        return self.command

    @property
    def author_is_admin(self) -> bool:
        for role in self.author.roles:
            if role.name.lower() == 'game admin':
                return True
        return False

    def convert_arguments(self,
                          arg_types: Sequence[ArgType],
                          game: Optional[PlayerGame] = None) -> None:
        if len(self.args) > len(arg_types):
            raise CommandException(self, 'Too many arguments.')

        if len(self.args) < len([x for x in arg_types if not x.optional]):
            raise CommandException(self, 'Too few arguments.')

        new_args: List[Any] = []
        for arg, arg_type in itertools.zip_longest(
                self.args, arg_types, fillvalue=''):
            try:
                new_args.append(arg_type.convert(arg, game))
                # if issubclass(arg_type, Findable):
                #     assert game
                #     new_args.append(arg_type.find(arg, game))
                # else:
                #     # Gives "Too many arguments for "object" without cast
                #     new_args.append(cast(type, arg_type)(arg))

            except ValueError:
                raise CommandException(self, 'Invalid type for argument {}. '
                                       'Not convertible to {}'.format(
                                           arg, arg_type))
        self.args = new_args


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
                 args: Sequence[ArgType] = (),
                 help_text: str = 'This command has no help text.'
                 ) -> None:
        self.command_name_list = (command_name,) + command_names
        self.games = games
        self.requirements = requirements
        self.args = args
        self.help_text = help_text

    def __str__(self) -> str:
        return self.command_name

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
                          channel: typing.Union[discord.TextChannel,
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
            command.convert_arguments(self.args)
            await self._do_execute(command)
            return

        game = self._find_game(command)

        if not game:
            raise CommandException(self, 'Found no game.')

        command.convert_arguments(self.args, game.game)

        self._validate_game_state(game.state)

        command.game = game

        if not self.player_only:
            await self._do_execute(command)
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

        command.player = player

        await self._do_execute(command)

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
        raise NotImplementedError(
            '{}: Called do_execute in the abstract '
            'base class.'.format(command.command))


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

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.player
        assert command.game
        if command.player.ready:
            raise CommandException(
                self, '{} already ready.'.format(command.player))
        await command.game.ready(command.player)


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

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.player
        assert command.game

        if not command.player.ready:
            raise CommandException(
                self, '{} already unready.'.format(command.player))
        await command.game.unready(command.player)


class Propose(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = (
            'Propose a seat swap with another player, optionally bundling '
            'a bribe of garnets.')
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=[GameState.RUNNING])
        args = (ArgType(Player),
                ArgType(int, optional=True))
        super().__init__('propose',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        target: Player = command.args[0]
        garnets = command.args[1] if command.args[1] is not None else 0

        if command.player == target:
            raise CommandException(self, 'Cannot swap with yourself.')

        # TODO: public swaps

        command.player.add_proposal_to(target, garnets)

        await command.player.send(
            'Proposal sent to {target} offering {garnets} garnets.\n'
            'Those garnets are locked up until either player cancels the '
            'proposal.\n'
            'You now have {player.garnets} garnets.\n'
            'You can cancel the proposal with `!cancel.`'.format(
                target=target,
                garnets=garnets,
                player=command.player))

        await target.send(
            'Proposal received from {player} offering {garnets}.'.format(
                player=command.player,
                garnets=garnets))


class CancelProposal(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = (
            'Cancel an outgoing proposal. If you have multiple proposals you '
            'must specify to which player the proposal is.')
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=(GameState.RUNNING,))
        args = (ArgType(Player, optional=True),)
        super().__init__('cancel', 'cancelproposal',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        target: Optional[Player] = command.args[0]

        proposals = command.player.proposals

        if not proposals:
            raise CommandException(self, 'You have no outgoing proposals.')

        if target is not None:
            try:
                proposal = next(x for x in proposals if x.target == target)
            except StopIteration:
                raise CommandException(
                    self, 'You have no proposals to {}.'.format(target))

        elif len(proposals) == 1:
            proposal = proposals[0]

        else:
            raise CommandException(
                self, 'You have multiple proposals, '
                'please specify to which player.')

        command.game.game.cancel_proposal(proposal)
        await command.player.send(
            'Canceled proposal to {}.'.format(proposal.target))
        await proposal.target.send(
            '{} canceled their proposal to you.'.format(command.player))


class Proposals(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = 'List all your incoming and outgoing proposals.'
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=(GameState.RUNNING, GameState.PAUSED))
        super().__init__('proposals',
                         games=games,
                         requirements=requirements,
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        if not command.player.proposals:
            await command.player.send(
                'You have no incoming or outgoing proposals.')
            return

        await command.player.send(
            *(str(x) for x in command.player.proposals),
            start='```',
            end='```',
            sep='\n')


class Leave(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = 'Leave a game. Cannot leave a game in progress.'
        requirements = Requirements(
            player_only=True,
            valid_game_states=[GameState.CREATED,
                               GameState.STARTING])
        super().__init__('leave',
                         games=games,
                         requirements=requirements,
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.player
        assert command.game

        await command.game.remove_player(command.player)


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

    async def _do_execute(self, command: CommandMessage) -> None:
        assert self.games is not None
        assert command.game

        game = DiscordGame(command.channel, command.game.game.options)
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

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        await command.game.add_player(command.author)


# General commands
class Shutdown(CommandType):
    def __init__(self, client: discord.Client):
        help_text = ('Turns off the bot.')
        requirements = Requirements(public_only=True,  # User has no roles
                                    admin_only=True)
        super().__init__('shutdown', 'forcequit',
                         requirements=requirements,
                         help_text=help_text)
        self.client = client

    async def _do_execute(self, command: CommandMessage) -> None:
        await command.channel.send('Shutting down.')
        await self.client.close()


class Help(CommandType):
    def __init__(self) -> None:
        help_text = ('DM a help text, optionally for a specified command.')
        # TODO: args = (ArgType(CommandType),)
        super().__init__('help', 'info',
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        await command.author.send(
            'Type `!help` to see this help text.\n'
            'Type `!rules` for an overview and explanation on how the game '
            'works.\n'
            'Type `!commands` for a list of the commands available through '
            'direct messages.\n'
            'Most of the commands are only available to players that have '
            'joined the game.\n'
            'Knowing the rules, most of the commands should be '
            'self-explanatory, and they will '
            "give helpful error messages if you're invoking them "
            "incorrectly.\n"
            'Help for individual commands is not yet implemented, so you '
            'will have to experiment or ask :).'
        )
        if not isinstance(command.channel, discord.DMChannel):
            await command.channel.send('Help text sent via DM.')


class Rules(CommandType):
    def __init__(self) -> None:
        help_text = 'DM an overview of the rules for the Seat Exchange Game'
        # TODO: args = (ArgType(str),) ? for different subsections of rules
        super().__init__('rules', 'rule',
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        await command.author.send(
            RULES_STR.format(
                url=WIKIPEDIA_URL,
                start_garnets=20,  # self._game.options['start_garnets'],
                win_garnets=10,  # self._game.options['win_garnets'],
                lose_garnets=10,  # self._game.options['x_garnets']*-1
            ))
        if not isinstance(command.channel, discord.DMChannel):
            await command.channel.send('Rules sent via DM.')


class Commands(CommandType):
    def __init__(self, commands: Sequence[CommandType]) -> None:
        self.commands = commands
        help_text = 'DM full list of all available commands'
        # TODO: Split into Commands, GameCommands,
        # AdminCommands (PlayerCommands?)
        super().__init__('commands', 'command',
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        await command.author.send(
            ' '.join('`!' + str(x) + '`' for x in self.commands))
        if not isinstance(command.channel, discord.DMChannel):
            await command.channel.send('Command list sent via DM.')


class Source(CommandType):
    def __init__(self) -> None:
        help_text = 'Prints the URL to the source code.'
        super().__init__('source', 'sourcecode', 'code',
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        await command.channel.send(
            'https://github.com/h00701350103/seat_exchange')


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

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        await command.game.start()


class ListPlayers(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            game_only=True)
        help_text = ('List players that have joined.')
        super().__init__('players', 'listplayers',
                         games=games,
                         requirements=requirements,
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        if not list(command.game.players):
            command.game.send('No players joined.')
            return

        await command.channel.send('```', *command.game.players,
                                   sep='\n', end='```')


class AddBot(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            game_only=True,
            public_only=True,
            valid_game_states=[GameState.CREATED])
        args = (ArgType(str),)
        help_text = ('Add a bot with the specified name to the game.')
        super().__init__('addbot',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game

        name = cast(str, command.args[0])
        if not name.isalnum() or not name[0].isalpha():
            raise CommandException(
                self, 'Give the bot a proper name!')

        await command.game.add_bot(name.lower())


class RemoveBot(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            game_only=True,
            public_only=True,
            valid_game_states=[GameState.CREATED])
        args = (ArgType(BotPlayer),)
        help_text = ('Remove the specified bot from the game.')
        super().__init__('removebot',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        await command.game.remove_bot(command.args[0])
