"""
backend/scripts/build_pdf_index.py

Offline pipeline — run once, or whenever new documents are added.

  1. Read device_documents table for all active PDFs (with a file_url).
  2. Download each PDF from Supabase Storage.
  3. Extract text  (pdf_processing/extract_text.py)
  4. Clean text    (pdf_processing/clean_text.py)
  5. Chunk text    (pdf_processing/chunk_text.py)
  6. Embed + save  (pdf_processing/embed_chunks.py)

Usage:
    # Full rebuild — re-indexes every active document
    python backend/scripts/build_pdf_index.py

    # Incremental — skip docs whose chunk_ids are already in the index
    python backend/scripts/build_pdf_index.py --incremental

PDFs are NEVER downloaded during user queries.
"""

import os
import sys
from pathlib import Path

# Allow imports from backend/ when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from pdf_processing.extract_text import extract
from pdf_processing.clean_text   import clean_pages
from pdf_processing.chunk_text   import chunk_document
from pdf_processing.embed_chunks import build_pdf_index, add_to_pdf_index, METADATA_PATH

import pickle
import os as _os


def _already_indexed() -> set[str]:
    """Return set of document_names already present in the metadata store."""
    if not _os.path.exists(METADATA_PATH):
        return set()
    with open(METADATA_PATH, "rb") as f:
        meta: list[dict] = pickle.load(f)
    return {m["document_name"] for m in meta}


def fetch_documents() -> list[dict]:
    """Return all active rows from device_documents that have a file_url."""
    from database.supabase_client import supabase
    result = (
        supabase.table("device_documents")
        .select("id, product_name, document_name, file_url")
        .eq("is_active", True)
        .not_.is_("file_url", "null")
        .execute()
    )
    return result.data or []


def process_document(doc: dict) -> list[dict]:
    """
    Full pipeline for one document row.
    Returns a list of chunk dicts ready for embedding, or [] on failure.
    """
    url           = doc["file_url"]
    product_name  = doc["product_name"]
    document_name = doc["document_name"]

    try:
        print(f"  Downloading : {document_name} ({product_name})")
        pages = extract(url)

        clean = clean_pages(pages)
        if not clean.strip():
            print(f"  SKIP (no extractable text): {document_name}")
            return []

        chunks = chunk_document(clean, product_name, document_name)
        print(f"  Chunked     : {len(chunks)} chunk(s)")
        return chunks

    except Exception as e:
        print(f"  ERROR processing {document_name}: {type(e).__name__}: {e}")
        return []


def main(incremental: bool = False) -> None:
    docs = fetch_documents()
    # Deduplicate: same document_name may appear in multiple category rows
    seen_names: set[str] = set()
    unique_docs: list[dict] = []
    for d in docs:
        if d["document_name"] not in seen_names:
            seen_names.add(d["document_name"])
            unique_docs.append(d)

    print(f"[pdf_index] Indexed PDFs={len(unique_docs)}")

    already = _already_indexed() if incremental else set()
    if incremental and already:
        print(f"[pdf_index] Incremental mode: already indexed={len(already)} — skipping those.")

    all_chunks: list[dict] = []
    skipped = 0

    for doc in unique_docs:
        if incremental and doc["document_name"] in already:
            print(f"  SKIP (already indexed): {doc['document_name']}")
            skipped += 1
            continue
        chunks = process_document(doc)
        all_chunks.extend(chunks)

    print(f"[pdf_index] Chunks created={len(all_chunks)} (skipped {skipped} already-indexed docs)")

    if not all_chunks:
        print("[pdf_index] No new chunks to index.")
        return

    print(f"[pdf_index] Embeddings created={len(all_chunks)}")
    if incremental:
        add_to_pdf_index(all_chunks)
    else:
        build_pdf_index(all_chunks)

    print("[pdf_index] PDF index build complete.")


if __name__ == "__main__":
    incremental = "--incremental" in sys.argv
    main(incremental=incremental)
