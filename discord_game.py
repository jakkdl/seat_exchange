# pragma pylint: disable=missing-docstring
from __future__ import annotations

import random
import asyncio
import math

from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any, Generator, Union, cast


import discord  # type: ignore

from player_game import Player, Proposal, PlayerGame

from seat_typing import Seat, SeatException


class DiscordGameException(SeatException):
    pass


class GameState(Enum):
    CREATED = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSED = auto()
    GAME_OVER = auto()
    STOPPED = auto()


class DiscordPlayer(Player):
    def __init__(self,
                 discord_user: discord.User,
                 player_game: PlayerGame,
                 seat: Seat = cast(Seat, -1),
                 garnets: int = 0) -> None:
        super().__init__(player_game, seat, garnets)
        self.user = discord_user
        self.ready = False
        self.assigned_numbers: Dict[Player, int] = {}

    def __str__(self) -> str:
        return cast(str, self.user.display_name)

    def matches(self, search_key: str) -> bool:
        if search_key.lower() in (self.user.name.lower(),
                                  self.user.display_name.lower()):
            return True
        if search_key.isdigit():
            if (int(search_key) == self.user.id
                    or int(search_key) == self._seat):
                return True
        return False

    async def send(self,
                   *args: str,
                   sep: str = ' ',
                   end: str = '',
                   **kwargs: Tuple[str, str]) -> None:
        # don't send to ourselves
        if self.user.id == 573077970445402113:
            return

        try:
            await self.user.send(sep.join(args)+end, **kwargs)
        except discord.errors.Forbidden:
            print('blocked by {}'.format(self))


class BotPlayer(Player):
    def __init__(self,
                 name: str,
                 player_game: PlayerGame,
                 seat: Seat = cast(Seat, -1),
                 garnets: int = 0) -> None:
        super().__init__(player_game, seat, garnets)
        self.name = name

    def __str__(self) -> str:
        return self.name

    def matches(self, search_key: str) -> bool:
        return search_key.lower() == self.name.lower()

    async def send(self, *args: str, sep: str = ' ', end: str = '',
                   **kwargs: Tuple[str, str]) -> None:
        pass


class BotSwap(Proposal):
    """A proposal between two bots, sponsored by a player.

    We pass 0 garnets into Proposal to avoid lockup (better solution?).
    """

    def __init__(self,
                 source: BotPlayer,
                 target: BotPlayer,
                 guarantor: DiscordPlayer,
                 garnets: int = 0):
        super().__init__(source, target, 0)
        self.guarantor = guarantor
        self.garnets = garnets

        self.__lock_up_garnets()

    def __lock_up_garnets(self) -> None:
        if self.garnets < 0:
            raise DiscordGameException(
                'Garnet amount must be non-negative.')

        if self.guarantor.garnets < self.garnets:
            raise DiscordGameException(
                "Can't create proposal, insufficient garnets.")

        self.guarantor.garnets -= self.garnets

    def __str__(self) -> str:
        return ('Botswap between {} and {} '
                'guaranteed by {} with {} garnets'.format(
                    self.source, self.target,
                    self.guarantor, self.garnets))

    def accept(self) -> None:
        super().accept()

        rewards = [math.ceil(self.garnets/2), math.floor(self.garnets/2)]
        random.shuffle(rewards)
        self.source.garnets += rewards[0]
        self.target.garnets += rewards[1]

    def cancel(self) -> None:
        self.guarantor.garnets += self.garnets


class DiscordGame:
    def __init__(self,
                 channel: discord.TextChannel,
                 options: Optional[Dict[str, Any]] = None) -> None:
        self.channel: discord.TextChannel = channel
        self.game = PlayerGame(options)
        self.discord_players: Dict[discord.User, DiscordPlayer] = {}
        self.bots: List[BotPlayer] = []
        self.botswaps: List[BotSwap] = []
        self.state: GameState = GameState.CREATED

        self.dm_player_commands = {
            '!incoming':  self._command_incoming,
            '!outgoing':  self._command_outgoing,
            '!seating':   self._command_seating,
            '!garnet':    self._command_garnets,
            '!garnets':   self._command_garnets,

            '!assign':    self._command_assign,
            '!donate':    self._command_donate,

            # '!botswap'  : self._command_botswap,
            # '!cancelbotswaps' : self._command_cancelall_botswaps,

            '!propose':      self._command_propose,
            '!cancel':       self._command_cancel,
            '!cancelall':    self._command_cancelall,
            '!accept':       self._command_accept,
            '!reject':       self._command_reject,
            '!rejectall':    self._command_rejectall,
        }

    async def send(self,
                   *args: Any,
                   sep: str = ' ',
                   end: str = '',
                   **kwargs: Tuple[str, str]) -> None:
        await self.channel.send(sep.join(str(arg) for arg in args)+end,
                                **kwargs)

    async def ready(self, author: DiscordPlayer) -> None:
        if self.state != GameState.CREATED:
            raise DiscordGameException('Invalid game state.')
        if author.ready:
            raise DiscordGameException('{} already ready.'.format(author))
        author.ready = True

        await self.send('{} ready.'.format(author))

        for player in self.discord_players.values():
            if not player.ready:
                break
        else:
            await self.start_game_countdown()

    async def start_game_countdown(self, timer: int = 10) -> None:
        self.state = GameState.STARTING

        await self.send('Starting game in {} seconds.'.format(timer))

        for time in timer-5, 5:
            await asyncio.sleep(time)

            if self.state != GameState.STARTING:
                await self.send('Countdown canceled.')
                return

            await self.send('Starting game{}.'.format(
                'in 5 seconds' if time != 5 else ''))

        await self.start()

    async def unready(self, author: DiscordPlayer) -> None:
        if self.state not in (GameState.CREATED, GameState.STARTING):
            raise DiscordGameException('Invalid game state.')
        if not author.ready:
            raise DiscordGameException("{} player already unready.")
        author.ready = False

        await self.send('{} unready.'.format(author))

        if self.state == GameState.STARTING:
            self.state = GameState.CREATED

    # This is *obviously* best solved with a Generator
    @property
    def players(self) -> Generator[Player, None, None]:
        for player in self.discord_players.values():
            yield player
        for bot in self.bots:
            yield bot

    @property
    def player_count(self) -> int:
        return len(self.discord_players) + len(self.bots)

    # Tihi, don't feel like this is correct usage of this operator, but I
    # couldn't refrain.
    def __contains__(self, key: Union[discord.user, DiscordPlayer]) -> bool:
        return (key in self.discord_players
                or key in self.discord_players.values())

    @property
    def running(self) -> bool:
        return self.state == GameState.RUNNING

    @property
    def game_over(self) -> bool:
        return self.state == GameState.GAME_OVER

    @property
    def stopped(self) -> bool:
        return self.state == GameState.STOPPED

    async def start(self) -> None:
        if self.player_count < 2:
            raise DiscordGameException(
                'Insufficient number of players: {}'.format(
                    self.player_count))

        if self.state not in (GameState.CREATED, GameState.STARTING):
            raise DiscordGameException(
                'Error: Invalid game state: {}'.format(self.state))

        self.state = GameState.RUNNING
        self.game.start_game()

        await self._message_start_game()

        await self._round_loop()

    async def force_new_round(self) -> None:
        await self._start_new_round()
        await self._round_loop()

    async def _round_loop(self) -> None:
        while True:
            current_round = self.game.current_round
            await asyncio.sleep(self.game.options['round_length'])
            if self.state != GameState.RUNNING:
                print('Game not running, quitting silently.')
                return
            if current_round != self.game.current_round:
                print('Next round prematurely started.')
                return
            self._start_new_round()

    async def _message_start_game(self) -> None:  # TODO
        await self.channel.send(self._current_options_string())
        await self._message_new_round()

    async def _start_new_round(self) -> None:
        await self._message_new_round()
        if not self.game.new_round():
            self.state = GameState.GAME_OVER
            await self._message_game_over()

    def stop(self) -> None:
        self.state = GameState.STOPPED

    def pause(self) -> None:
        self.state = GameState.PAUSED

    def resume(self) -> None:
        self.state = GameState.RUNNING
        # TODO: Sleep reduced time
        self._round_loop()

    async def add_player(self, user: discord.user) -> None:
        player = DiscordPlayer(user, self.game)
        self.discord_players[user] = player
        self.game.add_player(player)
        await self.send('{} joined the game'.format(player))

    def remove_player(self, player: DiscordPlayer) -> None:
        # TODO: Should this one take a Player?
        self.discord_players.pop(player.user)
        self.game.remove_player(player)

    def add_bot(self, name: str) -> None:
        bot = BotPlayer(name, self.game)
        self.bots.append(bot)
        self.game.add_player(bot)

    def remove_bot(self, name: str) -> None:
        pass  # TODO: take name, Player or BotPlayer?

    def _current_options_string(self) -> str:
        if self.game.options['public_swaps']:
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
            '```Current options\n'
            '{swap_info_str}\n'
            'Players who are part of the winning streak will gain '
            '{o[win_garnets]} garnets.\n'
            'All players will start with {o[start_garnets]} garnets.\n'
            'Any players who have the number X in the final round will '
            'lose {x_garnets} garnets.\n'
            'Each round will last {o[round_length]} seconds.\n'
            '```'.format(
                swap_info_str=swap_info_str,
                o=self.game.options,
                x_garnets=self.game.options['x_garnets']*-1)
        )

    async def _message_new_round(self) -> None:
        for player in self.discord_players.values():
            if not self.game.current_x:
                message_current_x = ''
            elif len(self.game.current_x) == 1:
                message_current_x = 'The new X is {current_x}.\n'.format(
                    current_x=self.game.current_x[0])
            else:
                message_current_x = (
                    'The following numbers are now X: '
                    '{current_x}.\n'.format(
                        current_x=' '.join(
                            [str(x) for x in self.game.current_x])))

            print(player)
            await player.send(
                '**Round {current_round} started.**\n'
                'All your proposals have been canceled\n'
                'Your seat is {player.seat} and your number is '
                '{player.number}.\n'
                'You have {player.garnets} garnets.\n'
                '{message_current_x}'
                'Type `!help` for help or `!commands` for commands.'.format(
                    player=player,
                    current_round=self.game.current_round,
                    message_current_x=message_current_x
                ))

        # TODO: pylint gives missing-format-attribute if i try to acces
        # the attributes of self.game inside the format string.
        # why??
        await self.send(
            '**Round {current_round} started.**\n'
            '```Seat  Player\n'
            '{table_layout}```\n'
            "The game didn't finish last round with the old X value.\n"
            'With the new X the longest streak is {streak}.\n'
            'Streak required to win is {win_streak_length}.\n'
            '{message_current_x}' .format(
                current_round=self.game.current_round,
                table_layout=self._get_table_layout_string(),
                streak=self.game.longest_streak,
                win_streak_length=self.game.win_streak_length,
                message_current_x=message_current_x
            ))

    async def _message_game_over(self) -> None:
        if not self.game.current_x:
            message_x_result = ''
        elif len(self.game.current_x) == 1:
            message_x_result = (
                '{losing_player} was X and lost '
                '{lose_garnets} garnets.\n'.format(
                    losing_player=self.game.current_x_players[0],
                    lose_garnets=10))
        else:
            message_x_result = (
                'The following players were X and lost '
                '{lose_garnets} garnets:\n'
                '{losing_players}\n'.format(
                    losing_players=' '.join(
                        [str(x) for x in self.game.current_x_players]),
                    lose_garnets=10))

        await self.send(
            '**Game Over!**\n'
            'Round: {current_round}\n'
            'The following players completed a streak '
            'and won {win_garnets} garnets:\n'
            '```Seat Number Player\n'
            '{winning_players}```\n'
            '{message_x_result}'
            '**Final Results**\n'
            '```Garnets Player\n'
            '{player_garnets}```'.format(
                current_round=self.game.current_round,
                winning_players=self._get_winner_string(),
                win_garnets=10,
                message_x_result=message_x_result,
                player_garnets=self._get_garnets_string()
            ))

    async def _command_incoming(
            self, _parameters: List[str],
            player: DiscordPlayer) -> None:  # pylint: disable=unused-argument
        if not player.incoming_proposals:
            await player.send('No incoming proposals')
            return

        await player.send('\n'.join(
            [str(p) for p in player.incoming_proposals]))

    async def _command_outgoing(
            self, _parameters: List[str],
            player: DiscordPlayer) -> None:  # pylint: disable=unused-argument
        if not player.outgoing_proposals:
            await player.send('No outgoing proposals')
            return
        await player.send('\n'.join(
            [str(p) for p in player.outgoing_proposals]))

    async def _command_seating(self, _parameters: List[str],
                               player: DiscordPlayer) -> None:
        # def _get_table_layout_string(self):
        # I'm sorry
        seat_string = ''
        for other_player in self.game.players:
            seat = player.seat
            number = (player.assigned_numbers.get(other_player, '')
                      if other_player != player else player.number)
            seat_string += '{0:>3} {1:>4}  {2}\n'.format(
                seat,
                number,
                other_player)
        await player.send('```{}```'.format(seat_string))

    async def _command_garnets(self, _parameters: List[str],
                               player: DiscordPlayer) -> None:
        await player.send('You have {} garnets.'.format(player.garnets))

    async def _command_assign(self, parameters: List[str],
                              player: DiscordPlayer) -> None:
        if not self.running:
            raise DiscordGameException(
                'Error: game is not running')

        if not parameters:
            raise DiscordGameException(
                'Error: please specify <player/seat> and number.\n'
                'Example: `!assign jakkdl 5`.')

        target = self.find_player(' '.join(parameters[:-1]))

        if not parameters[-1].isdigit():
            raise DiscordGameException(
                'Error: {} is not a valid number'.format(parameters[-1])
            )

        # if player == target:
        #     raise DiscordGameException(
        #         "Error: can't assign yourself")

        digit = int(parameters[-1])
        player.assigned_numbers[target] = digit

        await player.send('{} assigned to {}'.format(digit, target))

    async def _command_donate(self, parameters: List[str],
                              player: DiscordPlayer) -> None:
        if len(parameters) < 2:
            raise DiscordGameException(
                'Error: please specify a player and amount.')

        target = self.find_player(' '.join(parameters[:-1]))

        try:
            garnets = int(parameters[-1])
        except ValueError:
            raise DiscordGameException(
                'Invalid garnet amount {}.'.format(parameters[-1]))

        if garnets < 1 or garnets > player.garnets:
            raise DiscordGameException(
                'Invalid garnet amount {}.'.format(parameters[-1]))

        await player.donate_garnets(target, garnets)

        await player.send('You have sent {garnets} garnets to {target}.\n'
                          'You now have {player.garnets} garnets.'.format(
                              garnets=garnets,
                              target=target,
                              player=player))
        await target.send('{player} has sent {garnets} garnets to you.\n'
                          'You now have {target.garnets} garnets.'.format(
                              garnets=garnets,
                              target=target,
                              player=player))

#    async def _command_botswap(self, parameters: List[str],
#                               player: DiscordPlayer):
#        if not self.running:
#            raise DiscordGameException(
#                'Error: game is not running')
#
#        if not parameters or 'with' not in parameters:
#            raise DiscordGameException(
#                'Error: please specify bots and number in '
#                'the following format.\n'
#                '`!assign <bot> with <bot> <garnets>`\n'
#                'Example: `!botswap Seat Exchange Bot with '
#                'necro_score_bot 5`.')
#
#        if not parameters[-1].isdigit():
#            raise DiscordGameException(
#                'Error: invalid garnet amount {}'.format(parameters[-1])
#            )
#
#        garnets = int(parameters[-1])
#
#        with_index = parameters.index('with')
#
#        source = self.find_player(' '.join(parameters[:with_index]))
#
#        target = self.find_player(' '.join(parameters[with_index+1:-1]))
#
#        if not source.user.bot:
#            raise DiscordGameException(
#                'Error: {} is not a bot.'.format(source))
#
#        if not target.user.bot:
#            raise DiscordGameException(
#                'Error: {} is not a bot.'.format(target))
#
#        player.botswaps.append(Proposal(source, target, self.game, garnets))
#
#        if source == target:
#            await player.send('Bribed {} to not swap with {} garnets.'.format(
#                source, garnets))
#
#        else:
#            await player.send('Proposed botswap with {} and {} '
#                              'with a total bribe of {} garnets.'.format(
#                                  source, target, garnets))
#
#    async def _command_cancelall_botswaps(self,
#                                          _parameters: List[str],
#                                          player: DiscordPlayer):
#        if not self.running:
#            raise DiscordGameException(
#                'Error: game is not running')
#
#        if not player.botswaps:
#            raise DiscordGameException(
#                'Error: you have no active botswaps proposed.')
#
#        player.botswaps = []

    async def _command_propose(self, parameters: List[str],
                               player: DiscordPlayer) -> None:
        if not self.running:
            raise DiscordGameException(
                'Error: game is not running')

        if not parameters:
            raise DiscordGameException(
                'Error: please provide the id, seat, name or '
                'display name of a player '
                'and optionally an amount of garnets to bribe with.')

        try:
            target = self.find_player(' '.join(parameters[:-1]))
            garnet_bribe = True
        except DiscordGameException:
            target = self.find_player(' '.join(parameters))
            garnet_bribe = False

        if player == target:
            raise DiscordGameException(
                "Error: can't propose to yourself.")

        if player.swapped and self.game.options['public_swaps']:
            raise DiscordGameException(
                'Error: you have already swapped seats this round')

        if target.swapped and self.game.options['public_swaps']:
            raise DiscordGameException(
                'Error: {} have already swapped seats this round.'.format(
                    target))

        if len(parameters) > 1 and garnet_bribe:
            if parameters[-1].isdigit() and int(parameters[-1]) >= 0:
                garnets = int(parameters[-1])
            else:
                raise DiscordGameException('invalid amount of garnets {}'
                                           ''.format(parameters[1]))
        else:
            garnets = 0

        player.add_proposal_to(target, garnets)

        await player.send(
            'Proposal sent to {target} offering {garnets} garnets.\n'
            'Those garnets are locked up until either player cancels the '
            'proposal.\n'
            'You now have {player.garnets} garnets.\n'
            'You can cancel the proposal with `!cancel.`'.format(
                player=player,
                target=target,
                garnets=garnets
            ))

        if target.swapped:
            message = (
                'You have already swapped seats this round, and '
                'cannot accept this proposal.\n'
                'You can reject the proposal with `!reject`.')
        else:
            message = (
                'You can accept the proposal with `!accept` '
                'or reject it with `!reject`.')

        await target.send(
            'Proposal received from {player} offering {garnets}.\n'
            '{message}'.format(
                player=player,
                garnets=garnets,
                message=message))

    async def _command_cancel(self, parameters: List[str],
                              player: DiscordPlayer) -> None:
        proposals = player.outgoing_proposals
        if not proposals:
            raise DiscordGameException(
                'Error: you have no outgoing proposals')

        if len(proposals) > 1 and not parameters[0]:
            raise DiscordGameException(
                'Error: you have multiple outgoing proposals, '
                'please specify '
                'the name, display name, id or seat of the player '
                'to which you want to cancel your proposal.')

        if not parameters:
            proposal = proposals[0]
        else:
            for prop in proposals:
                if prop.target.matches(' '.join(parameters)):
                    proposal = prop
                    break
            else:
                raise DiscordGameException(
                    'Error: found no proposal matching {}.'
                    ''.format(parameters[0]))

        player.game.cancel_proposal(proposal)
        await message_cancel(canceler=player,
                             receiver=proposal.target)

    async def _command_cancelall(self, _parameters: List[str],
                                 player: DiscordPlayer) -> None:
        if not player.outgoing_proposals:
            raise DiscordGameException(
                'Error: you have no outgoing proposals')

        for proposal in player.outgoing_proposals:
            player.game.cancel_proposal(proposal)

            await message_cancel(canceler=player,
                                 receiver=proposal.target)

    @staticmethod
    def _common_handle_incoming_proposal(parameters: List[str],
                                         player: DiscordPlayer) -> Proposal:
        proposals = player.incoming_proposals
        if not proposals:
            raise DiscordGameException(
                'Error: you have no incoming proposals')

        if len(proposals) > 1 and not parameters[0]:
            raise DiscordGameException(
                'Error: you have multiple incoming proposals, '
                'please specify '
                'the name, display name, id or seat of the player '
                'to which you want to cancel your proposal.')

        # We only have one proposal and didn't specify a parameter,
        # so return it
        if not parameters:
            return proposals[0]

        for prop in proposals:
            if prop.source.matches(' '.join(parameters)):
                return prop

        raise DiscordGameException(
            'Error: found no proposal matching {}.'.format(parameters[0]))

    async def _command_accept(self, parameters: List[str],
                              player: DiscordPlayer) -> None:
        proposal = self._common_handle_incoming_proposal(parameters, player)

        if player.swapped:
            raise DiscordGameException(
                'Error: you have already swapped this round.')

        if proposal.source.swapped:
            await proposal.source.send(
                '{} tried accepting your proposal, but you have already '
                'swapped.'
                'Proposal canceled.'.format(
                    player))
            player.game.cancel_proposal(proposal)
            raise DiscordGameException(
                '{} has already swapped this round. Proposal canceled.'
                ''.format(proposal.source))

        player.game.accept_proposal(proposal)

        if self.game.options['public_swaps']:
            other_proposals_string = ('\nAll your other proposals have '
                                      'been canceled.')
        else:
            other_proposals_string = ''

        await player.send(
            'Proposal from {source} accepted.\n'
            'You have gained {garnets} garnets.\n'
            'You now have {player.garnets} garnets.\n'
            'You have switched seats from {source.seat} to {player.seat}'
            '{other_proposals}'.format(
                source=proposal.source,
                player=player,
                other_proposals=other_proposals_string,
                garnets=proposal.garnets
            ))

        await proposal.source.send(
            '{player} has accepted their proposal from you '
            'gaining {garnets} garnets.\n'
            'You now have {source.garnets} garnets.\n'
            'You have switched seats from {player.seat} to {source.seat}.'
            '{other_proposals}'
            .format(
                source=proposal.source,
                player=player,
                garnets=proposal.garnets,
                other_proposals=other_proposals_string
            ))

        if self.game.options['public_swaps']:
            swappers = [player, proposal.source]
            random.shuffle(swappers)
            await self.send(
                '{0} have swapped with {1}.\n'
                '{0} is now in seat {0.seat}.\n'
                '{1} is now in seat {1.seat}.'.format(
                    swappers[0],
                    swappers[1]))

            for prop in player.proposals + proposal.source.proposals:
                prop.cancel()
                if prop.source not in (proposal.source, player):
                    proposer = prop.source
                    rejecter = prop.target

                    await message_reject(rejecter, proposer)

                else:
                    receiver = prop.target
                    canceler = prop.source

                    await message_cancel(canceler, receiver)

    async def _command_reject(self, parameters: List[str],
                              player: DiscordPlayer) -> None:
        proposal = self._common_handle_incoming_proposal(parameters, player)

        player.game.cancel_proposal(proposal)

        await message_reject(rejecter=player, proposer=proposal.source)

    async def _command_rejectall(self, _parameters: List[str],
                                 player: DiscordPlayer) -> None:
        if not player.incoming_proposals:
            raise DiscordGameException(
                'Error: you have no incoming proposals')
        for proposal in player.incoming_proposals:
            player.game.cancel_proposal(proposal)

            await message_reject(rejecter=player,
                                 proposer=proposal.source)

    # tries to match search key by id, name, display_name or seat
    def find_player(self, search_key: str) -> Player:
        for player in self.players:
            if player.matches(search_key):
                return player

        raise DiscordGameException(
            'Error: cannot find any matches for {}'.format(search_key))

    def _get_table_layout_string(self) -> str:
        # I'm sorry
        return ''.join([
            '{0:>3}   {1}\n'.format(
                player.seat,
                player)
            for player in self.game.players])

    def _get_winner_string(self) -> str:
        return '\n'.join([
            '{0.seat:>3} {0.number:>5}   {0}'.format(winner)
            for winner in self.game.winners
        ])

    def _get_garnets_string(self) -> str:
        players = list(self.players)
        players.sort(key=lambda x: -x.garnets)
        return '\n'.join([
            '{0.garnets:>5}   {0}'.format(player)
            for player in players
        ])


async def message_cancel(canceler: Player,
                         receiver: Player) -> None:
    await canceler.send(
        'Proposal to {} canceled. Any locked up garnets are returned.'
        ''.format(receiver))

    await receiver.send(
        '{} has canceled their proposal to you.'.format(
            canceler))


async def message_reject(rejecter: Player,
                         proposer: Player) -> None:
    await rejecter.send(
        'Proposal from {} rejected.'.format(
            proposer))
    await proposer.send(
        '{} has rejected your proposal. Any locked up garnets are '
        'returned.'.format(
            rejecter))
