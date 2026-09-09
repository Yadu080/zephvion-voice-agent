"""Knowledge base search for customer support answers.

Answers come only from knowledge_base.json, so the agent can't invent policies
or prices. Matching is done here rather than by handing the whole file to the
model, which keeps answers exact and costs nothing to run.

Scoring combines keyword hits, the topic name, and words from the answer text
itself, with light stemming and a synonym map so real phrasings match — "how
much does it cost", "what are your charges" and "is it expensive" all reach the
pricing entry. When nothing clears the confidence bar the caller is told so,
rather than being handed a near miss.
"""

import json
import re
from pathlib import Path

KB_PATH = Path(__file__).resolve().parent.parent / "knowledge_base.json"

# Words that carry no meaning for matching.
STOPWORDS = {
    "a", "an", "the", "is", "are", "am", "was", "were", "be", "been", "do", "does",
    "did", "can", "could", "would", "will", "shall", "should", "may", "might", "i",
    "you", "your", "we", "our", "us", "me", "my", "it", "its", "they", "them",
    "this", "that", "there", "here", "to", "of", "in", "on", "at", "for", "with",
    "and", "or", "but", "if", "so", "as", "by", "from", "about", "have", "has",
    "had", "please", "tell", "know", "want", "need", "like", "get", "give", "hi",
    "hello", "thanks", "thank", "just", "some", "any", "what", "when", "where",
    "how", "who", "which", "whats",
}

# Maps everyday phrasings onto the vocabulary used in the knowledge base.
SYNONYMS = {
    "cost": "price", "costs": "price", "charge": "price", "charges": "price",
    "fee": "price", "fees": "price", "rate": "price", "rates": "price",
    "expensive": "price", "cheap": "price", "pay": "price", "payment": "price",
    "much": "price", "afford": "price",
    "timing": "hours", "timings": "hours", "schedule": "hours", "shut": "close",
    "closing": "close", "closed": "close", "opening": "open", "opens": "open",
    "availability": "hours",
    "located": "location", "address": "location", "reach": "location",
    "directions": "location", "situated": "location", "parking": "location",
    "insurance": "insurance", "insured": "insurance", "cover": "insurance",
    "covered": "insurance", "coverage": "insurance", "claim": "insurance",
    "policy": "policy", "cancellation": "cancel", "cancelling": "cancel",
    "refund": "cancel", "reschedule": "cancel",
    "bring": "bring", "carry": "bring", "documents": "bring", "document": "bring",
    "prepare": "bring", "preparation": "bring", "required": "bring",
    "service": "services", "treatment": "services", "treatments": "services",
    "offer": "services", "offers": "services", "provide": "services",
    "specialist": "specialist", "specialists": "specialist",
    "doctor": "specialist", "doctors": "specialist", "physician": "specialist",
    # Deliberately not mapping "take" -> duration: "do you take my insurance"
    # is far more common than "how long does it take".
    "long": "duration", "duration": "duration", "length": "duration",
    "time": "duration",
    "new": "new", "first": "new", "register": "new", "registration": "new",
    "signup": "new", "join": "new",
    "emergency": "emergency", "urgent": "emergency", "serious": "emergency",
    "severe": "emergency", "immediately": "emergency",
}

MIN_SCORE = 2.0

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


def _stem(word: str) -> str:
    """Crude suffix stripping — enough to match plurals and -ing forms."""
    for suffix in ("ings", "ing", "ies", "es", "s"):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


def _normalize(text: str) -> set:
    words = re.findall(r"[a-z']+", (text or "").lower())
    out = set()
    for word in words:
        if word in STOPWORDS:
            continue
        word = SYNONYMS.get(word, word)
        out.add(word)
        out.add(_stem(word))
    return out


def _score(entry, question_words: set) -> float:
    score = 0.0

    # Keyword hits are the strongest signal.
    for keyword in entry.get("keywords", []):
        kw_words = _normalize(keyword)
        if not kw_words:
            continue
        overlap = kw_words & question_words
        if overlap:
            # Multi-word keywords count for more when fully matched.
            score += 2.0 * len(overlap) / len(kw_words) * (2 if len(kw_words) > 1 else 1)

    # The topic name is a decent signal too.
    score += 1.5 * len(_normalize(entry.get("topic", "")) & question_words)

    # Words from the answer itself catch phrasings nobody listed as keywords.
    score += 0.25 * len(_normalize(entry.get("answer", "")) & question_words)

    return score


def search(query: str):
    """Return the best-matching entry, or None if nothing is confident enough."""
    question_words = _normalize(query)
    if not question_words:
        return None

    ranked = sorted(
        ((_score(entry, question_words), entry) for entry in _load()),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not ranked:
        return None

    best_score, best_entry = ranked[0]
    return best_entry if best_score >= MIN_SCORE else None


def topics() -> list:
    return [entry["topic"] for entry in _load()]
