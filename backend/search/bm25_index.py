"""
search/bm25_index.py

BM25 keyword index over product chunks.

Built once at module load from the same _chunks list that the FAISS index uses.
Provides:
    bm25_search(query, top_k) -> list[tuple[str, float]]
        Returns (chunk_text, normalised_score) pairs, best-first.
        Scores are normalised to [0, 1] so they are comparable with
        FAISS-derived confidence values used in the RRF fusion step.

Design notes:
- Tokenises by lowercasing and splitting on non-alphanumeric characters,
  which handles "TC50", "TC 50", "TC-50" equally after query normalisation.
- Stop-word list is deliberately minimal — medical model numbers and
  short tokens ("TC", "AED", "EV") must NOT be removed.
- Safe to call even when the corpus is empty (returns []).
"""

import re
from typing import Optional

# rank_bm25 is a pure-Python BM25 implementation (numpy-backed).
# Installed via: pip install rank-bm25==0.2.2
from rank_bm25 import BM25Okapi


# ── Minimal stop-word list ─────────────────────────────────────────────────
# Keeps medically relevant short tokens while removing pure noise.
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were",
    "in", "on", "at", "to", "for", "of", "and", "or",
    "what", "how", "does", "do", "tell", "me", "about",
    "can", "you", "give", "please", "i", "want", "need",
})


def _tokenise(text: str) -> list[str]:
    """
    Lowercase, split on non-alphanumeric characters, drop stop-words
    and single-character tokens.  Preserves numeric tokens (model numbers).
    """
    tokens = re.split(r"[^a-z0-9]+", text.lower())
    return [t for t in tokens if t and len(t) > 1 and t not in _STOP_WORDS]


# ── Index (built at module import) ────────────────────────────────────────

_bm25:   Optional[BM25Okapi] = None
_chunks: list[str]           = []


def _build_index(chunks: list[str]) -> None:
    """Tokenise chunks and construct the BM25Okapi index."""
    global _bm25, _chunks
    _chunks = chunks
    if not chunks:
        print("[bm25_index] No chunks — BM25 index not built.")
        return
    corpus = [_tokenise(c) for c in chunks]
    _bm25 = BM25Okapi(corpus)
    print(f"[bm25_index] BM25 index built | chunks={len(chunks)}")


def _lazy_load() -> None:
    """
    Load the shared _chunks from product_search on first use.
    Avoids a circular import at module level.
    """
    global _bm25, _chunks
    if _bm25 is not None or _chunks:
        return
    try:
        from search.product_search import _chunks as product_chunks
        _build_index(product_chunks)
    except Exception as exc:
        print(f"[bm25_index] Failed to load product chunks: {exc}")


# ── Public API ─────────────────────────────────────────────────────────────

def bm25_search(query: str, top_k: int = 5) -> list[tuple[str, float]]:
    """
    Keyword search over product chunks using BM25Okapi.

    Parameters
    ----------
    query  : raw user query (normalisation applied internally)
    top_k  : number of results to return

    Returns
    -------
    List of (chunk_text, normalised_score) tuples, sorted descending by score.
    normalised_score is in [0, 1]:  1.0 = best possible BM25 score in corpus.
    Returns [] if the index is empty or all scores are zero.
    """
    _lazy_load()

    if _bm25 is None or not _chunks:
        return []

    # Apply the same query normalisation used by FAISS to keep tokens consistent
    from search.common import normalise_query
    q_norm = normalise_query(query)
    tokens = _tokenise(q_norm)

    if not tokens:
        return []

    scores = _bm25.get_scores(tokens)

    max_score = float(scores.max()) if len(scores) else 0.0
    if max_score <= 0.0:
        return []                 # No BM25 signal — all chunks score 0

    # Normalise to [0, 1]
    norm_scores = scores / max_score

    # Collect top_k indices sorted by descending score
    # argsort is ascending, so take from the tail
    import numpy as np
    top_indices = np.argsort(norm_scores)[::-1][:top_k]

    results: list[tuple[str, float]] = []
    for idx in top_indices:
        score = float(norm_scores[idx])
        if score <= 0.0:
            break               # remaining entries have zero BM25 signal
        results.append((_chunks[idx], score))

    print(
        f"[bm25_index] QUERY={q_norm!r} | "
        f"tokens={tokens} | hits={len(results)} | "
        f"top_score={results[0][1]:.4f}" if results else
        f"[bm25_index] QUERY={q_norm!r} | tokens={tokens} | hits=0"
    )
    return results
