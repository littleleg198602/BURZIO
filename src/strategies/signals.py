"""Signal utility helpers."""

from __future__ import annotations

from typing import Iterable

import pandas as pd


SIGNAL_COLUMNS = ["time", "symbol", "signal", "strategy"]


def validate_signal_schema(df: pd.DataFrame) -> None:
    """Validate canonical strategy signal schema."""
    missing = [c for c in SIGNAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing signal columns: {missing}")


def combine_signals(signal_frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate multiple signal frames with consistent schema."""
    frames = list(signal_frames)
    if not frames:
        return pd.DataFrame(columns=SIGNAL_COLUMNS)

    for frame in frames:
        validate_signal_schema(frame)

    combined = pd.concat([f[SIGNAL_COLUMNS] for f in frames], ignore_index=True)
    combined["time"] = pd.to_datetime(combined["time"], errors="coerce")
    combined = combined.sort_values(["symbol", "time", "strategy"], kind="mergesort").reset_index(drop=True)
    return combined
