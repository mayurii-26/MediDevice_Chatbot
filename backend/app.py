from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import ChatRequest, ChatResponse, ContactRequest, ContactResponse
from search import smart_search
from gemini_service import generate_answer
from email_service import send_email
from logger import log_search
from intent_detector import detect_intent
from document_service import get_categories, get_subcategories, get_documents, get_documents_by_product, get_documents_by_names

from cache_service import (
    get_cached_answer,
    save_cached_answer
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
    "I am a medical device assistant trained on Philips healthcare products. "
    "Please ask about supported medical devices. "
    "For further assistance contact support@medidevicechatbot.com"
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
        print(f"[request] Detected Intent: {intent}")

        cached_answer = get_cached_answer(req.question, intent)
        if cached_answer:
            if conversation_id:
                save_message(conversation_id, "assistant", cached_answer)
            # Run document lookup even on cache hits (Issue 2 & 3)
            cached_result = smart_search(req.question, intent)
            cached_docs = []
            if cached_result.matched_product:
                try:
                    cached_docs = get_documents_by_product(cached_result.matched_product)
                except Exception:
                    pass
            return ChatResponse(
                answer=cached_answer,
                source="cache",
                matched_product=cached_result.matched_product,
                matched_category=cached_result.matched_category or "Unknown",
                confidence=cached_result.confidence,
                conversation_id=conversation_id,
                documents=cached_docs,
            )

        result = smart_search(req.question, intent)
        print(
            f"[debug] intent={intent} | matched_product={result.matched_product or 'None'}"
            f" | source={result.source} | chunks={len(result.chunks)}"
            f" | pdf_chunks={len(result.pdf_chunks)}"
        )

        # Build structured context with clearly separated sections.
        combined_context = []

        if result.chunks:
            from search.common import deduplicate_by_product, extract_product_name, extract_category
            import re as _re

            def _format_product_chunk(chunk: str) -> str:
                name = extract_product_name(chunk) or "Unknown Product"
                category = extract_category(chunk) or "Unknown"
                # Extract description — everything after "Description:" line
                desc_m = _re.search(r"Description:\s*(.+)", chunk, _re.DOTALL)
                description = desc_m.group(1).strip() if desc_m else ""
                # Strip any remaining "Key: value" lines that aren't description
                description = _re.sub(r"\n[A-Za-z ]+:\s*.+", "", description).strip()
                parts = [f"📦 Product\n\n{name}\n\nCategory\n{category}"]
                if description:
                    parts.append(f"Summary\n\n{description}")
                return "\n\n".join(parts)

            from intent_detector import COMPARISON_QUERY
            chunks_to_use = result.chunks
            if result.matched_product and intent != COMPARISON_QUERY:
                chunks_to_use = [
                    c for c in result.chunks
                    if (extract_product_name(c) or "").lower() == result.matched_product.lower()
                ] or result.chunks  # fall back to all if filter empties the list

            unique_chunks = deduplicate_by_product(chunks_to_use)
            formatted = [_format_product_chunk(c) for c in unique_chunks]
            section = "\n\n---\n\n".join(formatted)
            combined_context.append(section)

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

        # Dynamic search results are already in result.chunks when source=="dynamic_search";
        # label them explicitly so Gemini sees the section header.
        if result.source == "dynamic_search" and result.chunks:
            combined_context = [
                "🌐 Dynamic Search\n\n" + "\n\n".join(result.chunks)
            ]

        answer = generate_answer(
            req.question,
            combined_context,
            result.source,
            intent,
        )
        answer = answer or _FALLBACK

        save_cached_answer(req.question, answer, intent)

        if conversation_id:
            save_message(conversation_id, "assistant", answer)

        print(
            f"\n[request]"
            f"\n  QUESTION  : {req.question}"
            f"\n  INTENT    : {intent}"
            f"\n  SOURCE    : {result.source}"
            f"\n  CATEGORY  : {result.matched_category or 'Unknown'}"
            f"\n  PRODUCT   : {result.matched_product or 'None'}"
            f"\n  CONFIDENCE: {result.confidence}"
        )

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
                print(f"[debug] documents_found={len(documents)}")
            except Exception as doc_err:
                print(f"[documents] lookup failed (non-fatal): {type(doc_err).__name__}: {doc_err}")

        # If pdf_chunks were used, always attach their source documents.
        if result.pdf_chunks:
            try:
                pdf_doc_names = list({pc["document_name"] for pc in result.pdf_chunks})
                pdf_docs = get_documents_by_names(pdf_doc_names)
                # Merge — avoid duplicates by document_name
                existing_names = {d["document_name"] for d in documents}
                documents += [d for d in pdf_docs if d["document_name"] not in existing_names]
                print(f"[debug] pdf_source_docs_added={len(pdf_docs)}")
            except Exception as pdf_doc_err:
                print(f"[documents] pdf source lookup failed (non-fatal): {type(pdf_doc_err).__name__}: {pdf_doc_err}")

        print(
            f"\n[debug] intent={intent}"
            f"\n[debug] matched_product={result.matched_product or 'None'}"
            f"\n[debug] source={result.source}"
            f"\n[debug] documents_found={len(documents)}"
        )

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
        print(f"[request] ERROR: {type(e).__name__}: {e}")
        log_search(question=req.question, source="fallback")
        if conversation_id:
            save_message(conversation_id, "assistant", _FALLBACK)
        return ChatResponse(
            answer=_FALLBACK,
            source="fallback",
            matched_category="Unknown",
            conversation_id=conversation_id,
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
