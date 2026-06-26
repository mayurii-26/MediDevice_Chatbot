"""
cache_service.py
Improvements:
  1. Semantic similarity matching via cosine similarity on embeddings.
  2. Never cache fallback / error responses.
  3. Ignore invalid (fallback) answers already in cache.
  4. Cache quality gate: answer must be > 100 chars and contain real content.

Embedding column migration:
  Run this once in Supabase SQL editor:
      ALTER TABLE cached_answers ADD COLUMN IF NOT EXISTS embedding vector(384);
  Until the column exists the service degrades to exact-match only.
"""

import numpy as np
from database.supabase_client import supabase

# ── Similarity threshold ──────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.90

# ── Fallback fragments that must never be cached or returned ──────────────
_FALLBACK_FRAGMENTS = [
    "i am a medical device assistant trained on philips",
    "our ai service is temporarily unavailable",
    "please ask about supported medical devices",
    "temporarily unavailable",
    "contact support@medidevicechatbot.com for further assistance",
    "i could not find relevant information",
]


def _normalise_question(question: str) -> str:
    return " ".join(question.strip().lower().split())


def _cache_key(question: str, intent: str) -> str:
    return f"{intent}::{_normalise_question(question)}"


def _is_fallback(text: str) -> bool:
    low = text.lower()
    return any(frag in low for frag in _FALLBACK_FRAGMENTS)


def _is_quality(answer: str) -> bool:
    """True if the answer is worth caching."""
    return (
        bool(answer)
        and len(answer.strip()) > 100
        and not _is_fallback(answer)
    )


# ── Known product tokens — used to prevent cross-product cache hits ────────
# Any two questions containing different tokens from this list must NOT match.
_PRODUCT_TOKENS = [
    "tc50", "tc35", "tc10",
    "frx", "hs1",
    "dfm100",
    "st80i",
    "oscar 2",
    "cardiac workstation",
    "trilogy",
]


def _extract_product_token(text: str) -> str | None:
    """Return the first known product token found in text, or None."""
    t = text.lower()
    for token in _PRODUCT_TOKENS:
        if token in t:
            return token
    return None


def _product_tokens_conflict(question: str, cached_question_key: str) -> bool:
    """
    Return True if the incoming question mentions a specific product that is
    DIFFERENT from the product mentioned in the cached question key.
    This prevents 'TC50' question from hitting a 'TC10' cached answer.
    """
    q_token     = _extract_product_token(question)
    cached_token = _extract_product_token(cached_question_key)
    if q_token is None or cached_token is None:
        return False          # no product token in one or both — no conflict
    return q_token != cached_token


# ── Lazy model reference — reuses the instance already loaded in search.py ─
def _get_model():
    from search import _model
    return _model


def _embed(text: str) -> np.ndarray:
    """Return a unit-norm 384-d embedding of the normalised text."""
    from search import normalise_query
    normalised = normalise_query(text)
    vec = _get_model().encode([normalised], convert_to_numpy=True)[0]
    norm = np.linalg.norm(vec)
    return (vec / norm) if norm > 0 else vec


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))          # both already unit-norm


# ── Semantic cache lookup ─────────────────────────────────────────────────

def _semantic_lookup(question: str, intent: str) -> str | None:
    """
    Fetch all rows for the given intent, compute cosine similarity against
    the query embedding, return the best answer if >= threshold.
    Falls back to exact-key lookup if embedding column is unavailable.
    """
    intent_prefix = f"{intent}::"

    try:
        result = (
            supabase.table("cached_answers")
            .select("question, answer, embedding")
            .like("question", f"{intent_prefix}%")
            .execute()
        )
    except Exception as e:
        print(f"[cache] DB error during lookup: {e}")
        return None

    rows = result.data or []
    if not rows:
        return None

    # Check if any row has a non-null embedding
    has_embeddings = any(r.get("embedding") is not None for r in rows)

    if not has_embeddings:
        # Embedding column missing or all null — exact match only
        key = _cache_key(question, intent)
        for row in rows:
            if row["question"] == key:
                answer = row["answer"]
                if _is_fallback(answer):
                    print("[cache] invalid cached answer ignored")
                    return None
                if _product_tokens_conflict(question, row["question"]):
                    print(f"[cache] skipped (product mismatch) | cached_q={row['question']}")
                    return None
                print(f"[cache] CACHE HIT (exact) | key={key}")
                return answer
        return None

    # Semantic matching
    print("[cache] semantic lookup started")
    q_vec = _embed(question)
    best_score = 0.0
    best_answer = None
    best_question = None

    for row in rows:
        answer = row.get("answer", "")
        if _is_fallback(answer):
            continue

        raw_emb = row.get("embedding")
        if raw_emb is None:
            continue

        # Product-aware guard: skip if cached question targets a different product
        if _product_tokens_conflict(question, row.get("question", "")):
            print(f"[cache] skipped (product mismatch) | cached_q={row['question']}")
            continue

        # Supabase pgvector returns the value as a string "[-0.145,0.019,...]"
        # when the column type is vector(384). Parse it before converting.
        print(f"[cache] embedding_type={type(raw_emb).__name__}")
        try:
            if isinstance(raw_emb, str):
                raw_emb = [float(x) for x in raw_emb.strip("[]").split(",")]
            cached_vec = np.array(raw_emb, dtype=np.float32)
        except Exception as parse_err:
            print(f"[cache] embedding parse failed for row {row.get('question')}: {parse_err}")
            continue

        norm = np.linalg.norm(cached_vec)
        if norm > 0:
            cached_vec = cached_vec / norm

        score = _cosine(q_vec, cached_vec)
        print(f"[cache] comparing | cached_q={row['question']} | similarity={score:.4f}")
        if score > best_score:
            best_score = score
            best_answer = answer
            best_question = row["question"]

    if best_score >= SIMILARITY_THRESHOLD:
        print(f"[cache] semantic match found | best_q={best_question} | similarity={best_score:.4f}")
        return best_answer

    print(f"[cache] semantic match not found | best_q={best_question} | best_similarity={best_score:.4f}")
    return None


# ── Public API ────────────────────────────────────────────────────────────

def get_cached_answer(question: str, intent: str = "product_query") -> str | None:
    try:
        answer = _semantic_lookup(question, intent)
    except Exception as e:
        print(f"[cache] semantic lookup failed: {type(e).__name__}: {e}")
        answer = None
    if answer:
        return answer
    print(f"[cache] CACHE MISS | question={_normalise_question(question)} | intent={intent}")
    return None


def save_cached_answer(question: str, answer: str, intent: str = "product_query") -> None:
    # Quality gate
    if not _is_quality(answer):
        if _is_fallback(answer):
            print("[cache] skip cache | reason=fallback_response")
        else:
            print(f"[cache] skip cache | reason=low_quality (len={len(answer.strip())})")
        return

    key = _cache_key(question, intent)

    # Duplicate check
    existing = (
        supabase.table("cached_answers")
        .select("question")
        .eq("question", key)
        .limit(1)
        .execute()
    )
    if existing.data:
        return

    # Try to store with embedding
    try:
        vec = _embed(question).tolist()
        supabase.table("cached_answers").insert({
            "question": key,
            "answer":   answer,
            "embedding": vec,
        }).execute()
        print(f"[cache] stored with embedding | key={key}")
    except Exception:
        # embedding column may not exist yet — store without it
        try:
            supabase.table("cached_answers").insert({
                "question": key,
                "answer":   answer,
            }).execute()
            print(f"[cache] stored (no embedding column) | key={key}")
            print("[cache] MIGRATION NEEDED: ALTER TABLE cached_answers ADD COLUMN IF NOT EXISTS embedding vector(384);")
        except Exception as e2:
            print(f"[cache] insert failed: {e2}")
