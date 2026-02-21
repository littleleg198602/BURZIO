"""Normalization pipeline for MT5 parsed dataframes."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.data.mt5_parser import parse_mt5_csv
from src.data.schemas import (
    CLOSE_COLUMN,
    HIGH_COLUMN,
    LOW_COLUMN,
    NORMALIZED_COLUMNS,
    OPEN_COLUMN,
    ROW_ID_COLUMN,
    SOURCE_FILE_COLUMN,
    SPREAD_COLUMN,
    SYMBOL_COLUMN,
    TIME_COLUMN,
    VOLUME_COLUMN,
    check_h1_frequency,
    validate_ohlc_values,
    validate_required_columns,
    validate_time_column,
)

logger = logging.getLogger(__name__)


def finalize_normalized_dataframe(
    df: pd.DataFrame,
    duplicate_keep: str = "last",
) -> pd.DataFrame:
    """Finalize ordering, deduplication, row ids, and validation."""
    work = df.copy()

    validate_required_columns(work)

    work[TIME_COLUMN] = pd.to_datetime(work[TIME_COLUMN], errors="coerce")
    work[SYMBOL_COLUMN] = work[SYMBOL_COLUMN].astype(str).str.strip().str.upper()

    for col in (OPEN_COLUMN, HIGH_COLUMN, LOW_COLUMN, CLOSE_COLUMN, VOLUME_COLUMN, SPREAD_COLUMN):
        work[col] = pd.to_numeric(work[col], errors="coerce")

    before_dropna = len(work)
    work = work.dropna(subset=[TIME_COLUMN, OPEN_COLUMN, HIGH_COLUMN, LOW_COLUMN, CLOSE_COLUMN, SYMBOL_COLUMN])
    dropped = before_dropna - len(work)
    if dropped:
        logger.warning("Dropped %s rows due to invalid required values", dropped)

    if SOURCE_FILE_COLUMN not in work.columns:
        work[SOURCE_FILE_COLUMN] = ""

    work[VOLUME_COLUMN] = work[VOLUME_COLUMN].fillna(0.0).astype(float)
    work[SPREAD_COLUMN] = work[SPREAD_COLUMN].fillna(0.0).astype(float)

    work = work.sort_values([SYMBOL_COLUMN, TIME_COLUMN], kind="mergesort")

    pre_dups = len(work)
    work = work.drop_duplicates(subset=[SYMBOL_COLUMN, TIME_COLUMN], keep=duplicate_keep)
    removed = pre_dups - len(work)
    if removed:
        logger.info("Removed %s duplicate rows by (%s, %s)", removed, SYMBOL_COLUMN, TIME_COLUMN)

    work = work.reset_index(drop=True)
    work[ROW_ID_COLUMN] = work.index.astype(int)

    work = work[NORMALIZED_COLUMNS]

    validate_required_columns(work)
    validate_time_column(work)
    validate_ohlc_values(work)

    return work


def normalize_mt5_dataframe(
    df: pd.DataFrame,
    symbol: str | None = None,
    source_file: str | None = None,
    duplicate_keep: str = "last",
) -> pd.DataFrame:
    """Normalize parsed MT5 dataframe into internal target schema."""
    work = df.copy()

    if symbol is not None:
        work[SYMBOL_COLUMN] = symbol.upper()

    if source_file is not None:
        work[SOURCE_FILE_COLUMN] = source_file

    normalized = finalize_normalized_dataframe(work, duplicate_keep=duplicate_keep)

    for sym in normalized[SYMBOL_COLUMN].unique():
        summary = check_h1_frequency(normalized, symbol=sym)
        logger.info("H1 validation summary for %s: %s", sym, summary)

    return normalized


def normalize_from_csv(
    path: str | Path,
    symbol: str | None = None,
    timeframe: str = "H1",
    delimiter: str | None = None,
    duplicate_keep: str = "last",
) -> pd.DataFrame:
    """Parse CSV then normalize into canonical dataframe format."""
    parsed = parse_mt5_csv(path=path, symbol=symbol, timeframe=timeframe, delimiter=delimiter)
    return normalize_mt5_dataframe(parsed, source_file=str(path), duplicate_keep=duplicate_keep)


def load_multiple_mt5_csvs(
    paths: list[str | Path],
    timeframe: str = "H1",
    duplicate_keep: str = "last",
) -> pd.DataFrame:
    """Load, normalize, and combine multiple MT5 CSV files."""
    if not paths:
        raise ValueError("paths cannot be empty")

    frames = [
        normalize_from_csv(path=p, timeframe=timeframe, duplicate_keep=duplicate_keep)
        for p in paths
    ]

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values([SYMBOL_COLUMN, TIME_COLUMN], kind="mergesort").reset_index(drop=True)
    combined[ROW_ID_COLUMN] = combined.index.astype(int)

    for sym in combined[SYMBOL_COLUMN].unique():
        summary = check_h1_frequency(combined, symbol=sym)
        logger.info("Combined H1 summary for %s: %s", sym, summary)

    return combined[NORMALIZED_COLUMNS]
