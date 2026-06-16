"""Normalize news text for phrase extraction."""
from __future__ import annotations

import re

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "in", "is", "it",
    "its", "of", "on", "or", "that", "the", "this", "to", "was", "with", "yahoo", "finance",
}
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9']+")
TAG_RE = re.compile(r"<[^>]+>")


def tokenize(text: str) -> list[str]:
    """Return lower-case tokens with common stop words removed."""
    clean = TAG_RE.sub(" ", text).lower()
    return [token for token in TOKEN_RE.findall(clean) if token not in STOP_WORDS and len(token) > 1]
