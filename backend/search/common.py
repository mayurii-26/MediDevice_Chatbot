"""
search/common.py
Shared types, constants, and utilities used across all search modules.
"""
import re
import random
from dataclasses import dataclass
from typing import Optional

# ── Thresholds ─────────────────────────────────────────────────────────────
FAISS_STRONG_THRESHOLD = 1.2

# ── Category keyword map ───────────────────────────────────────────────────
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "PatientMonitoring": [
        "patient monitor", "ecg machine", "cardiograph", "pagewriter",
        "defibrillator", "heartstart", "efficia", "syringe pump",
        "infusion pump", "ventilator", "trilogy", "fluid warmer",
        "vital signs", "bedside monitor",
    ],
    "Cardiology": [
        "cardiology", "cardiac workstation", "st80i", "stress test",
        "holter", "holter monitor", "abpm", "ambulatory blood pressure",
        "oscar 2", "ecg", "electrocardiogram", "arrhythmia",
        "heart monitor", "pagewriter", "tc50", "tc10", "tc35",
    ],
    "Anaesthesia": [
        "anaesthesia", "anesthesia", "laryngoscope", "resuscitator",
        "ambu", "e-flo", "bpl", "video laryngoscope", "intubation",
        "airway management", "anaesthetic",
    ],
    "OTComplex": [
        "surgery light", "ot table", "operating theatre", "surgical table",
        "surgical light", "operating room", "operation theatre",
    ],
    "MotherChildCare": [
        "neonatal", "infant", "radiant warmer", "phototherapy",
        "bubble cpap", "cpap", "pulse oximeter", "newborn",
        "premature", "jaundice", "nicu", "draeger", "paediatric",
        "pediatric", "mother", "fetal", "maternity",
    ],
}

# ── Result dataclass ───────────────────────────────────────────────────────
@dataclass
class SearchResult:
    chunks:           list[str]
    source:           str           = "faiss"
    matched_product:  Optional[str] = None
    matched_category: Optional[str] = None
    confidence:       float         = 0.0
    intent:           str           = "product_query"
    pdf_chunks:       list[dict]    = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.pdf_chunks is None:
            self.pdf_chunks = []

# ── Query normalisation ────────────────────────────────────────────────────
_NORMALISE_MAP = [
    (r"\bpage\s+writer\b",  "pagewriter"),
    (r"\bheart\s+start\b",  "heartstart"),
    (r"\btc\s+50\b",        "tc50"),
    (r"\btc\s+35\b",        "tc35"),
    (r"\btc\s+10\b",        "tc10"),
    (r"\bdfm\s+100\b",      "dfm100"),
    (r"\bst\s+80i?\b",      "st80i"),
    (r"\boscar\s+2\b",      "oscar 2"),
]

def normalise_query(query: str) -> str:
    q = query.lower().strip()
    for pattern, replacement in _NORMALISE_MAP:
        q = re.sub(pattern, replacement, q)
    return q

# ── Shared helpers ─────────────────────────────────────────────────────────
def extract_product_name(chunk: str) -> Optional[str]:
    m = re.search(r"Product Name:\s*(.+)", chunk)
    return m.group(1).strip() if m else None

def extract_category(chunk: str) -> Optional[str]:
    m = re.search(r"Category:\s*(.+)", chunk)
    return m.group(1).strip() if m else None

def detect_category_from_query(query: str) -> str:
    q = query.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            return category
    return "Unknown"

def deduplicate(chunks: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for chunk in chunks:
        key = chunk.strip()
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
    return unique


# Category priority: more specific wins over broader
_CATEGORY_PRIORITY = {
    "Cardiology": 1,
    "Anaesthesia": 1,
    "OTComplex": 1,
    "MotherChildCare": 1,
    "PatientMonitoring": 2,   # broadest — lowest priority
    "Unknown": 3,
}


def deduplicate_by_product(chunks: list[str]) -> list[str]:
    """
    Ensure each product name appears at most once.
    When multiple chunks share the same Product Name:
      - keep the chunk whose Category has the highest priority (lowest number)
      - append any unique content lines from secondary chunks
    Chunks without a Product Name are kept as-is.
    """
    # Separate named vs unnamed chunks
    named: dict[str, list[str]] = {}   # product_name -> [chunk, ...]
    unnamed: list[str] = []

    for chunk in chunks:
        product = extract_product_name(chunk)
        if product:
            named.setdefault(product, []).append(chunk)
        else:
            unnamed.append(chunk)

    result: list[str] = []
    for product, product_chunks in named.items():
        if len(product_chunks) == 1:
            result.append(product_chunks[0])
            continue

        # Pick the chunk with the best (lowest priority number) category
        def _priority(c: str) -> int:
            cat = extract_category(c) or "Unknown"
            return _CATEGORY_PRIORITY.get(cat, 3)

        best = min(product_chunks, key=_priority)
        best_lines = set(best.splitlines())

        # Collect unique content lines from the other chunks
        extras: list[str] = []
        for other in product_chunks:
            if other is best:
                continue
            for line in other.splitlines():
                line = line.strip()
                if line and line not in best_lines and not line.startswith("Category:"):
                    best_lines.add(line)
                    extras.append(line)

        merged = best.rstrip()
        if extras:
            merged += "\n" + "\n".join(extras)
        result.append(merged)

    return result + unnamed

def faiss_confidence(distance: float) -> float:
    normalised = min(distance / FAISS_STRONG_THRESHOLD, 1.0)
    return round(1.0 - (normalised * 0.05), 2)

def web_confidence() -> float:
    return round(random.uniform(0.70, 0.85), 2)
