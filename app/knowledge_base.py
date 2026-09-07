"""Simple keyword-scored knowledge base for customer support answers.

Deliberately dependency-free: the entries live in knowledge_base.json and are
matched on keyword overlap, which is plenty for a bounded FAQ set and keeps
answers deterministic (no hallucinated policies).
"""

import json
import re
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent.parent / "knowledge_base.json"

_entries = None


def _load():
    global _entries
    if _entries is None:
        try:
            with open(KB_PATH) as f:
                _entries = json.load(f)
        except Exception as exc:
            print(f"[knowledge_base load failed] {exc}")
            _entries = []
    return _entries


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-z']+", (text or "").lower()))


def search(query: str) -> dict | None:
    """Return the best-matching entry, or None if nothing is relevant enough."""
    words = _tokenize(query)
    if not words:
        return None

    best, best_score = None, 0
    for entry in _load():
        score = 0
        for keyword in entry["keywords"]:
            kw_words = _tokenize(keyword)
            # Multi-word keywords must match fully; single words just need to appear.
            if kw_words and kw_words.issubset(words):
                score += len(kw_words)
        if score > best_score:
            best, best_score = entry, score

    return best if best_score > 0 else None


def topics() -> list:
    return [entry["topic"] for entry in _load()]
