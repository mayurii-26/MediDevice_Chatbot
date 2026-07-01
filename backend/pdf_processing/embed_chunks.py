"""
pdf_processing/embed_chunks.py

Generates sentence-transformer embeddings for PDF chunks and maintains
a dedicated FAISS index — completely separate from the product index.

Artifacts written:
    backend/pdf_processing/faiss/pdf.index
    backend/pdf_processing/metadata/pdf_metadata.pkl

Each metadata entry (mirrors chunk dict from chunk_text.py):
    {
        "chunk_id":      str,
        "product_name":  str,
        "document_name": str,
        "page_number":   int,
        "chunk_text":    str,
    }

Public API
----------
build_pdf_index(chunks)          — build from scratch, overwrite existing
add_to_pdf_index(chunks)         — append to existing index (or create if absent)
"""

import os
import pickle
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# ── Paths ──────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH    = os.path.join(_BASE, "faiss", "pdf.index")
METADATA_PATH = os.path.join(_BASE, "metadata", "pdf_metadata.pkl")

os.makedirs(os.path.dirname(INDEX_PATH),    exist_ok=True)
os.makedirs(os.path.dirname(METADATA_PATH), exist_ok=True)

# Same model as the product index — reused from search.py at runtime
_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model() -> SentenceTransformer:
    """Reuse the already-loaded model from search.py if available."""
    try:
        from search import _model
        return _model
    except Exception:
        return SentenceTransformer(_MODEL_NAME)


def _embed(texts: list[str]) -> np.ndarray:
    model = _get_model()
    vecs = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
    return np.array(vecs, dtype=np.float32)


def _texts(chunks: list[dict]) -> list[str]:
    """Extract the text field used for embedding."""
    return [c["chunk_text"] for c in chunks]


# ── Public API ─────────────────────────────────────────────────────────────

def build_pdf_index(chunks: list[dict]) -> None:
    """
    Build a fresh PDF FAISS index from the given chunks.
    Overwrites any existing index and metadata.
    """
    if not chunks:
        print("[pdf_embed] No chunks provided — nothing to build.")
        return

    print(f"[pdf_embed] Embedding {len(chunks)} chunks...")
    embeddings = _embed(_texts(chunks))

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    faiss.write_index(index, INDEX_PATH)
    with open(METADATA_PATH, "wb") as f:
        pickle.dump(chunks, f)

    print(f"[pdf_embed] Saved {len(chunks)} chunks | vectors={index.ntotal} | path={INDEX_PATH}")
    print(f"[pdf_embed] Metadata saved to {METADATA_PATH}")


def add_to_pdf_index(chunks: list[dict]) -> None:
    """
    Append new chunks to the existing PDF index.
    Creates the index from scratch if it does not exist yet.
    """
    if not chunks:
        return

    # Load existing state if present
    if os.path.exists(INDEX_PATH) and os.path.exists(METADATA_PATH):
        index = faiss.read_index(INDEX_PATH)
        with open(METADATA_PATH, "rb") as f:
            existing: list[dict] = pickle.load(f)
    else:
        index = None
        existing = []

    print(f"[pdf_embed] Embedding {len(chunks)} new chunks...")
    embeddings = _embed(_texts(chunks))

    if index is None:
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)

    index.add(embeddings)
    all_metadata = existing + chunks

    faiss.write_index(index, INDEX_PATH)
    with open(METADATA_PATH, "wb") as f:
        pickle.dump(all_metadata, f)

    print(f"[pdf_embed] Index now contains {index.ntotal} vectors.")
