"""Aggregate reaction statistics by extracted phrase."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean

from .database import Database, PhraseStatRow
from .phrase_extractor import extract_phrases


def calculate_phrase_stats(db: Database, tickers: tuple[str, ...], min_occurrences: int = 2) -> int:
    """Calculate phrase-level statistics separately for every reaction window."""
    rows: list[PhraseStatRow] = []
    for ticker in tickers:
        returns_by_window_and_phrase: dict[tuple[int, str], list[float]] = defaultdict(list)
        news_by_guid = {row["guid"]: row for row in db.fetch_news(ticker)}
        phrases_by_guid = {
            guid: extract_phrases(news["title"], news["summary"])
            for guid, news in news_by_guid.items()
        }

        for reaction in db.fetch_reactions(ticker):
            return_pct = reaction["return_pct"]
            if return_pct is None or reaction["guid"] not in phrases_by_guid:
                continue
            for phrase in phrases_by_guid[reaction["guid"]]:
                key = (int(reaction["window_days"]), phrase)
                returns_by_window_and_phrase[key].append(float(return_pct))

        for (window_days, phrase), returns in returns_by_window_and_phrase.items():
            if len(returns) < min_occurrences:
                continue
            avg_return = mean(returns)
            wins = [value for value in returns if value > 0]
            downs = [value for value in returns if value < 0]
            win_rate = len(wins) / len(returns)
            average_down = mean(downs) if downs else 0.0
            confidence = _confidence_score(returns, avg_return, win_rate)
            rows.append((ticker, window_days, phrase, len(returns), avg_return, win_rate, average_down, confidence))
    db.replace_phrase_stats(rows, tickers)
    return len(rows)


def _confidence_score(returns: list[float], average_return: float, win_rate: float) -> float:
    """Rank phrases by sample size, directional consistency, and average move size."""
    sample_weight = len(returns) ** 0.5
    directional_weight = 0.5 + abs(win_rate - 0.5)
    return sample_weight * abs(average_return) * directional_weight
