"""Defines data types used for typing in the rest of the project."""
from __future__ import annotations
from typing import NewType, cast
# Seat = NewType("Seat", int)
PrivateNumber = NewType("PrivateNumber", int)


class SeatException(Exception):
    pass


class Seat(int):
    def __str__(self) -> str:
        return chr(ord('A') + int(self))

    def __add__(self, other: int) -> Seat:
        return cast(Seat, super().__add__(other))

    def __sub__(self, other: int) -> Seat:
        return cast(Seat, super().__sub__(other))

    def __mod__(self, other: int) -> Seat:
        return cast(Seat, super().__mod__(other))
