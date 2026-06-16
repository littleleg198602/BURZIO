"""Command-line pipeline for Yahoo Finance news impact analysis."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import AppConfig, DEFAULT_TICKERS
from .database import Database
from .excel_exporter import export_excel
from .phrase_stats import calculate_phrase_stats
from .reaction_analyzer import analyze_reactions
from .yahoo_news_loader import load_news
from .yahoo_price_loader import load_prices


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Yahoo Finance news impact on stock movement.")
    parser.add_argument("--tickers", nargs="+", default=list(DEFAULT_TICKERS), help="Ticker symbols to analyze.")
    parser.add_argument("--db", default=str(AppConfig().db_path), help="SQLite database path.")
    parser.add_argument("--output", default=str(AppConfig().excel_path), help="Excel output path.")
    parser.add_argument("--min-occurrences", type=int, default=2, help="Minimum phrase observations to include.")
    return parser.parse_args()


def run(config: AppConfig, min_occurrences: int = 2) -> None:
    """Run the full cache, analyze, and export workflow."""
    _ensure_parent(config.db_path)
    _ensure_parent(config.excel_path)
    db = Database(config.db_path)
    for ticker in config.tickers:
        price_count = load_prices(db, ticker, config.price_period, config.price_interval)
        news_count = load_news(db, ticker)
        reaction_count = analyze_reactions(db, ticker, config.reaction_windows)
        print(f"{ticker}: cached {price_count} price rows, {news_count} new news rows, {reaction_count} reactions")
    phrase_count = calculate_phrase_stats(db, config.tickers, min_occurrences=min_occurrences)
    export_excel(db, config.tickers, str(config.excel_path))
    print(f"Exported {phrase_count} phrase statistics to {config.excel_path}")


def _ensure_parent(path: Path) -> None:
    """Create a parent directory when the path is not in the current directory."""
    if str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    config = AppConfig(tickers=tuple(symbol.upper() for symbol in args.tickers), db_path=Path(args.db), excel_path=Path(args.output))
    run(config, min_occurrences=args.min_occurrences)


if __name__ == "__main__":
    main()
