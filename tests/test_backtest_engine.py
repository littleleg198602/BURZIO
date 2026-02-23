from __future__ import annotations

import pandas as pd
import pytest

from src.engine.backtest_engine import BacktestConfig, BacktestEngine
from src.engine.execution_model import ExecutionConfig
from src.reporting.metrics import compute_metrics
from src.strategies import MACrossoverStrategy


def make_data() -> pd.DataFrame:
    t = pd.date_range("2024-01-01 00:00:00", periods=8, freq="1h")
    return pd.DataFrame(
        {
            "time": t,
            "symbol": ["EURUSD"] * len(t),
            "open": [1.1000, 1.1002, 1.1005, 1.1008, 1.1010, 1.1012, 1.1015, 1.1017],
            "high": [1.1003, 1.1008, 1.1010, 1.1012, 1.1015, 1.1018, 1.1020, 1.1022],
            "low": [1.0997, 1.1000, 1.1002, 1.1005, 1.1008, 1.1010, 1.1012, 1.1014],
            "close": [1.1001, 1.1006, 1.1009, 1.1011, 1.1013, 1.1016, 1.1018, 1.1020],
            "spread": [0.0000] * len(t),
            "volume": [1000] * len(t),
        }
    )


def make_signals(vals: list[float]) -> pd.DataFrame:
    t = pd.date_range("2024-01-01 00:00:00", periods=len(vals), freq="1h")
    return pd.DataFrame({"time": t, "symbol": ["EURUSD"] * len(vals), "signal": vals, "strategy": ["test"] * len(vals)})


def test_validation_empty_data() -> None:
    engine = BacktestEngine()
    empty = pd.DataFrame(columns=["time", "symbol", "open", "high", "low", "close"])
    sig = make_signals([0, 0])
    with pytest.raises(ValueError, match="cannot be empty"):
        engine.run(empty, sig)


def test_validation_multi_symbol_fails() -> None:
    data = make_data()
    data.loc[0, "symbol"] = "GBPUSD"
    with pytest.raises(ValueError, match="single symbol"):
        BacktestEngine().run(data, make_signals([0] * len(data)))


def test_no_signal_no_trades_equity_unchanged() -> None:
    data = make_data()
    cfg = BacktestConfig(initial_capital=10000, fixed_quantity=10000)
    res = BacktestEngine(cfg).run(data, make_signals([0] * len(data)))
    assert res.trades.empty
    assert float(res.equity_curve["equity"].iloc[-1]) == 10000


def test_enter_long_next_bar_open_not_same_bar() -> None:
    data = make_data()
    signals = make_signals([1, 0, 0, 0, 0, 0, 0, 0])
    cfg = BacktestConfig(stop_loss_distance=1.0, take_profit_distance=1.0, fixed_quantity=1, initial_capital=100)
    res = BacktestEngine(cfg).run(data, signals)
    tr = res.trades.iloc[0]
    assert str(tr["entry_time"]) == str(data.loc[1, "time"])


def test_short_trade_pnl_sign() -> None:
    data = make_data()
    # force lower closes after entry
    data.loc[2:, ["open", "high", "low", "close"]] = [1.1000, 1.1001, 1.0990, 1.0992]
    signals = make_signals([-1, 0, 0, 0, 0, 0, 0, 0])
    cfg = BacktestConfig(stop_loss_distance=1.0, take_profit_distance=1.0, fixed_quantity=10000, initial_capital=10000)
    res = BacktestEngine(cfg).run(data, signals)
    assert float(res.trades.iloc[0]["pnl"]) > 0


def test_sl_tp_conservative_rule_sl_first_when_both_touched() -> None:
    data = make_data()
    # signal at bar0 -> entry at bar1 open=1.1002
    # set bar1 high/low to hit both sl and tp distances of 0.0001
    data.loc[1, "high"] = 1.1004
    data.loc[1, "low"] = 1.1000
    signals = make_signals([1, 0, 0, 0, 0, 0, 0, 0])
    cfg = BacktestConfig(stop_loss_distance=0.0001, take_profit_distance=0.0001, fixed_quantity=10000)
    res = BacktestEngine(cfg).run(data, signals)
    assert res.trades.iloc[0]["exit_reason"] == "SL"


def test_opposite_signal_closes_position_next_open_no_auto_reverse() -> None:
    data = make_data()
    signals = make_signals([1, -1, 0, 0, 0, 0, 0, 0])
    cfg = BacktestConfig(stop_loss_distance=1.0, take_profit_distance=1.0, allow_reversal_on_opposite_signal=False)
    res = BacktestEngine(cfg).run(data, signals)
    assert len(res.trades) == 1
    assert res.trades.iloc[0]["exit_reason"] == "OPPOSITE_SIGNAL"


def test_force_close_eod() -> None:
    data = make_data()
    signals = make_signals([1, 0, 0, 0, 0, 0, 0, 0])
    cfg = BacktestConfig(stop_loss_distance=2.0, take_profit_distance=2.0)
    res = BacktestEngine(cfg).run(data, signals)
    assert res.trades.iloc[-1]["exit_reason"] == "EOD"


def test_strategy_integration_with_task3_ma() -> None:
    data = make_data()
    ma_signals = MACrossoverStrategy(short_window=2, long_window=3).generate_signals(data)
    res = BacktestEngine().run(data, ma_signals, strategy_name="ma_crossover")
    assert "equity" in res.equity_curve.columns
    assert isinstance(res.metrics, dict)


def test_compute_metrics_smoke() -> None:
    trades = pd.DataFrame({"pnl": [10.0, -5.0, 15.0]})
    equity = pd.DataFrame({"equity": [100, 95, 110]})
    out = compute_metrics(trades, equity, 100)
    assert out["number_of_trades"] == 3
    assert out["max_drawdown"] <= 0
