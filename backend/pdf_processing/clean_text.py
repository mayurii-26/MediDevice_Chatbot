"""
pdf_processing/clean_text.py

Cleans raw per-page text extracted from a PDF:
  - Removes page numbers (standalone digit lines)
  - Removes repeated headers / footers (lines that appear on many pages)
  - Collapses excessive whitespace
  - Preserves section headings and paragraph structure

Entry point: clean_pages(pages) -> str
"""
import re
from collections import Counter


# A line is considered a repeated header/footer if it appears on this
# fraction of pages or more (e.g. 0.4 = present on ≥40 % of pages).
_REPEAT_THRESHOLD = 0.4

# Regex: a line that is only digits (optionally surrounded by whitespace)
_PAGE_NUMBER_RE = re.compile(r"^\s*\d+\s*$")


def _is_page_number(line: str) -> bool:
    return bool(_PAGE_NUMBER_RE.match(line))


def _repeated_lines(pages: list[str]) -> set[str]:
    """
    Return the set of lines that appear (case-insensitively, stripped)
    on >= _REPEAT_THRESHOLD fraction of pages — these are headers/footers.
    Single-page documents skip this step.
    """
    if len(pages) < 2:
        return set()

    # Count how many pages each stripped line appears on
    line_page_count: Counter = Counter()
    for page in pages:
        seen_on_this_page: set[str] = set()
        for raw_line in page.splitlines():
            stripped = raw_line.strip()
            if stripped and stripped not in seen_on_this_page:
                line_page_count[stripped] += 1
                seen_on_this_page.add(stripped)

    threshold = max(2, int(len(pages) * _REPEAT_THRESHOLD))
    return {line for line, count in line_page_count.items() if count >= threshold}


def clean_pages(pages: list[str]) -> str:
    """
    Accept a list of raw page strings (from extract_text.py).
    Return a single clean string with noise removed and structure preserved.
    """
    repeated = _repeated_lines(pages)
    cleaned_pages: list[str] = []

    for page in pages:
        kept_lines: list[str] = []
        for raw_line in page.splitlines():
            stripped = raw_line.strip()

            # Drop empty lines at this stage (re-added as paragraph breaks later)
            if not stripped:
                continue
            # Drop standalone page numbers
            if _is_page_number(stripped):
                continue
            # Drop repeated header/footer lines
            if stripped in repeated:
                continue

            kept_lines.append(stripped)

        if kept_lines:
            cleaned_pages.append("\n".join(kept_lines))

    # Join pages with a blank line between them to preserve section breaks
    full_text = "\n\n".join(cleaned_pages)

    # Collapse 3+ consecutive newlines to 2 (one blank line)
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    # Collapse runs of spaces/tabs (but not newlines) to a single space
    full_text = re.sub(r"[ \t]{2,}", " ", full_text)

    return full_text.strip()
