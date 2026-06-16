"""Load and cache ticker news from Yahoo Finance RSS and Yahoo Search."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Iterable

import feedparser
import yfinance as yf

from .config import NEWS_LOOKBACK_YEARS, YAHOO_RSS_URL, YAHOO_SEARCH_NEWS_COUNT
from .database import Database, NewsRow


def load_news(db: Database, ticker: str, lookback_years: int = NEWS_LOOKBACK_YEARS) -> int:
    """Download Yahoo news that is available for a ticker and cache unseen items.

    Yahoo RSS usually returns only recent items. Yahoo Search can return more items,
    but it still does not guarantee a complete five-year archive. We cache everything
    Yahoo returns inside the requested lookback window and build history over time.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=365 * lookback_years)
    rows = [row for row in _rss_rows(ticker) + _search_rows(ticker) if _is_inside_lookback(row, cutoff)]
    return db.upsert_news(_dedupe_rows(rows))


def _rss_rows(ticker: str) -> list[NewsRow]:
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
    return rows


def _search_rows(ticker: str) -> list[NewsRow]:
    try:
        search = yf.Search(ticker, news_count=YAHOO_SEARCH_NEWS_COUNT, max_results=0, lists_count=0, include_research=False, raise_errors=False)
    except Exception as exc:
        print(f"{ticker}: Yahoo Search news failed: {exc}")
        return []

    rows: list[NewsRow] = []
    for item in getattr(search, "news", []) or []:
        guid = str(item.get("uuid") or item.get("link") or item.get("title", ""))
        title = unescape(str(item.get("title", "")).strip())
        publisher = str(item.get("publisher", "Yahoo Finance")).strip()
        summary = f"Zdroj: {publisher}" if publisher else ""
        link = str(item.get("link", "")).strip()
        published = _parse_unix_timestamp(item.get("providerPublishTime"))
        if guid and title and published:
            rows.append((ticker, guid, published, title, summary, link))
    return rows


def _dedupe_rows(rows: Iterable[NewsRow]) -> list[NewsRow]:
    seen: set[tuple[str, str]] = set()
    unique: list[NewsRow] = []
    for row in rows:
        key = (row[0], row[1])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _is_inside_lookback(row: NewsRow, cutoff: datetime) -> bool:
    try:
        published = datetime.fromisoformat(row[2])
    except ValueError:
        return True
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return published >= cutoff


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


def _parse_unix_timestamp(value: object) -> str:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
