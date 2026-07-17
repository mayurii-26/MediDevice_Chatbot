"""
fallback_formatter.py

Structures retrieval chunks into readable markdown when Gemini is unavailable.

ROOT CAUSE FIX (2026-07-03)
---------------------------
The chunks that reach this module have ALREADY been formatted by
_format_product_chunk() in app.py.  Their structure is:

    📦 Product

    PageWriter TC50

    Category
    Cardiology

    Summary

    <description text>

    Features

    - Feature A: detail
    - Feature B: detail

    Specifications

    - Spec A: value
    - Spec B: value

NOT the raw "Product Name: X\nCategory: Y\n..." format the old extractors
assumed.  This caused every field extractor to return None/[] and produced
responses with empty "Product:", "Category:", "Description:" headings.

All field extractors have been rewritten to parse the formatted structure.
Duplicate _MEDICAL_CONCEPTS / format_general_medical_answer definitions
have been removed (only one of each now exists).
"""

import re
from typing import Optional


# ── Chunk field extractors ────────────────────────────────────────────────
# The chunks we receive look like:
#
#   📦 Product
#
#   PageWriter TC50
#
#   Category
#   Cardiology
#
#   Summary
#
#   <multi-line description>
#
#   Features
#
#   - Feature Name: detail
#
#   Specifications
#
#   - Spec Name: value
#
# We parse this structure using section-based extraction.

def _get_section(chunk: str, header: str) -> str:
    """
    Extract the text content of a named section.

    Looks for a line containing only `header` (case-insensitive),
    then collects everything until the next DIFFERENT section header or
    end of chunk.  The current header is excluded from the stop-list so
    we do not accidentally produce a zero-length match.
    Returns stripped multi-line content, or "".
    """
    # Build a stop list that excludes the current header itself
    all_headers = ["Category", "Summary", "Features", "Specifications", "Source", "Highlights"]
    stop_headers = [h for h in all_headers if h.lower() != header.lower()]
    stop_pattern = "|".join(re.escape(h) for h in stop_headers)

    pattern = re.compile(
        rf"(?:^|\n)\s*{re.escape(header)}\s*\n(.*?)(?=\n\s*(?:{stop_pattern})\s*\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(chunk)
    if m:
        return m.group(1).strip()
    return ""


def _product_name(chunk: str) -> str:
    """
    Extract the product name from a formatted chunk.

    The name appears after the '📦 Product' header and before the next
    section header.
    """
    # Formatted chunks: "📦 Product\n\n<name>\n\nCategory\n..."
    m = re.search(
        r"📦\s*Product\s*\n+(.*?)(?=\n\n|\nCategory|\nSummary|\nFeatures|\nSpecifications|$)",
        chunk, re.IGNORECASE | re.DOTALL
    )
    if m:
        name = m.group(1).strip()
        if name:
            return name

    # Raw chunks: "Product Name: PageWriter TC50"
    m2 = re.search(r"Product Name\s*:\s*(.+)", chunk)
    if m2:
        return m2.group(1).strip()

    return ""


def _category(chunk: str) -> str:
    """Extract category from formatted or raw chunk."""
    # Formatted: "Category\nCardiology"
    m = re.search(r"\bCategory\s*\n([^\n]+)", chunk, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Raw: "Category: Cardiology"
    m2 = re.search(r"Category\s*:\s*(.+)", chunk)
    if m2:
        return m2.group(1).strip()
    return ""


def _description(chunk: str) -> str:
    """Extract description from Summary section (formatted) or Description: (raw)."""
    # Formatted: Summary section
    summary = _get_section(chunk, "Summary")
    if summary:
        return summary
    # Raw: "Description: ..."
    m = re.search(r"Description\s*:\s*(.+)", chunk, re.DOTALL)
    if m:
        return m.group(1).strip()[:500]
    return ""


def _feature_lines(chunk: str) -> list[str]:
    """
    Extract bullet feature lines from the Features section.

    Returns a list of plain strings (without the leading "- ").
    Each string is the full feature text, e.g. "Feature Name: detail".
    """
    # Formatted: "Features\n\n- Item\n- Item\n\nSpecifications..."
    features_section = _get_section(chunk, "Features")
    if features_section:
        lines = []
        for line in features_section.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                lines.append(stripped[2:].strip())
            elif stripped:
                lines.append(stripped)
        return [l for l in lines if l]

    # Raw: "Features:\n- Item\n- Item"
    in_features = False
    results = []
    for line in chunk.splitlines():
        if re.match(r"^\s*Features\s*:", line, re.IGNORECASE):
            in_features = True
            continue
        if in_features and re.match(r"^\s*Specifications\s*", line, re.IGNORECASE):
            break
        if in_features:
            stripped = line.strip()
            if stripped.startswith("- "):
                results.append(stripped[2:].strip())
    return results


def _spec_lines(chunk: str) -> list[str]:
    """
    Extract bullet spec lines from the Specifications section.

    Returns a list of plain strings (without the leading "- ").
    """
    specs_section = _get_section(chunk, "Specifications")
    if specs_section:
        lines = []
        for line in specs_section.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                lines.append(stripped[2:].strip())
            elif stripped:
                lines.append(stripped)
        return [l for l in lines if l]

    # Raw fallback
    in_specs = False
    results = []
    for line in chunk.splitlines():
        if re.match(r"^\s*Specifications\s*:", line, re.IGNORECASE):
            in_specs = True
            continue
        if in_specs:
            stripped = line.strip()
            if stripped.startswith("- "):
                results.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("-"):
                break
    return results


# ── Public formatters ─────────────────────────────────────────────────────

def format_product_answer(chunks: list[str]) -> str:
    """Overview for product_query intent."""
    if not chunks:
        return "No product information available."

    chunk    = chunks[0]
    product  = _product_name(chunk)
    category = _category(chunk)
    desc     = _description(chunk)
    features = _feature_lines(chunk)

    lines = ["## 📦 Product Information\n"]

    if product:
        lines.append(f"**{product}**")
    if category:
        lines.append(f"*Category: {category}*")

    if desc:
        lines.append(f"\n### Overview\n{desc}")

    if features:
        lines.append("\n### Key Features")
        for feat in features[:6]:
            lines.append(f"- {feat}")

    specs = _spec_lines(chunk)
    if specs:
        lines.append("\n### Specifications")
        for spec in specs[:6]:
            lines.append(f"- {spec}")

    if len(lines) <= 2:
        return "No product information is currently available for this query."

    print("[fallback] product formatter used")
    return "\n".join(lines)


def format_feature_answer(chunks: list[str]) -> str:
    """Bullet-list features for feature_query intent."""
    if not chunks:
        return "No feature information available."

    chunk    = chunks[0]
    product  = _product_name(chunk)
    features = _feature_lines(chunk)

    header = f"## Key Features"
    if product:
        header = f"## Key Features — {product}"

    lines = [f"{header}\n"]

    if features:
        for feat in features:
            lines.append(f"- {feat}")
        # Clinical benefit sentence
        lines.append(f"\nThese features make the {product or 'device'} well-suited for professional clinical environments.")
    else:
        desc = _description(chunk)
        if desc:
            lines.append(desc)
        else:
            lines.append("Detailed feature information is not currently available for this product.")

    print("[fallback] feature formatter used")
    return "\n".join(lines)


def format_specification_answer(chunks: list[str]) -> str:
    """Specification bullet list for specification_query intent."""
    if not chunks:
        return "No specification information available."

    chunk   = chunks[0]
    product = _product_name(chunk)
    specs   = _spec_lines(chunk)

    header = "## Technical Specifications"
    if product:
        header = f"## Technical Specifications — {product}"

    lines = [f"{header}\n"]

    if specs:
        for spec in specs:
            lines.append(f"- {spec}")
    else:
        lines.append("Detailed specifications are not currently available for this product.")
        desc = _description(chunk)
        if desc:
            lines.append(f"\n**Overview:** {desc}")

    print("[fallback] specification formatter used")
    return "\n".join(lines)


def format_category_answer(chunks: list[str]) -> str:
    """Device list for category_query intent."""
    if not chunks:
        return "No category information available."

    seen: set[str]           = set()
    category: Optional[str]  = None
    products: list[tuple[str, str]] = []   # (name, description)

    for chunk in chunks:
        cat  = _category(chunk)
        name = _product_name(chunk)
        desc = _description(chunk)

        if cat and not category:
            category = cat
        if name and name not in seen:
            seen.add(name)
            short_desc = (desc[:120] + "…") if len(desc) > 120 else desc
            products.append((name, short_desc))

    lines = [f"## 🏥 {category or 'Medical'} Devices\n"]

    if products:
        lines.append("This category includes the following devices:\n")
        for name, desc in products:
            lines.append(f"**{name}**")
            if desc:
                lines.append(f"{desc}\n")
    else:
        lines.append("Device information for this category is not currently available.")

    print("[fallback] category formatter used")
    return "\n".join(lines)


def format_comparison_answer(chunks: list[str]) -> str:
    """Markdown comparison table for comparison_query intent."""
    if not chunks:
        return "No product information available for comparison."

    products: list[dict] = []
    seen: set[str] = set()

    for chunk in chunks:
        name = _product_name(chunk)
        if not name or name in seen:
            continue
        seen.add(name)
        products.append({
            "name":     name,
            "category": _category(chunk) or "—",
            "desc":     (_description(chunk) or "—")[:150],
            "features": _feature_lines(chunk),
            "specs":    _spec_lines(chunk),
        })
        if len(products) == 2:
            break

    if len(products) < 2:
        # Only one product retrieved — show what we have with a note
        if products:
            p = products[0]
            lines = [f"## 📊 Product Comparison\n"]
            lines.append(f"⚠️ Only **{p['name']}** was found. Information for the second product is not available.\n")
            lines.append(f"**{p['name']}**")
            if p["desc"] and p["desc"] != "—":
                lines.append(f"\n**Overview:** {p['desc']}")
            if p["features"]:
                lines.append("\n**Key Features:**")
                for f in p["features"][:5]:
                    lines.append(f"- {f}")
            print("[fallback] comparison formatter used (single product)")
            return "\n".join(lines)
        return format_product_answer(chunks)

    p1, p2 = products[0], products[1]

    lines = ["## 📊 Product Comparison\n"]
    lines.append(f"| Attribute | {p1['name']} | {p2['name']} |")
    lines.append("|---|---|---|")
    lines.append(f"| Category | {p1['category']} | {p2['category']} |")

    # Description row (truncated for table)
    d1 = (p1['desc'][:100] + "…") if len(p1['desc']) > 100 else p1['desc']
    d2 = (p2['desc'][:100] + "…") if len(p2['desc']) > 100 else p2['desc']
    lines.append(f"| Overview | {d1} | {d2} |")

    # Feature rows
    max_f = max(len(p1["features"]), len(p2["features"]))
    for i in range(min(max_f, 5)):
        f1 = p1["features"][i] if i < len(p1["features"]) else "—"
        f2 = p2["features"][i] if i < len(p2["features"]) else "—"
        lines.append(f"| Feature {i+1} | {f1} | {f2} |")

    # Spec rows
    max_s = max(len(p1["specs"]), len(p2["specs"]))
    for i in range(min(max_s, 4)):
        s1 = p1["specs"][i] if i < len(p1["specs"]) else "—"
        s2 = p2["specs"][i] if i < len(p2["specs"]) else "—"
        lines.append(f"| Spec {i+1} | {s1} | {s2} |")

    lines.append(f"\n### Summary\n{p1['name']} and {p2['name']} are both professional medical devices. "
                 f"Refer to the table above for a direct feature and specification comparison.")

    print("[fallback] comparison formatter used")
    return "\n".join(lines)


# ── Medical concept knowledge map ─────────────────────────────────────────
_MEDICAL_CONCEPTS: dict[str, dict] = {
    "ecg": {
        "name": "Electrocardiogram (ECG)",
        "explanation": "An ECG is a non-invasive diagnostic test that records the electrical activity of the heart over time using electrodes placed on the skin.",
        "purpose": "Detect arrhythmias, heart attacks, conduction abnormalities, and assess overall cardiac health.",
        "clinical_use": "Used in emergency departments, cardiology clinics, ICUs, ambulances, and routine health check-ups.",
        "related_products": ["PageWriter TC50", "PageWriter TC35", "PageWriter TC10", "Cardiac Workstation 7000"],
    },
    "electrocardiogram": {
        "name": "Electrocardiogram (ECG / EKG)",
        "explanation": "An electrocardiogram records the heart's electrical impulses to reveal information about heart rate, rhythm, and structure.",
        "purpose": "Diagnose cardiac conditions including myocardial infarction, atrial fibrillation, and ventricular hypertrophy.",
        "clinical_use": "Standard in hospitals, clinics, and pre-operative assessments worldwide.",
        "related_products": ["PageWriter TC50", "PageWriter TC35", "PageWriter TC10"],
    },
    "arrhythmia": {
        "name": "Cardiac Arrhythmia",
        "explanation": "An arrhythmia is an irregular heartbeat — the heart may beat too fast (tachycardia), too slow (bradycardia), or with an irregular rhythm. ECG is the primary tool for detection.",
        "purpose": "Identify abnormal electrical patterns in the heart that can lead to stroke, heart failure, or sudden cardiac death.",
        "clinical_use": "Diagnosed via resting ECG, Holter monitoring, or stress testing in cardiology clinics and emergency departments.",
        "related_products": ["PageWriter TC50", "PageWriter TC35", "PageWriter TC10"],
    },
    "aed": {
        "name": "Automated External Defibrillator (AED)",
        "explanation": "An AED is a portable device that automatically diagnoses life-threatening cardiac arrhythmias and delivers an electric shock to restore normal heart rhythm.",
        "purpose": "Treat sudden cardiac arrest (SCA) in out-of-hospital or public settings.",
        "clinical_use": "Public access defibrillation programmes, first responders, schools, airports, and workplaces.",
        "related_products": ["HeartStart FRx AED", "HeartStart HS1"],
    },
    "defibrillator": {
        "name": "Defibrillator",
        "explanation": "A defibrillator delivers a therapeutic dose of electrical energy to the heart to terminate dangerous arrhythmias such as ventricular fibrillation.",
        "purpose": "Restore normal cardiac rhythm in patients experiencing sudden cardiac arrest or life-threatening arrhythmias.",
        "clinical_use": "Emergency medicine, ICU, cardiac catheterisation labs, and public access programmes.",
        "related_products": ["HeartStart FRx AED", "HeartStart HS1", "Efficia DFM100"],
    },
    "holter": {
        "name": "Holter Monitor",
        "explanation": "A Holter monitor is a portable ECG device worn by the patient for 24–48 hours to continuously record cardiac electrical activity during normal daily activities.",
        "purpose": "Detect intermittent arrhythmias that may not appear during a standard resting ECG.",
        "clinical_use": "Outpatient cardiac monitoring, palpitation evaluation, and post-arrhythmia treatment follow-up.",
        "related_products": [],
    },
    "abpm": {
        "name": "Ambulatory Blood Pressure Monitor (ABPM)",
        "explanation": "An ABPM device automatically measures blood pressure at regular intervals over 24 hours while the patient goes about normal activities.",
        "purpose": "Diagnose white-coat hypertension, masked hypertension, and assess blood pressure variability.",
        "clinical_use": "Hypertension diagnosis, treatment monitoring, and cardiovascular risk assessment.",
        "related_products": ["Oscar 2 Ambulatory Blood Pressure Monitor"],
    },
    "ambulatory blood pressure": {
        "name": "Ambulatory Blood Pressure Monitoring (ABPM)",
        "explanation": "Ambulatory blood pressure monitoring records blood pressure repeatedly over 24 hours as the patient performs normal activities, capturing variations that a single clinic reading misses.",
        "purpose": "Diagnose hypertension, white-coat effect, masked hypertension, and assess nocturnal blood pressure dipping.",
        "clinical_use": "Used by cardiologists and GPs to confirm or rule out hypertension before starting medication.",
        "related_products": ["Oscar 2 Ambulatory Blood Pressure Monitor"],
    },
    "cpap": {
        "name": "CPAP (Continuous Positive Airway Pressure)",
        "explanation": "CPAP delivers a constant stream of pressurised air through a mask to keep the airways open during sleep or in patients with respiratory distress.",
        "purpose": "Treat obstructive sleep apnoea, neonatal respiratory distress syndrome, and support breathing in critically ill patients.",
        "clinical_use": "NICUs, ICUs, sleep clinics, and home respiratory therapy.",
        "related_products": [],
    },
    "ventilator": {
        "name": "Mechanical Ventilator",
        "explanation": "A ventilator is a machine that mechanically assists or replaces spontaneous breathing by moving air in and out of the lungs.",
        "purpose": "Support or replace breathing in patients who cannot breathe adequately on their own.",
        "clinical_use": "ICUs, operating theatres, emergency departments, and transport of critically ill patients.",
        "related_products": [],
    },
    "pulse oximeter": {
        "name": "Pulse Oximeter",
        "explanation": "A pulse oximeter is a non-invasive device that measures oxygen saturation (SpO₂) in the blood and pulse rate using light absorption through the skin.",
        "purpose": "Continuously monitor a patient's blood oxygen level and detect hypoxaemia early.",
        "clinical_use": "Hospitals, operating theatres, home care, and emergency settings.",
        "related_products": [],
    },
    "stress test": {
        "name": "Cardiac Stress Test",
        "explanation": "A stress test records the heart's electrical activity, blood pressure, and heart rate during controlled physical exertion on a treadmill or cycle ergometer.",
        "purpose": "Detect coronary artery disease, evaluate exercise capacity, and assess the heart's response to stress.",
        "clinical_use": "Cardiology outpatient clinics, pre-operative evaluation, and cardiac rehabilitation.",
        "related_products": ["ST80i Stress Testing System"],
    },
    "phototherapy": {
        "name": "Neonatal Phototherapy",
        "explanation": "Phototherapy uses specific wavelengths of light to break down bilirubin in a newborn's skin, treating neonatal jaundice without medication.",
        "purpose": "Reduce elevated serum bilirubin levels in neonates to prevent kernicterus (brain damage).",
        "clinical_use": "Neonatal intensive care units (NICUs) and maternity wards.",
        "related_products": [],
    },
    "surgery lights": {
        "name": "Surgical / Operating Theatre Lights",
        "explanation": "Surgical lights (also called operating lights or OR lights) provide bright, shadow-free illumination of the surgical field to enable precise surgical procedures.",
        "purpose": "Provide optimal visibility for surgeons during operations by delivering high-intensity, adjustable, shadow-free light.",
        "clinical_use": "Operating theatres, procedure rooms, and examination rooms in hospitals and clinics.",
        "related_products": [],
    },
    "operating light": {
        "name": "Operating Theatre Lights",
        "explanation": "Operating lights illuminate the surgical site with bright, colour-corrected, shadow-free light that allows surgeons to distinguish tissue types clearly.",
        "purpose": "Ensure clear, consistent illumination of the operative field throughout surgery.",
        "clinical_use": "Hospital operating theatres, day surgery units, and examination rooms.",
        "related_products": [],
    },
}


def format_general_medical_answer(query: str, chunks: list | None = None) -> str:
    """
    Returns a structured explanation of a medical concept.
    Matches the query against _MEDICAL_CONCEPTS keys.
    Falls back to a generic structure if the concept is unknown,
    using Wikipedia/dynamic search content from the chunks.
    """
    q = query.lower()
    concept = None

    # Longest-match first to avoid 'ecg' matching 'electrocardiogram' mid-word
    for key in sorted(_MEDICAL_CONCEPTS.keys(), key=len, reverse=True):
        if key in q:
            concept = _MEDICAL_CONCEPTS[key]
            break

    # Collect product names found in chunks
    chunk_products: list[str] = []
    wiki_text: str = ""
    if chunks:
        seen: set[str] = set()
        for chunk in chunks:
            name = _product_name(chunk)
            if name and name not in seen:
                seen.add(name)
                chunk_products.append(name)
            # If the chunk is Wikipedia/dynamic content, extract the text
            if "📚 Medical Background" in chunk or "🌐 Dynamic Search" in chunk:
                # Strip the header line and use the rest as enrichment text
                text_part = re.sub(r"^.*?(?:Background|Search)\n+", "", chunk, flags=re.DOTALL).strip()
                if text_part and len(text_part) > 50:
                    wiki_text = text_part[:800]

    if concept is None:
        # Generic fallback — use Wikipedia text if available
        if wiki_text:
            lines = [f"## 🏥 Medical Information\n"]
            lines.append(wiki_text)
            if chunk_products:
                lines.append("\n**Related Devices:**")
                for p in chunk_products:
                    lines.append(f"- {p}")
            print("[fallback] general_medical formatter used (wiki text)")
            return "\n".join(lines)

        lines = ["## 🏥 Medical Device Information\n"]
        lines.append("This query relates to a medical concept or device technology.")
        if chunk_products:
            lines.append("\n**Related Devices:**")
            for p in chunk_products:
                lines.append(f"- {p}")
        print("[fallback] general_medical formatter used (generic)")
        return "\n".join(lines)

    lines = [f"## 🏥 {concept['name']}\n"]

    # If we have Wikipedia text, prefer it as the explanation (richer)
    if wiki_text:
        lines.append(f"**What it is:**\n{wiki_text}\n")
    else:
        lines.append(f"**What it is:** {concept['explanation']}\n")

    lines.append(f"**Purpose:** {concept['purpose']}\n")
    lines.append(f"**Clinical Use:** {concept['clinical_use']}\n")

    # Merge concept-defined related products with any found in chunks
    all_products = list(dict.fromkeys(concept["related_products"] + chunk_products))
    if all_products:
        lines.append("**Related Devices:**")
        for p in all_products:
            lines.append(f"- {p}")

    print("[fallback] general_medical formatter used")
    return "\n".join(lines)
