"""
search/dynamic_search.py
DuckDuckGo web search fallback.
"""
from search.common import SearchResult, detect_category_from_query, web_confidence


def search(query: str) -> SearchResult:
    """DuckDuckGo web search. Returns a SearchResult with source='dynamic_search'."""
    category = detect_category_from_query(query)

    try:
        from dynamic_search.duckduckgo_search import search_web
        from dynamic_search.web_summary import summarise_web_results

        web_results = search_web(query)
        if not web_results:
            return SearchResult(chunks=[], source="fallback", matched_category=category)

        summary = summarise_web_results(web_results)
        return SearchResult(
            chunks=[summary] if summary else [],
            source="dynamic_search",
            matched_product=None,
            matched_category=category,
            confidence=web_confidence(),
        )

    except Exception as e:
        print(f"[dynamic_search] error: {type(e).__name__}")
        return SearchResult(chunks=[], source="fallback", matched_category=category)
