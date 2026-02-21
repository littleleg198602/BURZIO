"""Base strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """Abstract strategy contract for signal generation."""

    @abstractmethod
    def generate_signals(self) -> dict[str, float]:
        """Return symbol-to-signal mapping (placeholder contract)."""
        raise NotImplementedError
