# pragma pylint: disable=missing-docstring
import random
import asyncio
import discord


import discord_game

#TODO: police nickname changes


class DiscordBotException(Exception):
    pass

# pylint: disable=too-many-instance-attributes
# The commands variables are sorta ugly, but I can't make them static
# as they refer to self. If anybody reading this has a tip, hit me up.
class DiscordBot(discord.Client):

    def __init__(self):
        super().__init__()
        self._game = None
        self._players = {}
        self._game_channel = None
        self._game_started = None

        self._round_length_seconds = 300

        #TODO: implement !proposals
        self._dm_commands = {
            '!seating'  : self._command_seating,
            '!propose'  : self._command_propose,
            '!cancel'   : self._command_cancel,
            '!cancelall': self._command_cancelall,
            '!accept'   : self._command_accept,
            '!reject'   : self._command_reject,
            '!rejectall': self._command_rejectall
        }

        #TODO: implement !kick
        self._admin_commands = {
            '!close'     : self._command_close
        }

        #!stop
        self._public_commands = {
            '!start'    : self._command_start,
            '!create'   : self._command_create,
            '!join'     : self._command_join,
            '!leave'    : self._command_leave
        }

    async def on_ready(self):
        print('We have logged in as {0.user}'.format(self))
        await self.guilds[0].channels[0].send('Seat Exchange Bot v0.1')


    async def on_message(self, message):
        if message.author == self.user:
            return

        if not message.startswith('!'):
            return

        command = message.content.split(' ')[0]
        parameters = message.content.split(' ')[1:]

        try:
            self._parse_command(command, parameters, message.author, message.channel)


        except DiscordBotException as error:
            print(error)
            await message.channel.send(error)
        except discord_game.DiscordGameException as error:
            print(error)
            await message.channel.send(
                'Error in game engine: {}'.format(error))
        except Exception as error: # pylint: disable=broad-except
            print(error)
            await message.channel.send(
                'Error: {}'.format(error))

    def _command_close(self, _parameters, _author, channel):
        await channel.send('quitting...')
        await self.close()

    def _command_start(self, _parameters, _author, _channel):
        if self._game.game_running:
            raise DiscordBotException(
                'Game already running.')

        import time
        game_started = time.time()
        self._game_started = game_started
        self._game.start_game()

        while True:
            self._message_new_round()

            await asyncio.sleep(self._round_length_seconds)

            # game canceled, quit silently
            if not self._game.game_running:
                return

            # another game was created in the meantime
            if game_started != self._game_started:
                return

            # Game Over
            if self._game.game_over:
                self._message_game_over()
                return

            # Otherwise, continue with next round and loop
            self._game.new_round()





    def _message_new_round(self):
        current_round = self._game.current_round
        current_x = self._game.current_x

        for player in self._players.values():
            seat = self._game.get_seat(player.id)
            number = self._game.get_number(player.id)
            await player.send(
                'Round {current_round} started.\n'
                'Your seat is {seat} and your number is {number}.\n'
                '{current_x} is X'
                'Type `!help` for help or `!commands` for commands.'.format(
                    current_round=current_round,
                    seat=seat,
                    number=number,
                    current_x=current_x
                ))

        await self._game_channel.send(
            'Round {current_round} started\n'
            'Current table layout is:\n'
            '{table_layout}\n'
            'The longest loop is {loop}.\n'
            '{current_x} is X'.format(
                current_round=current_round,
                table_layout=self._get_table_layout_string,
                loop=self._game.longest_loop,
                current_x=current_x
            ))

    def _message_game_over(self):
        await self._game_channel.send(
            '**Game Over!**\n'
            'Round: {current_round}'
            'The following players completed a streak and won:\n'
            '{winning_players}'
            '{losing_player} was X and lost'.format(
                current_round=self._game.current_round,
                winning_players=self._get_winner_string,
                losing_player=self._players[self._game.current_x_player].display_name))

    def _get_table_layout_string(self):
        #I'm sorry
        return ''.join([
            'Seat {0:>2} - {1}\n'.format(
                seat,
                self._players[self._game.get_player_in_seat(seat)].display_name)
            for seat in range(len(self._players))])

    def _get_winner_string(self):
        return ''.join([
            'Seat {0:>2} - Number {1:>2} - {2}'.format(
                winner[0], winner[1], self._players[winner[2]].display_name)
            for winner in self._game.winners])

    def _command_seating(self, _parameters, author):
        await author.send(self._get_table_layout_string)

    def _command_create(self, _parameters, _author, channel):
        if self._game:
            raise DiscordBotException('game already exists')

        self._game = discord_game.DiscordGame()
        self._game_channel = channel
        await channel.send('Game created in this channel. Type !join to join')

    def _parse_command(self, command, parameters, author, channel):
        if command in self._admin_commands:
            #if admin
            self._admin_commands[command](parameters,
                                          author,
                                          channel)

        elif channel is discord.TextChannel:
            if command in self._public_commands:
                self._public_commands[command](parameters,
                                               author,
                                               channel)
            elif command in self._dm_commands:
                raise DiscordBotException(
                    'Command {} not allowed in this channel.'.format(command))

            else:
                raise DiscordBotException(
                    'Unknown command {}.'.format(command))

        elif channel is discord.DMChannel:
            if command in self._dm_commands:
                self._dm_commands[command](parameters, author)

            elif command in self._public_commands:
                raise DiscordBotException(
                    'Command {} not allowed in this channel.'.format(command))

            else:
                raise DiscordBotException('Unknown command {}'.format(
                    command))


        else:
            raise DiscordBotException(
                'Channel not supported.')


    def _command_join(self, _parameters, author, channel):
        if author in self._players.values(): #compares ids
            raise DiscordBotException(
                '{} already joined'.format(author.display_name))

        self._game.add_player(author.id)
        self._players[author.id] = author

        print('{0.name} has joined with id {0.id}'.format(author))
        await channel.send('{} has joined'.format(author.display_name))

    def _command_leave(self, _parameters, author, channel):
        if author not in self._players.values(): #compares ids
            raise DiscordBotException(
                'Error: {} has not joined.'.format(author.display_name))

        #send message asking for confirmation in the form of emoji reaction to message.
        if self._game.game_running:
            raise DiscordBotException(
                'Error: cannot leave game in progress (WIP)'
            )

        self._game.remove_player(author.id)
        self._players.pop(author.id)

        await channel.send('{} has left the game'.format(author.display_name))



    #tries to match search key by id, name, display_name or seat
    def _find_player(self, search_key):
        if search_key.isdigit():
            #id
            if int(search_key) in self._players.keys():
                return self._players[int(search_key)]

            #seat
            try:
                player_id = self._game.get_player_in_seat(search_key)
                return self._players[player_id]
            except IndexError:
                pass

        #name or display name
        for player in self._players:
            if search_key in (player.name, player.display_name):
                return player

        raise DiscordBotException(
            'Error: cannot find any matches for {}'.format(search_key))

    #TODO: garnet bribe?
    def _command_propose(self, author, parameters):
        if not parameters:
            raise DiscordBotException(
                'Error: please provide the id, seat, name or display name of a player')

        target = self._find_player(parameters[1])

        if not self._game.game_running:
            raise DiscordBotException(
                'Error: game is not running')

        if self._game.have_swapped(author.id):
            raise DiscordBotException(
                'Error: you have already swapped seats this round')


        if self._game.public_swaps and self._game.have_swapped(target.id):
            raise DiscordBotException(
                'Error: {} have already swapped seats this round.'.format(
                    target.display_name))

        self._game.add_outgoing_proposal(author.id, target.id)

        await author.send(
            'Proposal sent to {}.\n'
            'You can cancel the proposal with `!cancel.`'.format(
                target.display_name))


        if self._game.have_swapped(target.id):
            message = (
                'You have already swapped seats this round, and '
                'cannot accept this proposal.\n'
                'You can decline the proposal with `!decline`.')
        else:
            message = (
                'Proposal received from {1}.\n'
                'You can accept the proposal with `!accept'
                'or decline it with `!decline`.')

        await target.send(
            'Proposal received from {}.\n'
            '{}'.format(
                author.display_name, message))

    def _command_cancel(self, author, parameters):
        proposals = self._game.get_outgoing_proposals(author.id)
        if not proposals:
            raise DiscordBotException(
                'Error: you have no outgoing proposals')

        if len(proposals) > 1 and not parameters[0]:
            raise DiscordBotException(
                'Error: you have multiple outgoing proposals, '
                'please specify '
                'the name, display name, id or seat of the player '
                'to which you want to cancel your proposal.')

        if not parameters[0]:
            target = self._players[proposals[0].target_id]
        else:
            target = self._find_player(parameters[0])

        self._game.cancel_proposal(author.id, target.id)

        self._message_cancel(canceler=author, receiver=target)

    def _command_cancelall(self, author, _parameters):
        for proposal in self._game.get_outgoing_proposals(author.id):
            self._game.cancel_proposal(author.id, proposal.target_id)

            self._message_cancel(canceler=author,
                                 receiver=self._players[proposal.target.id])

    def _command_accept(self, author, parameters):
        source = self._common_handle_incoming_proposal(author, parameters)

        if self._game.have_swapped(author.id):
            raise DiscordBotException(
                'Error: you have already swapped this round.')

        if self._game.have_swapped(source.id):
            await author.send(
                '{} has already swapped this round. Proposal canceled.')
            await source.send(
                '{} tried accepting your proposal, but you have already swapped.'
                'Proposal canceled.'.format(
                    author.display_name))
            self._game.cancel_proposal(source.id, author.id)


        canceled_proposals = self._game.accept_incoming_proposal(source.id, author.id)

        if self._game.public_swaps:
            other_proposals = 'All your other proposals have been canceled.'

        #TODO: print seats
        await author.send(
            'Proposal from {} accepted.\n'
            'You have switched seats from {} to {}\n'
            '{}'.format(
                source.display_name, 0, 0, other_proposals))

        await source.send(
            '{} has accepted their proposal from you'.format(
                author.display_name))

        if self._game.public_swaps:
            swappers = [author, source]
            random.shuffle(swappers)
            self._game_channel.send(
                '{0} have swapped with {1}.\n'
                '{0} is now in seat {2}, {1} is now in seat {3}.'.format(
                    swappers[0].display_name,
                    swappers[1].display_name,
                    self._game.get_seat(swappers[0].id),
                    self._game.get_seat(swappers[1].id)))

            for proposal in canceled_proposals:
                if proposal.source_id not in (source.id, author.id):
                    proposer = self._players[proposal.source_id]
                    rejecter = self._players[proposal.target_id]

                    self._message_reject(rejecter, proposer)

                else:
                    receiver = self._players[proposal.target_id]
                    canceler = self._players[proposal.source_id]

                    self._message_cancel(canceler, receiver)

    def _command_reject(self, author, parameters):
        source = self._common_handle_incoming_proposal(author, parameters)

        self._game.cancel_proposal(source.id, author.id)

        self._message_reject(rejecter=author, proposer=source)

    def _command_rejectall(self, author, _parameters):
        for proposal in self._game.get_outgoing_proposals(author.id):
            self._game.cancel_proposal(proposal.source_id, author.id)

            self._message_reject(rejecter=author,
                                 proposer=self._players[proposal.source_id])


    @staticmethod
    def _message_cancel(canceler, receiver):
        await canceler.send(
            'Proposal to {} canceled.'.format(receiver.display_name))

        await receiver.send(
            '{} has canceled their proposal to you.'.format(
                canceler.display_name))

    @staticmethod
    def _message_reject(rejecter, proposer):
        await rejecter.send(
            'Proposal from {} rejected.'.format(
                proposer.display_name))
        await proposer.send(
            '{} has rejected your proposal.'.format(
                rejecter.display_name))

    def _common_handle_incoming_proposal(self, author, parameters):
        proposals = self._game.get_incoming_proposals(author.id)
        if not proposals:
            raise DiscordBotException(
                'Error: you have no incoming proposals')

        if len(proposals) > 1 and not parameters[0]:
            raise DiscordBotException(
                'Error: you have multiple incoming proposals, '
                'please specify '
                'the name, display name, id or seat of the player '
                'to which you want to cancel your proposal.')

        if not parameters[0]:
            return self._players[proposals[0].source_id]

        return self._find_player(parameters[0])







def main():
    with open('discord_token') as f: #pylint: disable=invalid-name
        token = f.read().strip()

    bot = DiscordBot()
    bot.run(token)


if __name__ == '__main__':
    main()
