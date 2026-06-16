"""Load and cache historical prices from yfinance."""
from __future__ import annotations

from datetime import timezone

import yfinance as yf

from .config import PRICE_INTERVAL, PRICE_PERIOD
from .database import Database, PriceRow


def load_prices(db: Database, ticker: str, period: str = PRICE_PERIOD, interval: str = PRICE_INTERVAL) -> int:
    """Download five years of daily prices and cache them in SQLite."""
    frame = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
        group_by="column",
        multi_level_index=False,
    )
    if frame.empty:
        return 0
    rows: list[PriceRow] = []
    for index, row in frame.iterrows():
        date = index.to_pydatetime().astimezone(timezone.utc).date().isoformat() if index.tzinfo else index.date().isoformat()
        rows.append(
            (
                ticker,
                date,
                _float(row.get("Open")),
                _float(row.get("High")),
                _float(row.get("Low")),
                _float(row.get("Close")),
                _float(row.get("Adj Close", row.get("Close"))),
                _int(row.get("Volume")),
            )
        )
    db.upsert_prices(rows)
    return len(rows)


def _float(value: object) -> float | None:
    try:
        if hasattr(value, "iloc"):
            value = value.iloc[0]
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    try:
        if hasattr(value, "iloc"):
            value = value.iloc[0]
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None
