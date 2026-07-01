"""
pdf_processing/chunk_text.py

Splits clean PDF text into overlapping semantic chunks that respect
paragraph boundaries.

Target: ~500 words per chunk, ~100-word overlap.

Entry point:
    chunk_document(clean_text, product_name, document_name) -> list[dict]

Each returned dict:
    {
        "chunk_id":      str,   # "{product_name}::{document_name}::N"
        "product_name":  str,
        "document_name": str,
        "page_number":   int,   # 1-based; estimated from paragraph position
        "chunk_text":    str,
    }
"""

TARGET_WORDS = 500
OVERLAP_WORDS = 100


def _paragraphs(text: str) -> list[str]:
    """Split on blank lines, discard empty paragraphs."""
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _word_count(s: str) -> int:
    return len(s.split())


def chunk_document(
    clean_text: str,
    product_name: str,
    document_name: str,
) -> list[dict]:
    """
    Split clean_text into overlapping chunks preserving paragraph boundaries.
    Returns a list of chunk metadata dicts.
    """
    paragraphs = _paragraphs(clean_text)
    if not paragraphs:
        return []

    chunks: list[dict] = []
    current_paras: list[str] = []
    current_words = 0
    # Track cumulative paragraph index to estimate page number (every ~3
    # paragraphs ≈ 1 page; good-enough for a text-only estimate).
    para_index = 0

    def _flush(paras: list[str], start_para_idx: int) -> dict:
        text = "\n\n".join(paras)
        n = len(chunks) + 1
        return {
            "chunk_id":      f"{product_name}::{document_name}::{n}",
            "product_name":  product_name,
            "document_name": document_name,
            "page_number":   max(1, start_para_idx // 3 + 1),
            "chunk_text":    text,
        }

    chunk_start_para = 0

    for para in paragraphs:
        wc = _word_count(para)

        # If a single paragraph exceeds the target, hard-split it by words.
        if wc > TARGET_WORDS:
            # Flush whatever is pending first
            if current_paras:
                chunks.append(_flush(current_paras, chunk_start_para))
                # Keep overlap from tail of current chunk
                overlap_paras, overlap_words = [], 0
                for p in reversed(current_paras):
                    pw = _word_count(p)
                    if overlap_words + pw > OVERLAP_WORDS:
                        break
                    overlap_paras.insert(0, p)
                    overlap_words += pw
                current_paras = overlap_paras
                current_words = overlap_words
                chunk_start_para = para_index

            words = para.split()
            i = 0
            while i < len(words):
                segment = " ".join(words[i: i + TARGET_WORDS])
                chunks.append({
                    "chunk_id":      f"{product_name}::{document_name}::{len(chunks) + 1}",
                    "product_name":  product_name,
                    "document_name": document_name,
                    "page_number":   max(1, para_index // 3 + 1),
                    "chunk_text":    segment,
                })
                i += TARGET_WORDS - OVERLAP_WORDS
        else:
            current_paras.append(para)
            current_words += wc

            if current_words >= TARGET_WORDS:
                chunks.append(_flush(current_paras, chunk_start_para))

                # Seed next chunk with overlap from the tail
                overlap_paras, overlap_words = [], 0
                for p in reversed(current_paras):
                    pw = _word_count(p)
                    if overlap_words + pw > OVERLAP_WORDS:
                        break
                    overlap_paras.insert(0, p)
                    overlap_words += pw

                current_paras = overlap_paras
                current_words = overlap_words
                chunk_start_para = para_index

        para_index += 1

    # Flush any remaining paragraphs
    if current_paras:
        chunks.append(_flush(current_paras, chunk_start_para))

    return chunks
