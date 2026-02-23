"""Event and exit reason constants for the backtest engine."""

from __future__ import annotations

from enum import StrEnum


class ExitReason(StrEnum):
    """Supported position exit reasons for Task 4."""

    STOP_LOSS = "SL"
    TAKE_PROFIT = "TP"
    OPPOSITE_SIGNAL = "OPPOSITE_SIGNAL"
    END_OF_DATA = "EOD"
