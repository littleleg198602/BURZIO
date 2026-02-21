"""Breakout strategy placeholder."""

from __future__ import annotations

from .base_strategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    """Breakout strategy skeleton."""

    def generate_signals(self) -> dict[str, float]:
        raise NotImplementedError("Breakout strategy will be implemented later.")
