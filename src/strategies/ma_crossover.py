"""Moving-average crossover strategy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .base_strategy import BaseStrategy


@dataclass(slots=True)
class MACrossoverStrategy(BaseStrategy):
    """Generate crossover signals from short/long moving averages.

    Signals are computed with one-bar lag to avoid look-ahead bias.
    """

    short_window: int = 5
    long_window: int = 20
    signal_column: str = "signal"

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        if self.short_window <= 0 or self.long_window <= 0:
            raise ValueError("short_window and long_window must be > 0")
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be smaller than long_window")

        required = {"time", "symbol", "close"}
        missing = required - set(data.columns)
        if missing:
            raise ValueError(f"Missing required columns for MA strategy: {sorted(missing)}")

        work = data[["time", "symbol", "close"]].copy()
        work["time"] = pd.to_datetime(work["time"], errors="coerce")
        work = work.sort_values(["symbol", "time"], kind="mergesort").reset_index(drop=True)

        short_ma = work.groupby("symbol")["close"].transform(
            lambda s: s.rolling(self.short_window, min_periods=self.short_window).mean()
        )
        long_ma = work.groupby("symbol")["close"].transform(
            lambda s: s.rolling(self.long_window, min_periods=self.long_window).mean()
        )

        # shift by one bar to prevent using current close to generate current-bar signal
        short_ma = short_ma.groupby(work["symbol"]).shift(1)
        long_ma = long_ma.groupby(work["symbol"]).shift(1)

        signal = np.where(short_ma > long_ma, 1.0, np.where(short_ma < long_ma, -1.0, 0.0))
        signal = pd.Series(signal, index=work.index).where(short_ma.notna() & long_ma.notna(), 0.0)

        out = pd.DataFrame(
            {
                "time": work["time"],
                "symbol": work["symbol"],
                self.signal_column: signal.astype(float),
                "strategy": "ma_crossover",
            }
        )
        return out
