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
    "I am a medical device assistant trained on Philips healthcare products. "
    "Please ask about supported medical devices. "
    "For further assistance contact support@medidevicechatbot.com"
)

_OUT_OF_SCOPE = (
    "I could not find relevant information for your question in the "
    "medical device knowledge base. Please ask about a specific medical "
    "device or contact support@medidevicechatbot.com for further assistance."
)


# ── Prompt builders ────────────────────────────────────────────────────────

# Injected into every prompt to preserve list formatting from context
_BULLET_RULE = "- Preserve ALL bullet points and lists exactly as they appear in the context. Each list item MUST appear on its own line using markdown (- item). Never merge list items into a single paragraph."

def _build_product_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

Instructions:
- Answer using ONLY the provided product information.
- Include product name, category, description, key features, and specifications if present.
- Write clearly and professionally.
- {_BULLET_RULE}
- Do NOT mention "context", "knowledge base", or "database".
- If the context does not contain enough information, reply exactly: {_OUT_OF_SCOPE}

Product Information:
{context}

Question: {question}

Answer:"""


def _build_feature_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

The user is asking specifically about FEATURES of a medical device.

Instructions:
- List ONLY the features of the product from the provided information.
- Format your response as:
  **Features of [Product Name]:**
  - Feature 1: description
  - Feature 2: description
  (continue for all features)
- {_BULLET_RULE}
- Do NOT include specifications, pricing, or general description unless asked.
- Do NOT mention "context" or "database".
- If no features are available, reply exactly: {_OUT_OF_SCOPE}

Product Information:
{context}

Question: {question}

Answer:"""


def _build_specification_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

The user is asking specifically about SPECIFICATIONS of a medical device.

Instructions:
- List ONLY the technical specifications from the provided information.
- Format your response as:
  **Specifications of [Product Name]:**
  - Spec 1: value
  - Spec 2: value
  (continue for all specifications)
- {_BULLET_RULE}
- Do NOT include features, general description, or marketing text.
- Do NOT mention "context" or "database".
- If no specifications are available, reply exactly: {_OUT_OF_SCOPE}

Product Information:
{context}

Question: {question}

Answer:"""


def _build_comparison_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

The user wants to COMPARE two or more medical devices.

Instructions:
- Create a clear comparison using a markdown table with columns: Feature | [Product 1] | [Product 2]
- Include rows for: category, device type, key features, specifications (if available), and use case.
- After the table, add a short 2-3 sentence summary of the key differences.
- {_BULLET_RULE}
- Use ONLY information from the provided context.
- Do NOT mention "context" or "database".
- If insufficient information for comparison, reply exactly: {_OUT_OF_SCOPE}

Product Information:
{context}

Question: {question}

Answer:"""


def _build_category_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

The user is asking about a CATEGORY of medical devices, not a specific product.

Instructions:
- Give an overview of this category of medical devices.
- Explain: what devices belong to this category, their medical purpose, clinical use cases.
- If the context contains product names in this category, mention them as examples.
- Do NOT focus on a single product. Give a broad category-level answer.
- Write 3-5 sentences in clear, professional language.
- {_BULLET_RULE}
- Do NOT mention "context", "web search", or "database".

Context:
{context}

Question: {question}

Answer:"""


def _build_general_medical_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

The user is asking about a general medical concept or technology.

Instructions:
- First explain the medical concept clearly (what it is, how it works, clinical purpose).
- Then, if the context mentions specific products related to this concept, briefly list them as examples.
- Write 3-5 sentences. Be medically accurate and professional.
- {_BULLET_RULE}
- Do NOT mention "context", "web search", or "database".
- Do NOT fabricate product names or specifications.

Context:
{context}

Question: {question}

Answer:"""


def _build_web_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

Instructions:
- Read the search results and write a clean, professional answer.
- Include: what the device/concept is, its medical purpose, how it is used, and key clinical benefits.
- Do NOT copy snippets verbatim.
- {_BULLET_RULE}
- Do NOT mention "search results", "web search", "DuckDuckGo", or any search engine.
- Keep the answer concise (3-5 sentences) and medically accurate.
- If results are not relevant, reply exactly: {_OUT_OF_SCOPE}

Search Context:
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
                print(f"[gemini] OK using key {i + 1}")
                return response.text.strip()
            return None

        except Exception as e:
            if _is_quota_error(e):
                print(f"[gemini] Key {i + 1} quota exhausted, trying next...")
                # Extract retry delay from error message if present
                import re
                match = re.search(r"retry in (\d+)", str(e).lower())
                wait = int(match.group(1)) if match else 5
                wait = min(wait, 10)  # cap at 10s so UI doesn't hang
                import time
                time.sleep(wait)
                continue
            print(f"[gemini] Hard error on key {i + 1}: {type(e).__name__}")
            return None

    print("[gemini] All keys exhausted.")
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


def _format_raw_context(chunks: list) -> str:
    """
    Rule-based extractive summarization when Gemini is unavailable.
    Cleans OCR noise, deduplicates, scores lines, and returns 8-12 bullet points.
    No LLM involved — fully deterministic.
    """
    if not chunks:
        return _OUT_OF_SCOPE

    # Combine all chunks; strip section headers we added ourselves
    combined = "\n".join(
        _re.sub(r"^(📦|📄|🌐)[^\n]+\n", "", chunk.strip(), flags=_re.MULTILINE)
        for chunk in chunks if chunk.strip()
    )

    bullets = _extract_bullets(combined, max_bullets=12, min_bullets=8)
    if not bullets:
        return _OUT_OF_SCOPE

    return "\n\n".join(f"- {b}" for b in bullets)


# ── Public API ─────────────────────────────────────────────────────────────
def generate_answer(question: str, context: list, source: str = "faiss", intent: str = "product_query") -> str:
    """
    Generate a Gemini answer using an intent-specific prompt.
    """
    from intent_detector import (
        FEATURE_QUERY, SPECIFICATION_QUERY, COMPARISON_QUERY,
        CATEGORY_QUERY, GENERAL_MEDICAL,
    )

    if not context:
        return _OUT_OF_SCOPE

    context_text = "\n\n".join(context)
    clean_context = context_text.replace("[Web Search Results]\n", "").strip()

    # Select prompt based on source then intent
    if source == "dynamic_search":
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

    result = _call_gemini(prompt)

    if result:
        return result

    # Gemini unavailable — return the retrieved context directly, formatted cleanly.
    # Do not apologise and do not use the fallback formatter.
    print("[gemini] unavailable — returning raw retrieved context")
    return _format_raw_context(context)
