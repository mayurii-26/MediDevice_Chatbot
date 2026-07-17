"""
cache_service.py

Improvements:
  1. CACHE_VERSION = 2 — every new cache entry is written with a `version`
     field.  Reads ONLY return rows whose version matches the current
     CACHE_VERSION.  Older rows are automatically ignored (not deleted) so
     the cache table is never dropped and stale malformed text is never
     served again.

  2. _is_formatted() guard — save_cached_answer() rejects responses that
     look like raw retrieval output (FAISS chunks, raw PDF text, raw Gemini
     output, or partially formatted content).  Only final markdown responses
     are stored.

  3. ENABLE_CACHE flag — controlled by .env.  When False, all cache reads
     and writes are skipped and the full pipeline always executes.

  4. Full structured logging:
       [CACHE] STATUS   : HIT | MISS | DISABLED
       [CACHE] QUESTION : <normalised question>
       [CACHE] KEY      : <cache key>
       [CACHE] SOURCE   : cache | pipeline

  5. Semantic similarity matching via cosine similarity on embeddings.

  6. Never cache fallback / error responses.

  7. Ignore invalid (fallback) answers already in cache.

  8. Cache quality gate: answer must be > 100 chars and contain real content.

Schema notes
------------
  The cached_answers table is NEVER dropped or truncated.
  Old rows (version < CACHE_VERSION) are silently skipped on read and will
  age out naturally if the table has a TTL policy, or can be manually pruned:

      DELETE FROM cached_answers WHERE version IS NULL OR version < 2;

  Embedding column migration (run once in Supabase SQL editor):
      ALTER TABLE cached_answers ADD COLUMN IF NOT EXISTS embedding vector(384);

  Version column migration (run once in Supabase SQL editor):
      ALTER TABLE cached_answers ADD COLUMN IF NOT EXISTS version integer;
"""

import os
import numpy as np
from dotenv import load_dotenv
from database.supabase_client import supabase

# ── Load environment ──────────────────────────────────────────────────────
load_dotenv()

# ── Cache version ─────────────────────────────────────────────────────────
# Bump this constant whenever the response format changes significantly.
# All existing cache rows without this version will be ignored on read;
# all new rows will be written with this version.
CACHE_VERSION: int = 2

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
    # Sample report intent replies — never cache these
    "sample reports related information is not available through the chatbot",
]

# ── Raw-output markers that must never be cached ──────────────────────────
# These patterns appear in raw FAISS chunks, raw PDF text, raw Gemini
# output, or partially formatted responses that leaked through.
_RAW_OUTPUT_MARKERS = [
    # FAISS / knowledge-base raw chunk headers
    "product name:",
    "category:",
    "description:",
    "features:\n",
    "specifications:\n",
    # Raw web-search / DuckDuckGo output
    "[web search results]",
    "🌐 dynamic search\n\n",
    # Raw Wikipedia context header
    "📚 medical background\n\n",
    # PDF raw chunk marker
    "📄 pdf knowledge\n\n",
]


# ── Helpers ───────────────────────────────────────────────────────────────

def _normalise_question(question: str) -> str:
    return " ".join(question.strip().lower().split())


def _cache_key(question: str, intent: str) -> str:
    return f"{intent}::{_normalise_question(question)}"


def _is_fallback(text: str) -> bool:
    low = text.lower()
    return any(frag in low for frag in _FALLBACK_FRAGMENTS)


def _is_formatted(answer: str) -> bool:
    """
    Return True only when `answer` is a final formatted markdown response
    that is safe to cache.

    Rejects:
      - Raw FAISS/PDF chunks (contain "Product Name:", "Category:", etc.)
      - Raw Gemini output prefixed with context markers
      - Partially formatted responses (DuckDuckGo / Wikipedia raw headers)
      - Answers that are too short or contain fallback text
    """
    if not answer or len(answer.strip()) < 100:
        return False
    if _is_fallback(answer):
        return False
    low = answer.lower()
    for marker in _RAW_OUTPUT_MARKERS:
        if marker in low:
            return False
    return True


def _is_quality(answer: str) -> bool:
    """True if the answer passes both the quality and format gates."""
    return _is_formatted(answer)


def _log_cache(status: str, question: str, intent: str, extra: str = "") -> None:
    """
    Emit a structured cache log line.

    status  : HIT | MISS | DISABLED | STORED | SKIPPED
    """
    key = _cache_key(question, intent)
    print(
        f"\n╔══ [CACHE] ══════════════════════════════════════════"
        f"\n║  STATUS   : {status}"
        f"\n║  VERSION  : {CACHE_VERSION}"
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
    Fetch all rows for the given intent that match CACHE_VERSION,
    compute cosine similarity against the query embedding, and return
    the best answer if >= threshold.

    Falls back to exact-key lookup if embedding column is unavailable.
    Rows with a missing or mismatched version are silently skipped.
    """
    intent_prefix = f"{intent}::"

    try:
        result = (
            supabase.table("cached_answers")
            .select("question, answer, embedding, version")
            .like("question", f"{intent_prefix}%")
            .execute()
        )
    except Exception as e:
        print(f"[CACHE] DB error during lookup: {e}")
        return None

    rows = result.data or []
    if not rows:
        return None

    # ── Filter: only accept rows with the current CACHE_VERSION ──────────
    # Rows without a version column (NULL) are treated as version 1
    # and are rejected when CACHE_VERSION > 1.
    versioned_rows = [
        r for r in rows
        if (r.get("version") or 1) == CACHE_VERSION
    ]

    skipped_old = len(rows) - len(versioned_rows)
    if skipped_old:
        print(
            f"[CACHE] skipped {skipped_old} row(s) with version < {CACHE_VERSION} "
            f"(stale cache entries — not deleted)"
        )

    if not versioned_rows:
        return None

    has_embeddings = any(r.get("embedding") is not None for r in versioned_rows)

    if not has_embeddings:
        # Exact-match fallback
        key = _cache_key(question, intent)
        for row in versioned_rows:
            if row["question"] == key:
                answer = row["answer"]
                if _is_fallback(answer):
                    print("[CACHE] invalid cached answer ignored (fallback fragment)")
                    return None
                if not _is_formatted(answer):
                    print("[CACHE] invalid cached answer ignored (not formatted / raw output)")
                    return None
                if _product_tokens_conflict(question, row["question"]):
                    print(f"[CACHE] skipped — product mismatch | cached_q={row['question']}")
                    return None
                return answer
        return None

    # Semantic matching
    print("[CACHE] running semantic similarity lookup …")
    q_vec = _embed(question)
    best_score    = 0.0
    best_answer   = None
    best_question = None

    for row in versioned_rows:
        answer = row.get("answer", "")
        if _is_fallback(answer):
            continue
        if not _is_formatted(answer):
            print(f"[CACHE] skipped raw-output row | q={row.get('question')}")
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
    Only returns answers that were stored with CACHE_VERSION == current version.
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
    Persist a new answer to the cache — only when ENABLE_CACHE is True,
    the answer passes the quality gate (_is_formatted), and the intent
    is cacheable.

    Writes CACHE_VERSION into every new row so older stale entries are
    automatically ignored by future reads without table deletion.

    Never stores:
      - Raw FAISS chunks
      - Raw PDF text
      - Raw Gemini output
      - Raw dynamic search results
      - Partially formatted responses
      - Fallback / error messages
    """
    if not ENABLE_CACHE:
        print("[CACHE] save skipped — ENABLE_CACHE=False")
        return

    # Never cache purchase intent or out-of-scope responses
    _UNCACHEABLE_INTENTS = {"purchase_intent", "out_of_scope", "sample_report_intent"}
    if intent in _UNCACHEABLE_INTENTS:
        print(f"[CACHE] save skipped — intent={intent} is not cacheable")
        return

    if not _is_formatted(answer):
        if _is_fallback(answer):
            reason = "fallback_response"
        else:
            import re as _re
            low = answer.lower()
            raw_marker = next(
                (m for m in _RAW_OUTPUT_MARKERS if m in low), None
            )
            if raw_marker:
                reason = f"raw_output_detected (marker={raw_marker!r})"
            else:
                reason = f"not_formatted (len={len(answer.strip())})"
        print(f"[CACHE] SKIPPED — {reason}")
        return

    key = _cache_key(question, intent)

    # Duplicate check — skip if an entry with the same key AND version exists
    try:
        existing = (
            supabase.table("cached_answers")
            .select("question, version")
            .eq("question", key)
            .eq("version", CACHE_VERSION)
            .limit(1)
            .execute()
        )
        if existing.data:
            print(f"[CACHE] already stored (v{CACHE_VERSION}) — no-op | key={key}")
            return
    except Exception as dup_err:
        print(f"[CACHE] duplicate check error (proceeding): {dup_err}")

    # Try to store with embedding + version
    try:
        vec = _embed(question).tolist()
        supabase.table("cached_answers").insert({
            "question":  key,
            "answer":    answer,
            "embedding": vec,
            "version":   CACHE_VERSION,
        }).execute()
        print(f"[CACHE] STORED (v{CACHE_VERSION}, with embedding) | key={key}")
    except Exception:
        # Embedding column might not exist yet — try without it
        try:
            supabase.table("cached_answers").insert({
                "question": key,
                "answer":   answer,
                "version":  CACHE_VERSION,
            }).execute()
            print(f"[CACHE] STORED (v{CACHE_VERSION}, no embedding column) | key={key}")
            print(
                "[CACHE] MIGRATION NEEDED: "
                "ALTER TABLE cached_answers ADD COLUMN IF NOT EXISTS embedding vector(384);"
            )
        except Exception as e2:
            print(f"[CACHE] insert failed: {e2}")
