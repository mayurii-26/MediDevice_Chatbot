"""
search/query_rewriter.py

Rule-based query rewriter that runs BEFORE retrieval.

Design goals
------------
- Zero latency cost: pure Python, no LLM, no network call.
- Improves recall for FAISS and BM25 by producing cleaner, more specific
  search queries from conversational or abbreviated user input.
- Does NOT change the user-facing question — only the internal retrieval query.

Public API
----------
rewrite(query, intent) -> RewrittenQuery

RewrittenQuery
--------------
  .original   : str   — the raw user query, untouched
  .canonical  : str   — cleaned, normalised retrieval query (primary)
  .variants   : list  — additional search variants for multi-query retrieval

Pipeline position
-----------------
  User query
      │
  rewrite(query, intent)
      │
  canonical / variants  ──→  FAISS + BM25 retrieval
                                    │
                              reranker (uses original query for cross-encoder)
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Dataclass ──────────────────────────────────────────────────────────────

@dataclass
class RewrittenQuery:
    original:  str
    canonical: str
    variants:  list[str] = field(default_factory=list)


# ── Filler phrase patterns — stripped from query before retrieval ──────────
# These add noise to embeddings without contributing retrieval signal.
_FILLER_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*(can you |could you |please |kindly )+", re.I),
    re.compile(r"^\s*(tell me |give me |show me |explain |describe )(about |the |me )*", re.I),
    re.compile(r"^\s*(what (is|are|does|do) (the |a |an )?)", re.I),
    re.compile(r"^\s*(i want to know |i need |i am looking for |i would like )", re.I),
    re.compile(r"^\s*(do you know |do you have |can you tell me )(about |the )?", re.I),
    re.compile(r"\?+\s*$"),             # trailing question marks
    re.compile(r"\s{2,}", ),            # collapse extra whitespace
]

# ── Abbreviation expansion map ────────────────────────────────────────────
# Applied AFTER filler removal, BEFORE variant generation.
# Keys are lowercased exact tokens; values are expanded forms.
_ABBREV: dict[str, str] = {
    "ecg":    "electrocardiogram ECG",
    "ekg":    "electrocardiogram ECG",
    "aed":    "automated external defibrillator AED",
    "abpm":   "ambulatory blood pressure monitor ABPM",
    "spo2":   "pulse oximeter SpO2",
    "ctg":    "cardiotocograph CTG fetal monitor",
    "cpap":   "CPAP continuous positive airway pressure",
    "icu":    "ICU intensive care unit",
    "nicu":   "NICU neonatal intensive care unit",
    "ot":     "operating theatre",
    "bp":     "blood pressure",
    "hr":     "heart rate",
    "ivf":    "intravenous fluid",
}

# ── Intent-specific prefix map ────────────────────────────────────────────
# Prepending a structured phrase improves BM25 token overlap.
_INTENT_PREFIX: dict[str, str] = {
    "feature_query":        "features and capabilities of",
    "specification_query":  "technical specifications of",
    "comparison_query":     "compare features specifications of",
    "category_query":       "medical devices in category",
    "general_medical_query": "medical device",
}


def _strip_fillers(text: str) -> str:
    """Remove conversational filler phrases from the start of the query."""
    result = text.strip()
    changed = True
    while changed:
        changed = False
        for pat in _FILLER_PATTERNS[:6]:   # first 6 are start-anchored strip patterns
            new = pat.sub("", result).strip()
            if new != result:
                result = new
                changed = True
    # Collapse whitespace (last pattern)
    result = re.sub(r"\s{2,}", " ", result)
    return result.strip()


def _expand_abbreviations(text: str) -> str:
    """
    Replace known abbreviations with their expanded form + original token.
    Only replaces whole-word occurrences to avoid partial matches.
    Example: "ECG machine" → "electrocardiogram ECG machine"
    """
    words = text.split()
    out: list[str] = []
    for w in words:
        clean = w.lower().strip(".,;:()")
        if clean in _ABBREV:
            out.append(_ABBREV[clean])
        else:
            out.append(w)
    return " ".join(out)


def _add_intent_prefix(text: str, intent: str) -> str:
    """Prepend an intent-appropriate context phrase if not already present."""
    prefix = _INTENT_PREFIX.get(intent, "")
    if not prefix:
        return text
    text_lower = text.lower()
    # Don't double-add if the first word of the prefix is already in text
    first_word = prefix.split()[0]
    if text_lower.startswith(first_word):
        return text
    return f"{prefix} {text}"


def _generate_variants(canonical: str, original: str, intent: str) -> list[str]:
    """
    Generate 1–2 alternative search strings to improve recall.

    Strategy:
    - Variant 1: original query stripped of fillers (no abbreviation expansion,
      no prefix) — preserves exact product names and model numbers as typed.
    - Variant 2: intent-prefixed canonical (only for feature/spec intents where
      the prefix helps token matching significantly).
    """
    variants: list[str] = []

    stripped_original = _strip_fillers(original)
    if stripped_original.lower() != canonical.lower():
        variants.append(stripped_original)

    if intent in ("feature_query", "specification_query"):
        prefixed = _add_intent_prefix(canonical, intent)
        if prefixed.lower() != canonical.lower():
            variants.append(prefixed)

    # Deduplicate while preserving order
    seen: set[str] = {canonical.lower()}
    unique: list[str] = []
    for v in variants:
        if v.lower() not in seen and v.strip():
            seen.add(v.lower())
            unique.append(v)

    return unique[:2]    # cap at 2 variants — more adds noise


# ── Public API ─────────────────────────────────────────────────────────────

def rewrite(query: str, intent: str = "product_query") -> RewrittenQuery:
    """
    Rewrite a user query for optimal retrieval quality.

    Steps applied to produce `canonical`:
      1. Strip conversational filler phrases.
      2. Expand medical abbreviations (keeps original token too).
      3. Apply query normalisation (same rules as search/common.py).

    `variants` are additional strings to also retrieve against;
    the orchestrator union-merges and deduplicates all results.

    Parameters
    ----------
    query  : raw user query string
    intent : detected intent (from intent_detector.py)

    Returns
    -------
    RewrittenQuery with .original, .canonical, .variants
    """
    # Step 1 — strip fillers
    stripped = _strip_fillers(query)

    # Step 2 — expand abbreviations
    expanded = _expand_abbreviations(stripped)

    # Step 3 — apply the same normalisation already used in search/common.py
    # (handles "page writer" → "pagewriter", "TC 50" → "tc50", etc.)
    try:
        from search.common import normalise_query
        canonical = normalise_query(expanded)
    except Exception:
        canonical = expanded.lower().strip()

    # Step 4 — generate retrieval variants
    variants = _generate_variants(canonical, query, intent)

    print(
        f"[query_rewriter] original={query!r} | "
        f"canonical={canonical!r} | "
        f"variants={variants} | intent={intent}"
    )

    return RewrittenQuery(
        original=query,
        canonical=canonical,
        variants=variants,
    )
