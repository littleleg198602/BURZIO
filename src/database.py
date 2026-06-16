"""SQLite persistence for prices, news, reactions, and phrase statistics."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, Sequence

PriceRow = tuple[str, str, float | None, float | None, float | None, float | None, float | None, int | None]
NewsRow = tuple[str, str, str, str, str, str]
ReactionRow = tuple[str, str, str, int, float | None]
PhraseStatRow = tuple[str, int, str, int, float, float, float, float]


class Database:
    """Small SQLite wrapper with idempotent upserts for cacheable data."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            self._migrate_phrase_stats(conn)
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS prices (
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    adj_close REAL,
                    volume INTEGER,
                    PRIMARY KEY (ticker, date)
                );
                CREATE TABLE IF NOT EXISTS news (
                    ticker TEXT NOT NULL,
                    guid TEXT NOT NULL,
                    published TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    link TEXT NOT NULL,
                    PRIMARY KEY (ticker, guid)
                );
                CREATE TABLE IF NOT EXISTS reactions (
                    ticker TEXT NOT NULL,
                    guid TEXT NOT NULL,
                    news_date TEXT NOT NULL,
                    window_days INTEGER NOT NULL,
                    return_pct REAL,
                    PRIMARY KEY (ticker, guid, window_days)
                );
                CREATE TABLE IF NOT EXISTS phrase_stats (
                    ticker TEXT NOT NULL,
                    window_days INTEGER NOT NULL,
                    phrase TEXT NOT NULL,
                    occurrences INTEGER NOT NULL,
                    average_return REAL NOT NULL,
                    win_rate_up REAL NOT NULL,
                    average_down_move REAL NOT NULL,
                    confidence_score REAL NOT NULL,
                    PRIMARY KEY (ticker, window_days, phrase)
                );
                """
            )

    def _migrate_phrase_stats(self, conn: sqlite3.Connection) -> None:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(phrase_stats)").fetchall()]
        if columns and "window_days" not in columns:
            conn.execute("DROP TABLE phrase_stats")

    def upsert_prices(self, rows: Iterable[PriceRow]) -> None:
        rows = list(rows)
        if not rows:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, date) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, adj_close=excluded.adj_close, volume=excluded.volume
                """,
                rows,
            )

    def upsert_news(self, rows: Iterable[NewsRow]) -> int:
        rows = list(rows)
        if not rows:
            return 0
        with self.connect() as conn:
            before = conn.total_changes
            conn.executemany(
                """
                INSERT OR IGNORE INTO news (ticker, guid, published, title, summary, link)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            return conn.total_changes - before

    def replace_reactions(self, rows: Iterable[ReactionRow]) -> None:
        rows = list(rows)
        if not rows:
            return
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO reactions VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ticker, guid, window_days) DO UPDATE SET
                    news_date=excluded.news_date, return_pct=excluded.return_pct
                """,
                rows,
            )

    def replace_phrase_stats(self, rows: Iterable[PhraseStatRow], tickers: Sequence[str]) -> None:
        with self.connect() as conn:
            conn.executemany("DELETE FROM phrase_stats WHERE ticker = ?", [(ticker,) for ticker in tickers])
            conn.executemany("INSERT INTO phrase_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?)", list(rows))

    def fetch_prices(self, ticker: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM prices WHERE ticker = ? ORDER BY date", (ticker,)).fetchall()

    def fetch_news(self, ticker: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM news WHERE ticker = ? ORDER BY published", (ticker,)).fetchall()

    def fetch_reactions(self, ticker: str) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM reactions WHERE ticker = ? ORDER BY news_date, guid, window_days", (ticker,)).fetchall()

    def fetch_phrase_stats(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM phrase_stats ORDER BY confidence_score DESC, occurrences DESC").fetchall()
