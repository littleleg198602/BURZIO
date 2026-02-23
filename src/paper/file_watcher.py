"""Polling helpers for MT5 CSV paper runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data.normalizer import normalize_from_csv


@dataclass(slots=True)
class ChangedFile:
    """Filesystem change metadata for one symbol CSV."""

    symbol: str
    path: str
    mtime: float


def discover_symbol_files(input_dir: str | Path, symbols: list[str] | None = None) -> dict[str, str]:
    """Discover symbol CSV files in input directory."""
    root = Path(input_dir)
    if not root.exists():
        return {}

    out: dict[str, str] = {}
    allowed = {s.upper() for s in symbols} if symbols else None
    for path in sorted(root.glob("*.csv")):
        symbol = path.stem.upper().split("_")[0]
        if allowed is not None and symbol not in allowed:
            continue
        out[symbol] = str(path)
    return out


def poll_file_changes(
    files: dict[str, str],
    last_seen_mtime: dict[str, float] | None = None,
) -> tuple[list[ChangedFile], dict[str, float]]:
    """Return changed files since last poll and updated mtime map."""
    last = dict(last_seen_mtime or {})
    changed: list[ChangedFile] = []
    for symbol, path in files.items():
        csv_path = Path(path)
        if not csv_path.exists():
            continue
        mtime = csv_path.stat().st_mtime
        if mtime > float(last.get(symbol, 0.0)):
            changed.append(ChangedFile(symbol=symbol, path=str(csv_path), mtime=mtime))
        last[symbol] = mtime
    return changed, last


def load_new_bars_for_symbol(
    path: str | Path,
    symbol: str,
    last_processed_time: str | None,
    confirmation_lag: int = 1,
) -> pd.DataFrame:
    """Load only newly confirmed bars for one symbol.

    Uses confirmation lag: newest ``confirmation_lag`` bars are ignored to avoid
    acting on still-forming candles.
    """
    if confirmation_lag < 0:
        raise ValueError("confirmation_lag must be >= 0")

    df = normalize_from_csv(path=path, symbol=symbol)
    if df.empty:
        return df

    df = df.sort_values("time", kind="mergesort").reset_index(drop=True)

    if confirmation_lag > 0 and len(df) > confirmation_lag:
        df = df.iloc[:-confirmation_lag].copy()
    elif confirmation_lag > 0:
        return df.iloc[0:0].copy()

    if last_processed_time:
        ts = pd.to_datetime(last_processed_time)
        df = df[df["time"] > ts].copy()

    return df.reset_index(drop=True)
