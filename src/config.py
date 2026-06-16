"""Project configuration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_TICKERS = ("NVDA", "AAPL", "MSFT", "AMD", "TSLA")
REACTION_WINDOWS = (1, 3, 5, 10)
DEFAULT_DB_PATH = Path("data/news_impact_yahoo.sqlite")
DEFAULT_EXCEL_PATH = Path("data/news_impact_yahoo.xlsx")
PRICE_PERIOD = "5y"
PRICE_INTERVAL = "1d"
YAHOO_RSS_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"


@dataclass(frozen=True)
class AppConfig:
    """Runtime settings for the analysis pipeline."""

    tickers: tuple[str, ...] = DEFAULT_TICKERS
    db_path: Path = DEFAULT_DB_PATH
    excel_path: Path = DEFAULT_EXCEL_PATH
    price_period: str = PRICE_PERIOD
    price_interval: str = PRICE_INTERVAL
    reaction_windows: tuple[int, ...] = REACTION_WINDOWS
