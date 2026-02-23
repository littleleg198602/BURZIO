"""Position sizing logic for portfolio backtesting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SizingConfig:
    """Sizing configuration for Task 5.

    Uses simplified forex price-delta PnL model consistent with Task 4.
    """

    risk_per_trade_pct: float = 0.01
    min_units: float = 0.0
    max_units: float | None = None
    fallback_fixed_units: float = 10_000.0


class PositionSizer:
    """Calculate position units from equity/risk and stop distance."""

    def __init__(self, config: SizingConfig | None = None):
        self.config = config or SizingConfig()

    @staticmethod
    def calculate_risk_amount(equity: float, risk_pct: float) -> float:
        """Return risk amount in account currency units."""
        if equity <= 0:
            raise ValueError("equity must be positive")
        if risk_pct <= 0:
            raise ValueError("risk_pct must be positive")
        return float(equity * risk_pct)

    def calculate_units_from_stop_distance(
        self,
        equity: float,
        stop_distance: float,
        risk_pct: float | None = None,
    ) -> float:
        """Calculate units with simplified model: units = risk_amount / stop_distance."""
        if stop_distance <= 0:
            raise ValueError("stop_distance must be positive")

        pct = float(risk_pct if risk_pct is not None else self.config.risk_per_trade_pct)
        risk_amount = self.calculate_risk_amount(equity, pct)
        units = float(risk_amount / stop_distance)

        if self.config.max_units is not None:
            units = min(units, float(self.config.max_units))
        units = max(units, float(self.config.min_units))
        return units

    def calculate_fixed_units(self, units: float | None = None) -> float:
        """Return fixed units fallback."""
        out = float(units if units is not None else self.config.fallback_fixed_units)
        if out <= 0:
            raise ValueError("fixed units must be positive")
        return out
