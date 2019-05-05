# pragma pylint: disable=missing-docstring
from typing import Dict
from typing import List

import random
import asyncio

import discord # type: ignore

import discord_game
from discord_game import Player
from discord_game import Proposal

#TODO: police nickname changes


class DiscordBotException(Exception):
    pass



# pylint: disable=too-many-instance-attributes
# The commands variables are sorta ugly, but I can't make them static
# as they refer to self. If anybody reading this has a tip, hit me up.
class DiscordBot(discord.Client):

    #placing them out here makes pylint happy, and feels better
    #but doesn't work with mypy
    #self._admin_commands = {
        #'!close'     : _command_close
    #}


    def __init__(self):
        super().__init__()
        self._game: discord_game.DiscordGame = discord_game.DiscordGame()
        self._players: Dict[discord.User, Player] = {}
        self._game_channel: discord.TextChannel = None
        self._game_started: float = 0.0

        self._round_length: int = 300

        #TODO: implement !kick
        self._admin_commands = {
            #!kick
            #!forcenextround - impossible?
            '!close'     : self._command_close,
            '!forcejoin' : self._command_forcejoin,
            '!forcejoinall' : self._command_forcejoinall,
            '!destroy'   : self._command_destroy,
            '!forceseatnumbers' : self._command_forceseatnumbers,
            '!admincommands' : self._command_admincommands
        }

        self._dm_commands = {
            '!help'     : self._dm_command_commands,
            '!commands' : self._dm_command_commands,
            '!incoming' : self._command_incoming,
            '!outgoing' : self._command_outgoing,
            '!seating'  : self._command_seating,
            '!garnets'  : self._command_garnets,

            '!donate'   : self._command_donate,

            '!propose'  : self._command_propose,
            '!cancel'   : self._command_cancel,
            '!cancelall': self._command_cancelall,
            '!accept'   : self._command_accept,
            '!reject'   : self._command_reject,
            '!rejectall': self._command_rejectall
        }


        #!stop
        self._player_commands = {
            '!start'    : self._command_start,
            '!leave'    : self._command_leave,
            '!setoption': self._command_setoption,
            '!getoptions': self._command_getoptions

        }

        self._public_commands = {
            '!help'     : self._public_command_help,
            '!commands' : self._public_command_commands,
            '!source'   : self._public_command_source,
            '!players'  : self._public_command_players,
            '!join'     : self._command_join,
        }

    async def on_ready(self):
        print('We have logged in as {0.user}'.format(self))
        await self.guilds[0].channels[0].send('Seat Exchange Bot v0.1')


    async def on_message(self, message):
        if message.author == self.user:
            return

        if not message.content.startswith('!'):
            return

        command = message.content.split(' ')[0]
        parameters = message.content.split(' ')[1:]

        try:
            await self._parse_command(command, parameters, message.author, message.channel)


        except DiscordBotException as error:
            print(error)
            await message.channel.send(error)
        except discord_game.DiscordGameException as error:
            print(error)
            await message.channel.send(
                'Error in game engine: {}'.format(error))

    async def _parse_command(self, command, parameters: List[str], author, channel):
        if command in self._admin_commands:
            #TODO: if admin
            for role in author.roles:
                if role.name == 'game admin':
                    await self._admin_commands[command](parameters,
                                                        author,
                                                        channel)
                    break
            else:
                raise DiscordBotException('Unauthorized.')

        elif isinstance(channel, discord.TextChannel):
            if command in self._public_commands:
                await self._public_commands[command](parameters,
                                                     author,
                                                     channel)
            elif command in self._player_commands:
                if author not in self._players:
                    raise DiscordBotException(
                        'Error: {} not a player in a current game.'.format(author))
                await self._player_commands[command](parameters,
                                                     self._players[author],
                                                     channel)

            elif command in self._dm_commands:
                raise DiscordBotException(
                    'Command {} not allowed in this channel.'.format(command))

            else:
                raise DiscordBotException(
                    'Unknown command {}.'.format(command))

        elif isinstance(channel, discord.DMChannel):
            if command in self._dm_commands:
                if author not in self._players:
                    raise DiscordBotException(
                        'Error: {} not a player in a current game.'.format(author))
                await self._dm_commands[command](parameters, self._players[author])

            elif command in self._public_commands:
                raise DiscordBotException(
                    'Command {} not allowed in this channel.'.format(command))

            else:
                raise DiscordBotException('Unknown command {}'.format(
                    command))


        else:
            raise DiscordBotException(
                'Channel not supported.')

    async def _command_close(self, _parameters: List[str], _author, channel):
        await channel.send('closing...')
        print('closing...\n\n')
        await self.close()

    async def _command_forcejoin(self, parameters: List[str], _author, channel):
        for member in channel.guild.members:
            if ' '.join(parameters).lower() in (str(member.id),
                                                member.name.lower(),
                                                member.display_name.lower()):
                await self._command_join(parameters, member, channel)
                break
        else:
            raise DiscordBotException('Invalid member {}'.format(
                ' '.join(parameters)))


    async def _command_forcejoinall(self, parameters: List[str], _author, channel):
        for member in channel.guild.members:
            await self._command_join(parameters, member, channel)

    async def _command_start(self, _parameters: List[str], _player: Player, _channel):
        if self._game_started:
            raise DiscordBotException(
                'Game already running.')

        if len(self._players) < 2:
            raise DiscordBotException(
                'Insufficient number of players: {}'.format(
                    len(self._players)))

        import time
        game_started = time.time()
        self._game_started = game_started
        self._game.start_game()

        await self._game_channel.send(self._current_options_string())

        while True:
            await self._message_new_round()

            await asyncio.sleep(self._game.options['round_length'])

            print('finished sleep')
            # game canceled, quit silently

            # another game was started in the meantime, or game got canceled
            if game_started != self._game_started:
                print('quitting silently, another game started or we got canceled.')
                return

            # Game Over
            if not self._game.new_round():
                self._game_started = 0.0
                await self._message_game_over()
                self._game = discord_game.DiscordGame(self._game.options)
                self._players = {}
                return

            # Otherwise, continue with next round and loop

    def _current_options_string(self):
        if self._game.options['public_swaps']:
            swap_info_str = (
                'Swaps are announced, proposals cannot be made to players who '
                'have swapped, and players who have swapped cannot send new proposals.')
        else:
            swap_info_str = (
                'Swaps are not announced, and swapped players can receive and '
                'send proposals. Trying to accept a proposal involving a swapped player will '
                'notify both players.')
        return (
            '```Current options\n'
            '{swap_info_str}\n'
            'Players who are part of the winning streak will gain {o[win_garnets]} garnets.\n'
            'All players will start with {o[start_garnets]} garnets.\n'
            'Any players who have the number X in the final round will '
            'lose {x_garnets} garnets.\n'
            'Each round will last {o[round_length]} seconds.\n'
            '```'.format(
                swap_info_str=swap_info_str,
                o=self._game.options,
                x_garnets=self._game.options['x_garnets']*-1)
        )

    async def _command_getoptions(self, _parameters: List[str], _player: Player, channel):
        await channel.send('```{}```'.format(
            '\n'.join(
                ['{}: {}'.format(key, self._game.options[key])
                 for key in self._game.options]
            )))

    async def _command_setoption(self, parameters: List[str], _player: Player, channel):
        async def set_option(key, value):
            self._game.options[key] = value
            await channel.send('{} set to {}'.format(key, value))

        if len(parameters) < 2:
            raise DiscordBotException('Please specify option and value.')

        key = parameters[0]
        value = parameters[1]
        if key not in self._game.options:
            raise DiscordBotException('Invalid option.')

        if value.isdigit() and key in ('win_garnets', 'x_garnets', 'start_garnets', 'round_length'):
            await set_option(key, int(value))

        elif value[0] == '-' and value[1:].isdigit() and key in ('win_garnets', 'x_garnets'):
            await set_option(key, int(value))

        elif key == 'public_swaps' and value.lower() in ('true', 'false'):
            await set_option(key, value.lower() == 'true')

        else:
            raise DiscordBotException('Invalid value {} for key {}.'.format(value, key))


    async def _message_new_round(self):
        for player in self._players.values():
            if not self._game.current_x:
                message_current_x = ''
            elif len(self._game.current_x) == 1:
                message_current_x = 'Number {current_x} is X.\n'.format(
                    current_x=self._game.current_x[0])
            else:
                message_current_x = 'The following numbers are X: {current_x}.\n'.format(
                    current_x=' '.join(self._game.current_x))

            await player.send(
                '**Round {current_round} started.**\n'
                'All your proposals have been canceled\n'
                'Your seat is {player.seat} and your number is {player.number}.\n'
                'You have {player.garnets} garnets.\n'
                '{message_current_x}'
                'Type `!help` for help or `!commands` for commands.'.format(
                    player=player,
                    current_round=self._game.current_round,
                    message_current_x=message_current_x
                ))

        # TODO: pylint gives missing-format-attribute if i try to acces
        # the attributes of self._game inside the format string.
        # why??
        await self._game_channel.send(
            '**Round {current_round} started.**\n'
            '```Seat  Player\n'
            '{table_layout}```\n'
            'The longest streak is {streak}.\n'
            'Streak required to win is {win_streak_length}.\n'
            '{message_current_x}' .format(
                current_round=self._game.current_round,
                table_layout=self._get_table_layout_string(),
                streak=self._game.longest_streak,
                win_streak_length=self._game.win_streak_length,
                message_current_x=message_current_x
            ))

    async def _message_game_over(self):
        if not self._game.current_x:
            message_x_result = ''
        elif len(self._game.current_x) == 1:
            message_x_result = ('{losing_player} was X and lost {lose_garnets} garnets.\n'.format(
                losing_player=self._game.current_x_players[0],
                lose_garnets=10))
        else:
            message_x_result = ('The following players were X and lost {lose_garnets} garnets:\n'
                                '{losing_players}\n'.format(
                                    losing_players=' '.join(self._game.current_x_players),
                                    lose_garnets=10))


        await self._game_channel.send(
            '**Game Over!**\n'
            'Round: {current_round}\n'
            'The following players completed a streak and won {win_garnets} garnets:\n'
            '```Seat Number Player\n'
            '{winning_players}```\n'
            '{message_x_result}'
            '**Final Results**\n'
            '```Garnets Player\n'
            '{player_garnets}```'.format(
                current_round=self._game.current_round,
                winning_players=self._get_winner_string(),
                win_garnets=10,
                message_x_result=message_x_result,
                player_garnets=self._get_garnets_string()
            ))

    def _get_table_layout_string(self):
        #I'm sorry
        return ''.join([
            '{0:>3}   {1}\n'.format(
                seat,
                self._game.player_in_seat(seat))
            for seat in range(len(self._players))])

    def _get_winner_string(self):
        return '\n'.join([
            '{0.seat:>3} {0.number:>5}   {0}'.format(winner)
            for winner in self._game.winners
        ])

    def _get_garnets_string(self):
        players = list(self._players.values())
        players.sort(key=lambda x: -x.garnets)
        return '\n'.join([
            '{0.garnets:>5}   {0}'.format(player)
            for player in players
        ])

    async def _command_admincommands(self, _parameters: List[str],
                                     _player: Player, channel): #pylint: disable=unused-argument
        await channel.send('`' + '` `'.join(self._admin_commands.keys()) + '`')

    async def _dm_command_commands(self, _parameters: List[str],
                                   player: Player): #pylint: disable=unused-argument
        await player.send('`' + '` `'.join(self._dm_commands.keys()) + '`')

    async def _command_incoming(self, _parameters: List[str],
                                player: Player): #pylint: disable=unused-argument
        if not player.incoming_proposals:
            await player.send('No incoming proposals')
            return

        await player.send('\n'.join([str(p) for p in player.incoming_proposals]))

    async def _command_outgoing(self, _parameters: List[str],
                                player: Player): #pylint: disable=unused-argument
        if not player.outgoing_proposals:
            await player.send('No outgoing proposals')
            return
        await player.send('\n'.join([str(p) for p in player.outgoing_proposals]))

    async def _command_seating(self, _parameters: List[str], player: Player):
        await player.send('```{}```'.format(self._get_table_layout_string()))

    async def _command_garnets(self, _parameters: List[str], player: Player):
        await player.send('You have {} garnets.'.format(player.garnets))

    async def _public_command_help(self, _parameters: List[str], _player: Player,
                                   channel): #pylint: disable=unused-argument
        await channel.send('https://en.wikipedia.org/wiki/The_Genius:_Rule_Breaker'
                           '#Episode_2:_Seat_Exchange_(12_Contestants)\n'
                           'Type `!commands` for list of commands.')

    async def _public_command_commands(self, _parameters: List[str], _player: Player,
                                       channel): #pylint: disable=unused-argument
        await channel.send('`' + '` `'.join(
            list(self._public_commands.keys()) + list(self._player_commands.keys())) + '`')

    async def _public_command_players(self, _parameters: List[str], _player: Player,
                                      channel): #pylint: disable=unused-argument
        if not self._game:
            await channel.send('No game exists.')
            return
        if not self._game.players:
            await channel.send('No players in the game')
            return
        await channel.send('```Players joined:\n'
                           '{}```'.format('\n'.join([
                               str(p) for p in self._game.players])))

    async def _public_command_source(self, _parameters: List[str], _player: Player,
                                     channel): #pylint: disable=unused-argument
        await channel.send('https://github.com/h00701350103/seat_exchange')

    async def _command_destroy(self, _parameters: List[str], _player: Player, channel):

        self._game_started = 0.0
        self._players = {}
        self._game = discord_game.DiscordGame(self._game.options)
        await channel.send('Game canceled.')

    async def _command_forceseatnumbers(self, _parameters: List[str], _player: Player, channel):
        await channel.send('```Seat Number\n'
                           '{}```'.format('\n'.join([
                               '{seat:>3} {number:>3}'.format(
                                   seat=seat,
                                   number=self._game.number_in_seat(seat))
                               for seat in range(len(self._players))
                           ])))

    async def _command_join(self, _parameters: List[str], author, channel):
        if self._game_started:
            raise DiscordBotException('Cannot join game in progress.')

        if author in self._players: #compares ids
            raise DiscordBotException(
                '{} already joined'.format(author.display_name))

        self._game_channel = channel
        self._players[author] = self._game.add_player(author)

        print('{0.name} has joined with id {0.id}'.format(author))
        await channel.send('{} has joined'.format(author.display_name))

    async def _command_leave(self, _parameters: List[str], player: Player, channel):
        if player not in self._players.values(): #compares ids
            raise DiscordBotException(
                'Error: {} has not joined.'.format(player))

        #send message asking for confirmation in the form of emoji reaction to message.
        if self._game_started:
            raise DiscordBotException(
                'Error: cannot leave game in progress (WIP)'
            )

        self._game.remove_player(player)
        self._players.pop(player.user)

        await channel.send('{} has left the game'.format(player))



    #tries to match search key by id, name, display_name or seat
    def _find_player(self, search_key: str) -> Player:
        for player in self._players.values():
            if player.matches(search_key):
                return player

        raise DiscordBotException(
            'Error: cannot find any matches for {}'.format(search_key))

    async def _command_donate(self, parameters: List[str], player: Player):
        if len(parameters) < 2:
            raise DiscordBotException(
                'Error: please specify a player and amount.')


        target = self._find_player(' '.join(parameters[:-1]))

        try:
            garnets = int(parameters[-1])
        except ValueError:
            raise DiscordBotException(
                'Invalid garnet amount {}.'.format(parameters[-1]))

        if garnets < 1 or garnets > player.garnets:
            raise DiscordBotException(
                'Invalid garnet amount {}.'.format(parameters[-1]))

        player.send_garnets(target, garnets)

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




    async def _command_propose(self, parameters: List[str], player: Player):
        if not self._game_started:
            raise DiscordBotException(
                'Error: game is not running')

        if not parameters:
            raise DiscordBotException(
                'Error: please provide the id, seat, name or display name of a player '
                'and optionally an amount of garnets to bribe with.')

        try:
            target = self._find_player(' '.join(parameters[:-1]))
            garnet_bribe = True
        except DiscordBotException:
            target = self._find_player(' '.join(parameters))
            garnet_bribe = False

        if player == target:
            raise DiscordBotException(
                "Error: can't propose to yourself.")


        if player.swapped and self._game.options['public_swaps']:
            raise DiscordBotException(
                'Error: you have already swapped seats this round')

        if self._game.options['public_swaps'] and target.swapped:
            raise DiscordBotException(
                'Error: {} have already swapped seats this round.'.format(
                    target))

        if len(parameters) > 1 and garnet_bribe:
            if parameters[-1].isdigit():
                garnets = int(parameters[-1])
                if garnets < 0:
                    raise DiscordBotException(
                        'Error: non-negative amount of garnets')
            else:
                raise DiscordBotException('invalid amount of garnets {}'.format(parameters[1]))
        else:
            garnets = 0

        player.add_proposal_to(target, garnets)

        await player.send(
            'Proposal sent to {target} offering {garnets} garnets.\n'
            'Those garnets are locked up until either player cancels the proposal.\n'
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

    async def _command_cancel(self, parameters: List[str], player: Player):
        proposals = player.outgoing_proposals
        if not proposals:
            raise DiscordBotException(
                'Error: you have no outgoing proposals')

        if len(proposals) > 1 and not parameters[0]:
            raise DiscordBotException(
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
                raise DiscordBotException(
                    'Error: found no proposal matching {}.'.format(parameters[0]))

        proposal.cancel()
        await self._message_cancel(canceler=player, receiver=proposal.target)

    async def _command_cancelall(self, _parameters: List[str], player: Player):
        if not player.outgoing_proposals:
            raise DiscordBotException(
                'Error: you have no outgoing proposals')

        for proposal in player.outgoing_proposals:
            proposal.cancel()

            await self._message_cancel(canceler=player,
                                       receiver=proposal.target)

    @staticmethod
    def _common_handle_incoming_proposal(parameters: List[str], player: Player) -> Proposal:
        proposals = player.incoming_proposals
        if not proposals:
            raise DiscordBotException(
                'Error: you have no incoming proposals')

        if len(proposals) > 1 and not parameters[0]:
            raise DiscordBotException(
                'Error: you have multiple incoming proposals, '
                'please specify '
                'the name, display name, id or seat of the player '
                'to which you want to cancel your proposal.')

        # We only have one proposal and didn't specify a parameter, so return it
        if not parameters:
            return proposals[0]

        for prop in proposals:
            if prop.source.matches(' '.join(parameters)):
                return prop

        raise DiscordBotException(
            'Error: found no proposal matching {}.'.format(parameters[0]))

    async def _command_accept(self, parameters: List[str], player: Player):
        proposal = self._common_handle_incoming_proposal(parameters, player)

        if player.swapped:
            raise DiscordBotException(
                'Error: you have already swapped this round.')

        if proposal.source.swapped:
            await proposal.source.send(
                '{} tried accepting your proposal, but you have already swapped.'
                'Proposal canceled.'.format(
                    player))
            proposal.cancel()
            raise DiscordBotException(
                '{} has already swapped this round. Proposal canceled.'.format(proposal.source))


        proposal.accept()

        if self._game.options['public_swaps']:
            other_proposals_string = '\nAll your other proposals have been canceled.'
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

        if self._game.options['public_swaps']:
            swappers = [player, proposal.source]
            random.shuffle(swappers)
            await self._game_channel.send(
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

                    await self._message_reject(rejecter, proposer)

                else:
                    receiver = prop.target
                    canceler = prop.source

                    await self._message_cancel(canceler, receiver)

    async def _command_reject(self, parameters: List[str], player: Player):
        proposal = self._common_handle_incoming_proposal(parameters, player)

        proposal.cancel()


        await self._message_reject(rejecter=player, proposer=proposal.source)

    async def _command_rejectall(self, _parameters: List[str], player: Player):
        if not player.incoming_proposals:
            raise DiscordBotException(
                'Error: you have no incoming proposals')
        for proposal in player.incoming_proposals:
            proposal.cancel()

            await self._message_reject(rejecter=player,
                                       proposer=proposal.source)


    @staticmethod
    async def _message_cancel(canceler, receiver):
        await canceler.send(
            'Proposal to {} canceled. Any locked up garnets are returned.'.format(receiver))

        await receiver.send(
            '{} has canceled their proposal to you.'.format(
                canceler))

    @staticmethod
    async def _message_reject(rejecter, proposer):
        await rejecter.send(
            'Proposal from {} rejected.'.format(
                proposer))
        await proposer.send(
            '{} has rejected your proposal. Any locked up garnets are returned.'.format(
                rejecter))







def main():
    with open('discord_token') as f: #pylint: disable=invalid-name
        token = f.read().strip()

    bot = DiscordBot()
    bot.run(token)


if __name__ == '__main__':
    main()
