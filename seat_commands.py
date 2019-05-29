"""Heavily inspired by incnone's necrobot for racing crypt of the necrodancer.
"""
from __future__ import annotations

import itertools
import asyncio
from enum import Enum, auto
import typing
from typing import Optional, List, Any, Sequence, cast
from dataclasses import dataclass

import discord  # type: ignore

import seat_typing
import discord_game
from discord_game import DiscordPlayer, DiscordGame, GameState, BotPlayer
from player_game import Findable, Player, Proposal

import strings

OPTIONAL_STR = "Brackets around an argument means that it's optional."
OWNER_ID = 84627464709472256
REVEAL_TIME = 5

GameDict = typing.Dict[discord.TextChannel, DiscordGame]


class CommandException(seat_typing.SeatException):
    def __init__(self, command: typing.Union[CommandType, CommandMessage],
                 message: str):
        super().__init__('Error running `{}`: {}'.format(
            command, message))


class ArgType:
    def __init__(self, arg_type: type,
                 optional: bool = False,
                 defaultvalue: Any = None,
                 name: Optional[str] = None) -> None:
        self.arg_type: type = arg_type
        self.optional: bool = optional
        self.defaultvalue: Any = defaultvalue
        self.name = name

    def __str__(self) -> str:
        if self.name is not None:
            name: str = self.name
        else:
            name = self.arg_type.__name__

        if self.optional:
            return '[{}]'.format(name)
        return name

    def convert(self, arg: str, **kwargs: Any) -> Any:
        if arg == '' and self.optional:
            return self.defaultvalue

        if issubclass(self.arg_type, Findable):
            return self.arg_type.find(arg, **kwargs)

        # Gives "Too many arguments for "object" without cast
        return cast(type, self.arg_type)(arg)


class CommandMessage:
    """Wrapper for discord.message"""
    def __init__(self, message: discord.message,
                 channel: seat_typing.SeatChannel) -> None:
        self._message = message

        self.author: discord.User = message.author
        self.channel = channel
        self.command: str = message.content.split(' ')[0][1:]
        self.args: List[Any] = message.content.split(' ')[1:]

        self.game: Optional[DiscordGame] = None
        self.player: Optional[DiscordPlayer] = None

    def __str__(self) -> str:
        return self.command

    @property
    def author_is_admin(self) -> bool:
        if self.author.id == OWNER_ID:
            return True
        if not isinstance(self.author, discord.Member):
            return False
        for role in self.author.roles:
            if role.name.lower() == 'game admin':
                return True
        return False

    def convert_arguments(self,
                          arg_types: Sequence[ArgType],
                          **kwargs: Any,
                          ) -> typing.List[typing.Any]:
        if len(self.args) > len(arg_types):
            raise CommandException(self, 'Too many arguments.')

        if len(self.args) < len([x for x in arg_types if not x.optional]):
            raise CommandException(self, 'Too few arguments.')

        new_args: List[Any] = []
        for arg, arg_type in itertools.zip_longest(
                self.args, arg_types, fillvalue=''):
            try:
                new_args.append(arg_type.convert(arg, **kwargs))

            except ValueError:
                raise CommandException(self, 'Invalid type for argument {}. '
                                       'Not convertible to {}'.format(
                                           arg, arg_type))
        return new_args


def format_list_with_conjunction_and_comma(sequence: typing.Iterable[Any],
                                           conjunction: str) -> str:
    if not sequence:
        raise NotImplementedError('Empty list.')

    res = ''
    str_sequence = list(map(str, sequence))

    for seq in str_sequence[:-2]:
        res += seq + ', '

    if len(str_sequence) > 1:
        res += '{} {} '.format(str_sequence[-2], conjunction)

    return res + str_sequence[-1]


@dataclass
class Requirements:
    public_only: bool = False
    private_only: bool = False
    admin_only: bool = False
    game_only: bool = False
    real_life_game_only: bool = False
    not_active_player: bool = False

    # implies game_only
    valid_game_states: typing.Iterable[GameState] = GameState
    player_only: bool = False

    def human_readable(self) -> List[str]:
        result = []
        if self.public_only:
            result.append('in a public channel')
        if self.private_only:
            result.append('in a private channel')
        if self.admin_only:
            result.append("you're an admin")
        if self.not_active_player:
            result.append("you're not a player in an active game")
        if self.game_only or self.player_only:
            result.append('there is a valid game')
        if self.player_only:
            result.append("you're a player in that game")
        if self.valid_game_states != GameState:
            result.append(
                'the game is {}.'.format(
                    format_list_with_conjunction_and_comma(
                        self.valid_game_states, 'or')))
        return result


class CommandTag(Enum):
    INFO = auto()
    MANAGEMENT = auto()
    GAMEPLAY = auto()
    OPTIONS = auto()
    REALLIFE = auto()
    ADMIN = auto()


class CommandType():
    def __init__(self,
                 command_name: str,
                 *command_names: str,
                 games: Optional[GameDict] = None,
                 requirements: Requirements = Requirements(),
                 args: Sequence[ArgType] = (),
                 help_text: str = 'This command has no help text.',
                 tag: CommandTag
                 ) -> None:
        self.command_name_list = (command_name,) + command_names
        self.games = games
        self.requirements = requirements
        self.args = args
        self.help_text = help_text
        self.tag = tag

    def __str__(self) -> str:
        return self.command_name

    @property
    def command_name(self) -> str:
        return self.command_name_list[0]

    @property
    def help(self) -> str:
        return '```{name}\n{arg_format}\n{help_text}```'.format(
            name=self.command_name,
            arg_format=self.arg_format,
            help_text=self.help_text)

    @property
    def arg_format(self) -> str:
        return '!{}{}'.format(
            self.command_name,
            ''.join(' '+str(arg) for arg in self.args))

    @property
    def game_only(self) -> bool:
        return (self.requirements.game_only
                or self.requirements.player_only
                or self.requirements.valid_game_states != GameState
                or self.requirements.real_life_game_only)  # TODO

    @property
    def player_only(self) -> bool:
        return self.requirements.player_only

    def _validate_channel(self,
                          channel: seat_typing.SeatChannel) -> None:
        # channel can also be group dm
        if self.requirements.public_only and not channel.is_public:
            raise CommandException(self, 'Not a public channel.')
        if (self.requirements.private_only and not channel.is_dm):
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
            await self._do_execute(command)
            return

        game = self._find_game(command)

        if not game:
            raise CommandException(self, 'Found no game.')

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

        if command.channel.is_public:
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
            help_text=help_text,
            tag=CommandTag.MANAGEMENT
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
                         help_text=help_text,
                         tag=CommandTag.MANAGEMENT
                         )

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.player
        assert command.game

        if not command.player.ready:
            raise CommandException(
                self, '{} already unready.'.format(command.player))
        await command.game.unready(command.player)


class ProposeSeatSwap(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = (
            'Propose a seat swap with another player, optionally bundling '
            'a bribe of garnets.')
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=[GameState.RUNNING])
        args = (ArgType(Player),
                ArgType(int, optional=True, defaultvalue=0))
        super().__init__('propose',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player
        target: Player
        garnets: int

        target, garnets = command.convert_arguments(
            self.args, game=command.game)

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


class AcceptSeatSwap(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = (
            'Accept an incoming proposal. If you have multiple proposals you '
            'must specify from which player the proposal is.')
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=(GameState.RUNNING,))
        args = (ArgType(Proposal, optional=True),)  # TODO
        super().__init__('accept', 'acceptproposal', 'acceptincoming',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        proposal: Proposal = command.convert_arguments(
            self.args, player=command.player)[0]
        proposals = command.player.proposals

        if not proposals:
            raise CommandException(self, 'You have no incoming proposals.')

        if proposal is None and len(proposals) != 1:
            raise CommandException(
                self, 'You have multiple incoming proposals, '
                'please specify from which player.')

        if proposal is not None:
            if proposal.target != command.player:
                raise CommandException(
                    self, 'You can only accept proposals others sent to you.')

            source = proposal.source

        else:  # len(proposals) == 1:
            proposal = proposals[0]
            source = proposal.source

        if source.swapped:
            await source.send(
                '{} tried accepting your proposal, but you have already '
                'swapped.'
                'Proposal canceled.'.format(
                    command.player))
            command.game.cancel_proposal(proposal)
            raise CommandException(
                self, '{} has already swapped this round. Proposal canceled.'
                ''.format(source))

        command.game.accept_proposal(proposal)

        await command.player.send(
            'Accepted proposal from {source}, gaining {garnets} garnets.\n'
            'You now have {player.garnets} garnets.\n'
            'Your new seat is {player.seat}.\n'
            "{source}'s new seat is {source.seat}.\n" .format(
                player=command.player,
                source=source,
                garnets=proposal.garnets))

        await source.send(
            '{player} accepted your proposal, gaining {garnets} garnets.\n'
            'Your new seat is {source.seat}.\n'
            "{player}'s new seat is {player.seat}.\n".format(
                player=command.player,
                source=source,
                garnets=proposal.garnets))


class CancelSeatSwap(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = (
            'Cancel a proposal. If you have multiple proposals you '
            'must specify with which player the proposal is.')
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=(GameState.RUNNING,))
        args = (ArgType(Proposal, optional=True),)
        super().__init__('cancel', 'reject',
                         'cancelproposal', 'rejectproposal',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        proposal: Proposal = command.convert_arguments(
            self.args, player=command.player)[0]

        proposals = command.player.proposals

        if not proposals:
            raise CommandException(self, 'You have no proposals.')

        if proposal is None and len(proposals) != 1:
            raise CommandException(
                self, 'You have multiple incoming proposals, '
                'please specify from which player.')

        if proposal is None:
            proposal = proposals[0]

        if proposal.source == command.player:
            other = proposal.target
        else:
            other = proposal.source

        command.game.cancel_proposal(proposal)
        await command.player.send(
            'Canceled proposal with {}.'.format(other))
        await other.send(
            '{} canceled their proposal with you.'.format(command.player))


class CreateBotSwap(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = (
            'Propose a seat swap between two bots, optionally bundling '
            'a bribe of garnets. Your bribe must be higher than either bots '
            'highest offer for them to accept it, unless neither has any '
            'offers. If several botswaps have the same bribe they\'re '
            'resolved in a random order.\n'
            'If you propose a botswap listing the same bot twice, that is '
            'interpreted as a bribe for the bot to stay still and not accept '
            'any other proposals. The bribe still needs to exceed other '
            'proposals.')
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=[GameState.RUNNING])
        args = (ArgType(BotPlayer),
                ArgType(BotPlayer),
                ArgType(int, optional=True, defaultvalue=0))
        super().__init__('botswap', 'proposebotswap',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        source: BotPlayer
        target: BotPlayer
        garnets: int
        source, target, garnets = (
            command.convert_arguments(self.args, game=command.game))

        botswaps = [
            x for x in command.game.botswaps
            if source in x and target in x and x.guarantor == command.player]

        if botswaps:
            raise CommandException(
                self, 'Found a botswap between {} and {} sponsored by you.'
                ''.format(source, target))

        botswap = discord_game.BotSwap(
            source, target, command.player, garnets)

        command.game.botswaps.add(botswap)

        await command.player.send(
            'Created: {}'.format(botswap))


class CancelBotSwap(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = 'Cancel a proposed seat swap between two bots'
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=[GameState.RUNNING])
        args = (ArgType(BotPlayer),
                ArgType(BotPlayer))
        super().__init__('cancelbotswap',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        source: BotPlayer
        target: BotPlayer
        source, target = command.convert_arguments(self.args,
                                                   game=command.game)

        try:
            botswap = next(x for x in command.game.botswaps
                           if (source in x and target in x
                               and x.guarantor == command.player))
        except StopIteration:
            raise CommandException(
                self, 'Found no botswaps between {} and {} sponsored by you.'
                ''.format(source, target))

        command.game.botswaps.remove(botswap)

        await command.player.send(
            'Canceled: {}'.format(botswap))


class DonateGarnets(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = (
            'Donate a number of garnets to a player.')
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=[GameState.RUNNING])
        args = (ArgType(Player),
                ArgType(int))
        super().__init__('donate', 'donategarnets',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.player

        target: Player
        garnets: int
        target, garnets = command.convert_arguments(self.args,
                                                    game=command.game)

        await command.player.donate_garnets(target, garnets)

        await command.player.send(
            'You have sent {garnets} garnets to {target}.\n'
            'You now have {player.garnets} garnets.'.format(
                garnets=garnets,
                target=target,
                player=command.player))

        await target.send(
            '{player} has sent {garnets} garnets to you.\n'
            'You now have {target.garnets} garnets.'.format(
                garnets=garnets,
                target=target,
                player=command.player))


# Game info
class PrintProposals(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = 'List all your incoming and outgoing proposals.'
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=(GameState.RUNNING, GameState.PAUSED))
        super().__init__('proposals',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        if not command.player.proposals:
            await command.player.send(
                'You have no incoming or outgoing proposals.')
            return

        await command.player.send(
            *(str(x) for x in command.player.proposals),
            start='```\n',
            end='```',
            sep='\n')


class PrintBotSwaps(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = 'Print all botswaps sponsored by you.'
        requirements = Requirements(
            player_only=True,
            private_only=True,
            valid_game_states=[GameState.RUNNING])
        super().__init__('botswaps', 'printbotswaps',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        botswaps = (x for x in command.game.botswaps
                    if x.guarantor == command.player)

        if not botswaps:
            await command.player.send("Found no botswaps sponsored by you.")
            return

        await command.player.send(
            *botswaps, start='```\n', end='```', sep='\n')


class PrintPlayers(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            game_only=True)
        help_text = ('List players that have joined.')
        super().__init__('players', 'listplayers',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        if not list(command.game.players):
            await command.game.send('No players joined.')
            return

        await command.channel.send(*command.game.players, sep='\n',
                                   start='```\n', end='```')


class PrintGarnets(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            game_only=True,
            player_only=True)
        help_text = ('Print how many garnets you have.')
        super().__init__('garnets', 'printgarnets', 'garnet',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.player

        await command.player.send(command.player.garnets)


class PrintSeating(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            game_only=True,
            player_only=True)
        help_text = ('Print seat and assigned numbers for all players.')
        super().__init__('seating', 'printseating',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        assigned_numbers = command.player.assigned_numbers

        await command.player.send(
            '\n'.join(
                '{0:>3} {1:>4} {2}'.format(
                    player.seat,
                    assigned_numbers.get(player, ''),
                    player)
                for player in command.game.players),
            start='```', end='```',
        )


class AssignNumber(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            game_only=True,
            player_only=True)
        help_text = ('Assign a deduced number to a player. '
                     'For use with `!seating`')
        args = (ArgType(Player),
                ArgType(int))
        super().__init__('assign', 'assignnumber',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        target: Player
        number: int
        target, number = command.convert_arguments(self.args,
                                                   game=command.game)

        command.player.assigned_numbers[target] = number

        await command.player.send('Assigned {} to {}.'.format(
            target, number))


class UnassignNumber(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            game_only=True,
            player_only=True)
        help_text = ('Remove the assigned number from a player. '
                     'For use with `!seating`')
        args = (ArgType(Player),)
        super().__init__('unassign', 'unassignnumber',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.GAMEPLAY)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        assert command.player

        target: Player = command.convert_arguments(
            self.args, game=command.game)[0]
        number = command.player.assigned_numbers.pop(target)

        await command.player.send('Unassigned {} from {}.'.format(
            number, command.args[0]))


# Game management commands
class Create(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            public_only=True)
        help_text = ('Creates a seat game.')
        super().__init__('create',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.MANAGEMENT)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert self.games is not None

        if self._find_game(command):
            raise CommandException(self, 'game already running.')

        game = DiscordGame(command.channel, {})
        self.games[command.channel] = game
        await game.send(
            'Game created. Game will start when all players are `!ready` and '
            'at least {}  players, of which {} human, have joined.'.format(
                discord_game.MIN_PLAYERS,
                discord_game.MIN_HUMAN_PLAYERS))


class Recreate(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            public_only=True,
            game_only=True,
            valid_game_states=(
                GameState.GAME_OVER,
                GameState.STOPPED))
        help_text = ("Recreates a finished game with the same options.")
        super().__init__('recreate',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.MANAGEMENT)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert self.games is not None
        assert command.game

        game = DiscordGame(command.channel, command.game.options)
        self.games[command.channel] = game
        await game.send(
            'Game recreated with the same options. Game will start when all '
            'players are `!ready`.')


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
                         help_text=help_text,
                         tag=CommandTag.MANAGEMENT)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        await command.game.add_user(command.author)


class CreateJoin(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            public_only=True,
            not_active_player=True)
        help_text = ('Creates and joins a game if there is none.')
        super().__init__('createjoin', 'join',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.MANAGEMENT)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert self.games is not None

        if self._find_game(command):
            raise CommandException(self, 'game already running.')

        game = DiscordGame(command.channel, {})
        self.games[command.channel] = game
        await game.send(
            'Game created. Game will start when all players are `!ready`.')
        await game.add_user(command.author)


class RecreateJoin(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            public_only=True,
            game_only=True,
            not_active_player=True,
            valid_game_states=(
                GameState.GAME_OVER,
                GameState.STOPPED))
        help_text = ("Recreates a finished game and joins it.")
        super().__init__('recreatejoin', 'join',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.MANAGEMENT)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert self.games is not None
        assert command.game

        game = DiscordGame(command.channel, command.game.options)
        self.games[command.channel] = game
        await game.add_user(command.author)
        await game.send(
            'Game recreated with the same options. Game will start when all '
            'players are `!ready`.')


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
                         help_text=help_text,
                         tag=CommandTag.MANAGEMENT)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.player
        assert command.game

        await command.game.remove_discord_player(command.player)


class AddBot(CommandType):
    def __init__(self, games: GameDict) -> None:
        requirements = Requirements(
            game_only=True,
            public_only=True,
            valid_game_states=[GameState.CREATED])
        args = (ArgType(str, name='name'),)
        help_text = ('Add a bot with the specified name to the game.')
        super().__init__('addbot', 'ab',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.MANAGEMENT)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game

        name: str = command.convert_arguments(self.args, game=command.game)[0]

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
                         help_text=help_text,
                         tag=CommandTag.MANAGEMENT)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        bot: BotPlayer = command.convert_arguments(
            self.args, game=command.game)[0]
        await command.game.remove_bot(bot)


class RoundLength(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = ('Print or set the round length.')
        args = (ArgType(int, optional=True),)
        requirements = Requirements(
            public_only=True,
            game_only=True)
        super().__init__('roundlength',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.OPTIONS)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game

        arg: Optional[int] = command.convert_arguments(
            self.args, game=command.game)[0]

        if arg is None:
            await command.channel.send(
                'Current round length is: {} seconds.'.format(
                    command.game.options['round_length']))
            return

        command.game.options['round_length'] = arg
        await command.channel.send('Round length set to {} seconds.'.format(
            arg))


class StreakLength(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = ('Print or set the streak length.')
        args = (ArgType(int, optional=True),)
        requirements = Requirements(
            public_only=True,
            game_only=True)
        super().__init__('streaklength',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.OPTIONS)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game

        arg: Optional[int] = command.convert_arguments(
            self.args, game=command.game)[0]

        if arg is None:
            await command.channel.send(
                'Current streak length is {}.'.format(
                    command.game.win_streak_length))
            return

        command.game.options['win_streak_length'] = arg
        await command.channel.send('Streak length set to {}.'.format(
            arg))


class XCount(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = ('Print or set the X count.')
        args = (ArgType(int, optional=True),)
        requirements = Requirements(
            public_only=True,
            game_only=True)
        super().__init__('xcount', 'x_count',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.OPTIONS)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game

        arg: Optional[int] = command.convert_arguments(
            self.args, game=command.game)[0]

        if arg is None:
            await command.channel.send(
                'Current x count is {}.'.format(
                    command.game.x_count))
            return

        command.game.options['x_count'] = arg
        await command.channel.send('X count set to {}.'.format(
            arg))


class RevealLongestStreak(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = ('Print or set whether the longest streak is revealed at '
                     'the beginning of each round.')
        args = (ArgType(str, name='bool', optional=True),)
        requirements = Requirements(
            public_only=True,
            game_only=True)
        super().__init__('reveallongeststreak', 'revealstreak',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.OPTIONS)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game

        arg: Optional[str] = command.convert_arguments(
            self.args, game=command.game)[0]

        if arg is None:
            await command.channel.send(
                'Reveal longest streak is set to: {}.'.format(
                    command.game.options['reveal_longest_streak']))
            return

        if arg.lower() not in ('true', 'false'):
            raise CommandException(self, 'argument must be `true` or `false`.')

        argvalue = arg.lower() == 'true'

        command.game.options['reveal_longest_streak'] = argvalue
        await command.channel.send('Reveal longest streak set to {}.'.format(
            argvalue))


class Pause(CommandType):  # TODO
    async def _do_execute(self, command: CommandMessage) -> None:
        pass


class Resume(CommandType):  # TODO
    async def _do_execute(self, command: CommandMessage) -> None:
        pass


class Stop(CommandType):  # TODO
    async def _do_execute(self, command: CommandMessage) -> None:
        pass


# kick, leave game-in-progress?

# General commands
class Help(CommandType):
    def __init__(self,
                 command_dict: typing.Dict[str, typing.List[CommandType]]
                 ) -> None:

        help_text = (
            'DM a help text, optionally for a specified command.\n'
            'Some commands are callable by several different aliases, these '
            'will all be listed when running help on either of them (for '
            'example, this command is also known as `info`).\n'
            'In the "Usage" line some parameters may be written with '
            'brackets. This means they are optional and can be left out. '
            'The help text will often explain what is the difference between '
            'specifying the parameter and not.\n'
        )
        args = (ArgType(str, optional=True, name='command'),)
        super().__init__('help', 'info',
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.INFO)
        self.command_dict = command_dict

    async def _do_execute(self, command: CommandMessage) -> None:
        user_channel = await seat_typing.SeatChannel.from_user(command.author)
        if not command.channel.is_dm:
            await command.channel.send('Help text sent via DM.')

        key: Optional[str] = command.convert_arguments(self.args)[0]

        print('{} called help {}'.format(command.author, key))

        if not key:
            await user_channel.send(strings.HELP_HELP)
            return

        key = key.lower().lstrip('!').rstrip('.')

        if key not in self.command_dict:
            raise CommandException(
                self, 'Cannot find help for unknown command `{}`.'.format(
                    command.args[0]))

        full_text = ''

        if len(self.command_dict[key]) > 1:
            full_text = 'Found {} commands matching {}.\n'.format(
                len(self.command_dict[key]), key)

        for help_cmd in self.command_dict[key]:
            full_text += 'Help for `{}`:\n'.format(
                '`, `'.join(str(cmd) for cmd in help_cmd.command_name_list))

            full_text += '  {}\n'.format(
                help_cmd.help_text.replace('\n', '\n  '))

            full_text += '  Usage: `{}`\n'.format(help_cmd.arg_format)
            reqs_readable = help_cmd.requirements.human_readable()
            if reqs_readable:
                full_text += '  Can only be run if {}\n'.format(
                    format_list_with_conjunction_and_comma(
                        reqs_readable, 'and'))

        await user_channel.send(full_text)


class Rules(CommandType):
    def __init__(self) -> None:
        help_text = ('Print the rules index, or if a section is specified '
                     'that section is shown.')
        requirements = Requirements(
            private_only=True)
        args = (ArgType(str, optional=True, name='section'),)
        super().__init__('rules', 'rule',
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.INFO)

    async def _do_execute(self, command: CommandMessage) -> None:
        user_channel = await seat_typing.SeatChannel.from_user(command.author)
        key: Optional[str] = command.convert_arguments(self.args)[0]

        print('{} called rules {}'.format(command.author, key))

        if not key:
            await user_channel.send(strings.RULES_INDEX)
            return

        key = key.lower().rstrip('.')

        if key not in strings.RULES_DICT:
            raise CommandException(
                self, "Unknown rules section `{}`.".format(key))

        await user_channel.send(strings.RULES_DICT[key])


class Commands(CommandType):
    def __init__(self, commands: Sequence[CommandType]) -> None:
        self.commands = commands
        help_text = 'Print list of available commands'
        requirements = Requirements(private_only=True)
        # TODO: Split into Commands, GameCommands,
        # AdminCommands (PlayerCommands?)
        super().__init__('commands', 'command',
                         help_text=help_text,
                         requirements=requirements,
                         tag=CommandTag.INFO)

    async def _do_execute(self, command: CommandMessage) -> None:
        await command.author.send(
            ' '.join('`!' + str(x) + '`' for x in self.commands))
        # TODO do it like rules


class Source(CommandType):
    def __init__(self) -> None:
        help_text = 'Prints the URL to the source code.'
        super().__init__('source', 'sourcecode', 'code',
                         help_text=help_text,
                         tag=CommandTag.INFO)

    async def _do_execute(self, command: CommandMessage) -> None:
        await command.channel.send(
            'https://github.com/h00701350103/seat_exchange')


# RealLifeGame commands
class CreateRealLifeGame(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = 'Create an IRL game.'
        requirements = Requirements(
            public_only=True)
        super().__init__('createirl',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.REALLIFE)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert self.games is not None

        if self._find_game(command):
            raise CommandException(self, 'game already running.')

        game = DiscordGame(command.channel, {})
        self.games[command.channel] = game
        await game.send('Real-life game created.')


class Reveal(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = ('Reveal the private number of a real-life player '
                     'for {} seconds.'.format(REVEAL_TIME))
        requirements = Requirements(
            real_life_game_only=True)
        args = (ArgType(Player),)
        super().__init__('reveal',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.REALLIFE)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game is not None
        player: Player

        player = command.convert_arguments(
            self.args, game=command.game)[0]

        message = await command.game.channel.wait_send(
            'Player {}\'s number is {}.'.format(
                player, player.number))

        await asyncio.sleep(REVEAL_TIME)

        await message.edit(content='<deleted>')


class Swap(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = 'Swap two players'
        requirements = Requirements(
            real_life_game_only=True)
        args = (ArgType(Player), ArgType(Player))
        super().__init__('swap',
                         games=games,
                         requirements=requirements,
                         args=args,
                         help_text=help_text,
                         tag=CommandTag.REALLIFE)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game is not None

        source: Player
        target: Player

        source, target = command.convert_arguments(
            self.args, game=command.game)

        source.swap(target)

        await command.game.send('Swapped {} and {}.'.format(source, target))


class RealLifeSeating(CommandType):
    def __init__(self, games: GameDict) -> None:
        help_text = 'Reveal seating of all the players.'
        requirements = Requirements(
            real_life_game_only=True)
        super().__init__('seating',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.REALLIFE)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        await command.game.send(
            '\n'.join(
                '{0:>3} {1}'.format(
                    player.seat,
                    player)
                for player in command.game.players),
            start='```', end='```',
        )


# Admin commands
class Shutdown(CommandType):
    def __init__(self, client: discord.Client):
        help_text = ('Turns off the bot.')
        requirements = Requirements(admin_only=True)
        super().__init__('shutdown', 'forcequit',
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.ADMIN)
        self.client = client

    async def _do_execute(self, command: CommandMessage) -> None:
        await command.channel.wait_send('Shutting down.')
        await self.client.close()


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
                         help_text=help_text,
                         tag=CommandTag.ADMIN)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        await command.game.start()


class ForceStop(CommandType):
    def __init__(self, games: GameDict):
        help_text = ('Stops game.')
        requirements = Requirements(
            public_only=True,
            game_only=True,
            admin_only=True,
            # valid_game_states=(GameState.RUNNING,
            #                    GameState.PAUSED)
        )
        super().__init__('forcestop',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.ADMIN)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game

        command.game.state = GameState.STOPPED
        await command.game.send('Game stopped.')


class ForceNewRound(CommandType):
    def __init__(self, games: GameDict):
        help_text = ('Forces next round to start.')
        requirements = Requirements(
            public_only=True,
            game_only=True,
            admin_only=True,
            valid_game_states=(GameState.RUNNING,))
        super().__init__('forcenewround', 'newround',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.ADMIN)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game

        await command.game.force_new_round()


class ForceSeatNumbers(CommandType):  # TODO
    def __init__(self, games: GameDict) -> None:
        help_text = 'Reveal seating and numbers of all the players.'
        requirements = Requirements(
            admin_only=True,
            game_only=True)
        super().__init__('forceseatnumbers',
                         games=games,
                         requirements=requirements,
                         help_text=help_text,
                         tag=CommandTag.ADMIN)

    async def _do_execute(self, command: CommandMessage) -> None:
        assert command.game
        await command.game.send(
            '\n'.join(
                '{0:>2} {1:>2}  {2}'.format(
                    player.seat,
                    player.number,
                    player)
                for player in command.game.players),
            start='```', end='```',
        )
