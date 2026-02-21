"""Moving-average crossover strategy placeholder."""

from __future__ import annotations

from .base_strategy import BaseStrategy


class MACrossoverStrategy(BaseStrategy):
    """MA crossover strategy skeleton."""

    def generate_signals(self) -> dict[str, float]:
        raise NotImplementedError("MA crossover strategy will be implemented later.")
