# MediDevice AI Chatbot — Complete Technical Documentation

---

## 1. Project Title

**MediDevice AI Chatbot** — An intelligent conversational assistant for Philips medical device information, built with a hybrid retrieval-augmented generation (RAG) architecture, secure document management, and a full-stack web application.

---

## 2. Project Objective

The MediDevice AI Chatbot provides healthcare professionals, hospital procurement teams, and biomedical engineers with instant, accurate, and professionally formatted information about Philips medical devices. The system eliminates the need to manually search product catalogues, specification sheets, or contact sales representatives for routine product information.

It answers natural language questions about device features, technical specifications, product comparisons, general medical concepts, and provides access to official product documentation through a secure OTP-verified download workflow. The chatbot operates 24/7, maintains per-user conversation histories, personalises responses based on browsing preferences, and ensures no sensitive document is served without identity verification.

---

## 3. Problem Statement

Healthcare procurement teams and biomedical engineers frequently need detailed technical information about medical devices — specifications, feature comparisons, clinical applications, and compatibility details. This information is typically scattered across multiple PDF datasheets, product websites with inconsistent navigation, and sales representatives who may not be immediately available.

Existing solutions have these limitations:

- **Static FAQ pages** answer only pre-defined questions and cannot handle follow-up queries or comparisons.
- **Manual document search** requires users to download and read entire PDFs to find a single specification value.
- **Generic AI assistants** (ChatGPT, Gemini direct) have no knowledge of specific product catalogues or model numbers, and hallucinate specifications.
- **Keyword search engines** return documents but do not synthesise answers from multiple sources.
- **No access control** on document downloads — sensitive clinical datasheets are often publicly accessible without identity verification.
- **No chat history** — each session starts over with no continuity.

The result is that procurement decisions are delayed, sales cycles are lengthened, and clinical staff waste time on information retrieval instead of patient care.

---

## 4. Existing System

Before this project, there was no dedicated conversational interface for Philips medical device information. The information landscape consisted of:

- The Philips Healthcare website with category-based browsing, requiring users to already know which product they were looking for.
- PDF datasheets stored in Supabase Storage, accessible only through direct URL sharing with no access control or identity verification.
- A basic product listing page with static descriptions, no search, and no filtering by clinical specification.
- No chat history, no personalisation, no comparison capability, and no way to ask a natural language question like "what is the difference between the TC50 and TC35 for a cardiology department?"
- No out-of-scope filtering, no purchase intent detection, and no session timeout — meaning any query would attempt to search the knowledge base regardless of relevance.

---

## 5. Proposed System

The proposed system is a full-stack AI-powered chatbot with the following capabilities:

**Conversational Intelligence:** Users type natural language questions. The system detects intent, retrieves relevant information from a vector knowledge base and PDF index, synthesises a structured markdown response using Google Gemini 2.0 Flash, and streams the answer token by token via Server-Sent Events.

**Hybrid Retrieval:** FAISS semantic search and BM25 keyword search are combined using Reciprocal Rank Fusion (RRF). A CrossEncoder reranker selects the top 5 most relevant chunks. When no product is found, the system falls back to DuckDuckGo web search enriched with Wikipedia summaries for general medical concepts.

**Confidence Gating:** When FAISS returns a product with confidence below 0.97 and the product name does not appear in the original query, the match is discarded and the system falls through to dynamic web search rather than returning a wrong product answer.

**Secure Document Access:** Users can browse a categorised document library. Downloading any document requires filling an identity form, verifying a 6-digit OTP sent by email, and using a single-use signed token that expires in 15 minutes. Raw Supabase storage URLs are never exposed to the client.

**Authentication and Session Management:** Full Supabase Auth integration with email/password registration, JWT token validation on every API call, 30-minute inactivity session timeout, and cross-tab logout broadcast via BroadcastChannel.

**Chat History:** Every conversation is stored per authenticated user. Users can browse past conversations, resume them, and all messages render with the same markdown formatter regardless of whether they come from a live stream, cache, or history restore.

**Versioned Semantic Cache:** A `CACHE_VERSION=2` cache stores final formatted responses with 384-dimensional sentence-transformer embeddings. Semantically similar future queries are matched with cosine similarity above a 0.90 threshold. Old entries from previous pipeline versions are automatically ignored without deleting the cache table. Only final validated formatted markdown is ever cached — never raw FAISS chunks, PDF text, or partially formatted output.

**Response Quality Pipeline:** Every Gemini response passes through a deterministic validator before being returned. If validation fails (wrong product, raw metadata detected, missing structural headers), the response_refiner regenerates the answer entirely without Gemini.

---

## 6. Project Architecture

### 6.1 Overall Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    FRONTEND (React 19)                    │
│  FloatingChatbot │ ResourcesPage │ Auth Pages             │
│  DownloadModal   │ Navbar/Footer │ Products/Contact       │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTPS  (Axios / Fetch SSE)
┌──────────────────────────▼───────────────────────────────┐
│                   BACKEND (FastAPI + Uvicorn)             │
│  /chat  /chat/stream  /history  /conversation            │
│  /documents  /download/*  /preferences  /contact        │
└──────────┬──────────────┬──────────────┬─────────────────┘
           │              │              │
      ┌────▼────┐   ┌─────▼──────┐  ┌───▼──────────────┐
      │Supabase │   │Gemini 2.0  │  │ FAISS / BM25     │
      │DB+Auth  │   │Flash API   │  │ PDF Index        │
      │+Storage │   │(Key Rotate)│  │ DuckDuckGo       │
      └─────────┘   └────────────┘  │ Wikipedia API    │
                                    └──────────────────┘
```

### 6.2 Backend Architecture

The backend is a single FastAPI application (`backend/app.py`) that exposes all REST endpoints. Key module responsibilities:

**`app.py`** — Main router. Defines all endpoints and the shared module-level pipeline helpers: `_format_product_chunk` (converts raw FAISS chunks to structured sections), `_build_combined_context` (builds full context list for both /chat and /chat/stream identically), `_build_retry_context` (fresh context for validator retry path), `_sse_encode` (encodes newlines as `\n` literals so SSE wire format preserves markdown spacing).

**`intent_detector.py`** — Pure Python keyword/regex classifier. Returns one of six intent constants. Contains five guard functions: `is_purchase_intent`, `is_out_of_scope`, `is_sample_report_intent`, `is_medical_query`, and `detect_intent`. Purchase, OOS, and sample report guards short-circuit before cache or retrieval. A concept-trigger gate routes generic device concept queries ("tell me about ECG") to `general_medical_query` instead of `product_query`.

**`gemini_service.py`** — Wraps Google Gemini 2.0 Flash. Builds seven intent-specific prompts, rotates across two API keys (`GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`), handles quota errors with exponential backoff (capped at 10 seconds), streams tokens asynchronously, and contains structural validation guards before returning Gemini output. The response_refiner always runs first as the deterministic base; Gemini is an optional polish layer.

**`response_refiner.py`** — Deterministic formatter. Parses structured product chunks using regex section extraction and produces clean markdown output for all 7 intent types without any AI call. This is the guaranteed fallback that always produces output even when Gemini is unavailable. Contains the `_wiki_summary` function that aggressively filters raw search snippets, DuckDuckGo title prefixes, URLs, domain names, and MedicalExpo headings before extracting clean prose sentences.

**`cache_service.py`** — Versioned semantic cache with `CACHE_VERSION=2`. Uses `_is_formatted()` to reject raw FAISS chunks, web search output, PDF headers, and fallback messages. Embeds queries with `all-MiniLM-L6-v2` and stores 384-dimensional vectors. Skips entries whose version field does not match the current `CACHE_VERSION`. Logs every cache event with STATUS, VERSION, QUESTION, and KEY.

**`search/orchestrator.py`** — Coordinates the full retrieval pipeline. Contains the confidence gate that drops low-confidence wrong-product matches. Routes category and general_medical queries to dynamic search only. Adds Wikipedia enrichment for general_medical queries when DuckDuckGo results are weak.

**`search/product_search.py`** — Loads FAISS index (`vector_db/faiss_index.bin`) and product chunks (`vector_db/product_chunks.pkl`) at startup. Implements `exact_match` (scans chunk names against normalised query), `faiss_search` (delegates to hybrid search), and `comparison_search` (split-and-retrieve with brand prefix enrichment for bare model numbers like "TC70").

**`search/hybrid_search.py`** — Combines FAISS and BM25 results using Reciprocal Rank Fusion with k=60. Retrieves up to 10 FAISS candidates and 10 BM25 candidates, fuses by RRF score, returns top 5. Falls back gracefully to whichever source produces results when the other returns nothing.

**`search/bm25_index.py`** — BM25Okapi index built at startup from all 20 product chunks. Handles tokenisation, stopword filtering, and returns ranked (chunk, score) pairs.

**`search/reranker.py`** — CrossEncoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) lazy-loaded on first call. Scores each (query, chunk) pair and returns top 5 by descending score. Falls back to original order if model load fails.

**`search/query_rewriter.py`** — Strips conversational fillers ("tell me about", "can you explain"), expands medical abbreviations (`ecg` → `electrocardiogram ECG`, `aed` → `automated external defibrillator AED`), and generates up to 2 retrieval variants for multi-query retrieval.

**`search/pdf_search.py`** — Searches the PDF FAISS index (`pdf_processing/faiss/pdf.index`) filtered by product name with per-chunk L2 distance threshold of 1.4. Loads lazily — absent until `build_pdf_index.py` has been run. Returns metadata dicts with `chunk_id`, `product_name`, `document_name`, `page_number`, `chunk_text`.

**`pipeline/context_cleaner.py`** — Post-retrieval, pre-Gemini cleaner. Removes noise lines (lone page numbers, copyright lines, bare URLs, divider lines) while always preserving structural labels (Product, Category, Summary, Features, Specifications) and bullet markers. Joins kept lines with `\n` — never with spaces, because space-joining causes the "ProductPageWriterTC35Category..." concatenation bug. Cross-chunk deduplication is skipped for comparison queries.

**`pipeline/response_validator.py`** — Validates Gemini output: minimum 60 characters, no fallback sentinel fragments, no raw metadata lines (`Product Name:`, `Category:`), no out-of-scope sentinel when context was available, product name must be present for product/feature/spec intents, structural section headers required for comparison/specification/general_medical intents.

**`dynamic_search/duckduckgo_search.py`** — Calls DDGS (DuckDuckGo Search) with a medical device enriched query. Returns raw `title: body` snippet strings.

**`dynamic_search/wikipedia_service.py`** — Wikipedia REST summary API client. In-memory TTL cache (1 hour, 200 entries LRU). Tries exact-title lookup first, falls back to MediaWiki search API. Cleans reference markers, truncates at 600 characters at last sentence boundary.

**`dynamic_search/wikipedia_guard.py`** — Decides whether Wikipedia is appropriate for a given query. Only fires for `general_medical_query` intent with no known product fragment in query. Extracts the best topic string from the query using a priority list of medical keywords.

**`chat_history.py`** — Four Supabase operations: `create_conversation`, `save_message`, `get_user_conversations`, `get_conversation_messages`.

**`download_service.py`** — Complete OTP download pipeline: rate limit check (1 download per authenticated user per 24 hours, guests blocked), request creation, OTP generation and email dispatch via Gmail SMTP, OTP verification, HMAC-SHA256 serve token generation and single-use consumption, download tracking.

**`document_service.py`** — Queries `device_documents` table: `get_categories`, `get_subcategories`, `get_documents`, `get_documents_by_product`, `get_documents_by_names`. Deduplicates by `(document_name, document_type)` key.

### 6.3 Frontend Architecture

The frontend is a React 19 SPA built with Create React App.

**`App.js`** — Root component wrapping everything in `AuthProvider` and `BrowserRouter`. Defines all client-side routes: `/`, `/chat`, `/login`, `/register`, `/products`, `/services`, `/about`, `/contact`, `/resources`, `/documents`.

**`FloatingChatbot.jsx`** — The primary UI: streaming SSE reader with `\n` decode (reverses server-side `_sse_encode`), live markdown rendering via `ReactMarkdown + remarkGfm` with a shared `MD` component map, message bubbles for user and bot, source badges (📦 Knowledge Base, 🌐 Web, ⚡ Cached), history panel, document cards with View/Download buttons, voice input, feedback buttons (thumbs up/down, copy, regenerate), contact form popup, category selector, suggested questions, purchase/OOS/sample-report canned reply injection (client-side guard mirrors backend guard).

**`DownloadModal.jsx`** — Three-step modal: identity form (full_name, email, phone, designation, country) → OTP input with resend → success with serve URL download.

**`AuthContext.jsx`** — React context providing `session`, `user`, `isGuest`, `guestId`, `authLoading`. Subscribes to `onAuthStateChange` for reactive auth state across all components.

**`useSessionTimeout.js`** — 30-minute inactivity timer. Resets on `mousemove`, `mousedown`, `keydown`, `scroll`, `touchstart`, `wheel`, `visibilitychange`, `focus`, `click`. Fires `onTimeout` callback when expired. Only active for non-guest users.

### 6.4 AI Pipeline Architecture

```
User Query
    │
    ├─► is_purchase_intent?     YES → canned reply, no pipeline
    ├─► is_sample_report_intent? YES → canned reply, no pipeline, not cached
    ├─► is_out_of_scope?         YES → canned reply, no pipeline
    │
    ▼ NO guards triggered
detect_intent(query)
    → product_query | feature_query | specification_query
    → comparison_query | category_query | general_medical_query
    │
    ▼
get_cached_answer(question, intent)
    └─► HIT (version=2 + similarity ≥ 0.90) → stream from cache → save to history
    │
    ▼ MISS
query_rewriter.rewrite(query, intent)
    → canonical (fillers stripped, abbreviations expanded)
    → variants (original stripped, intent-prefixed)
    │
    ▼
orchestrator.smart_search(query, intent)
    │
    ├── category_query / general_medical
    │       → DuckDuckGo search
    │       → Wikipedia enrichment (general_medical only, if DDG weak)
    │       → SearchResult(source="dynamic_search" / "wikipedia")
    │
    ├── Exact product name match (conf=1.0, no reranking)
    │
    ├── Comparison split-and-retrieve (two independent FAISS lookups)
    │
    └── Hybrid FAISS+BM25 → RRF fusion → CrossEncoder top-5
            → Confidence gate (conf<0.97 AND product not in query → drop)
            → PDF search (product-scoped, distance threshold 1.4)
            → SearchResult(source="faiss")
    │
    ▼
_build_combined_context(result, intent)
    → _format_product_chunk per chunk (raw → structured sections)
    → PDF highlights extraction
    → Dynamic search wrapping with 🌐 header
    → context_cleaner.clean_chunks (noise removal, dedup)
    │
    ▼
response_refiner.refine(question, context, source, intent)  ← always runs
    → Deterministic base_answer (guaranteed output)
    │
    ▼
gemini_service.generate_answer(...) or generate_answer_streaming(...)
    → Intent-specific prompt (7 variants)
    → _call_gemini (key rotation, quota handling)
    → Structure validation guard per intent
    → Returns gemini_result if valid, else base_answer
    │
    ▼
response_validator.validate_response(answer, ...)
    └─► FAIL → _build_retry_context → refiner retry → final_answer
    └─► PASS → final_answer
    │
    ▼
_sse_encode (replace \n with \\n for SSE wire safety)
Stream tokens to frontend via SSE
    │
    ▼ (after full_answer assembled)
save_cached_answer (only if _is_formatted passes, writes CACHE_VERSION=2)
save_message (conversation_id, "assistant", full_answer)
```

### 6.5 Authentication Architecture

Authentication is entirely delegated to Supabase Auth. The backend never stores passwords or manages JWT issuance directly.

```
Registration:
  supabase.auth.signUp(email, password)
    → Supabase creates user in auth.users
    → Confirmation email sent (optional based on Supabase project settings)

Login:
  supabase.auth.signInWithPassword(email, password)
    → Returns: { session: { access_token, refresh_token }, user }
    → access_token = JWT signed by Supabase
    → Stored in localStorage by Supabase JS SDK

Every authenticated API call:
  Frontend: Authorization: Bearer <access_token> header
  Backend:  supabase.auth.get_user(token) → validated user UUID
  If invalid → 401 HTTPException

Session Restore:
  On page load: supabase.auth.getSession() → restores session from localStorage
  supabase.auth.onAuthStateChange() → reactive updates for sign in / sign out

Session Timeout (30 min inactivity):
  useSessionTimeout hook fires onTimeout()
    → supabase.auth.signOut()
    → SessionTimeoutModal shown 60 seconds before
    → BroadcastChannel broadcasts logout to all open tabs
```

Guest users receive a stable UUID stored in `localStorage` (`guest_<uuid4>`). Guest sessions are browser-tab scoped, conversations are not persisted to Supabase, and document downloads are blocked for guests (rate limit check explicitly raises `ValueError` for `user_id=None`).

### 6.6 Document Download Architecture

```
1. User clicks ⬇ button on a document card
        │
2. DownloadModal opens (step 1: identity form)
   Fields: full_name, email, phone, designation, country
        │
3. POST /download/request
   Backend:
     a. check_download_limit(user_id)  ← guest blocked, 1/24h for auth users
     b. _generate_otp() → 6 random digits
     c. INSERT document_download_requests row (otp_verified=false)
     d. _send_otp_email(email, name, otp, document_name) via Gmail SMTP
   Returns: { request_id, email }
        │
4. Modal step 2: OTP entry (6-digit code from email)
   POST /download/verify  { request_id, otp }
   Backend:
     a. Fetch request row
     b. Check _is_expired(otp_expiry)  ← 5-minute window
     c. Compare otp_code == otp_entered
     d. UPDATE otp_verified=true, downloaded=true, downloaded_at=now()
     e. _generate_serve_token(request_id):
          raw_token = secrets.token_urlsafe(32)  ← 256-bit random
          token_hash = HMAC-SHA256(DOWNLOAD_TOKEN_SECRET, raw_token)
          INSERT secure_download_tokens (token_hash, expires_at=now()+15min, used=false)
          return raw_token (NEVER stored in DB)
   Returns: { verified: true, serve_url: "/download/serve/<raw_token>" }
        │
5. Modal step 3: success, "Download Now" button → serve_url
   GET /download/serve/{token}
   Backend:
     a. Compute HMAC-SHA256(secret, token)
     b. SELECT from secure_download_tokens WHERE token_hash=hash
     c. Validate: not used, not expired
     d. UPDATE used=true, used_at=now()  ← single-use, atomic
     e. Fetch download request row for file_url
     f. httpx.AsyncClient.get(file_url)  ← server-side fetch from Supabase Storage
     g. Stream bytes as application/pdf
        Content-Disposition: attachment; filename="<safe_name>.pdf"
        Cache-Control: no-store, no-cache, must-revalidate, private
```

Raw Supabase Storage URLs are **never sent to the client** at any point. The only URL the client ever receives is `/download/serve/<token>`, which is a single-use backend endpoint.

---


## 7. Complete Technology Stack

### 7.1 Frontend
| Technology | Version | Purpose |
|---|---|---|
| React | 19.2.7 | UI framework |
| React Router DOM | 7.18.0 | Client-side routing |
| React Markdown | 10.1.0 | Markdown rendering in chat |
| remark-gfm | 4.0.1 | GitHub Flavoured Markdown tables and strikethrough |
| react-syntax-highlighter | 15.6.1 | Code block syntax highlighting |
| Framer Motion | 11.18.2 | Animations (chat window open/close, loading dots) |
| Lucide React | 0.469.0 | Icon set |
| Axios | 1.17.0 | HTTP client for REST API calls |
| MUI (Material UI) | 9.0.1 | UI component library (used in Resources/Documents page) |
| react-speech-recognition | 4.0.1 | Browser Web Speech API wrapper for voice input |
| @supabase/supabase-js | 2.108.2 | Supabase Auth and database client |

### 7.2 Backend
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.10 | Runtime |
| FastAPI | 0.136.3 | REST API framework |
| Uvicorn | 0.49.0 | ASGI server |
| Pydantic | 2.13.4 | Request/response validation schemas |
| python-dotenv | 1.2.1 | Environment variable loading |

### 7.3 Database
| Technology | Purpose |
|---|---|
| Supabase (PostgreSQL) | Primary database for all persistent data |
| pgvector extension | Vector storage for semantic cache embeddings (384 dimensions) |

### 7.4 Authentication
| Technology | Purpose |
|---|---|
| Supabase Auth | JWT-based email/password authentication |
| Supabase JS SDK | Frontend session management and token handling |
| Supabase Python SDK | Backend JWT validation via `auth.get_user()` |

### 7.5 AI Models
| Model | Provider | Purpose |
|---|---|---|
| gemini-2.0-flash | Google Gemini API | Primary response generation |
| all-MiniLM-L6-v2 | Sentence Transformers (HuggingFace) | Query/chunk embeddings for FAISS and cache |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | Sentence Transformers | CrossEncoder reranker for top-5 chunk selection |

### 7.6 Vector Database
| Component | Purpose |
|---|---|
| FAISS (faiss-cpu 1.14.2) | Product knowledge base index (20 chunks) and PDF knowledge index (260+ chunks) |
| IndexFlatL2 | Exact L2 distance index type used for both product and PDF indices |

### 7.7 Search
| Component | Purpose |
|---|---|
| FAISS semantic search | Dense vector retrieval for product and PDF chunks |
| BM25Okapi (rank-bm25 0.2.2) | Sparse keyword retrieval over product chunks |
| Reciprocal Rank Fusion | Hybrid fusion algorithm combining FAISS and BM25 results |
| CrossEncoder reranker | Second-pass relevance scoring after RRF fusion |
| DuckDuckGo DDGS (ddgs ≥9.14.4) | Web search fallback for general medical queries |
| Wikipedia REST API | Medical concept summaries (no API key required) |

### 7.8 Caching
| Component | Purpose |
|---|---|
| Supabase `cached_answers` table | Persistent semantic cache storage |
| pgvector IVFFlat index | Approximate nearest-neighbour search on cached embeddings |
| all-MiniLM-L6-v2 | Cache query embedding for cosine similarity matching |
| CACHE_VERSION=2 | Version field on every row; old versions ignored automatically |

### 7.9 Storage
| Component | Purpose |
|---|---|
| Supabase Storage | PDF document storage (datasheets, user manuals) |
| Local filesystem (`vector_db/`) | Product FAISS index and chunk pickle file |
| Local filesystem (`pdf_processing/`) | PDF FAISS index and metadata pickle |

### 7.10 APIs
| API | Purpose |
|---|---|
| Google Gemini API (gemini-2.0-flash) | LLM response generation with key rotation |
| Supabase REST API | All database operations via Python SDK |
| Wikipedia REST Summary API | Medical concept summaries |
| DuckDuckGo Search (DDGS) | Web search fallback |
| Gmail SMTP | OTP delivery email |

### 7.11 Key Libraries
| Library | Purpose |
|---|---|
| sentence-transformers 5.5.1 | SentenceTransformer and CrossEncoder model loading |
| faiss-cpu 1.14.2 | FAISS index creation, search, serialisation |
| numpy 2.2.6 | Vector arithmetic for embeddings and distance calculations |
| pypdf 4.3.1 | PDF text extraction in the PDF processing pipeline |
| rank-bm25 0.2.2 | BM25Okapi implementation |
| httpx | Async HTTP client for server-side PDF file fetching |
| python-dateutil | OTP and token expiry timestamp parsing |
| secrets | Cryptographically secure random token generation |
| hmac / hashlib | HMAC-SHA256 for serve token hashing |

---

## 8. Folder Structure

```
MediDevice_Chatbot/
│
├── backend/                        ← All Python server code
│   ├── app.py                      ← FastAPI app, all endpoints, shared pipeline helpers
│   ├── intent_detector.py          ← Query intent classification and guard functions
│   ├── gemini_service.py           ← Gemini API wrapper, prompts, streaming, guards
│   ├── response_refiner.py         ← Deterministic markdown formatter (7 intent formatters)
│   ├── cache_service.py            ← Versioned semantic cache (CACHE_VERSION=2)
│   ├── chat_history.py             ← Supabase conversation and message operations
│   ├── document_service.py         ← Device document library queries
│   ├── download_service.py         ← OTP download pipeline and secure token management
│   ├── email_service.py            ← Contact form SMTP email sender
│   ├── logger.py                   ← Structured search event logger
│   ├── models.py                   ← All Pydantic request/response schemas
│   ├── conversation_service.py     ← Legacy conversation helper (thin wrapper)
│   ├── requirements.txt            ← Python dependencies
│   │
│   ├── search/                     ← Retrieval pipeline modules
│   │   ├── __init__.py             ← Exports smart_search, _model, normalise_query
│   │   ├── orchestrator.py         ← Full retrieval pipeline coordinator
│   │   ├── product_search.py       ← FAISS product search, exact match, comparison
│   │   ├── hybrid_search.py        ← RRF fusion of FAISS and BM25 results
│   │   ├── bm25_index.py           ← BM25Okapi index over product chunks
│   │   ├── reranker.py             ← CrossEncoder lazy-loaded reranker
│   │   ├── query_rewriter.py       ← Filler stripping, abbreviation expansion, variants
│   │   ├── pdf_search.py           ← PDF FAISS index search with product filtering
│   │   ├── common.py               ← Shared types (SearchResult), normalise_query, helpers
│   │   └── dynamic_search.py       ← Thin wrapper calling duckduckgo_search.search()
│   │
│   ├── pipeline/                   ← Post-retrieval quality pipeline
│   │   ├── context_cleaner.py      ← Noise removal and cross-chunk deduplication
│   │   └── response_validator.py   ← Gemini output structural validation
│   │
│   ├── dynamic_search/             ← Web and Wikipedia search modules
│   │   ├── duckduckgo_search.py    ← DDGS web search with medical query enrichment
│   │   ├── wikipedia_service.py    ← Wikipedia REST API with TTL in-memory cache
│   │   └── wikipedia_guard.py      ← Guard and topic extractor for Wikipedia calls
│   │
│   ├── pdf_processing/             ← PDF ingestion and index building
│   │   ├── extract_text.py         ← pypdf text extraction from PDF files
│   │   ├── clean_text.py           ← Post-extraction text normalisation
│   │   ├── chunk_text.py           ← Semantic chunking (~500 words, 100-word overlap)
│   │   ├── embed_chunks.py         ← FAISS index building for PDF chunks
│   │   ├── faiss/                  ← pdf.index (FAISS binary)
│   │   └── metadata/               ← pdf_metadata.pkl (chunk metadata dicts)
│   │
│   ├── vector_db/                  ← Product knowledge base
│   │   ├── faiss_index.bin         ← Product FAISS index (20 vectors, 384-dim)
│   │   ├── product_chunks.pkl      ← 20 product chunk strings
│   │   └── create_embeddings.py    ← Script to rebuild product index
│   │
│   ├── database/
│   │   └── supabase_client.py      ← Supabase Python client singleton
│   │
│   ├── scripts/
│   │   ├── build_pdf_index.py      ← Offline script: fetch PDFs, chunk, embed, index
│   │   ├── sync_documents.py       ← Sync device_documents table with storage
│   │   └── cleanup_cache.py        ← Cache maintenance utilities
│   │
│   ├── data/
│   │   ├── dynamic_products.json   ← Product metadata for dynamic display
│   │   └── device_urls.json        ← Device URL mapping
│   │
│   └── logs/
│       └── search_logs.txt         ← Structured search event log
│
├── frontend/                       ← React 19 SPA
│   ├── src/
│   │   ├── App.js                  ← Root component, routing
│   │   ├── App.css                 ← Global styles
│   │   ├── index.js                ← React DOM entry point
│   │   │
│   │   ├── components/
│   │   │   ├── FloatingChatbot.jsx ← Full chat widget (streaming, history, docs)
│   │   │   ├── DownloadModal.jsx   ← OTP-verified document download wizard
│   │   │   ├── Navbar.jsx          ← Top navigation with auth state
│   │   │   ├── SessionTimeoutModal.jsx  ← 30-minute inactivity warning
│   │   │   ├── SessionTimeoutHandler.jsx ← Hooks timeout to logout action
│   │   │   ├── ContactForm.jsx     ← Contact support form
│   │   │   ├── VoiceInput.jsx      ← Web Speech API microphone input
│   │   │   ├── SuggestedQuestions.jsx ← Category-aware question chips
│   │   │   ├── CategoryDropdown.jsx   ← Device category selector
│   │   │   ├── SignInPromptModal.jsx  ← Prompt shown to guests
│   │   │   ├── FeaturedProducts.jsx  ← Homepage product cards
│   │   │   ├── Hero.jsx              ← Homepage hero section
│   │   │   ├── Footer.jsx            ← Site footer
│   │   │   ├── Testimonials.jsx      ← Social proof section
│   │   │   ├── WhyChooseUs.jsx       ← Feature highlights section
│   │   │   ├── ServicesSection.jsx   ← Services overview section
│   │   │   └── StatsSection.jsx      ← Numerical stats section
│   │   │
│   │   ├── pages/
│   │   │   ├── Home.jsx            ← Landing page composition
│   │   │   ├── Chatbot.js          ← Dedicated chatbot page (full-screen)
│   │   │   ├── Login.jsx           ← Supabase email/password login
│   │   │   ├── Register.jsx        ← Supabase registration with email confirm
│   │   │   ├── ResourcesPage.jsx   ← Document library (category/subcategory browser)
│   │   │   ├── ProductsPage.jsx    ← Product catalogue listing
│   │   │   ├── ServicesPage.jsx    ← Services description page
│   │   │   ├── ContactPage.jsx     ← Contact form page
│   │   │   ├── About.jsx           ← About page
│   │   │   └── Documents.jsx       ← Alternative documents page
│   │   │
│   │   ├── context/
│   │   │   └── AuthContext.jsx     ← Global auth state provider
│   │   │
│   │   ├── hooks/
│   │   │   └── useSessionTimeout.js ← 30-minute inactivity timer hook
│   │   │
│   │   └── lib/
│   │       ├── supabase.js          ← Supabase JS client (anon key)
│   │       ├── guestSession.js      ← Guest UUID generator/persister
│   │       ├── purchaseIntentDetector.js  ← Client-side purchase guard
│   │       ├── outOfScopeDetector.js      ← Client-side OOS guard
│   │       └── sampleReportDetector.js    ← Client-side sample report guard
│   │
│   ├── public/                     ← Static assets (index.html, favicon, logos)
│   └── package.json                ← Frontend dependencies
│
├── supabase_migration.sql          ← Main DB migration (user_preferences, download_requests)
├── supabase_indexes_migration.sql  ← Index migration (pgvector, conversations, messages)
├── phase5_4_migration.sql          ← secure_download_tokens table
├── phase5_5_migration.sql          ← Download rate-limit index
├── requirements.txt                ← Root-level Python deps (mirrors backend/)
├── Procfile                        ← Deployment process file
└── DOCUMENTATION.md                ← This document
```

---


## 9. Database Design

The database runs on Supabase (managed PostgreSQL). All tables are in the `public` schema. The backend uses the **service role key** which bypasses Row Level Security for all operations. RLS policies exist to protect direct anon/authenticated client access.

### Table 1: `auth.users` (Supabase managed)

Managed entirely by Supabase Auth. The backend never writes to this table directly.

| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key, referenced by all user-linked tables |
| email | text | User's email address |
| encrypted_password | text | Bcrypt hash (managed by Supabase) |
| created_at | timestamptz | Account creation timestamp |

### Table 2: `conversations`

Stores one row per chat conversation. Each authenticated user can have many conversations.

| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key (gen_random_uuid()) |
| user_id | uuid | FK → auth.users(id) ON DELETE CASCADE |
| title | text | First 60 characters of the first question |
| created_at | timestamptz | Conversation creation time |

**Indexes:** `idx_conversations_user_id` (fast user lookup), `idx_conversations_created_at DESC` (most-recent-first listing).

**Relationship:** One `conversations` row → many `messages` rows.

### Table 3: `messages`

Stores individual chat messages within a conversation. Each message is either from the user or the assistant.

| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| conversation_id | uuid | FK → conversations(id) ON DELETE CASCADE |
| sender | text | Either `"user"` or `"assistant"` |
| content | text | Full message text (markdown for assistant) |
| created_at | timestamptz | Message timestamp |

**Indexes:** `idx_messages_conversation_id` (fast conversation load), `idx_messages_created_at` (chronological ordering).

**Relationship:** Many `messages` rows → one `conversations` row.

### Table 4: `cached_answers`

Stores versioned semantic cache entries. Each row is a (question_key, answer, embedding, version) tuple. The `question` column stores a normalised composite key in the format `intent::normalised_question` (e.g. `product_query::what is pagewriter tc50`).

| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| question | text | Cache key: `intent::normalised_question` |
| answer | text | Final formatted markdown response |
| embedding | vector(384) | all-MiniLM-L6-v2 embedding of the question |
| version | integer | Cache version (currently 2); older versions are ignored on read |
| created_at | timestamptz | Row creation time |

**Indexes:** `idx_cached_answers_embedding` (IVFFlat vector_cosine_ops, lists=100) for approximate nearest-neighbour semantic lookup.

**Logic:** On read, only rows with `version = CACHE_VERSION` are considered. The system never deletes old rows — they are silently skipped. On write, a duplicate check ensures no two rows share the same key+version combination.

### Table 5: `device_documents`

Stores metadata for all downloadable documents. Each row represents a single PDF document associated with a product.

| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| product_name | text | Product this document belongs to |
| document_name | text | Human-readable document name |
| document_type | text | e.g. "Datasheet", "User Manual", "Brochure" |
| category | text | e.g. "Cardiology", "PatientMonitoring" |
| subcategory | text | e.g. "ECG Machines", "Defibrillators" |
| file_url | text | Supabase Storage URL (never sent to client directly) |
| storage_path | text | Relative storage path for backend fetch |
| is_active | boolean | Soft-delete flag; inactive rows are excluded from all queries |

**Indexes:** `idx_device_documents_category_subcategory` (WHERE is_active=true), `idx_device_documents_product_name`, `idx_device_documents_document_name`, `idx_device_documents_is_active`.

### Table 6: `document_download_requests`

Tracks every download request with the full OTP state machine. Works for both authenticated users and guest users.

| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| user_id | uuid | FK → auth.users (nullable — NULL for guests) |
| guest_session_id | text | Guest UUID from localStorage (nullable — NULL for auth users) |
| full_name | text | Requester's full name |
| email | text | Requester's email (OTP sent here) |
| phone | text | Contact phone number |
| designation | text | Job title/role |
| country | text | Country of residence |
| document_id | text | ID of the document being requested |
| document_name | text | Document name displayed to user |
| file_url | text | Raw Supabase Storage URL (server-side only, never sent to client) |
| otp_code | text | Current 6-digit OTP |
| otp_verified | boolean | True after successful OTP verification |
| otp_expiry | timestamptz | OTP validity window (5 minutes from generation) |
| resend_count | integer | Number of OTP resends (max 3) |
| downloaded | boolean | True after first successful download |
| downloaded_at | timestamptz | Timestamp of first download |
| created_at | timestamptz | Request creation time |

**Indexes:** `idx_ddr_user_id`, `idx_ddr_guest_session_id`, `idx_ddr_email`, `idx_ddr_created_at DESC`, `idx_ddr_user_downloads_24h` (partial index for rate-limit query: WHERE otp_verified=true AND downloaded=true).

### Table 7: `secure_download_tokens`

Stores HMAC-SHA256 hashes of single-use serve tokens. The raw token is **never stored** — only its hash. This table is the enforcement layer for single-use, time-limited file serving.

| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| request_id | uuid | FK → document_download_requests(id) ON DELETE CASCADE |
| token_hash | text | HMAC-SHA256(DOWNLOAD_TOKEN_SECRET, raw_token) — UNIQUE |
| expires_at | timestamptz | Token validity (15 minutes from generation) |
| used | boolean | True after the token is consumed |
| used_at | timestamptz | Timestamp of consumption |
| created_at | timestamptz | Token creation time |

**Indexes:** `idx_sdt_token_hash` (fast serve-endpoint lookup), `idx_sdt_expires_at` (cleanup jobs).

**RLS:** Service role full access only. Anon and authenticated roles have no direct access. Token validation is entirely server-side.

### Table 8: `user_preferences`

Lightweight personalisation store. One row per authenticated user, upserted on every preference update.

| Column | Type | Description |
|---|---|---|
| user_id | uuid | PK + FK → auth.users(id) ON DELETE CASCADE |
| preferred_category | text | Last browsed device category |
| recent_products | text[] | Array of recently viewed product names |
| favorite_products | text[] | Array of user-starred product names |
| last_active | timestamptz | Last time preferences were updated |
| created_at | timestamptz | Row creation time |

**Index:** `idx_user_preferences_last_active DESC`.

### Entity Relationship Summary

```
auth.users (1) ──────< conversations (many)
                              │
                              └──────< messages (many)

auth.users (1) ──────< document_download_requests (many)
                              │
                              └──────< secure_download_tokens (many)

auth.users (1) ──────< user_preferences (1)

device_documents ── standalone (no FK to users)
cached_answers   ── standalone (no FK to users)
```

---

## 10. Complete AI Pipeline

This section describes every step a query takes from the moment a user submits it to the moment a response is rendered in the chat.

### Step 1 — User Query

The user types a question in the chat input and presses Enter or clicks Ask. On the frontend, three client-side guards run **before any API call**:

1. **`isPurchaseIntent(q)`** — checks for buying, pricing, quote, demo, dealer keywords. If true, injects a canned reply directly into the message list and returns. No API call is made.
2. **`isSampleReportIntent(q)`** — checks for sample report, example ECG, PDF output requests. If true, injects a canned reply. No API call is made.
3. **`isOutOfScope(q)`** — checks for off-topic domains (programming, sports, movies, politics). If true, injects a canned reply. No API call is made.

If no guard fires, the frontend calls `POST /chat/stream` with `{ question, user_id, conversation_id }` and opens an SSE stream.

### Step 2 — Intent Detection

`detect_intent(query)` runs on the backend with pure Python regex, taking microseconds:

1. **Comparison** — checks for "compare", "vs", "versus", "difference between", "which is better".
2. **Feature** — checks for "features", "capabilities", "functions", "benefits".
3. **Specification** — checks for "specifications", "specs", "dimensions", "weight", "technical detail".
4. **Category** — only if no specific product fragment present. Checks for "patient monitoring devices", "cardiology equipment", "overview of", "list of devices".
5. **General Medical** — only if no product fragment present. Checks `_GENERAL_MEDICAL_TERMS` (surgery lights, holter monitor, bubble cpap, infusion pump, etc.) and a concept-trigger gate for generic device terms ("tell me about ECG" when no model number is present).
6. **Product Query** — default for everything else.

Three additional backend guards run after intent detection:

- `is_purchase_intent` → canned reply, conversation saved, no pipeline
- `is_sample_report_intent` → canned reply, conversation saved, not cached
- `is_out_of_scope` → canned reply, conversation saved, no pipeline

### Step 3 — Cache Check

`get_cached_answer(question, intent)` is called before any retrieval:

1. If `ENABLE_CACHE=false` → skip (full pipeline always runs).
2. Fetch all rows from `cached_answers` WHERE `question LIKE 'intent::%'`.
3. Filter: keep only rows WHERE `(version OR 1) == CACHE_VERSION` (currently 2). Older rows are logged and skipped.
4. If no versioned rows have embeddings → exact key match only (`intent::normalised_question`).
5. If embeddings present → embed the current query with `all-MiniLM-L6-v2`, compute cosine similarity against each cached embedding, check product token conflict (e.g. TC50 query should not hit a TC35 cached answer).
6. If best score ≥ 0.90 → return cached answer.
7. On cache HIT → save to chat history → stream to frontend → done (pipeline ends here).

### Step 4 — Query Rewriting

`query_rewriter.rewrite(query, intent)` produces a `RewrittenQuery`:

1. **Strip fillers** — removes "can you", "tell me about", "what is", "please", "I want to know" from the start of the query.
2. **Expand abbreviations** — whole-word replacement: `ecg` → `electrocardiogram ECG`, `aed` → `automated external defibrillator AED`, `abpm` → `ambulatory blood pressure monitor ABPM`, `cpap` → `CPAP continuous positive airway pressure`.
3. **Normalise** — applies `normalise_query`: lowercases, fixes spacing in compound names (`page writer` → `pagewriter`, `TC 50` → `tc50`).
4. **Generate variants** — up to 2 additional retrieval strings: stripped original (preserves exact product names), intent-prefixed canonical for feature/spec queries.

The canonical goes to all retrieval steps; variants are used for multi-query FAISS/BM25 retrieval and merged with RRF.

### Step 5 — Retrieval (Orchestrator)

`smart_search(query, intent)` routes based on intent:

**Category / General Medical route:**
- Calls `dynamic_search.search(query)` → DuckDuckGo DDGS with `query + "medical device healthcare hospital equipment"`.
- For `general_medical_query`: if `should_use_wikipedia(query, intent)` returns true (no product fragment, correct intent), also calls `wikipedia_service.fetch(topic)`. If DuckDuckGo returned fewer than 2 chunks, Wikipedia becomes the sole source. Otherwise, Wikipedia is appended as supplementary background.
- Returns `SearchResult(source="dynamic_search" or "wikipedia")`.

**All other intents:**

1. **Exact match** — scans all 20 product chunks. For each chunk, checks if `extract_product_name(chunk).lower() in normalise_query(query)`. For comparison queries, also tries split-side lookup with brand prefix enrichment (e.g. "TC70" → "PageWriter TC70"). Returns `SearchResult(conf=1.0)` immediately if match found.

2. **Comparison split search** — for `comparison_query` with no exact match: `_split_comparison(query)` splits on "vs", "versus", "and" separators; strips leading verbs; enriches bare model numbers with brand prefix. Runs two independent FAISS lookups, merges results up to 6 chunks.

3. **Hybrid FAISS + BM25** — `hybrid_product_search(query, top_k=5)`:
   - FAISS: encode normalised query with `all-MiniLM-L6-v2`, search top 10 candidates in `IndexFlatL2`, filter by `MAX_CHUNK_DISTANCE=1.4`.
   - BM25: `bm25_search(query, top_k=10)` using `BM25Okapi` over tokenised product chunks.
   - RRF fusion: `RRF_score(doc) = Σ 1/(60 + rank_i(doc))` across both lists.
   - Multi-query: also retrieves for each rewriter variant, merges with RRF.

4. **CrossEncoder reranking** — `rerank(original_query, chunks, top_k=5)`: scores each `(query, chunk)` pair with `cross-encoder/ms-marco-MiniLM-L-6-v2`, returns top 5 by descending score. The **original** user query (not rewritten canonical) is used here, as cross-encoders are trained on natural language.

5. **Confidence gate** — if `result.confidence < 0.97` AND none of the matched product's name tokens appear in the original query text → the result is discarded and falls through to dynamic search. This prevents wrong-product answers (e.g. "Tell me about Infusion Pumps" matching DFM100 at 0.95 confidence).

6. **PDF search** — `pdf_search.search(query, top_k=3, matched_product=result.matched_product)`: filters `pdf_metadata` to chunks whose `product_name` fuzzy-matches the matched product, computes L2 distances against filtered set, keeps chunks with distance ≤ `MAX_PDF_DISTANCE=1.4`.

7. **Dynamic search fallback** — if hybrid search returns nothing and `is_medical_query(query)` returns true, falls through to DuckDuckGo. If `is_medical_query` returns false → returns `SearchResult(source="out_of_scope")` which triggers the OOS canned reply.

### Step 6 — Context Building

`_build_combined_context(result, intent)` in `app.py`:

1. **Product chunks**: for each unique chunk (after `deduplicate_by_product`), calls `_format_product_chunk(chunk)` to convert raw FAISS text into the structured section format:
   ```
   📦 Product
   
   PageWriter TC50
   
   Category
   Cardiology
   
   Summary
   
   <description>
   
   Features
   
   - Feature Name: detail
   
   Specifications
   
   - Spec Name: value
   ```
   Multiple chunks separated by `\n\n---\n\n`. This format is what `response_refiner` expects.

2. **PDF chunks**: extracts bullet-worthy lines using `_extract_bullets(chunk_text)` (scoring heuristic: technical keywords, numbers, sentence length). Formats as:
   ```
   📄 PDF Knowledge
   
   Source
   
   <document_name>
   Page <page_number>
   
   Highlights
   
   - bullet
   ```

3. **Dynamic search**: wraps all chunks in `🌐 Dynamic Search\n\n<joined_chunks>`.

4. **Context cleaning**: `clean_chunks(combined_context, intent)` removes noise lines, preserves structural labels, deduplicates across chunks (skipped for comparison queries).

### Step 7 — Response Refiner (Deterministic Base)

`response_refiner.refine(question, context, source, intent)` always runs first and produces `base_answer`:

Routing:
- `source in ("wikipedia", "dynamic_search")` → `format_general_medical` or `format_category` or `format_dynamic`
- `feature_query` → `format_features`
- `specification_query` → `format_specifications`
- `comparison_query` → `format_comparison`
- `category_query` → `format_category`
- `general_medical_query` → `format_general_medical`
- default → `format_product`

Each formatter parses the structured context sections using `_get_section`, `_product_name`, `_category`, `_description`, `_features`, `_specs` regex extractors and produces clean markdown with the standardised emoji headers:

| Intent | Header | Sections |
|---|---|---|
| product_query | `## 📦 Product Name` | Overview, Key Features (•), Specifications (•), Applications, Documents |
| feature_query | `## ✨ Features — Name` | Bullet list with •, closing clinical sentence |
| specification_query | `## 📋 Technical Specifications — Name` | Bullet list `• **Param:** value` |
| comparison_query | `## 📊 A vs B` | ### Product A, ### Product B, ### Key Differences, ### Recommendation |
| category_query | `## 🏥 Category Devices` | ### Available Devices, ### Applications |
| general_medical_query | `## 🏥 Concept Name` | ### What it is, ### Purpose, ### Clinical Use, ### Related Devices |
| dynamic/format_dynamic | `## 🌐 Web Information` | ### Summary, ### Key Points, ### Clinical Relevance |

The `_wiki_summary` function strips DuckDuckGo "Title: body" prefixes, URLs, MedicalExpo/navigation headings, bare domain names, and title-case short lines. It accepts only sentences with terminal punctuation and ≥6 words. Deduplicates case-insensitively before returning up to 4 clean prose sentences.

### Step 8 — Gemini Polish (Optional)

`generate_answer(question, context, source, intent)` in `gemini_service.py`:

1. Uses `base_answer` from the refiner as fallback.
2. Selects one of 7 intent-specific prompt templates (product, feature, specification, comparison, category, general_medical, web/wikipedia), each with mandatory `_FORMAT_RULES`.
3. Calls `_call_gemini(prompt)`: tries `GEMINI_API_KEY_1` first, falls back to `GEMINI_API_KEY_2` on quota error. Quota errors trigger a sleep (min of 10s or the retry-after value from the error message).
4. Validates `gemini_result` structure against the intent:
   - **comparison**: must have `###` section headers or `|` table rows
   - **specification**: must have `•` bullets, `|` table, or "unavailable" message
   - **general_medical**: must have `🏥` emoji in a line, or ≥2 known section headers
5. If validation passes and `len(gemini_result) > len(base_answer) * 0.5` → returns `gemini_result`.
6. Otherwise → returns `base_answer`.

For streaming (`generate_answer_streaming`), structured intents (comparison, specification, general_medical) are **buffered completely** before the structure check, then streamed in 64-byte chunks. Non-structured intents stream tokens as they arrive.

### Step 9 — Response Validator

`response_validator.validate_response(answer, question, intent, matched_product, has_context)`:

1. Empty or blank → FAIL
2. Length < 60 characters → FAIL
3. Contains fallback fragment → FAIL
4. Contains ≥2 raw metadata patterns (`Product Name:`, `Category:`, `Description:`) → FAIL
5. Has context but contains out-of-scope sentinel → FAIL
6. Product name absent for product/feature/spec intents → FAIL
7. Comparison: no `###` headers and no `|` table → FAIL
8. Specification: no `•` bullets, no `|` table, no "unavailable" message → FAIL
9. General medical: no `🏥` emoji and fewer than 2 known section headers → FAIL
10. All checks pass → PASS

On FAIL, the pipeline calls `_build_retry_context(result, intent)` (fresh context without context_cleaner, in case cleaner dropped needed sections) and re-runs `response_refiner.refine()` directly.

### Step 10 — SSE Encoding and Streaming

`_sse_encode(token)` replaces every `\n` with the literal string `\n` (backslash-n). This is necessary because SSE uses bare newlines as event delimiters — without encoding, every markdown paragraph break in the streamed response would be silently dropped, causing all sections to run together as one line.

The frontend SSE reader decodes: `const decoded = data.replace(/\\n/g, "\n")` before accumulating tokens in `fullText`.

### Step 11 — Cache Storage

After the full pipeline produces `full_answer`, `save_cached_answer(question, answer, intent)`:

1. Skips if `ENABLE_CACHE=false` or intent is `purchase_intent`/`out_of_scope`/`sample_report_intent`.
2. Calls `_is_formatted(answer)`: rejects if shorter than 100 chars, if fallback fragment present, or if any `_RAW_OUTPUT_MARKERS` found (`product name:`, `[web search results]`, `🌐 dynamic search`, `📄 pdf knowledge`, etc.).
3. Generates 384-dim embedding of the query.
4. Checks for duplicate: existing row with same key AND same version.
5. Inserts: `{ question: key, answer, embedding: vec, version: CACHE_VERSION }`.

### Step 12 — Chat History Storage

`save_message(conversation_id, "assistant", full_answer)` inserts the complete final markdown response into the `messages` table. This is the same text that will be rendered when a user reopens the conversation — ensuring history and live chat are always identical.

---


## 11. Authentication Flow

### Registration

1. User navigates to `/register` and submits email + password.
2. `supabase.auth.signUp({ email, password })` is called on the frontend.
3. Supabase creates a row in `auth.users`, hashes the password with bcrypt, and optionally sends a confirmation email (configurable in Supabase dashboard).
4. On success, a session is established and the user is redirected to the home page.
5. `AuthContext` receives the new session via `onAuthStateChange`, updating `user`, `session`, `isGuest=false` globally.

### Login

1. User navigates to `/login` and submits email + password.
2. `supabase.auth.signInWithPassword({ email, password })` is called.
3. Supabase validates credentials and returns `{ session: { access_token, refresh_token }, user }`.
4. The Supabase JS SDK stores the session in `localStorage` automatically.
5. `AuthContext` updates, all protected UI elements become available.

### Every API Call

1. Frontend calls `authHeaders()`: `supabase.auth.getSession()` retrieves the current session, extracts `access_token`.
2. All Axios/fetch calls include `Authorization: Bearer <access_token>`.
3. Backend `_get_authenticated_user_id(authorization)`:
   - Parses `Bearer <token>` from header.
   - Calls `supabase.auth.get_user(token)` — Supabase validates the JWT signature and expiry.
   - Returns `user.id` (UUID).
   - Raises HTTP 401 if token is missing, malformed, or expired.

### Guest Access

1. No login required to use the chatbot.
2. `getGuestSessionId()` checks localStorage for an existing `guest_<uuid4>`. If absent, generates and stores a new one.
3. Guest users can ask questions and receive answers, but conversations are not persisted to Supabase.
4. Document downloads are blocked for guests — `check_download_limit(user_id=None)` raises `ValueError` immediately.
5. A `Sign In →` prompt appears in the chat header and in the guest banner.

### Session Restore

1. On every page load, `supabase.auth.getSession()` checks localStorage and restores the session if the access token is still valid or can be refreshed.
2. The refresh token is used automatically by the Supabase JS SDK to obtain a new access token when the current one expires (~1 hour default).

### Logout

1. Triggered by the user clicking Logout, or automatically by `useSessionTimeout` after 30 minutes of inactivity.
2. `supabase.auth.signOut()` clears the session from localStorage.
3. `AuthContext` updates to `user=null`, `isGuest=true`.
4. `BroadcastChannel("auth")` broadcasts the logout event so all open browser tabs sign out simultaneously.

---

## 12. Session Management

Session management is implemented in two layers: Supabase token lifecycle and the application-level inactivity timeout.

### Supabase Token Lifecycle

Supabase issues JWTs with a default expiry of 3600 seconds (1 hour). The Supabase JS SDK automatically uses the refresh token to obtain a new access token before expiry, so active users are never logged out unexpectedly by token expiry alone.

### Inactivity Timeout (30 minutes)

`useSessionTimeout({ isActive: !isGuest, onTimeout })` in `SessionTimeoutHandler.jsx`:

- Only active for authenticated (non-guest) users.
- Monitors 9 browser events: `mousemove`, `mousedown`, `keydown`, `scroll`, `touchstart`, `wheel`, `visibilitychange`, `focus`, `click`.
- Any of these events resets a `setTimeout(onTimeout, 30 * 60 * 1000)` timer.
- When the timer fires, `onTimeout()` is called, which shows `SessionTimeoutModal`.

### SessionTimeoutModal

- Displayed 60 seconds before timeout (the parent component triggers it).
- Shows a countdown and a "Stay Logged In" button.
- "Stay Logged In" resets the inactivity timer.
- If the user does nothing, `supabase.auth.signOut()` is called automatically and they are redirected to `/login`.

### Cross-Tab Logout

When any tab signs out (whether from the timeout or manual logout), a `BroadcastChannel("auth")` message is posted. All other open tabs listening on the same channel immediately call `supabase.auth.signOut()` and update their auth state, ensuring no stale authenticated session remains in any tab.

---

## 13. Chat History Management

### Conversation Lifecycle

1. **Creation**: When an authenticated user sends their first message in a new chat, `_ensure_conversation(user_id, conversation_id=None, question)` calls `create_conversation(user_id, title)`. The title is the first 60 characters of the question. Returns the new conversation row including its UUID.

2. **User message save**: Immediately after creating/resolving the conversation, `save_message(conversation_id, "user", question)` inserts the user's message.

3. **Assistant message save**: After the full pipeline produces `full_answer` (whether from cache or from Gemini/refiner), `save_message(conversation_id, "assistant", full_answer)` inserts the complete final formatted response. This happens whether the pipeline took the cache path or the full retrieval path.

4. **Conversation resume**: When a user opens the history panel and clicks an existing conversation, `loadConversation(id)` calls `GET /conversation/{id}`. The backend validates ownership (`conversation.user_id == authenticated_user_id`) and returns all messages ordered by `created_at`. The frontend maps these to `{ type: "user"|"bot", text: m.content, timestamp: m.created_at }`.

5. **All messages rendered identically**: Whether a message comes from a live stream, cache, or history restore, it always renders through `<ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>{msg.text}</ReactMarkdown>`. The `MD` component map applies consistent heading sizes, table styles, bullet list spacing, and code highlighting. There is no separate raw-text render path for history.

### Guest Behaviour

Guest conversations are stored only in React component state (`messages` array). They are never saved to Supabase. If the page is refreshed, history is lost. When a guest logs in, any accumulated guest messages are transferred to the authenticated session's state via `guestMessagesRef`.

---

## 14. Document Intelligence Layer

### 14.1 PDF Processing Pipeline

The offline pipeline processes PDF documents and builds a searchable FAISS index. It runs via `backend/scripts/build_pdf_index.py` and is separate from the live request pipeline.

**Step 1 — Text Extraction** (`pdf_processing/extract_text.py`): Uses `pypdf` to extract raw text from each page of a PDF. Returns a full-document string with page break markers.

**Step 2 — Text Cleaning** (`pdf_processing/clean_text.py`): Normalises the extracted text by removing header/footer repeats, collapsing excess whitespace, fixing hyphenated line breaks, and removing non-printable characters. Returns clean prose text suitable for chunking.

**Step 3 — Semantic Chunking** (`pdf_processing/chunk_text.py`): Splits clean text into overlapping chunks targeting ~500 words per chunk with ~100-word overlap. Respects paragraph boundaries — never splits mid-paragraph unless a single paragraph exceeds the target. Returns a list of dicts: `{ chunk_id, product_name, document_name, page_number, chunk_text }`. Page numbers are estimated from paragraph position (every ~3 paragraphs ≈ 1 page).

**Step 4 — Embedding and Indexing** (`pdf_processing/embed_chunks.py`): Encodes all chunk texts using `all-MiniLM-L6-v2` (the same model as the product index). Builds an `IndexFlatL2` FAISS index and writes it to `pdf_processing/faiss/pdf.index`. Writes metadata to `pdf_processing/metadata/pdf_metadata.pkl`. Both `build_pdf_index` (rebuild from scratch) and `add_to_pdf_index` (append) functions are available.

### 14.2 FAISS Index Details

**Product index** (`vector_db/faiss_index.bin`):
- 20 vectors (one per product chunk)
- 384 dimensions (all-MiniLM-L6-v2 output)
- IndexFlatL2 (exact search — small enough for brute force)
- Loaded once at module import in `product_search.py`

**PDF index** (`pdf_processing/faiss/pdf.index`):
- 260+ vectors (grows as PDFs are added)
- 384 dimensions
- IndexFlatL2
- Loaded lazily in `pdf_search.py` — absent until `build_pdf_index.py` has run

### 14.3 Offline Search

At runtime, `pdf_search.search(query, top_k=3, matched_product)`:
1. Encodes query with `all-MiniLM-L6-v2`.
2. If `matched_product` given, filters `pdf_metadata` to chunks whose `product_name` fuzzy-matches (substring in either direction).
3. For small candidate pools (≤ top_k): reconstructs vectors from index, computes L2 distances, applies `MAX_PDF_DISTANCE=1.4` threshold.
4. For larger pools: scores all candidates, sorts by distance, applies threshold to top_k.
5. Returns metadata dicts for passing chunks.

### 14.4 Metadata

Each PDF chunk metadata dict contains:
- `chunk_id`: `{product_name}::{document_name}::{N}` — unique identifier
- `product_name`: product this chunk belongs to
- `document_name`: source PDF file name
- `page_number`: estimated 1-based page number
- `chunk_text`: 500-word chunk text with 100-word overlap

This metadata is used in the context builder to create the `📄 PDF Knowledge` section, showing users the document source and page number for each insight.

---

## 15. Dynamic Web Search Pipeline

Dynamic search handles two scenarios: (a) category/general_medical queries that bypass FAISS entirely, and (b) product queries where FAISS returns nothing above threshold.

### DuckDuckGo Search

`duckduckgo_search.search_web(query, max_results=5)`:
1. Appends `"medical device healthcare hospital equipment"` to the user's query.
2. Calls `DDGS().text(search_query, max_results=5)`.
3. Returns a list of strings in the format `"title: body"`.

### Wikipedia Enrichment

`wikipedia_service.fetch(topic)`:
1. Checks in-memory TTL cache (1-hour TTL, 200-entry LRU).
2. Tries exact-title REST summary: `GET https://en.wikipedia.org/api/rest_v1/page/summary/{title}`.
3. If not found (404 / type ends with "not_found"), tries MediaWiki search API and fetches the top result.
4. Cleans the extract: removes `[1]`, `[note X]` reference markers, truncates at last sentence boundary before 600 characters.
5. Returns `WikipediaResult(title, summary, url, found=True/False)`.
6. Caches both found and not-found results to avoid repeat fetches.

Wikipedia guard (`should_use_wikipedia(query, intent)`): only permits Wikipedia when intent is `general_medical_query` AND no known product fragment (pagewriter, tc50, frx, dfm100, etc.) or model-number pattern is in the query. This prevents Wikipedia from injecting generic medical content into product-specific answers.

### `_wiki_summary` Cleaning

Before any web or Wikipedia content reaches a formatter, `_wiki_summary(chunks)` processes all dynamic/wiki chunks with these filtering steps:

1. Strip block headers (`📚 Medical Background`, `🌐 Dynamic Search`, `[Web Search Results]`).
2. Remove `Source:` lines and all URLs/domain names.
3. Strip DuckDuckGo "Title: body" prefixes (multiline regex `^[^:.\n]{3,80}:\s+`).
4. Remove navigation/marketing headings (MedicalExpo, Browse, Filter, Shop, etc.).
5. Strip title-token prepended to first sentence (Wikipedia title line collapsed before sentence split).
6. Collapse whitespace.
7. Sentence-filter: keep only sentences with terminal punctuation, ≥6 words, no URL fragment, not title-case-only ≤7 words.
8. Deduplicate case-insensitively.
9. Return up to 4 clean prose sentences joined with spaces.

---

## 16. Caching Architecture

### Overview

The cache is a persistent semantic store in the `cached_answers` Supabase table. It is designed to serve repeated or semantically similar queries without running the full FAISS + Gemini pipeline.

### Cache Key

Keys are stored as `intent::normalised_question` (e.g. `product_query::what is pagewriter tc50`). Normalisation lowercases and collapses whitespace. The intent prefix prevents cross-intent collisions — a specification query for "TC50 specs" will never hit a product query cache entry for "what is TC50".

### Cache Versioning

`CACHE_VERSION = 2` is defined as a module-level constant. Every new row written to the cache includes `version=2`. On read, the `_semantic_lookup` function filters: `(r.get("version") or 1) == CACHE_VERSION`. Rows without a version column (created before the version column was added) are treated as version 1 and silently skipped. Old rows are never deleted — they age out naturally or can be manually pruned with `DELETE FROM cached_answers WHERE version IS NULL OR version < 2`.

### Semantic Matching

If embeddings are present in the versioned rows:
1. The query is embedded with `all-MiniLM-L6-v2` (384 dimensions, L2-normalised).
2. Each cached embedding is also L2-normalised.
3. Cosine similarity = dot product of two unit vectors.
4. Best score across all versioned rows is compared to `SIMILARITY_THRESHOLD = 0.90`.
5. Additionally, a product token conflict check prevents TC50 queries hitting TC35 cached answers: both query and cached question are scanned for known product tokens (`tc50`, `tc35`, `frx`, `hs1`, etc.), and if they differ, the row is skipped.

### Cache Write Guard (`_is_formatted`)

Before any answer is written to cache, `_is_formatted(answer)` checks:
- Length ≥ 100 characters
- No fallback fragment present
- No raw output marker present: `product name:`, `category:`, `[web search results]`, `🌐 dynamic search\n\n`, `📄 pdf knowledge\n\n`, `📚 medical background\n\n`

This ensures the cache never stores raw FAISS chunks, raw web search snippets, PDF text, or partially formatted responses — only final validated markdown.

### Cache Logging

Every cache event emits a structured log block:
```
╔══ [CACHE] ══════════════════════════════════════════
║  STATUS   : HIT / MISS / DISABLED / STORED / SKIPPED
║  VERSION  : 2
║  QUESTION : normalised question text
║  KEY      : intent::normalised_question
║  SOURCE   : cache / pipeline
║  NOTE     : reason (if SKIPPED or DISABLED)
╚═════════════════════════════════════════════════════
```

---


## 17. Contact Support Workflow

The contact form is available from two entry points: the standalone `/contact` page (`ContactPage.jsx`) and an inline popup within the chatbot triggered by purchase intent, sample report intent, or out-of-scope responses.

### Inline Contact Form (FloatingChatbot)

When the user triggers a purchase intent, sample report, or OOS canned reply, a "Fill Contact Form" or "Contact Support" button appears attached to that message. Clicking it opens `ContactFormInline` in an animated bottom-sheet overlay (`framer-motion`).

The form collects: **Name**, **Email**, **Message**.

On submit:
1. Validates all fields are non-empty.
2. `POST /contact` with `{ name, email, message }`.
3. Backend `send_email(name, email, message)` uses Gmail SMTP (configured via `EMAIL_USER` and `EMAIL_PASSWORD` env vars) to send the message to the support inbox.
4. On success: green confirmation banner `"✅ Query submitted successfully. We'll get back to you shortly!"`.
5. On failure: red error banner with fallback email address.

### Standalone Contact Page

`ContactPage.jsx` contains the full `ContactForm.jsx` component with the same backend integration. Used for general enquiries not triggered by chatbot intent guards.

---

## 18. Secure Document Download Workflow

### Overview

The document download system is a 5-step security chain: rate limiting → identity collection → OTP verification → single-use token issuance → server-side file proxy. Raw Supabase Storage URLs are never exposed to the browser at any point.

### Step 1 — Document Discovery

Users browse documents through `ResourcesPage.jsx`. The page calls:
- `GET /documents/categories` → returns distinct category names from `device_documents`.
- `GET /documents/subcategories/{category}` → returns subcategory names for a category.
- `GET /documents/list?category=X&subcategory=Y` → returns document rows (id, product_name, document_name, document_type, file_url NOT included — only metadata).

Additionally, when the chatbot matches a product, it calls `GET` on the matched product and appends document cards to the bot response.

### Step 2 — Rate Limit Enforcement

`POST /download/request` begins with `check_download_limit(user_id)`:
- If `user_id is None` (guest) → raises `ValueError("Guest users cannot download documents. Please sign in.")`
- Queries `document_download_requests` WHERE `user_id=X AND otp_verified=true AND downloaded=true AND downloaded_at >= now()-24h`.
- If any row found → raises `ValueError("You have reached today's download limit. Please try again after 24 hours.")`.
- Only completed downloads (otp_verified=true AND downloaded=true) count against the limit. Abandoned requests (OTP never entered) do not consume quota.

### Step 3 — OTP Generation and Email

After rate limit passes:
1. `_generate_otp()` → 6 random decimal digits using `random.choices(string.digits, k=6)`.
2. `_expiry_ts(5)` → `datetime.now(UTC) + timedelta(minutes=5)`.isoformat().
3. INSERT row into `document_download_requests` with all form fields and OTP state.
4. `_send_otp_email(email, full_name, otp, document_name)` → SMTP STARTTLS on port 587 to `smtp.gmail.com`.

Email subject: `"Your Download Verification Code — {document_name}"`.
Email body includes the 6-digit code and a 5-minute validity notice.

### Step 4 — OTP Verification

`POST /download/verify { request_id, otp }`:
1. Fetch request row by UUID.
2. If already `otp_verified=true` → issue a fresh serve token (idempotent re-verify).
3. Check `_is_expired(otp_expiry)` → parses timestamptz with `dateutil.parser`, handles timezone-naive strings.
4. Compare `otp_code == otp_entered.strip()`.
5. On match: UPDATE `otp_verified=true, downloaded=true, downloaded_at=now()`.
6. Call `_generate_serve_token(request_id)`:
   - `raw_token = secrets.token_urlsafe(32)` → 256-bit cryptographically random URL-safe string.
   - `token_hash = hmac.new(_TOKEN_SECRET, raw_token, sha256).hexdigest()`.
   - INSERT into `secure_download_tokens`: `{ request_id, token_hash, expires_at=now()+15min, used=false }`.
   - Returns `raw_token` — the hash is in the DB, not the raw token.
7. Returns `{ verified: true, serve_url: "/download/serve/<raw_token>" }`.

### Step 5 — Token Consumption and File Serving

`GET /download/serve/{token}`:
1. Compute `token_hash = HMAC-SHA256(secret, token)`.
2. SELECT from `secure_download_tokens WHERE token_hash=hash`. If not found → 401.
3. Check `used=true` → 401 "This download link has already been used."
4. Check `_is_expired(expires_at)` → 401 "This download link has expired."
5. UPDATE `used=true, used_at=now()` **atomically before fetching the file** to prevent race-condition double-use.
6. Fetch linked `document_download_requests` row for `file_url` and `document_name`.
7. `httpx.AsyncClient().get(file_url, timeout=30)` → fetches bytes from Supabase Storage server-side.
8. Returns `Response(content=file_bytes, media_type="application/pdf")` with:
   - `Content-Disposition: attachment; filename="<safe_name>.pdf"` (filename sanitised, path separators stripped, max 120 chars)
   - `Cache-Control: no-store, no-cache, must-revalidate, private`
   - `X-Content-Type-Options: nosniff`

### OTP Resend

`POST /download/resend { request_id }`:
- Fetches request row, checks `otp_verified` (if already verified → error).
- Checks `resend_count >= MAX_RESENDS (3)` → error if limit reached.
- Generates new OTP and new expiry.
- UPDATE `otp_code, otp_expiry, resend_count++`.
- Sends new OTP email.
- Returns `{ email: masked_email }`.

---

## 19. Current Features

### Chatbot Features
- Natural language question answering about Philips medical devices
- Seven intent types: product overview, features, specifications, comparison, category listing, general medical concepts, dynamic web search
- Real-time token-by-token SSE streaming with markdown preservation
- Standardised emoji-headed response format for all intents
- Voice input via Web Speech API
- Message copy, thumbs-up/down feedback, and regenerate (last bot message)
- Source badge on every response (📦 Knowledge Base, 🌐 Web, ⚡ Cached)
- Suggested questions chip bar, category-aware
- Device category selector (Cardiology, PatientMonitoring, Anaesthesia, OTComplex, MotherChildCare)

### Retrieval Features
- FAISS semantic search over 20 product chunks
- BM25 keyword search fused with FAISS via Reciprocal Rank Fusion
- CrossEncoder second-pass reranking (top 5 from up to 20 candidates)
- Query rewriting: filler stripping, abbreviation expansion, retrieval variants
- Exact product name match (confidence=1.0, bypasses reranking)
- Comparison split-and-retrieve with brand prefix enrichment
- Confidence gate: drops low-confidence wrong-product FAISS matches
- PDF knowledge integration: product-scoped FAISS search over 260+ PDF chunks
- DuckDuckGo web search fallback for general medical queries
- Wikipedia enrichment for unknown medical concepts
- Dynamic search cleaning: strips DuckDuckGo title prefixes, URLs, MedicalExpo headings

### Response Quality Features
- Deterministic response_refiner always produces a base answer before Gemini
- Response validator with 9 structural checks per intent type
- Validator retry: builds fresh context and re-runs refiner on failure
- Gemini structural guards (comparison, specification, general_medical) before Gemini output is used
- Context cleaner: noise removal, structural label preservation, cross-chunk deduplication
- SSE newline encoding/decoding to preserve markdown spacing through the SSE wire format

### Authentication Features
- Email/password registration via Supabase Auth
- JWT-based API authentication on all protected endpoints
- Guest mode (no registration required) with localStorage-based guest UUID
- 30-minute inactivity session timeout with 60-second warning modal
- Cross-tab logout via BroadcastChannel

### Chat History Features
- Persistent conversation storage per authenticated user
- Conversation list panel with titles and timestamps
- Resume any past conversation by clicking in the history panel
- All history messages rendered with the same ReactMarkdown formatter as live responses
- Guest message preservation on login (state-level transfer)

### Document Library Features
- Hierarchical category → subcategory → document browser
- Product-linked document cards appear in chatbot responses after product queries
- Document preview via inline PDF iframe
- Secure OTP-verified download with rate limiting (1 per 24 hours per user)
- Guest download blocked (sign-in required)

### Security Features (see Section 20 for full detail)
- JWT authentication on all user-facing endpoints
- OTP verification for document downloads
- Single-use HMAC-signed serve tokens (15-minute expiry)
- Raw storage URLs never exposed to the client
- Download rate limiting (1 per authenticated user per 24 hours)
- Guests cannot download documents

### Personalisation Features
- Preferred category stored in `user_preferences` and restored on next session
- "Last browsed" banner for returning users with category resume button
- Preferred category saved automatically when a category is matched in a response

### Guard Features (client and server mirrored)
- Purchase intent guard: price, quote, demo, dealer, buy, order keywords → canned reply
- Sample report intent guard: sample ECG, example report, PDF output requests → canned reply (not cached)
- Out-of-scope guard: programming, sports, movies, politics, general trivia → canned reply
- Medical query guard: prevents non-medical queries reaching DuckDuckGo/Wikipedia
- Canned replies show contextual action buttons (Fill Contact Form, Contact Support)

---

## 20. Security Features

### API Authentication
Every endpoint that accesses user data (`/history`, `/conversation`, `/preferences`, `/download/*`) requires a valid Supabase JWT. The backend validates the token on every request using `supabase.auth.get_user(token)`. Invalid, expired, or missing tokens return HTTP 401.

### Endpoint Ownership Enforcement
History and conversation endpoints verify `authenticated_user_id == resource.user_id` before returning data. A user cannot access another user's conversations or preferences — HTTP 403 is returned on mismatch.

### Download Security
- Guest users are blocked from all download operations.
- OTP expires in 5 minutes; re-verification generates a fresh OTP.
- Maximum 3 OTP resends per request record.
- Serve tokens are 256-bit random values; only their HMAC-SHA256 hash is stored in the database.
- Tokens are single-use: marked `used=true` before file bytes are fetched (atomic — prevents race-condition double-use).
- Tokens expire in 15 minutes.
- Raw Supabase Storage URLs are never sent to the browser — the backend proxies all file bytes.
- File names are sanitised: path separators stripped, truncated to 120 characters.
- Response headers include `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.

### Rate Limiting
One completed download (otp_verified=true AND downloaded=true) per authenticated user per 24-hour window. The partial-index `idx_ddr_user_downloads_24h` makes this check sub-millisecond even with large tables.

### Input Validation
All request bodies are validated by Pydantic models before any handler logic runs. FastAPI automatically returns HTTP 422 for malformed requests.

### Row Level Security (Supabase)
RLS policies on `user_preferences`, `document_download_requests`: authenticated users can only read their own rows. Service role (used by the backend) bypasses RLS. `secure_download_tokens` is accessible only to the service role — anon and authenticated roles have zero direct access.

### Environment Secret Management
All secrets (Gemini API keys, Supabase URL/keys, email credentials, download token secret) are loaded from `.env` via `python-dotenv`. The `.env` file is in `.gitignore` and is never committed to version control.

### Session Security
- 30-minute inactivity auto-logout prevents abandoned authenticated sessions.
- BroadcastChannel cross-tab logout ensures all tabs sign out simultaneously.
- Supabase refresh tokens are rotated automatically by the JS SDK.

---

## 21. APIs

All backend endpoints are served by FastAPI at the base URL configured in `API_BASE_URL` (default: `http://127.0.0.1:8000`).

### Chat Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/chat` | Optional | Non-streaming chat. Runs full pipeline, returns `ChatResponse` with complete answer. |
| POST | `/chat/stream` | Optional | Streaming chat via SSE. Yields response tokens with `data: <token>\n\n` events. Final event is `data: [META]{json}\n\n` with source, product, category, confidence, documents, conversation_id. |

### History Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/history/{user_id}` | Required | Returns list of conversations for the authenticated user (id, title, created_at). Validates user_id matches authenticated user. |
| GET | `/conversation/{conversation_id}` | Required | Returns all messages in a conversation (sender, content, created_at). Validates conversation belongs to authenticated user. |

### Document Library Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/documents/categories` | None | Returns distinct active category names from `device_documents`. |
| GET | `/documents/subcategories/{category}` | None | Returns distinct active subcategory names for a category. |
| GET | `/documents/list` | None | Returns document rows for a given category+subcategory. Query params: `category`, `subcategory`. |

### Secure Download Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/download/request` | Required | Create download request, generate OTP, send email. Body: `DownloadRequestBody`. Returns `{ request_id, email }`. |
| POST | `/download/verify` | None | Verify OTP, issue single-use serve token. Body: `{ request_id, otp }`. Returns `{ verified, serve_url }`. |
| POST | `/download/resend` | None | Resend OTP (max 3 times). Body: `{ request_id }`. Returns `{ email }`. |
| GET | `/download/serve/{token}` | None | Consume serve token, proxy file bytes from Supabase Storage. Returns `application/pdf` with attachment disposition. |

### User Preferences Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/preferences/{user_id}` | Required | Retrieve user's preferences (preferred_category, recent_products, favorite_products, last_active). |
| POST | `/preferences/{user_id}` | Required | Upsert user preferences. Body: `UserPreferencesBody`. Returns updated `UserPreferencesResponse`. |

### Contact Endpoint

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/contact` | None | Send contact form email via Gmail SMTP. Body: `{ name, email, message }`. Returns `{ message: "Email sent successfully" }`. |

---


## 22. Major Challenges Faced

### Challenge 1 — Wrong Product Mappings from FAISS
FAISS semantic search returns the nearest-embedding chunk even when the query is about a device not in the knowledge base. Queries like "Tell me about Infusion Pump" returned the Efficia DFM100 because "infusion" and "patient monitoring" share embedding space with that product. Similarly, "Holter Monitor" mapped to PageWriter TC50 due to shared ECG/cardiac vocabulary, and "Bubble CPAP" mapped to Oscar 2 due to shared neonatal/clinical vocabulary.

### Challenge 2 — Raw Context Leaking into Responses
In early pipeline versions, raw FAISS chunk text (containing `Product Name: X`, `Category: Y`, `Description:` headers) was being injected directly into the response when Gemini failed or returned an empty answer. This produced responses like `Product Name: PageWriter TC50Category: CardiologyDescription: A device...` with no formatting.

### Challenge 3 — SSE Newline Collapse
Server-Sent Events use bare `\n` as an event delimiter. Gemini tokens containing markdown section breaks (`\n\n`) were being consumed by the SSE parser as event separators and silently dropped. This caused all markdown sections to concatenate into a single line: `📦 PageWriter TC50CardiologyOverview...`

### Challenge 4 — Stale Cache Returning Old Malformed Responses
Cache entries written during earlier pipeline versions (before the formatter standardisation) contained raw text, tables, or incorrectly structured output. These entries were being served to users even after the pipeline was fixed, because there was no mechanism to distinguish old from new cache entries.

### Challenge 5 — Context Cleaner Joining Lines with Spaces
An early version of `context_cleaner.py` joined kept lines with `" "` (space) instead of `"\n"` (newline). This caused structured section headers to concatenate with values: `ProductPageWriter TC50CategoryCardiologySummary...`. The resulting context broke all regex parsers in `response_refiner.py`.

### Challenge 6 — Comparison Queries with Bare Model Numbers
A query like "Compare TC50 and TC70" failed because FAISS was given "TC70" as a standalone search string. The embedding for a 4-character token has very low specificity and FAISS returned unrelated products. The product name normalization did not handle the case where one side of the comparison was a bare model suffix without the brand prefix.

### Challenge 7 — Gemini Structural Inconsistency
Gemini occasionally ignored the structured output instructions in the prompt and returned raw prose descriptions instead of the required markdown format (tables for specifications, section headers for comparisons, `🏥` heading for general medical). This caused incorrect formatting to reach the frontend.

### Challenge 8 — DuckDuckGo Snippet Pollution
DuckDuckGo returns results as `"Title: body"` strings. Titles like `"ECG machine"`, `"MedicalExpo"`, `"PageWriter TC50: Find and compare..."` leaked directly into responses. The old `_wiki_summary` used a regex that only stripped capitalised prefixes — it missed lowercase titles, domain names, and navigation headings.

### Challenge 9 — duplicate `_format_product_chunk` Definitions
The chunk formatting function was defined inline inside both `/chat` and `/chat/stream` handler bodies, plus a third time inside the validator retry block. A change to the format required updating three separate copies, and any mismatch caused inconsistent context between the streaming and non-streaming paths.

### Challenge 10 — Session Persistence and Cross-Tab Logout
Guest messages were lost on login because the guest state was cleared before the authenticated state was available. Cross-tab logout was not implemented, leaving stale authenticated sessions open in background tabs after a manual logout.

---

## 23. Solutions Implemented

### Solution 1 — Intent Routing + Confidence Gate
Added Holter Monitor, Bubble CPAP, Infusion Pump, Syringe Pump to `_GENERAL_MEDICAL_TERMS` in `intent_detector.py`. These queries now route to `general_medical_query` and use Wikipedia/web search instead of FAISS. Added a concept-trigger gate for generic device terms ("tell me about ECG" without a model number) that routes to `general_medical_query`. Added a confidence gate in `orchestrator.py`: when FAISS confidence < 0.97 AND the matched product name does not appear in the original query text, the result is discarded and falls through to dynamic search.

### Solution 2 — Response Refiner as Guaranteed Base
The `response_refiner.refine()` function now always runs first before Gemini and produces `base_answer` from deterministic regex parsing. Gemini is only an optional polish layer. The `response_validator` rejects any Gemini output that fails structural checks and the validator retry path re-runs the refiner with fresh context. This ensures raw context can never reach the frontend.

### Solution 3 — SSE Newline Encoding
Introduced `_sse_encode(token)` in `app.py`: replaces `\n` with `\n` (the two-character backslash-n literal) before every `yield f"data: {encoded}\n\n"`. The frontend SSE reader decodes with `data.replace(/\\n/g, "\n")` before accumulating tokens. This preserves all markdown section breaks through the SSE wire format.

### Solution 4 — Cache Versioning
Added `CACHE_VERSION=2` to `cache_service.py`. All new cache writes include `version=2`. All cache reads filter by `(version or 1) == CACHE_VERSION`. Old rows (version 1 or NULL) are silently skipped and never deleted. Added `_is_formatted()` guard that rejects raw FAISS chunks, web snippets, PDF headers, and fallback messages before any write.

### Solution 5 — Context Cleaner Line Joining Fix
Changed `context_cleaner.py` to join kept lines with `"\n"` instead of `" "`. Added the invariant comment: "Joining lines with ' ' produces 'ProductPageWriterTC35Category...' which is the bug this module exists to fix." Added special handling to always preserve structural labels (Product, Category, Summary, Features, Specifications) from deduplication.

### Solution 6 — Comparison Side Enrichment
Added `_enrich_comparison_sides(left, right)` in `product_search.py`. When one side is a bare model number (≤12 chars, no spaces) and the other has a brand prefix (e.g. "pagewriter"), the brand prefix is prepended to the bare side: "TC70" becomes "PageWriter TC70". This gives FAISS enough signal to find the correct product.

### Solution 7 — Gemini Structural Guards
Added per-intent validation guards in both `gemini_service.py` (non-streaming) and the streaming buffer path. For comparison: requires `###` section headers or `|` table rows. For specification: requires `•` bullets, `|` table, or "unavailable" message. For general_medical: requires `🏥` emoji or ≥2 known section headers. If the guard fails, `base_answer` from the refiner is returned instead.

### Solution 8 — Multi-Layer DuckDuckGo Cleaning
Rewrote `_wiki_summary()` in `response_refiner.py` with layered noise filtering: (1) strip `Source:` and URL lines, (2) strip DuckDuckGo "Title: body" prefixes using a multiline regex for any-case titles, (3) remove navigation/marketing headings, (4) strip bare domain names, (5) collapse whitespace, (6) strip stray Wikipedia title tokens prepended to first sentence, (7) sentence-filter requiring terminal punctuation and ≥6 words, (8) case-insensitive deduplication.

### Solution 9 — Shared Module-Level Helpers
Extracted `_format_product_chunk`, `_build_combined_context`, `_build_retry_context`, and `_sse_encode` as module-level functions in `app.py`. Both `/chat` and `/chat/stream` handlers call these identically. The validator retry path uses `_build_retry_context`. There is now exactly one definition of each function, verified by AST assertion in tests.

### Solution 10 — Guest Message Preservation and Cross-Tab Logout
Implemented `guestMessagesRef` to buffer guest messages. When a guest logs in, `useEffect([user.id])` detects the new authenticated user and transfers buffered messages to the main `messages` state. Implemented `BroadcastChannel("auth")` in `SessionTimeoutHandler.jsx` to broadcast logout events across all open tabs simultaneously.

---

## 24. Future Enhancements

### Retrieval and Knowledge Base
- **Expand the product catalog**: Currently 12 products / 20 FAISS chunks. Adding more devices (Efficia CM series, IntelliBridge, SureSigns) would require re-running `create_embeddings.py` with updated product data.
- **Multi-turn conversation context**: Pass the last 2–3 messages as context to Gemini so follow-up questions like "What about its battery life?" resolve correctly without the user repeating the product name.
- **Hybrid re-indexing pipeline**: Automate nightly re-indexing when new products or documents are added to Supabase Storage.
- **Real Philips product scraper**: Replace the current static JSON with a scheduled scraper that keeps the knowledge base current.

### Response Quality
- **Multi-document comparison**: Current comparison handles exactly 2 products. Extend to 3-way comparisons.
- **Structured specification tables**: Optionally re-enable markdown tables for specification queries on wider screens.
- **Confidence score display**: Show users the retrieval confidence badge (high / medium / web fallback) alongside the source badge.

### Authentication and User Experience
- **OAuth providers**: Add Google and Microsoft OAuth login via Supabase Auth providers.
- **Magic link login**: Email-only authentication for users who prefer not to manage passwords.
- **Conversation search**: Allow authenticated users to search across their conversation history.
- **Conversation export**: Export a conversation as PDF or Markdown.

### Document System
- **Bulk download**: Allow downloading multiple documents as a ZIP archive after a single OTP verification.
- **Document preview without download**: Stream PDF pages as images to allow in-app reading without triggering the download quota.
- **Email notification on document added**: Notify subscribed users when a new document is published for a product they have viewed.

### Performance and Scalability
- **Redis cache**: Replace the Supabase-table semantic cache with a Redis vector store for sub-millisecond cache lookups at scale.
- **Horizontal scaling**: Deploy multiple Uvicorn workers behind a load balancer; the Supabase-based cache is already shared-state safe.
- **Streaming from PDF index**: Add server-sent streaming for PDF-heavy responses to match the product query streaming experience.

### Analytics
- **Search analytics dashboard**: Log and visualise which products are most queried, which queries result in cache misses, and which intents are most frequent.
- **Feedback collection**: Store thumbs-up/thumbs-down feedback in Supabase and use it to tune reranker thresholds.

---

## 25. Project Statistics

| Metric | Count |
|---|---|
| Backend Python files | ~30 (app.py, 5 search modules, 2 pipeline modules, 3 dynamic_search modules, 4 pdf_processing modules, 8 service/utility modules, 3 script files) |
| Frontend React files | ~30 (15 components, 10 pages, 3 lib files, 2 context/hook files) |
| REST API endpoints | 14 (2 chat, 2 history, 3 documents, 4 download, 2 preferences, 1 contact) |
| Supabase database tables | 8 (auth.users managed by Supabase, conversations, messages, cached_answers, device_documents, document_download_requests, secure_download_tokens, user_preferences) |
| AI/ML modules | 7 (intent_detector, gemini_service, response_refiner, cache_service with embeddings, hybrid_search with RRF, reranker CrossEncoder, wikipedia_service) |
| Response intent formatters | 7 (format_product, format_features, format_specifications, format_comparison, format_category, format_general_medical, format_dynamic) |
| FAISS product chunks | 20 (12 unique products) |
| FAISS PDF chunks | 260+ (grows with each indexed document) |
| Implemented features | 40+ (see Section 19) |
| SQL migration files | 4 (main migration, indexes migration, Phase 5.4 tokens, Phase 5.5 rate-limit index) |
| Lines of backend code | ~4,500 |
| Lines of frontend code | ~3,500 |

---

## 26. Development Phases

### Phase 1 — Foundation

**Objective**: Build the minimum viable chatbot that could answer basic questions about Philips medical devices.

**What was built**:
- Initial React frontend with a basic chat interface.
- FastAPI backend with a single `/chat` endpoint.
- Product knowledge base created by scraping 12 Philips medical device pages from MedicalExpo using Playwright. Scraped data included product name, category, description, features, and specifications.
- FAISS index built using `all-MiniLM-L6-v2` sentence transformer embeddings over 20 product chunks.
- Google Gemini API integration (initial version) with a single generic prompt.
- Basic product query answering: FAISS retrieval → Gemini → plain text response.
- Static product data stored in `products.json` and `products_cleaned.json`.
- No authentication, no history, no streaming, no caching.

**Outcome**: A working prototype that could answer "What is PageWriter TC50?" and similar direct product questions, but with no structure, no formatting consistency, and no quality controls.

---

### Phase 2 — Intelligence Layer

**Objective**: Improve retrieval accuracy, add multiple intent types, and produce structured responses.

**What was built**:
- `intent_detector.py`: Pure Python keyword/regex classifier supporting 6 intent types (product_query, feature_query, specification_query, comparison_query, category_query, general_medical_query).
- `query_rewriter.py`: Filler stripping, abbreviation expansion, multi-query variants.
- BM25 keyword search (`search/bm25_index.py`) and Reciprocal Rank Fusion with FAISS (`search/hybrid_search.py`).
- CrossEncoder reranker (`search/reranker.py`) with lazy model loading.
- `response_refiner.py`: First version of the deterministic formatter with intent-specific formatting functions.
- `pipeline/context_cleaner.py`: Noise removal with structural label preservation.
- `pipeline/response_validator.py`: Gemini output validation with 9 structural checks.
- `search/query_rewriter.py`: Canonicalisation and variant generation.
- Comparison query split-and-retrieve with brand prefix enrichment.
- Dynamic search pipeline: DuckDuckGo DDGS + Wikipedia REST API + `wikipedia_guard.py`.
- Intent-specific Gemini prompt templates (7 variants).
- Gemini key rotation across two API keys with quota handling.

**Outcome**: The chatbot correctly distinguished between "what is TC50" (product_query), "features of TC50" (feature_query), and "compare TC50 and TC35" (comparison_query). Retrieval accuracy improved significantly with RRF and reranking. General medical questions ("what is an ECG") were answered from Wikipedia rather than hallucinated by Gemini.

---

### Phase 3 — Streaming and Document Intelligence

**Objective**: Add real-time streaming responses and integrate the PDF knowledge base.

**What was built**:
- `POST /chat/stream` endpoint with Server-Sent Events streaming via `generate_answer_streaming()`.
- `StreamingResponse` in FastAPI with `text/event-stream` media type.
- `generate_answer_streaming()` async generator in `gemini_service.py` with streaming token emission.
- Structure-required intent buffering in streaming path (comparison, specification, general_medical fully buffered before structural check).
- PDF processing pipeline: `extract_text.py` (pypdf), `clean_text.py`, `chunk_text.py` (500-word semantic chunks, 100-word overlap), `embed_chunks.py` (dedicated PDF FAISS index).
- `search/pdf_search.py`: product-scoped PDF FAISS search with per-chunk distance threshold.
- PDF highlights extraction in context builder using `_extract_bullets` scoring heuristic.
- Document library frontend: `ResourcesPage.jsx` with category → subcategory → document hierarchy.
- `device_documents` Supabase table and `document_service.py`.
- Document cards attached to chatbot responses for matched products.

**Outcome**: Responses streamed token by token for a typing-effect UX. PDF datasheets were indexed and searchable — questions like "What does the PageWriter TC50 datasheet say about battery life?" returned answers grounded in the actual document content with source attribution (document name and page number).

---

### Phase 4 — Authentication and Chat History

**Objective**: Add user accounts, persistent conversation history, and personalisation.

**What was built**:
- Supabase Auth integration: `Register.jsx`, `Login.jsx`, `AuthContext.jsx`.
- JWT-based API authentication on all protected endpoints (`_get_authenticated_user_id`).
- Guest mode with localStorage UUID (`guestSession.js`).
- `chat_history.py`: `create_conversation`, `save_message`, `get_user_conversations`, `get_conversation_messages`.
- Conversation management in `FloatingChatbot.jsx`: history panel, loadConversation, conversation resume.
- `GET /history/{user_id}` and `GET /conversation/{conversation_id}` endpoints.
- `user_preferences` table and `/preferences` CRUD endpoints.
- Preferred category persistence and restoration on next session.
- "Last browsed" banner for returning users.
- Guest message preservation on login via `guestMessagesRef`.
- `useSessionTimeout.js`: 30-minute inactivity timer.
- `SessionTimeoutModal.jsx` and `SessionTimeoutHandler.jsx`.
- Cross-tab logout via `BroadcastChannel`.
- Supabase database migration: conversations, messages, user_preferences tables with RLS policies.
- Index migration: pgvector extension, IVFFlat index on cached_answers, all performance indexes.

**Outcome**: Authenticated users could sign in, ask questions, close the browser, and resume their exact conversation later. The history panel showed all past conversations with titles. Guest users could still use the chatbot without signing in. Sessions auto-expired after 30 minutes of inactivity.

---

### Phase 5 — Security, Quality, and Polish

Phase 5 was delivered in five sub-phases:

**Phase 5.1 — Purchase Intent and Out-of-Scope Guards**:
- `is_purchase_intent()` and `is_out_of_scope()` guards in `intent_detector.py` with mirrored client-side detectors in `lib/purchaseIntentDetector.js` and `lib/outOfScopeDetector.js`.
- Purchase intent and OOS queries return canned replies with "Contact Support" / "Fill Contact Form" action buttons.
- Both guards short-circuit before cache, FAISS, BM25, and Gemini.
- `is_medical_query()` gate prevents non-medical queries reaching DuckDuckGo.

**Phase 5.2 — Semantic Cache**:
- `cached_answers` table with `embedding vector(384)` column.
- Semantic similarity matching with cosine similarity threshold 0.90.
- Product token conflict prevention.
- Quality gate: minimum length, fallback detection.
- Structured cache logging.

**Phase 5.3 — Secure Document Download**:
- `document_download_requests` and `secure_download_tokens` tables.
- `download_service.py`: full OTP pipeline with HMAC-SHA256 serve tokens.
- `DownloadModal.jsx`: 3-step wizard (identity form → OTP → success).
- `/download/request`, `/download/verify`, `/download/resend`, `/download/serve/{token}` endpoints.
- Raw storage URL never sent to client; all file bytes proxied server-side.

**Phase 5.4 — Sample Report Intent and Rate Limiting**:
- `is_sample_report_intent()` guard with mirrored client-side detector.
- Sample report canned reply with contact form button. Not cached.
- `check_download_limit()`: 1 download per authenticated user per 24 hours.
- Partial index `idx_ddr_user_downloads_24h` for sub-millisecond rate-limit check.
- Guest download block.

**Phase 5.5 — Pipeline Unification and Response Formatting**:
- Extracted shared module-level pipeline helpers to eliminate triple-duplication of `_format_product_chunk`.
- `_sse_encode`/decode for SSE newline preservation (fixes markdown spacing collapse bug).
- `CACHE_VERSION=2` with `_is_formatted()` raw-output guard.
- All 6 intent formatters standardised with emoji headers (`📦`, `✨`, `📋`, `📊`, `🏥`, `🌐`).
- `response_validator` and `gemini_service` guards updated to match new formatter output.
- Intent routing fixes: Holter, Bubble CPAP, Infusion Pump → general_medical; concept-trigger gate for ECG/defibrillator; confidence gate for wrong-product FAISS matches.
- Multi-layer DuckDuckGo snippet cleaning in `_wiki_summary`.
- `format_dynamic` rewritten with `🌐 Web Information` / `### Summary` / `### Key Points` / `### Clinical Relevance` structure.

**Outcome after Phase 5**: The system handles all edge cases gracefully. No raw text leaks to the frontend in any scenario. Cache always serves correctly formatted responses. Streaming markdown preserves spacing. Wrong-product FAISS matches are dropped. Documents can only be downloaded by authenticated users who have completed OTP verification, with one download per day enforced at the database level. All security features are tested and verified.

---

*End of Technical Documentation*
*Last updated: July 2026*
*Version: Phase 5.5 complete*
