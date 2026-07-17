"""
gemini_service.py
Generates answers using Gemini API.
- Uses google-generativeai SDK (installed in venv).
- Two separate prompt strategies: FAISS knowledge base vs web search.
- Key rotation across GEMINI_API_KEY_1 and GEMINI_API_KEY_2.
- Never exposes raw web snippets or internal context to the user.
- Model and keys loaded ONCE at module level (never per request).
"""
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ── API keys (loaded once at startup) ─────────────────────────────────────
_API_KEYS = [k for k in [
    os.getenv("GEMINI_API_KEY_1"),
    os.getenv("GEMINI_API_KEY_2"),
] if k]

if not _API_KEYS:
    raise RuntimeError("No Gemini API keys found in .env")

_MODEL_NAME = "gemini-2.0-flash"

# ── Static messages ────────────────────────────────────────────────────────
_FALLBACK = (
    "I am a medical device assistant trained on medical device knowledge. "
    "Please ask about supported medical devices. "
    "For further assistance contact support@medideviceai.com"
)

_OUT_OF_SCOPE = (
    "I could not find relevant information for your question in the "
    "medical device knowledge base. Please ask about a specific medical "
    "device or contact support@medidevicechatbot.com for further assistance."
)


# ── Prompt builders ────────────────────────────────────────────────────────

# Common markdown output rule injected into every prompt
_FORMAT_RULES = """OUTPUT FORMAT RULES (mandatory — follow exactly):
- Use markdown formatting in every response.
- Use **bold** for product names, section labels, and key terms.
- Use bullet lists (- item) for features, specifications, and any enumeration.
- Every list item must be on its own line.
- Never merge list items into a single sentence or paragraph.
- Never output raw metadata lines like "Product Name: X" or "Category: Y".
- Never output key:value pairs without formatting them as readable sentences or bullet points.
- Separate sections with a blank line.
- Minimum response length: 3 sentences or 5 bullet points."""


def _build_product_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

{_FORMAT_RULES}

The user is asking about a medical device product.

Instructions:
1. Start with a brief **Overview** paragraph (2-3 sentences) introducing the product by name and purpose.
2. If features are present in the context, list them under a **## Key Features** heading as bullet points.
3. If specifications are present, list them under a **## Specifications** heading as bullet points.
4. End with a short **## Clinical Use** sentence about where or how the device is used.
5. Use ONLY information from the provided context. Do NOT invent details.
6. Do NOT output "Product Name:", "Category:", or any raw metadata lines.
7. Do NOT mention "context", "knowledge base", or "database".
8. If the context does not contain enough information, reply exactly: {_OUT_OF_SCOPE}

Product Information:
{context}

Question: {question}

Answer:"""


def _build_feature_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

{_FORMAT_RULES}

The user is asking specifically about the FEATURES of a medical device.

Instructions:
1. Start with: **Features of [Product Name]** as a heading.
2. List every feature as a separate bullet point in this format:
   - **Feature Name:** Brief description of what it does.
3. Include all features present in the context — do not summarise or omit any.
4. After the feature list, add one sentence about the clinical benefit of these features.
5. Do NOT include raw metadata lines. Do NOT mention "context" or "database".
6. If no features are available in the context, reply exactly: {_OUT_OF_SCOPE}

Product Information:
{context}

Question: {question}

Answer:"""


def _build_specification_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

{_FORMAT_RULES}

The user is asking specifically about the SPECIFICATIONS of a medical device.

Instructions:
1. Start with the heading: **Technical Specifications — [Product Name]**
   (replace [Product Name] with the actual product name from the context)
2. Output ALL specifications as a markdown table in this EXACT format:

   | Parameter | Value |
   |---|---|
   | Spec Name | spec value |
   | Spec Name | spec value |

3. Every specification must be on its own table row — never merge multiple specs into one row.
4. Use ONLY specifications from the provided context. Do NOT invent values.
5. Do NOT include features, overview, or marketing text — specifications table only.
6. Do NOT output bullet points, raw "Key: value" lines, or plain prose.
7. Do NOT mention "context", "knowledge base", or "database".
8. If no specifications are present in the context, output exactly this two-line message:
   Detailed specifications are currently unavailable.
   Please refer to the official product datasheet.

Product Information:
{context}

Question: {question}

Answer:"""


def _build_comparison_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

{_FORMAT_RULES}

The user wants to COMPARE two or more medical devices.

Instructions:
1. Create a markdown comparison table using this exact format:

   | Feature | [Product 1 Name] | [Product 2 Name] |
   |---------|-----------------|-----------------|
   | Category | ... | ... |
   | Device Type | ... | ... |
   | Key Features | ... | ... |
   | Specifications | ... | ... |
   | Clinical Use | ... | ... |

2. Replace [Product 1 Name] and [Product 2 Name] with the actual product names from the context.
3. Fill every table cell with real data from the context. Use "—" only if data is genuinely missing.
4. After the table, add a **## Summary** section with 2-3 sentences about the key differences.
5. Use ONLY information from the provided context. Do NOT invent specifications.
6. Do NOT output raw metadata lines. Do NOT mention "context" or "database".
7. If there is insufficient information for a comparison, reply exactly: {_OUT_OF_SCOPE}

Product Information:
{context}

Question: {question}

Answer:"""


def _build_category_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

{_FORMAT_RULES}

The user is asking about a CATEGORY of medical devices.

Instructions:
1. Start with a **## [Category Name] Devices** heading.
2. Write 2-3 sentences explaining what this category covers and its clinical role.
3. List the available devices in this category under a **## Available Devices** heading:
   - **[Product Name]:** One-sentence description of what it does.
   (one bullet per product, using actual product names from the context)
4. End with a **## Clinical Applications** sentence about where these devices are used.
5. Do NOT focus on a single product. Give a broad, category-level answer.
6. Do NOT output raw metadata lines. Do NOT mention "context", "web search", or "database".

Context:
{context}

Question: {question}

Answer:"""


def _build_general_medical_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

{_FORMAT_RULES}

The user is asking about a general medical concept or technology.

Instructions:
1. Start with the heading: # 🏥 [Medical Concept Name]
   (replace [Medical Concept Name] with the correct name of the concept)
2. Write a 2-3 sentence summary paragraph explaining what the concept is.
3. Add a ## Key Points section as a bullet list (3-5 points about how it works or what it measures).
4. Add a ## Common Uses section as a bullet list (3-5 clinical uses or situations where it is used).
5. Add a ## Benefits section as a bullet list (3-4 clinical benefits).
6. If the context mentions specific medical device products by name, add a ## Related Philips Products section as a bullet list:
   - **[Product Name]**
7. Be medically accurate. Use ONLY information from the context — do NOT fabricate clinical claims.
8. Do NOT mention "context", "web search", "Wikipedia", "DuckDuckGo", or "database".
9. Do NOT copy raw search result titles or URLs.
10. Do NOT output "What it is:" / "How it works:" prose paragraphs — use the section headings above.

Context:
{context}

Question: {question}

Answer:"""


def _build_web_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

{_FORMAT_RULES}

Instructions:
1. Start with the heading: # 🏥 [Medical Concept Name]
   (replace [Medical Concept Name] with the correct name of the concept or device)
2. Write a 2-3 sentence summary paragraph explaining what the concept is.
3. Add a ## Key Points section as a bullet list (3-5 points).
4. Add a ## Common Uses section as a bullet list (3-5 clinical uses).
5. Add a ## Benefits section as a bullet list (3-4 clinical benefits).
6. If related medical device products are mentioned, add a ## Related Philips Products section.
7. Synthesise from the search context — do NOT copy snippets verbatim.
8. Do NOT mention "search results", "web search", "DuckDuckGo", or any search engine name.
9. Do NOT output raw URLs or result titles.
10. If results are not relevant to the question, reply exactly: {_OUT_OF_SCOPE}

Search Context:
{context}

Question: {question}

Answer:"""


def _build_wikipedia_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

{_FORMAT_RULES}

The context contains verified medical background information from a trusted reference source.

Instructions:
1. Start with the heading: # 🏥 [Medical Concept Name]
   (replace [Medical Concept Name] with the correct name of the concept)
2. Write a 2-3 sentence summary paragraph explaining what the concept is.
3. Add a ## Key Points section as a bullet list (3-5 points about how it works or what it measures).
4. Add a ## Common Uses section as a bullet list (3-5 clinical uses or situations).
5. Add a ## Benefits section as a bullet list (3-4 clinical benefits).
6. If related medical device products are mentioned in the context, add a ## Related Philips Products section:
   - **[Product Name]**
7. Be medically accurate. Do NOT fabricate names, numbers, or clinical claims.
8. Do NOT mention "Wikipedia", "web search", "context", or "database".
9. Do NOT copy raw URLs, reference numbers, or source headings.
10. If the context is not relevant to the question, reply exactly: {_OUT_OF_SCOPE}

Medical Background:
{context}

Question: {question}

Answer:"""


# ── Quota error detection ──────────────────────────────────────────────────
def _is_quota_error(e: Exception) -> bool:
    s = str(e).lower()
    return any(k in s for k in ["quota", "429", "resource_exhausted"])


# ── Core call with key rotation ────────────────────────────────────────────
def _call_gemini(prompt: str) -> str | None:
    """
    Try each API key in order.
    Returns the text response or None if all keys fail.
    Never raises.
    """
    prompt_preview = prompt[:120].replace("\n", " ")
    print(f"[gemini] REQUEST SENT | model={_MODEL_NAME} | keys_available={len(_API_KEYS)} | prompt_preview={prompt_preview!r}")

    for i, api_key in enumerate(_API_KEYS):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(_MODEL_NAME)
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 1024,
                }
            )
            if hasattr(response, "text") and response.text:
                answer_preview = response.text.strip()[:80].replace("\n", " ")
                print(f"[gemini] RESPONSE RECEIVED | key={i + 1} | chars={len(response.text)} | preview={answer_preview!r}")
                return response.text.strip()
            print(f"[gemini] EMPTY RESPONSE | key={i + 1} | response={response}")
            return None

        except Exception as e:
            if _is_quota_error(e):
                print(f"[gemini] QUOTA EXHAUSTED | key={i + 1} | error={str(e)[:200]}")
                import re
                match = re.search(r"retry in (\d+)", str(e).lower())
                wait = int(match.group(1)) if match else 5
                wait = min(wait, 10)  # cap at 10s so UI doesn't hang
                import time
                time.sleep(wait)
                continue
            print(f"[gemini] HARD ERROR | key={i + 1} | type={type(e).__name__} | error={str(e)[:200]}")
            return None

    print(f"[gemini] ALL KEYS EXHAUSTED | FALLBACK TRIGGERED | keys_tried={len(_API_KEYS)}")
    return None


# ── Rule-based extractive summarizer (Gemini-unavailable path) ────────────

import re as _re

# Patterns for lines that are pure noise — never include these
_NOISE_PATTERNS = [
    _re.compile(r"^\s*\d+\s*$"),                              # lone page numbers
    _re.compile(r"^\s*page\s+\d+", _re.I),                   # "Page 6 of 8"
    _re.compile(r"©|copyright|all rights reserved", _re.I),  # copyright
    _re.compile(r"philips\s+(healthcare|medical systems)\s*$", _re.I),  # footer brand
    _re.compile(r"^www\.", _re.I),                            # URLs
    _re.compile(r"^\s*https?://", _re.I),
    _re.compile(r"^\s*[\-\|_=]{3,}\s*$"),                    # divider lines
    _re.compile(r"^\s*confidential", _re.I),
    _re.compile(r"for\s+(professional|healthcare)\s+use\s+only", _re.I),
    _re.compile(r"^\s*\d+\s+of\s+\d+\s*$", _re.I),          # "6 of 8"
]

# A line is worth keeping if it has enough real words
_MIN_WORDS = 2

def _is_noise(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if len(s.split()) < _MIN_WORDS:
        return True
    return any(p.search(s) for p in _NOISE_PATTERNS)


def _score(line: str) -> int:
    """Higher = more informative. Simple heuristic scoring."""
    s = line.lower()
    score = 0
    # Technical/medical content signals
    for kw in ("display", "measurement", "parameter", "accuracy", "battery",
               "weight", "size", "resolution", "range", "voltage", "connectivity",
               "wireless", "alarm", "monitoring", "detection", "output", "input",
               "patient", "clinical", "iso", "standard", "approved", "fda",
               "waveform", "leads", "channel", "memory", "storage", "print"):
        if kw in s:
            score += 1
    # Prefer sentences with numbers (specs tend to have them)
    if _re.search(r"\d", s):
        score += 1
    # Prefer longer sentences (more content)
    score += min(len(s.split()) // 5, 3)
    return score


def _extract_bullets(text: str, max_bullets: int = 12, min_bullets: int = 8) -> list[str]:
    """
    From a block of text return 8–12 clean, informative lines as bullet candidates.
    Steps:
      0. Pre-split collapsed bullet runs ("• a • b" → two lines).
      1. Split into lines, strip whitespace.
      2. Remove noise lines.
      3. Deduplicate (case-insensitive).
      4. Score and sort — keep top candidates.
      5. Restore original order for readability.
      6. Cap at max_bullets; pad to min_bullets only if enough lines exist.
    """
    # Step 0: expand collapsed bullet markers onto separate lines
    text = _re.sub(r"\s*[•●○▪]\s*", "\n", text)
    # Expand numbered list items: "1. item 2. item" → split on digits+dot
    text = _re.sub(r"(?<!\n)(\d+\.\s)", r"\n\1", text)

    raw_lines = [l.strip() for l in text.splitlines()]
    seen: set[str] = set()
    candidates: list[tuple[int, int, str]] = []  # (original_index, score, line)

    for idx, line in enumerate(raw_lines):
        if _is_noise(line):
            continue
        key = _re.sub(r"\s+", " ", line.lower())
        if key in seen:
            continue
        seen.add(key)
        candidates.append((idx, _score(line), line))

    if not candidates:
        return []

    # Sort by score descending, take top max_bullets, then restore original order
    top = sorted(candidates, key=lambda x: -x[1])[:max_bullets]
    top.sort(key=lambda x: x[0])   # back to document order
    return [line for _, _, line in top]


def _format_raw_context(chunks: list, intent: str = "product_query", question: str = "") -> str:
    """
    Deterministic fallback when Gemini is unavailable or its refiner call fails.

    Always routes through response_refiner.refine() — the single source of
    truth for formatting — so the output is identical regardless of whether
    Gemini is available.

    If the incoming chunks are raw FAISS chunks (Product Name: / Category: /
    Description: / Features: / Specifications: labels), they are first
    pre-formatted through the same _format_product_chunk() logic used by
    app.py before reaching response_refiner.  This guarantees the refiner
    always receives the '📦 Product / Category / Summary / Features /
    Specifications' structure it expects.
    """
    if not chunks:
        return _OUT_OF_SCOPE

    try:
        # ── Determine whether chunks need pre-formatting ──────────────────
        # Chunks that came from combined_context (already formatted by
        # app.py._format_product_chunk) start with the '📦 Product' header.
        # Raw FAISS chunks start with 'Product Name: ...'.
        # We pre-format only the raw ones to avoid double-processing.
        def _looks_raw(chunk: str) -> bool:
            return bool(_re.search(r"(?m)^Product Name\s*:", chunk))

        def _format_product_chunk(chunk: str) -> str:
            """Mirror of app.py._format_product_chunk — converts raw FAISS text."""
            from search.common import extract_product_name, extract_category
            name     = extract_product_name(chunk) or "Unknown Product"
            category = extract_category(chunk) or "Unknown"

            desc_m = _re.search(
                r"Description:\s*(.+?)(?=\nFeatures:|\nSpecifications:|$)",
                chunk, _re.DOTALL,
            )
            description = desc_m.group(1).strip() if desc_m else ""

            parts = [f"📦 Product\n\n{name}\n\nCategory\n{category}"]

            if description:
                parts.append(f"Summary\n\n{description}")

            feat_m = _re.search(r"Features:\s*\n((?:- .+\n?)+)", chunk)
            if feat_m:
                parts.append(f"Features\n\n{feat_m.group(1).strip()}")

            spec_m = _re.search(r"Specifications:\s*\n((?:- .+\n?)+)", chunk)
            if spec_m:
                parts.append(f"Specifications\n\n{spec_m.group(1).strip()}")

            return "\n\n".join(parts)

        # Split combined-context strings on the '---' separator so each
        # product chunk is a separate item, then pre-format raw ones.
        formatted_chunks: list[str] = []
        for c in chunks:
            if not isinstance(c, str) or not c.strip():
                continue
            parts = _re.split(r"\n\n---\n\n", c)
            for part in parts:
                if not part.strip():
                    continue
                if _looks_raw(part):
                    formatted_chunks.append(_format_product_chunk(part.strip()))
                else:
                    formatted_chunks.append(part.strip())

        if not formatted_chunks:
            return _OUT_OF_SCOPE

        # ── Route through response_refiner (single formatter) ────────────
        from response_refiner import refine as _refine
        result = _refine(question, formatted_chunks, "faiss", intent)
        if result and len(result.strip()) > 40:
            print(f"[gemini] _format_raw_context via response_refiner | intent={intent} | chars={len(result)}")
            return result

    except Exception as exc:
        print(f"[gemini] _format_raw_context error: {exc}")

    return _OUT_OF_SCOPE


# ── Public API ─────────────────────────────────────────────────────────────
def generate_answer(question: str, context: list, source: str = "faiss", intent: str = "product_query") -> str:
    """
    Generate a response using response_refiner as the primary engine.
    Gemini is called only as an optional polish layer — if it fails for any
    reason the refiner output is returned directly.

    Pipeline:
        1. response_refiner.refine()  ← always runs, always produces output
        2. _call_gemini(prompt)       ← optional; improves wording if available
        3. Return refiner output if Gemini is unavailable or returns empty
    """
    from intent_detector import (
        FEATURE_QUERY, SPECIFICATION_QUERY, COMPARISON_QUERY,
        CATEGORY_QUERY, GENERAL_MEDICAL,
    )

    # ── Step 1: deterministic refiner (primary, never fails) ──────────────
    try:
        from response_refiner import refine as _refine
        base_answer = _refine(question, context, source, intent)
        print(f"[gemini] REFINER COMPLETE | intent={intent} | chars={len(base_answer)}")
    except Exception as _re_err:
        print(f"[gemini] refiner error (non-fatal): {_re_err}")
        base_answer = _format_raw_context(context, intent=intent, question=question)

    if not context:
        return base_answer

    # ── Step 2: Gemini polish (optional) ──────────────────────────────────
    context_text  = "\n\n".join(context)
    clean_context = context_text.replace("[Web Search Results]\n", "").strip()

    if source == "wikipedia":
        prompt = _build_wikipedia_prompt(question, clean_context)
    elif source == "dynamic_search":
        if intent == CATEGORY_QUERY:
            prompt = _build_category_prompt(question, clean_context)
        elif intent == GENERAL_MEDICAL:
            prompt = _build_general_medical_prompt(question, clean_context)
        else:
            prompt = _build_web_prompt(question, clean_context)
    elif intent == FEATURE_QUERY:
        prompt = _build_feature_prompt(question, clean_context)
    elif intent == SPECIFICATION_QUERY:
        prompt = _build_specification_prompt(question, clean_context)
    elif intent == COMPARISON_QUERY:
        prompt = _build_comparison_prompt(question, clean_context)
    else:
        prompt = _build_product_prompt(question, clean_context)

    gemini_result = _call_gemini(prompt)

    if gemini_result and len(gemini_result.strip()) > len(base_answer) * 0.5:
        # ── Comparison guard: Gemini must return a table, not raw prose ───
        # ── Comparison guard: must have ### sections or a table ──────────
        # format_comparison() now emits ### sections (no table).
        # Accept Gemini output that has either ### headers or a | table.
        if intent == COMPARISON_QUERY:
            _has_section = any(
                l.strip().startswith("###")
                for l in gemini_result.splitlines()
            )
            _has_table = any(
                l.strip().startswith("|") and l.strip().endswith("|")
                for l in gemini_result.splitlines()
            )
            if not _has_section and not _has_table:
                print(
                    f"[gemini] COMPARISON STRUCTURE MISSING in Gemini output "
                    f"— using refiner | intent={intent} | source={source}"
                )
                return base_answer

        # ── Specification guard: must have bullets or table ───────────────
        # format_specifications() now emits "• **Param:** value" bullets.
        # Accept bullet list, markdown table, or unavailable message.
        if intent == SPECIFICATION_QUERY:
            _spec_unavail = "detailed specifications are currently unavailable"
            _has_bullets  = "•" in gemini_result
            _has_table    = any(
                l.strip().startswith("|") and l.strip().endswith("|")
                for l in gemini_result.splitlines()
            )
            if not _has_bullets and not _has_table and _spec_unavail not in gemini_result.lower():
                print(
                    f"[gemini] SPECIFICATION CONTENT MISSING in Gemini output "
                    f"— using refiner | intent={intent} | source={source}"
                )
                return base_answer

        # ── General medical guard: must have 🏥 heading or known sections ─
        if intent == GENERAL_MEDICAL:
            _has_hc_heading = any(
                "\U0001f3e5" in line   # 🏥 U+1F3E5
                for line in gemini_result.splitlines()
            )
            _known_secs = (
                "### What it is", "### Purpose", "### Clinical Use",
                "## Key Points", "## Common Uses",
            )
            _sec_count = sum(1 for s in _known_secs if s in gemini_result)
            if not _has_hc_heading and _sec_count < 2:
                print(
                    f"[gemini] GENERAL_MEDICAL STRUCTURE MISSING in Gemini output "
                    f"— using refiner | intent={intent} | source={source}"
                )
                return base_answer

        print(f"[gemini] ANSWER SOURCE: gemini_polish | intent={intent} | source={source}")
        return gemini_result

    # Gemini unavailable or returned something shorter than refiner — use refiner
    print(f"[gemini] ANSWER SOURCE: refiner | intent={intent} | source={source} | gemini_available={bool(gemini_result)}")
    return base_answer


async def generate_answer_streaming(question: str, context: list, source: str = "faiss", intent: str = "product_query"):
    """
    Async generator that yields response tokens.

    Pipeline:
        1. response_refiner.refine()  ← runs synchronously, always produces output
        2. Try Gemini streaming       ← optional polish; if successful yields its tokens
        3. If Gemini fails            ← yield the refiner output in 64-char chunks

    This ensures the user always gets a complete, formatted response even when
    Gemini is unavailable.
    """
    from intent_detector import (
        FEATURE_QUERY, SPECIFICATION_QUERY, COMPARISON_QUERY,
        CATEGORY_QUERY, GENERAL_MEDICAL,
    )

    # ── Step 1: deterministic refiner (always runs first) ─────────────────
    try:
        from response_refiner import refine as _refine
        base_answer = _refine(question, context, source, intent)
        print(f"[gemini/stream] REFINER COMPLETE | intent={intent} | chars={len(base_answer)}")
    except Exception as _re_err:
        print(f"[gemini/stream] refiner error (non-fatal): {_re_err}")
        base_answer = _format_raw_context(context, intent=intent, question=question)

    if not context:
        yield base_answer
        return

    # ── Step 2: Gemini streaming (optional polish) ─────────────────────────
    context_text  = "\n\n".join(context)
    clean_context = context_text.replace("[Web Search Results]\n", "").strip()

    if source == "wikipedia":
        prompt = _build_wikipedia_prompt(question, clean_context)
    elif source == "dynamic_search":
        if intent == CATEGORY_QUERY:
            prompt = _build_category_prompt(question, clean_context)
        elif intent == GENERAL_MEDICAL:
            prompt = _build_general_medical_prompt(question, clean_context)
        else:
            prompt = _build_web_prompt(question, clean_context)
    elif intent == FEATURE_QUERY:
        prompt = _build_feature_prompt(question, clean_context)
    elif intent == SPECIFICATION_QUERY:
        prompt = _build_specification_prompt(question, clean_context)
    elif intent == COMPARISON_QUERY:
        prompt = _build_comparison_prompt(question, clean_context)
    else:
        prompt = _build_product_prompt(question, clean_context)

    for i, api_key in enumerate(_API_KEYS):
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(_MODEL_NAME)
            print(f"[gemini/stream] REQUEST SENT | key={i + 1} | model={_MODEL_NAME} | intent={intent} | source={source}")
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.3, "max_output_tokens": 1024},
                stream=True,
            )
            token_count = 0

            # ── Structure-required guard: buffer the full response first ──
            # For comparison_query, specification_query, and general_medical_query
            # we must verify correct structure before emitting tokens.
            if intent in (COMPARISON_QUERY, SPECIFICATION_QUERY, GENERAL_MEDICAL):
                buffered = ""
                for chunk in response:
                    if hasattr(chunk, "text") and chunk.text:
                        buffered += chunk.text
                        token_count += 1

                # Check structural requirement per intent
                if intent == COMPARISON_QUERY:
                    _ok = any(
                        l.strip().startswith("###")
                        for l in buffered.splitlines()
                    ) or any(
                        l.strip().startswith("|") and l.strip().endswith("|")
                        for l in buffered.splitlines()
                    )
                    _reason = "### sections or table"
                elif intent == SPECIFICATION_QUERY:
                    _spec_unavail = "detailed specifications are currently unavailable"
                    _ok = (
                        "•" in buffered
                        or any(l.strip().startswith("|") and l.strip().endswith("|") for l in buffered.splitlines())
                        or _spec_unavail in buffered.lower()
                    )
                    _reason = "bullets or table"
                else:  # GENERAL_MEDICAL
                    _has_hc = any("\U0001f3e5" in l for l in buffered.splitlines())
                    _known_secs = ("### What it is", "### Purpose", "### Clinical Use",
                                   "## Key Points", "## Common Uses")
                    _sec_count = sum(1 for s in _known_secs if s in buffered)
                    _ok = _has_hc or _sec_count >= 2
                    _reason = "🏥 heading or sections"

                if _ok:
                    print(
                        f"[gemini/stream] RESPONSE COMPLETE ({intent}, {_reason} OK) "
                        f"| key={i + 1} | chunks_buffered={token_count}"
                    )
                    print(f"[gemini/stream] ANSWER SOURCE: gemini_polish | intent={intent} | source={source}")
                    chunk_size = 64
                    for pos in range(0, len(buffered), chunk_size):
                        yield buffered[pos:pos + chunk_size]
                    return
                else:
                    print(
                        f"[gemini/stream] STRUCTURE MISSING ({_reason}) in Gemini output "
                        f"— using refiner | key={i + 1} | intent={intent} | source={source}"
                    )
                    break

            else:
                # Non-comparison: stream tokens as they arrive (original behaviour)
                for chunk in response:
                    if hasattr(chunk, "text") and chunk.text:
                        token_count += 1
                        yield chunk.text
                print(f"[gemini/stream] RESPONSE COMPLETE | key={i + 1} | chunks_yielded={token_count}")
                print(f"[gemini/stream] ANSWER SOURCE: gemini_polish | intent={intent} | source={source}")
                return  # Gemini succeeded — done

        except Exception as e:
            if _is_quota_error(e):
                print(f"[gemini/stream] QUOTA EXHAUSTED | key={i + 1} | error={str(e)[:200]}")
                import re as _re2, time
                match = _re2.search(r"retry in (\d+)", str(e).lower())
                wait = min(int(match.group(1)) if match else 5, 10)
                time.sleep(wait)
                continue
            print(f"[gemini/stream] HARD ERROR | key={i + 1} | type={type(e).__name__} | error={str(e)[:200]}")
            break

    # ── Step 3: Gemini unavailable — stream refiner output ────────────────
    print(f"[gemini/stream] ANSWER SOURCE: refiner | intent={intent} | source={source} | GEMINI UNAVAILABLE")
    chunk_size = 64
    for i in range(0, len(base_answer), chunk_size):
        yield base_answer[i:i + chunk_size]
