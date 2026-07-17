from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from models import (
    ChatRequest, ChatResponse, ContactRequest, ContactResponse,
    DownloadRequestBody, DownloadRequestResponse,
    VerifyOtpBody, VerifyOtpResponse,
    ResendOtpBody, ResendOtpResponse,
    UserPreferencesBody, UserPreferencesResponse,
)
from search import smart_search
from gemini_service import generate_answer, generate_answer_streaming
from email_service import send_email
from logger import log_search
from intent_detector import detect_intent, is_purchase_intent, is_out_of_scope
from document_service import get_categories, get_subcategories, get_documents, get_documents_by_product, get_documents_by_names

from cache_service import (
    get_cached_answer,
    save_cached_answer,
    ENABLE_CACHE,
)

from chat_history import (
    create_conversation,
    get_conversation,
    get_conversation_messages,
    get_user_conversations,
    save_message,
)
from database.supabase_client import supabase

app = FastAPI(title="MediDevice Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_FALLBACK = (
    "I am a medical device assistant trained on medical device knowledge. "
    "Please ask about supported medical devices. "
    "For further assistance contact support@medideviceai.com"
)


def _title_from_question(question: str) -> str:
    title = " ".join(question.strip().split())
    return title[:60] or "New Chat"


def _get_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    return token


def _get_authenticated_user_id(authorization: str | None) -> str:
    token = _get_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        result = supabase.auth.get_user(token)
        user = getattr(result, "user", None)
        if user is None and isinstance(result, dict):
            user = result.get("user")
        if not user:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        if isinstance(user, dict):
            return user["id"]
        return user.id
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")


def _ensure_conversation(user_id: str | None, conversation_id: str | None, question: str):
    if not user_id:
        return None

    if conversation_id:
        conversation = get_conversation(conversation_id)
        if conversation and conversation.get("user_id") == user_id:
            return conversation

    return create_conversation(user_id, _title_from_question(question))


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, authorization: str | None = Header(default=None)):
    conversation_id = None

    # ── Pipeline execution tracker ────────────────────────────────────────
    _pipeline = {
        "cache_bypassed":      False,
        "gemini_executed":     False,
        "hybrid_search_exec":  False,
        "bm25_executed":       False,
        "wikipedia_executed":  False,
        "response_regenerated": False,
        "answer_source":       "unknown",
    }

    def _print_pipeline_report():
        print(
            f"\n╔══ [PIPELINE REPORT] ════════════════════════════════"
            f"\n║  QUESTION           : {req.question}"
            f"\n║  Cache Bypassed?    : {'✅ YES' if _pipeline['cache_bypassed'] else '❌ NO'}"
            f"\n║  Gemini Executed?   : {'✅ YES' if _pipeline['gemini_executed'] else '❌ NO'}"
            f"\n║  Hybrid Search?     : {'✅ YES' if _pipeline['hybrid_search_exec'] else '❌ NO'}"
            f"\n║  BM25 Executed?     : {'✅ YES' if _pipeline['bm25_executed'] else '❌ NO'}"
            f"\n║  Wikipedia Used?    : {'✅ YES' if _pipeline['wikipedia_executed'] else '❌ NO'}"
            f"\n║  Response Regen?    : {'✅ YES (refiner retry)' if _pipeline['response_regenerated'] else '❌ NO'}"
            f"\n║  Answer Source      : {_pipeline['answer_source']}"
            f"\n╚═════════════════════════════════════════════════════\n"
        )

    try:
        authenticated_user_id = None
        if authorization:
            authenticated_user_id = _get_authenticated_user_id(authorization)
        elif req.user_id:
            raise HTTPException(status_code=401, detail="Authentication required")

        conversation = _ensure_conversation(
            authenticated_user_id,
            req.conversation_id,
            req.question,
        )
        if conversation:
            conversation_id = conversation["id"]
            save_message(conversation_id, "user", req.question)

        intent = detect_intent(req.question)
        print(f"\n[PIPELINE] ▶ Step 1 — Intent Detection : {intent}")

        # ── Purchase / Price / Quote intent guard ──────────────────────────
        # Short-circuit BEFORE cache, FAISS, BM25, Wikipedia, and Gemini.
        # Any purchase-related keyword immediately returns a canned response
        # directing the user to the Contact Support form.
        if is_purchase_intent(req.question):
            print("[PIPELINE] ▶ Purchase Intent DETECTED → bypassing full pipeline")
            _pipeline["answer_source"] = "purchase_intent_guard"
            _print_pipeline_report()
            _purchase_reply = (
                "Pricing and purchasing information is not available through the chatbot.\n\n"
                "Please contact our support team and we'll get back to you shortly."
            )
            if conversation_id:
                save_message(conversation_id, "assistant", _purchase_reply)
            return ChatResponse(
                answer=_purchase_reply,
                source="purchase_intent",
                matched_product=None,
                matched_category="Unknown",
                confidence=0.0,
                conversation_id=conversation_id,
                documents=[],
            )
        # ──────────────────────────────────────────────────────────────────

        # ── Out-of-scope query guard ───────────────────────────────────────
        # Short-circuit BEFORE cache, FAISS, BM25, Wikipedia, and Gemini.
        # Queries unrelated to medical devices / healthcare return immediately.
        if is_out_of_scope(req.question):
            print("[PIPELINE] ▶ Out-of-Scope Query DETECTED → bypassing full pipeline")
            _pipeline["answer_source"] = "out_of_scope_guard"
            _print_pipeline_report()
            _oos_reply = (
                "This platform is designed only for Medical devices and healthcare-related queries.\n\n"
                "Please contact our support team for further assistance."
            )
            if conversation_id:
                save_message(conversation_id, "assistant", _oos_reply)
            return ChatResponse(
                answer=_oos_reply,
                source="out_of_scope",
                matched_product=None,
                matched_category="Unknown",
                confidence=0.0,
                conversation_id=conversation_id,
                documents=[],
            )
        # ──────────────────────────────────────────────────────────────────

        # ── Cache check ────────────────────────────────────────────────────
        cached_answer = get_cached_answer(req.question, intent)
        if cached_answer:
            _pipeline["answer_source"] = "cache"
            _pipeline["cache_bypassed"] = False
            print("[PIPELINE] ▶ Step 2 — Search Source  : CACHE HIT → skipping pipeline")
            if conversation_id:
                save_message(conversation_id, "assistant", cached_answer)
            # Run document lookup even on cache hits
            cached_result = smart_search(req.question, intent)
            cached_docs = []
            if cached_result.matched_product:
                try:
                    cached_docs = get_documents_by_product(cached_result.matched_product)
                except Exception:
                    pass
            _print_pipeline_report()
            return ChatResponse(
                answer=cached_answer,
                source="cache",
                matched_product=cached_result.matched_product,
                matched_category=cached_result.matched_category or "Unknown",
                confidence=cached_result.confidence,
                conversation_id=conversation_id,
                documents=cached_docs,
            )

        # Cache was not used — full pipeline runs
        _pipeline["cache_bypassed"] = True
        print("[PIPELINE] ▶ Step 2 — Cache       : MISS / DISABLED → full pipeline executing")

        # ── Hybrid Search + BM25 + Reranker ───────────────────────────────
        print("[PIPELINE] ▶ Step 3 — Hybrid Search + BM25 + Reranker …")
        result = smart_search(req.question, intent)
        _pipeline["hybrid_search_exec"] = True
        _pipeline["bm25_executed"]      = True   # BM25 is always part of smart_search
        _pipeline["wikipedia_executed"] = result.source in ("dynamic_search", "wikipedia")

        # ── Out-of-scope sentinel from orchestrator ────────────────────────
        # Raised when FAISS+BM25 found nothing AND query has no medical terms.
        # Skip Gemini entirely and return the OOS canned reply.
        if result.source == "out_of_scope":
            print("[PIPELINE] ▶ OOS sentinel from orchestrator → bypassing Gemini")
            _pipeline["answer_source"] = "out_of_scope_guard"
            _print_pipeline_report()
            _oos_reply = (
                "This platform is designed only for Medical devices and "
                "healthcare-related queries.\n\n"
                "Please contact our support team for further assistance."
            )
            if conversation_id:
                save_message(conversation_id, "assistant", _oos_reply)
            return ChatResponse(
                answer=_oos_reply,
                source="out_of_scope",
                matched_product=None,
                matched_category="Unknown",
                confidence=0.0,
                conversation_id=conversation_id,
                documents=[],
            )
        # ──────────────────────────────────────────────────────────────────

        print(
            f"[PIPELINE]   matched_product={result.matched_product or 'None'}"
            f" | source={result.source} | chunks={len(result.chunks)}"
            f" | pdf_chunks={len(result.pdf_chunks)}"
        )
        if _pipeline["wikipedia_executed"]:
            print("[PIPELINE] ▶ Step 4 — Wikipedia      : ✅ used (source={})".format(result.source))
        else:
            print(f"[PIPELINE] ▶ Step 4 — Wikipedia      : ❌ not used (source={result.source})")

        # ── Build structured context ───────────────────────────────────────
        combined_context = []

        if result.chunks:
            from search.common import deduplicate_by_product, extract_product_name, extract_category
            import re as _re

            def _format_product_chunk(chunk: str) -> str:
                """
                Format a product chunk for the Gemini prompt.

                Preserves ALL structured sections from the chunk (Description,
                Features, Specifications) so intent-specific prompts receive
                the full data they need.
                """
                name     = extract_product_name(chunk) or "Unknown Product"
                category = extract_category(chunk) or "Unknown"

                desc_m = _re.search(
                    r"Description:\s*(.+?)(?=\nFeatures:|\nSpecifications:|$)",
                    chunk, _re.DOTALL
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

            from intent_detector import COMPARISON_QUERY
            chunks_to_use = result.chunks
            if result.matched_product and intent != COMPARISON_QUERY:
                chunks_to_use = [
                    c for c in result.chunks
                    if (extract_product_name(c) or "").lower() == result.matched_product.lower()
                ] or result.chunks

            unique_chunks = deduplicate_by_product(chunks_to_use)
            formatted = [_format_product_chunk(c) for c in unique_chunks]
            combined_context.append("\n\n---\n\n".join(formatted))

        if result.pdf_chunks:
            from gemini_service import _extract_bullets
            sections = ["📄 PDF Knowledge"]
            for pc in result.pdf_chunks:
                bullets = _extract_bullets(pc["chunk_text"], max_bullets=8, min_bullets=3)
                highlights = "\n".join(f"- {b}" for b in bullets) if bullets else pc["chunk_text"][:300]
                sections.append(
                    f"Source\n\n{pc['document_name']}\nPage {pc['page_number']}\n\n"
                    f"Highlights\n\n{highlights}"
                )
            combined_context.append("\n\n".join(sections))

        if result.source == "dynamic_search" and result.chunks:
            combined_context = [
                "🌐 Dynamic Search\n\n" + "\n\n".join(result.chunks)
            ]

        # ── Context cleaning ───────────────────────────────────────────────
        try:
            from pipeline.context_cleaner import clean_chunks
            combined_context = clean_chunks(combined_context)
        except Exception as _cc_err:
            print(f"[PIPELINE] context_cleaner error (non-fatal): {_cc_err}")

        # ── Gemini ─────────────────────────────────────────────────────────
        print("[PIPELINE] ▶ Step 5 — Gemini         : generating answer …")
        answer = generate_answer(
            req.question,
            combined_context,
            result.source,
            intent,
        )
        _pipeline["gemini_executed"] = True
        answer = answer or _FALLBACK
        print(f"[PIPELINE]   Gemini answer length : {len(answer)} chars")

        # ── Response validation ────────────────────────────────────────────
        print("[PIPELINE] ▶ Step 6 — Formatter      : validating response …")
        try:
            from pipeline.response_validator import validate_response
            vr = validate_response(
                answer=answer,
                question=req.question,
                intent=intent,
                matched_product=result.matched_product,
                has_context=bool(combined_context),
            )
            if not vr.is_valid:
                # The refiner is the guaranteed base — only truly empty or
                # sentinel responses reach here.  Re-run refiner directly on
                # the raw result.chunks (may differ from combined_context
                # when context_cleaner dropped sections).
                print(f"[PIPELINE]   Validation FAILED: {vr.reason} → re-running refiner on raw chunks")
                _pipeline["response_regenerated"] = True
                try:
                    from response_refiner import refine as _refine
                    answer = _refine(req.question, result.chunks, result.source, intent)
                except Exception as _ref_err:
                    print(f"[PIPELINE]   refiner retry error: {_ref_err}")
                answer = answer or _FALLBACK
            else:
                print("[PIPELINE]   Validation PASSED ✅")
        except Exception as _vr_err:
            print(f"[PIPELINE] response_validator error (non-fatal): {_vr_err}")

        _pipeline["answer_source"] = "pipeline"
        print(f"[PIPELINE] ▶ Step 7 — Final Answer   : ready ({len(answer)} chars)")

        save_cached_answer(req.question, answer, intent)

        if conversation_id:
            save_message(conversation_id, "assistant", answer)

        log_search(
            question=req.question,
            source=result.source,
            matched_product=result.matched_product or "",
            matched_category=result.matched_category or "",
            confidence=result.confidence,
        )

        documents = []
        if result.matched_product:
            try:
                documents = get_documents_by_product(result.matched_product)
            except Exception as doc_err:
                print(f"[PIPELINE] documents lookup failed (non-fatal): {type(doc_err).__name__}: {doc_err}")

        if result.pdf_chunks:
            try:
                pdf_doc_names = list({pc["document_name"] for pc in result.pdf_chunks})
                pdf_docs = get_documents_by_names(pdf_doc_names)
                existing_names = {d["document_name"] for d in documents}
                documents += [d for d in pdf_docs if d["document_name"] not in existing_names]
            except Exception as pdf_doc_err:
                print(f"[PIPELINE] pdf source lookup failed (non-fatal): {type(pdf_doc_err).__name__}: {pdf_doc_err}")

        _print_pipeline_report()

        return ChatResponse(
            answer=answer,
            source=result.source,
            matched_product=result.matched_product,
            matched_category=result.matched_category or "Unknown",
            confidence=result.confidence,
            conversation_id=conversation_id,
            documents=documents,
        )

    except HTTPException:
        raise

    except Exception as e:
        print(f"[PIPELINE] ERROR: {type(e).__name__}: {e}")
        log_search(question=req.question, source="fallback")
        if conversation_id:
            save_message(conversation_id, "assistant", _FALLBACK)
        return ChatResponse(
            answer=_FALLBACK,
            source="fallback",
            matched_category="Unknown",
            conversation_id=conversation_id,
        )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, authorization: str | None = Header(default=None)):
    """
    Streaming variant of /chat.
    Sends the AI response token-by-token via Server-Sent Events (SSE).
    Meta (source, product, documents, conversation_id) is emitted as a
    final JSON event prefixed with 'data: [META]'.
    """
    import json, asyncio

    async def event_generator():
        conversation_id = None

        # ── Pipeline execution tracker ────────────────────────────────────
        _pipeline = {
            "cache_bypassed":       False,
            "gemini_executed":      False,
            "hybrid_search_exec":   False,
            "bm25_executed":        False,
            "wikipedia_executed":   False,
            "response_regenerated": False,
            "answer_source":        "unknown",
        }

        def _print_stream_pipeline_report():
            print(
                f"\n╔══ [PIPELINE REPORT] (stream) ═══════════════════════"
                f"\n║  QUESTION           : {req.question}"
                f"\n║  Cache Bypassed?    : {'✅ YES' if _pipeline['cache_bypassed'] else '❌ NO'}"
                f"\n║  Gemini Executed?   : {'✅ YES' if _pipeline['gemini_executed'] else '❌ NO'}"
                f"\n║  Hybrid Search?     : {'✅ YES' if _pipeline['hybrid_search_exec'] else '❌ NO'}"
                f"\n║  BM25 Executed?     : {'✅ YES' if _pipeline['bm25_executed'] else '❌ NO'}"
                f"\n║  Wikipedia Used?    : {'✅ YES' if _pipeline['wikipedia_executed'] else '❌ NO'}"
                f"\n║  Response Regen?    : {'✅ YES (refiner retry)' if _pipeline['response_regenerated'] else '❌ NO'}"
                f"\n║  Answer Source      : {_pipeline['answer_source']}"
                f"\n╚═════════════════════════════════════════════════════\n"
            )

        try:
            authenticated_user_id = None
            if authorization:
                authenticated_user_id = _get_authenticated_user_id(authorization)
            elif req.user_id:
                yield "data: [ERROR] Authentication required\n\n"
                return

            conversation = _ensure_conversation(
                authenticated_user_id, req.conversation_id, req.question
            )
            if conversation:
                conversation_id = conversation["id"]
                save_message(conversation_id, "user", req.question)

            intent = detect_intent(req.question)
            print(f"\n[PIPELINE/stream] ▶ Step 1 — Intent Detection : {intent}")

            # ── Purchase / Price / Quote intent guard ──────────────────────
            # Short-circuit BEFORE cache, FAISS, BM25, Wikipedia, and Gemini.
            # Immediately streams a canned response and skips the full pipeline.
            if is_purchase_intent(req.question):
                print("[PIPELINE/stream] ▶ Purchase Intent DETECTED → bypassing full pipeline")
                _pipeline["answer_source"] = "purchase_intent_guard"
                _purchase_reply = (
                    "Pricing and purchasing information is not available through the chatbot.\n\n"
                    "Please contact our support team and we'll get back to you shortly."
                )
                if conversation_id:
                    save_message(conversation_id, "assistant", _purchase_reply)
                # Stream the canned reply in small chunks (natural typing feel)
                chunk_size = 40
                for i in range(0, len(_purchase_reply), chunk_size):
                    yield f"data: {_purchase_reply[i:i+chunk_size]}\n\n"
                    await asyncio.sleep(0.01)
                meta = {
                    "source": "purchase_intent",
                    "matched_product": None,
                    "matched_category": "Unknown",
                    "confidence": 0.0,
                    "conversation_id": conversation_id,
                    "documents": [],
                }
                _print_stream_pipeline_report()
                yield f"data: [META]{json.dumps(meta)}\n\n"
                return
            # ────────────────────────────────────────────────────────────────

            # ── Out-of-scope query guard ────────────────────────────────────
            # Short-circuit BEFORE cache, FAISS, BM25, Wikipedia, and Gemini.
            # Streams a canned reply immediately for off-topic queries.
            if is_out_of_scope(req.question):
                print("[PIPELINE/stream] ▶ Out-of-Scope Query DETECTED → bypassing full pipeline")
                _pipeline["answer_source"] = "out_of_scope_guard"
                _oos_reply = (
                    "This platform is designed only for Medical devices and healthcare-related queries.\n\n"
                    "Please contact our support team for further assistance."
                )
                if conversation_id:
                    save_message(conversation_id, "assistant", _oos_reply)
                chunk_size = 40
                for i in range(0, len(_oos_reply), chunk_size):
                    yield f"data: {_oos_reply[i:i+chunk_size]}\n\n"
                    await asyncio.sleep(0.01)
                meta = {
                    "source": "out_of_scope",
                    "matched_product": None,
                    "matched_category": "Unknown",
                    "confidence": 0.0,
                    "conversation_id": conversation_id,
                    "documents": [],
                }
                _print_stream_pipeline_report()
                yield f"data: [META]{json.dumps(meta)}\n\n"
                return
            # ────────────────────────────────────────────────────────────────

            # ── Cache check ────────────────────────────────────────────────
            cached_answer = get_cached_answer(req.question, intent)
            if cached_answer:
                _pipeline["answer_source"] = "cache"
                _pipeline["cache_bypassed"] = False
                print("[PIPELINE/stream] ▶ Step 2 — Search Source  : CACHE HIT → skipping pipeline")
                if conversation_id:
                    save_message(conversation_id, "assistant", cached_answer)
                cached_result = smart_search(req.question, intent)
                cached_docs = []
                if cached_result.matched_product:
                    try:
                        cached_docs = get_documents_by_product(cached_result.matched_product)
                    except Exception:
                        pass
                chunk_size = 32
                for i in range(0, len(cached_answer), chunk_size):
                    yield f"data: {cached_answer[i:i+chunk_size]}\n\n"
                    await asyncio.sleep(0.008)
                meta = {
                    "source": "cache",
                    "matched_product": cached_result.matched_product,
                    "matched_category": cached_result.matched_category or "Unknown",
                    "confidence": cached_result.confidence,
                    "conversation_id": conversation_id,
                    "documents": cached_docs,
                }
                _print_stream_pipeline_report()
                yield f"data: [META]{json.dumps(meta)}\n\n"
                return

            # Cache not used — full pipeline runs
            _pipeline["cache_bypassed"] = True
            print("[PIPELINE/stream] ▶ Step 2 — Cache       : MISS / DISABLED → full pipeline executing")

            # ── Hybrid Search + BM25 + Reranker ───────────────────────────
            print("[PIPELINE/stream] ▶ Step 3 — Hybrid Search + BM25 + Reranker …")
            result = smart_search(req.question, intent)
            _pipeline["hybrid_search_exec"] = True
            _pipeline["bm25_executed"]      = True
            _pipeline["wikipedia_executed"] = result.source in ("dynamic_search", "wikipedia")

            # ── Out-of-scope sentinel from orchestrator ────────────────────
            if result.source == "out_of_scope":
                print("[PIPELINE/stream] ▶ OOS sentinel from orchestrator → bypassing Gemini")
                _pipeline["answer_source"] = "out_of_scope_guard"
                _oos_reply = (
                    "This platform is designed only for Medical devices and "
                    "healthcare-related queries.\n\n"
                    "Please contact our support team for further assistance."
                )
                if conversation_id:
                    save_message(conversation_id, "assistant", _oos_reply)
                chunk_size = 40
                for i in range(0, len(_oos_reply), chunk_size):
                    yield f"data: {_oos_reply[i:i+chunk_size]}\n\n"
                    await asyncio.sleep(0.01)
                _print_stream_pipeline_report()
                yield f"data: [META]{json.dumps({'source': 'out_of_scope', 'matched_product': None, 'matched_category': 'Unknown', 'confidence': 0.0, 'conversation_id': conversation_id, 'documents': []})}\n\n"
                return
            # ────────────────────────────────────────────────────────────────

            print(
                f"[PIPELINE/stream]   matched_product={result.matched_product or 'None'}"
                f" | source={result.source} | chunks={len(result.chunks)}"
                f" | pdf_chunks={len(result.pdf_chunks)}"
            )
            if _pipeline["wikipedia_executed"]:
                print("[PIPELINE/stream] ▶ Step 4 — Wikipedia      : ✅ used (source={})".format(result.source))
            else:
                print(f"[PIPELINE/stream] ▶ Step 4 — Wikipedia      : ❌ not used (source={result.source})")

            # ── Build context ──────────────────────────────────────────────
            combined_context = []
            if result.chunks:
                from search.common import deduplicate_by_product, extract_product_name, extract_category
                import re as _re

                def _format_product_chunk(chunk: str) -> str:
                    name     = extract_product_name(chunk) or "Unknown Product"
                    category = extract_category(chunk) or "Unknown"

                    desc_m = _re.search(
                        r"Description:\s*(.+?)(?=\nFeatures:|\nSpecifications:|$)",
                        chunk, _re.DOTALL
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

                from intent_detector import COMPARISON_QUERY
                chunks_to_use = result.chunks
                if result.matched_product and intent != COMPARISON_QUERY:
                    chunks_to_use = [
                        c for c in result.chunks
                        if (extract_product_name(c) or "").lower() == result.matched_product.lower()
                    ] or result.chunks

                from search.common import deduplicate_by_product
                unique_chunks = deduplicate_by_product(chunks_to_use)
                formatted = [_format_product_chunk(c) for c in unique_chunks]
                combined_context.append("\n\n---\n\n".join(formatted))

            if result.pdf_chunks:
                from gemini_service import _extract_bullets
                sections = ["📄 PDF Knowledge"]
                for pc in result.pdf_chunks:
                    bullets = _extract_bullets(pc["chunk_text"], max_bullets=8, min_bullets=3)
                    highlights = "\n".join(f"- {b}" for b in bullets) if bullets else pc["chunk_text"][:300]
                    sections.append(
                        f"Source\n\n{pc['document_name']}\nPage {pc['page_number']}\n\n"
                        f"Highlights\n\n{highlights}"
                    )
                combined_context.append("\n\n".join(sections))

            if result.source == "dynamic_search" and result.chunks:
                combined_context = ["🌐 Dynamic Search\n\n" + "\n\n".join(result.chunks)]

            # ── Context cleaning ───────────────────────────────────────────
            try:
                from pipeline.context_cleaner import clean_chunks
                combined_context = clean_chunks(combined_context)
            except Exception as _cc_err:
                print(f"[PIPELINE/stream] context_cleaner error (non-fatal): {_cc_err}")

            # ── Stream Gemini tokens ───────────────────────────────────────
            print("[PIPELINE/stream] ▶ Step 5 — Gemini         : streaming answer …")
            full_answer = ""
            async for token in generate_answer_streaming(req.question, combined_context, result.source, intent):
                full_answer += token
                yield f"data: {token}\n\n"
                await asyncio.sleep(0)
            _pipeline["gemini_executed"] = True

            if not full_answer:
                full_answer = _FALLBACK
                yield f"data: {_FALLBACK}\n\n"

            print(f"[PIPELINE/stream]   Gemini answer length : {len(full_answer)} chars")

            # ── Response validation ────────────────────────────────────────
            print("[PIPELINE/stream] ▶ Step 6 — Formatter      : validating response …")
            try:
                from pipeline.response_validator import validate_response
                vr = validate_response(
                    answer=full_answer,
                    question=req.question,
                    intent=intent,
                    matched_product=result.matched_product,
                    has_context=bool(combined_context),
                )
                if not vr.is_valid:
                    print(f"[PIPELINE/stream]   Validation FAILED: {vr.reason} → re-running refiner on raw chunks")
                    _pipeline["response_regenerated"] = True
                    try:
                        from response_refiner import refine as _refine
                        full_answer = _refine(req.question, result.chunks, result.source, intent)
                    except Exception as _ref_err:
                        print(f"[PIPELINE/stream]   refiner retry error: {_ref_err}")
                    full_answer = full_answer or _FALLBACK
                    chunk_size = 64
                    for i in range(0, len(full_answer), chunk_size):
                        yield f"data: {full_answer[i:i+chunk_size]}\n\n"
                        await asyncio.sleep(0.008)
                else:
                    print("[PIPELINE/stream]   Validation PASSED ✅")
            except Exception as _vr_err:
                print(f"[PIPELINE/stream] response_validator error (non-fatal): {_vr_err}")

            _pipeline["answer_source"] = "pipeline"
            print(f"[PIPELINE/stream] ▶ Step 7 — Final Answer   : ready ({len(full_answer)} chars)")

            save_cached_answer(req.question, full_answer, intent)
            if conversation_id:
                save_message(conversation_id, "assistant", full_answer)

            # ── Documents lookup ───────────────────────────────────────────
            documents = []
            if result.matched_product:
                try:
                    documents = get_documents_by_product(result.matched_product)
                except Exception:
                    pass
            if result.pdf_chunks:
                try:
                    pdf_doc_names = list({pc["document_name"] for pc in result.pdf_chunks})
                    pdf_docs = get_documents_by_names(pdf_doc_names)
                    existing_names = {d["document_name"] for d in documents}
                    documents += [d for d in pdf_docs if d["document_name"] not in existing_names]
                except Exception:
                    pass

            log_search(
                question=req.question,
                source=result.source,
                matched_product=result.matched_product or "",
                matched_category=result.matched_category or "",
                confidence=result.confidence,
            )

            _print_stream_pipeline_report()

            meta = {
                "source": result.source,
                "matched_product": result.matched_product,
                "matched_category": result.matched_category or "Unknown",
                "confidence": result.confidence,
                "conversation_id": conversation_id,
                "documents": documents,
            }
            yield f"data: [META]{json.dumps(meta)}\n\n"

        except HTTPException as e:
            yield f"data: [ERROR] {e.detail}\n\n"
        except Exception as e:
            print(f"[PIPELINE/stream] ERROR: {type(e).__name__}: {e}")
            yield f"data: {_FALLBACK}\n\n"
            if conversation_id:
                save_message(conversation_id, "assistant", _FALLBACK)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/history/{user_id}")
def history(user_id: str, authorization: str | None = Header(default=None)):
    authenticated_user_id = _get_authenticated_user_id(authorization)
    if authenticated_user_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot access another user's history")

    return get_user_conversations(user_id)


@app.get("/conversation/{conversation_id}")
def conversation(conversation_id: str, authorization: str | None = Header(default=None)):
    authenticated_user_id = _get_authenticated_user_id(authorization)
    conversation_row = get_conversation(conversation_id)

    if not conversation_row:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation_row.get("user_id") != authenticated_user_id:
        raise HTTPException(status_code=403, detail="Cannot access this conversation")

    return get_conversation_messages(conversation_id)


@app.post("/contact", response_model=ContactResponse)
def contact(request: ContactRequest):
    try:
        send_email(request.name, request.email, request.message)
        return ContactResponse(message="Email sent successfully")
    except Exception as e:
        print(f"[contact] ERROR: {type(e).__name__}")
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Please try again later."
        )



# ── Document Library ───────────────────────────────────────────────────────

@app.get("/documents/categories")
def documents_categories():
    return get_categories()


@app.get("/documents/subcategories/{category}")
def documents_subcategories(category: str):
    return get_subcategories(category)


@app.get("/documents/list")
def documents_list(category: str, subcategory: str):
    return get_documents(category, subcategory)


# ── Secure Document Download (OTP flow) ───────────────────────────────────

from download_service import request_download, verify_otp, resend_otp, validate_and_consume_token


@app.post("/download/request", response_model=DownloadRequestResponse)
def download_request(body: DownloadRequestBody):
    try:
        result = request_download(
            full_name=body.full_name,
            email=body.email,
            phone=body.phone,
            designation=body.designation,
            country=body.country,
            document_id=body.document_id,
            document_name=body.document_name,
            file_url=body.file_url,
            user_id=body.user_id,
            guest_session_id=body.guest_session_id,
        )
        return DownloadRequestResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[download/request] ERROR: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create download request")


@app.post("/download/verify", response_model=VerifyOtpResponse)
def download_verify(body: VerifyOtpBody):
    try:
        result = verify_otp(body.request_id, body.otp)
        return VerifyOtpResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[download/verify] ERROR: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Verification failed")


@app.post("/download/resend", response_model=ResendOtpResponse)
def download_resend(body: ResendOtpBody):
    try:
        result = resend_otp(body.request_id)
        return ResendOtpResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[download/resend] ERROR: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Failed to resend OTP")


@app.get("/download/serve/{token}")
async def download_serve(token: str):
    """
    Secure file serving endpoint.

    Flow:
      1. Validate the single-use signed token (expiry + used flag).
      2. Retrieve the real file_url from the linked download request row.
      3. Fetch the file from Supabase Storage server-side using the
         service-role key — the storage URL is never sent to the client.
      4. Stream the file bytes back with:
           Content-Disposition: attachment  (forces browser download)
           Cache-Control: no-store          (prevents browser/CDN caching)
           Content-Type: application/pdf

    Security properties:
      - Token is single-use and expires in 15 minutes.
      - Raw storage URL never leaves the backend.
      - Token is a random 256-bit value; only its HMAC hash is stored.
      - A consumed or expired token returns 401 — no file served.
    """
    import httpx
    from fastapi.responses import Response

    try:
        request_row = validate_and_consume_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        print(f"[download/serve] token validation error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired download link.")

    file_url      = request_row.get("file_url", "")
    document_name = request_row.get("document_name", "document.pdf")

    if not file_url:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Fetch the file from Supabase Storage using service-role credentials
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(file_url)
        if resp.status_code != 200:
            print(f"[download/serve] upstream fetch failed: {resp.status_code}")
            raise HTTPException(status_code=502, detail="Failed to retrieve document.")
        file_bytes = resp.content
    except HTTPException:
        raise
    except Exception as e:
        print(f"[download/serve] fetch error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=502, detail="Failed to retrieve document.")

    # Sanitise filename — strip path separators and limit length
    safe_name = document_name.replace("/", "_").replace("\\", "_")[:120]
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"

    return Response(
        content=file_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Cache-Control":       "no-store, no-cache, must-revalidate, private",
            "Pragma":              "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ── User Preferences ──────────────────────────────────────────────────────

@app.get("/preferences/{user_id}", response_model=UserPreferencesResponse)
def get_preferences(user_id: str, authorization: str | None = Header(default=None)):
    authenticated_user_id = _get_authenticated_user_id(authorization)
    if authenticated_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        rows = (
            supabase.table("user_preferences")
            .select("*").eq("user_id", user_id).limit(1).execute()
        ).data
        if not rows:
            return UserPreferencesResponse(user_id=user_id)
        row = rows[0]
        return UserPreferencesResponse(
            user_id=row["user_id"],
            preferred_category=row.get("preferred_category"),
            recent_products=row.get("recent_products") or [],
            favorite_products=row.get("favorite_products") or [],
            last_active=str(row.get("last_active")) if row.get("last_active") else None,
        )
    except Exception as e:
        print(f"[preferences] get failed: {e}")
        return UserPreferencesResponse(user_id=user_id)


@app.post("/preferences/{user_id}", response_model=UserPreferencesResponse)
def upsert_preferences(
    user_id: str,
    body: UserPreferencesBody,
    authorization: str | None = Header(default=None),
):
    authenticated_user_id = _get_authenticated_user_id(authorization)
    if authenticated_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        data = {"user_id": user_id, "last_active": now}
        if body.preferred_category is not None:
            data["preferred_category"] = body.preferred_category
        if body.recent_products is not None:
            data["recent_products"] = body.recent_products
        if body.favorite_products is not None:
            data["favorite_products"] = body.favorite_products

        supabase.table("user_preferences").upsert(data, on_conflict="user_id").execute()
        return get_preferences(user_id, authorization)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[preferences] upsert failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")
