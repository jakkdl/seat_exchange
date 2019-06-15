# pragma pylint: disable=missing-docstring
from __future__ import annotations

import random
import asyncio
import math

from enum import Enum, auto
import typing
from typing import Dict, Optional, Any, cast


import discord  # type: ignore

import seat_strings
import seat_commands as commands
from seat_game import SeatGame
from seat_typing import (SeatException, SeatChannel, DiscordUser)
from discord_seat_game_subclasses import (
    CommonPlayer, DiscordPlayer, BotPlayer, Proposal, BotSwap, CP,
    ListProposals)

DEFAULT_ROUND_LENGTH = 300
DEFAULT_PUBLIC_SWAPS = False
BOT_ID = 573077970445402113
MIN_HUMAN_PLAYERS = 1
MIN_PLAYERS = 2


class DiscordGameException(SeatException):
    pass


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


class ReactFunction:  # pylint: disable=too-few-public-methods
    def __init__(self,
                 message: discord.Message,
                 emoji: str,
                 react_needed: int) -> None:
        self.message = message
        self.emoji = emoji
        self.react_needed = react_needed

    async def on_react(self,
                       reaction: discord.Reaction,
                       user: DiscordUser) -> None:
        raise NotImplementedError('Virtual function.')


class NewRoundEarly(ReactFunction):  # pylint: disable=too-few-public-methods
    def __init__(self, game: DiscordGame,
                 message: discord.Message,
                 emoji: str,
                 react_needed: int) -> None:
        super().__init__(message, emoji, react_needed)
        self.game = game

    async def on_react(self,
                       reaction: discord.Reaction,
                       user: DiscordUser) -> None:
        print('on_react')
        if reaction.emoji != self.emoji:
            print('wrong_emoji')
            return
        if user not in self.game and user.discord_id != BOT_ID:
            await reaction.remove(user)
            await user.send(
                'Error: You are not allowed to vote on that message.')
            return
        if reaction.count < self.react_needed:
            return

        await self.game.force_new_round()


class DiscordGame(SeatGame[CommonPlayer]):
    # pylint: disable=too-many-instance-attributes
    default_options: typing.Dict[str, Any] = seat_strings.DEFAULT_OPTIONS

    def __init__(self,
                 channel: SeatChannel,
                 options: Optional[Dict[str, Any]] = None) -> None:
        self.options = options if options is not None else {}
        if 'round_length' not in self.options:
            self.options['round_length'] = DEFAULT_ROUND_LENGTH
        if 'public_swaps' not in self.options:
            self.options['public_swaps'] = DEFAULT_PUBLIC_SWAPS
        for key in self.default_options:
            if key not in self.options:
                self.options[key] = self.default_options[key]

        super().__init__(self.options)

        self.channel: SeatChannel = channel
        self.state: GameState = GameState.CREATED
        self.reactable_messages: Dict[discord.Message, ReactFunction] = {}
        self.command_list: typing.List[commands.CommandType] = []
        self.command_dict: Dict[str, typing.List[commands.CommandType]] = {}

        # TODO: Remove, but requires some refactoring
        self.discord_players: Dict[DiscordUser, DiscordPlayer] = {}
        self.bots: Dict[str, BotPlayer] = {}

        self._initialize_commands()

    def _initialize_commands(self) -> None:
        self.command_list += [
            # Game management
            commands.Join(self),
            commands.Recreate(self),
            commands.RecreateJoin(self),

            commands.Leave(self),
            commands.AddBot(self),
            commands.RemoveBot(self),

            commands.Ready(self),
            commands.Unready(self),

            # Options
            commands.StreakLength(self),
            commands.XCount(self),
            commands.RoundLength(self),
            # commands.RevealLongestStreak(self),

            # game info
            commands.PrintProposals(self),
            commands.PrintBotSwaps(self),
            commands.PrintPlayers(self),
            commands.PrintGarnets(self),

            commands.PrintSeating(self),
            commands.AssignNumber(self),
            commands.UnassignNumber(self),

            # gameplay
            commands.ProposeSeatSwap(self),
            commands.AcceptSeatSwap(self),
            commands.CancelSeatSwap(self),

            commands.CreateBotSwap(self),
            commands.CancelBotSwap(self),
            commands.DonateGarnets(self),

            # real life game
            commands.Reveal(self),
            commands.Swap(self),
            commands.RealLifeSeating(self),

            # admin
            commands.ForceStart(self),
            commands.ForceStop(self),
            commands.ForceSwap(self),
            commands.ForceNewRound(self),
            commands.ForceSeatNumbers(self),
        ]

        # TODO
        # pylint: disable=duplicate-code
        for command in self.command_list:
            for command_name in command.command_name_list:
                if command_name not in self.command_dict:
                    self.command_dict[command_name] = [command]
                else:
                    self.command_dict[command_name].append(command)

    def recreate(self) -> None:
        self.state = GameState.CREATED
        self.reactable_messages.clear()
        self.discord_players.clear()
        self.bots.clear()
        super().recreate()

    async def send(self,
                   *args: Any,
                   **kwargs: str) -> discord.Message:
        return await self.channel.send(*args, **kwargs)

    async def ready(self, author: DiscordPlayer) -> None:
        if author.ready:
            raise DiscordGameException('{} already ready.'.format(author))
        author.ready = True

        await self.send('{} ready.'.format(author))

        if self._all_players_ready():
            await self.start_game_countdown()

    def _all_players_ready(self) -> bool:
        for player in self.discord_players.values():
            if not player.ready:
                return False
        return True

    async def start_game_countdown(self, timer: int = 10) -> None:
        if self.player_count - len(self.bots) < MIN_HUMAN_PLAYERS:
            return
        if self.player_count < MIN_PLAYERS:
            return

        self.state = GameState.STARTING

        for time in range(timer, 0, -5):
            await self.send('Starting game in {} seconds.'.format(time))
            await asyncio.sleep(time)

            if self.state != GameState.STARTING:
                await self.send('Countdown canceled.')
                return

        await self.start()

    async def unready(self, author: DiscordPlayer) -> None:
        if not author.ready:
            raise DiscordGameException("{} player already unready.")
        author.ready = False

        await self.send('{} unready.'.format(author))

        if self.state == GameState.STARTING:
            self.state = GameState.CREATED

    # Tihi, don't feel like this is correct usage of this operator, but I
    # couldn't refrain.
    def __contains__(self,
                     key: typing.Union[discord.user, DiscordPlayer]) -> bool:
        return (key in self.discord_players
                or key in self.discord_players.values())

    @property
    def running(self) -> bool:
        return self.state == GameState.RUNNING

    async def start(self) -> None:
        if self.state not in (GameState.CREATED, GameState.STARTING):
            raise DiscordGameException(
                'Error: Invalid game state: {}'.format(self.state))

        for player in self.players:
            player.new_round()

        await self._message_start_game()
        self.state = GameState.RUNNING

        await self._round_loop()

    async def force_new_round(self) -> None:
        await self.new_discord_round()
        await self._round_loop()

    async def _round_loop(self) -> None:
        while True:
            current_round = self.current_round
            if self.options['round_length'] < 0:
                return
            await asyncio.sleep(self.options['round_length'])
            if self.state != GameState.RUNNING:
                print('Game not running, quitting silently.')
                return
            if current_round != self.current_round:
                print('Next round prematurely started.')
                return
            await self.new_discord_round()

    async def _message_start_game(self) -> None:  # TODO
        await self.channel.wait_send(self._current_options_string())
        await self._message_new_round()
        await self._message_react_earlynewround()

    async def _resolve_botswaps_proposals(self) -> None:
        def garnet_key(proposal: Proposal[CP]) -> int:
            return proposal.garnets

        bot_proposals: ListProposals = []
        botswap_set: typing.Set[BotSwap] = set()

        for bot in self.bots.values():
            bot_proposals += [x for x in bot.incoming_proposals
                              if not x.source.swapped]
            botswap_set.update(bot.botswaps)

        botswaps = list(botswap_set)
        random.shuffle(botswaps)
        botswaps.sort(key=garnet_key, reverse=True)

        for botswap in botswaps:
            source_proposals = [x for x in bot_proposals
                                if x.target == botswap.source]
            target_proposals = [x for x in bot_proposals
                                if x.target == botswap.target]

            source_proposals.sort(key=garnet_key)
            target_proposals.sort(key=garnet_key)

            def list_get(proposals: typing.List[Proposal[CommonPlayer]],
                         index: int) -> int:
                if index < len(proposals):
                    return proposals[index].garnets
                return 0

            source_max = list_get(source_proposals, 0)
            target_max = list_get(target_proposals, 0)
            total = source_max+target_max

            # to avoid exploit where another player screws a botswap
            # by proposing to both targets
            if (source_proposals and target_proposals and
                    source_proposals[0].source == target_proposals[0].source):
                total = max(source_max + list_get(target_proposals, 1),
                            target_max + list_get(source_proposals, 1))

            if (botswap.garnets > total
                    or (not source_proposals and not target_proposals)):
                try:
                    botswap.accept()
                except SeatException:
                    pass
                else:
                    await botswap.guarantor.send(
                        'Your botswap between {} and {} was accepted.'.format(
                            botswap.source, botswap.target))
                bot_proposals = [x for x in bot_proposals
                                 if cast(BotPlayer, x.target) not in botswap]

        random.shuffle(bot_proposals)
        bot_proposals.sort(key=garnet_key, reverse=True)
        for proposal in bot_proposals:
            try:
                proposal.accept()
            except SeatException:
                pass
            else:
                await proposal.source.send(
                    '{proposal.target} accepted your proposal, '
                    'gaining {proposal.garnets}.\n'
                    'Your new seat is {proposal.source.seat}.\n'
                    "{proposal.target}'s new seat is {proposal.target.seat}"
                    ''.format(proposal=proposal))

    async def new_discord_round(self) -> None:
        await self._resolve_botswaps_proposals()

        if self.game_over:
            self.state = GameState.GAME_OVER
            self._award_win_garnets()
            await self._message_game_over()
            return

        for player in self.players:
            player.new_round()
        self.new_round()

        await self._message_new_round()
        await self._message_react_earlynewround()

    def _award_win_garnets(self) -> None:
        for player in self.winners:
            player.garnets += self.options['win_garnets']
        for player in self.current_x_players:
            player.garnets += self.options['x_garnets']

        streak_length = self.win_streak_length
        middle_garnets = self.options['middle_garnets']
        if streak_length % 2 == 0:
            self.winners[streak_length//2].garnets += middle_garnets//2
            self.winners[streak_length//2-1].garnets += middle_garnets//2
        else:
            self.winners[(streak_length-1)//2].garnets += middle_garnets

    async def _message_react_earlynewround(self) -> None:
        react_needed = max(2, math.ceil(len(self.discord_players)/2)+1)
        emoji = '✅'  # :white_check_mark:
        message = await self.channel.wait_send(
            'React {} to this message to vote for starting the next round '
            'early. {} reactions needed, only players may vote.'.format(
                emoji,
                react_needed))
        await message.add_reaction(emoji)
        self.reactable_messages[message.id] = NewRoundEarly(
            self, message, emoji, react_needed)

    def stop(self) -> None:
        self.state = GameState.STOPPED

    def pause(self) -> None:
        self.state = GameState.PAUSED

    def resume(self) -> None:
        self.state = GameState.RUNNING
        # TODO: Sleep reduced time
        self._round_loop()

    async def add_user(self, user: discord.user) -> None:
        if self.state == GameState.STARTING:
            self.state = GameState.CREATED

        player = DiscordPlayer(user,
                               garnets=self.options['start_garnets'])
        self.discord_players[user] = player
        self.add_player(player)
        await self.send('{} joined the game'.format(player))

    async def remove_discord_player(self, player: DiscordPlayer) -> None:
        self.discord_players.pop(player.user)
        self.remove_player(player)
        await self.send('{} left the game'.format(player))

        if self._all_players_ready():
            await self.start_game_countdown()

    async def add_bot(self, name: str) -> None:
        bot = BotPlayer(name)
        self.bots[name] = bot
        self.add_player(bot)
        await self.send('Bot player {} added to the game'.format(bot))

        if self._all_players_ready():
            await self.start_game_countdown()

    async def remove_bot(self, bot: BotPlayer) -> None:
        self.bots.pop(bot.name)
        self.remove_player(bot)
        await self.send('Bot player {} removed from the game'.format(bot))

    def _current_options_string(self) -> str:
        if self.options['public_swaps']:
            swap_info_str = (
                'Swaps are announced, proposals cannot be made to players who '
                'have swapped, and players who have swapped cannot '
                'send new proposals.')
        else:
            swap_info_str = (
                'Swaps are not announced, and swapped players can receive and '
                'send proposals. Trying to accept a proposal involving a '
                'swapped player will '
                'notify both players.')
        return (
            '```\nCurrent options\n'
            '{swap_info_str}\n'
            'Players who are part of the winning streak will gain '
            '{o[win_garnets]} garnets.\n'
            'All players will start with {o[start_garnets]} garnets.\n'
            'Any players who have the number X in the final round will '
            'lose {x_garnets} garnets.\n'
            'Each round will last {o[round_length]} seconds.\n'
            '```'.format(
                swap_info_str=swap_info_str,
                o=self.options,
                x_garnets=self.options['x_garnets']*-1)
        )

    async def _message_new_round(self) -> None:
        if not self.current_x:
            message_current_x = ''
        elif len(self.current_x) == 1:
            message_current_x = 'The new X is {current_x}.\n'.format(
                current_x=self.current_x[0])
        else:
            message_current_x = (
                'The following numbers are now X: '
                '{current_x}.\n'.format(
                    current_x=' '.join(
                        [str(x) for x in self.current_x])))

        for player in self.discord_players.values():
            await player.send(
                '**Round {current_round} started.**\n'
                'All your proposals have been canceled\n'
                'Your seat is {player.seat} and your number is '
                '{player.number}.\n'
                'You have {player.garnets} garnets.\n'
                '{message_current_x}'
                'Type `!help` for help or `!commands` for commands.'.format(
                    player=player,
                    current_round=self.current_round,
                    message_current_x=message_current_x
                ))

        await self.channel.wait_send(
            '**Round {current_round} started.**\n'
            '```\nSeat  Player\n'
            '{table_layout}```\n'
            "The game didn't finish last round with the old X value.\n"
            'With the new X the longest streak is {streak}.\n'
            'Streak required to win is {win_streak_length}.\n'
            '{message_current_x}' .format(
                current_round=self.current_round,
                table_layout=self._get_table_layout_string(),
                streak=self.longest_streak.longest_streak,
                win_streak_length=self.win_streak_length,
                message_current_x=message_current_x
            ))

    async def _message_game_over(self) -> None:
        if not self.current_x:
            message_x_result = ''
        elif len(self.current_x) == 1:
            message_x_result = (
                '{losing_player} was X and lost '
                '{lose_garnets} garnets.\n'.format(
                    losing_player=self.current_x_players[0],
                    lose_garnets=10))
        else:
            message_x_result = (
                'The following players were X and lost '
                '{lose_garnets} garnets:\n'
                '{losing_players}\n'.format(
                    losing_players=' '.join(
                        [str(x) for x in self.current_x_players]),
                    lose_garnets=10))

        await self.send(
            '**Game Over!**\n'
            'Round: {current_round}\n'
            'The following players completed a streak '
            'and won {win_garnets} garnets:\n'
            '```\nSeat Number Player\n'
            '{winning_players}```\n'
            '{message_x_result}'
            '**Final Results**\n'
            '```\nGarnets Player\n'
            '{player_garnets}```'.format(
                current_round=self.current_round,
                winning_players=self._get_winner_string(),
                win_garnets=10,
                message_x_result=message_x_result,
                player_garnets=self._get_garnets_string()
            ))

    def _get_table_layout_string(self) -> str:
        players = self.players.copy()
        players.sort(key=lambda x: x.public_seat)
        # I'm sorry
        print(type(self.players[0].seat))
        return ''.join([
            '{0}     {1}\n'.format(
                player.public_seat,
                player)
            for player in players])

    def _get_winner_string(self) -> str:
        return '\n'.join([
            '  {0.seat} {0.number:>5}   {0}'.format(winner)
            for winner in self.winners
        ])

    def _get_garnets_string(self) -> str:
        players = self.players.copy()
        players.sort(reverse=True, key=lambda x: x.garnets)
        return '\n'.join([
            '{0.garnets:>5}   {0}'.format(player)
            for player in players
        ])


async def message_cancel(canceler: CommonPlayer,
                         receiver: CommonPlayer) -> None:
    await canceler.send(
        'Proposal to {} canceled. Any locked up garnets are returned.'
        ''.format(receiver))

    await receiver.send(
        '{} has canceled their proposal to you.'.format(
            canceler))
