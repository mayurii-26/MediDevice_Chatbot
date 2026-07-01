"""
search/product_search.py
FAISS-backed product retrieval: exact name match and semantic search.
Assets loaded ONCE at module level.
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


# ── Strategies ─────────────────────────────────────────────────────────────

def exact_match(query: str, intent: str = "product_query") -> Optional[SearchResult]:
    """
    Scan all chunks for products whose name appears in the normalised query.
    Comparison intent: up to 2 products, 6 chunks total.
    All other intents: first matched product, up to 3 chunks.
    """
    from intent_detector import COMPARISON_QUERY
    q_norm = normalise_query(query)

    matched_by_product: dict[str, list[str]] = {}
    for chunk in _chunks:
        product = extract_product_name(chunk)
        if product and product.lower() in q_norm:
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
    Returns (left, right); right equals query if no split point found.
    """
    q = query.lower().strip()
    # Explicit comparison separators — try in priority order
    for sep in (r"\bvs\.?\b", r"\bversus\b", r"\bdifference between\b"):
        m = re.search(sep, q)
        if m:
            left  = q[:m.start()].strip()
            right = q[m.end():].strip()
            if left and right:
                return left, right
    # "compare X and Y" pattern
    m = re.search(r"\bcompare\b(.+?)\band\b(.+)", q)
    if m:
        left, right = m.group(1).strip(), m.group(2).strip()
        if left and right:
            return left, right
    # Generic "X and Y"
    parts = re.split(r"\band\b", q, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    return q, q


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
        raw = [_chunks[idx] for dist, idx in zip(distances[0], indices[0])
               if idx != -1 and idx < len(_chunks)]
        unique = deduplicate(raw)
        if not unique:
            return [], None, None
        return unique[:3], extract_product_name(unique[0]), extract_category(unique[0])

    left_chunks,  left_product,  left_cat  = _best(left)
    right_chunks, right_product, right_cat = _best(right)

    # Avoid returning the same product for both sides
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
    """Semantic FAISS search. Returns None if best distance exceeds threshold."""
    q_norm = normalise_query(query)
    embedding = model.encode([q_norm])
    distances, indices = _index.search(np.array(embedding, dtype=np.float32), top_k)

    best_dist = float(distances[0][0]) if len(distances[0]) else 999.0
    if best_dist > FAISS_STRONG_THRESHOLD:
        return None

    raw: list[str] = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx != -1 and idx < len(_chunks):
            raw.append(_chunks[idx])

    unique = deduplicate(raw)
    if not unique:
        return None

    top = unique[0]
    return SearchResult(
        chunks=unique,
        source="faiss",
        matched_product=extract_product_name(top),
        matched_category=extract_category(top) or detect_category_from_query(query),
        confidence=faiss_confidence(best_dist),
    )
