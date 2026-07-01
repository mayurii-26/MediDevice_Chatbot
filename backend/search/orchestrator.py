"""
search/orchestrator.py
smart_search — orchestrates product, PDF, and dynamic search.
"""
from search.common import SearchResult
from search import product_search, pdf_search, dynamic_search


def smart_search(query: str, intent: str = "product_query") -> SearchResult:
    """
    Main entry point for all retrieval.

    Routing:
      category_query / general_medical_query  → dynamic search only
      all other intents                        → exact match → FAISS → dynamic fallback
                                                 + PDF search on any product hit
    """
    from intent_detector import CATEGORY_QUERY, GENERAL_MEDICAL, COMPARISON_QUERY

    print(f"[search] Detected Intent: {intent}")

    if intent in (CATEGORY_QUERY, GENERAL_MEDICAL):
        print(f"[search] DYNAMIC SEARCH (intent={intent}) | query={query}")
        result = dynamic_search.search(query)
        result.intent = intent
        print(f"[search] WEB | category={result.matched_category} | confidence={result.confidence}")
        return result

    # 1. Exact product name match (handles explicit names like "TC50 vs TC35")
    result = product_search.exact_match(query, intent)
    if result:
        result.intent = intent
        result.pdf_chunks = pdf_search.search(query, matched_product=result.matched_product)
        print(f"[search] EXACT MATCH | product={result.matched_product} | confidence={result.confidence}")
        return result

    # 2a. Comparison: split into two halves, retrieve each independently
    if intent == COMPARISON_QUERY:
        result = product_search.comparison_search(query)
        if result:
            result.intent = intent
            print(f"[search] COMPARISON | product={result.matched_product} | confidence={result.confidence}")
            return result

    # 2b. FAISS semantic search
    result = product_search.faiss_search(query)
    if result:
        result.intent = intent
        result.pdf_chunks = pdf_search.search(query, matched_product=result.matched_product)
        print(f"[search] FAISS | product={result.matched_product} | category={result.matched_category} | confidence={result.confidence}")
        return result

    # 3. Dynamic search fallback
    print(f"[search] DYNAMIC SEARCH | query={query}")
    result = dynamic_search.search(query)
    result.intent = intent
    print(f"[search] WEB | category={result.matched_category} | confidence={result.confidence}")
    return result


# ── Backward-compatible wrappers ───────────────────────────────────────────
def search_products(query: str, top_k: int = 3) -> list[str]:
    """Legacy wrapper."""
    return smart_search(query).chunks


def search_with_fallback(query: str, top_k: int = 3) -> tuple[list[str], str]:
    """Legacy wrapper."""
    result = smart_search(query)
    return result.chunks, result.source
