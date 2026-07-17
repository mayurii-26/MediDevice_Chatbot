"""
pipeline/context_cleaner.py

Dedicated context cleaning module.

Runs AFTER retrieval and reranking, BEFORE context is passed to Gemini.

Purpose
-------
Raw retrieval chunks can contain:
  - Duplicate sentences that appear in multiple chunks (wastes context tokens)
  - Very short meaningless fragments (isolated numbers, lone punctuation)
  - OCR noise (e.g. "3", "Page 1", "©", "www.philips.com")
  - Excessive blank lines

CRITICAL INVARIANTS (must never be violated):
  - Newlines between lines are ALWAYS preserved.  Joining lines with " "
    produces "ProductPageWriterTC35Category..." which is the bug this
    module exists to fix.
  - Single-word structural labels (Product, Category, Summary, Features,
    Specifications, Highlights, Source, Description) are ALWAYS kept.
    They are section headers that the Gemini prompt depends on.
  - Bullet markers ("- text") are always kept verbatim.
  - Markdown formatting characters (**, *, #, |) are never stripped.

Public API
----------
clean_chunks(chunks: list[str]) -> list[str]
    Accepts formatted context sections (as built by _format_product_chunk),
    returns cleaned versions.  Empty sections are dropped.

clean_pdf_highlight(text: str) -> str
    Cleans a single PDF highlight string.
"""

import re
from typing import Optional


# ── Structural labels — single-word lines that must NEVER be removed ───────
_STRUCTURAL_LABELS: frozenset[str] = frozenset({
    "product", "category", "summary", "features", "specifications",
    "highlights", "source", "description", "overview",
    # section emoji headers (first word after splitting)
    "📦", "📄", "🌐", "📚",
})

# ── Noise patterns — lines matching these are noise ───────────────────────
# Applied ONLY after confirming the line is not a structural label or bullet.
_NOISE_LINE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*\d+\s*$"),                               # lone page numbers
    re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.I),  # "Page 6 of 8"
    re.compile(r"^\s*\d+\s+of\s+\d+\s*$", re.I),             # "6 of 8"
    re.compile(r"©|copyright|all rights reserved", re.I),    # copyright
    re.compile(r"^\s*www\.", re.I),                           # bare URLs
    re.compile(r"^\s*https?://\S+\s*$", re.I),
    re.compile(r"^\s*[\-\|_=]{4,}\s*$"),                     # pure divider lines
    re.compile(r"^\s*confidential\s*$", re.I),
    re.compile(r"^for\s+(professional|healthcare)\s+use\s+only", re.I),
    re.compile(r"^philips\s+(healthcare|medical systems)\s*$", re.I),
    re.compile(r"^\s*[•●○▪]\s*$"),                           # lone bullet char
]

# Minimum word count for a non-structural, non-bullet line to be kept
_MIN_WORDS_CONTENT = 2

# Minimum character length for a cleaned chunk to be kept at all
_MIN_CHUNK_CHARS = 20


def _is_structural(line: str) -> bool:
    """Return True if this line is a section header that must be kept."""
    stripped = line.strip()
    if not stripped:
        return False
    first_word = stripped.split()[0].lower().rstrip(":")
    return first_word in _STRUCTURAL_LABELS


def _is_bullet(line: str) -> bool:
    """Return True if this line is a markdown bullet or numbered list item."""
    stripped = line.strip()
    return bool(re.match(r"^(\s*[-*•]\s+|\s*\d+\.\s+)", stripped))


def _is_noise_line(line: str) -> bool:
    """
    Return True only if this line should be removed.

    Order of precedence (first match wins):
      1. Empty → keep (paragraph separator, collapsed later)
      2. Structural label → KEEP
      3. Bullet item → KEEP
      4. Contains markdown syntax → KEEP
      5. Noise pattern match → noise
      6. Short lines: keep if they start with uppercase (category values,
         product names); drop only pure numbers or lone lowercase tokens
      7. Otherwise → KEEP
    """
    stripped = line.strip()

    # Empty line — keep for paragraph separation
    if not stripped:
        return False

    if _is_structural(stripped):
        return False

    if _is_bullet(stripped):
        return False

    # Lines containing markdown syntax are kept
    if re.search(r"\*\*|__|\||-{3,}|#{1,6}\s|`", stripped):
        return False

    # Check noise patterns
    if any(p.search(stripped) for p in _NOISE_LINE_PATTERNS):
        return True

    # Short lines: distinguish between noise and content values.
    # "Cardiology", "PatientMonitoring", "Unknown" are single-word
    # category values that must be kept.
    words = stripped.split()
    if len(words) < _MIN_WORDS_CONTENT:
        # Pure digit → noise (page number not caught by pattern above)
        if re.match(r"^\d+$", stripped):
            return True
        # Starts with uppercase → likely a proper noun / category value → keep
        if stripped[0].isupper():
            return False
        # All-caps abbreviation → keep
        if stripped.isupper() and len(stripped) >= 2:
            return False
        # Single lowercase word → noise
        return True

    return False


def _clean_lines(text: str) -> str:
    """
    Remove noise lines from text while preserving line structure.

    IMPORTANT: kept lines are re-joined with '\\n', not ' '.
    Joining with ' ' is the root cause of word concatenation bugs
    like "ProductPageWriterTC35Category...".
    """
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        if not _is_noise_line(line):
            kept.append(line.rstrip())   # strip trailing spaces only

    # Collapse runs of 3+ consecutive blank lines to a maximum of 2
    result = "\n".join(kept)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _dedup_sentences(chunks: list[str]) -> list[str]:
    """
    Remove duplicate sentences that appear across multiple chunks.

    Deduplication operates at the LINE level (not word level) to avoid
    accidentally merging content.  A line is a duplicate if its
    lowercased, whitespace-normalised form has been seen in a previous
    chunk.  The FIRST occurrence is kept; subsequent identical lines
    are dropped.

    Structural labels (Category, Features, etc.) are EXEMPT from
    deduplication — they appear in every chunk header and must be kept.

    After deduplication, lines are reassembled with '\\n' to preserve
    paragraph structure.
    """
    global_seen: set[str] = set()
    result: list[str] = []

    for chunk in chunks:
        lines = chunk.splitlines()
        kept_lines: list[str] = []

        for line in lines:
            # Blank lines are always kept (paragraph separators)
            if not line.strip():
                kept_lines.append(line)
                continue

            # Structural labels are always kept regardless of duplication
            if _is_structural(line.strip()):
                kept_lines.append(line)
                continue

            # Bullet items: deduplicate by content only
            key = re.sub(r"\s+", " ", line.strip().lower())
            if key in global_seen:
                continue   # drop duplicate
            global_seen.add(key)
            kept_lines.append(line)

        # Reassemble with newlines — NEVER with spaces
        cleaned = "\n".join(kept_lines).strip()
        # Collapse excess blank lines again after dedup
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        if len(cleaned) >= _MIN_CHUNK_CHARS:
            result.append(cleaned)

    return result


def _is_comparison_context(chunks: list[str]) -> bool:
    """
    Return True if the chunk list represents a comparison context
    (i.e. chunks from two or more distinct products).

    Detection heuristics (any one is sufficient):
      1. More than one '📦 Product' header is present across all chunks.
      2. Any single chunk contains the '\\n\\n---\\n\\n' separator that
         app.py uses to join multiple product chunks before passing to
         context_cleaner.

    When True, cross-chunk deduplication is skipped so that feature and
    description lines from the *second* product are not erroneously dropped
    because they happen to look similar to lines from the first product.
    """
    product_headers = 0
    for chunk in chunks:
        # Count '📦 Product' section headers across all chunks
        product_headers += len(re.findall(r"📦\s*Product", chunk))
        # A single combined-context string already contains both products
        if "\n\n---\n\n" in chunk:
            return True
    return product_headers >= 2


def clean_chunks(chunks: list[str], intent: str = "") -> list[str]:
    """
    Clean a list of formatted context chunks.

    Steps:
      1. Per-chunk noise-line removal (preserves line structure via \\n join).
      2. Cross-chunk line deduplication (structural labels exempt).
         SKIPPED for comparison_query intent or when two-product context is
         detected — dedup across product chunks strips content from the
         second product that is needed for the comparison table.
      3. Drop chunks that are too short after cleaning.

    Parameters
    ----------
    chunks : formatted context strings (output of _format_product_chunk
             or the PDF highlights section in app.py)
    intent : optional intent string; pass "comparison_query" to force-skip
             cross-chunk deduplication

    Returns
    -------
    Cleaned list, order preserved, short/empty chunks dropped.
    """
    if not chunks:
        return []

    # Step 1 — per-chunk noise removal
    step1: list[str] = []
    for chunk in chunks:
        cleaned = _clean_lines(chunk)
        if len(cleaned) >= _MIN_CHUNK_CHARS:
            step1.append(cleaned)

    if not step1:
        return []

    # Step 2 — cross-chunk deduplication
    # Skip for comparison queries: the second product's content looks
    # "duplicate" relative to the first product's content (same feature
    # bullet prefixes, same category label values, similar descriptions).
    # Deduplicating across products strips the data needed for the table.
    skip_dedup = (
        intent == "comparison_query"
        or _is_comparison_context(step1)
    )

    if skip_dedup:
        step2 = step1
        print(
            f"[context_cleaner] input={len(chunks)} | "
            f"after_noise={len(step1)} | "
            f"dedup=SKIPPED (comparison context)"
        )
    else:
        step2 = _dedup_sentences(step1)
        print(
            f"[context_cleaner] input={len(chunks)} | "
            f"after_noise={len(step1)} | "
            f"after_dedup={len(step2)}"
        )

    return step2


def clean_pdf_highlight(text: str) -> str:
    """
    Clean a single PDF highlight string.
    Removes noise lines and collapses whitespace.  Preserves line breaks.
    """
    return _clean_lines(text)
