"""Schema constants and validation helpers for normalized market data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

TIME_COLUMN = "time"
SYMBOL_COLUMN = "symbol"
OPEN_COLUMN = "open"
HIGH_COLUMN = "high"
LOW_COLUMN = "low"
CLOSE_COLUMN = "close"
VOLUME_COLUMN = "volume"
SPREAD_COLUMN = "spread"
SOURCE_FILE_COLUMN = "source_file"
ROW_ID_COLUMN = "row_id"

NORMALIZED_COLUMNS = [
    TIME_COLUMN,
    SYMBOL_COLUMN,
    OPEN_COLUMN,
    HIGH_COLUMN,
    LOW_COLUMN,
    CLOSE_COLUMN,
    VOLUME_COLUMN,
    SPREAD_COLUMN,
    SOURCE_FILE_COLUMN,
    ROW_ID_COLUMN,
]

REQUIRED_COLUMNS = [
    TIME_COLUMN,
    SYMBOL_COLUMN,
    OPEN_COLUMN,
    HIGH_COLUMN,
    LOW_COLUMN,
    CLOSE_COLUMN,
    VOLUME_COLUMN,
    SPREAD_COLUMN,
]


@dataclass(slots=True)
class H1ValidationSummary:
    """Summary of H1 timestamp quality checks for one symbol."""

    symbol: str
    rows: int
    duplicates: int
    non_monotonic: int
    expected_h1_gaps: int
    invalid_gaps: int
    missing_bar_estimate: int

    def to_dict(self) -> dict[str, Any]:
        """Return dictionary representation for logging/serialization."""
        return asdict(self)


def validate_required_columns(df: pd.DataFrame) -> None:
    """Ensure normalized dataframe includes required columns."""
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def validate_time_column(df: pd.DataFrame) -> None:
    """Ensure time column is datetime-like with no null values."""
    if TIME_COLUMN not in df.columns:
        raise ValueError("Missing required time column")

    if df[TIME_COLUMN].isna().any():
        raise ValueError("Time column contains null/invalid datetime values")

    if not pd.api.types.is_datetime64_any_dtype(df[TIME_COLUMN]):
        raise ValueError("Time column must use datetime dtype")


def validate_ohlc_values(df: pd.DataFrame) -> None:
    """Validate OHLC consistency: low <= open/high/close <= high."""
    for col in (OPEN_COLUMN, HIGH_COLUMN, LOW_COLUMN, CLOSE_COLUMN):
        if col not in df.columns:
            raise ValueError(f"Missing OHLC column: {col}")

    low = df[LOW_COLUMN]
    high = df[HIGH_COLUMN]
    open_ = df[OPEN_COLUMN]
    close = df[CLOSE_COLUMN]

    invalid = (low > high) | (open_ < low) | (open_ > high) | (close < low) | (close > high)
    if invalid.any():
        idx = invalid[invalid].index.tolist()[:5]
        raise ValueError(f"Invalid OHLC relationships detected on rows: {idx}")


def check_h1_frequency(df: pd.DataFrame, symbol: str | None = None) -> dict[str, Any]:
    """Return basic H1 integrity summary (duplicates, ordering, and hourly gaps).

    Weekend/session filtering is intentionally not handled in Task 2.
    """
    validate_required_columns(df)
    validate_time_column(df)

    subset = df
    summary_symbol = symbol or "ALL"
    if symbol is not None:
        subset = df[df[SYMBOL_COLUMN] == symbol].copy()
        summary_symbol = symbol

    subset = subset.sort_values([SYMBOL_COLUMN, TIME_COLUMN], kind="mergesort")

    duplicates = int(subset.duplicated([SYMBOL_COLUMN, TIME_COLUMN]).sum())

    non_monotonic = 0
    invalid_gaps = 0
    missing_bar_estimate = 0
    expected_h1_gaps = 0

    for sym, group in subset.groupby(SYMBOL_COLUMN):
        times = group[TIME_COLUMN]
        expected_h1_gaps += max(len(times) - 1, 0)

        diffs = times.diff().dropna()
        non_monotonic += int((diffs <= pd.Timedelta(0)).sum())
        invalid = diffs[diffs != pd.Timedelta(hours=1)]
        invalid_gaps += int(len(invalid))

        for gap in invalid:
            if gap > pd.Timedelta(hours=1):
                missing_bar_estimate += int(gap / pd.Timedelta(hours=1)) - 1

    summary = H1ValidationSummary(
        symbol=summary_symbol,
        rows=int(len(subset)),
        duplicates=duplicates,
        non_monotonic=non_monotonic,
        expected_h1_gaps=expected_h1_gaps,
        invalid_gaps=invalid_gaps,
        missing_bar_estimate=missing_bar_estimate,
    )
    return summary.to_dict()
