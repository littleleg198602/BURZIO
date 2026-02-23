"""Breakout strategy implementation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


@dataclass(slots=True)
class BreakoutStrategy(BaseStrategy):
    """Generate Donchian-style breakout signals.

    Signal at time ``t`` uses only bars strictly before ``t`` (shifted rolling window),
    which avoids look-ahead bias.
    """

    lookback: int = 20
    signal_column: str = "signal"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        if self.lookback <= 1:
            raise ValueError("lookback must be > 1")

        required = {"time", "symbol", "high", "low", "close"}
        missing = required - set(data.columns)
        if missing:
            raise ValueError(f"Missing required columns for breakout strategy: {sorted(missing)}")

        work = data[["time", "symbol", "high", "low", "close"]].copy()
        work["time"] = pd.to_datetime(work["time"], errors="coerce")
        work = work.sort_values(["symbol", "time"], kind="mergesort").reset_index(drop=True)

        prev_high = work.groupby("symbol")["high"].transform(
            lambda s: s.rolling(self.lookback, min_periods=self.lookback).max().shift(1)
        )
        prev_low = work.groupby("symbol")["low"].transform(
            lambda s: s.rolling(self.lookback, min_periods=self.lookback).min().shift(1)
        )

        signal = np.where(work["close"] > prev_high, 1.0, np.where(work["close"] < prev_low, -1.0, 0.0))
        signal = pd.Series(signal, index=work.index).where(prev_high.notna() & prev_low.notna(), 0.0)

        out = pd.DataFrame(
            {
                "time": work["time"],
                "symbol": work["symbol"],
                self.signal_column: signal.astype(float),
                "strategy": "breakout",
            }
        )
        return out
