# pragma pylint: disable=missing-docstring
from typing import Dict, List
import datetime

import discord  # type: ignore

from discord_game import DiscordGame

import seat_commands as commands

from seat_typing import SeatException, SeatChannel

# TODO: police nickname changes


class DiscordBotException(SeatException):
    pass


class DiscordBot(discord.Client):  # type: ignore
    def __init__(self) -> None:
        super().__init__()
        self.games: Dict[SeatChannel, DiscordGame] = {}
        # self.players: Dict[discord.user, DiscordGame] = {}

        self.command_list: List[commands.CommandType] = []
        self.command_dict: Dict[str, List[commands.CommandType]] = {}

        self._initialize_commands()

    def _initialize_commands(self) -> None:
        self.command_list += [
            # General info
            commands.Help(self.command_dict),
            commands.Rules(),
            commands.Commands(self.command_list),
            commands.Source(),

            # Game management
            commands.Create(self.games),
            commands.Recreate(self.games),
            commands.Join(self.games),
            commands.CreateJoin(self.games),
            commands.RecreateJoin(self.games),

            commands.Leave(self.games),
            commands.AddBot(self.games),
            commands.RemoveBot(self.games),

            commands.Ready(self.games),
            commands.Unready(self.games),

            commands.RoundLength(self.games),

            # game info
            commands.PrintProposals(self.games),
            commands.PrintBotSwaps(self.games),
            commands.PrintPlayers(self.games),
            commands.PrintGarnets(self.games),

            commands.PrintSeating(self.games),
            commands.AssignNumber(self.games),
            commands.UnassignNumber(self.games),

            # gameplay
            commands.ProposeSeatSwap(self.games),
            commands.AcceptSeatSwap(self.games),
            commands.CancelSeatSwap(self.games),

            commands.CreateBotSwap(self.games),
            commands.CancelBotSwap(self.games),
            commands.DonateGarnets(self.games),

            # real life game
            commands.CreateRealLifeGame(self.games),
            commands.Reveal(self.games),
            commands.Swap(self.games),
            commands.RealLifeSeating(self.games),

            # admin
            commands.Shutdown(self),
            commands.ForceStart(self.games),
            commands.ForceStop(self.games),
            commands.ForceNewRound(self.games),
            commands.ForceSeatNumbers(self.games),
        ]

        for command in self.command_list:
            for command_name in command.command_name_list:
                if command_name not in self.command_dict:
                    self.command_dict[command_name] = [command]
                else:
                    self.command_dict[command_name].append(command)

    async def on_ready(self) -> None:
        print('Logged in as {0.user} at {1}'.format(
            self, datetime.datetime.now()))
        # for guild in self.guilds:
        #     for channel in guild.channels:
        #         if channel.name == 'testing':
        #             await channel.send('Seat Exchange Bot v0.1')

    async def on_message(self, message: discord.message) -> None:
        if message.author == self.user:
            return

        if not message.content.startswith('!'):
            return

        command = message.content.split(' ')[0][1:]
        channel = SeatChannel(message.channel)
        # parameters = message.content.split(' ')[1:]

        if command in self.command_dict:
            command_message = commands.CommandMessage(message, channel)
            errors = []
            for matching_command in self.command_dict[command]:
                try:
                    await matching_command.execute(command_message)
                    return
                except SeatException as error:
                    errors.append(error)
            print(errors)
            await message.channel.send('\n'.join(str(x) for x in errors))

    async def on_reaction_add(self,
                              reaction: discord.Reaction,
                              user: discord.User) -> None:  # TODO
        print('reaction added')
        message = reaction.message
        channel = SeatChannel(message.channel)

        if channel not in self.games:
            print('no channel')
            return

        game = self.games[channel]

        if message.id not in game.reactable_messages:
            print(message, '\n', game.reactable_messages)
            return

        await game.reactable_messages[message.id].on_react(
            reaction, user)

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

    # async def _command_forcestop(self, _parameters: List[str],
    #                              _player: Player, channel):

    #     if channel not in self.games:
    #         raise DiscordBotException('No game in this channel')

    #     self.games[channel].stop()
    #     await channel.send('Game stopped.')

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


def main() -> None:
    with open('discord_token') as f:  # pylint: disable=invalid-name
        token = f.read().strip()

    bot = DiscordBot()
    bot.run(token)


if __name__ == '__main__':
    main()
