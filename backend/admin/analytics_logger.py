"""
admin/analytics_logger.py
─────────────────────────────────────────────────────────────────────────────
Centralised analytics event logger for the admin portal.

All functions are:
  - Fire-and-forget (non-fatal — never raises, never blocks the pipeline)
  - Called AFTER the response is built, not during retrieval
  - Idempotent-safe (duplicate rows are acceptable for counts)

Public API
──────────
log_query(...)              → query_logs table (every chatbot query)
log_product_search(...)     → product_search_logs table (upsert search count)
log_comparison(...)         → comparison_logs table
log_specification(...)      → specification_logs table
log_unanswered_query(...)   → unanswered_queries table

  "Unknown Queries" definition (v2):
  ─────────────────────────────────
  A query is stored here when:
    1. It is a healthcare/medical/device domain question, AND
    2. It was NOT answered from the internal product KB
       (answer_source NOT IN {faiss, bm25, pdf, cache})

  This is NOT about "no response received."
  It is about "our product knowledge base could not answer this."
  The chatbot may have replied via web search, Wikipedia, a medical
  assistant canned reply, or a fallback — all of those are STORED
  because they represent gaps in our KB.

  Only intentional guards (purchase/sample-report) are excluded.

Documents and contact requests are already written by download_service.py
and app.py (/contact endpoint) respectively — no duplicate writes here.

Tables (created by analytics_migration.sql + unanswered_queries_migration.sql):
  query_logs
  product_search_logs   (UPSERT on product_name)
  comparison_logs
  specification_logs
  unanswered_queries    (UPSERT on query_normalised, increments times_asked)
"""

from __future__ import annotations
import re

from database.supabase_client import supabase


# ── Internal helpers ───────────────────────────────────────────────────────

def _insert(table: str, row: dict) -> None:
    """Non-fatal insert — logs error but never raises."""
    try:
        supabase.table(table).insert(row).execute()
    except Exception as exc:
        print(f"[analytics] INSERT {table} failed (non-fatal): {type(exc).__name__}: {exc}")


# ── Healthcare domain filter ───────────────────────────────────────────────
# Two-pass approach:
#   Pass 1 — explicit BLOCKLIST: clearly off-topic topics → False immediately
#   Pass 2 — ALLOWLIST: any medical/health/device term → True
#
# This ensures questions like "What medicine for fever?" pass (medicine, fever)
# while "python programming" or "football score" are blocked.

_OOS_BLOCKLIST_FILTER = re.compile(
    r"\b(weather|cricket|ipl|football|soccer|basketball|tennis|badminton"
    r"|movie|film|bollywood|netflix|spotify|song|music|singer"
    r"|python|javascript|react|angular|coding|programming|algorithm"
    r"|bitcoin|crypto|blockchain|nft|stock market|share price"
    r"|recipe|cook|chef|restaurant|hotel|travel|tourism"
    r"|joke|meme|funny|prank|game|esports|minecraft|fortnite"
    r"|weather forecast|rain|temperature outside)\b",
    re.IGNORECASE,
)

_HEALTHCARE_TERMS = [
    # ── Diseases & conditions ──────────────────────────────────────────────
    "fever", "malaria", "dengue", "typhoid", "cholera", "tuberculosis", "tb",
    "covid", "coronavirus", "influenza", "flu", "pneumonia", "bronchitis",
    "asthma", "copd", "emphysema",
    "hypertension", "high blood pressure", "low blood pressure", "hypotension",
    "diabetes", "diabetic", "insulin", "blood sugar", "glucose",
    "cancer", "tumour", "tumor", "oncology", "chemotherapy", "radiotherapy",
    "stroke", "heart attack", "cardiac arrest", "myocardial infarction",
    "angina", "arrhythmia", "atrial fibrillation", "tachycardia", "bradycardia",
    "heart failure", "congestive heart failure",
    "kidney failure", "renal failure", "dialysis",
    "liver disease", "hepatitis", "cirrhosis", "jaundice",
    "anemia", "anaemia", "sickle cell", "thalassemia",
    "epilepsy", "seizure", "convulsion",
    "alzheimer", "dementia", "parkinson",
    "arthritis", "osteoporosis", "gout", "rheumatoid",
    "thyroid", "hypothyroid", "hyperthyroid", "goitre",
    "hiv", "aids", "std", "sti",
    "sepsis", "infection", "bacterial", "viral", "fungal",
    "appendicitis", "gallstone", "kidney stone", "urinary tract infection", "uti",
    "ibs", "irritable bowel", "crohn", "colitis", "gastritis", "ulcer",
    "migraine", "headache", "vertigo", "tinnitus",
    "depression", "anxiety", "schizophrenia", "bipolar", "mental health",
    "autism", "adhd",
    "neonatal", "premature birth", "jaundice", "birth defect",
    "malnutrition", "obesity", "bmi",
    "fracture", "bone", "orthopedic", "orthopaedic",
    "wound", "burn", "laceration", "trauma",
    # ── Symptoms ──────────────────────────────────────────────────────────
    "chest pain", "shortness of breath", "breathlessness", "dyspnea",
    "palpitation", "dizziness", "fainting", "syncope",
    "cough", "cold", "sore throat", "runny nose", "congestion",
    "vomiting", "nausea", "diarrhea", "diarrhoea", "constipation",
    "abdominal pain", "stomach pain", "cramps",
    "swelling", "oedema", "edema",
    "rash", "itching", "skin", "allergy",
    "fatigue", "weakness", "lethargy",
    "weight loss", "weight gain",
    "blurred vision", "eye pain",
    "bleeding", "haemorrhage", "hemorrhage",
    "pain", "ache", "swell",
    # ── Medicines & treatments ────────────────────────────────────────────
    "medicine", "medication", "drug", "tablet", "capsule", "injection",
    "antibiotic", "antiviral", "antifungal", "antiseptic",
    "paracetamol", "ibuprofen", "aspirin", "acetaminophen",
    "painkiller", "analgesic", "antipyretic",
    "vaccine", "vaccination", "immunisation", "immunization",
    "antihistamine", "steroid", "corticosteroid",
    "insulin", "metformin", "atorvastatin", "lisinopril",
    "chemotherapy", "radiation therapy", "immunotherapy",
    "surgery", "operation", "transplant", "bypass",
    "treatment", "therapy", "cure", "remedy", "prescription",
    "dose", "dosage", "overdose", "side effect",
    # ── Diagnostics & procedures ──────────────────────────────────────────
    "mri", "ct scan", "x-ray", "xray", "ultrasound", "sonography",
    "ecg", "ekg", "electrocardiogram", "echocardiogram", "echo",
    "biopsy", "endoscopy", "colonoscopy", "bronchoscopy",
    "blood test", "urine test", "stool test",
    "cbc", "complete blood count", "creatinine", "urea", "bilirubin",
    "cholesterol", "triglyceride", "hdl", "ldl",
    "pathology", "laboratory", "lab test", "diagnosis", "diagnostic",
    "screening", "scan", "imaging",
    "spirometry", "pulse oximetry", "capnography",
    "holter", "stress test", "treadmill test", "angiography",
    # ── Medical devices & equipment ───────────────────────────────────────
    "monitor", "ventilator", "defibrillator", "aed",
    "cpap", "bipap", "bubble cpap",
    "infusion pump", "syringe pump",
    "pulse oximeter", "spo2", "oximeter",
    "blood pressure monitor", "bp monitor", "sphygmomanometer",
    "glucometer", "glucose meter",
    "thermometer", "temperature",
    "nebulizer", "inhaler", "spacer",
    "spirometer", "peak flow meter",
    "patient monitor", "bedside monitor",
    "ctg", "fetal monitor", "cardiotocograph",
    "phototherapy", "incubator", "radiant warmer",
    "laryngoscope", "video laryngoscope",
    "anaesthesia", "anesthesia", "anaesthetic", "anesthetic",
    "surgical", "ot complex", "operating theatre", "operating room",
    "nicu", "picu", "icu", "critical care",
    "electrocardiograph", "defibrillation", "resuscitation",
    "ambulatory", "telemetry", "waveform",
    "tidal volume", "airway", "intubation",
    "air bed", "hospital bed", "stretcher", "wheelchair",
    # ── Medical brands & product families ────────────────────────────────
    "philips", "pagewriter", "heartstart", "efficia", "trilogy",
    "tc50", "tc35", "tc10", "frx", "hs1", "dfm100", "st80i", "oscar",
    # ── General healthcare context ────────────────────────────────────────
    "medical device", "medical equipment", "healthcare",
    "clinical", "hospital", "clinic", "biomedical",
    "patient", "doctor", "nurse", "physician", "specialist",
    "ward", "icu", "emergency", "casualty",
    "health", "disease", "illness", "disorder", "condition", "syndrome",
    "preventive", "prophylaxis", "prognosis",
    "anatomy", "physiology",
    "organ", "tissue", "cell", "nerve", "muscle", "vein", "artery",
    "heart", "lung", "kidney", "liver", "brain", "spine",
    "blood", "urine", "stool", "saliva",
    "sensor", "probe", "electrode", "lead",
    "portable", "bedside", "handheld", "wireless",
    "life support", "monitoring system",
]

_HEALTHCARE_RE = re.compile(
    "|".join(
        re.escape(t) if " " in t else rf"\b{re.escape(t)}\b"
        for t in _HEALTHCARE_TERMS
    ),
    re.IGNORECASE,
)


def _is_healthcare_query(question: str) -> bool:
    """
    Returns True when:
      1. The question does NOT match the off-topic blocklist, AND
      2. The question contains at least one healthcare/medical/device term.

    Used to gate log_unanswered_query so only clinically-relevant failures
    are stored in the Unknown Queries tab.
    """
    q = question or ""
    # Fast-reject clearly off-topic queries
    if _OOS_BLOCKLIST_FILTER.search(q):
        return False
    return bool(_HEALTHCARE_RE.search(q))


def _normalise(question: str) -> str:
    """
    Lowercase + collapse whitespace → dedup key for unanswered_queries.
    Strips punctuation that doesn't affect meaning.
    """
    q = question.lower().strip()
    q = re.sub(r"[^\w\s]", " ", q)      # remove punctuation
    q = re.sub(r"\s+", " ", q).strip()  # collapse spaces
    return q


# ── 1. Query log ───────────────────────────────────────────────────────────

def log_query(
    *,
    question:         str,
    intent:           str,
    answer_source:    str,
    conversation_id:  str | None = None,
    user_id:          str | None = None,
    is_guest:         bool       = False,
    confidence:       float      = 0.0,
    matched_product:  str | None = None,
    matched_category: str | None = None,
) -> None:
    """
    Log every chatbot query to query_logs.

    Called from both /chat and /chat/stream after the final answer is ready.

    Sample row:
    {
      "question":        "What are the specifications of PageWriter TC50?",
      "intent":          "specification_query",
      "answer_source":   "faiss",
      "conversation_id": "3f2a...",
      "user_id":         "a1b2...",
      "is_guest":        false,
      "confidence":      1.0,
      "matched_product": "PageWriter TC50",
      "matched_category":"Cardiology"
    }
    """
    _insert("query_logs", {
        "question":         question.strip(),
        "intent":           intent,
        "answer_source":    answer_source,
        "conversation_id":  conversation_id or None,
        "user_id":          user_id or None,
        "is_guest":         is_guest,
        "confidence":       round(float(confidence), 4),
        "matched_product":  matched_product or None,
        "matched_category": matched_category or None,
    })


# ── 2. Product search log ──────────────────────────────────────────────────

def log_product_search(
    *,
    product_name: str,
) -> None:
    """
    Upsert a product search count in product_search_logs.

    Uses INSERT ... ON CONFLICT DO UPDATE to increment search_count atomically.
    Falls back to a plain INSERT if upsert fails.

    Sample row:
    {
      "product_name":  "PageWriter TC50",
      "search_count":  14,
      "last_searched": "2026-07-21T12:00:00+00:00"
    }
    """
    if not product_name or product_name.strip() in ("", "N/A"):
        return
    name = product_name.strip()
    try:
        # Supabase upsert with on_conflict: increments search_count
        # The raw SQL equivalent is:
        #   INSERT INTO product_search_logs (product_name, search_count, last_searched)
        #   VALUES ($1, 1, now())
        #   ON CONFLICT (product_name)
        #   DO UPDATE SET search_count = product_search_logs.search_count + 1,
        #                 last_searched = now();
        existing = (
            supabase.table("product_search_logs")
            .select("id, search_count")
            .eq("product_name", name)
            .limit(1)
            .execute()
        )
        if existing.data:
            row_id     = existing.data[0]["id"]
            new_count  = existing.data[0]["search_count"] + 1
            from datetime import datetime, timezone
            supabase.table("product_search_logs").update({
                "search_count":  new_count,
                "last_searched": datetime.now(timezone.utc).isoformat(),
            }).eq("id", row_id).execute()
        else:
            _insert("product_search_logs", {"product_name": name, "search_count": 1})
    except Exception as exc:
        print(f"[analytics] product_search upsert failed (non-fatal): {exc}")


# ── 3. Comparison log ──────────────────────────────────────────────────────

def log_comparison(
    *,
    products_compared: str,
    user_id:           str | None = None,
    conversation_id:   str | None = None,
) -> None:
    """
    Log a comparison query.

    products_compared should be a comma-separated string of product names,
    e.g. "PageWriter TC50, PageWriter TC70"

    Sample row:
    {
      "products_compared": "PageWriter TC50, PageWriter TC70",
      "user_id":           "a1b2...",
      "conversation_id":   "3f2a..."
    }
    """
    if not products_compared or not products_compared.strip():
        return
    _insert("comparison_logs", {
        "products_compared": products_compared.strip(),
        "user_id":           user_id or None,
        "conversation_id":   conversation_id or None,
    })


# ── 4. Specification log ───────────────────────────────────────────────────

def log_specification(
    *,
    product_name:    str,
    user_id:         str | None = None,
    conversation_id: str | None = None,
) -> None:
    """
    Log a specification query for a product.

    Sample row:
    {
      "product_name":    "PageWriter TC50",
      "user_id":         "a1b2...",
      "conversation_id": "3f2a..."
    }
    """
    if not product_name or product_name.strip() in ("", "N/A"):
        return
    _insert("specification_logs", {
        "product_name":    product_name.strip(),
        "user_id":         user_id or None,
        "conversation_id": conversation_id or None,
    })



# ── 5. Unanswered query log (healthcare-only, deduplicated) ────────────────

# Sources that mean "answered from our internal product knowledge base"
# Any query answered by these sources is KNOWN → do NOT store.
_KB_SOURCES = frozenset({"faiss", "bm25", "pdf", "cache"})

# Sources that are intentional short-circuits (not failures, not gaps)
# Purchase / sample report guards fire BEFORE the search pipeline even runs.
_INTENTIONAL_GUARDS = frozenset({
    "purchase_intent_guard",
    "sample_report_intent_guard",
    "purchase_intent",
    "sample_report_intent",
})

def log_unanswered_query(
    *,
    question:        str,
    answer_source:   str,
    user_id:         str | None = None,
    is_guest:        bool       = False,
    confidence:      float      = 0.0,
    matched_product: str | None = None,
) -> None:
    """
    Store a healthcare/medical query that was NOT answered from the internal
    product knowledge base (FAISS / BM25 / PDF / Cache).

    ── WHAT "UNKNOWN QUERY" MEANS ────────────────────────────────────────────
    NOT "a query that received no response."
    YES "a query answered WITHOUT using our internal product knowledge."

    The chatbot has multiple fallback layers (dynamic search, Wikipedia,
    medical-device assistant canned reply, general healthcare reply, etc.)
    so almost every query DOES receive SOME response.  The Unknown Queries
    admin table captures the KNOWLEDGE GAP — queries our KB cannot serve.

    ── STORAGE DECISION ─────────────────────────────────────────────────────

    SKIP (do not store):
      1. answer_source in _KB_SOURCES            → answered from internal KB
         {"faiss", "bm25", "pdf", "cache"}
      2. answer_source in _INTENTIONAL_GUARDS    → intentional short-circuit
         purchase/sample-report guards: not a knowledge gap, a deliberate block
      3. query does NOT pass _is_healthcare_query → off-topic (weather, sports,
         coding, etc.) — we only track healthcare/medical domain gaps

    STORE (all other healthcare queries not served by the KB):
      - "dynamic_search"     → DuckDuckGo answered it, not our KB
      - "wikipedia"          → Wikipedia answered it, not our KB
      - "fallback"           → Pipeline found nothing at all
      - "fallback_formatter" → Response formatter failed
      - "out_of_scope"       → Guard or orchestrator found no product match
      - any other source     → Unexpected / future source → store as gap

    ── REASON CLASSIFICATION ────────────────────────────────────────────────
      "Web Search Response"      → dynamic_search, wikipedia (web answered it)
      "General Medical Fallback" → fallback, fallback_formatter (no answer at all)
      "Out of Scope"             → out_of_scope (guard or orchestrator rejected it)
      "No Product Match"         → any other non-KB source

    ── DEDUPLICATION ─────────────────────────────────────────────────────────
      Normalise question → query_normalised key.
      Row exists  → increment times_asked + update last_asked_at.
      New row     → INSERT with times_asked = 1.

    ── LOG FORMAT ────────────────────────────────────────────────────────────
      [unknown] query=... | response_source=... | knowledge_used=True/False |
                stored=True/False | times_asked=N
    """
    from datetime import datetime, timezone

    src            = (answer_source or "unknown").lower().strip()
    knowledge_used = src in _KB_SOURCES

    # ── Gate 1: intentional guards — not a knowledge gap ──────────────────
    if src in _INTENTIONAL_GUARDS:
        print(
            f"[unknown] query={question[:70]!r} | response_source={src!r} | "
            f"knowledge_used=N/A | stored=False | times_asked=0  "
            f"(intentional guard — not a knowledge gap)"
        )
        return

    # ── Gate 2: skip KB-answered queries ──────────────────────────────────
    if knowledge_used:
        print(
            f"[unknown] query={question[:70]!r} | response_source={src!r} | "
            f"knowledge_used=True | stored=False | times_asked=0"
        )
        return

    # ── Gate 3: healthcare domain filter ──────────────────────────────────
    # Only track medical/healthcare/device domain gaps.
    # Off-topic queries (weather, sports, coding, etc.) are silently ignored.
    is_medical = _is_healthcare_query(question)
    if not is_medical:
        print(
            f"[unknown] query={question[:70]!r} | response_source={src!r} | "
            f"knowledge_used=False | stored=False | times_asked=0  "
            f"(not a healthcare query)"
        )
        return

    # ── All gates passed: healthcare query + NOT from KB → store it ────────
    # Classify a human-readable reason for the admin table
    if src in {"dynamic_search", "wikipedia"}:
        reason = "Web Search Response"
    elif src in {"fallback", "fallback_formatter"}:
        reason = "General Medical Fallback"
    elif src in {"out_of_scope", "out_of_scope_guard"}:
        reason = "Out of Scope"
    else:
        reason = "No Product Match"

    # ── Deduplication upsert ───────────────────────────────────────────────
    normalised = _normalise(question)
    now_iso    = datetime.now(timezone.utc).isoformat()
    saved      = False
    times      = 0

    try:
        existing = (
            supabase.table("unanswered_queries")
            .select("id, times_asked")
            .eq("query_normalised", normalised)
            .limit(1)
            .execute()
        )

        if existing.data:
            # Row already exists — increment counter
            row_id = existing.data[0]["id"]
            times  = existing.data[0]["times_asked"] + 1
            supabase.table("unanswered_queries").update({
                "times_asked":   times,
                "last_asked_at": now_iso,
                "user_id":       user_id or None,
                "is_guest":      is_guest,
                "updated_at":    now_iso,
            }).eq("id", row_id).execute()
            saved = True
            print(
                f"[unknown] query={question[:70]!r} | response_source={src!r} | "
                f"knowledge_used=False | stored=True(update) | times_asked={times}"
            )
        else:
            # New query — insert fresh row
            times = 1
            supabase.table("unanswered_queries").insert({
                "query":            question.strip(),
                "query_normalised": normalised,
                "user_id":          user_id or None,
                "is_guest":         is_guest,
                "times_asked":      1,
                "reason":           reason,
                "status":           "Pending",
                "first_asked_at":   now_iso,
                "last_asked_at":    now_iso,
                "updated_at":       now_iso,
            }).execute()
            saved = True
            print(
                f"[unknown] query={question[:70]!r} | response_source={src!r} | "
                f"knowledge_used=False | stored=True(insert) | times_asked=1"
            )

    except Exception as exc:
        print(
            f"[unknown] query={question[:70]!r} | response_source={src!r} | "
            f"knowledge_used=False | stored=False | times_asked={times} | "
            f"ERROR={type(exc).__name__}: {exc}"
        )
