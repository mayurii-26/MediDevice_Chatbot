"""
cache_service.py

Improvements:
  1. ENABLE_CACHE flag — controlled by .env.  When False, all cache reads
     and writes are skipped and the full pipeline always executes.
  2. Full structured logging:
       [CACHE] STATUS   : HIT | MISS | DISABLED
       [CACHE] QUESTION : <normalised question>
       [CACHE] KEY      : <cache key>
       [CACHE] SOURCE   : cache | pipeline
  3. Semantic similarity matching via cosine similarity on embeddings.
  4. Never cache fallback / error responses.
  5. Ignore invalid (fallback) answers already in cache.
  6. Cache quality gate: answer must be > 100 chars and contain real content.

Embedding column migration:
  Run this once in Supabase SQL editor:
      ALTER TABLE cached_answers ADD COLUMN IF NOT EXISTS embedding vector(384);
  Until the column exists the service degrades to exact-match only.
"""

import os
import numpy as np
from dotenv import load_dotenv
from database.supabase_client import supabase

# ── Load environment ──────────────────────────────────────────────────────
load_dotenv()

# ── Single feature flag — flip this in .env to re-enable cache ───────────
_raw_flag = os.getenv("ENABLE_CACHE", "true").strip().lower()
ENABLE_CACHE: bool = _raw_flag in ("1", "true", "yes", "on")

# ── Similarity threshold ──────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.90

# ── Fallback fragments that must never be cached or returned ──────────────
_FALLBACK_FRAGMENTS = [
    # Generic fallback responses
    "i am a medical device assistant trained on",
    "our ai service is temporarily unavailable",
    "please ask about supported medical devices",
    "temporarily unavailable",
    "contact support@medideviceai.com for further assistance",
    "i could not find relevant information",
    # Purchase / pricing intent replies (Phase 5.2) — never cache these
    "pricing and purchasing information is not available through the chatbot",
    "please contact our support team and we'll get back to you shortly",
    # Out-of-scope / out-of-context replies (Phase 5.3 / 5.6) — never cache
    "this platform is designed only for medical devices",
    "healthcare-related queries",
]


# ── Helpers ───────────────────────────────────────────────────────────────

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


def _log_cache(status: str, question: str, intent: str, extra: str = "") -> None:
    """
    Emit a structured cache log line.

    status  : HIT | MISS | DISABLED | STORED | SKIPPED
    """
    key = _cache_key(question, intent)
    print(
        f"\n╔══ [CACHE] ══════════════════════════════════════════"
        f"\n║  STATUS   : {status}"
        f"\n║  QUESTION : {_normalise_question(question)}"
        f"\n║  KEY      : {key}"
        f"\n║  SOURCE   : {'cache' if status == 'HIT' else 'pipeline'}"
        + (f"\n║  NOTE     : {extra}" if extra else "")
        + f"\n╚═════════════════════════════════════════════════════\n"
    )


# ── Known product tokens — used to prevent cross-product cache hits ────────
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
    t = text.lower()
    for token in _PRODUCT_TOKENS:
        if token in t:
            return token
    return None


def _product_tokens_conflict(question: str, cached_question_key: str) -> bool:
    q_token      = _extract_product_token(question)
    cached_token = _extract_product_token(cached_question_key)
    if q_token is None or cached_token is None:
        return False
    return q_token != cached_token


# ── Lazy model reference — reuses the instance already loaded in search.py ─
def _get_model():
    from search import _model
    return _model


def _embed(text: str) -> np.ndarray:
    from search import normalise_query
    normalised = normalise_query(text)
    vec = _get_model().encode([normalised], convert_to_numpy=True)[0]
    norm = np.linalg.norm(vec)
    return (vec / norm) if norm > 0 else vec


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))   # both already unit-norm


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
        print(f"[CACHE] DB error during lookup: {e}")
        return None

    rows = result.data or []
    if not rows:
        return None

    has_embeddings = any(r.get("embedding") is not None for r in rows)

    if not has_embeddings:
        # Exact-match fallback
        key = _cache_key(question, intent)
        for row in rows:
            if row["question"] == key:
                answer = row["answer"]
                if _is_fallback(answer):
                    print("[CACHE] invalid cached answer ignored (fallback fragment)")
                    return None
                if _product_tokens_conflict(question, row["question"]):
                    print(f"[CACHE] skipped — product mismatch | cached_q={row['question']}")
                    return None
                return answer
        return None

    # Semantic matching
    print("[CACHE] running semantic similarity lookup …")
    q_vec = _embed(question)
    best_score   = 0.0
    best_answer  = None
    best_question = None

    for row in rows:
        answer = row.get("answer", "")
        if _is_fallback(answer):
            continue

        raw_emb = row.get("embedding")
        if raw_emb is None:
            continue

        if _product_tokens_conflict(question, row.get("question", "")):
            print(f"[CACHE] skipped — product mismatch | cached_q={row['question']}")
            continue

        try:
            if isinstance(raw_emb, str):
                raw_emb = [float(x) for x in raw_emb.strip("[]").split(",")]
            cached_vec = np.array(raw_emb, dtype=np.float32)
        except Exception as parse_err:
            print(f"[CACHE] embedding parse failed for {row.get('question')}: {parse_err}")
            continue

        norm = np.linalg.norm(cached_vec)
        if norm > 0:
            cached_vec = cached_vec / norm

        score = _cosine(q_vec, cached_vec)
        print(f"[CACHE] similarity check | cached_q={row['question']} | score={score:.4f}")
        if score > best_score:
            best_score    = score
            best_answer   = answer
            best_question = row["question"]

    if best_score >= SIMILARITY_THRESHOLD:
        print(
            f"[CACHE] semantic match | best_q={best_question} | similarity={best_score:.4f}"
        )
        return best_answer

    print(
        f"[CACHE] no match above threshold | best_q={best_question} | "
        f"best_similarity={best_score:.4f} | threshold={SIMILARITY_THRESHOLD}"
    )
    return None


# ── Public API ────────────────────────────────────────────────────────────

def get_cached_answer(question: str, intent: str = "product_query") -> str | None:
    """
    Return a cached answer if available and ENABLE_CACHE is True.
    Always logs the outcome with QUESTION, KEY, and STATUS.
    """
    if not ENABLE_CACHE:
        _log_cache("DISABLED", question, intent, "ENABLE_CACHE=False → full pipeline will run")
        return None

    try:
        answer = _semantic_lookup(question, intent)
    except Exception as e:
        print(f"[CACHE] semantic lookup error: {type(e).__name__}: {e}")
        answer = None

    if answer:
        _log_cache("HIT", question, intent)
        return answer

    _log_cache("MISS", question, intent)
    return None


def save_cached_answer(question: str, answer: str, intent: str = "product_query") -> None:
    """
    Persist a new answer to the cache — only when ENABLE_CACHE is True and
    the answer passes the quality gate.
    """
    if not ENABLE_CACHE:
        print("[CACHE] save skipped — ENABLE_CACHE=False")
        return

    # Never cache purchase intent or out-of-scope responses
    _UNCACHEABLE_INTENTS = {"purchase_intent", "out_of_scope"}
    if intent in _UNCACHEABLE_INTENTS:
        print(f"[CACHE] save skipped — intent={intent} is not cacheable")
        return

    if not _is_quality(answer):
        reason = "fallback_response" if _is_fallback(answer) else f"low_quality (len={len(answer.strip())})"
        print(f"[CACHE] SKIPPED — {reason}")
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
        print(f"[CACHE] already stored — no-op | key={key}")
        return

    # Try to store with embedding
    try:
        vec = _embed(question).tolist()
        supabase.table("cached_answers").insert({
            "question":  key,
            "answer":    answer,
            "embedding": vec,
        }).execute()
        print(f"[CACHE] STORED (with embedding) | key={key}")
    except Exception:
        try:
            supabase.table("cached_answers").insert({
                "question": key,
                "answer":   answer,
            }).execute()
            print(f"[CACHE] STORED (no embedding column) | key={key}")
            print("[CACHE] MIGRATION NEEDED: ALTER TABLE cached_answers ADD COLUMN IF NOT EXISTS embedding vector(384);")
        except Exception as e2:
            print(f"[CACHE] insert failed: {e2}")
