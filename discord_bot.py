# pragma pylint: disable=missing-docstring
from typing import Dict, List

import discord  # type: ignore
from discord import TextChannel

from discord_game import DiscordGame

import seat_commands as commands

# from strings import WIKIPEDIA_URL, RULES_STR
from seat_typing import SeatException

# TODO: police nickname changes


class DiscordBotException(SeatException):
    pass


# pylint: disable=too-many-instance-attributes
# The commands variables are sorta ugly, but I can't make them static
# as they refer to self. If anybody reading this has a tip, hit me up.
class DiscordBot(discord.Client):  # type: ignore
    def __init__(self) -> None:
        super().__init__()
        self.games: Dict[TextChannel, DiscordGame] = {}
        self.players: Dict[discord.user, DiscordGame] = {}

        # TODO: implement !kick
        # self._admin_commands = {
        # !kick
        # !forcenextround - impossible?
        # '!forcequit':        self._command_forcequit,
        # '!forcejoin':        self._command_forcejoin,
        # '!forcejoinall':     self._command_forcejoinall,
        # '!forceleave':       self._command_forceleave,
        # '!forcestart':        self._command_forcestart,
        # '!forcestop':        self._command_forcestop,
        # '!forceseatnumbers': self._command_forceseatnumbers,
        # '!admincommands':    self._command_admincommands
        # }

        # self._public_player_commands = {
        # '!ready':        self._command_ready,
        # '!unready':      self._command_unready,
        # '!stop':         self._command_stop,
        # '!leave':        self._command_leave,
        # '!setoption':    self._command_setoption,
        # '!getoptions':   self._command_getoptions,
        # }

        # self._public_commands = {
        # '!help':         self._public_command_help,
        # '!command':      self._public_command_commands,
        # '!commands':     self._public_command_commands,
        # '!source':       self._public_command_source,
        # '!players':      self._public_command_players,
        # '!join':         self._command_join,
        # }

        # self._dm_commands = {
        # '!help':         self._dm_command_help,
        # '!command':      self._dm_command_commands,
        # '!commands':     self._dm_command_commands,
        # '!rules':        self._dm_command_rules,
        # '!source':       self._dm_command_source,
        # }

        command_list = (
            commands.Ready(self.games),
            commands.Unready(self.games),

            commands.Join(self.games),
            commands.CreateJoin(self.games),
            commands.RecreateJoin(self.games),

            commands.Shutdown(self),
            commands.ForceStart(self.games),
            commands.ListPlayers(self.games)
        )

        self.command_dict: Dict[str, List[commands.CommandType]] = {}
        for command in command_list:
            for command_name in command.command_name_list:
                if command_name not in self.command_dict:
                    self.command_dict[command_name] = [command]
                else:
                    self.command_dict[command_name].append(command)

        # TODO
        self._dm_player_commands = (
            DiscordGame(None).dm_player_commands.keys())

    async def on_ready(self) -> None:
        print('We have logged in as {0.user}'.format(self))
        for guild in self.guilds:
            for channel in guild.channels:
                if channel.name == 'testing':
                    await channel.send('Seat Exchange Bot v0.1')

    async def on_message(self, message: discord.message) -> None:
        if message.author == self.user:
            return

        if not message.content.startswith('!'):
            return

        command = message.content.split(' ')[0][1:]
        # parameters = message.content.split(' ')[1:]

        if command in self.command_dict:
            command_message = commands.CommandMessage(message)
            errors = []
            for matching_command in self.command_dict[command]:
                try:
                    await matching_command.execute(command_message)
                    return
                except SeatException as error:
                    errors.append(error)
            print(errors)
            await message.channel.send('\n'.join(str(x) for x in errors))

            return

        # try:
        #     await self._parse_command(command, parameters, message.author,
        #                               message.channel)

        # except DiscordBotException as error:
        #     print(error)
        #     await message.channel.send(error)
        # except DiscordGameException as error:
        #     print(error)
        #     await message.channel.send(error)
        # except PlayerGameException as error:
        #     print(error)
        #     await message.channel.send(
        #         'Error in game engine: {}'.format(error))

    # async def on_reaction_add(self, reaction, _user):  # TODO
    #     print('reaction added')
    #     message = reaction.message
    #     channel = message.channel
    #     if message.content != '!stop':
    #         return

    #     if not self._game_started:
    #         print('game not started')
    #         return

    #     if message.created_at.timestamp() < self._game_started:
    #         print('old message, {} < {}'.format(
    #             message.created_at.timestamp(), self._game_started))
    #         return

    #     if reaction.count >= len(self.players)//2:
    #         await channel.send('Game stopped.')
    #         self.games[channel].stop()

    # async def _parse_command(self, command, parameters: List[str], author,
    #                          channel) -> None:
    #     if command in self._admin_commands:
    #         # TODO: if admin
    #         for role in author.roles:
    #             if role.name.lower() == 'game admin':
    #                 await self._admin_commands[command](parameters,
    #                                                     author,
    #                                                     channel)
    #                 break
    #         else:
    #             raise DiscordBotException('Unauthorized.')

    #     elif isinstance(channel, discord.TextChannel):
    #         await self._parse_public_command(command, parameters, author,
    #                                          channel)

    #     elif isinstance(channel, discord.DMChannel):
    #         await self._parse_dm_command(command, parameters, author)

    #     else:
    #         raise DiscordBotException(
    #             'Channel not supported.')

    # async def _parse_public_command(self, command: str,
    # parameters: List[str],
    #                                 author, channel):
    #     if command in self._public_commands:
    #         await self._public_commands[command](parameters,
    #                                              author,
    #                                              channel)
    #     elif command in self._public_player_commands:
    #         if channel not in self.games:
    #             raise DiscordBotException(
    #                 'Error: No game running in this channel.')
    #         game = self.games[channel]
    #         if author not in game.players:
    #             raise DiscordBotException(
    #                 'Error: {} not a player in the game in '
    #                 'this channel.'.format(author))
    #         await self._public_player_commands[command](
    #             parameters,
    #             game.discord_players[author],
    #             channel)
    #     elif (command in self._dm_player_commands
    #           or command in self._dm_commands):
    #         raise DiscordBotException(
    #             'Command `{}` only allowed in direct messages.'
    #             ''.format(command))

    #     else:
    #         raise DiscordBotException(
    #             'Unknown command `{}`.'.format(command))

    # async def _parse_dm_command(self, command: str, parameters: List[str],
    #                             author):

    #     if command in self._dm_commands:
    #         await self._dm_commands[command](parameters, author)
    #         return

    #     if command in self._public_commands:
    #         raise DiscordBotException(
    #             'Command `{}` only allowed in public channels.'.format(
    # command)
    #         )

    #     if command in self._public_player_commands:
    #         raise DiscordBotException(
    #             'Command `{}` only allowed in a public game channel.'
    #             ''.format(command))

    #     for i in self.games.values():
    #         if author in i.players:
    #             player = i.discord_players[author]
    #             game = i
    #             break
    #     else:
    #         raise DiscordBotException(
    #             'Command `{}` is only for players that have joined a game.'
    #             'Please `!join` a game in a public game channel first.'
    #             ''.format(command))

    #     if command in self._dm_player_commands:
    #         await game.dm_player_commands[command](
    #             parameters, player)

    #     else:
    #         raise DiscordBotException('Unknown command `{}`'.format(
    #             command))

    # async def _command_forcequit(self, _parameters: List[str], _author,
    #                              channel):
    #     await channel.send('closing...')
    #     print('closing...\n\n')
    #     await self.close()

    # async def _command_forcejoin(self, parameters: List[str],
    #                             _author, channel):
    #    for member in channel.guild.members:
    #        if ' '.join(parameters).lower() in (str(member.id),
    #                                            member.name.lower(),
    #                                            member.display_name.lower()):
    #            await self._command_join(parameters, member, channel)
    #            break
    #    else:
    #        raise DiscordBotException('Invalid member {}'.format(
    #            ' '.join(parameters)))

    # async def _command_forceleave(self, parameters, _author, channel):
    #    if channel not in self.games:
    #        raise DiscordBotException('No game in this channel.')

    #    for player in self.games[channel].players.values():
    #        if player.matches(' '.join(parameters)):
    #            await self._command_leave(parameters, player, channel)
    #            break
    #    else:
    #        raise DiscordBotException('Invalid player {}'.format(
    #            ' '.join(parameters)))

    # async def _command_forcejoinall(self, parameters: List[str], _author,
    #                                channel):
    #    for member in channel.members:
    #        try:
    #            await self._command_join(parameters, member, channel)
    #        except DiscordBotException:
    #            pass

    # async def _command_ready(self,
    #                          _parameters: List[str],
    #                          player: Player,
    #                          _channel):
    #     """Sets player to be ready.

    #     Triggering chain reaction that may start the game.
    #     Assumes that player is valid and in a game."""
    #     player.ready()

    # async def _command_unready(self,
    #                            _parameters: List[str],
    #                            player: Player,
    #                            _channel):
    #     """Sets player to be unready.

    #     If start countdown has started this will cancel that.
    #     Assumes that player is valid and in a game."""
    #     player.unready()

    # async def _command_forcestart(self,
    #                               _parameters: List[str],
    #                               _player: Player,
    #                               channel):
    #     if channel not in self.games:
    #         raise DiscordBotException(
    #             'No game in this channel')

    #     await self.games[channel].start()

    # def _resolve_botswaps(self):
    #     def highest_proposal_bribe(player: Player, botswap) -> int:
    #         def get_value(proposal: Proposal) -> int:
    #             print('get value', proposal.source.swapped,
    #                   proposal.target.swapped,
    #                   proposal == botswap)
    #             if (proposal.source.swapped
    #                     or proposal.target.swapped
    #                     or proposal == botswap):
    #                 return 0
    #             return proposal.garnets

    #         proposal = max(player.incoming_proposals,
    #                        key=get_value,
    #                        default=None)
    #         if proposal:
    #             return proposal.garnets
    #         return 0

    #     botswaps = []

    #     # get all botswaps from players
    #     for player in self.players.values():
    #         for botswap in player.botswaps:
    #             botswaps.append((player, botswap,))

    #     print("len(botswaps): {}".format(len(botswaps)))

    #     random.shuffle(botswaps)

    #     # sort them by largest garnets first
    #     botswaps.sort(key=lambda x: -x[1].garnets)

    #     for player, botswap in botswaps:
    #         print(botswap.garnets,
    #               highest_proposal_bribe(botswap.source, botswap),
    #               highest_proposal_bribe(botswap.target, botswap))
    #         if botswap.source == botswap.target:
    #             print('same-swap')
    #             if botswap.garnets > highest_proposal_bribe(botswap.source,
    #                                                         botswap):
    #                 try:
    #                     botswap.accept()
    #                     botswap.source.garnets += botswap.garnets
    #                     player.garnets -= botswap.garnets

    #                 except PlayerGameException as exception:
    #                     print(botswap, exception)

    #         if (botswap.garnets > highest_proposal_bribe(botswap.source,
    #                                                      botswap)
    #                 + highest_proposal_bribe(botswap.target, botswap)):
    #             try:
    #                 sgarnets = botswap.source.garnets
    #                 tgarnets = botswap.target.garnets
    #                 print('bsw', sgarnets, tgarnets, player.garnets,
    #                       botswap.garnets)
    #                 botswap.accept()
    #                 botswap.source.garnets = (sgarnets +
    #                                           math.ceil(botswap.garnets*1.5))
    #                 botswap.target.garnets = (tgarnets +
    #                                           math.floor(botswap.garnets/2))
    #                 player.garnets -= botswap.garnets
    #                 print('bsw', sgarnets, tgarnets, player.garnets)
    #             except PlayerGameException as exception:
    #                 print(botswap, exception)

    # TODO: wants the message
    # async def _command_stop(self, _parameters: List[str], _player: Player,
    #                         channel):
    #     if not self._game_started:
    #         raise DiscordBotException('Game not started')

    #     await channel.send('If {} people react with a single emoji to '
    #                        'the `!stop` message '
    #                        'the game will be stopped'.format(
    #                            len(self.players)//2))

    # def _stop_game(self):
    #     self._game_started = 0.0
    #     self._game = DiscordGame(self._game.options)
    #     self.players = {}

    # async def _command_getoptions(self, _parameters: List[str],
    #                               _player: Player, channel):
    #     await channel.send('```{}```'.format(
    #         '\n'.join(
    #             ['{}: {}'.format(key, self.games[channel].game.options[key])
    #              for key in self.games[channel].game.options]
    #         )))

    # async def _command_setoption(self, parameters: List[str],
    #                              _player: Player, channel):
    #     async def set_option(key: str, value: Any):
    #         self.games[channel].game.options[key] = value
    #         await channel.send('{} set to {}'.format(key, value))

    #     if len(parameters) < 2:
    #         raise DiscordBotException('Please specify option and value.')

    #     key = parameters[0]
    #     value = parameters[1]
    #     if key not in self.games[channel].game.options:
    #         raise DiscordBotException('Invalid option.')

    #     if value.isdigit() and key in ('win_garnets', 'x_garnets',
    #                                    'start_garnets', 'round_length'):
    #         await set_option(key, int(value))

    #     elif (value[0] == '-' and value[1:].isdigit()
    #           and key in ('win_garnets', 'x_garnets')):
    #         await set_option(key, int(value))

    #     elif key == 'public_swaps' and value.lower() in ('true', 'false'):
    #         await set_option(key, value.lower() == 'true')

    #     else:
    #         raise DiscordBotException('Invalid value {} for key {}.'
    # ''.format(value, key))

    # async def _command_admincommands(
    #         self, _parameters: List[str],
    #         _player: Player,
    #         channel):  # pylint: disable=unused-argument
    #     await channel.send('`' + '` `'.join(self._admin_commands.keys())
    # + '`' )

    # async def _dm_command_help(
    #         self, _parameters: List[str],
    #         player: Player):  # pylint: disable=unused-argument
    #     await player.send(
    #         'Type `!help` to see this help text.\n'
    #         'Type `!rules` for an overview and explanation on how the game '
    #         'works.\n'
    #         'Type `!commands` for a list of the commands available through '
    #         'direct messages.\n'
    #         'Most of the commands are only available to players that have '
    #         'joined the game.\n'
    #         'Knowing the rules, most of the commands should be '
    #         'self-explanatory, and they will '
    #         "give helpful error messages if you're invoking them "
    #         "incorrectly.\n"
    #         'Help for individual commands is not yet implemented, so you '
    #         'will have to experiment '
    #         'or ask :).'
    #     )

    # async def _dm_command_source(
    #         self, _parameters: List[str],
    #         player: Player):  # pylint: disable=unused-argument
    #     await player.send('https://github.com/h00701350103/seat_exchange')

    # async def _dm_command_commands(
    #         self, _parameters: List[str],
    #         player: Player):  # pylint: disable=unused-argument
    #     await player.send(
    #         'Command list for private messages:\n'
    #         'General commands: `{general}`\n'
    #         'Player-only commands: `{player}`'.format(
    #             general='` `'.join(self._dm_commands.keys()),
    #             player='` `'.join(self._dm_player_commands)  # TODO
    #         )
    #     )

    # async def _dm_command_rules(self, _parameters: List[str],
    # player: Player):
    #     await player.send(RULES_STR.format(
    #         url=WIKIPEDIA_URL,
    #         start_garnets=20,  # self._game.options['start_garnets'],
    #         win_garnets=10,  # self._game.options['win_garnets'],
    #         lose_garnets=10,  # self._game.options['x_garnets']*-1
    #     ))

    # async def _public_command_help(self, parameters: List[str],
    #                                author: discord.User,
    #                                channel):
    #     await channel.send('Information sent in a private message.\n'
    #                        'Type `!commands` for list of public commands.')
    #     await self._dm_command_help(parameters, author)

    # async def _public_command_commands(self, _parameters: List[str],
    #                                    _author: discord.User,
    #                                    channel):
    #     await channel.send(
    #         'Command list for public channels:\n'
    #         'General commands: `{general}`\n'
    #         'Player-only commands: `{player}`'.format(
    #             general='` `'.join(self._public_commands.keys()),
    #             player='` `'.join(self._public_player_commands)
    #         )
    #     )

    # async def _public_command_players(self, _parameters: List[str],
    #                                   _author: discord.User,
    #                                   channel):
    #     if channel not in self.games:
    #         await channel.send('No game exists in this channel.')
    #         return
    #     game = self.games[channel]
    #     if not game.players:
    #         await channel.send('No players in the game')
    #         return
    #     await channel.send('```Players joined:\n'
    #                        '{}```'.format('\n'.join([
    #                            str(p) for p in game.players])))

    # async def _public_command_source(
    #         self,
    #         _parameters: List[str],
    #         _author: discord.User,
    #         channel):  # pylint: disable=unused-argument
    #     await channel.send('https://github.com/h00701350103/seat_exchange')

    # async def _command_forcestop(self, _parameters: List[str],
    #                              _player: Player, channel):

    #     if channel not in self.games:
    #         raise DiscordBotException('No game in this channel')

    #     self.games[channel].stop()
    #     await channel.send('Game stopped.')

    # async def _command_forceseatnumbers(self, _parameters: List[str],
    #                                     _player: Player, channel):
    #     if channel not in self.games:
    #         raise DiscordBotException(
    #             'No game running in this channel.')

    #     game = self.games[channel].game
    #     await channel.send('```Seat Number\n'
    #                        '{}```'.format('\n'.join([
    #                            '{seat:>3} {number:>3} {player}'.format(
    #                                seat=Seat(seat),
    #                                number=game.number_in_seat(Seat(seat)),
    #                                player=game.player_in_seat(Seat(seat))
    #                            )
    #                            for seat in range(len(game.players))
    #                        ])))

    # async def _command_join(self, _parameters: List[str], author, channel):
    #     if channel not in self.games:
    #         self.games[channel] = DiscordGame(channel, {})
    #         await channel.send('Creating new game in {}'.format(channel))

    #     elif self.games[channel].game_over or self.games[channel].stopped:
    #         self.games[channel] = DiscordGame(
    #             channel,
    #             self.games[channel].game.options)
    #         await channel.send('Restarting new game with the same options.')

    #     elif self.games[channel].running:
    #         raise DiscordBotException(
    #             'Error: {} cannot join game in progress'.format(author))

    #     for game in self.games.values():
    #         if author in game.players:  # TODO
    #             raise DiscordBotException(
    #                 'Error: {} already joined a game in {}.'.format(
    #                     author.display_name, game.channel))

    #     self.games[channel].add_player(
    #         Player(discord_user=author,
    #                discord_game=self.games[channel].game))

    #     self.players[author] = self.games[channel]

    #     print('{0.name} has joined {1}'.format(author, channel))
    #     await channel.send('{} has joined'.format(author.display_name))

    # async def _command_kick(self, parameters, _author, channel):
    #     if channel not in self.games:
    #         raise DiscordBotException(
    #             'No game in this channel.')

    #     game = self.games[channel]
    #     player = game.find_player(' '.join(parameters))

    #     game.game.remove_player(player)
    #     self.players.pop(player.user)
    #     await channel.send(
    #         '{} has been kicked from the game.'.format(player))

    # async def _command_leave(self, _parameters: List[str],
    #                          player: Player, channel):
    #     if channel not in self.games:
    #         raise DiscordBotException(
    #             'No game in this channel.')

    #     game = self.games[channel]
    #     if player not in game.players:
    #         raise DiscordBotException(
    #             'Error: {} has not joined.'.format(player))

    #     # send message asking for confirmation in the form
    #     # of emoji reaction to message.
    #     # if self._game_started:
    #     #     raise DiscordBotException(
    #     #         'Error: cannot leave game in progress (WIP)'
    #     #     )

    #     game.remove_player(player)

    #     await channel.send('{} has left the game'.format(player))

    # def _find_member(self, channel, search_key: str) -> Player:
    #     for player in self.games[channel].players.values():
    #         if player.matches(search_key):
    #             return player

    #     raise DiscordBotException(
    #         'Error: cannot find any matches for {}'.format(search_key))


def main() -> None:
    with open('discord_token') as f:  # pylint: disable=invalid-name
        token = f.read().strip()

    bot = DiscordBot()
    bot.run(token)


if __name__ == '__main__':
    main()
