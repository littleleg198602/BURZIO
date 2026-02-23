from __future__ import annotations

import json

from src.engine.execution_model import ExecutionConfig
from src.paper.paper_runner import PaperRunner, PaperRunnerConfig
from src.portfolio.position_sizer import SizingConfig
from src.portfolio.risk_manager import PortfolioRiskConfig


def _write_mt5_csv(path, rows: list[dict[str, object]]) -> None:
    header = "DateTime,Open,High,Low,Close,TickVolume,Spread\n"
    lines = [header]
    for row in rows:
        lines.append(
            f"{row['DateTime']},{row['Open']},{row['High']},{row['Low']},{row['Close']},{row.get('TickVolume', 100)},{row.get('Spread', 0)}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")


def _base_runner_config(tmp_path, process_historical_on_start: bool = True) -> PaperRunnerConfig:
    return PaperRunnerConfig(
        input_dir=str(tmp_path),
        poll_interval_seconds=0,
        symbols=["EURUSD", "GBPUSD"],
        bar_confirmation_lag=1,
        state_path=str(tmp_path / "state.json"),
        events_log_path=str(tmp_path / "events.ndjson"),
        trades_path=str(tmp_path / "trades.csv"),
        equity_path=str(tmp_path / "equity.csv"),
        positions_path=str(tmp_path / "positions.json"),
        status_path=str(tmp_path / "status.json"),
        process_historical_on_start=process_historical_on_start,
        strategy_name="ma_crossover",
        strategy_params={"short_window": 2, "long_window": 3},
        stop_loss_distance=0.002,
        take_profit_distance=0.004,
        execution=ExecutionConfig(use_data_spread=True, fixed_spread=0.0, slippage=0.0),
        sizing=SizingConfig(risk_per_trade_pct=0.01),
        risk=PortfolioRiskConfig(max_open_trades=2, max_risk_per_trade_pct=0.02, max_portfolio_risk_pct=0.05, max_drawdown_guard_pct=0.5),
    )


def test_run_once_idempotent_and_resume(tmp_path) -> None:
    eur = tmp_path / "EURUSD_H1.csv"
    gbp = tmp_path / "GBPUSD_H1.csv"

    rows = [
        {"DateTime": "2024-01-01 00:00:00", "Open": 1.1000, "High": 1.1010, "Low": 1.0990, "Close": 1.1005},
        {"DateTime": "2024-01-01 01:00:00", "Open": 1.1005, "High": 1.1020, "Low": 1.1000, "Close": 1.1015},
        {"DateTime": "2024-01-01 02:00:00", "Open": 1.1015, "High": 1.1030, "Low": 1.1010, "Close": 1.1025},
        {"DateTime": "2024-01-01 03:00:00", "Open": 1.1025, "High": 1.1040, "Low": 1.1020, "Close": 1.1035},
        {"DateTime": "2024-01-01 04:00:00", "Open": 1.1035, "High": 1.1050, "Low": 1.1030, "Close": 1.1045},
    ]
    _write_mt5_csv(eur, rows)
    _write_mt5_csv(gbp, [{**r, "Open": r["Open"] + 0.1, "High": r["High"] + 0.1, "Low": r["Low"] + 0.1, "Close": r["Close"] + 0.1} for r in rows])

    runner = PaperRunner(_base_runner_config(tmp_path, process_historical_on_start=True))
    summary1 = runner.run_once()
    trades_after_first = len(runner.state.trades)
    assert summary1.processed_bars > 0

    summary2 = runner.run_once()
    assert summary2.processed_bars == 0
    assert len(runner.state.trades) == trades_after_first

    rows.append({"DateTime": "2024-01-01 05:00:00", "Open": 1.1045, "High": 1.1060, "Low": 1.1040, "Close": 1.1055})
    _write_mt5_csv(eur, rows)
    _write_mt5_csv(gbp, [{**r, "Open": r["Open"] + 0.1, "High": r["High"] + 0.1, "Low": r["Low"] + 0.1, "Close": r["Close"] + 0.1} for r in rows])

    runner_restarted = PaperRunner(_base_runner_config(tmp_path, process_historical_on_start=True))
    summary3 = runner_restarted.run_once()
    assert summary3.processed_bars > 0
    assert len(runner_restarted.state.equity_curve) >= len(runner.state.equity_curve)


def test_process_historical_on_start_false_only_sets_watermark(tmp_path) -> None:
    eur = tmp_path / "EURUSD_H1.csv"
    _write_mt5_csv(
        eur,
        [
            {"DateTime": "2024-01-01 00:00:00", "Open": 1.1000, "High": 1.1010, "Low": 1.0990, "Close": 1.1005},
            {"DateTime": "2024-01-01 01:00:00", "Open": 1.1005, "High": 1.1020, "Low": 1.1000, "Close": 1.1015},
            {"DateTime": "2024-01-01 02:00:00", "Open": 1.1015, "High": 1.1030, "Low": 1.1010, "Close": 1.1025},
        ],
    )

    runner = PaperRunner(_base_runner_config(tmp_path, process_historical_on_start=False))
    summary = runner.run_once()
    assert summary.processed_bars == 0
    assert runner.state.last_processed_by_symbol["EURUSD"] == "2024-01-01T01:00:00"


def test_runner_logs_errors_and_continues_other_symbols(tmp_path) -> None:
    eur = tmp_path / "EURUSD_H1.csv"
    bad = tmp_path / "GBPUSD_H1.csv"

    _write_mt5_csv(
        eur,
        [
            {"DateTime": "2024-01-01 00:00:00", "Open": 1.1000, "High": 1.1010, "Low": 1.0990, "Close": 1.1005},
            {"DateTime": "2024-01-01 01:00:00", "Open": 1.1005, "High": 1.1020, "Low": 1.1000, "Close": 1.1015},
            {"DateTime": "2024-01-01 02:00:00", "Open": 1.1015, "High": 1.1030, "Low": 1.1010, "Close": 1.1025},
        ],
    )
    bad.write_text("DateTime,Open\n2024-01-01 00:00:00,1.0\n", encoding="utf-8")

    runner = PaperRunner(_base_runner_config(tmp_path, process_historical_on_start=True))
    summary = runner.run_once()
    assert summary.errors >= 1
    assert summary.processed_bars > 0

    events = [json.loads(line) for line in (tmp_path / "events.ndjson").read_text(encoding="utf-8").splitlines() if line]
    assert any(e.get("event_type") == "ERROR" and e.get("symbol") == "GBPUSD" for e in events)
