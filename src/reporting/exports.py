"""Simple CSV export helpers for backtest artifacts."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_trades_csv(trades_df: pd.DataFrame, path: str | Path) -> None:
    """Export trade log dataframe to CSV."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    trades_df.to_csv(path, index=False)


def export_equity_csv(equity_df: pd.DataFrame, path: str | Path) -> None:
    """Export equity curve dataframe to CSV."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    equity_df.to_csv(path, index=False)
