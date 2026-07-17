"""
dynamic_search/wikipedia_service.py

Wikipedia REST API client with in-memory TTL cache.

Responsibilities
----------------
- Fetch plain-text summaries for medical concepts via the Wikipedia
  REST summary endpoint (no authentication required, JSON response).
- Clean the returned text (strip reference markers, normalise whitespace).
- Cache every successful response in memory for 1 hour (TTL) with a
  maximum of 200 entries (LRU eviction when full).

Public API
----------
fetch(topic: str) -> WikipediaResult
    Look up a topic on Wikipedia.
    Returns a WikipediaResult; check .found before using .summary.

WikipediaResult
    .title   : str   — Wikipedia page title as returned by the API
    .summary : str   — cleaned plain-text extract (≤ 600 chars)
    .url     : str   — canonical Wikipedia URL
    .found   : bool  — False when no article was found or fetch failed

Design constraints
------------------
- Uses only the standard library (urllib) + json — no new dependencies.
- Never raises: all exceptions are caught and result in found=False.
- All network calls have a 5-second timeout to avoid blocking the
  response pipeline.
- Cache key is the lowercased, stripped topic string.
"""

from __future__ import annotations

import re
import json
import time
from dataclasses import dataclass, field
from urllib.request import urlopen, Request
from urllib.parse import quote
from urllib.error import URLError
from typing import Optional


# ── Result type ────────────────────────────────────────────────────────────

@dataclass
class WikipediaResult:
    title:   str
    summary: str
    url:     str
    found:   bool = True


_NOT_FOUND = WikipediaResult(title="", summary="", url="", found=False)


# ── Cache ──────────────────────────────────────────────────────────────────

_TTL_SECONDS = 3600          # 1 hour
_MAX_ENTRIES = 200           # LRU eviction after this

# {cache_key: (timestamp, WikipediaResult)}
_cache: dict[str, tuple[float, WikipediaResult]] = {}


def _cache_get(key: str) -> Optional[WikipediaResult]:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, result = entry
    if time.time() - ts > _TTL_SECONDS:
        del _cache[key]
        return None
    # Refresh position (LRU: re-insert at end)
    _cache[key] = (ts, result)
    return result


def _cache_put(key: str, result: WikipediaResult) -> None:
    if len(_cache) >= _MAX_ENTRIES:
        # Evict the oldest entry
        oldest_key = next(iter(_cache))
        del _cache[oldest_key]
    _cache[key] = (time.time(), result)


# ── Network helpers ────────────────────────────────────────────────────────

_TIMEOUT = 5          # seconds
_USER_AGENT = "MediDevice-Chatbot/1.0 (medical device assistant; fallback search)"

_SUMMARY_URL  = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_SEARCH_URL   = "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&srlimit=3&format=json"


def _http_get(url: str) -> Optional[dict]:
    """GET url, return parsed JSON dict or None on any error."""
    req = Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
            return json.loads(raw)
    except (URLError, json.JSONDecodeError, Exception):
        return None


# ── Text cleaning ──────────────────────────────────────────────────────────

# Reference-style markers like [1], [note 3]
_REF_RE     = re.compile(r"\[\d+\]|\[note[^\]]*\]|\[citation[^\]]*\]", re.I)
# Excess whitespace
_SPACE_RE   = re.compile(r"[ \t]{2,}")
# Strip trailing "See also…" / "References" fragments
_TRAILER_RE = re.compile(r"\s*(See also|References|External links|Further reading)\s*$", re.I)

_MAX_SUMMARY_CHARS = 600


def _clean(text: str) -> str:
    """Remove reference markers and normalise whitespace."""
    text = _REF_RE.sub("", text)
    text = _TRAILER_RE.sub("", text)
    text = _SPACE_RE.sub(" ", text)
    text = text.strip()
    # Hard-cap length — Wikipedia extracts can be very long
    if len(text) > _MAX_SUMMARY_CHARS:
        # Truncate at the last sentence boundary before the limit
        cut = text[:_MAX_SUMMARY_CHARS]
        last_dot = cut.rfind(". ")
        text = cut[:last_dot + 1] if last_dot > 100 else cut
    return text


# ── Core fetch logic ───────────────────────────────────────────────────────

def _fetch_summary(title: str) -> Optional[WikipediaResult]:
    """
    Fetch the Wikipedia REST summary for an exact page title.
    Returns None on 404 / network failure.
    """
    url = _SUMMARY_URL.format(title=quote(title, safe=""))
    data = _http_get(url)
    if not data:
        return None

    # REST API returns {"type": "https://mediawiki.org/wiki/HyperSwitch/errors/not_found"}
    # for missing pages.
    if data.get("type", "").endswith("not_found"):
        return None

    extract = data.get("extract", "").strip()
    if not extract:
        return None

    page_title = data.get("title", title)
    canonical  = data.get("content_urls", {}).get("desktop", {}).get("page", "")
    if not canonical:
        canonical = f"https://en.wikipedia.org/wiki/{quote(page_title, safe='')}"

    return WikipediaResult(
        title=page_title,
        summary=_clean(extract),
        url=canonical,
        found=True,
    )


def _search_and_fetch(topic: str) -> Optional[WikipediaResult]:
    """
    Use the MediaWiki search API to find the best matching article title,
    then fetch its summary.  Falls back gracefully if search returns nothing.
    """
    search_url = _SEARCH_URL.format(q=quote(topic, safe=""))
    data = _http_get(search_url)
    if not data:
        return None

    hits = data.get("query", {}).get("search", [])
    if not hits:
        return None

    # Try the top 3 search hits; return the first that has a usable extract
    for hit in hits[:3]:
        page_title = hit.get("title", "")
        if not page_title:
            continue
        result = _fetch_summary(page_title)
        if result:
            return result

    return None


# ── Public API ─────────────────────────────────────────────────────────────

def fetch(topic: str) -> WikipediaResult:
    """
    Look up a medical topic on Wikipedia.

    Strategy:
      1. Check in-memory TTL cache.
      2. Try exact-title summary endpoint.
      3. If not found, run MediaWiki search and fetch the best result.
      4. Cache the result (even found=False, to avoid re-fetching 404s).

    Parameters
    ----------
    topic : search string (a medical concept, e.g. "electrocardiogram")

    Returns
    -------
    WikipediaResult with .found=True on success, .found=False on failure.
    Never raises.
    """
    key = topic.lower().strip()
    cached = _cache_get(key)
    if cached is not None:
        source = "HIT" if cached.found else "HIT(miss)"
        print(f"[wikipedia] CACHE {source} | topic={topic!r}")
        return cached

    print(f"[wikipedia] FETCH | topic={topic!r}")
    result: Optional[WikipediaResult] = None

    try:
        # Step 1: exact title lookup
        result = _fetch_summary(topic)

        # Step 2: fallback to search
        if result is None:
            result = _search_and_fetch(topic)

    except Exception as exc:
        print(f"[wikipedia] FETCH ERROR | topic={topic!r} | error={exc}")
        result = None

    final = result if result is not None else _NOT_FOUND
    _cache_put(key, final)

    status = f"title={final.title!r} | chars={len(final.summary)}" if final.found else "not_found"
    print(f"[wikipedia] RESULT | topic={topic!r} | {status}")
    return final
