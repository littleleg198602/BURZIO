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
        for window in windows:
            return_pct = None
            end_idx = start_idx + window
            if start_idx < len(closes) and end_idx < len(closes) and closes[start_idx] and closes[end_idx]:
                return_pct = (float(closes[end_idx]) - float(closes[start_idx])) / float(closes[start_idx])
            reactions.append((ticker, news["guid"], news_date, window, return_pct))
    db.replace_reactions(reactions)
    return len(reactions)
