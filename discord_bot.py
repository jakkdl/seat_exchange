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
        #'!close'     : self._command_close
    #}


    def __init__(self):
        super().__init__()
        self._game: discord_game.DiscordGame = None
        self._players: Dict[discord.User, Player] = {}
        self._game_channel: discord.TextChannel = None
        self._game_started: float = 0.0

        self._round_length: int = 60

        #TODO: implement !kick
        self._admin_commands = {
            #!kick
            #!forcenextround
            '!close'     : self._command_close,
            '!forcejoin' : self._command_forcejoin,
            '!forcejoinall' : self._command_forcejoinall,
            '!destroy'   : self._command_destroy
        }

        #TODO: implement !proposals
        self._dm_commands = {
            '!incoming' : self._command_incoming,
            '!outgoing' : self._command_outgoing,
            '!seating'  : self._command_seating,

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
            '!setoption': self._command_setoption

        }

        self._public_commands = {
            '!create'   : self._command_create,
            '!join'     : self._command_join
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
       #except Exception as error: # pylint: disable=broad-except
       #    print(error)
       #    await message.channel.send(
       #        'Error: {}'.format(error))

    async def _parse_command(self, command, parameters: List[str], author, channel):
        if command in self._admin_commands:
            #await self.close()
            #TODO: if admin
            await self._admin_commands[command](parameters,
                                                author,
                                                channel)

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
            if ' '.join(parameters) in (str(member.id), member.name, member.display_name):
                await self._command_join(parameters, member, channel)

    async def _command_forcejoinall(self, parameters: List[str], _author, channel):
        for member in channel.guild.members:
            await self._command_join(parameters, member, channel)

    async def _command_start(self, _parameters: List[str], _player: Player, _channel):
        if self._game.running:
            raise DiscordBotException(
                'Game already running.')

        import time
        game_started = time.time()
        self._game_started = game_started
        self._game.start_game()

        while True:
            await self._message_new_round()

            await asyncio.sleep(self._round_length)

            print('finished sleep')
            # game canceled, quit silently

            # another game was created in the meantime
            if game_started != self._game_started:
                print('quitting silently, another game started')
                return

            if not self._game.running:
                print('game canceled')
                return

            # Game Over
            if self._game.game_over:
                await self._message_game_over()
                return

            # Otherwise, continue with next round and loop
            self._game.new_round()


    async def _command_setoption(self, parameters: List[str], _player: Player, channel):
        if len(parameters) < 2:
            raise DiscordBotException('please specify option and value')
        if parameters[0] == 'round_length':
            if not parameters[1].isdigit():
                raise DiscordBotException('Round length must be an integer (seconds).')
            self._round_length = int(parameters[1])
            await channel.send('Round length set to {} seconds.'.format(int(parameters[1])))



    async def _message_new_round(self):
        for player in self._players.values():
            # TODO: pylint gives missing-format-attribute if i try to acces
            # the attributes of self._game inside the format string.
            # why??
            await player.send(
                'Round {current_round} started.\n'
                'Your seat is {player.seat} and your number is {player.number}.\n'
                'You have {player.garnets} garnets.\n'
                '{current_x} is X\n'
                'Type `!help` for help or `!commands` for commands.'.format(
                    player=player,
                    current_round=self._game.current_round,
                    current_x=self._game.current_x
                ))

        await self._game_channel.send(
            'Round {current_round} started\n'
            'Current table layout is:\n'
            '{table_layout}\n'
            'The longest streak is {streak}.\n'
            'Streak required to win is {win_streak_length}.\n'
            '{current_x} is X'.format(
                current_round=self._game.current_round,
                table_layout=self._get_table_layout_string(),
                streak=self._game.longest_streak,
                win_streak_length=self._game.win_streak_length,
                current_x=self._game.current_x
            ))

    async def _message_game_over(self):
        await self._game_channel.send(
            '**Game Over!**\n'
            'Round: {current_round}'
            'The following players completed a streak and won {win_garnets} garnets:\n'
            '{winning_players}'
            '{losing_player} was X and lost {lose_garnets} garnets.'
            'Results in order of garnets:\n'
            '{player_garnets}'.format(
                current_round=self._game.current_round,
                winning_players=self._get_winner_string(),
                losing_player=self._game.current_x_player,
                win_garnets=10,
                lose_garnets=10,
                player_garnets=self._get_garnets_string()
            ))

    def _get_table_layout_string(self):
        #I'm sorry
        return ''.join([
            'Seat {0:>2} - {1}\n'.format(
                seat,
                self._game.player_in_seat(seat))
            for seat in range(len(self._players))])

    def _get_winner_string(self):
        return ''.join([
            'Seat {0.seat:>2} - Number {0.number:>2} - {0}\n'.format(winner)
            for winner in self._game.winners
        ])

    def _get_garnets_string(self):
        players = list(self._players.values())
        players.sort(key=lambda x: x.garnets)
        return '\n'.join([
            '{0.garnets:>3} - {0}'.format(player)
            for player in players
        ])

    @staticmethod
    async def _command_incoming(self, _parameters: List[str], player: Player):
        await player.send(player.incoming_proposals)

    async def _command_outgoing(self, _parameters: List[str], player: Player):
        await player.send(player.outgoing_proposals)

    async def _command_seating(self, _parameters: List[str], player: Player):
        await player.send(self._get_table_layout_string)

    async def _command_create(self, _parameters: List[str], _player: Player, channel):
        if self._game and self._game.running:
            raise DiscordBotException('game already exists')

        self._game = discord_game.DiscordGame()
        self._game_channel = channel
        await channel.send('Game created in this channel. Type !join to join')

    async def _command_destroy(self, _parameters: List[str], _player: Player, channel):
        if not self._game:
            raise DiscordBotException("game doesn't exists")

        self._game.stop_game()
        self._game_started = 0.0
        await channel.send('Game destroyed.')

    async def _command_join(self, _parameters: List[str], author, channel):
        if not self._game:
            raise DiscordBotException(
                'No game exists.')

        if author in self._players.values(): #compares ids
            raise DiscordBotException(
                '{} already joined'.format(author.display_name))

        self._players[author] = self._game.add_player(author)

        print('{0.name} has joined with id {0.id}'.format(author))
        await channel.send('{} has joined'.format(author.display_name))

    async def _command_leave(self, _parameters: List[str], player: Player, channel):
        if player not in self._players.values(): #compares ids
            raise DiscordBotException(
                'Error: {} has not joined.'.format(player))

        #send message asking for confirmation in the form of emoji reaction to message.
        if self._game.running:
            raise DiscordBotException(
                'Error: cannot leave game in progress (WIP)'
            )

        self._game.remove_player(player)
        self._players.pop(player)

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



    async def _command_propose(self, parameters: List[str], player: Player):
        if not parameters:
            raise DiscordBotException(
                'Error: please provide the id, seat, name or display name of a player')

        try:
            target = self._find_player(' '.join(parameters[:-1]))
            garnet_bribe = True
        except DiscordBotException:
            target = self._find_player(' '.join(parameters))
            garnet_bribe = False


        if not self._game.running:
            raise DiscordBotException(
                'Error: game is not running')

        if player.swapped:
            raise DiscordBotException(
                'Error: you have already swapped seats this round')

        if self._game.public_swaps and target.swapped:
            raise DiscordBotException(
                'Error: {} have already swapped seats this round.'.format(
                    target))

        verb = 'offering'
        direction = 1

        if len(parameters) > 1 and garnet_bribe:
            if parameters[-1].isdigit():
                garnets = int(parameters[-1])
                if garnets < 0:
                    verb = 'demanding'
                    direction = -1
            else:
                raise DiscordBotException('invalid amount of garnets {}'.format(parameters[1]))
        else:
            garnets = 0

        player.add_proposal_to(target, garnets)

        await player.send(
            'Proposal sent to {target} {verb} {garnets} garnets.\n'
            'You can cancel the proposal with `!cancel.`'.format(
                target=target,
                verb=verb,
                garnets=garnets*direction
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
            'Proposal received from {player} {verb} {garnets}.\n'
            '{message}'.format(
                player=player,
                verb=verb,
                garnets=garnets*direction,
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

        player.cancel_proposal(proposal)
        await self._message_cancel(canceler=player, receiver=proposal.target)

    async def _command_cancelall(self, _parameters: List[str], player: Player):
        for proposal in player.outgoing_proposals:
            player.cancel_proposal(proposal) #test to remove .target

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
            await player.send(
                '{} has already swapped this round. Proposal canceled.')
            await proposal.source.send(
                '{} tried accepting your proposal, but you have already swapped.'
                'Proposal canceled.'.format(
                    player))
            player.cancel_proposal(proposal)


        canceled_proposals = player.accept_incoming_proposal(proposal)

        if self._game.public_swaps:
            other_proposals_string = '\nAll your other proposals have been canceled.'
        else:
            other_proposals_string = ''

        player_verb = 'gained'
        source_verb = 'lost'
        direction = 1
        if proposal.garnets < 0:
            player_verb, source_verb = source_verb, player_verb
            direction = -1

        await player.send(
            'Proposal from {source} accepted.\n'
            'You have {verb} {garnets} garnets.\n'
            'You now have {player.garnets}.\n'
            'You have switched seats from {source.seat} to {player.seat}'
            '{other_proposals}'.format(
                source=proposal.source,
                player=player,
                other_proposals=other_proposals_string,
                verb = player_verb,
                garnets = proposal.garnets*direction
            ))

        await proposal.source.send(
            '{player} has accepted their proposal from you\n'
            'You have {verb} {garnets} garnets.\n'
            'You now have {source.garnets}.\n'
            'You have switched seats from {player.seat} to {source.seat}.'
            '{other_proposals}'
            .format(
                source=proposal.source,
                player=player,
                other_proposals=other_proposals_string,
                garnets=proposal.garnets*direction
            ))

        if self._game.public_swaps:
            swappers = [player, proposal.source]
            random.shuffle(swappers)
            await self._game_channel.send(
                '{0} have swapped with {1}.\n'
                '{0} is now in seat {0.seat}, '
                '{1} is now in seat {1.seat}.'.format(
                    swappers[0],
                    swappers[1]))

            for prop in canceled_proposals:
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

        player.reject_proposal(proposal)

        await self._message_reject(rejecter=player, proposer=proposal.source)

    async def _command_rejectall(self, player: Player, _parameters: List[str]):
        for proposal in player.incoming_proposals:
            player.reject_proposal(proposal)

            await self._message_reject(rejecter=player,
                                       proposer=proposal.source)


    @staticmethod
    async def _message_cancel(canceler, receiver):
        await canceler.send(
            'Proposal to {} canceled.'.format(receiver))

        await receiver.send(
            '{} has canceled their proposal to you.'.format(
                canceler))

    @staticmethod
    async def _message_reject(rejecter, proposer):
        await rejecter.send(
            'Proposal from {} rejected.'.format(
                proposer))
        await proposer.send(
            '{} has rejected your proposal.'.format(
                rejecter))







def main():
    with open('discord_token') as f: #pylint: disable=invalid-name
        token = f.read().strip()

    bot = DiscordBot()
    bot.run(token)


if __name__ == '__main__':
    main()
