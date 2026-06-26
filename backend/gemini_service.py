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
def _build_product_prompt(question: str, context: str) -> str:
    return f"""You are a professional Medical Device Assistant for a healthcare chatbot.

Instructions:
- Answer using ONLY the provided product information.
- Include product name, category, description, key features, and specifications if present.
- Write clearly and professionally.
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

    if source == "dynamic_search":
        return _FALLBACK

    # Gemini unavailable — use structured fallback formatter
    from fallback_formatter import (
        format_product_answer, format_feature_answer,
        format_specification_answer, format_category_answer,
        format_comparison_answer, format_general_medical_answer,
    )

    if not context:
        return _FALLBACK

    if intent == FEATURE_QUERY:
        return format_feature_answer(context)
    if intent == SPECIFICATION_QUERY:
        return format_specification_answer(context)
    if intent == COMPARISON_QUERY:
        return format_comparison_answer(context)
    if intent == CATEGORY_QUERY:
        return format_category_answer(context)
    if intent == GENERAL_MEDICAL:
        return format_general_medical_answer(question, context)
    return format_product_answer(context)
