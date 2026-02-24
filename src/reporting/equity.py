"""Equity curve helper utilities."""

from __future__ import annotations

import pandas as pd


def build_equity_dataframe(times: list[pd.Timestamp], equity: list[float], cash: list[float]) -> pd.DataFrame:
    """Build equity curve dataframe."""
    return pd.DataFrame({"time": pd.to_datetime(times), "equity": equity, "cash_equity": cash})


def compute_drawdown_series(equity_curve: pd.Series) -> pd.Series:
    """Compute drawdown series from equity values."""
    running_max = equity_curve.cummax()
    return equity_curve / running_max - 1.0
