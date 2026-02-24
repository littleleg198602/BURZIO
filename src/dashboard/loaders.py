"""Helper loaders for dashboard backtest and paper-monitor views."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def discover_symbol_csvs(data_dir: str | Path) -> dict[str, str]:
    """Discover CSV files and infer symbol from filename prefix."""
    root = Path(data_dir)
    if not root.exists():
        return {}

    symbols: dict[str, str] = {}
    for path in sorted(root.glob("*.csv")):
        symbol = path.stem.split("_")[0].upper()
        symbols[symbol] = str(path)
    return symbols


def load_json_file(path: str | Path) -> dict | None:
    """Load JSON file if it exists, else return None."""
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_csv_file(path: str | Path) -> pd.DataFrame:
    """Load CSV to DataFrame; return empty DataFrame when missing."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def load_ndjson_file(path: str | Path, limit: int | None = None) -> pd.DataFrame:
    """Load newline-delimited JSON; skip malformed lines safely."""
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()

    rows: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    if limit is not None and limit > 0:
        rows = rows[-limit:]
    return pd.DataFrame(rows)


def load_paper_artifacts(
    *,
    state_path: str | Path,
    events_path: str | Path,
    status_path: str | Path,
    positions_path: str | Path,
    trades_path: str | Path,
    equity_path: str | Path,
    events_limit: int = 500,
) -> dict[str, object]:
    """Load all paper runtime artifacts into a single structure."""
    return {
        "state": load_json_file(state_path),
        "status": load_json_file(status_path),
        "positions": load_json_file(positions_path),
        "events": load_ndjson_file(events_path, limit=events_limit),
        "trades": load_csv_file(trades_path),
        "equity": load_csv_file(equity_path),
    }
