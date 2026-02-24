from __future__ import annotations

import pandas as pd

from src.strategies import BreakoutStrategy, MACrossoverStrategy, SIGNAL_COLUMNS


def make_single_symbol_df() -> pd.DataFrame:
    times = pd.date_range("2024-01-01 00:00:00", periods=12, freq="1h")
    close = [100, 101, 102, 103, 104, 106, 108, 107, 109, 110, 111, 112]
    high = [c + 0.6 for c in close]
    low = [c - 0.6 for c in close]
    return pd.DataFrame(
        {
            "time": times,
            "symbol": ["EURUSD"] * len(times),
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": [1000] * len(times),
            "spread": [10] * len(times),
        }
    )


def test_strategy_output_schema_consistent() -> None:
    df = make_single_symbol_df()
    ma = MACrossoverStrategy(short_window=3, long_window=5).generate_signals(df)
    bo = BreakoutStrategy(lookback=4).generate_signals(df)

    assert list(ma.columns) == SIGNAL_COLUMNS
    assert list(bo.columns) == SIGNAL_COLUMNS
    assert len(ma) == len(df)
    assert len(bo) == len(df)


def test_breakout_no_lookahead_bias() -> None:
    df = make_single_symbol_df()
    lookback = 4
    bo = BreakoutStrategy(lookback=lookback).generate_signals(df)

    # first actionable index where previous rolling window exists should still be 0
    # unless close[t] exceeds max(high[t-lookback:t]) using only history.
    first_actionable = lookback
    hist_high = df.loc[first_actionable - lookback : first_actionable - 1, "high"].max()
    expected = 1.0 if df.loc[first_actionable, "close"] > hist_high else 0.0
    assert float(bo.loc[first_actionable, "signal"]) == expected

    # Ensure no signal appears before enough history is available.
    assert bo.loc[: lookback - 1, "signal"].eq(0.0).all()
