"""
intent_detector.py
Classifies a user query into one of six intent types using keyword rules.
No ML model — pure regex/keyword matching, runs in microseconds.
"""
import re

# Intent constants
PRODUCT_QUERY      = "product_query"
FEATURE_QUERY      = "feature_query"
SPECIFICATION_QUERY = "specification_query"
COMPARISON_QUERY   = "comparison_query"
CATEGORY_QUERY     = "category_query"
GENERAL_MEDICAL    = "general_medical_query"
PURCHASE_INTENT    = "purchase_intent"  # Phase 5.2 — bypasses all retrieval
SAMPLE_REPORT_INTENT = "sample_report_intent"  # bypasses all retrieval — returns canned reply

# ── Purchase / Price / Quote keywords ─────────────────────────────────────
# Mirrors purchaseIntentDetector.js on the frontend so both layers agree.
_PURCHASE_KEYWORDS = [
    # buying
    "buy", "purchase", "buying", "purchasing",
    "procure", "procurement", "acquire", "acquisition",
    # pricing
    "price", "pricing", "cost", "costs", "costing",
    "rate", "rates", "tariff", "fee", "fees",
    "charges", "charge", "expensive", "affordable", "budget",
    # quotation
    "quote", "quotes", "quotation", "quotations", "rfq",
    "request for quote", "request a quote", "get a quote", "send a quote",
    # ordering
    "order", "orders", "ordering", "place an order", "place order",
    # sales / commercial
    "sales", "sale", "contact sales", "sales team",
    "sales rep", "sales representative", "commercial",
    # demo
    "demo", "request demo", "request a demo",
    "book a demo", "schedule a demo", "free demo",
    # distribution
    "dealer", "dealers", "dealership",
    "distributor", "distributors", "distribution",
    "reseller", "resellers", "vendor", "vendors",
    "supplier", "suppliers",
    # availability / stock
    "availability", "in stock", "out of stock", "stock",
    # invoice / payment
    "invoice", "invoicing", "payment", "payments",
    "pay", "checkout", "billing",
]

# Compiled regex: phrase keywords use simple match, single words use \b…\b.
_PURCHASE_RE = re.compile(
    "|".join(
        re.escape(kw) if " " in kw else rf"\b{re.escape(kw)}\b"
        for kw in _PURCHASE_KEYWORDS
    ),
    re.IGNORECASE,
)


def is_purchase_intent(query: str) -> bool:
    """
    Returns True when the query contains a purchase / pricing / quote keyword.
    Runs BEFORE the retrieval pipeline — no FAISS / BM25 / Wikipedia / Gemini
    should execute if this returns True.
    """
    if not query or not isinstance(query, str):
        return False
    return bool(_PURCHASE_RE.search(query.strip()))


# ── Sample Report Request detection ───────────────────────────────────────
# Mirrors sampleReportDetector.js on the frontend so both layers agree.
_SAMPLE_REPORT_PHRASES = [
    # "sample" combinations
    "sample report",
    "sample ecg report",
    "sample ecg",
    "sample output",
    "sample patient report",
    "sample pdf",
    "sample print",
    "sample printout",
    "sample result",
    "sample test report",
    "sample document",
    "sample reading",
    # "example" combinations
    "example report",
    "example ecg",
    "example ecg report",
    "example output",
    "example patient report",
    "example pdf",
    "example result",
    # "report format" combinations
    "report format",
    "ecg report format",
    "report template",
    "report layout",
    "report structure",
    "report style",
    # "ECG print" combinations
    "ecg print sample",
    "ecg printout sample",
    "ecg print example",
    "ecg printout",
    "ecg print",
    # "PDF report" combinations
    "pdf report sample",
    "pdf report example",
    "pdf sample",
    "pdf example",
    "pdf output",
    # generic demo/preview report requests
    "demo report",
    "report preview",
    "report demo",
    "report specimen",
    "specimen report",
]

_SAMPLE_REPORT_RE = re.compile(
    "|".join(
        re.escape(phrase) for phrase in _SAMPLE_REPORT_PHRASES
    ),
    re.IGNORECASE,
)


def is_sample_report_intent(query: str) -> bool:
    """
    Returns True when the query is requesting a sample / example report.
    Runs BEFORE the retrieval pipeline — no FAISS / BM25 / Wikipedia / Gemini
    should execute if this returns True, and the response must NOT be cached.
    """
    if not query or not isinstance(query, str):
        return False
    return bool(_SAMPLE_REPORT_RE.search(query.strip()))


# ── Out-of-scope detection (Phase 5.3) ────────────────────────────────────
# Two-pass: ALLOWLIST first (medical terms always pass), BLOCKLIST second.
# Mirrors outOfScopeDetector.js on the frontend so both layers agree.

OUT_OF_SCOPE_INTENT = "out_of_scope"  # returned as source when guard fires

# ALLOWLIST — any query with a medical / healthcare term bypasses blocking.
_OOS_ALLOWLIST = [
    # Philips brand & products
    "philips", "pagewriter", "heartstart", "efficia", "trilogy",
    "tc50", "tc35", "tc10", "frx", "hs1", "dfm100", "st80i", "oscar 2",
    "cardiac workstation",
    # Device categories
    "medical device", "medical equipment", "medical technology", "healthcare",
    "patient monitor", "patient monitoring", "bedside monitor",
    "ecg", "ekg", "electrocardiogram", "electrocardiograph",
    "defibrillator", "aed", "automated external defibrillator",
    "holter", "holter monitor", "abpm", "ambulatory blood pressure",
    "pulse oximeter", "spo2", "oximetry", "oxygen saturation",
    "ventilator", "ventilators", "cpap", "bipap", "respiratory", "respiration",
    "infusion pump", "syringe pump",
    "anaesthesia", "anesthesia", "anaesthetic", "anesthetic",
    "laryngoscope", "video laryngoscope",
    "ctg", "cardiotocograph", "fetal monitor",
    "phototherapy", "phototherapy lamp", "radiant warmer",
    "surgical", "surgery", "operating theatre", "ot complex",
    "neonatal", "incubator", "nicu", "picu",
    "cardiology", "cardiac", "cardio",
    # Medical concepts
    "clinical", "diagnosis", "diagnostic", "treatment", "therapy",
    "hospital", "clinic", "icu", "critical care",
    "blood pressure", "heart rate",
    "waveform", "arrhythmia", "ecg lead", "electrode",
    "intubation", "airway", "ventilation", "tidal volume",
    "cardiac arrest", "defibrillation", "resuscitation", "cpr",
    "stress test", "telemetry",
    "medical", "health", "biomedical",
    # Anatomy terms that could appear in non-medical blocklist queries
    "elbow", "knee", "shoulder", "spine", "fracture", "tendon", "ligament",
    "joint", "bone", "nerve", "tissue", "organ", "muscle",
    "wound", "injury", "sprain", "strain", "pain relief",
]

# Compiled allowlist regex.
_OOS_ALLOW_RE = re.compile(
    "|".join(
        re.escape(t) if " " in t else rf"\b{re.escape(t)}\b"
        for t in _OOS_ALLOWLIST
    ),
    re.IGNORECASE,
)

# BLOCKLIST — off-topic topics; only checked when allowlist does NOT match.
_OOS_BLOCKLIST = [
    # Programming / tech
    r"\bpython\b", r"\bjavascript\b", r"\btypescript\b", r"\bjava\b",
    r"\bkotlin\b", r"\bswift\b", r"\bgolang\b", r"\brust\b",
    r"\bruby\b", r"\bphp\b", r"\bperl\b",
    r"\breact\b", r"\bangular\b", r"\bvue\.?js\b",
    r"\bdjango\b", r"\bflask\b",
    r"\bnodejs\b", r"\bnode\.js\b",
    r"\balgorithm\b", r"\bdata structure\b", r"\blinked list\b",
    r"\bbinary tree\b", r"\bsorting algorithm\b", r"\brecursion\b",
    r"\bfibonacci\b", r"\bhtml\b", r"\bcss\b",
    r"\bsql\b", r"\bnosql\b", r"\bmongodb\b", r"\bpostgresql\b",
    r"\bdocker\b", r"\bkubernetes\b",
    r"\bmachine learning\b", r"\bdeep learning\b", r"\bneural network\b",
    r"\bchatgpt\b", r"\bopenai\b", r"\bgenerative ai\b",
    r"\bblockchain\b", r"\bcryptocurrency\b", r"\bbitcoin\b",
    r"\bethereum\b", r"\bnft\b",
    r"\bcoding\b", r"\bprogramming\b",
    r"\bdebug\b", r"\bcompile\b", r"\bruntime error\b",
    r"\bgithub\b", r"\bgitlab\b", r"\bgit commit\b",
    r"\bsmartphone\b", r"\biphone\b", r"\bvideo game\b",
    r"\besports\b", r"\bminecraft\b", r"\bfortnite\b", r"\bpubg\b",
    # Cricket / sports
    r"\bcricket\b", r"\bipl\b", r"\bt20\b",
    r"\bbatsman\b", r"\bbowler\b", r"\bwicket\b",
    r"\bfootball\b", r"\bsoccer\b", r"\bfifa\b", r"\bpremier league\b",
    r"\bbasketball\b", r"\bnba\b", r"\btennis\b", r"\bwimbledon\b",
    r"\bbadminton\b",
    r"\bolympics\b", r"\bworld cup\b", r"\bstadium\b",
    # Movies / entertainment
    r"\bmovie\b", r"\bfilm\b", r"\bcinema\b", r"\bbollywood\b",
    r"\bhollywood\b", r"\bnetflix\b", r"\bamazon prime\b",
    r"\bactor\b", r"\bactress\b", r"\bdirector\b", r"\bbox office\b",
    r"\btv show\b", r"\bweb series\b",
    r"\bmusic\b", r"\bsong\b", r"\balbum\b", r"\bconcert\b",
    r"\bspotify\b", r"\bsinger\b", r"\brapper\b",
    r"\banime\b", r"\bmanga\b",
    # Politics
    r"\bpolitics\b", r"\bpolitical party\b", r"\belection\b",
    r"\bvote\b", r"\breferendum\b",
    r"\bparliament\b", r"\bsenate\b", r"\bcongress\b",
    r"\bgovernment policy\b", r"\bdiplomacy\b",
    r"\bdemocrat\b", r"\brepublican\b",
    # General knowledge / trivia
    r"\bcapital of\b", r"\bpresident of\b", r"\bpopulation of\b",
    r"\bhistory of\b", r"\bwho invented\b",
    r"\bgeography\b", r"\bcontinent\b",
    r"\bmathematics\b", r"\bcalculus\b", r"\balgebra\b",
    r"\bperiodic table\b", r"\bblack hole\b",
    r"\bspeed of light\b", r"\bexplain gravity\b",
    # Jokes
    r"\btell me a joke\b", r"\bfunny joke\b", r"\bknock knock\b",
    r"\briddle\b",
    # Weather
    r"\bweather\b", r"\bforecast\b", r"\brain today\b",
    r"\bhumidity\b", r"\bsnowfall\b",
    # Shopping / eCommerce
    r"\bamazon\b", r"\bflipkart\b", r"\bebay\b", r"\bshopify\b",
    r"\bdiscount code\b", r"\bcoupon\b", r"\bcashback\b",
    r"\bfashion\b", r"\bclothing\b", r"\bjewellery\b", r"\bmakeup\b",
    r"\brestaurant\b", r"\bfood delivery\b", r"\bswiggy\b",
    r"\bzomato\b",
    # Finance
    r"\bstock market\b", r"\bsensex\b", r"\bnifty\b",
    r"\bshare price\b", r"\bmutual funds?\b", r"\bforex\b",
    r"\btrading\b",
    # Travel
    r"\bflight booking\b", r"\bbook a flight\b", r"\bhotel booking\b",
    r"\btourist spot\b", r"\bvisa application\b",
    # Social media
    r"\binstagram\b", r"\btwitter\b", r"\bfacebook\b",
    r"\btiktok\b", r"\bsnapchat\b",
    r"\bviral post\b", r"\bmeme\b",
    # Food
    r"\brecipe\b", r"\bhow to cook\b", r"\bbiryani\b",
    r"\bcalories in\b",
    # Astrology
    r"\bhoroscope\b", r"\bzodiac sign\b", r"\bastrology\b",
]

# Compiled blocklist regex.
_OOS_BLOCK_RE = re.compile(
    "|".join(_OOS_BLOCKLIST),
    re.IGNORECASE,
)


def is_out_of_scope(query: str) -> bool:
    """
    Returns True when the query is unrelated to medical devices / healthcare.

    Pass 1 — allowlist:  any medical term present → return False immediately.
    Pass 2 — blocklist:  off-topic keyword found   → return True.
    Default             → return False (unknown queries go to the pipeline).
    """
    if not query or not isinstance(query, str):
        return False
    q = query.strip()
    # Medical allowlist wins — never block a legitimate healthcare query
    if _OOS_ALLOW_RE.search(q):
        return False
    # Check off-topic blocklist
    return bool(_OOS_BLOCK_RE.search(q))


def is_medical_query(query: str) -> bool:
    """
    Returns True when the query has sufficient medical/healthcare relevance
    to justify a dynamic web search fallback.

    Used by the orchestrator to guard the dynamic search step:
      - If FAISS+BM25 both returned nothing AND this returns False,
        dynamic search is skipped and the out-of-scope reply is returned.
      - Mirrors the allowlist from is_out_of_scope() but as a positive gate.

    Conservative by design — when in doubt returns False so unrelated
    queries like "what is car?" never reach DuckDuckGo/Wikipedia.
    """
    if not query or not isinstance(query, str):
        return False
    q = query.strip()
    # Reuse the OOS allowlist — if a medical term is present, it's medical
    return bool(_OOS_ALLOW_RE.search(q))

# ── Keyword patterns (checked in priority order) ───────────────────────────

_COMPARISON_PATTERNS = [
    r"\bcompare\b", r"\bvs\b", r"\bversus\b", r"\bdifference between\b",
    r"\bwhich is better\b", r"\bcomparison\b",
]

_FEATURE_PATTERNS = [
    r"\bfeatures?\b", r"\bwhat (can|does) .+ (do|offer)\b",
    r"\bcapabilit(y|ies)\b", r"\bfunctions?\b", r"\bbenefit",
]

_SPEC_PATTERNS = [
    r"\bspecification", r"\bspecs?\b", r"\bdimension", r"\bweight\b",
    r"\bdisplay size\b", r"\btechnical detail", r"\bparameter",
]

_CATEGORY_PATTERNS = [
    r"\bcategor(y|ies)\b",
    r"\bpatient monitoring (devices?|equipment|systems?)\b",
    r"\bcardiology (devices?|equipment|systems?|products?)\b",
    r"\banaesthesia (devices?|equipment|systems?|products?)\b",
    r"\bot (complex|equipment|devices?)\b",
    r"\bmother (and )?child( care)?\b",
    r"\bneonatal (devices?|equipment|care)\b",
    r"\btell me about .*(monitoring|cardiology|anaesthesia|surgical|neonatal)\b",
    r"\bwhat (devices?|equipment|products?) .*(monitoring|cardiology|anaesthesia)\b",
    r"\boverview of\b",
    r"\blist of (devices?|products?|equipment)\b",
    r"\btypes of (devices?|equipment|monitors?)\b",
]

_GENERAL_MEDICAL_TERMS = {
    # Pure medical concepts — no Philips catalog entry, route to web search
    "cardiac arrest", "arrhythmia",
    "jaundice treatment", "phototherapy",
    "intubation", "defibrillation",
    "electrocardiography", "oximetry",
    "ambulatory blood pressure", "stress testing",
    "ventilation",
    # OT / surgical equipment not in catalog — route to general_medical → Wikipedia
    "surgery lights", "surgical lights", "operating lights", "operating theatre lights",
    "surgical lamp", "operation theatre lights", "ot lights",
    "surgical table", "operating table",
    "surgical equipment", "operation theatre equipment",
    # Devices that are NOT in the Philips FAISS catalog.
    # If FAISS is asked about these it returns a wrong product (high similarity
    # to Trilogy/DFM100/Oscar due to shared clinical vocabulary).
    # Route to general_medical so Wikipedia/web gives a correct answer.
    "holter monitor", "holter",
    "bubble cpap", "bubble c-pap",
    "infusion pump", "infusion pumps",
    "syringe pump", "syringe pumps",
    "patient monitoring device", "patient monitoring equipment",
}

# Medical device names that exist in (or are closely related to) our catalog.
# Queries containing these should route to product_query so FAISS can match them.
_DEVICE_NAME_TERMS = {
    "ecg", "electrocardiogram",
    "aed", "automated external defibrillator",
    "defibrillator",
    "holter", "holter monitor",
    "abpm",
    "cpap",
    "ventilator",
    "pulse oximeter", "spo2",
    "infusion pump", "syringe pump",
    "laryngoscope", "video laryngoscope",
    "patient monitor", "bedside monitor",
    "ctg", "cardiotocograph",
    "stress test",
    "phototherapy lamp", "radiant warmer",
    "anaesthesia machine", "anaesthesia workstation",
    "anesthesia machine",
}

# Known product name fragments — presence means product_query, not general
_KNOWN_PRODUCT_FRAGMENTS = [
    "pagewriter", "tc50", "tc35", "tc10",
    "heartstart", "frx", "hs1",
    "efficia", "dfm100",
    "st80i",
    "oscar 2",
    "cardiac workstation",
    "trilogy",
]


def detect_intent(query: str) -> str:
    """
    Returns one of the six intent constants.
    Evaluation order:
      1. comparison  (strongest signal — always explicit)
      2. feature     (explicit "features of X")
      3. specification (explicit "specs of X")
      4. category    (broad device category, no specific product)
      5. general_medical (medical concept without a known product)
      6. product_query (default — specific product or anything else)
    """
    q = query.lower().strip()

    # 1. Comparison
    if any(re.search(p, q) for p in _COMPARISON_PATTERNS):
        return COMPARISON_QUERY

    # 2. Feature
    if any(re.search(p, q) for p in _FEATURE_PATTERNS):
        return FEATURE_QUERY

    # 3. Specification
    if any(re.search(p, q) for p in _SPEC_PATTERNS):
        return SPECIFICATION_QUERY

    # 4. Category — only if no specific product name is mentioned
    has_product = any(frag in q for frag in _KNOWN_PRODUCT_FRAGMENTS)
    if not has_product and any(re.search(p, q) for p in _CATEGORY_PATTERNS):
        return CATEGORY_QUERY

    # 5. General medical concept — only if no specific product name
    if not has_product:
        for term in _GENERAL_MEDICAL_TERMS:
            if term in q:
                return GENERAL_MEDICAL

        # Generic device-concept queries with no product name → general_medical
        # so Wikipedia/web explains the concept rather than FAISS returning
        # whichever product happens to be semantically closest.
        # "ecg" / "electrocardiogram" alone (without a model number) is a
        # concept question: "Tell me about ECG", "What is an ECG" etc.
        _concept_only_terms = {
            "ecg", "electrocardiogram", "ekg",
            "defibrillator", "aed",
            "ventilator", "cpap",
            "pulse oximeter",
        }
        # Check: no known product fragment AND query is a concept question
        _concept_triggers = ("tell me about", "what is", "explain", "describe",
                              "how does", "what are", "overview of")
        _is_concept_q = any(t in q for t in _concept_triggers)
        if _is_concept_q:
            for term in _concept_only_terms:
                if term in q:
                    return GENERAL_MEDICAL

        # Device names in our catalog → product_query so FAISS can match them
        for term in _DEVICE_NAME_TERMS:
            if term in q:
                return PRODUCT_QUERY

    # 6. Default: treat as a product query
    return PRODUCT_QUERY
