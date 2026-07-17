"""
dynamic_search/wikipedia_guard.py

Guard and topic extractor for Wikipedia lookups.

Responsibilities
----------------
1. Decide whether a Wikipedia lookup is appropriate for a given query/intent.
   Wikipedia must NEVER be called for device-specific queries.

2. Extract the best search topic from the user's natural language question
   to use as the Wikipedia API lookup term.

Public API
----------
should_use_wikipedia(query, intent) -> bool
    Returns True only when Wikipedia is appropriate:
      - Intent is GENERAL_MEDICAL
      - No known product name fragment appears in the query
      - No device model number appears in the query

extract_topic(query, intent) -> str
    Return the cleaned topic string to pass to wikipedia_service.fetch().
    Strips filler, removes device-specific tokens, returns the medical
    concept core (e.g. "what is electrocardiography?" → "electrocardiography").

Design
------
These functions are intentionally conservative: when in doubt they return
False / a broad topic rather than risk injecting Wikipedia content into a
product-specific answer.

The guard is checked in orchestrator.py BEFORE calling wikipedia_service.
"""

from __future__ import annotations

import re
from typing import Optional


# ── Intent constants (imported at call-time to avoid circular import) ──────
# Copied here as string literals for guard logic — no import needed at module level.
_GENERAL_MEDICAL = "general_medical_query"

# Intents that are device-specific — Wikipedia is never appropriate
_DEVICE_INTENTS: frozenset[str] = frozenset({
    "product_query",
    "feature_query",
    "specification_query",
    "comparison_query",
})

# Category intent is borderline; we allow Wikipedia only when no product
# fragment is mentioned (guard handles this below).
_CATEGORY_INTENT = "category_query"


# ── Known product fragment guard ──────────────────────────────────────────
# If any of these appear in the query, it is a device-specific question
# and Wikipedia must NOT be called.  Matches are case-insensitive substrings.
_PRODUCT_FRAGMENTS: frozenset[str] = frozenset({
    # PageWriter series
    "pagewriter", "tc50", "tc35", "tc10",
    # HeartStart / AED
    "heartstart", "frx", "hs1",
    # Efficia
    "efficia", "dfm100",
    # ST80i
    "st80i",
    # Oscar
    "oscar 2",
    # Cardiac Workstation
    "cardiac workstation",
    # Trilogy
    "trilogy",
    # Generic device model patterns: letters + digits
})

# Regex that matches bare model-number patterns (e.g. "TC50", "DFM100")
_MODEL_NUMBER_RE = re.compile(r"\b[A-Za-z]{1,4}\d{2,5}[A-Za-z]?\b")


def _contains_product(query: str) -> bool:
    """Return True if the query mentions any known product or model number."""
    q = query.lower()
    if any(frag in q for frag in _PRODUCT_FRAGMENTS):
        return True
    if _MODEL_NUMBER_RE.search(query):
        return True
    return False


# ── Topic extraction helpers ───────────────────────────────────────────────

# Filler phrases stripped before extracting the search topic
_TOPIC_FILLER: list[re.Pattern] = [
    re.compile(r"^\s*(can you |could you |please |kindly )+", re.I),
    re.compile(r"^\s*(tell me |give me |show me |explain |describe )(about |the |me )*", re.I),
    re.compile(r"^\s*(what (is|are|does|do) (the |a |an )?)", re.I),
    re.compile(r"^\s*(i want to know |i need |i am looking for )", re.I),
    re.compile(r"^\s*(do you know |do you have )(about |the )?", re.I),
    re.compile(r"\?+\s*$"),
    re.compile(r"\s{2,}"),
]

# Medical concept keywords we specifically want to keep as the topic
# (helps avoid extracting "medical devices" from category queries)
_MEDICAL_KEYWORDS: list[str] = [
    "electrocardiogram", "electrocardiography", "ecg", "ekg",
    "defibrillation", "cardiac arrest", "arrhythmia",
    "phototherapy", "jaundice", "bilirubin",
    "intubation", "laryngoscopy",
    "oximetry", "pulse oximeter", "spo2",
    "ambulatory blood pressure", "abpm",
    "cpap", "bubble cpap", "ventilation", "ventilator",
    "stress testing", "holter", "holter monitor",
    "anaesthesia", "anesthesia",
    "neonatal", "radiant warmer",
    "infusion pump", "syringe pump",
    "patient monitoring",
    "surgery lights", "surgical lights", "operating theatre lights",
]


def _strip_filler(text: str) -> str:
    result = text.strip()
    changed = True
    while changed:
        changed = False
        for pat in _TOPIC_FILLER:
            new = pat.sub("", result).strip() if pat.pattern != r"\s{2,}" else re.sub(r"\s{2,}", " ", result)
            if new != result:
                result = new
                changed = True
    return result.strip()


# ── Public API ─────────────────────────────────────────────────────────────

def should_use_wikipedia(query: str, intent: str) -> bool:
    """
    Return True only when a Wikipedia lookup is safe and useful.

    Rules (all must pass):
      1. Intent is GENERAL_MEDICAL  (Wikipedia not used for any other intent)
      2. No known product fragment in query  (device-specific → no Wikipedia)
      3. No bare model-number pattern in query

    Category queries and product queries are excluded by rule 1.
    """
    if intent != _GENERAL_MEDICAL:
        return False

    if _contains_product(query):
        print(f"[wikipedia_guard] BLOCKED | product fragment detected | query={query!r}")
        return False

    return True


def extract_topic(query: str, intent: str) -> str:
    """
    Extract the best Wikipedia search topic from a user query.

    Strategy:
      1. Check if a known medical keyword appears in the query — use it
         directly (most precise lookup term).
      2. Otherwise strip filler phrases and return what remains.

    Returns a non-empty string (falls back to the stripped query).
    """
    q_lower = query.lower()

    # Priority: known medical keywords (most specific → longest match wins)
    matches = [kw for kw in _MEDICAL_KEYWORDS if kw in q_lower]
    if matches:
        # Take the longest matching keyword (most specific)
        topic = max(matches, key=len)
        print(f"[wikipedia_guard] TOPIC (keyword match) | topic={topic!r}")
        return topic

    # Fallback: strip filler and use the remainder
    stripped = _strip_filler(query)
    topic = stripped if stripped else query.strip()
    print(f"[wikipedia_guard] TOPIC (stripped query) | topic={topic!r}")
    return topic
