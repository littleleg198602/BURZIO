"""Paper trading simulation loop (polling mode, no live execution)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.config.loader import load_app_config
from src.engine.events import ExitReason
from src.engine.execution_model import ExecutionConfig, apply_entry_price, apply_exit_price
from src.portfolio.position_sizer import PositionSizer, SizingConfig
from src.portfolio.risk_manager import PortfolioRiskConfig, PortfolioRiskManager
from src.reporting.exports import export_equity_csv, export_trades_csv
from src.strategies import BreakoutStrategy, MACrossoverStrategy

from .file_watcher import discover_symbol_files, load_new_bars_for_symbol, poll_file_changes
from .state_store import PaperStateStore


@dataclass(slots=True)
class PaperRunnerConfig:
    """Runtime configuration for polling-based paper trading."""

    input_dir: str = "data/raw"
    poll_interval_seconds: int = 10
    symbols: list[str] = field(default_factory=list)
    timeframe: str = "H1"
    bar_confirmation_lag: int = 1
    state_path: str = "data/paper/state.json"
    events_log_path: str = "logs/paper_events.ndjson"
    trades_path: str = "logs/paper_trades.csv"
    equity_path: str = "logs/paper_equity.csv"
    positions_path: str = "logs/current_positions.json"
    status_path: str = "logs/latest_status.json"
    max_loops: int | None = None
    process_historical_on_start: bool = False
    strategy_name: str = "ma_crossover"
    strategy_params: dict[str, Any] = field(default_factory=dict)
    initial_capital: float = 100_000.0
    stop_loss_distance: float = 0.0020
    take_profit_distance: float = 0.0040
    allow_reversal_on_opposite_signal: bool = False
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    sizing: SizingConfig = field(default_factory=SizingConfig)
    risk: PortfolioRiskConfig = field(default_factory=PortfolioRiskConfig)


@dataclass(slots=True)
class PaperRunSummary:
    """Single loop execution summary."""

    processed_bars: int
    accepted_entries: int
    rejected_entries: int
    exits: int
    errors: int


class PaperRunner:
    """Incremental paper runtime with restart-safe state persistence."""

    def __init__(self, config: PaperRunnerConfig):
        self.config = config
        self.state_store = PaperStateStore(config.state_path, config.events_log_path)
        self.state = self.state_store.load_state(initial_capital=config.initial_capital)
        self.last_seen_mtime: dict[str, float] = {}
        self.sizer = PositionSizer(config.sizing)
        self.risk_manager = PortfolioRiskManager(config.risk)
        self.strategy = self._build_strategy(config.strategy_name, config.strategy_params)

    @staticmethod
    def _build_strategy(name: str, params: dict[str, Any]) -> Any:
        key = name.lower()
        if key == "ma_crossover":
            return MACrossoverStrategy(**params)
        if key == "breakout":
            return BreakoutStrategy(**params)
        raise ValueError(f"Unsupported strategy: {name}")

    def run(self, max_loops: int | None = None) -> None:
        """Run polling loop until max_loops is reached (or forever)."""
        loops = 0
        limit = max_loops if max_loops is not None else self.config.max_loops
        while True:
            self.run_once()
            loops += 1
            if limit is not None and loops >= limit:
                break
            time.sleep(self.config.poll_interval_seconds)

    def run_forever(self) -> None:
        """Run polling loop indefinitely."""
        self.run(max_loops=None)

    def run_once(self) -> PaperRunSummary:
        """Run one polling/process cycle."""
        files = discover_symbol_files(self.config.input_dir, self.config.symbols or None)
        changed, self.last_seen_mtime = poll_file_changes(files, self.last_seen_mtime)

        accepted_entries = 0
        rejected_entries = 0
        exits = 0
        processed_bars = 0
        errors = 0

        if not changed:
            self.state_store.append_event({"event_type": "LOOP_STATUS", "message": "no_file_changes"})
            self.state_store.save_state(self.state)
            return PaperRunSummary(0, 0, 0, 0, 0)

        new_bars_by_symbol: dict[str, pd.DataFrame] = {}
        for ch in changed:
            try:
                last_ts = self.state.last_processed_by_symbol.get(ch.symbol)
                bars = load_new_bars_for_symbol(ch.path, ch.symbol, last_ts, self.config.bar_confirmation_lag)
                if bars.empty:
                    continue

                if last_ts is None and not self.config.process_historical_on_start:
                    last_confirmed = pd.Timestamp(bars["time"].iloc[-1])
                    self.state.last_processed_by_symbol[ch.symbol] = last_confirmed.isoformat()
                    self.state.history_by_symbol[ch.symbol] = self._records_for_state(bars)
                    self.state.latest_close_by_symbol[ch.symbol] = float(bars["close"].iloc[-1])
                    self.state_store.append_event(
                        {
                            "event_type": "LOOP_STATUS",
                            "symbol": ch.symbol,
                            "message": "historical_skipped_on_start",
                            "last_processed": last_confirmed.isoformat(),
                        }
                    )
                    continue

                new_bars_by_symbol[ch.symbol] = bars
                self.state_store.append_event(
                    {
                        "event_type": "NEW_BAR_PROCESSED",
                        "symbol": ch.symbol,
                        "rows": int(len(bars)),
                        "from_file": ch.path,
                    }
                )
            except Exception as exc:  # recoverable per symbol
                errors += 1
                self.state_store.append_event({"event_type": "ERROR", "symbol": ch.symbol, "message": str(exc)})

        if not new_bars_by_symbol:
            self.state_store.save_state(self.state)
            return PaperRunSummary(0, 0, 0, 0, errors)

        signal_map: dict[tuple[pd.Timestamp, str], float] = {}
        strategy_map: dict[tuple[pd.Timestamp, str], str] = {}

        for symbol, new_df in new_bars_by_symbol.items():
            hist_records = self.state.history_by_symbol.get(symbol, [])
            hist_df = pd.DataFrame(hist_records) if hist_records else pd.DataFrame(columns=new_df.columns)
            if not hist_df.empty:
                hist_df["time"] = pd.to_datetime(hist_df["time"], errors="coerce")
            full_df = pd.concat([hist_df, new_df], ignore_index=True) if not hist_df.empty else new_df.copy()
            full_df = full_df.sort_values("time", kind="mergesort").drop_duplicates(["time", "symbol"], keep="last")
            self.state.history_by_symbol[symbol] = self._records_for_state(full_df)

            sig_df = self.strategy.generate_signals(full_df)
            for row in sig_df.itertuples(index=False):
                ts = pd.Timestamp(row.time)
                signal_map[(ts, str(row.symbol))] = float(row.signal)
                strategy_map[(ts, str(row.symbol))] = str(row.strategy)

        all_new = pd.concat(list(new_bars_by_symbol.values()), ignore_index=True).sort_values(["time", "symbol"], kind="mergesort")

        for current_time in sorted(all_new["time"].unique()):
            t = pd.Timestamp(current_time)
            slice_df = all_new[all_new["time"] == t]

            for row in slice_df.itertuples(index=False):
                symbol = str(row.symbol)
                open_, high, low, close = float(row.open), float(row.high), float(row.low), float(row.close)
                spread = self.config.execution.spread_for_bar(float(getattr(row, "spread", 0.0)))

                hist_df = pd.DataFrame(self.state.history_by_symbol[symbol])
                hist_df["time"] = pd.to_datetime(hist_df["time"], errors="coerce")
                hist_df = hist_df.sort_values("time", kind="mergesort")
                prev = hist_df[hist_df["time"] < t]
                prev_time = pd.Timestamp(prev.iloc[-1]["time"]) if not prev.empty else None
                prev_signal = float(signal_map.get((prev_time, symbol), 0.0)) if prev_time is not None else 0.0

                pos = self.state.open_positions.get(symbol)
                if pos and self._is_opposite(str(pos["side"]), prev_signal):
                    exit_px = apply_exit_price(open_, str(pos["side"]), spread, self.config.execution.slippage)
                    self._close_position(symbol, t, exit_px, ExitReason.OPPOSITE_SIGNAL)
                    exits += 1
                    self.state_store.append_event(
                        {"event_type": "POSITION_EXITED", "symbol": symbol, "reason": str(ExitReason.OPPOSITE_SIGNAL)}
                    )
                    pos = None

                pos = self.state.open_positions.get(symbol)
                if pos:
                    sl_hit, tp_hit = self._check_sltp(pos, high, low)
                    if sl_hit and tp_hit:
                        reason, raw_exit = ExitReason.STOP_LOSS, float(pos["stop_price"])
                    elif sl_hit:
                        reason, raw_exit = ExitReason.STOP_LOSS, float(pos["stop_price"])
                    elif tp_hit:
                        reason, raw_exit = ExitReason.TAKE_PROFIT, float(pos["take_profit_price"])
                    else:
                        reason, raw_exit = None, None

                    if reason is not None:
                        exit_px = apply_exit_price(float(raw_exit), str(pos["side"]), spread, self.config.execution.slippage)
                        self._close_position(symbol, t, exit_px, reason)
                        exits += 1
                        self.state_store.append_event({"event_type": "POSITION_EXITED", "symbol": symbol, "reason": str(reason)})

                if symbol not in self.state.open_positions and prev_signal != 0.0:
                    side = "LONG" if prev_signal > 0 else "SHORT"
                    current_equity = self._current_equity()
                    safe_equity = max(current_equity, 1.0)
                    risk_amount = self.sizer.calculate_risk_amount(safe_equity, self.config.sizing.risk_per_trade_pct)
                    ok, reason = self.risk_manager.can_open_trade(
                        open_positions=self.state.open_positions,
                        requested_risk_amount=risk_amount,
                        current_equity=current_equity,
                        peak_equity=self.state.peak_equity,
                    )
                    if not ok:
                        rejected_entries += 1
                        rej = {"time": t.isoformat(), "symbol": symbol, "signal": prev_signal, "reason": reason}
                        self.state.rejected_entries.append(rej)
                        self.state_store.append_event({"event_type": "ENTRY_REJECTED", **rej})
                    else:
                        qty = self.sizer.calculate_units_from_stop_distance(
                            equity=safe_equity,
                            stop_distance=self.config.stop_loss_distance,
                            risk_pct=self.config.sizing.risk_per_trade_pct,
                        )
                        entry_px = apply_entry_price(open_, side, spread, self.config.execution.slippage)
                        stop = entry_px - self.config.stop_loss_distance if side == "LONG" else entry_px + self.config.stop_loss_distance
                        tp = entry_px + self.config.take_profit_distance if side == "LONG" else entry_px - self.config.take_profit_distance
                        self.state.open_positions[symbol] = {
                            "symbol": symbol,
                            "side": side,
                            "entry_time": t.isoformat(),
                            "entry_price": float(entry_px),
                            "qty": float(qty),
                            "stop_price": float(stop),
                            "take_profit_price": float(tp),
                            "strategy_name": strategy_map.get((prev_time, symbol), self.config.strategy_name),
                            "risk_amount": float(risk_amount),
                        }
                        accepted_entries += 1
                        self.state_store.append_event(
                            {"event_type": "ENTRY_ACCEPTED", "symbol": symbol, "side": side, "time": t.isoformat()}
                        )

                self.state.latest_close_by_symbol[symbol] = close
                self.state.last_processed_by_symbol[symbol] = t.isoformat()
                processed_bars += 1
                self.state_store.append_event(
                    {
                        "event_type": "SIGNAL_GENERATED",
                        "symbol": symbol,
                        "time": t.isoformat(),
                        "signal_used": prev_signal,
                    }
                )

            equity = self._current_equity()
            self.state.peak_equity = max(float(self.state.peak_equity), equity)
            self.state.equity_curve.append({"time": t.isoformat(), "equity": equity, "cash_equity": float(self.state.cash)})
            self.state_store.append_event(
                {"event_type": "LOOP_STATUS", "time": t.isoformat(), "equity": equity, "open_positions": len(self.state.open_positions)}
            )

        self._persist_artifacts()
        self.state_store.save_state(self.state)
        self.state_store.append_event({"event_type": "STATE_SAVED"})

        return PaperRunSummary(processed_bars, accepted_entries, rejected_entries, exits, errors)

    @staticmethod
    def _records_for_state(df: pd.DataFrame) -> list[dict[str, Any]]:
        work = df.copy()
        work["time"] = pd.to_datetime(work["time"], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S")
        return work.to_dict(orient="records")

    def _current_equity(self) -> float:
        m2m = 0.0
        for symbol, pos in self.state.open_positions.items():
            last_close = self.state.latest_close_by_symbol.get(symbol)
            if last_close is None:
                continue
            entry = float(pos["entry_price"])
            qty = float(pos["qty"])
            if str(pos["side"]) == "LONG":
                m2m += (float(last_close) - entry) * qty
            else:
                m2m += (entry - float(last_close)) * qty
        return float(self.state.cash + m2m)

    def _close_position(self, symbol: str, exit_time: pd.Timestamp, exit_price: float, reason: ExitReason) -> None:
        pos = self.state.open_positions[symbol]
        side = str(pos["side"])
        entry = float(pos["entry_price"])
        qty = float(pos["qty"])
        pnl = (exit_price - entry) * qty if side == "LONG" else (entry - exit_price) * qty
        base = entry * qty
        trade = {
            "symbol": symbol,
            "side": side,
            "entry_time": pos["entry_time"],
            "entry_price": entry,
            "exit_time": exit_time.isoformat(),
            "exit_price": float(exit_price),
            "exit_reason": str(reason),
            "qty": qty,
            "pnl": float(pnl),
            "pnl_pct": float(pnl / base) if base else 0.0,
            "strategy_name": str(pos.get("strategy_name", self.config.strategy_name)),
            "risk_amount": float(pos.get("risk_amount", 0.0)),
        }
        self.state.cash = float(self.state.cash + pnl)
        self.state.trades.append(trade)
        del self.state.open_positions[symbol]

    @staticmethod
    def _is_opposite(side: str, signal: float) -> bool:
        return (side == "LONG" and signal < 0) or (side == "SHORT" and signal > 0)

    @staticmethod
    def _check_sltp(pos: dict[str, Any], high: float, low: float) -> tuple[bool, bool]:
        if str(pos["side"]) == "LONG":
            return low <= float(pos["stop_price"]), high >= float(pos["take_profit_price"])
        return high >= float(pos["stop_price"]), low <= float(pos["take_profit_price"])

    def _persist_artifacts(self) -> None:
        trades_df = pd.DataFrame(self.state.trades)
        equity_df = pd.DataFrame(self.state.equity_curve)
        export_trades_csv(trades_df, self.config.trades_path)
        export_equity_csv(equity_df, self.config.equity_path)

        Path(self.config.positions_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.config.positions_path).write_text(json.dumps(self.state.open_positions, indent=2), encoding="utf-8")

        status = {
            "cash": self.state.cash,
            "peak_equity": self.state.peak_equity,
            "open_positions": len(self.state.open_positions),
            "trades": len(self.state.trades),
            "rejected_entries": len(self.state.rejected_entries),
        }
        Path(self.config.status_path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.config.status_path).write_text(json.dumps(status, indent=2), encoding="utf-8")


def build_runner_config(config_path: str = "configs/app_config.example.yaml") -> PaperRunnerConfig:
    """Build paper runner config from app YAML."""
    cfg = load_app_config(config_path)
    p = cfg.get("paper", {})
    s = cfg.get("strategy_runtime", {})

    execution = ExecutionConfig(
        slippage=float(p.get("slippage", 0.0)),
        use_data_spread=bool(p.get("use_data_spread", True)),
        fixed_spread=float(p.get("fixed_spread", 0.0)),
    )

    return PaperRunnerConfig(
        input_dir=str(p.get("input_dir", "data/raw")),
        poll_interval_seconds=int(p.get("poll_interval_seconds", 10)),
        symbols=list(p.get("symbols", [])),
        timeframe=str(p.get("timeframe", "H1")),
        bar_confirmation_lag=int(p.get("bar_confirmation_lag", 1)),
        state_path=str(p.get("state_path", "data/paper/state.json")),
        events_log_path=str(p.get("events_log_path", "logs/paper_events.ndjson")),
        trades_path=str(p.get("trades_path", "logs/paper_trades.csv")),
        equity_path=str(p.get("equity_path", "logs/paper_equity.csv")),
        positions_path=str(p.get("positions_path", "logs/current_positions.json")),
        status_path=str(p.get("status_path", "logs/latest_status.json")),
        max_loops=p.get("max_loops"),
        process_historical_on_start=bool(p.get("process_historical_on_start", False)),
        strategy_name=str(s.get("strategy_name", "ma_crossover")),
        strategy_params=dict(s.get("params", {})),
        initial_capital=float(p.get("initial_capital", 100_000)),
        stop_loss_distance=float(p.get("stop_loss_distance", 0.0020)),
        take_profit_distance=float(p.get("take_profit_distance", 0.0040)),
        allow_reversal_on_opposite_signal=bool(p.get("allow_reversal_on_opposite_signal", False)),
        execution=execution,
        sizing=SizingConfig(
            risk_per_trade_pct=float(p.get("risk_per_trade_pct", 0.01)),
            min_units=float(p.get("min_units", 0.0)),
            max_units=float(p["max_units"]) if p.get("max_units") is not None else None,
            fallback_fixed_units=float(p.get("fallback_fixed_units", 10_000.0)),
        ),
        risk=PortfolioRiskConfig(
            max_open_trades=int(p.get("max_open_trades", 3)),
            max_risk_per_trade_pct=float(p.get("max_risk_per_trade_pct", 0.02)),
            max_portfolio_risk_pct=float(p.get("max_portfolio_risk_pct", 0.05)),
            max_drawdown_guard_pct=float(p.get("max_drawdown_guard_pct", 0.2)),
        ),
    )


if __name__ == "__main__":
    runner_cfg = build_runner_config("configs/app_config.example.yaml")
    PaperRunner(runner_cfg).run(max_loops=runner_cfg.max_loops)
