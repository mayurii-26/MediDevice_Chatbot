"""
response_refiner.py  —  Primary deterministic response engine.

This module is the SOLE response formatter when Gemini is unavailable.
It must produce responses that are indistinguishable from a well-prompted
LLM: structured headings, clean bullets, readable English, no raw metadata.

Input
-----
context : list[str]
    Each item is a formatted chunk from app.py._format_product_chunk(), e.g.:

        📦 Product

        PageWriter TC50

        Category
        Cardiology

        Summary

        Multi-line description...

        Features

        - Feature Name: detail
        - Feature Name: detail

        Specifications

        - Spec Name: value

    Multiple chunks within the same context item are separated by:
        \\n\\n---\\n\\n

    Wikipedia / dynamic-search chunks look like:
        📚 Medical Background

        Title

        Summary text...

        Source: https://...

Public API
----------
format_product(question, context)         → str
format_features(question, context)        → str
format_specifications(question, context)  → str
format_comparison(question, context)      → str
format_category(question, context)        → str
format_general_medical(question, context) → str
format_dynamic(question, context)         → str
refine(question, context, source, intent) → str   ← main entry point
"""

import re
from typing import Optional


# ── Sentinel ──────────────────────────────────────────────────────────────
_NO_INFO = (
    "I was unable to find relevant information for your question. "
    "Please try rephrasing or ask about a specific Philips medical device."
)


# ══════════════════════════════════════════════════════════════════════════
# SECTION 1 — CHUNK PARSERS
# ══════════════════════════════════════════════════════════════════════════

def _split_chunks(context: list[str]) -> list[str]:
    """Split combined_context into individual product chunks."""
    result: list[str] = []
    for item in context:
        if not isinstance(item, str) or not item.strip():
            continue
        for part in re.split(r"\n\n---\n\n", item):
            if part.strip():
                result.append(part.strip())
    return result


def _get_section(chunk: str, header: str) -> str:
    """
    Extract content of a named section.
    The current header is excluded from the stop-list to prevent
    zero-length matches.
    """
    all_h = ["Category", "Summary", "Features", "Specifications",
             "Source", "Highlights", "Overview"]
    stops = [h for h in all_h if h.lower() != header.lower()]
    stop_pat = "|".join(re.escape(h) for h in stops)
    pat = re.compile(
        rf"(?:^|\n)\s*{re.escape(header)}\s*\n(.*?)"
        rf"(?=\n\s*(?:{stop_pat})\s*\n|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pat.search(chunk)
    return m.group(1).strip() if m else ""


def _product_name(chunk: str) -> str:
    # Formatted chunk: 📦 Product\n\n<name>\n\nCategory...
    m = re.search(
        r"📦\s*Product\s*\n+(.*?)(?=\n\n|\nCategory|\nSummary|\nFeatures|\nSpecifications|$)",
        chunk, re.IGNORECASE | re.DOTALL,
    )
    if m:
        v = m.group(1).strip()
        if v:
            return v
    # Raw FAISS chunk: "Product Name: ..."
    m2 = re.search(r"Product(?:\s+Name)?\s*:\s*(.+)", chunk)
    if m2:
        return m2.group(1).strip().split("\n")[0].strip()
    return ""


def _category(chunk: str) -> str:
    # Formatted: Category\nCardiology
    m = re.search(r"\bCategory\s*\n([^\n]+)", chunk, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Raw: Category: Cardiology
    m2 = re.search(r"Category\s*:\s*(.+)", chunk)
    if m2:
        return m2.group(1).strip().split("\n")[0].strip()
    return ""


def _clean_desc(text: str) -> str:
    """
    Clean a description block.
    - Strip leading/trailing whitespace on every line.
    - Collapse 3+ blank lines to one.
    - Truncate to 3 sentences max.
    - Never return concatenated words (ProductNameCategoryValue).
    """
    if not text:
        return ""

    # Remove obvious metadata lines that leaked in
    lines = []
    for line in text.splitlines():
        s = line.strip()
        # Skip lines that look like "Key: value" metadata
        if re.match(r"^(Product|Category|Features|Specifications|Source|Highlights)\s*:", s, re.I):
            continue
        lines.append(s)

    cleaned = " ".join(l for l in lines if l)

    # Split into sentences and take first 3
    sentences = re.split(r"(?<=[.!?])\s+", cleaned.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    result = " ".join(sentences[:3])

    return result[:500] if result else ""


def _description(chunk: str) -> str:
    """Extract and clean description text."""
    s = _get_section(chunk, "Summary")
    if s:
        return _clean_desc(s)
    m = re.search(r"Description\s*:\s*(.+)", chunk, re.DOTALL)
    if m:
        return _clean_desc(m.group(1))
    return ""


def _features(chunk: str) -> list[str]:
    """
    Return feature lines as plain strings.
    Input formats handled:
      - Formatted: Features\\n\\n- Name: detail
      - Raw FAISS: Features:\\n- Name: detail
    """
    section = _get_section(chunk, "Features")
    if section:
        out = []
        for line in section.splitlines():
            s = line.strip()
            if s.startswith("- "):
                out.append(s[2:].strip())
            elif s and not re.match(r"^(Category|Summary|Specifications|Source)\s*[:$]", s, re.I):
                out.append(s)
        return [x for x in out if len(x) > 3]

    # Raw FAISS fallback
    in_f, out = False, []
    for line in chunk.splitlines():
        if re.match(r"^\s*Features\s*:", line, re.I):
            in_f = True
            continue
        if in_f and re.match(r"^\s*Specifications\s*", line, re.I):
            break
        if in_f:
            s = line.strip()
            if s.startswith("- "):
                out.append(s[2:].strip())
    return [x for x in out if len(x) > 3]


def _specs(chunk: str) -> list[str]:
    """Return specification lines as plain strings."""
    section = _get_section(chunk, "Specifications")
    if section:
        out = []
        for line in section.splitlines():
            s = line.strip()
            if s.startswith("- "):
                out.append(s[2:].strip())
            elif s and not re.match(r"^(Category|Summary|Features|Source)\s*[:$]", s, re.I):
                out.append(s)
        return [x for x in out if len(x) > 3]

    # Raw FAISS fallback
    in_s, out = False, []
    for line in chunk.splitlines():
        if re.match(r"^\s*Specifications\s*:", line, re.I):
            in_s = True
            continue
        if in_s:
            s = line.strip()
            if s.startswith("- "):
                out.append(s[2:].strip())
            elif s and not s.startswith("-"):
                break
    return [x for x in out if len(x) > 3]


def _wiki_summary(chunks: list[str]) -> str:
    """
    Extract clean prose sentences from Wikipedia / DuckDuckGo / web-search
    context chunks.

    Returns at most 4 clean sentences. Aggressively filters:
      - URLs and source lines
      - DuckDuckGo "Title: body" prefixes (any casing)
      - Wikipedia page-title lines
      - MedicalExpo / vendor / navigation headings
      - Bare domain names (e.g. "medicalexpo.com", "en.wikipedia.org")
      - Short-fragment lines (< 6 words)
      - Duplicate sentences (case-insensitive)

    Never concatenates raw search snippets — only prose that reads as a
    complete, grammatically correct sentence is kept.

    Handles three chunk formats:
      1. Wikipedia:   '📚 Medical Background'
      2. DuckDuckGo:  '🌐 Dynamic Search'
      3. Web results: '[Web Search Results]'
    """
    # ── Compile noise patterns once ────────────────────────────────────────
    _url_re      = re.compile(r"https?://\S+|www\.\S+|\S+\.(com|org|net|io|edu|gov)\b[^\s]*", re.I)
    _source_re   = re.compile(r"^\s*source\s*:.*$", re.I | re.M)
    _domain_re   = re.compile(r"^\s*\S+\.(com|org|net|io|edu|gov|co)\S*\s*$", re.I)
    # DuckDuckGo returns "Title: body" — strip everything up to and including the first ": "
    # even when title is lower-case (e.g. "ecg machine: An ECG...")
    _ddg_prefix_re = re.compile(r"^[^:.\n]{3,80}:\s+", re.M)
    # Marketing / navigation headings
    _nav_re      = re.compile(
        r"(?m)^(MedicalExpo|Manufacturer|Find|Browse|Compare|Filter|Sort|Results|Shop|"
        r"Home|Menu|Navigation|Advertisement|Sponsored|Related|More|Search|Contact|"
        r"About|Privacy|Terms|Cookie)\b.*$",
        re.I,
    )
    # Wikipedia / title-case short lines with no terminal punctuation
    _title_re    = re.compile(r"^[A-Z][A-Za-z\s\-]{0,60}$")

    all_sentences: list[str] = []

    for chunk in chunks:
        is_wiki = "📚 Medical Background" in chunk
        is_ddg  = "🌐 Dynamic Search" in chunk
        is_web  = chunk.lstrip().startswith("[Web Search Results]")

        if not (is_wiki or is_ddg or is_web):
            continue

        # ── Strip block headers ────────────────────────────────────────────
        if is_wiki or is_ddg:
            text = re.sub(r"^.*?(?:Background|Search)\n+", "", chunk, flags=re.DOTALL)
        else:
            text = re.sub(r"^\[Web Search Results\]\s*\n*", "", chunk, flags=re.I | re.M)

        # ── Remove source/URL lines ────────────────────────────────────────
        text = _source_re.sub("", text)
        text = _url_re.sub("", text)

        # ── Strip DuckDuckGo "Title: " prefixes from every line ────────────
        # This handles "ECG machine: An ECG records..." → "An ECG records..."
        text = _ddg_prefix_re.sub("", text)

        # ── Remove navigation / marketing headings ─────────────────────────
        text = _nav_re.sub("", text)

        # ── Remove bare domain names ───────────────────────────────────────
        text = re.sub(r"(?m)^\s*\S+\.(com|org|net|io|edu|gov|co)\S*\s*$", "", text, flags=re.I)

        # ── Collapse whitespace ────────────────────────────────────────────
        text = re.sub(r"\n+", " ", text)
        text = re.sub(r"\s{2,}", " ", text).strip()

        # ── Strip stray title tokens prepended to sentences ────────────────
        # e.g. "Electrocardiogram An electrocardiogram is..." →
        #      "An electrocardiogram is..."
        # Pattern: a title-case word (no trailing punct) followed immediately
        # by a capital letter starting real prose.
        text = re.sub(r"\b([A-Z][a-z]{3,}(?:\s+[A-Z][a-z]+){0,4})\s+(?=[A-Z])", "", text)

        # ── Sentence split ─────────────────────────────────────────────────
        raw_sents = re.split(r"(?<=[.!?])\s+", text)

        for s in raw_sents:
            s = s.strip()
            # Must look like prose: terminal punctuation, ≥ 6 words, no bare "Title" patterns
            if len(s) < 25:
                continue
            if len(s.split()) < 6:
                continue
            if not re.search(r"[.!?]$", s):
                continue
            # Reject lines that still look like a title (all title-case, ≤ 7 words, no verb markers)
            if _title_re.match(s) and len(s.split()) <= 7:
                continue
            # Reject lines that still contain a URL fragment
            if _url_re.search(s):
                continue
            all_sentences.append(s)

    if not all_sentences:
        return ""

    # ── Deduplicate (case-insensitive, exact) ──────────────────────────────
    seen: set[str] = set()
    unique: list[str] = []
    for s in all_sentences:
        key = re.sub(r"\s+", " ", s.lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(s)

    return " ".join(unique[:4])


def _is_dynamic(chunks: list[str]) -> bool:
    """True if any chunk is a Wikipedia / dynamic-search result."""
    return any(
        "📚 Medical Background" in c or "🌐 Dynamic Search" in c
        for c in chunks
    )



# ══════════════════════════════════════════════════════════════════════════
# SECTION 2 — INTENT FORMATTERS
# ══════════════════════════════════════════════════════════════════════════

def format_product(question: str, context: list[str]) -> str:
    """
    product_query — spec format:
        📦 Product Name
        Category
        Overview (2-3 sentences)
        Applications
        Documents note
    """
    chunks = _split_chunks(context)
    if not chunks:
        return _NO_INFO

    chunk   = chunks[0]
    product = _product_name(chunk)
    cat     = _category(chunk)
    desc    = _description(chunk)
    feat    = _features(chunk)
    spec    = _specs(chunk)

    if not product and not desc:
        return _NO_INFO

    title = product or "Medical Device"
    L: list[str] = []

    # ── Header ─────────────────────────────────────────────────────────────
    L.append(f"## 📦 {title}")
    if cat:
        L.append(f"*{cat}*")
    L.append("")

    # ── Overview ───────────────────────────────────────────────────────────
    if desc:
        L.append("### Overview")
        L.append("")
        L.append(desc)
        L.append("")

    # ── Key Features ───────────────────────────────────────────────────────
    if feat:
        L.append("### Key Features")
        L.append("")
        for f in feat:
            if ":" in f:
                name, _, detail = f.partition(":")
                L.append(f"• **{name.strip()}** — {detail.strip()}")
            else:
                L.append(f"• {f}")
        L.append("")

    # ── Specifications ─────────────────────────────────────────────────────
    if spec:
        L.append("### Specifications")
        L.append("")
        for s in spec:
            if ":" in s:
                k, _, v = s.partition(":")
                L.append(f"• **{k.strip()}:** {v.strip()}")
            else:
                L.append(f"• {s}")
        L.append("")

    # ── Applications ───────────────────────────────────────────────────────
    L.append("### Applications")
    L.append("")
    if cat:
        L.append(f"• Professional use in **{cat}** clinical environments")
    L.append("• Hospitals, diagnostic centres, and specialist clinics")
    if feat:
        for f in feat[:2]:
            name = f.partition(":")[0].strip()
            if any(w in name.lower() for w in ("monitor", "detect", "record", "measur", "print", "connect")):
                L.append(f"• {name}")
    L.append("")

    # ── Documents ──────────────────────────────────────────────────────────
    L.append("### Documents")
    L.append("")
    L.append("• Product datasheets and user manuals may be available — use the Documents section above.")
    L.append("")

    print(f"[refiner] format_product | product={product!r} | feat={len(feat)} | spec={len(spec)}")
    return "\n".join(L).rstrip()


def format_features(question: str, context: list[str]) -> str:
    """
    feature_query — bullet list only.  No description, no specs.
    """
    chunks = _split_chunks(context)
    if not chunks:
        return _NO_INFO

    chunk   = chunks[0]
    product = _product_name(chunk)
    feat    = _features(chunk)

    L: list[str] = []
    device  = product or "this device"
    L.append(f"## ✨ Features — {product}" if product else "## ✨ Features")
    L.append("")

    if feat:
        for f in feat:
            if ":" in f:
                name, _, detail = f.partition(":")
                L.append(f"• **{name.strip()}** — {detail.strip()}")
            else:
                L.append(f"• {f}")
        L.append("")
        L.append(
            f"The **{device}** is designed for professional clinical use, "
            f"combining these capabilities to support accurate diagnosis and efficient workflows."
        )
    else:
        desc = _description(chunk)
        if desc:
            L.append(desc)
        else:
            L.append("Feature details are not currently available for this product.")

    print(f"[refiner] format_features | product={product!r} | count={len(feat)}")
    return "\n".join(L).rstrip()



def format_specifications(question: str, context: list[str]) -> str:
    """
    specification_query — spec format:
        📋 Technical Specifications — Product Name
        bullet list of specifications
    """
    chunks = _split_chunks(context)
    if not chunks:
        return _NO_INFO

    chunk   = chunks[0]
    product = _product_name(chunk)
    spec    = _specs(chunk)

    L: list[str] = []
    L.append(f"## 📋 Technical Specifications — {product}" if product else "## 📋 Technical Specifications")
    L.append("")

    if spec:
        for s in spec:
            if ":" in s:
                k, _, v = s.partition(":")
                L.append(f"• **{k.strip()}:** {v.strip()}")
            else:
                L.append(f"• {s}")
        L.append("")
    else:
        L.append("Detailed specifications are currently unavailable.")
        L.append("Please refer to the official product datasheet.")
        desc = _description(chunk)
        if desc:
            L.append("")
            L.append(desc)

    print(f"[refiner] format_specifications | product={product!r} | spec={len(spec)}")
    return "\n".join(L).rstrip()


def format_comparison(question: str, context: list[str]) -> str:
    """
    comparison_query — spec format:
        📊 Comparison
        Product A section
        Product B section
        Key Differences
        Recommendation
    """
    chunks = _split_chunks(context)
    if not chunks:
        return _NO_INFO

    # Collect up to 2 distinct products
    products: list[dict] = []
    seen: set[str] = set()
    for chunk in chunks:
        name = _product_name(chunk)
        if not name or name in seen:
            continue
        seen.add(name)
        products.append({
            "name":  name,
            "cat":   _category(chunk) or "—",
            "desc":  _description(chunk) or "—",
            "feat":  _features(chunk),
            "spec":  _specs(chunk),
        })
        if len(products) == 2:
            break

    L: list[str] = []

    if len(products) < 2:
        p = products[0] if products else None
        if not p:
            return _NO_INFO
        L.append("## 📊 Comparison")
        L.append("")
        L.append(
            f"⚠️ Only one product was found in the knowledge base.\n\n"
            f"**{p['name']}** was retrieved but the second product could not be found. "
            f"Showing available details below."
        )
        L.append("")
        L += format_product(question, context).splitlines()
        return "\n".join(L).rstrip()

    p1, p2 = products[0], products[1]
    L.append(f"## 📊 {p1['name']} vs {p2['name']}")
    L.append("")

    # ── Product A ──────────────────────────────────────────────────────────
    L.append(f"### {p1['name']}")
    L.append(f"*{p1['cat']}*")
    L.append("")
    if p1["desc"] and p1["desc"] != "—":
        L.append(p1["desc"])
        L.append("")
    if p1["feat"]:
        for f in p1["feat"][:5]:
            if ":" in f:
                n, _, d = f.partition(":")
                L.append(f"• **{n.strip()}** — {d.strip()}")
            else:
                L.append(f"• {f}")
        L.append("")

    # ── Product B ──────────────────────────────────────────────────────────
    L.append(f"### {p2['name']}")
    L.append(f"*{p2['cat']}*")
    L.append("")
    if p2["desc"] and p2["desc"] != "—":
        L.append(p2["desc"])
        L.append("")
    if p2["feat"]:
        for f in p2["feat"][:5]:
            if ":" in f:
                n, _, d = f.partition(":")
                L.append(f"• **{n.strip()}** — {d.strip()}")
            else:
                L.append(f"• {f}")
        L.append("")

    # ── Key Differences ────────────────────────────────────────────────────
    L.append("### Key Differences")
    L.append("")
    diffs: list[str] = []
    if len(p1["feat"]) != len(p2["feat"]):
        more  = p1["name"] if len(p1["feat"]) > len(p2["feat"]) else p2["name"]
        less  = p2["name"] if more == p1["name"] else p1["name"]
        diffs.append(
            f"**{more}** has more documented features "
            f"({max(len(p1['feat']), len(p2['feat']))} vs "
            f"{min(len(p1['feat']), len(p2['feat']))})."
        )
    if p1["cat"] != p2["cat"] and p1["cat"] != "—" and p2["cat"] != "—":
        diffs.append(
            f"**{p1['name']}** is categorised under **{p1['cat']}**; "
            f"**{p2['name']}** is under **{p2['cat']}**."
        )
    if p1["spec"] or p2["spec"]:
        # Surface first spec difference if available
        s1 = p1["spec"][0] if p1["spec"] else None
        s2 = p2["spec"][0] if p2["spec"] else None
        if s1 and s2 and s1 != s2:
            diffs.append(f"Key specification difference: {s1} vs {s2}")
    if not diffs:
        diffs.append(
            "Both are professional clinical devices. "
            "Consult the datasheets for full technical differences."
        )
    for d in diffs:
        L.append(f"• {d}")
    L.append("")

    # ── Recommendation ─────────────────────────────────────────────────────
    L.append("### Recommendation")
    L.append("")
    L.append(
        f"Choose **{p1['name']}** or **{p2['name']}** based on your clinical "
        f"workflow, facility requirements, and budget. "
        f"Contact a Philips representative for personalised guidance."
    )

    print(f"[refiner] format_comparison | p1={p1['name']!r} | p2={p2['name']!r}")
    return "\n".join(L).rstrip()



def format_category(question: str, context: list[str]) -> str:
    """
    category_query — short intro, product list with descriptions,
    applications, summary table.
    """
    chunks = _split_chunks(context)
    if not chunks:
        return _NO_INFO

    seen: set[str] = set()
    cat_name: str = ""
    products: list[tuple[str, str]] = []  # (name, short_desc)

    for chunk in chunks:
        cat  = _category(chunk)
        name = _product_name(chunk)
        desc = _description(chunk)
        if cat and not cat_name:
            cat_name = cat
        if name and name not in seen:
            seen.add(name)
            short = (desc[:150] + "…") if len(desc) > 150 else desc
            products.append((name, short))

    display = cat_name or "Medical"
    L: list[str] = []
    L.append(f"## 🏥 {display} Devices")
    L.append("")
    L.append(
        f"The **{display}** category includes specialised medical devices "
        f"for professional clinical use."
    )
    L.append("")

    if products:
        L.append("### Available Devices")
        L.append("")
        for name, desc in products:
            L.append(f"**{name}**")
            if desc:
                L.append(desc)
            L.append("")

        L.append("### Applications")
        L.append("")
        L.append(f"• Professional use in **{display}** departments")
        L.append("• Hospitals, clinics, and diagnostic centres")
        L.append("• Supports clinical decision-making and patient care")
        L.append("")
    else:
        L.append("No device information is currently available for this category.")

    print(f"[refiner] format_category | category={cat_name!r} | products={len(products)}")
    return "\n".join(L).rstrip()


def format_dynamic(question: str, context: list[str]) -> str:
    """
    dynamic_search / wikipedia source — produces clean, structured markdown.

    Output structure:
        🌐 Web Information
        ## Summary
        ## Key Points        (if extractable)
        ## Clinical Relevance (if question contains clinical keywords)

    Rules:
    - Maximum 2 short paragraphs in Summary (≤ 2 sentences each).
    - Bullet points for Key Points and Clinical Relevance.
    - NEVER outputs raw search snippets, URLs, titles, or website names.
    - NEVER concatenates raw search engine output.
    - Does NOT affect knowledge-base (FAISS) formatters.
    """
    chunks  = _split_chunks(context)
    summary = _wiki_summary(chunks)

    # ── Derive a readable topic name from the question ─────────────────────
    q_clean = re.sub(
        r"^(what is|what are|explain|tell me about|define|describe|how does?|why is)\s+",
        "", question.strip(), flags=re.I,
    ).strip()
    topic = q_clean.title() or "Medical Information"

    L: list[str] = ["## 🌐 Web Information", ""]

    if not summary:
        L.append(
            "Detailed web information for this query is not currently available. "
            "Please ask about a specific Philips medical device for detailed information."
        )
        print(f"[refiner] format_dynamic | topic={topic!r} | no_summary")
        return "\n".join(L).rstrip()

    # ── Split summary into at most 4 sentences, group into ≤2 paragraphs ──
    sents = re.split(r"(?<=[.!?])\s+", summary.strip())
    sents = [s.strip() for s in sents if len(s.strip()) > 15]

    # Paragraph 1: sentences 1–2
    # Paragraph 2: sentences 3–4 (if present)
    para1 = " ".join(sents[:2])
    para2 = " ".join(sents[2:4]) if len(sents) > 2 else ""

    L.append("### Summary")
    L.append("")
    L.append(para1)
    if para2:
        L.append("")
        L.append(para2)
    L.append("")

    # ── Key Points: distil bullet-worthy facts from the summary ───────────
    # Extract noun-phrase / clause candidates — sentences with numbers,
    # measurement units, or defining copulas ("is", "are", "refers to").
    kp_candidates: list[str] = []
    for s in sents:
        low = s.lower()
        if any(kw in low for kw in (
            " is ", " are ", "refers to", "used to", "measures", "records",
            "provides", "detects", "monitors", "allows", "enables",
        )):
            # Shorten: trim to first clause (up to first comma or 15 words)
            first_clause = re.split(r",|\band\b", s)[0].strip()
            words = first_clause.split()
            short = " ".join(words[:15]) + ("." if not first_clause.endswith(".") else "")
            if len(short) > 20:
                kp_candidates.append(short)

    if kp_candidates:
        # Deduplicate
        seen_kp: set[str] = set()
        L.append("### Key Points")
        L.append("")
        for kp in kp_candidates[:4]:
            key = kp.lower().strip()
            if key not in seen_kp:
                seen_kp.add(key)
                L.append(f"- {kp}")
        L.append("")

    # ── Clinical Relevance: show only if question has clinical keywords ────
    clinical_kws = (
        "diagnos", "treat", "clinical", "hospital", "patient", "monitor",
        "test", "procedure", "therap", "surgery", "medical", "health",
        "condition", "disease", "symptom",
    )
    q_low = question.lower()
    if any(kw in q_low for kw in clinical_kws):
        # Pull sentences that contain clinical phrasing
        cr_lines: list[str] = []
        for s in sents:
            low = s.lower()
            if any(kw in low for kw in ("diagnos", "treat", "clinical", "hospital", "patient", "used in", "used for")):
                cr_lines.append(s)
        if cr_lines:
            L.append("### Clinical Relevance")
            L.append("")
            for cr in cr_lines[:3]:
                L.append(f"- {cr}")
            L.append("")

    print(f"[refiner] format_dynamic | topic={topic!r} | summary_chars={len(summary)} | kp={len(kp_candidates)}")
    return "\n".join(L).rstrip()


# ── Medical concept knowledge base ────────────────────────────────────────
_CONCEPTS: dict[str, dict] = {
    "ecg": {
        "name": "Electrocardiogram (ECG)",
        "summary": "An ECG records the electrical activity of the heart using skin electrodes, producing a waveform trace used to assess cardiac health.",
        "key_points": [
            "Non-invasive test using electrodes placed on the skin",
            "Records heart rate, rhythm, and electrical conduction",
            "Results are available immediately after the test",
        ],
        "uses": [
            "Diagnosing arrhythmias and conduction abnormalities",
            "Detecting myocardial infarction (heart attack)",
            "Pre-operative cardiac assessment",
            "Routine cardiac monitoring in hospitals and clinics",
        ],
        "benefits": [
            "Painless and non-invasive",
            "Fast results — completed in minutes",
            "No radiation or contrast agents required",
            "Portable devices available for field and ambulance use",
        ],
        "products": ["PageWriter TC50", "PageWriter TC35", "PageWriter TC10", "ST80i Stress Testing System"],
    },
    "electrocardiogram": {
        "name": "Electrocardiogram (ECG / EKG)",
        "summary": "An electrocardiogram measures the heart's electrical impulses to reveal heart rate, rhythm, and structural abnormalities.",
        "key_points": [
            "Measures electrical impulses generated by the heart",
            "Identifies abnormal rhythms, blockages, and ischaemia",
            "Standard diagnostic tool in cardiology worldwide",
        ],
        "uses": [
            "Detecting atrial fibrillation and ventricular arrhythmias",
            "Identifying bundle branch blocks and hypertrophy",
            "Monitoring patients with known cardiac conditions",
        ],
        "benefits": [
            "Rapid, repeatable assessment",
            "Widely available across all clinical settings",
            "No radiation or contrast agents needed",
        ],
        "products": ["PageWriter TC50", "PageWriter TC35", "PageWriter TC10"],
    },
    "arrhythmia": {
        "name": "Cardiac Arrhythmia",
        "summary": "A cardiac arrhythmia is an abnormal heart rhythm caused by irregular electrical signals. It can cause the heart to beat too fast, too slow, or irregularly.",
        "key_points": [
            "Caused by abnormal electrical impulse generation or conduction",
            "Types include atrial fibrillation, ventricular tachycardia, and bradycardia",
            "ECG is the primary diagnostic tool",
        ],
        "uses": [
            "Diagnosed via resting ECG, Holter monitoring, or stress testing",
            "Treated with medication, ablation, or implantable devices",
        ],
        "benefits": [
            "Early detection prevents stroke and heart failure",
            "Wide range of treatment options available",
        ],
        "products": ["PageWriter TC50", "PageWriter TC35"],
    },
    "aed": {
        "name": "Automated External Defibrillator (AED)",
        "summary": "An AED is a portable device that automatically analyses heart rhythm and delivers a controlled electric shock to restore normal rhythm during sudden cardiac arrest.",
        "key_points": [
            "Designed for use by non-medical personnel with voice guidance",
            "Automatically analyses rhythm before delivering a shock",
            "Compact and portable for public access deployment",
        ],
        "uses": [
            "Out-of-hospital cardiac arrest in public spaces",
            "Workplaces, schools, airports, and sports facilities",
            "First-responder use before paramedics arrive",
        ],
        "benefits": [
            "Significantly improves survival rates when used within minutes",
            "Easy to use with clear audio and visual instructions",
            "Compact, lightweight, and low maintenance",
        ],
        "products": ["HeartStart FRx AED", "HeartStart HS1"],
    },
    "defibrillator": {
        "name": "Defibrillator",
        "summary": "A defibrillator delivers a controlled electrical shock to the heart to stop dangerous arrhythmias such as ventricular fibrillation and restore normal rhythm.",
        "key_points": [
            "Available in manual (clinical) and automated (AED) forms",
            "Terminates ventricular fibrillation and pulseless VT",
            "Critical device in cardiac resuscitation protocols",
        ],
        "uses": [
            "Emergency cardiac arrest resuscitation",
            "ICU and cardiac catheterisation labs",
            "Ambulances and emergency response vehicles",
        ],
        "benefits": [
            "Restores normal heart rhythm rapidly",
            "Modern devices include ECG monitoring and pacing",
            "AED models usable by untrained bystanders",
        ],
        "products": ["HeartStart FRx AED", "HeartStart HS1", "Efficia DFM100"],
    },
    "abpm": {
        "name": "Ambulatory Blood Pressure Monitoring (ABPM)",
        "summary": "ABPM automatically records blood pressure at intervals over 24 hours while the patient performs normal activities, providing a complete blood pressure profile.",
        "key_points": [
            "Records BP every 20–30 minutes over 24 hours",
            "Captures daytime, nocturnal, and activity-related variation",
            "Gold standard for confirming hypertension diagnosis",
        ],
        "uses": [
            "Diagnosing white-coat hypertension and masked hypertension",
            "Assessing nocturnal blood pressure dipping",
            "Monitoring antihypertensive therapy effectiveness",
        ],
        "benefits": [
            "Eliminates white-coat effect from single clinic readings",
            "Provides comprehensive 24-hour blood pressure data",
            "Reduces overdiagnosis and unnecessary medication",
        ],
        "products": ["Oscar 2 Ambulatory Blood Pressure Monitor"],
    },
    "ambulatory blood pressure": {
        "name": "Ambulatory Blood Pressure Monitoring (ABPM)",
        "summary": "Ambulatory blood pressure monitoring records BP repeatedly over 24 hours as the patient goes about normal activities, capturing variations missed by a single clinic reading.",
        "key_points": [
            "Worn by the patient during normal daily activities",
            "Automatically inflates and records at set intervals",
            "Provides daytime average, night-time average, and 24-hour mean",
        ],
        "uses": [
            "Hypertension diagnosis and classification",
            "Cardiovascular risk assessment",
            "Guiding antihypertensive medication decisions",
        ],
        "benefits": [
            "More accurate than isolated clinic measurements",
            "Identifies nocturnal hypertension (non-dipping pattern)",
            "Widely recommended by cardiology guidelines",
        ],
        "products": ["Oscar 2 Ambulatory Blood Pressure Monitor"],
    },
    "holter": {
        "name": "Holter Monitor",
        "summary": "A Holter monitor is a wearable ECG device that continuously records cardiac electrical activity over 24–48 hours during normal daily activities.",
        "key_points": [
            "Worn by the patient as a small portable device",
            "Records continuous ECG for 24 to 48 hours",
            "Captures arrhythmias that occur intermittently",
        ],
        "uses": [
            "Investigating unexplained palpitations or syncope",
            "Detecting intermittent arrhythmias not seen on resting ECG",
            "Post-treatment arrhythmia monitoring",
        ],
        "benefits": [
            "Captures events during normal daily activities",
            "Non-invasive and comfortable to wear",
            "Provides detailed long-term cardiac rhythm data",
        ],
        "products": [],
    },
    "stress test": {
        "name": "Cardiac Stress Test",
        "summary": "A cardiac stress test records ECG, blood pressure, and heart rate during controlled exercise to reveal cardiac abnormalities that appear only under physical stress.",
        "key_points": [
            "Performed on a treadmill or cycle ergometer",
            "Reveals ischaemia and arrhythmias provoked by exertion",
            "Includes continuous ECG and blood pressure monitoring",
        ],
        "uses": [
            "Diagnosing coronary artery disease",
            "Evaluating exercise capacity and fitness",
            "Pre-operative cardiac risk assessment",
        ],
        "benefits": [
            "Detects ischaemia not visible at rest",
            "Non-invasive alternative to invasive tests",
            "Guides surgical and medication planning",
        ],
        "products": ["ST80i Stress Testing System"],
    },
    "surgery lights": {
        "name": "Surgical / Operating Theatre Lights",
        "summary": "Surgical lights provide high-intensity, shadow-free illumination of the operative field, enabling surgeons to perform procedures with maximum visibility.",
        "key_points": [
            "Designed for shadow-free, colour-accurate illumination",
            "Adjustable intensity and colour temperature",
            "LED models offer long service life and low heat output",
        ],
        "uses": [
            "All surgical procedures in hospital operating theatres",
            "Procedure rooms and examination areas",
            "Day surgery and outpatient surgical centres",
        ],
        "benefits": [
            "Reduces surgeon fatigue with optimal lighting",
            "Sterilisable handles for infection control",
            "High lux output for deep cavity procedures",
        ],
        "products": [],
    },
    "surgical lights": {
        "name": "Surgical / Operating Theatre Lights",
        "summary": "Surgical lights illuminate the operative field with bright, adjustable, shadow-free light to support safe and precise surgical procedures.",
        "key_points": [
            "Shadow-free illumination across the surgical field",
            "Adjustable arm positioning for precise focus",
            "Available in ceiling-mounted and mobile configurations",
        ],
        "uses": ["Operating theatres", "Day surgery units", "Examination rooms"],
        "benefits": [
            "Consistent illumination throughout long procedures",
            "Ergonomic design reduces repositioning time",
            "LED technology reduces heat at the surgical site",
        ],
        "products": [],
    },
    "cpap": {
        "name": "CPAP (Continuous Positive Airway Pressure)",
        "summary": "CPAP delivers a constant stream of pressurised air to keep airways open, used primarily for sleep apnoea and neonatal respiratory distress.",
        "key_points": [
            "Delivers continuous positive pressure via a mask",
            "Prevents airway collapse during sleep or respiratory distress",
            "Available for adult and neonatal patients",
        ],
        "uses": [
            "Treating obstructive sleep apnoea",
            "Neonatal respiratory distress syndrome in NICUs",
            "Post-operative respiratory support",
        ],
        "benefits": [
            "Non-invasive — avoids the need for intubation",
            "Improves oxygenation and reduces apnoea events",
            "Compact home-use models available",
        ],
        "products": [],
    },
    "ventilator": {
        "name": "Mechanical Ventilator",
        "summary": "A mechanical ventilator assists or replaces spontaneous breathing by delivering controlled volumes of gas to the lungs.",
        "key_points": [
            "Delivers gas at controlled rate, volume, and pressure",
            "Multiple ventilation modes for different patient needs",
            "Integrated monitoring, alarms, and humidification",
        ],
        "uses": [
            "ICU management of respiratory failure",
            "Intraoperative ventilation in operating theatres",
            "Emergency and transport ventilation",
        ],
        "benefits": [
            "Sustains life when spontaneous breathing is inadequate",
            "Lung-protective ventilation modes reduce injury",
            "Real-time monitoring of respiratory parameters",
        ],
        "products": [],
    },
    "pulse oximeter": {
        "name": "Pulse Oximeter",
        "summary": "A pulse oximeter non-invasively measures blood oxygen saturation (SpO₂) and pulse rate using light absorption through the fingertip.",
        "key_points": [
            "Measures SpO₂ and heart rate continuously",
            "Clip-on probe attaches to finger, earlobe, or toe",
            "Immediate results with no blood draw required",
        ],
        "uses": [
            "Continuous SpO₂ monitoring in hospitals",
            "Operating theatre and recovery room monitoring",
            "Home care and emergency settings",
        ],
        "benefits": [
            "Painless and non-invasive",
            "Provides immediate early warning of hypoxaemia",
            "Compact and portable for bedside or field use",
        ],
        "products": [],
    },
    "phototherapy": {
        "name": "Neonatal Phototherapy",
        "summary": "Phototherapy uses specific wavelengths of blue-green light to break down bilirubin in a newborn's skin, treating neonatal jaundice without medication.",
        "key_points": [
            "Uses 430–490 nm blue-green light wavelengths",
            "Converts bilirubin into water-soluble forms for excretion",
            "Delivered via overhead lamps or fibre-optic blankets",
        ],
        "uses": [
            "Treating hyperbilirubinaemia in neonates",
            "Preventing kernicterus (bilirubin-induced brain damage)",
            "NICUs and maternity ward postnatal care",
        ],
        "benefits": [
            "Safe, well-established first-line treatment",
            "Avoids exchange transfusion in most cases",
            "Non-invasive and continuously monitored",
        ],
        "products": [],
    },
    "blood pressure monitor": {
        "name": "Blood Pressure Monitor",
        "summary": "A blood pressure monitor measures the force of blood against artery walls, recording systolic (peak) and diastolic (resting) pressure values used to assess cardiovascular health.",
        "key_points": [
            "Records systolic and diastolic blood pressure values",
            "Available as clinic, home, and ambulatory (24-hour) devices",
            "Non-invasive measurement via an inflatable cuff",
            "Ambulatory monitors record repeatedly over 24 hours during normal activity",
        ],
        "uses": [
            "Diagnosing and monitoring hypertension",
            "Detecting white-coat and masked hypertension",
            "Cardiovascular risk stratification",
            "Monitoring response to antihypertensive therapy",
        ],
        "benefits": [
            "Non-invasive and easy to use",
            "Ambulatory devices capture diurnal variation missed by single readings",
            "Immediate results with no laboratory analysis required",
            "Portable models available for home and ambulatory monitoring",
        ],
        "products": ["Oscar 2 Ambulatory Blood Pressure Monitor"],
    },
    "blood pressure": {
        "name": "Blood Pressure",
        "summary": "Blood pressure is the force exerted by circulating blood against the walls of blood vessels, expressed as systolic pressure over diastolic pressure (e.g. 120/80 mmHg).",
        "key_points": [
            "Measured in millimetres of mercury (mmHg)",
            "Normal range: systolic < 120 mmHg, diastolic < 80 mmHg",
            "Elevated blood pressure (hypertension) increases risk of heart disease and stroke",
            "Measured non-invasively with a sphygmomanometer or automated cuff device",
        ],
        "uses": [
            "Screening for hypertension in routine health check-ups",
            "Monitoring cardiovascular disease risk",
            "Guiding antihypertensive medication dosing",
            "Pre-operative and peri-operative patient assessment",
        ],
        "benefits": [
            "Simple, fast, and non-invasive measurement",
            "Early identification of hypertension reduces cardiovascular events",
            "Home monitoring empowers patient self-management",
            "24-hour ambulatory monitoring provides the most accurate profile",
        ],
        "products": ["Oscar 2 Ambulatory Blood Pressure Monitor"],
    },
}



def format_general_medical(question: str, context: list[str]) -> str:
    """
    general_medical_query — spec format:
        🏥 Medical Concept
        What it is   (definition / summary)
        Purpose      (key points)
        Clinical Use (uses)
        Related Devices
    Uses built-in knowledge base + Wikipedia enrichment.
    Never dumps raw snippets.
    """
    q = question.lower()
    concept: Optional[dict] = None

    # Longest-key match first to avoid short keys shadowing longer ones
    for key in sorted(_CONCEPTS.keys(), key=len, reverse=True):
        if key in q:
            concept = _CONCEPTS[key]
            break

    chunks  = _split_chunks(context)
    wiki    = _wiki_summary(chunks)

    L: list[str] = []

    if concept:
        L.append(f"## 🏥 {concept['name']}")
        L.append("")

        # What it is — prefer Wikipedia if richer
        L.append("### What it is")
        L.append("")
        if wiki and len(wiki) > len(concept["summary"]):
            L.append(wiki)
        else:
            L.append(concept["summary"])
        L.append("")

        # Purpose — key points
        if concept.get("key_points"):
            L.append("### Purpose")
            L.append("")
            for kp in concept["key_points"]:
                L.append(f"• {kp}")
            L.append("")

        # Clinical Use
        if concept.get("uses"):
            L.append("### Clinical Use")
            L.append("")
            for u in concept["uses"]:
                L.append(f"• {u}")
            L.append("")

        # Related Devices
        if concept.get("products"):
            L.append("### Related Devices")
            L.append("")
            for p in concept["products"]:
                L.append(f"• **{p}**")
            L.append("")

    elif wiki:
        # Unknown concept — derive title from query, use wiki prose
        q_clean = re.sub(
            r"^(what is|what are|explain|tell me about|define|describe)\s+",
            "", q, flags=re.I,
        ).strip().title()
        L.append(f"## 🏥 {q_clean or 'Medical Information'}")
        L.append("")

        L.append("### What it is")
        L.append("")
        # Emit up to 2-sentence paragraphs
        sents = re.split(r"(?<=[.!?])\s+", wiki)
        para: list[str] = []
        for i, s in enumerate(sents):
            para.append(s)
            if len(para) == 2 or i == len(sents) - 1:
                L.append(" ".join(para))
                L.append("")
                para = []
    else:
        L.append("## 🏥 Medical Information")
        L.append("")
        L.append(
            "This query relates to a medical concept or device technology. "
            "Please ask about a specific Philips medical device for detailed information."
        )

    matched = concept["name"] if concept else "None"
    print(f"[refiner] format_general_medical | concept={matched!r} | wiki={bool(wiki)}")
    return "\n".join(L).rstrip()


# ══════════════════════════════════════════════════════════════════════════
# SECTION 3 — MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

def refine(
    question: str,
    context: list[str],
    source: str = "faiss",
    intent: str = "product_query",
) -> str:
    """
    Route to the correct formatter based on intent and source.
    Never raises — returns _NO_INFO on any unexpected error.
    """
    try:
        # Wikipedia / dynamic-search sources always go to general formatters
        if source in ("wikipedia", "dynamic_search"):
            if intent == "general_medical_query":
                return format_general_medical(question, context)
            if intent == "category_query":
                return format_category(question, context)
            return format_dynamic(question, context)

        if intent == "feature_query":
            return format_features(question, context)
        if intent == "specification_query":
            return format_specifications(question, context)
        if intent == "comparison_query":
            return format_comparison(question, context)
        if intent == "category_query":
            return format_category(question, context)
        if intent == "general_medical_query":
            return format_general_medical(question, context)

        # Default — product_query
        return format_product(question, context)

    except Exception as exc:
        print(f"[refiner] ERROR: {type(exc).__name__}: {exc}")
        return _NO_INFO
