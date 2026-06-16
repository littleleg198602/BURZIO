"""Load and cache ticker news from Yahoo Finance RSS."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape

import feedparser

from .config import YAHOO_RSS_URL
from .database import Database, NewsRow


def load_news(db: Database, ticker: str) -> int:
    """Download currently available Yahoo Finance RSS news and cache unseen items."""
    feed = feedparser.parse(YAHOO_RSS_URL.format(ticker=ticker))
    rows: list[NewsRow] = []
    for entry in feed.entries:
        guid = str(entry.get("id") or entry.get("guid") or entry.get("link") or entry.get("title"))
        title = unescape(str(entry.get("title", "")).strip())
        summary = unescape(str(entry.get("summary", "")).strip())
        link = str(entry.get("link", "")).strip()
        published = _parse_published(entry.get("published") or entry.get("updated"))
        if guid and title and published:
            rows.append((ticker, guid, published, title, summary, link))
    return db.upsert_news(rows)


def _parse_published(value: object) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        parsed = parsedate_to_datetime(str(value))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).isoformat()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()
