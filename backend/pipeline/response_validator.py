"""
pipeline/response_validator.py

Validates Gemini-generated answers before they are returned to the user
or cached.

Purpose
-------
Gemini is probabilistic.  It can occasionally:
  - Return the out-of-scope sentinel even when context was present
  - Return a very short or empty response
  - Return a response about the wrong product
  - Echo the fallback message instead of generating content

This validator catches these cases and lets the caller decide to fall back
to the deterministic fallback_formatter instead.

Public API
----------
validate_response(answer, question, intent, matched_product, has_context)
    -> ValidationResult

ValidationResult
    .is_valid : bool
    .reason   : str     (human-readable, for logging)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


# ── Constants ──────────────────────────────────────────────────────────────

# Minimum acceptable answer length in characters
_MIN_ANSWER_CHARS = 60

# Fragments that indicate a non-answer (fallback/sentinel)
_FALLBACK_FRAGMENTS: frozenset[str] = frozenset({
    "i am a medical device assistant trained on",
    "please ask about supported medical devices",
    "our ai service is temporarily unavailable",
    "temporarily unavailable",
    "contact support@medideviceai.com",
    "contact support@medidevicechatbot.com",
})

# Fragments that indicate Gemini returned the out-of-scope sentinel
_OUT_OF_SCOPE_FRAGMENTS: frozenset[str] = frozenset({
    "i could not find relevant information",
    "could not find relevant information for your question",
    "please ask about a specific medical device",
})

# Raw metadata line patterns — if an answer STARTS with or heavily contains
# these patterns it is a raw retrieval chunk, not a formatted answer.
# The regex matches lines like "Product Name: PageWriter TC35" or
# "Category: Cardiology" at the very start of the response.
_RAW_METADATA_PATTERNS: list = [
    re.compile(r"^Product Name\s*:", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Category\s*:", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Description\s*:", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Features\s*:\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^Specifications\s*:\s*$", re.MULTILINE | re.IGNORECASE),
]

# Threshold: if this many raw metadata patterns match, reject the answer
_RAW_METADATA_THRESHOLD = 2


def _contains_raw_metadata(text: str) -> bool:
    """
    Return True if the answer looks like a raw retrieval chunk rather than
    a formatted response.  Checks for multiple raw 'Key: value' metadata
    lines that should never reach the frontend.
    """
    matches = sum(1 for p in _RAW_METADATA_PATTERNS if p.search(text))
    return matches >= _RAW_METADATA_THRESHOLD

# Intents that MUST reference the matched product by name in their response
_PRODUCT_NAME_REQUIRED_INTENTS: frozenset[str] = frozenset({
    "product_query",
    "feature_query",
    "specification_query",
})


# ── Result dataclass ───────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    is_valid: bool
    reason:   str = "ok"


# ── Helpers ────────────────────────────────────────────────────────────────

def _contains_fragment(text: str, fragments: frozenset[str]) -> bool:
    low = text.lower()
    return any(frag in low for frag in fragments)


def _product_name_present(answer: str, product: str) -> bool:
    """
    Check whether the answer mentions at least a significant part of the
    product name.  Handles compound names like "PageWriter TC50" by also
    accepting partial matches (e.g. "TC50" or "PageWriter").
    """
    answer_low = answer.lower()
    product_low = product.lower()

    # Exact match
    if product_low in answer_low:
        return True

    # Token-level match: at least one non-trivial token from the product name
    # must appear in the answer (ignores tokens < 3 chars like "TC")
    tokens = [t for t in re.split(r"[\s\-/]+", product_low) if len(t) >= 3]
    return any(t in answer_low for t in tokens)


# ── Public API ─────────────────────────────────────────────────────────────

def validate_response(
    answer:          str,
    question:        str,
    intent:          str,
    matched_product: Optional[str] = None,
    has_context:     bool = True,
) -> ValidationResult:
    """
    Validate a Gemini-generated answer.

    Parameters
    ----------
    answer          : generated text from Gemini (or fallback_formatter)
    question        : original user question (for logging)
    intent          : detected intent string
    matched_product : product name matched by retrieval, or None
    has_context     : True if retrieval found chunks to provide to Gemini

    Returns
    -------
    ValidationResult with .is_valid and .reason
    """
    if not answer or not answer.strip():
        return ValidationResult(False, "empty_response")

    stripped = answer.strip()

    # ── Length check ──────────────────────────────────────────────────────
    if len(stripped) < _MIN_ANSWER_CHARS:
        return ValidationResult(
            False,
            f"too_short (len={len(stripped)}, min={_MIN_ANSWER_CHARS})"
        )

    # ── Fallback sentinel check ───────────────────────────────────────────
    if _contains_fragment(stripped, _FALLBACK_FRAGMENTS):
        return ValidationResult(False, "fallback_sentinel_detected")

    # ── Raw metadata / unformatted chunk check ────────────────────────────
    # If the answer contains multiple raw "Key: value" metadata lines it is
    # a raw retrieval chunk that bypassed formatting — must be rejected.
    if _contains_raw_metadata(stripped):
        return ValidationResult(False, "raw_metadata_chunk_detected")

    # ── Out-of-scope sentinel when context was available ─────────────────
    # If we had retrieved context but Gemini still returned "I could not find…"
    # that is a failure — the fallback_formatter would do better.
    if has_context and _contains_fragment(stripped, _OUT_OF_SCOPE_FRAGMENTS):
        return ValidationResult(
            False,
            "out_of_scope_sentinel_with_context"
        )

    # ── Product name presence for product/feature/spec intents ───────────
    if (
        matched_product
        and has_context
        and intent in _PRODUCT_NAME_REQUIRED_INTENTS
    ):
        if not _product_name_present(stripped, matched_product):
            return ValidationResult(
                False,
                f"product_name_absent (expected='{matched_product}')"
            )

    # ── Comparison query must contain product section headers ─────────────
    # format_comparison() now emits "### Product A" / "### Product B" /
    # "### Key Differences" / "### Recommendation" — no markdown table.
    # Accept if: has at least one "###" section header, OR has a "|" table
    # (Gemini may still produce a table and that is fine too).
    if intent == "comparison_query" and has_context:
        _has_section = any(
            line.strip().startswith("###")
            for line in stripped.splitlines()
        )
        _has_table = any(
            line.strip().startswith("|") and line.strip().endswith("|")
            for line in stripped.splitlines()
        )
        if not _has_section and not _has_table:
            return ValidationResult(
                False,
                "comparison_missing_structure (no ### sections or table found)"
            )

    # ── Specification query must contain bullet specs or unavailable msg ──
    # format_specifications() now emits "• **Param:** value" bullets.
    # Accept if: has "•" bullets, OR a markdown table, OR the unavailable msg.
    if intent == "specification_query" and has_context:
        _spec_unavailable = "detailed specifications are currently unavailable"
        _has_bullets  = "•" in stripped
        _has_table    = any(
            line.strip().startswith("|") and line.strip().endswith("|")
            for line in stripped.splitlines()
        )
        _has_unavail  = _spec_unavailable in stripped.lower()
        if not _has_bullets and not _has_table and not _has_unavail:
            return ValidationResult(
                False,
                "specification_missing_content (no bullets, table, or unavailable message)"
            )

    # ── General medical query must contain 🏥 heading or known sections ───
    # format_general_medical() now emits "## 🏥 <Concept>" with
    # "### What it is" / "### Purpose" / "### Clinical Use" sections.
    if intent == "general_medical_query" and has_context:
        _has_hc_heading = any(
            "\U0001f3e5" in line   # 🏥 U+1F3E5
            for line in stripped.splitlines()
        )
        _known_sections = (
            "### What it is", "### Purpose", "### Clinical Use",
            "### Related Devices",
            # legacy section names still accepted (Gemini may produce them)
            "## Key Points", "## Common Uses", "## Benefits",
        )
        _section_count = sum(1 for s in _known_sections if s in stripped)
        if not _has_hc_heading and _section_count < 2:
            return ValidationResult(
                False,
                "general_medical_missing_structure (no 🏥 heading and fewer than 2 section headers)"
            )

    return ValidationResult(True, "ok")
