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
    "ecg", "electrocardiogram", "electrocardiography",
    "aed", "automated external defibrillator",
    "defibrillator", "defibrillation",
    "holter", "holter monitor",
    "abpm", "ambulatory blood pressure",
    "cpap", "ventilator", "ventilation",
    "pulse oximeter", "oximetry", "spo2",
    "infusion pump", "syringe pump",
    "stress test", "stress testing",
    "cardiac arrest", "arrhythmia",
    "phototherapy", "jaundice treatment",
    "laryngoscope", "intubation",
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

    # 6. Default: treat as a product query
    return PRODUCT_QUERY
