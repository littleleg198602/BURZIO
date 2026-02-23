"""Deterministic execution model for single-symbol backtesting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionConfig:
    """Execution assumptions for fills.

    Prices are adjusted by half-spread and slippage against the trader.
    """

    slippage: float = 0.0
    use_data_spread: bool = True
    fixed_spread: float = 0.0
    fill_on_next_open: bool = True

    def spread_for_bar(self, bar_spread: float | int | None) -> float:
        """Return spread to use for current bar."""
        if self.use_data_spread and bar_spread is not None:
            return float(bar_spread)
        return float(self.fixed_spread)


def apply_entry_price(raw_open: float, side: str, spread: float, slippage: float) -> float:
    """Apply spread/slippage to entry price."""
    half = spread / 2.0
    if side == "LONG":
        return float(raw_open + half + slippage)
    if side == "SHORT":
        return float(raw_open - half - slippage)
    raise ValueError(f"Unsupported side: {side}")


def apply_exit_price(raw_price: float, side: str, spread: float, slippage: float) -> float:
    """Apply spread/slippage to exit price."""
    half = spread / 2.0
    if side == "LONG":
        return float(raw_price - half - slippage)
    if side == "SHORT":
        return float(raw_price + half + slippage)
    raise ValueError(f"Unsupported side: {side}")
