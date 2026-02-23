from __future__ import annotations

import pandas as pd
import pytest

from src.portfolio import (
    PortfolioBacktestConfig,
    PortfolioBacktestManager,
    PortfolioRiskConfig,
    PortfolioRiskManager,
    PositionSizer,
    SizingConfig,
)
from src.strategies import MACrossoverStrategy


def make_multi_data() -> pd.DataFrame:
    t1 = pd.date_range("2024-01-01 00:00:00", periods=10, freq="1h")
    t2 = pd.date_range("2024-01-01 01:00:00", periods=9, freq="1h")  # sparse shift

    eur = pd.DataFrame(
        {
            "time": t1,
            "symbol": ["EURUSD"] * len(t1),
            "open": [1.1000 + i * 0.0002 for i in range(len(t1))],
            "high": [1.1002 + i * 0.0002 for i in range(len(t1))],
            "low": [1.0998 + i * 0.0002 for i in range(len(t1))],
            "close": [1.1001 + i * 0.0002 for i in range(len(t1))],
            "spread": [0.0] * len(t1),
            "volume": [1000] * len(t1),
            "source_file": ["eur.csv"] * len(t1),
            "row_id": list(range(len(t1))),
        }
    )

    gbp = pd.DataFrame(
        {
            "time": t2,
            "symbol": ["GBPUSD"] * len(t2),
            "open": [1.2700 + i * 0.0001 for i in range(len(t2))],
            "high": [1.2702 + i * 0.0001 for i in range(len(t2))],
            "low": [1.2698 + i * 0.0001 for i in range(len(t2))],
            "close": [1.2701 + i * 0.0001 for i in range(len(t2))],
            "spread": [0.0] * len(t2),
            "volume": [1000] * len(t2),
            "source_file": ["gbp.csv"] * len(t2),
            "row_id": list(range(len(t2))),
        }
    )

    return pd.concat([eur, gbp], ignore_index=True).sort_values(["time", "symbol"]).reset_index(drop=True)


def make_signals(times: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    for t in times:
        rows.append({"time": t, "symbol": "EURUSD", "signal": 1.0 if t.hour in (0, 1, 2) else 0.0, "strategy": "test"})
        rows.append({"time": t, "symbol": "GBPUSD", "signal": 1.0 if t.hour in (1, 2, 3) else 0.0, "strategy": "test"})
    return pd.DataFrame(rows)


def test_position_sizer_units_and_invalid_stop() -> None:
    s = PositionSizer(SizingConfig(risk_per_trade_pct=0.01))
    u = s.calculate_units_from_stop_distance(equity=100_000, stop_distance=0.002)
    assert u == pytest.approx(500_000)
    with pytest.raises(ValueError):
        s.calculate_units_from_stop_distance(equity=100_000, stop_distance=0)


def test_risk_manager_limits() -> None:
    rm = PortfolioRiskManager(PortfolioRiskConfig(max_open_trades=1, max_risk_per_trade_pct=0.02, max_portfolio_risk_pct=0.03, max_drawdown_guard_pct=0.1))
    open_positions = {"EURUSD": {"risk_amount": 1000.0}}
    ok, reason = rm.can_open_trade(open_positions=open_positions, requested_risk_amount=500.0, current_equity=100_000, peak_equity=100_000)
    assert not ok and reason == "max_open_trades_reached"


def test_drawdown_guard_blocks_entries() -> None:
    rm = PortfolioRiskManager(PortfolioRiskConfig(max_drawdown_guard_pct=0.05))
    ok, reason = rm.can_open_trade(open_positions={}, requested_risk_amount=100.0, current_equity=90_000, peak_equity=100_000)
    assert not ok and reason == "drawdown_guard_active"


def test_portfolio_manager_multi_asset_and_rejections() -> None:
    data = make_multi_data()
    times = pd.DatetimeIndex(sorted(data["time"].unique()))
    signals = make_signals(times)

    cfg = PortfolioBacktestConfig()
    cfg.risk.max_open_trades = 1  # force some rejections
    cfg.stop_loss_distance = 0.0003
    cfg.take_profit_distance = 0.0006
    mgr = PortfolioBacktestManager(cfg)
    res = mgr.run(data, signals)

    assert "equity" in res.equity_curve.columns
    assert "rejected_entries_count" in res.metrics
    assert float(res.metrics["rejected_entries_count"]) >= 1
    assert isinstance(res.trades, pd.DataFrame)


def test_one_position_per_symbol_enforced() -> None:
    data = make_multi_data()
    times = pd.DatetimeIndex(sorted(data["time"].unique()))
    signals = pd.DataFrame(
        [{"time": t, "symbol": "EURUSD", "signal": 1.0, "strategy": "test"} for t in times]
    )
    mgr = PortfolioBacktestManager(PortfolioBacktestConfig())
    res = mgr.run(data, signals)
    # no overlapping same-symbol entries at identical entry times
    if not res.trades.empty:
        assert not res.trades.duplicated(["symbol", "entry_time"]).any()


def test_sparse_symbol_timestamps_no_crash() -> None:
    data = make_multi_data()
    times = pd.DatetimeIndex(sorted(data["time"].unique()))
    signals = make_signals(times)
    res = PortfolioBacktestManager(PortfolioBacktestConfig()).run(data, signals)
    assert not res.equity_curve.empty


def test_integration_with_task3_strategy_two_symbols() -> None:
    data = make_multi_data()
    ma = MACrossoverStrategy(short_window=2, long_window=3)

    s1 = ma.generate_signals(data[data["symbol"] == "EURUSD"]).copy()
    s2 = ma.generate_signals(data[data["symbol"] == "GBPUSD"]).copy()
    signals = pd.concat([s1, s2], ignore_index=True)

    result = PortfolioBacktestManager(PortfolioBacktestConfig()).run(data, signals)
    assert isinstance(result.metrics, dict)
    assert "total_return" in result.metrics
    assert isinstance(result.rejected_signals, pd.DataFrame)
