"""Base strategy interface for signal generation."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """Abstract strategy contract for generating time-series signals."""

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return strategy signals for provided market data.

        Expected input columns: ``time``, ``symbol``, ``open``, ``high``, ``low``, ``close``.
        """
        raise NotImplementedError
