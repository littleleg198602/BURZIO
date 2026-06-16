"""Extract words, bigrams, and trigrams from article text."""
from __future__ import annotations

from .text_cleaner import tokenize


def extract_phrases(title: str, summary: str) -> set[str]:
    """Extract unique unigram, bigram, and trigram phrases from title plus summary."""
    tokens = tokenize(f"{title} {summary}")
    phrases: set[str] = set(tokens)
    for n in (2, 3):
        phrases.update(" ".join(tokens[i : i + n]) for i in range(max(0, len(tokens) - n + 1)))
    return phrases
