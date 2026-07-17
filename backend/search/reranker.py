"""
search/reranker.py

CrossEncoder reranker — second-pass relevance scoring after BM25+FAISS retrieval.

Model
-----
cross-encoder/ms-marco-MiniLM-L-6-v2
    - 22 M parameters, fast CPU inference (~5–15 ms per chunk on modern CPU)
    - Trained on MS MARCO passage ranking (general retrieval; transfers well
      to medical device Q&A)
    - Downloaded once by HuggingFace Hub, cached in ~/.cache/huggingface

Design
------
- Lazy-loaded: the CrossEncoder is instantiated on the FIRST call to rerank().
  App startup is not delayed. If the model download fails (offline/CI) the
  function falls back gracefully to the original chunk order.
- Thread-safe: Python GIL makes the single-model singleton safe for
  concurrent FastAPI requests.
- top_k=5: select the 5 best-scoring chunks from the combined candidate pool.

Pipeline position
-----------------
  BM25 + FAISS retrieval (up to 10+10 candidates)
         │
      rerank(query, chunks, top_k=5)   ← this module
         │
      Top-5 chunks → context builder → Gemini
"""

from __future__ import annotations

from typing import Optional

# ── Singleton ──────────────────────────────────────────────────────────────
_cross_encoder: Optional[object] = None   # sentence_transformers.CrossEncoder
_load_attempted: bool = False
_MODEL_ID = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Maximum chunks accepted as input to the reranker (guards against runaway
# candidate lists that would make inference slow).
_MAX_INPUT_CHUNKS = 20

# Default number of top chunks to return.
DEFAULT_TOP_K = 5


def _load_model() -> Optional[object]:
    """
    Load the CrossEncoder model exactly once.
    Returns the model or None if loading fails.
    """
    global _cross_encoder, _load_attempted
    if _load_attempted:
        return _cross_encoder

    _load_attempted = True
    try:
        from sentence_transformers import CrossEncoder
        print(f"[reranker] Loading CrossEncoder model: {_MODEL_ID}")
        _cross_encoder = CrossEncoder(_MODEL_ID, max_length=512)
        print(f"[reranker] CrossEncoder loaded successfully.")
    except Exception as exc:
        print(f"[reranker] CrossEncoder load FAILED (non-fatal, falling back): {exc}")
        _cross_encoder = None

    return _cross_encoder


# ── Public API ─────────────────────────────────────────────────────────────

def rerank(
    query: str,
    chunks: list[str],
    top_k: int = DEFAULT_TOP_K,
) -> list[str]:
    """
    Score each (query, chunk) pair with the CrossEncoder and return the
    top_k chunks sorted by descending relevance score.

    Parameters
    ----------
    query  : the ORIGINAL user query (not the rewritten canonical).
             Cross-encoders are trained on natural language questions;
             conversational phrasing is fine and sometimes better.
    chunks : candidate chunks from BM25+FAISS retrieval.
    top_k  : number of top chunks to return (default 5).

    Returns
    -------
    List of chunk strings, best-first, length <= min(top_k, len(chunks)).

    Fallback
    --------
    If the model is unavailable or prediction fails, returns the first
    top_k chunks in their original order unchanged.
    """
    if not chunks:
        return []

    # Cap input to avoid slow inference on large candidate pools
    candidates = chunks[:_MAX_INPUT_CHUNKS]
    effective_top_k = min(top_k, len(candidates))

    model = _load_model()
    if model is None:
        print(f"[reranker] Model unavailable — returning top-{effective_top_k} unranked.")
        return candidates[:effective_top_k]

    try:
        # Build (query, passage) pairs for the cross-encoder
        pairs = [(query, chunk) for chunk in candidates]

        scores: list[float] = model.predict(pairs, show_progress_bar=False).tolist()

        # Sort by score descending, preserve original chunk text
        ranked = sorted(
            zip(scores, candidates),
            key=lambda x: x[0],
            reverse=True,
        )

        top_chunks = [chunk for _, chunk in ranked[:effective_top_k]]

        # Log top-3 scores for observability
        score_preview = ", ".join(f"{s:.3f}" for s, _ in ranked[:3])
        print(
            f"[reranker] input={len(candidates)} | "
            f"top_k={effective_top_k} | "
            f"top_3_scores=[{score_preview}]"
        )

        return top_chunks

    except Exception as exc:
        print(f"[reranker] Prediction failed (non-fatal): {exc}")
        return candidates[:effective_top_k]
