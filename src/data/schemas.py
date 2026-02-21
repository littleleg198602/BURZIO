"""Core data schemas used by parser/normalizer modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Candle:
    """Normalized OHLCV candle schema."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
