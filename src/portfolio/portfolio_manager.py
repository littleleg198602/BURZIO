"""Multi-asset portfolio backtest orchestration for Task 5."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from src.engine.events import ExitReason
from src.engine.execution_model import ExecutionConfig, apply_entry_price, apply_exit_price
from src.reporting.equity import build_equity_dataframe
from src.reporting.metrics import compute_metrics
from src.strategies.signals import validate_signal_schema

from .position_sizer import PositionSizer, SizingConfig
from .risk_manager import PortfolioRiskConfig, PortfolioRiskManager


@dataclass(slots=True)
class PortfolioBacktestConfig:
    initial_capital: float = 100_000.0
    stop_loss_distance: float = 0.0020
    take_profit_distance: float = 0.0040
    allow_reversal_on_opposite_signal: bool = False
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    sizing: SizingConfig = field(default_factory=SizingConfig)
    risk: PortfolioRiskConfig = field(default_factory=PortfolioRiskConfig)


@dataclass(slots=True)
class PortfolioTradeRecord:
    symbol: str
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    exit_reason: str
    qty: float
    pnl: float
    pnl_pct: float
    bars_held: int
    strategy_name: str
    risk_amount: float


@dataclass(slots=True)
class PortfolioBacktestResult:
    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    metrics: dict[str, float]
    rejected_signals: pd.DataFrame


class PortfolioBacktestManager:
    """Chronological portfolio manager for multiple symbols.

    Preserves Task 4 semantics: signal at close T, entry/close at open T+1.
    """

    def __init__(self, config: PortfolioBacktestConfig | None = None):
        self.config = config or PortfolioBacktestConfig()
        self.sizer = PositionSizer(self.config.sizing)
        self.risk_manager = PortfolioRiskManager(self.config.risk)

    def run(self, data: pd.DataFrame, signals: pd.DataFrame) -> PortfolioBacktestResult:
        self._validate_inputs(data, signals)

        bars = data.copy()
        bars["time"] = pd.to_datetime(bars["time"], errors="coerce")
        bars = bars.sort_values(["time", "symbol"], kind="mergesort").reset_index(drop=True)

        sig = signals.copy()
        sig["time"] = pd.to_datetime(sig["time"], errors="coerce")
        sig = sig.sort_values(["time", "symbol"], kind="mergesort")
        signal_map = sig.drop_duplicates(["time", "symbol"], keep="last").set_index(["time", "symbol"])["signal"].to_dict()
        strategy_map = sig.drop_duplicates(["time", "symbol"], keep="last").set_index(["time", "symbol"])["strategy"].to_dict()

        grouped = {k: g.reset_index(drop=True) for k, g in bars.groupby("symbol")}
        index_by_time_symbol = {
            (pd.Timestamp(row.time), row.symbol): int(row.i)
            for row in bars.reset_index(names="i").itertuples(index=False)
        }

        cash = float(self.config.initial_capital)
        peak_equity = cash
        positions: dict[str, dict[str, float | str | pd.Timestamp | int]] = {}
        trades: list[PortfolioTradeRecord] = []
        rejected: list[dict[str, object]] = []
        eq_times: list[pd.Timestamp] = []
        eq_vals: list[float] = []
        cash_vals: list[float] = []

        for current_time in sorted(bars["time"].unique()):
            t = pd.Timestamp(current_time)

            for symbol, sym_df in grouped.items():
                idx = index_by_time_symbol.get((t, symbol))
                if idx is None:
                    continue
                bar_row = bars.loc[idx]
                open_, high, low, close = map(float, (bar_row["open"], bar_row["high"], bar_row["low"], bar_row["close"]))
                spread = self.config.execution.spread_for_bar(float(bar_row.get("spread", 0.0)))

                prev_idx = sym_df[sym_df["time"] < t].index.max() if not sym_df[sym_df["time"] < t].empty else None
                prev_time = pd.Timestamp(sym_df.loc[prev_idx, "time"]) if prev_idx is not None else None
                prev_signal = float(signal_map.get((prev_time, symbol), 0.0)) if prev_time is not None else 0.0

                closed_by_opposite = False
                pos = positions.get(symbol)
                if pos is not None and self._is_opposite(pos["side"], prev_signal):
                    exit_px = apply_exit_price(open_, str(pos["side"]), spread, self.config.execution.slippage)
                    trade = self._close_position(pos, t, exit_px, ExitReason.OPPOSITE_SIGNAL, int(pos["entry_i"]), idx)
                    cash += trade.pnl
                    trades.append(trade)
                    old_side = str(pos["side"])
                    del positions[symbol]
                    closed_by_opposite = True
                    if self.config.allow_reversal_on_opposite_signal:
                        desired_side = "LONG" if prev_signal > 0 else "SHORT"
                        if self._is_opposite(old_side, prev_signal):
                            opened = self._try_open(symbol, t, idx, open_, spread, prev_signal, strategy_map.get((prev_time, symbol), "unknown"), positions, cash, peak_equity, rejected)
                            if opened:
                                closed_by_opposite = False

                pos = positions.get(symbol)
                if pos is not None:
                    sl_hit, tp_hit = self._check_sltp(pos, high, low)
                    if sl_hit and tp_hit:
                        reason = ExitReason.STOP_LOSS
                        raw_exit = float(pos["stop_price"])
                    elif sl_hit:
                        reason = ExitReason.STOP_LOSS
                        raw_exit = float(pos["stop_price"])
                    elif tp_hit:
                        reason = ExitReason.TAKE_PROFIT
                        raw_exit = float(pos["take_profit_price"])
                    else:
                        reason = None
                        raw_exit = None

                    if reason is not None:
                        exit_px = apply_exit_price(raw_exit, str(pos["side"]), spread, self.config.execution.slippage)
                        trade = self._close_position(pos, t, exit_px, reason, int(pos["entry_i"]), idx)
                        cash += trade.pnl
                        trades.append(trade)
                        del positions[symbol]
                        pos = None

                if symbol not in positions and prev_signal != 0.0 and not closed_by_opposite:
                    self._try_open(symbol, t, idx, open_, spread, prev_signal, strategy_map.get((prev_time, symbol), "unknown"), positions, cash, peak_equity, rejected)

            m2m = sum(self._unrealized(positions[s], float(bars.loc[index_by_time_symbol[(t, s)], "close"])) for s in positions if (t, s) in index_by_time_symbol)
            eq = cash + m2m
            peak_equity = max(peak_equity, eq)
            eq_times.append(t)
            eq_vals.append(float(eq))
            cash_vals.append(float(cash))

        if not bars.empty:
            last_time = pd.Timestamp(bars["time"].max())
            for symbol, pos in list(positions.items()):
                idx = index_by_time_symbol.get((last_time, symbol))
                if idx is None:
                    continue
                row = bars.loc[idx]
                spread = self.config.execution.spread_for_bar(float(row.get("spread", 0.0)))
                exit_px = apply_exit_price(float(row["close"]), str(pos["side"]), spread, self.config.execution.slippage)
                tr = self._close_position(pos, last_time, exit_px, ExitReason.END_OF_DATA, int(pos["entry_i"]), idx)
                cash += tr.pnl
                trades.append(tr)
                del positions[symbol]
            if eq_vals:
                eq_vals[-1] = cash
                cash_vals[-1] = cash

        trades_df = pd.DataFrame([asdict(t) for t in trades])
        equity_df = build_equity_dataframe(eq_times, eq_vals, cash_vals)
        metrics = compute_metrics(trades_df, equity_df, self.config.initial_capital)
        metrics["average_trade_pnl"] = float(trades_df["pnl"].mean()) if not trades_df.empty else 0.0
        metrics["rejected_entries_count"] = float(len(rejected))
        rejected_df = pd.DataFrame(rejected)

        return PortfolioBacktestResult(trades=trades_df, equity_curve=equity_df, metrics=metrics, rejected_signals=rejected_df)

    def _try_open(
        self,
        symbol: str,
        time: pd.Timestamp,
        idx: int,
        raw_open: float,
        spread: float,
        signal: float,
        strategy_name: str,
        positions: dict[str, dict[str, float | str | pd.Timestamp | int]],
        cash: float,
        peak_equity: float,
        rejected: list[dict[str, object]],
    ) -> bool:
        side = "LONG" if signal > 0 else "SHORT"
        risk_amount = self.sizer.calculate_risk_amount(cash if cash > 0 else 1.0, self.config.sizing.risk_per_trade_pct)
        can_open, reason = self.risk_manager.can_open_trade(
            open_positions=positions,
            requested_risk_amount=risk_amount,
            current_equity=cash,
            peak_equity=peak_equity,
        )
        if not can_open:
            rejected.append({"time": time, "symbol": symbol, "signal": signal, "reason": reason})
            return False

        qty = self.sizer.calculate_units_from_stop_distance(cash, self.config.stop_loss_distance)
        entry_px = apply_entry_price(raw_open, side, spread, self.config.execution.slippage)
        stop = entry_px - self.config.stop_loss_distance if side == "LONG" else entry_px + self.config.stop_loss_distance
        tp = entry_px + self.config.take_profit_distance if side == "LONG" else entry_px - self.config.take_profit_distance

        positions[symbol] = {
            "symbol": symbol,
            "side": side,
            "entry_time": time,
            "entry_price": float(entry_px),
            "qty": float(qty),
            "stop_price": float(stop),
            "take_profit_price": float(tp),
            "entry_i": int(idx),
            "strategy_name": strategy_name,
            "risk_amount": float(risk_amount),
        }
        return True

    @staticmethod
    def _close_position(pos: dict[str, float | str | pd.Timestamp | int], exit_time: pd.Timestamp, exit_price: float, reason: ExitReason, entry_i: int, exit_i: int) -> PortfolioTradeRecord:
        side = str(pos["side"])
        entry_price = float(pos["entry_price"])
        qty = float(pos["qty"])
        pnl = (exit_price - entry_price) * qty if side == "LONG" else (entry_price - exit_price) * qty
        base = entry_price * qty
        pnl_pct = pnl / base if base else 0.0
        return PortfolioTradeRecord(
            symbol=str(pos["symbol"]),
            side=side,
            entry_time=pd.Timestamp(pos["entry_time"]),
            entry_price=entry_price,
            exit_time=exit_time,
            exit_price=float(exit_price),
            exit_reason=str(reason),
            qty=qty,
            pnl=float(pnl),
            pnl_pct=float(pnl_pct),
            bars_held=int(max(exit_i - entry_i, 0)),
            strategy_name=str(pos["strategy_name"]),
            risk_amount=float(pos.get("risk_amount", 0.0)),
        )

    @staticmethod
    def _unrealized(pos: dict[str, float | str | pd.Timestamp | int], close: float) -> float:
        side = str(pos["side"])
        entry = float(pos["entry_price"])
        qty = float(pos["qty"])
        return (close - entry) * qty if side == "LONG" else (entry - close) * qty

    @staticmethod
    def _is_opposite(side: str, signal: float) -> bool:
        return (side == "LONG" and signal < 0) or (side == "SHORT" and signal > 0)

    @staticmethod
    def _check_sltp(pos: dict[str, float | str | pd.Timestamp | int], high: float, low: float) -> tuple[bool, bool]:
        if str(pos["side"]) == "LONG":
            return low <= float(pos["stop_price"]), high >= float(pos["take_profit_price"])
        return high >= float(pos["stop_price"]), low <= float(pos["take_profit_price"])

    @staticmethod
    def _validate_inputs(data: pd.DataFrame, signals: pd.DataFrame) -> None:
        if data.empty:
            raise ValueError("market data cannot be empty")
        required_data = {"time", "symbol", "open", "high", "low", "close"}
        missing_data = required_data - set(data.columns)
        if missing_data:
            raise ValueError(f"market data missing required columns: {sorted(missing_data)}")

        validate_signal_schema(signals)
        if "signal" not in signals.columns:
            raise ValueError("signals must include 'signal' column")
