"""MT5 CSV parser for forex OHLC market data."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from src.data.schemas import (
    CLOSE_COLUMN,
    HIGH_COLUMN,
    LOW_COLUMN,
    OPEN_COLUMN,
    SOURCE_FILE_COLUMN,
    SPREAD_COLUMN,
    SYMBOL_COLUMN,
    TIME_COLUMN,
    VOLUME_COLUMN,
)

logger = logging.getLogger(__name__)

_COLUMN_ALIASES: dict[str, list[str]] = {
    TIME_COLUMN: ["datetime", "date_time", "timestamp", "date time", "dateandtime"],
    "date": ["date", "day"],
    "clock": ["time", "time_only", "clock", "hour"],
    OPEN_COLUMN: ["open", "o"],
    HIGH_COLUMN: ["high", "h"],
    LOW_COLUMN: ["low", "l"],
    CLOSE_COLUMN: ["close", "c"],
    VOLUME_COLUMN: ["volume", "tickvolume", "tick_volume", "realvolume", "real_volume"],
    SPREAD_COLUMN: ["spread"],
    SYMBOL_COLUMN: ["symbol", "ticker", "instrument"],
}


def _normalize_columns(columns: list[str]) -> dict[str, str]:
    normalized = {}
    for original in columns:
        key = original.strip().lower().replace(" ", "_")
        normalized[key] = original
    return normalized


def _find_column(normalized_map: dict[str, str], logical_name: str) -> str | None:
    aliases = _COLUMN_ALIASES.get(logical_name, [logical_name])
    for alias in aliases:
        alias_norm = alias.strip().lower().replace(" ", "_")
        if alias_norm in normalized_map:
            return normalized_map[alias_norm]
    return None


def _detect_delimiter(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    candidates = {",": first_line.count(","), ";": first_line.count(";"), "\t": first_line.count("\t")}
    best = max(candidates, key=candidates.get)
    return best if candidates[best] > 0 else ","


def _infer_symbol_from_filename(path: Path) -> str | None:
    stem = path.stem.upper()
    match = re.search(r"([A-Z]{6})", stem)
    if match:
        return match.group(1)
    return None


def parse_mt5_csv(
    path: str | Path,
    symbol: str | None = None,
    timeframe: str = "H1",
    delimiter: str | None = None,
) -> pd.DataFrame:
    """Parse MT5 CSV into a dataframe with canonical column names.

    Returns dataframe with at least: time, symbol, open, high, low, close, volume, spread,
    source_file.
    """
    if timeframe.upper() != "H1":
        logger.warning("Task 2 parser currently tuned for H1 validation, got timeframe=%s", timeframe)

    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    sep = delimiter or _detect_delimiter(csv_path)
    df = pd.read_csv(csv_path, sep=sep)
    logger.info("Loaded MT5 CSV %s with %s rows using delimiter '%s'", csv_path, len(df), sep)

    if df.empty:
        raise ValueError(f"CSV file has no rows: {csv_path}")

    column_map = _normalize_columns(df.columns.tolist())

    datetime_col = _find_column(column_map, TIME_COLUMN)
    date_col = _find_column(column_map, "date")
    time_col = _find_column(column_map, "clock")

    if date_col and time_col:
        parsed_time = pd.to_datetime(
            df[date_col].astype(str).str.strip() + " " + df[time_col].astype(str).str.strip(),
            errors="coerce",
        )
    elif datetime_col:
        parsed_time = pd.to_datetime(df[datetime_col], errors="coerce")
    else:
        raise ValueError(
            "Could not find datetime information. Provide either a datetime column or Date+Time columns."
        )

    out = pd.DataFrame()
    out[TIME_COLUMN] = parsed_time

    for logical in (OPEN_COLUMN, HIGH_COLUMN, LOW_COLUMN, CLOSE_COLUMN):
        src_col = _find_column(column_map, logical)
        if src_col is None:
            raise ValueError(f"Missing required price column: {logical}")
        out[logical] = pd.to_numeric(df[src_col], errors="coerce")

    volume_col = _find_column(column_map, VOLUME_COLUMN)
    spread_col = _find_column(column_map, SPREAD_COLUMN)
    symbol_col = _find_column(column_map, SYMBOL_COLUMN)

    out[VOLUME_COLUMN] = (
        pd.to_numeric(df[volume_col], errors="coerce") if volume_col else 0.0
    )
    out[SPREAD_COLUMN] = (
        pd.to_numeric(df[spread_col], errors="coerce") if spread_col else 0.0
    )

    if symbol_col:
        out[SYMBOL_COLUMN] = df[symbol_col].astype(str).str.strip().str.upper()
    else:
        inferred_symbol = symbol or _infer_symbol_from_filename(csv_path)
        if not inferred_symbol:
            raise ValueError(
                "Symbol missing in CSV and could not be inferred from filename. "
                "Pass symbol='EURUSD' explicitly."
            )
        out[SYMBOL_COLUMN] = inferred_symbol.upper()
        logger.info("Symbol inferred for %s -> %s", csv_path.name, inferred_symbol.upper())

    out[SOURCE_FILE_COLUMN] = str(csv_path)

    invalid_mask = out[[TIME_COLUMN, OPEN_COLUMN, HIGH_COLUMN, LOW_COLUMN, CLOSE_COLUMN]].isna().any(axis=1)
    if invalid_mask.any():
        bad_count = int(invalid_mask.sum())
        raise ValueError(f"Found {bad_count} rows with invalid datetime/OHLC values in {csv_path}")

    return out
