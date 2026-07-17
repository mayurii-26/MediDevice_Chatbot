"""
search/orchestrator.py

smart_search — orchestrates product, PDF, and dynamic search.

Pipeline (updated)
------------------
  User query
      │
  query_rewriter.rewrite()          ← NEW: expand abbreviations, strip filler
      │ canonical + variants
      │
  [exact_match / comparison_search] ← unchanged (uses rewritten canonical)
      │ (if no exact match)
  hybrid_search (BM25 + FAISS)      ← uses canonical + variants
      │ up to 10+10 candidates
      │
  reranker.rerank(original, chunks) ← NEW: CrossEncoder top-5 selection
      │ top-5 product chunks
      │
  pdf_search                        ← unchanged (product-filtered)
      │
  SearchResult

Notes
-----
- exact_match and comparison_search are EXEMPT from reranking: they already
  have high-confidence, product-anchored results that don't benefit from a
  general-purpose cross-encoder.
- dynamic_search (category/general_medical) is EXEMPT: no product chunks
  to rerank, and web snippets have different score distributions.
- All existing API signatures (smart_search, search_products,
  search_with_fallback) are unchanged.
"""
from search.common import SearchResult
from search import product_search, pdf_search, dynamic_search


def smart_search(query: str, intent: str = "product_query") -> SearchResult:
    """
    Main entry point for all retrieval.

    Routing:
      category_query / general_medical_query  → dynamic search only
      comparison_query                         → exact match → comparison_search
      all other intents                        → exact match → hybrid FAISS/BM25
                                                 → rerank → PDF search
    """
    from intent_detector import CATEGORY_QUERY, GENERAL_MEDICAL, COMPARISON_QUERY

    print(f"[search] Detected Intent: {intent}")

    # ── Dynamic search — no reranking needed ──────────────────────────────
    if intent in (CATEGORY_QUERY, GENERAL_MEDICAL):
        print(f"[search] DYNAMIC SEARCH (intent={intent}) | query={query}")
        result = dynamic_search.search(query)
        result.intent = intent
        print(f"[search] WEB | category={result.matched_category} | confidence={result.confidence}")

        # ── Wikipedia enrichment (GENERAL_MEDICAL only) ───────────────────
        # Triggered when:
        #   a) intent is exactly GENERAL_MEDICAL (never for CATEGORY_QUERY), AND
        #   b) the guard confirms no product fragment is present, AND
        #   c) DuckDuckGo returned fewer than 2 chunks OR source is 'fallback'
        #      (Wikipedia supplements a weak web result, never replaces FAISS)
        if intent == GENERAL_MEDICAL:
            _ddg_weak = len(result.chunks) < 2 or result.source == "fallback"
            try:
                from dynamic_search.wikipedia_guard import should_use_wikipedia, extract_topic
                if should_use_wikipedia(query, intent):
                    topic = extract_topic(query, intent)
                    from dynamic_search.wikipedia_service import fetch as wiki_fetch
                    wiki = wiki_fetch(topic)
                    if wiki.found:
                        wiki_section = (
                            f"📚 Medical Background\n\n"
                            f"{wiki.title}\n\n"
                            f"{wiki.summary}\n\n"
                            f"Source: {wiki.url}"
                        )
                        if _ddg_weak:
                            # DuckDuckGo failed — Wikipedia is the sole source
                            result.chunks = [wiki_section]
                            result.source = "wikipedia"
                            print(
                                f"[search] WIKIPEDIA (sole source) | "
                                f"topic={topic!r} | title={wiki.title!r}"
                            )
                        else:
                            # Merge: Wikipedia background appended after DuckDuckGo
                            result.chunks.append(wiki_section)
                            print(
                                f"[search] WIKIPEDIA (merged) | "
                                f"topic={topic!r} | title={wiki.title!r}"
                            )
                    else:
                        print(f"[search] WIKIPEDIA not_found | topic={topic!r}")
            except Exception as _wiki_err:
                print(f"[search] Wikipedia enrichment error (non-fatal): {_wiki_err}")

        return result

    # ── Query rewriting ────────────────────────────────────────────────────
    try:
        from search.query_rewriter import rewrite
        rq = rewrite(query, intent)
        retrieval_query = rq.canonical
        variants        = rq.variants
    except Exception as exc:
        print(f"[search] query_rewriter failed (non-fatal): {exc}")
        retrieval_query = query
        variants        = []

    # ── 1. Exact product name match ────────────────────────────────────────
    # Uses rewritten canonical for normalised name matching.
    result = product_search.exact_match(retrieval_query, intent)
    if result:
        result.intent = intent
        result.pdf_chunks = pdf_search.search(
            query, matched_product=result.matched_product
        )
        print(
            f"[search] EXACT MATCH | product={result.matched_product} "
            f"| confidence={result.confidence}"
        )
        return result

    # ── 2a. Comparison — split-and-retrieve ────────────────────────────────
    if intent == COMPARISON_QUERY:
        result = product_search.comparison_search(retrieval_query)
        if result:
            result.intent = intent
            print(
                f"[search] COMPARISON | product={result.matched_product} "
                f"| confidence={result.confidence}"
            )
            return result

    # ── 2b. Hybrid FAISS + BM25 for canonical query ────────────────────────
    result = product_search.faiss_search(retrieval_query)

    # ── 2c. Multi-query: also retrieve for each variant, merge results ─────
    if variants:
        extra_chunks: list[str] = []
        for variant in variants:
            try:
                from search.hybrid_search import hybrid_product_search
                extra = hybrid_product_search(variant, top_k=5)
                extra_chunks.extend(extra)
            except Exception as exc:
                print(f"[search] variant retrieval failed for {variant!r}: {exc}")

        if extra_chunks:
            from search.common import deduplicate
            if result:
                merged = deduplicate(result.chunks + extra_chunks)
                result.chunks = merged
                print(f"[search] multi-query merge | total_chunks={len(merged)}")
            else:
                # Hybrid returned nothing for canonical but variants hit something
                from search.common import extract_product_name, extract_category, detect_category_from_query, faiss_confidence, FAISS_STRONG_THRESHOLD
                unique = deduplicate(extra_chunks)
                if unique:
                    top = unique[0]
                    result = SearchResult(
                        chunks=unique,
                        source="faiss",
                        matched_product=extract_product_name(top),
                        matched_category=extract_category(top) or detect_category_from_query(query),
                        confidence=faiss_confidence(FAISS_STRONG_THRESHOLD * 0.9),
                    )

    # ── 3. CrossEncoder reranking — top 5 from merged candidate pool ───────
    if result and result.chunks:
        try:
            from search.reranker import rerank, DEFAULT_TOP_K
            # Use the ORIGINAL query for the cross-encoder (natural language)
            reranked = rerank(query, result.chunks, top_k=DEFAULT_TOP_K)
            if reranked:
                result.chunks = reranked
                print(f"[search] RERANKED | top_k={len(reranked)}")
        except Exception as exc:
            print(f"[search] reranker failed (non-fatal): {exc}")

    if result:
        result.intent = intent
        result.pdf_chunks = pdf_search.search(
            query, matched_product=result.matched_product
        )
        print(
            f"[search] HYBRID | product={result.matched_product} "
            f"| category={result.matched_category} "
            f"| confidence={result.confidence} "
            f"| chunks={len(result.chunks)}"
        )
        return result

    # ── 4. Dynamic search fallback ─────────────────────────────────────────
    # Guard: only execute dynamic search when the query is clearly medical /
    # healthcare related.  Queries like "what is car?", "football score",
    # "python programming" must NOT reach DuckDuckGo and must not return a
    # random MedicalExpo page that happens to contain the word.
    try:
        from intent_detector import is_medical_query
        _query_is_medical = is_medical_query(query)
    except Exception:
        _query_is_medical = True  # fail-safe: allow if guard itself errors

    if not _query_is_medical:
        print(
            f"[search] DYNAMIC SEARCH BLOCKED — query has no medical relevance "
            f"| query={query!r}"
        )
        # Return a sentinel result that app.py will turn into the OOS reply.
        return SearchResult(
            chunks=[],
            source="out_of_scope",
            matched_product=None,
            matched_category="Unknown",
            confidence=0.0,
        )

    print(f"[search] DYNAMIC SEARCH fallback | query={query}")
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
