# pragma pylint: disable=missing-docstring
from __future__ import annotations
import typing
from typing import List, Any

import random

import seat_game

import strings

from seat_typing import PrivateNumber, Seat, SeatException


class PlayerGameException(SeatException):
    pass


class Player(Findable):
    """A player in a discord game.

    Much of the commands interface directly with the public methods,
    and there's frequent cross-communication with PlayerGame and Proposal."""
    def __init__(self,
                 player_game: PlayerGame,
                 # discord_user: discord.User,
                 seat: Seat = Seat(-1),
                 garnets: int = 0):

        self.game: PlayerGame = player_game
        self._seat: Seat = seat
        self._swapped: bool = False
        self.garnets = garnets

    def new_round(self) -> None:
        pass

    # I'm not sure about these functions. A Player really doesn't need these,
    # and they make no sense in the context of this class, but when
    # discord_game handles BotPlayers and DiscordPlayers we would need to do
    # constant casting to not get mypy to scream at us.

    # Subclasses uses self so can't make it a function
    def matches(self, search_key: str) -> bool:
        raise NotImplementedError('Virtual method matches.')


class PlayerGame:

    def __init__(self,
                 options: typing.Optional[typing.Dict[str, Any]] = None):
        self.options = options if options is not None else {}
        for key in self.default_options:
            if key not in self.options:
                self.options[key] = self.default_options[key]

        # TODO super()
        self._game: seat_game.SeatGame = seat_game.SeatGame(
            options=self.options)

        self._seating_to_player: List[Player] = []
        self.proposals: typing.Set[Proposal] = set()

    # game management

    def add_player(self, player: Player) -> None:
        """Add a Player to the game with a random seat & number"""
        seat = self._game.add_seat()
        player.set_seat(seat)
        # player = Player(seat=seat, user=user, discord_game=self)

        if seat < len(self._seating_to_player):
            self._seating_to_player.append(
                self._seating_to_player[seat])
            self._seating_to_player[seat] = player
        else:
            self._seating_to_player.append(player)

    def remove_player(self, player: Player) -> None:
        self._game.remove_seat(player.seat)

        self._seating_to_player.pop(player.seat)
        for i in self._seating_to_player[player.seat:]:
            i.set_seat(i.seat - 1)

    def accept_proposal(self, proposal: Proposal) -> None:
        proposal.accept()
        self.proposals.remove(proposal)

    def cancel_proposal(self, proposal: Proposal) -> None:
        proposal.cancel()
        self.proposals.remove(proposal)

    def start_game(self) -> None:
        for player in self._seating_to_player:
            player.garnets = self.options['start_garnets']

    def new_round(self) -> bool:
        for player in self._seating_to_player:
            player.new_round()
        for player in self._seating_to_player:
            player.reset_swapped()

        old_proposals = self.proposals.copy()
        for proposal in old_proposals:
            proposal.cancel()
        self.proposals = set()

        if not self._game.game_over:
            self._game.new_round()
            return True

        self._award_win_garnets()

        return False
