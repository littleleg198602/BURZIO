"""Performance metrics for Task 4 backtest outputs."""

from __future__ import annotations

import pandas as pd

from src.reporting.equity import compute_drawdown_series


def compute_metrics(trades_df: pd.DataFrame, equity_df: pd.DataFrame, initial_capital: float) -> dict[str, float]:
    """Compute basic performance metrics."""
    pnl = trades_df["pnl"] if not trades_df.empty else pd.Series(dtype=float)
    gross_profit = float(pnl[pnl > 0].sum()) if not pnl.empty else 0.0
    gross_loss = float(pnl[pnl < 0].sum()) if not pnl.empty else 0.0
    wins = int((pnl > 0).sum()) if not pnl.empty else 0
    trades = int(len(trades_df))
    profit_factor = float(gross_profit / abs(gross_loss)) if gross_loss < 0 else float("inf") if gross_profit > 0 else 0.0

    if equity_df.empty:
        total_return = 0.0
        max_drawdown = 0.0
    else:
        end_equity = float(equity_df["equity"].iloc[-1])
        total_return = end_equity / float(initial_capital) - 1.0
        max_drawdown = float(compute_drawdown_series(equity_df["equity"]).min())

    return {
        "total_return": float(total_return),
        "number_of_trades": float(trades),
        "win_rate": float(wins / trades) if trades else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "max_drawdown": max_drawdown,
    }
