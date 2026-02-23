"""Single-symbol backtest engine for Task 4."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from src.engine.events import ExitReason
from src.engine.execution_model import ExecutionConfig, apply_entry_price, apply_exit_price
from src.reporting.equity import build_equity_dataframe
from src.reporting.metrics import compute_metrics


@dataclass(slots=True)
class BacktestConfig:
    """Config for single-symbol backtest simulation."""

    initial_capital: float = 10_000.0
    fixed_quantity: float = 10_000.0
    stop_loss_distance: float = 0.0020
    take_profit_distance: float = 0.0040
    allow_reversal_on_opposite_signal: bool = False
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)


@dataclass(slots=True)
class Position:
    symbol: str
    side: str  # LONG / SHORT
    entry_time: pd.Timestamp
    entry_price: float
    qty: float
    stop_price: float
    take_profit_price: float
    entry_index: int
    strategy_name: str


@dataclass(slots=True)
class TradeRecord:
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


@dataclass(slots=True)
class BacktestResult:
    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    metrics: dict[str, float]


class BacktestEngine:
    """Deterministic single-symbol engine.

    Assumptions:
    - Signals at bar close T
    - Entry/close decision fills on next bar open T+1
    - If both SL and TP touched intrabar, conservative rule: SL first
    """

    def __init__(self, config: BacktestConfig | None = None):
        self.config = config or BacktestConfig()

    def run(self, data: pd.DataFrame, signals: pd.DataFrame, strategy_name: str | None = None) -> BacktestResult:
        self._validate_inputs(data, signals)

        bars = data.copy()
        bars["time"] = pd.to_datetime(bars["time"], errors="coerce")
        bars = bars.sort_values("time", kind="mergesort").reset_index(drop=True)
        symbol = str(bars["symbol"].iloc[0])

        sig = signals.copy()
        sig["time"] = pd.to_datetime(sig["time"], errors="coerce")
        sig = sig[sig["symbol"] == symbol].sort_values("time", kind="mergesort")
        signal_map = sig.drop_duplicates("time", keep="last").set_index("time")["signal"].to_dict()

        cash = float(self.config.initial_capital)
        pos: Position | None = None
        trades: list[TradeRecord] = []
        eq_times: list[pd.Timestamp] = []
        eq_values: list[float] = []
        cash_values: list[float] = []

        for i, bar in bars.iterrows():
            t = pd.Timestamp(bar["time"])
            open_, high, low, close = map(float, (bar["open"], bar["high"], bar["low"], bar["close"]))
            bar_spread = self.config.execution.spread_for_bar(float(bar.get("spread", 0.0)))
            prev_signal = float(signal_map.get(pd.Timestamp(bars.loc[i - 1, "time"]), 0.0)) if i > 0 else 0.0

            closed_by_opposite = False
            if i > 0 and pos is not None and self._is_opposite_signal(pos.side, prev_signal):
                exit_px = apply_exit_price(open_, pos.side, bar_spread, self.config.execution.slippage)
                trade = self._close_position(pos, t, exit_px, ExitReason.OPPOSITE_SIGNAL, i)
                cash += trade.pnl
                trades.append(trade)
                old_side = pos.side
                pos = None
                closed_by_opposite = True
                if self.config.allow_reversal_on_opposite_signal:
                    new_side = "LONG" if prev_signal > 0 else "SHORT"
                    if self._is_opposite_signal(old_side, prev_signal):
                        pos = self._open_position(symbol, new_side, t, open_, bar_spread, i, strategy_name or "unknown")
                        closed_by_opposite = False

            if i > 0 and pos is None and prev_signal != 0.0 and not closed_by_opposite:
                side = "LONG" if prev_signal > 0 else "SHORT"
                pos = self._open_position(symbol, side, t, open_, bar_spread, i, strategy_name or self._strategy_name(sig))

            if pos is not None:
                sl_hit, tp_hit = self._check_sltp_hit(pos, high, low)
                if sl_hit and tp_hit:
                    reason = ExitReason.STOP_LOSS  # deterministic conservative rule
                    raw_exit = pos.stop_price
                elif sl_hit:
                    reason = ExitReason.STOP_LOSS
                    raw_exit = pos.stop_price
                elif tp_hit:
                    reason = ExitReason.TAKE_PROFIT
                    raw_exit = pos.take_profit_price
                else:
                    reason = None
                    raw_exit = None

                if reason is not None and raw_exit is not None:
                    exit_px = apply_exit_price(raw_exit, pos.side, bar_spread, self.config.execution.slippage)
                    trade = self._close_position(pos, t, exit_px, reason, i)
                    cash += trade.pnl
                    trades.append(trade)
                    pos = None

            equity = cash + (self._unrealized_pnl(pos, close) if pos is not None else 0.0)
            eq_times.append(t)
            eq_values.append(float(equity))
            cash_values.append(float(cash))

        if pos is not None:
            last = bars.iloc[-1]
            bar_spread = self.config.execution.spread_for_bar(float(last.get("spread", 0.0)))
            exit_px = apply_exit_price(float(last["close"]), pos.side, bar_spread, self.config.execution.slippage)
            trade = self._close_position(pos, pd.Timestamp(last["time"]), exit_px, ExitReason.END_OF_DATA, len(bars) - 1)
            cash += trade.pnl
            trades.append(trade)
            eq_values[-1] = cash
            cash_values[-1] = cash

        trades_df = pd.DataFrame([asdict(t) for t in trades])
        equity_df = build_equity_dataframe(eq_times, eq_values, cash_values)
        metrics = compute_metrics(trades_df, equity_df, self.config.initial_capital)
        return BacktestResult(trades=trades_df, equity_curve=equity_df, metrics=metrics)

    @staticmethod
    def _strategy_name(signals: pd.DataFrame) -> str:
        if signals.empty or "strategy" not in signals.columns:
            return "unknown"
        return str(signals["strategy"].iloc[-1])

    def _open_position(self, symbol: str, side: str, time: pd.Timestamp, raw_open: float, spread: float, idx: int, strategy_name: str) -> Position:
        px = apply_entry_price(raw_open, side, spread, self.config.execution.slippage)
        sl = px - self.config.stop_loss_distance if side == "LONG" else px + self.config.stop_loss_distance
        tp = px + self.config.take_profit_distance if side == "LONG" else px - self.config.take_profit_distance
        return Position(symbol, side, time, px, self.config.fixed_quantity, sl, tp, idx, strategy_name)

    @staticmethod
    def _is_opposite_signal(side: str, signal: float) -> bool:
        return (side == "LONG" and signal < 0) or (side == "SHORT" and signal > 0)

    @staticmethod
    def _check_sltp_hit(pos: Position, high: float, low: float) -> tuple[bool, bool]:
        if pos.side == "LONG":
            return low <= pos.stop_price, high >= pos.take_profit_price
        return high >= pos.stop_price, low <= pos.take_profit_price

    @staticmethod
    def _unrealized_pnl(pos: Position, close_price: float) -> float:
        return (close_price - pos.entry_price) * pos.qty if pos.side == "LONG" else (pos.entry_price - close_price) * pos.qty

    @staticmethod
    def _close_position(pos: Position, exit_time: pd.Timestamp, exit_price: float, reason: ExitReason, exit_index: int) -> TradeRecord:
        pnl = (exit_price - pos.entry_price) * pos.qty if pos.side == "LONG" else (pos.entry_price - exit_price) * pos.qty
        base = pos.entry_price * pos.qty
        pnl_pct = float(pnl / base) if base else 0.0
        return TradeRecord(
            symbol=pos.symbol,
            side=pos.side,
            entry_time=pos.entry_time,
            entry_price=float(pos.entry_price),
            exit_time=exit_time,
            exit_price=float(exit_price),
            exit_reason=str(reason),
            qty=float(pos.qty),
            pnl=float(pnl),
            pnl_pct=pnl_pct,
            bars_held=int(max(exit_index - pos.entry_index, 0)),
            strategy_name=pos.strategy_name,
        )

    @staticmethod
    def _validate_inputs(data: pd.DataFrame, signals: pd.DataFrame) -> None:
        if data.empty:
            raise ValueError("market data cannot be empty")

        required_data = {"time", "symbol", "open", "high", "low", "close"}
        missing_data = required_data - set(data.columns)
        if missing_data:
            raise ValueError(f"market data missing required columns: {sorted(missing_data)}")

        symbols = data["symbol"].dropna().astype(str).unique().tolist()
        if len(symbols) != 1:
            raise ValueError("Task 4 engine supports single symbol only")

        required_signals = {"time", "symbol", "signal", "strategy"}
        missing_signals = required_signals - set(signals.columns)
        if missing_signals:
            raise ValueError(f"signals missing required columns: {sorted(missing_signals)}")
