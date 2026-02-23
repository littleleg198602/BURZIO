"""Portfolio-level risk controls for Task 5."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PortfolioRiskConfig:
    """Risk constraints applied before opening new positions."""

    max_open_trades: int = 3
    max_risk_per_trade_pct: float = 0.02
    max_portfolio_risk_pct: float = 0.05
    max_drawdown_guard_pct: float = 0.2


class PortfolioRiskManager:
    """Decide whether portfolio can open a new trade."""

    def __init__(self, config: PortfolioRiskConfig | None = None):
        self.config = config or PortfolioRiskConfig()

    @staticmethod
    def current_drawdown_pct(current_equity: float, peak_equity: float) -> float:
        """Return current drawdown fraction from peak."""
        if peak_equity <= 0:
            return 0.0
        return max(0.0, (peak_equity - current_equity) / peak_equity)

    def is_drawdown_guard_active(self, current_equity: float, peak_equity: float) -> bool:
        """Whether drawdown guard blocks new entries."""
        return self.current_drawdown_pct(current_equity, peak_equity) >= self.config.max_drawdown_guard_pct

    @staticmethod
    def current_open_risk(open_positions: dict[str, dict[str, float]]) -> float:
        """Sum open risk amounts from positions map."""
        return float(sum(float(p.get("risk_amount", 0.0)) for p in open_positions.values()))

    def can_open_trade(
        self,
        *,
        open_positions: dict[str, dict[str, float]],
        requested_risk_amount: float,
        current_equity: float,
        peak_equity: float,
    ) -> tuple[bool, str]:
        """Validate constraints for a potential new trade."""
        if len(open_positions) >= self.config.max_open_trades:
            return False, "max_open_trades_reached"

        if self.is_drawdown_guard_active(current_equity, peak_equity):
            return False, "drawdown_guard_active"

        if current_equity <= 0:
            return False, "non_positive_equity"

        requested_pct = requested_risk_amount / current_equity
        if requested_pct > self.config.max_risk_per_trade_pct:
            return False, "max_risk_per_trade_exceeded"

        open_risk_pct = self.current_open_risk(open_positions) / current_equity
        if open_risk_pct + requested_pct > self.config.max_portfolio_risk_pct:
            return False, "max_portfolio_risk_exceeded"

        return True, "accepted"
