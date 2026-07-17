"""
search/pdf_search.py

PDF FAISS retrieval with optional product-scoped filtering and
per-chunk distance threshold.

Index loaded lazily — absent until build_pdf_index.py has run.

Changes vs previous version
----------------------------
- Added MAX_PDF_DISTANCE constant (per-chunk L2 threshold = 1.4).
  Previously the search returned all top_k candidates regardless of
  how far they were from the query embedding.  Now each chunk's L2
  distance must be <= MAX_PDF_DISTANCE to be included.  This prevents
  injecting irrelevant PDF sections into the Gemini context when the
  query has a weak semantic match to a document.
- When fewer than top_k candidates survive thresholding the function
  returns only the passing ones rather than padding with irrelevant hits.
"""
import os
import pickle
import faiss
import numpy as np
from typing import Optional

from search.common import normalise_query

# ── Per-chunk distance threshold ────────────────────────────────────────────
# L2 distances for PDF chunk embeddings.  Chunks with individual distance
# greater than this value are excluded even if they fall within top_k.
MAX_PDF_DISTANCE: float = 1.4

# ── Paths ──────────────────────────────────────────────────────────────────
_BASE          = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_INDEX_PATH    = os.path.join(_BASE, "pdf_processing", "faiss", "pdf.index")
_METADATA_PATH = os.path.join(_BASE, "pdf_processing", "metadata", "pdf_metadata.pkl")

_pdf_index:    Optional[faiss.Index] = None
_pdf_metadata: list[dict] = []


def _load() -> None:
    global _pdf_index, _pdf_metadata
    if not os.path.exists(_INDEX_PATH) or not os.path.exists(_METADATA_PATH):
        print("[pdf_search] Index files not found — PDF search disabled.")
        return
    try:
        _pdf_index = faiss.read_index(_INDEX_PATH)
        with open(_METADATA_PATH, "rb") as f:
            _pdf_metadata = pickle.load(f)
        print(f"[pdf_search] Loaded vectors={_pdf_index.ntotal} | chunks={len(_pdf_metadata)}")
    except Exception as e:
        print(f"[pdf_search] PDF index load failed (non-fatal): {e}")

_load()


def _product_match(chunk_product: str, matched_product: str) -> bool:
    """
    Fuzzy product name match: true if either name is a substring of the other.
    Handles cases where PDF metadata stores longer names than FAISS
    (e.g. 'PageWriter TC50 Cardiology' vs matched 'PageWriter TC50').
    """
    a = chunk_product.lower()
    b = matched_product.lower()
    return a == b or a.startswith(b) or b.startswith(a) or (b in a) or (a in b)


def search(query: str, top_k: int = 3, matched_product: Optional[str] = None) -> list[dict]:
    """
    Return up to top_k PDF metadata dicts ranked by semantic similarity.

    If matched_product is given, restricts candidates to chunks whose
    product_name fuzzy-matches (substring). Falls back to full-index
    search when matched_product is None or no candidates are found.

    Per-chunk filtering
    -------------------
    Each candidate chunk is included only if its L2 distance to the
    query embedding is <= MAX_PDF_DISTANCE.  Chunks that exceed this
    threshold are silently dropped.  This prevents weakly-related PDF
    sections from being injected into the Gemini prompt.
    """
    if _pdf_index is None or not _pdf_metadata:
        print(f"[pdf_search] Candidate chunks=0 (index not loaded)")
        return []

    # Import model from product_search to avoid loading a second instance
    from search.product_search import model
    q_vec = np.array(model.encode([normalise_query(query)]), dtype=np.float32)

    total_chunks = len(_pdf_metadata)

    if matched_product:
        candidates = [
            (i, m) for i, m in enumerate(_pdf_metadata)
            if _product_match(m.get("product_name", ""), matched_product)
        ]
        print(f"[pdf_search] Candidate chunks={len(candidates)} / {total_chunks} (filtered by product='{matched_product}')")
    else:
        candidates = list(enumerate(_pdf_metadata))
        print(f"[pdf_search] Candidate chunks={len(candidates)} (no product filter)")

    if not candidates:
        print(f"[pdf_search] No candidates for product='{matched_product}' — returning empty")
        return []

    if len(candidates) <= top_k:
        # Small candidate pool — compute distances, apply threshold, return
        idxs = [i for i, _ in candidates]
        vecs = np.zeros((len(idxs), _pdf_index.d), dtype=np.float32)
        for row, gi in enumerate(idxs):
            _pdf_index.reconstruct(gi, vecs[row])
        dists = np.sum((vecs - q_vec) ** 2, axis=1)

        results = []
        for row, (_, meta) in enumerate(candidates):
            if float(dists[row]) <= MAX_PDF_DISTANCE:
                results.append(meta)

        print(
            f"[pdf_search] Filtered chunks={len(candidates)} | "
            f"Passed threshold={len(results)} | Returned chunks={len(results)}"
        )
        return results

    # Larger candidate pool — score all, sort, threshold, take top_k
    idxs = [i for i, _ in candidates]
    vecs = np.zeros((len(idxs), _pdf_index.d), dtype=np.float32)
    for row, gi in enumerate(idxs):
        _pdf_index.reconstruct(gi, vecs[row])

    dists    = np.sum((vecs - q_vec) ** 2, axis=1)
    top_rows = np.argsort(dists)[:top_k]

    results = []
    for r in top_rows:
        dist = float(dists[r])
        if dist <= MAX_PDF_DISTANCE:
            results.append(candidates[r][1])

    print(
        f"[pdf_search] Filtered chunks={len(candidates)} | "
        f"Top-k considered={len(top_rows)} | "
        f"Passed threshold={len(results)} | Returned chunks={len(results)}"
    )
    return results
