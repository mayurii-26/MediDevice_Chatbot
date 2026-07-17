"""
search/hybrid_search.py

Combines BM25 (keyword) and FAISS (semantic) retrieval using
Reciprocal Rank Fusion (RRF), producing a single re-ranked list
of product chunks.

Public API
----------
hybrid_product_search(query, top_k=5) -> list[str]
    Returns deduplicated product chunks ranked by hybrid RRF score.

Algorithm
---------
Reciprocal Rank Fusion (Cormack et al., 2009):

    RRF_score(doc) = Σ  1 / (k + rank_i(doc))
                     i

where k=60 (standard constant that dampens the impact of high ranks)
and rank_i is the 1-based rank of the document in result list i.

Documents only in one list contribute via that list alone.
Documents appearing in both lists receive a double bonus — which is the
key hybrid advantage: if BM25 and FAISS independently agree on a chunk,
it rises to the top.

Fallback
--------
If BM25 returns no results (zero-score query), the function returns the
FAISS results unchanged so there is never a quality regression.
If FAISS returns no results, BM25 results are returned.
If both return nothing, returns [].

Per-chunk distance threshold
-----------------------------
FAISS hits are filtered by MAX_CHUNK_DISTANCE before fusion so
irrelevant semantic neighbours do not pollute the ranked list.
The threshold is imported from product_search to keep it in one place.
"""

from search.common import deduplicate, normalise_query

# RRF damping constant — 60 is the standard value from the literature.
_RRF_K = 60

# Maximum number of FAISS candidates to feed into RRF (wider net than top_k
# so fusion can re-rank, but still bounded to avoid noise).
_FAISS_CANDIDATES = 10
_BM25_CANDIDATES  = 10


def _rrf_fusion(
    faiss_chunks: list[str],   # ordered best-first by FAISS distance
    bm25_chunks:  list[str],   # ordered best-first by BM25 score
    top_k: int = 5,
) -> list[str]:
    """
    Merge two ranked lists using Reciprocal Rank Fusion.
    Returns the top_k unique chunks by fused score.
    """
    scores: dict[str, float] = {}

    for rank, chunk in enumerate(faiss_chunks, start=1):
        key = chunk.strip()
        scores[key] = scores.get(key, 0.0) + 1.0 / (_RRF_K + rank)

    for rank, chunk in enumerate(bm25_chunks, start=1):
        key = chunk.strip()
        scores[key] = scores.get(key, 0.0) + 1.0 / (_RRF_K + rank)

    # Sort by descending RRF score, preserving insertion order for ties
    ranked = sorted(scores.items(), key=lambda x: -x[1])

    # Deduplicate while preserving rank order
    seen: set[str] = set()
    result: list[str] = []
    for chunk_text, score in ranked:
        if chunk_text not in seen:
            seen.add(chunk_text)
            result.append(chunk_text)
        if len(result) >= top_k:
            break

    return result


def hybrid_product_search(query: str, top_k: int = 5) -> list[str]:
    """
    Run BM25 + FAISS retrieval and fuse results with RRF.

    Parameters
    ----------
    query  : user query (normalisation applied internally)
    top_k  : number of chunks to return after fusion

    Returns
    -------
    Deduplicated list of chunk strings, ranked by RRF score.
    """
    # ── FAISS retrieval (raw distances, no threshold applied here) ──────────
    faiss_chunks: list[str] = []
    faiss_hits:   list[str] = []   # filtered by per-chunk threshold

    try:
        import numpy as np
        from search.product_search import (
            model, _index, _chunks as product_chunks,
            MAX_CHUNK_DISTANCE,
        )
        from search.common import normalise_query, deduplicate

        q_norm = normalise_query(query)
        embedding = model.encode([q_norm])
        distances, indices = _index.search(
            np.array(embedding, dtype=np.float32), _FAISS_CANDIDATES
        )

        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1 or idx >= len(product_chunks):
                continue
            if float(dist) <= MAX_CHUNK_DISTANCE:
                faiss_chunks.append(product_chunks[idx])

        faiss_hits = deduplicate(faiss_chunks)
        print(
            f"[hybrid_search] FAISS hits={len(faiss_hits)} "
            f"(candidates={_FAISS_CANDIDATES}, threshold={MAX_CHUNK_DISTANCE})"
        )

    except Exception as exc:
        print(f"[hybrid_search] FAISS error: {exc}")

    # ── BM25 retrieval ─────────────────────────────────────────────────────
    bm25_hits: list[str] = []

    try:
        from search.bm25_index import bm25_search
        bm25_results = bm25_search(query, top_k=_BM25_CANDIDATES)
        bm25_hits = [chunk for chunk, _ in bm25_results]
        print(f"[hybrid_search] BM25  hits={len(bm25_hits)}")
    except Exception as exc:
        print(f"[hybrid_search] BM25 error: {exc}")

    # ── Fusion ─────────────────────────────────────────────────────────────
    if not faiss_hits and not bm25_hits:
        return []

    if not bm25_hits:
        # BM25 returned nothing — pure FAISS result
        print("[hybrid_search] BM25 returned no hits — using FAISS only")
        return deduplicate(faiss_hits)[:top_k]

    if not faiss_hits:
        # FAISS returned nothing — pure BM25 result
        print("[hybrid_search] FAISS returned no hits — using BM25 only")
        return deduplicate(bm25_hits)[:top_k]

    fused = _rrf_fusion(faiss_hits, bm25_hits, top_k=top_k)
    print(
        f"[hybrid_search] RRF fusion | faiss={len(faiss_hits)} "
        f"bm25={len(bm25_hits)} → fused={len(fused)}"
    )
    return fused
