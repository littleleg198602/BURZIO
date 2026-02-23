from __future__ import annotations

import json

import pandas as pd
import pytest

from src.dashboard.backtest_service import BacktestRunInput, validate_run_input
from src.dashboard.loaders import discover_symbol_csvs, load_ndjson_file, load_paper_artifacts


def test_discover_symbol_csvs(tmp_path) -> None:
    (tmp_path / "EURUSD_H1.csv").write_text("x\n", encoding="utf-8")
    (tmp_path / "GBPUSD_H1.csv").write_text("x\n", encoding="utf-8")
    out = discover_symbol_csvs(tmp_path)
    assert out["EURUSD"].endswith("EURUSD_H1.csv")
    assert out["GBPUSD"].endswith("GBPUSD_H1.csv")


def test_load_ndjson_file_skips_bad_lines(tmp_path) -> None:
    p = tmp_path / "events.ndjson"
    p.write_text(
        '{"event_type":"OK","symbol":"EURUSD"}\n'
        'not-json\n'
        '{"event_type":"ENTRY_REJECTED","reason":"max_open_trades_reached"}\n',
        encoding="utf-8",
    )
    df = load_ndjson_file(p)
    assert len(df) == 2
    assert set(df["event_type"].tolist()) == {"OK", "ENTRY_REJECTED"}


def test_load_paper_artifacts_missing_files(tmp_path) -> None:
    payload = load_paper_artifacts(
        state_path=tmp_path / "state.json",
        events_path=tmp_path / "events.ndjson",
        status_path=tmp_path / "status.json",
        positions_path=tmp_path / "positions.json",
        trades_path=tmp_path / "trades.csv",
        equity_path=tmp_path / "equity.csv",
    )
    assert payload["state"] is None
    assert payload["status"] is None
    assert payload["positions"] is None
    assert isinstance(payload["events"], pd.DataFrame) and payload["events"].empty
    assert isinstance(payload["trades"], pd.DataFrame) and payload["trades"].empty
    assert isinstance(payload["equity"], pd.DataFrame) and payload["equity"].empty


def test_validate_backtest_input_rejects_invalid() -> None:
    bad = BacktestRunInput(
        data_dir="data/raw",
        symbols=[],
        strategy_name="ma_crossover",
        strategy_params={"short_window": 5, "long_window": 20},
        initial_capital=100000,
        stop_loss_distance=0.002,
        take_profit_distance=0.004,
        risk_per_trade_pct=0.01,
        max_open_trades=3,
        max_portfolio_risk_pct=0.05,
        max_drawdown_guard_pct=0.2,
        max_risk_per_trade_pct=0.02,
        use_data_spread=True,
        fixed_spread=0.0,
        slippage=0.0,
    )
    with pytest.raises(ValueError):
        validate_run_input(bad)
