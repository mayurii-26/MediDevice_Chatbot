"""
search/product_search.py

FAISS-backed product retrieval: exact name match, hybrid BM25+FAISS search,
and comparison search.

Assets loaded ONCE at module level.

Changes vs previous version
----------------------------
- Added MAX_CHUNK_DISTANCE constant (per-chunk L2 threshold).
  Chunks whose individual FAISS distance exceeds this value are discarded
  before being returned or passed to RRF fusion.
- faiss_search() now delegates to hybrid_product_search() from
  search/hybrid_search.py, combining BM25 and FAISS scores via RRF.
  The external signature is unchanged.
- exact_match() and comparison_search() are unchanged.
"""
import os
import re
import pickle
import faiss
import numpy as np
from typing import Optional
from sentence_transformers import SentenceTransformer

from search.common import (
    SearchResult, normalise_query,
    extract_product_name, extract_category, detect_category_from_query,
    deduplicate, faiss_confidence, FAISS_STRONG_THRESHOLD,
)

# ── Assets ─────────────────────────────────────────────────────────────────
_BASE      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VECTOR_DB = os.path.join(_BASE, "vector_db")

model  = SentenceTransformer("all-MiniLM-L6-v2")
_index = faiss.read_index(os.path.join(_VECTOR_DB, "faiss_index.bin"))

with open(os.path.join(_VECTOR_DB, "product_chunks.pkl"), "rb") as _f:
    _chunks: list[str] = pickle.load(_f)

print(f"[product_search] Loaded {len(_chunks)} chunks from FAISS index.")

# ── Per-chunk distance threshold ────────────────────────────────────────────
# Individual FAISS distances (L2) are checked per-chunk, not just for the
# top-1 result.  Chunks with distance > MAX_CHUNK_DISTANCE are discarded
# before being included in results or passed to RRF fusion.
#
# This is deliberately set slightly looser than FAISS_STRONG_THRESHOLD (1.2)
# so that slightly weaker semantic matches are still considered as BM25
# candidates during fusion — but clearly irrelevant chunks (distance > 1.4)
# are excluded outright.
MAX_CHUNK_DISTANCE: float = 1.4


# ── Strategies ─────────────────────────────────────────────────────────────

def exact_match(query: str, intent: str = "product_query") -> Optional[SearchResult]:
    """
    Scan all chunks for products whose name appears in the normalised query.
    Comparison intent: up to 2 products, 6 chunks total.
    All other intents: first matched product, up to 3 chunks.

    FIX (2026-07-03): For comparison queries, also run _split_comparison
    and try to find each side independently when the full product name is not
    present in the raw query (e.g. "TC70" instead of "PageWriter TC70").
    """
    from intent_detector import COMPARISON_QUERY
    q_norm = normalise_query(query)

    matched_by_product: dict[str, list[str]] = {}
    for chunk in _chunks:
        product = extract_product_name(chunk)
        if product and product.lower() in q_norm:
            matched_by_product.setdefault(product, []).append(chunk)

    # For comparison: if we found fewer than 2 products, try split-side lookup
    if intent == COMPARISON_QUERY and len(matched_by_product) < 2:
        left, right = _split_comparison(query)
        for side in (left, right):
            side_norm = normalise_query(side)
            for chunk in _chunks:
                product = extract_product_name(chunk)
                if product and product not in matched_by_product:
                    p_low = product.lower()
                    if p_low in side_norm or side_norm in p_low:
                        matched_by_product.setdefault(product, []).append(chunk)

    if not matched_by_product:
        return None

    if intent == COMPARISON_QUERY:
        products_found = list(matched_by_product.keys())[:2]
        all_chunks: list[str] = []
        for p in products_found:
            all_chunks.extend(matched_by_product[p][:3])
        all_chunks = deduplicate(all_chunks)
        first = products_found[0]
        print(f"[product_search] EXACT MATCH (comparison) | products={products_found}")
        return SearchResult(
            chunks=all_chunks[:6],
            source="faiss",
            matched_product=" vs ".join(products_found),
            matched_category=extract_category(matched_by_product[first][0]) or detect_category_from_query(query),
            confidence=1.0,
        )

    best = next(iter(matched_by_product))
    chunks = deduplicate(matched_by_product[best])
    return SearchResult(
        chunks=chunks[:3],
        source="faiss",
        matched_product=best,
        matched_category=extract_category(chunks[0]) or detect_category_from_query(query),
        confidence=1.0,
    )


def _split_comparison(query: str) -> tuple[str, str]:
    """
    Split a comparison query into two target strings.

    FIX (2026-07-03): The previous implementation left the full "compare X"
    prefix on the left side, so left="compare pagewriter tc50" and
    right="tc70".  The FAISS lookup for "compare pagewriter tc50" matched
    TC50 correctly, but the lookup for bare "tc70" failed because there is
    no vector close to that single token.

    New behaviour:
      1. Strip leading verbs ("compare", "difference between") from both halves.
      2. If the right side is a SHORT fragment (≤ 10 chars, no spaces) and the
         left side contains a brand prefix (e.g. "pagewriter"), prepend the
         brand prefix to the right side so FAISS has a complete name to match.

    Examples:
      "compare pagewriter tc50 and tc70"
        → left="pagewriter tc50", right="pagewriter tc70"
      "tc50 vs tc70"
        → left="tc50", right="tc70"
      "compare heartstart frx and hs1"
        → left="heartstart frx", right="heartstart hs1"
    """
    q = query.lower().strip()

    # Remove common leading verbs
    q = re.sub(r"^(compare|comparison of|difference between|differences between)\s+", "", q)

    # Try explicit separators
    for sep in (r"\bvs\.?\b", r"\bversus\b"):
        m = re.search(sep, q)
        if m:
            left  = q[:m.start()].strip()
            right = q[m.end():].strip()
            if left and right:
                return _enrich_comparison_sides(left, right)

    # "X and Y" pattern
    m = re.search(r"^(.+?)\band\b(.+)$", q)
    if m:
        left, right = m.group(1).strip(), m.group(2).strip()
        if left and right:
            return _enrich_comparison_sides(left, right)

    return q, q


def _enrich_comparison_sides(left: str, right: str) -> tuple[str, str]:
    """
    If one side is a bare model number (short, no spaces) and the other side
    has a brand prefix, copy the brand prefix to the short side.

    e.g. left="pagewriter tc50", right="tc70"
      → right="pagewriter tc70"
    """
    def _brand_prefix(s: str) -> str:
        """Return everything up to the last space-separated token."""
        parts = s.strip().split()
        if len(parts) >= 2:
            return " ".join(parts[:-1])
        return ""

    def _is_bare_model(s: str) -> bool:
        """True if s looks like a bare model number (no spaces, ≤ 12 chars)."""
        return " " not in s.strip() and len(s.strip()) <= 12

    l = left.strip()
    r = right.strip()

    if _is_bare_model(r) and not _is_bare_model(l):
        prefix = _brand_prefix(l)
        if prefix:
            r = f"{prefix} {r}"
    elif _is_bare_model(l) and not _is_bare_model(r):
        prefix = _brand_prefix(r)
        if prefix:
            l = f"{prefix} {l}"

    return l, r


def comparison_search(query: str) -> Optional[SearchResult]:
    """
    For comparison queries where exact_match finds nothing:
    split the query into two halves, run independent FAISS lookups for each,
    and return up to 3 chunks per side (6 total).
    Returns None if neither side yields a confident hit.
    """
    left, right = _split_comparison(query)

    def _best(q: str) -> tuple[list[str], Optional[str], Optional[str]]:
        q_norm = normalise_query(q)
        emb = model.encode([q_norm])
        distances, indices = _index.search(np.array(emb, dtype=np.float32), 3)
        best_dist = float(distances[0][0]) if len(distances[0]) else 999.0
        if best_dist > FAISS_STRONG_THRESHOLD:
            return [], None, None
        raw = [
            _chunks[idx]
            for dist, idx in zip(distances[0], indices[0])
            if idx != -1 and idx < len(_chunks) and float(dist) <= MAX_CHUNK_DISTANCE
        ]
        unique = deduplicate(raw)
        if not unique:
            return [], None, None
        return unique[:3], extract_product_name(unique[0]), extract_category(unique[0])

    left_chunks,  left_product,  left_cat  = _best(left)
    right_chunks, right_product, right_cat = _best(right)

    if left_product and left_product == right_product:
        right_chunks, right_product, right_cat = [], None, None

    all_chunks = deduplicate(left_chunks + right_chunks)
    if not all_chunks:
        return None

    products = " vs ".join(p for p in [left_product, right_product] if p)
    category  = left_cat or right_cat or detect_category_from_query(query)

    print(f"[product_search] COMPARISON SPLIT | left='{left_product}' | right='{right_product}'")
    return SearchResult(
        chunks=all_chunks[:6],
        source="faiss",
        matched_product=products or None,
        matched_category=category,
        confidence=0.9,
    )


def faiss_search(query: str, top_k: int = 3) -> Optional[SearchResult]:
    """
    Hybrid BM25 + FAISS semantic search with RRF fusion.

    Delegates to hybrid_product_search() which:
      1. Runs FAISS, filters each result by MAX_CHUNK_DISTANCE.
      2. Runs BM25Okapi keyword search.
      3. Fuses both result lists via Reciprocal Rank Fusion (k=60).

    Returns None if no chunks pass the relevance threshold (mirrors the
    old behaviour of returning None when best_dist > FAISS_STRONG_THRESHOLD).

    External signature unchanged — existing callers (orchestrator.py) work
    without modification.
    """
    try:
        from search.hybrid_search import hybrid_product_search
        fused = hybrid_product_search(query, top_k=top_k)
    except Exception as exc:
        print(f"[product_search] hybrid_search failed, falling back to pure FAISS: {exc}")
        fused = _pure_faiss_fallback(query, top_k)

    if not fused:
        return None

    top = fused[0]
    # Compute a representative FAISS confidence from the top chunk's distance
    q_norm   = normalise_query(query)
    emb      = model.encode([q_norm])
    dists, _ = _index.search(np.array(emb, dtype=np.float32), 1)
    best_dist = float(dists[0][0]) if len(dists[0]) else FAISS_STRONG_THRESHOLD

    return SearchResult(
        chunks=fused,
        source="faiss",
        matched_product=extract_product_name(top),
        matched_category=extract_category(top) or detect_category_from_query(query),
        confidence=faiss_confidence(best_dist),
    )


def _pure_faiss_fallback(query: str, top_k: int = 3) -> list[str]:
    """
    Bare FAISS search used only when hybrid_search raises an exception.
    Applies per-chunk MAX_CHUNK_DISTANCE filtering.
    """
    q_norm = normalise_query(query)
    embedding = model.encode([q_norm])
    distances, indices = _index.search(np.array(embedding, dtype=np.float32), top_k)

    best_dist = float(distances[0][0]) if len(distances[0]) else 999.0
    if best_dist > FAISS_STRONG_THRESHOLD:
        return []

    raw: list[str] = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx != -1 and idx < len(_chunks) and float(dist) <= MAX_CHUNK_DISTANCE:
            raw.append(_chunks[idx])

    return deduplicate(raw)
