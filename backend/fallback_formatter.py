"""
fallback_formatter.py
Structures raw FAISS chunks into readable markdown when Gemini is unavailable.
All functions accept the same (chunks: list[str]) signature and return a str.
"""
import re
from typing import Optional


# ── Chunk field extractors ────────────────────────────────────────────────

def _field(chunk: str, label: str) -> Optional[str]:
    m = re.search(rf"{label}:\s*(.+)", chunk)
    return m.group(1).strip() if m else None


def _features(chunk: str) -> list[str]:
    return re.findall(r"^- (.+?):\s*(.+)", chunk, re.MULTILINE)


def _specs(chunk: str) -> list[tuple[str, str]]:
    in_specs = False
    results = []
    for line in chunk.splitlines():
        if line.strip().startswith("Specifications:"):
            in_specs = True
            continue
        if in_specs:
            m = re.match(r"^- (.+?):\s*(.+)", line.strip())
            if m:
                results.append((m.group(1), m.group(2)))
            elif line.strip() and not line.startswith("-"):
                break
    return results


def _feature_lines(chunk: str) -> list[tuple[str, str]]:
    in_features = False
    results = []
    for line in chunk.splitlines():
        if line.strip().startswith("Features:"):
            in_features = True
            continue
        if line.strip().startswith("Specifications:"):
            break
        if in_features:
            m = re.match(r"^- (.+?):\s*(.+)", line.strip())
            if m:
                results.append((m.group(1), m.group(2)))
    return results


# ── Public formatters ─────────────────────────────────────────────────────

def format_product_answer(chunks: list[str]) -> str:
    if not chunks:
        return "No product information available."

    chunk = chunks[0]
    product  = _field(chunk, "Product Name") or "Unknown Product"
    category = _field(chunk, "Category") or ""
    desc     = _field(chunk, "Description") or ""
    features = _feature_lines(chunk)

    lines = [f"📦 **Product Information**\n"]
    lines.append(f"**Product:** {product}")
    if category:
        lines.append(f"**Category:** {category}")
    if desc:
        lines.append(f"\n**Description:**\n{desc}")
    if features:
        lines.append("\n**Key Features:**")
        for title, detail in features[:5]:
            lines.append(f"- **{title}:** {detail}")

    print("[fallback] product formatter used")
    return "\n".join(lines)


def format_feature_answer(chunks: list[str]) -> str:
    if not chunks:
        return "No feature information available."

    chunk    = chunks[0]
    product  = _field(chunk, "Product Name") or "Unknown Product"
    features = _feature_lines(chunk)

    lines = [f"📦 **Product Overview**\n", f"**Product:** {product}\n"]

    if features:
        lines.append("**Key Features:**")
        for title, detail in features:
            lines.append(f"- **{title}:** {detail}")
    else:
        desc = _field(chunk, "Description") or ""
        if desc:
            lines.append(f"**Description:**\n{desc}")
        else:
            lines.append("Feature details are not available for this product.")

    print("[fallback] feature formatter used")
    return "\n".join(lines)


def format_specification_answer(chunks: list[str]) -> str:
    if not chunks:
        return "No specification information available."

    chunk   = chunks[0]
    product = _field(chunk, "Product Name") or "Unknown Product"
    specs   = _specs(chunk)

    lines = [f"📋 **Specifications**\n", f"**Product:** {product}\n"]

    if specs:
        for key, val in specs:
            lines.append(f"- **{key}:** {val}")
    else:
        lines.append("Detailed specifications are not available for this product.")
        desc = _field(chunk, "Description") or ""
        if desc:
            lines.append(f"\n**Description:**\n{desc}")

    print("[fallback] specification formatter used")
    return "\n".join(lines)


def format_category_answer(chunks: list[str]) -> str:
    """Collect unique products per category and produce a summary list."""
    if not chunks:
        return "No category information available."

    # Gather unique products from all chunks
    seen: set[str] = set()
    category = None
    products: list[tuple[str, str]] = []   # (product_name, description)

    for chunk in chunks:
        cat  = _field(chunk, "Category")
        name = _field(chunk, "Product Name")
        desc = _field(chunk, "Description") or ""

        if cat and not category:
            category = cat
        if name and name not in seen:
            seen.add(name)
            products.append((name, desc[:120] + ("…" if len(desc) > 120 else "")))

    lines = [f"🏥 **{category or 'Medical'} Devices Overview**\n"]

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
    """Build a markdown comparison table from the first two distinct products."""
    if not chunks:
        return "No product information available for comparison."

    # Extract up to 2 distinct products
    products: list[dict] = []
    seen: set[str] = set()

    for chunk in chunks:
        name = _field(chunk, "Product Name")
        if not name or name in seen:
            continue
        seen.add(name)
        products.append({
            "name":     name,
            "category": _field(chunk, "Category") or "—",
            "desc":     (_field(chunk, "Description") or "—")[:150],
            "features": _feature_lines(chunk),
            "specs":    _specs(chunk),
        })
        if len(products) == 2:
            break

    if len(products) < 2:
        # Fall back to plain product display if only one found
        return format_product_answer(chunks)

    p1, p2 = products[0], products[1]

    lines = ["📊 **Product Comparison**\n"]
    lines.append(f"| Attribute | {p1['name']} | {p2['name']} |")
    lines.append("|---|---|---|")
    lines.append(f"| Category | {p1['category']} | {p2['category']} |")
    lines.append(f"| Description | {p1['desc']} | {p2['desc']} |")

    # Features — align by index
    max_f = max(len(p1["features"]), len(p2["features"]))
    for i in range(min(max_f, 4)):
        f1 = f"**{p1['features'][i][0]}:** {p1['features'][i][1]}" if i < len(p1["features"]) else "—"
        f2 = f"**{p2['features'][i][0]}:** {p2['features'][i][1]}" if i < len(p2["features"]) else "—"
        lines.append(f"| Feature {i+1} | {f1} | {f2} |")

    # Specs — align by index
    max_s = max(len(p1["specs"]), len(p2["specs"]))
    for i in range(min(max_s, 4)):
        s1 = f"{p1['specs'][i][0]}: {p1['specs'][i][1]}" if i < len(p1["specs"]) else "—"
        s2 = f"{p2['specs'][i][0]}: {p2['specs'][i][1]}" if i < len(p2["specs"]) else "—"
        lines.append(f"| Spec {i+1} | {s1} | {s2} |")

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
}


def format_general_medical_answer(query: str, chunks: list[str] | None = None) -> str:
    """
    Returns a structured explanation of a medical concept.
    Matches the query against _MEDICAL_CONCEPTS keys.
    Falls back to a generic structure if the concept is unknown.
    """
    q = query.lower()
    concept = None
    for key in _MEDICAL_CONCEPTS:
        if key in q:
            concept = _MEDICAL_CONCEPTS[key]
            break

    # Also collect related products found in chunks
    chunk_products: list[str] = []
    if chunks:
        seen: set[str] = set()
        for chunk in chunks:
            name = _field(chunk, "Product Name")
            if name and name not in seen:
                seen.add(name)
                chunk_products.append(name)

    if concept is None:
        # Generic fallback for unknown medical terms
        lines = ["🏥 **Medical Device Information**\n"]
        lines.append("This query relates to a medical concept or device technology.")
        if chunk_products:
            lines.append("\n**Related Philips Products:**")
            for p in chunk_products:
                lines.append(f"- {p}")
        print("[fallback] general_medical formatter used (generic)")
        return "\n".join(lines)

    lines = [f"🏥 **{concept['name']}**\n"]
    lines.append(f"**What it is:** {concept['explanation']}\n")
    lines.append(f"**Purpose:** {concept['purpose']}\n")
    lines.append(f"**Clinical Use:** {concept['clinical_use']}\n")

    # Merge concept-defined related products with any found in chunks
    all_products = list(dict.fromkeys(concept["related_products"] + chunk_products))
    if all_products:
        lines.append("**Related Philips Products:**")
        for p in all_products:
            lines.append(f"- {p}")

    print("[fallback] general_medical formatter used")
    return "\n".join(lines)




# ── Medical concept knowledge ─────────────────────────────────────────────
_MEDICAL_CONCEPTS: dict[str, dict] = {
    "ecg": {
        "name": "Electrocardiogram (ECG)",
        "explanation": "An ECG records the electrical activity of the heart over time using skin electrodes, producing a trace of each heartbeat.",
        "purpose": "Detect arrhythmias, heart attacks, conduction abnormalities, and assess overall cardiac health.",
        "clinical_use": "Emergency departments, cardiology clinics, ICUs, ambulances, and routine health check-ups.",
        "related_products": ["PageWriter TC50", "PageWriter TC35", "PageWriter TC10", "Cardiac Workstation 7000"],
    },
    "electrocardiogram": {
        "name": "Electrocardiogram (ECG/EKG)",
        "explanation": "An electrocardiogram records the heart's electrical impulses to reveal heart rate, rhythm, and structural information.",
        "purpose": "Diagnose myocardial infarction, atrial fibrillation, and ventricular hypertrophy.",
        "clinical_use": "Standard in hospitals, clinics, and pre-operative assessments worldwide.",
        "related_products": ["PageWriter TC50", "PageWriter TC35", "PageWriter TC10"],
    },
    "aed": {
        "name": "Automated External Defibrillator (AED)",
        "explanation": "An AED automatically diagnoses life-threatening cardiac arrhythmias and delivers a defibrillating shock to restore normal heart rhythm.",
        "purpose": "Treat sudden cardiac arrest (SCA) outside hospital settings.",
        "clinical_use": "Public access programmes, first responders, schools, airports, and workplaces.",
        "related_products": ["HeartStart FRx AED", "HeartStart HS1"],
    },
    "defibrillator": {
        "name": "Defibrillator",
        "explanation": "A defibrillator delivers a therapeutic electrical shock to terminate dangerous arrhythmias such as ventricular fibrillation.",
        "purpose": "Restore normal cardiac rhythm in sudden cardiac arrest or life-threatening arrhythmia.",
        "clinical_use": "Emergency medicine, ICU, cardiac catheterisation labs, and public access programmes.",
        "related_products": ["HeartStart FRx AED", "HeartStart HS1", "Efficia DFM100"],
    },
    "holter": {
        "name": "Holter Monitor",
        "explanation": "A Holter monitor is a wearable ECG device that continuously records cardiac activity over 24–48 hours during normal daily activities.",
        "purpose": "Detect intermittent arrhythmias not captured on a standard resting ECG.",
        "clinical_use": "Outpatient cardiac monitoring and post-arrhythmia treatment follow-up.",
        "related_products": [],
    },
    "abpm": {
        "name": "Ambulatory Blood Pressure Monitor (ABPM)",
        "explanation": "An ABPM device automatically measures blood pressure at regular intervals over 24 hours while the patient performs normal activities.",
        "purpose": "Diagnose white-coat hypertension, masked hypertension, and assess blood pressure variability.",
        "clinical_use": "Hypertension diagnosis, treatment monitoring, and cardiovascular risk assessment.",
        "related_products": ["Oscar 2 Ambulatory Blood Pressure Monitor"],
    },
    "cpap": {
        "name": "CPAP (Continuous Positive Airway Pressure)",
        "explanation": "CPAP delivers a constant stream of pressurised air to keep airways open in patients with breathing difficulties.",
        "purpose": "Treat obstructive sleep apnoea and neonatal respiratory distress syndrome.",
        "clinical_use": "NICUs, ICUs, sleep clinics, and home respiratory therapy.",
        "related_products": [],
    },
    "ventilator": {
        "name": "Mechanical Ventilator",
        "explanation": "A ventilator mechanically assists or replaces spontaneous breathing by moving air into and out of the lungs.",
        "purpose": "Support or replace breathing in patients unable to breathe adequately on their own.",
        "clinical_use": "ICUs, operating theatres, emergency departments, and critical care transport.",
        "related_products": [],
    },
    "pulse oximeter": {
        "name": "Pulse Oximeter",
        "explanation": "A pulse oximeter non-invasively measures blood oxygen saturation (SpO₂) and pulse rate using light absorption through the skin.",
        "purpose": "Continuously monitor a patient's blood oxygen level and detect hypoxaemia early.",
        "clinical_use": "Hospitals, operating theatres, home care, and emergency settings.",
        "related_products": [],
    },
    "stress test": {
        "name": "Cardiac Stress Test",
        "explanation": "A stress test records cardiac electrical activity, blood pressure, and heart rate during controlled physical exertion.",
        "purpose": "Detect coronary artery disease and evaluate the heart's response to exercise.",
        "clinical_use": "Cardiology clinics, pre-operative evaluation, and cardiac rehabilitation.",
        "related_products": ["ST80i Stress Testing System"],
    },
    "phototherapy": {
        "name": "Neonatal Phototherapy",
        "explanation": "Phototherapy uses specific light wavelengths to break down bilirubin in a newborn's skin, treating neonatal jaundice.",
        "purpose": "Reduce elevated bilirubin levels to prevent kernicterus (bilirubin-induced brain damage).",
        "clinical_use": "Neonatal intensive care units (NICUs) and maternity wards.",
        "related_products": [],
    },
}


def format_general_medical_answer(query: str, chunks: list | None = None) -> str:
    """
    Structured explanation of a medical concept when Gemini is unavailable.
    Matches query text against _MEDICAL_CONCEPTS keys.
    """
    q = query.lower()
    concept = None
    for key in _MEDICAL_CONCEPTS:
        if key in q:
            concept = _MEDICAL_CONCEPTS[key]
            break

    # Collect product names from any retrieved chunks
    chunk_products: list[str] = []
    if chunks:
        seen: set[str] = set()
        for chunk in chunks:
            name = _field(chunk, "Product Name")
            if name and name not in seen:
                seen.add(name)
                chunk_products.append(name)

    if concept is None:
        lines = ["🏥 **Medical Device Information**\n"]
        lines.append("This query relates to a medical concept or device technology.")
        if chunk_products:
            lines.append("\n**Related Philips Products:**")
            for p in chunk_products:
                lines.append(f"- {p}")
        print("[fallback] general_medical formatter used (generic)")
        return "\n".join(lines)

    lines = [f"🏥 **{concept['name']}**\n"]
    lines.append(f"**What it is:** {concept['explanation']}\n")
    lines.append(f"**Purpose:** {concept['purpose']}\n")
    lines.append(f"**Clinical Use:** {concept['clinical_use']}\n")

    all_products = list(dict.fromkeys(concept["related_products"] + chunk_products))
    if all_products:
        lines.append("**Related Philips Products:**")
        for p in all_products:
            lines.append(f"- {p}")

    print("[fallback] general_medical formatter used")
    return "\n".join(lines)
