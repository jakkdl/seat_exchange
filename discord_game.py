# pragma pylint: disable=missing-docstring
from __future__ import annotations

import random
import asyncio
import math

from enum import Enum, auto
import typing
from typing import Dict, Optional, Any, cast


import discord  # type: ignore

import strings
from seat_game import SeatPlayer, SeatGame
from seat_typing import (Seat, PrivateNumber, SeatException, SeatChannel,
                         Findable, GenF)

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
                 discord_user: discord.User,
                 garnets: int = 0) -> None:
        super().__init__(garnets)
        self.user = discord_user
        self._channel: Optional[SeatChannel] = None
        self.ready = False
        self._assigned_numbers: Dict[SeatPlayer, PrivateNumber] = {}

    def __str__(self) -> str:
        return cast(str, self.user.display_name)

    def matches(self, search_key: str) -> bool:
        if search_key.lower() in (self.user.name.lower(),
                                  self.user.display_name.lower()):
            return True
        if search_key.isdigit():
            if (int(search_key) == self.user.id
                    or int(search_key) == self.seat):
                return True
        return False

    async def send(self, *args: Any, **kwargs: str) -> discord.Message:
        if self._channel is None:
            self._channel = await SeatChannel.from_user(self.user)
        return await self._channel.send(*args, **kwargs)

    @property
    def assigned_numbers(self) -> Dict[SeatPlayer, PrivateNumber]:
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

    async def send(self, *args: Any, **kwargs: str) -> discord.Message:
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
                       user: discord.User) -> None:
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
                       user: discord.User) -> None:
        print('on_react')
        if reaction.emoji != self.emoji:
            print('wrong_emoji')
            return
        if user not in self.game and user.id != BOT_ID:
            await reaction.remove(user)
            await user.send(
                'Error: You are not allowed to vote on that message.')
            return
        if reaction.count < self.react_needed:
            return

        await self.game.force_new_round()


class DiscordGame(SeatGame[CommonPlayer]):
    default_options: typing.Dict[str, Any] = strings.DEFAULT_OPTIONS

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

        # TODO: Remove, but requires some refactoring
        self.discord_players: Dict[discord.User, DiscordPlayer] = {}
        self.bots: Dict[str, BotPlayer] = {}


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

        await self._message_start_game()
        self.state = GameState.RUNNING

        await self._round_loop()

    async def force_new_round(self) -> None:
        await self.new_discord_round()
        await self._round_loop()

    async def _round_loop(self) -> None:
        while True:
            current_round = self.current_round
            await asyncio.sleep(self.options['round_length'])
            if self.state != GameState.RUNNING:
                print('Game not running, quitting silently.')
                return
            if current_round != self.current_round:
                print('Next round prematurely started.')
                return
            await self.new_discord_round()

    async def _message_start_game(self) -> None:  # TODO
        await self.channel.send(self._current_options_string())
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
                await proposal.source.send(
                    '{proposal.target} accepted your proposal, '
                    'gaining {proposal.garnets}.\n'
                    'Your new seat is {proposal.source.seat}.\n'
                    "{proposal.target}'s new seat is {proposal.target.seat}"
                    ''.format(proposal=proposal))
            except SeatException:
                pass

    async def new_discord_round(self) -> None:
        await self._resolve_botswaps_proposals()

        if self.game_over:
            self.state = GameState.GAME_OVER
            self._award_win_garnets()
            await self._message_game_over()
            return

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

        player = DiscordPlayer(user)
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

        # TODO: pylint gives missing-format-attribute if i try to acces
        # the attributes of self.game inside the format string.
        # why??
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
                streak=self.longest_streak,
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
        players.sort(reverse=True, key=lambda x: x.seat)
        # I'm sorry
        return ''.join([
            '{0:>3}   {1}\n'.format(
                player.seat,
                player)
            for player in self.players])

    def _get_winner_string(self) -> str:
        return '\n'.join([
            '{0.seat:>3} {0.number:>5}   {0}'.format(winner)
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
