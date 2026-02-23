"""Backtest orchestration helpers for Streamlit dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.normalizer import load_multiple_mt5_csvs
from src.engine.execution_model import ExecutionConfig
from src.portfolio import PortfolioBacktestConfig, PortfolioBacktestManager, PortfolioRiskConfig, SizingConfig
from src.strategies import BreakoutStrategy, MACrossoverStrategy
from src.strategies.signals import combine_signals

from .loaders import discover_symbol_csvs


@dataclass(slots=True)
class BacktestRunInput:
    """Inputs for running a dashboard-triggered backtest."""

    data_dir: str
    symbols: list[str]
    strategy_name: str
    strategy_params: dict[str, Any]
    initial_capital: float
    stop_loss_distance: float
    take_profit_distance: float
    risk_per_trade_pct: float
    max_open_trades: int
    max_portfolio_risk_pct: float
    max_drawdown_guard_pct: float
    max_risk_per_trade_pct: float
    use_data_spread: bool
    fixed_spread: float
    slippage: float


def validate_run_input(run_input: BacktestRunInput) -> None:
    """Validate dashboard backtest inputs."""
    if not run_input.symbols:
        raise ValueError("At least one symbol must be selected.")
    if run_input.initial_capital <= 0:
        raise ValueError("Initial capital must be > 0.")
    if run_input.stop_loss_distance <= 0 or run_input.take_profit_distance <= 0:
        raise ValueError("SL/TP distances must be > 0.")
    if run_input.max_open_trades <= 0:
        raise ValueError("max_open_trades must be > 0.")
    for name, value in [
        ("risk_per_trade_pct", run_input.risk_per_trade_pct),
        ("max_portfolio_risk_pct", run_input.max_portfolio_risk_pct),
        ("max_drawdown_guard_pct", run_input.max_drawdown_guard_pct),
        ("max_risk_per_trade_pct", run_input.max_risk_per_trade_pct),
    ]:
        if value <= 0:
            raise ValueError(f"{name} must be > 0.")


def build_strategy(name: str, params: dict[str, Any]) -> Any:
    """Construct strategy instance from UI selection."""
    key = name.lower().strip()
    if key == "ma_crossover":
        return MACrossoverStrategy(**params)
    if key == "breakout":
        return BreakoutStrategy(**params)
    raise ValueError(f"Unsupported strategy: {name}")


def load_market_data(data_dir: str | Path, symbols: list[str]) -> pd.DataFrame:
    """Load and normalize selected symbol CSVs from directory."""
    files = discover_symbol_csvs(data_dir)
    selected_paths = [files[s.upper()] for s in symbols if s.upper() in files]
    if not selected_paths:
        raise ValueError("No CSV files found for selected symbols in data directory.")
    return load_multiple_mt5_csvs(selected_paths)


def generate_signals(strategy: Any, market_data: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """Generate and combine per-symbol signals using Task 3 schema."""
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        symbol_data = market_data[market_data["symbol"] == symbol.upper()].copy()
        if symbol_data.empty:
            continue
        frames.append(strategy.generate_signals(symbol_data))

    if not frames:
        return pd.DataFrame(columns=["time", "symbol", "signal", "strategy"])
    return combine_signals(frames)


def run_backtest(run_input: BacktestRunInput) -> dict[str, object]:
    """Run portfolio backtest and return result payload for dashboard."""
    validate_run_input(run_input)

    market_data = load_market_data(run_input.data_dir, run_input.symbols)
    strategy = build_strategy(run_input.strategy_name, run_input.strategy_params)
    signals = generate_signals(strategy, market_data, run_input.symbols)

    cfg = PortfolioBacktestConfig(
        initial_capital=run_input.initial_capital,
        stop_loss_distance=run_input.stop_loss_distance,
        take_profit_distance=run_input.take_profit_distance,
        execution=ExecutionConfig(
            slippage=run_input.slippage,
            use_data_spread=run_input.use_data_spread,
            fixed_spread=run_input.fixed_spread,
        ),
        sizing=SizingConfig(risk_per_trade_pct=run_input.risk_per_trade_pct),
        risk=PortfolioRiskConfig(
            max_open_trades=run_input.max_open_trades,
            max_risk_per_trade_pct=run_input.max_risk_per_trade_pct,
            max_portfolio_risk_pct=run_input.max_portfolio_risk_pct,
            max_drawdown_guard_pct=run_input.max_drawdown_guard_pct,
        ),
    )

    result = PortfolioBacktestManager(cfg).run(market_data, signals)
    return {
        "market_data": market_data,
        "signals": signals,
        "result": result,
    }
