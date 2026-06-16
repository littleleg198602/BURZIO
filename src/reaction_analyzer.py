"""Calculate post-news price reactions."""
from __future__ import annotations

from bisect import bisect_left
from datetime import datetime

from .database import Database, ReactionRow


def analyze_reactions(db: Database, ticker: str, windows: tuple[int, ...]) -> int:
    """Calculate forward returns from the first trading day on/after each news date."""
    price_rows = db.fetch_prices(ticker)
    news_rows = db.fetch_news(ticker)
    dates = [row["date"] for row in price_rows]
    closes = [row["adj_close"] or row["close"] for row in price_rows]
    reactions: list[ReactionRow] = []
    for news in news_rows:
        news_date = datetime.fromisoformat(news["published"]).date().isoformat()
        start_idx = bisect_left(dates, news_date)
        start_price = _safe_price(closes[start_idx]) if start_idx < len(closes) else None
        for window in windows:
            return_pct = None
            end_price = None
            end_idx = start_idx + window
            if start_price and end_idx < len(closes):
                end_price = _safe_price(closes[end_idx])
                if end_price:
                    return_pct = (end_price - start_price) / start_price
            reactions.append((ticker, news["guid"], news_date, window, return_pct, start_price, end_price))
    db.replace_reactions(reactions)
    return len(reactions)


def _safe_price(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
