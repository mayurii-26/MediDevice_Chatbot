"""
search.py — compatibility shim.
All logic now lives in the search/ package.
This file re-exports the full public API so existing imports are unaffected.
"""
from search.common import SearchResult, normalise_query          # noqa: F401
from search.product_search import model as _model               # noqa: F401
from search.orchestrator import (                               # noqa: F401
    smart_search,
    search_products,
    search_with_fallback,
)
