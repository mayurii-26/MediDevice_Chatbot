"""
search/__init__.py
Re-exports the public search API so existing imports remain unchanged.
"""
from search.common import SearchResult, normalise_query
from search.orchestrator import smart_search, search_products, search_with_fallback

# Expose the sentence-transformer model from product_search so cache_service.py
# can continue to import it as `from search import _model`.
from search.product_search import model as _model

__all__ = [
    "SearchResult",
    "normalise_query",
    "smart_search",
    "search_products",
    "search_with_fallback",
    "_model",
]
