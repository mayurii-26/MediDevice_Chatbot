# MediDevice Chatbot — Technical Development Documentation

> Covers every major implementation stage from the Landing Webpage through to the Final Production Pipeline.
> Written for internship documentation and future project maintenance.

---

# Stage 1 — Landing Webpage + Floating Chatbot

## 1. How was it implemented?

The frontend is a React single-page application (SPA). The landing page contains multiple marketing sections — Hero, Featured Products, Services, Testimonials, Stats, Why Choose Us, and Footer — all composed as individual React components and assembled in `App.js`.

The chatbot itself is a **floating widget** that sits on top of every page. It is always visible as a small button in the bottom-right corner. When clicked, it expands into a chat panel.

**Workflow:**

1. User opens the website → `App.js` renders the landing page components.
2. `FloatingChatbot.jsx` is mounted globally alongside all pages.
3. User types a question → frontend sends a `POST /chat` request to the FastAPI backend.
4. FastAPI receives the question, runs a FAISS vector search to retrieve the most relevant product chunks, passes them to Gemini, and returns a text answer.
5. The answer is displayed inside the chat panel.

**Why:**
The floating widget pattern lets users ask questions without navigating away from the page they are browsing.

---

## 2. New Tech Stack / Libraries Added

| Technology | Why |
|---|---|
| **React** | Component-based UI framework for the landing page and chatbot |
| **FastAPI** | Python async web framework for the backend API |
| **FAISS** | Facebook AI Similarity Search — stores product chunk embeddings and retrieves the closest matches |
| **SentenceTransformers** (`all-MiniLM-L6-v2`) | Converts text to 384-dimensional vectors for semantic search |
| **Google Gemini API** | Generates natural-language answers from retrieved product context |
| **python-dotenv** | Loads API keys from `.env` without hardcoding them |

---

## 3. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `backend/app.py` | Main FastAPI application — defines the `/chat` endpoint |
| `backend/gemini_service.py` | Calls Gemini API with intent-specific prompts |
| `backend/models.py` | Pydantic request/response models (`ChatRequest`, `ChatResponse`) |
| `backend/vector_db/create_embeddings.py` | Script to encode product chunks and build FAISS index |
| `backend/vector_db/faiss_index.bin` | Serialised FAISS index (generated once, loaded at startup) |
| `backend/vector_db/product_chunks.pkl` | Serialised list of product text chunks |
| `backend/search.py` | Original simple FAISS search helper |
| `backend/logger.py` | Writes search events to `backend/logs/search_logs.txt` |
| `frontend/src/App.js` | Root React component, assembles all page sections |
| `frontend/src/components/FloatingChatbot.jsx` | The floating chat widget |
| `frontend/src/components/Hero.jsx` | Hero section |
| `frontend/src/components/FeaturedProducts.jsx` | Product showcase section |
| `frontend/src/components/Footer.jsx` | Page footer |
| `frontend/src/components/Navbar.jsx` | Top navigation bar |
| `frontend/src/components/Testimonials.jsx` | Customer testimonials section |
| `frontend/src/components/StatsSection.jsx` | Statistics display section |
| `frontend/src/components/ServicesSection.jsx` | Services overview section |
| `frontend/src/components/WhyChooseUs.jsx` | Value proposition section |
| `frontend/src/data/questions.js` | Pre-defined suggested questions for the chatbot |
| `frontend/src/components/SuggestedQuestions.jsx` | Renders suggested question chips |

---

## 4. Architecture after this Stage

```
User
 │
 ▼
React Landing Page (FloatingChatbot always visible)
 │
 ▼  POST /chat
FastAPI (app.py)
 │
 ▼
FAISS Vector Search  ←  faiss_index.bin + product_chunks.pkl
 │
 ▼
Gemini API  ←  Product context
 │
 ▼
ChatResponse → Frontend → Chat Panel
```

---
---

# Stage 2 — Guest Mode + User Sign-in

## 1. How was it implemented?

Two types of users were introduced: **Guests** and **Authenticated Users**.

**Guest Mode:**
- Any visitor who has not signed in is a guest.
- A unique `guest_session_id` is generated on the client using `uuid` and stored in `sessionStorage` (not `localStorage`) so it disappears when the browser tab closes.
- Guests can use the chatbot fully but their conversations are **never saved** to the database.
- The backend receives no `Authorization` header for guest requests — it treats them as anonymous.

**Authenticated User Mode:**
- Users register via `/register` (email + password) or sign in via `/login`.
- Supabase Auth handles password hashing, JWT generation, and session management.
- After sign-in, the frontend stores the Supabase JWT in memory (via React Context) and sends it as a `Bearer` token in every request.
- The backend verifies the token by calling `supabase.auth.get_user(token)`, extracts the `user_id`, and links all conversations to that user.

**Why conversations are NOT stored for guests:**
- No `user_id` is available without authentication.
- Storing anonymous conversations would create orphaned database rows with no way to retrieve them later.
- Guest sessions are ephemeral by design — refreshing the tab starts a new session.

**Why conversations ARE stored for logged-in users:**
- `user_id` is verified server-side from the JWT.
- Conversations are linked to the user in Supabase and can be retrieved later via `/history/{user_id}`.

**Session flow:**

```
Guest
  browser opens → generateGuestSessionId() → stored in sessionStorage
  question sent → POST /chat (no Authorization header)
  backend skips save_message()

Logged-in User
  POST /login → Supabase verifies credentials → returns JWT
  JWT stored in AuthContext (React)
  question sent → POST /chat (Authorization: Bearer <JWT>)
  backend verifies token → extracts user_id → saves conversation
```

---

## 2. New Tech Stack / Libraries Added

| Technology | Why |
|---|---|
| **Supabase Auth** | Managed authentication — handles user registration, login, JWT issuance |
| **Supabase JS Client** (`@supabase/supabase-js`) | Frontend library to call Supabase Auth and database |
| **React Context API** (`AuthContext`) | Share auth state (user, session, token) across all components without prop drilling |
| **python-jose** | JWT verification on the backend |
| **bcrypt / passlib** | Password hashing (used alongside Supabase Auth) |

---

## 3. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `frontend/src/pages/Login.jsx` | Login form — calls Supabase signInWithPassword |
| `frontend/src/pages/Register.jsx` | Registration form — calls Supabase signUp |
| `frontend/src/context/AuthContext.jsx` | React Context that holds the current user session and exposes login/logout functions |
| `frontend/src/lib/supabase.js` | Initialises the Supabase JS client with project URL and anon key |
| `frontend/src/lib/guestSession.js` | Generates and retrieves the guest session ID from sessionStorage |
| `frontend/src/components/LogoutButton.jsx` | Calls Supabase signOut and clears AuthContext |
| `frontend/src/components/SignInPromptModal.jsx` | Modal shown to guests suggesting they sign in to save history |
| `backend/database/supabase_client.py` | Initialises Supabase Python client with service role key |

### Modified Files

| File | Changes |
|---|---|
| `backend/app.py` | Added `_get_authenticated_user_id()` helper to verify JWT from Authorization header; added guest detection logic; skip `save_message()` when no `user_id` |
| `frontend/src/App.js` | Wrapped app in `AuthContext.Provider`; added routes for `/login` and `/register` |
| `frontend/src/components/FloatingChatbot.jsx` | Reads auth state from `AuthContext`; sends Bearer token if logged in; shows sign-in prompt for guests |
| `frontend/src/components/Navbar.jsx` | Shows Login/Register links for guests; shows Logout button for authenticated users |

---

## 4. Architecture after this Stage

```
User
 │
 ├─ Guest ──────────────────────────────────────────────┐
 │   sessionStorage: guest_session_id                    │
 │   No Authorization header                             │
 │   backend skips conversation save                     │
 │                                                        │
 └─ Authenticated User                                   │
     Supabase Auth JWT                                   │
     Authorization: Bearer <token>                       │
     backend verifies → user_id → saves conversation     │
                                                        ▼
                                               FastAPI /chat
                                                   │
                                             (same FAISS + Gemini pipeline)
```

---
---

# Stage 3 — Conversation History

## 1. How was it implemented?

Every conversation between a user and the chatbot is stored in Supabase with two linked tables:

- **`conversations`** — one row per conversation, with `id`, `user_id`, and `title` (first 60 characters of the opening question).
- **`messages`** — one row per message, with `conversation_id`, `sender` (user or assistant), and `content`.

**How it works:**

1. When an authenticated user sends their first message, the backend calls `create_conversation(user_id, title)` which inserts a row in `conversations` and returns a `conversation_id`.
2. Every subsequent message (user and assistant) is saved with `save_message(conversation_id, sender, content)`.
3. If `conversation_id` is sent in the request, the backend looks it up and re-uses the existing conversation rather than creating a new one.
4. The frontend fetches conversation history via `GET /history/{user_id}` and displays previous conversations in a sidebar.
5. Selecting a past conversation calls `GET /conversation/{conversation_id}` which returns all messages.

**Guest behaviour:**
- Guests receive no `conversation_id` in responses.
- No rows are written to `conversations` or `messages`.
- History sidebar is hidden for guests.

---

## 2. New Tech Stack / Libraries Added

No new external libraries — uses the Supabase Python client already installed.

---

## 3. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `backend/chat_history.py` | Contains `create_conversation`, `get_conversation`, `save_message`, `get_user_conversations`, `get_conversation_messages` — all Supabase table operations |

### Modified Files

| File | Changes |
|---|---|
| `backend/app.py` | Added `GET /history/{user_id}` endpoint; added `GET /conversation/{conversation_id}` endpoint; added `_ensure_conversation()` helper; integrated `save_message()` into `/chat` flow |
| `frontend/src/components/FloatingChatbot.jsx` | Added history sidebar; fetches conversations on load; clicking a past conversation loads its messages; sends `conversation_id` in subsequent requests |

---

## 4. Architecture after this Stage

```
Authenticated User
 │
 ▼
POST /chat  (with optional conversation_id)
 │
 ├─ No conversation_id → create_conversation() → new conversation_id
 └─ Has conversation_id → load existing
 │
 ▼
save_message(conversation_id, "user", question)
 │
 ▼
FAISS + Gemini pipeline
 │
 ▼
save_message(conversation_id, "assistant", answer)
 │
 ▼
ChatResponse (includes conversation_id)
 │
 ▼
GET /history/{user_id}  ←  sidebar loads past conversations
GET /conversation/{id}  ←  user clicks past conversation
```

---
---

# Stage 4 — User Preferences

## 1. How was it implemented?

A `user_preferences` table in Supabase stores per-user settings. Preferences are written and read via two dedicated API endpoints.

**What is stored:**

| Field | Description |
|---|---|
| `user_id` | Links to the authenticated user |
| `preferred_category` | The medical device category the user most often queries |
| `recent_products` | List of product names the user has recently viewed |
| `favorite_products` | Products the user has marked as favourites |
| `last_active` | ISO timestamp of last chatbot interaction |

**How personalisation works:**

1. After every chat response, the frontend calls `POST /preferences/{user_id}` with the matched product and category.
2. The backend upserts (insert or update) the preferences row using Supabase's `upsert` with `on_conflict="user_id"`.
3. On page load, the frontend calls `GET /preferences/{user_id}` to pre-select the user's preferred category in the chatbot.

**Why:**
Personalisation makes the chatbot feel context-aware — it can pre-filter suggestions and remember what the user cares about across sessions.

---

## 2. New Tech Stack / Libraries Added

No new libraries — uses existing Supabase client and FastAPI.

---

## 3. Files Created / Modified

### Modified Files

| File | Changes |
|---|---|
| `backend/app.py` | Added `GET /preferences/{user_id}` endpoint; added `POST /preferences/{user_id}` upsert endpoint |
| `backend/models.py` | Added `UserPreferencesBody` and `UserPreferencesResponse` Pydantic models |
| `frontend/src/components/FloatingChatbot.jsx` | Calls GET preferences on load; calls POST preferences after each answer; highlights preferred category |

---

## 4. Architecture after this Stage

```
User Logs In
 │
 ▼
GET /preferences/{user_id}  →  loads preferred_category, recent_products
 │
 ▼
User asks question
 │
 ▼
Chat pipeline runs
 │
 ▼
POST /preferences/{user_id}  →  upserts matched_product, matched_category, last_active
```

---
---

# Stage 5 — Cache System

## 1. How was it implemented?

The cache stores previously generated answers in a Supabase table called `cached_answers`. On every new request, the backend first checks this table before running the full search and generation pipeline. If a sufficiently similar question was answered before, the cached answer is returned immediately — saving time and API quota.

**Cache lookup flow:**

1. `get_cached_answer(question, intent)` is called at the start of every `/chat` request.
2. The question is normalised (lowercased, whitespace collapsed) and prefixed with the intent to form a cache key: `intent::normalised_question`.
3. All rows matching the intent prefix are fetched from Supabase.
4. If embedding vectors are present, cosine similarity is computed between the incoming question's embedding and each cached question's embedding.
5. If the best similarity score is ≥ 0.90 (threshold), the cached answer is returned directly.
6. If no embeddings exist yet, an exact string match is used as fallback.

**Cache save flow:**

1. After a new answer is generated, `save_cached_answer(question, answer, intent)` is called.
2. A quality gate checks: answer must be > 100 characters, must not be a fallback/error string.
3. A duplicate check prevents inserting the same key twice.
4. The answer is stored with the question embedding vector (384-d) for future semantic matching.

**Cache flag:**
A single `ENABLE_CACHE` environment variable controls both reading and writing. Set to `False` during development to bypass the cache entirely and test the full pipeline every time.

**Why semantic similarity instead of exact match:**
The same question asked with slightly different wording (e.g., "What is TC50?" vs "Tell me about TC50") should return the same cached answer. Cosine similarity on embeddings achieves this.

---

## 2. New Tech Stack / Libraries Added

| Technology | Why |
|---|---|
| **numpy** | Vector arithmetic for cosine similarity computation |
| **Supabase `pgvector`** | Stores 384-d embedding vectors in the `cached_answers` table |

---

## 3. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `backend/cache_service.py` | Complete cache implementation — semantic lookup, quality gate, save with embedding, ENABLE_CACHE flag |

### Modified Files

| File | Changes |
|---|---|
| `backend/app.py` | Imports `get_cached_answer`, `save_cached_answer`, `ENABLE_CACHE`; calls cache lookup at start of `/chat` and `/chat/stream`; calls cache save after answer generation |
| `.env` | Added `ENABLE_CACHE=True/False` flag |

---

## 4. Architecture after this Stage

```
POST /chat
 │
 ▼
get_cached_answer(question, intent)
 │
 ├─ CACHE HIT  (similarity ≥ 0.90) → return cached answer immediately
 │
 └─ CACHE MISS
      │
      ▼
   FAISS + Gemini pipeline
      │
      ▼
   save_cached_answer(question, answer)  →  Supabase cached_answers table
      │
      ▼
   Return answer to frontend
```

---


---

# Stage 6 — Hybrid Search (FAISS + BM25 + RRF)

## 1. How was it implemented?

The original search was pure semantic FAISS — it worked well for conceptual queries but missed exact keyword matches (e.g., a model number like "TC50"). Hybrid search combines two complementary retrieval methods:

**FAISS (semantic search):**
- The query is encoded into a 384-d vector using `all-MiniLM-L6-v2`.
- The FAISS index is searched for the 10 nearest neighbours by L2 distance.
- Chunks with L2 distance > 1.4 are discarded (too dissimilar to be relevant).

**BM25 (keyword search):**
- A BM25Okapi index is built at query time from all product chunks.
- The query is tokenised and scored against every chunk using term frequency and inverse document frequency.
- The top 10 results by BM25 score are collected.

**Reciprocal Rank Fusion (RRF):**
- Both ranked lists are merged using RRF with damping constant k=60:
  `score(doc) = Σ 1 / (60 + rank)`
- Documents appearing in both lists get a double bonus and rise to the top.
- The fused, re-ranked list is deduplicated and the top results are returned.

**Why:**
- FAISS alone misses exact model number queries.
- BM25 alone misses paraphrased or conceptual queries.
- Together they cover both and produce better candidates for the reranker.

---

## 2. New Tech Stack / Libraries Added

| Technology | Why |
|---|---|
| **rank-bm25** (`BM25Okapi`) | Fast BM25 keyword scoring over the product chunk corpus |

---

## 3. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `backend/search/hybrid_search.py` | `hybrid_product_search()` — FAISS + BM25 retrieval + RRF fusion |
| `backend/search/bm25_index.py` | `bm25_search()` — builds BM25 index from chunks and scores the query |
| `backend/search/common.py` | Shared utilities: `SearchResult` dataclass, `normalise_query()`, `extract_product_name()`, `extract_category()`, `deduplicate()`, `faiss_confidence()` |
| `backend/search/__init__.py` | Exposes `smart_search()` as the single public entry point; loads the SentenceTransformer model once |
| `backend/search/orchestrator.py` | `smart_search()` — routes the query through exact match → hybrid search → reranker → PDF search → dynamic search fallback |

### Modified Files

| File | Changes |
|---|---|
| `backend/search/product_search.py` | `faiss_search()` now delegates to `hybrid_product_search()` instead of running pure FAISS; added `MAX_CHUNK_DISTANCE=1.4` per-chunk threshold |
| `backend/app.py` | Changed `from search import smart_search` to use the new orchestrator entry point |

---

## 4. Architecture after this Stage

```
Query
 │
 ▼
FAISS (semantic, top-10)   +   BM25 (keyword, top-10)
         │                           │
         └─────────┬─────────────────┘
                   ▼
          Reciprocal Rank Fusion
                   │
                   ▼
          Deduplicated top-5 chunks
                   │
                   ▼
            Gemini → Answer
```

---
---

# Stage 7 — PDF Search

## 1. How was it implemented?

Beyond the product catalog (scraped web data), the system also indexes official Philips PDF documents (manuals, datasheets, brochures). These are chunked and stored in a separate FAISS index so they can be searched independently.

**How the PDF index is built:**
1. PDFs are extracted to text using `pypdf` (`extract_text.py`).
2. Text is cleaned — noise, headers, page numbers removed (`clean_text.py`).
3. Clean text is split into overlapping chunks with metadata: `document_name`, `page_number`, `product` (`chunk_text.py`).
4. Chunks are embedded and stored in a FAISS index (`embed_chunks.py`).
5. Metadata is saved to a `.pkl` file alongside the index.

**How PDF search works at query time:**
1. `pdf_search.search(query, matched_product)` is called after the main hybrid search.
2. The query is encoded and searched against the PDF FAISS index.
3. Results are filtered to chunks whose `product` field matches the product already identified by the main search.
4. Only chunks scoring above a similarity threshold are returned.
5. PDF chunks are kept separate from product chunks — they are passed to Gemini as a distinct `📄 PDF Knowledge` context section.

**Why:**
Product catalog data is short and structured. PDFs contain full technical specifications, warnings, and clinical use guidance that is not in the catalog.

---

## 2. New Tech Stack / Libraries Added

| Technology | Why |
|---|---|
| **pypdf** | Extracts text from PDF files without external binaries |

---

## 3. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `backend/pdf_processing/extract_text.py` | Reads PDF files and extracts raw text per page |
| `backend/pdf_processing/clean_text.py` | Removes noise (headers, footers, page numbers) from extracted text |
| `backend/pdf_processing/chunk_text.py` | Splits clean text into chunks with document/page metadata |
| `backend/pdf_processing/embed_chunks.py` | Encodes chunks and writes the PDF FAISS index + metadata pickle |
| `backend/pdf_processing/faiss/pdf.index` | The PDF FAISS binary index |
| `backend/pdf_processing/metadata/pdf_metadata.pkl` | Chunk metadata (document name, page, product) |
| `backend/search/pdf_search.py` | `search(query, matched_product)` — searches PDF FAISS index, filters by product |
| `backend/scripts/build_pdf_index.py` | One-time script to build the PDF index from a folder of PDFs |
| `backend/document_service.py` | `get_documents_by_product()` — queries Supabase `documents` table to return downloadable files linked to a product |

### Modified Files

| File | Changes |
|---|---|
| `backend/search/orchestrator.py` | Calls `pdf_search.search()` after hybrid search; attaches `pdf_chunks` to `SearchResult` |
| `backend/app.py` | Builds `📄 PDF Knowledge` context section from `result.pdf_chunks`; calls `get_documents_by_product()` to attach document download links to the response |

---

## 4. Architecture after this Stage

```
Query
 │
 ▼
Hybrid Search (FAISS + BM25)  →  product chunks
 +
PDF Search (separate FAISS)   →  pdf_chunks (filtered by matched_product)
 │
 ▼
Context = product chunks + pdf chunks
 │
 ▼
Gemini → Answer + Documents list
```

---
---

# Stage 8 — Dynamic Search (DuckDuckGo + Wikipedia)

## 1. How was it implemented?

Some queries have no answer in the product catalog or PDFs — for example, general medical concepts like "What is arrhythmia?" or category-level queries like "Tell me about cardiology devices". For these, the system falls back to external sources.

**Routing logic:**

The intent detector classifies queries as `general_medical_query` or `category_query`. These are routed directly to dynamic search, bypassing FAISS entirely.

**DuckDuckGo search:**
- `duckduckgo_search.py` uses the `duckduckgo-search` library to fetch the top web results for the query.
- Results are returned as title + snippet pairs.
- This handles category and general concept queries where no product exists.

**Wikipedia integration:**
- `wikipedia_guard.py` checks whether the query is about a pure medical concept (no Philips product fragment detected).
- If approved, `wikipedia_service.py` fetches the Wikipedia summary for the detected topic.
- Wikipedia is used as the **sole source** when DuckDuckGo returns fewer than 2 results (weak web result).
- Wikipedia is **merged** alongside DuckDuckGo when both return good results.
- Wikipedia is **never** used to override FAISS product results.

**Why separate systems:**
- DuckDuckGo covers current, broad web knowledge.
- Wikipedia provides structured, authoritative medical definitions.
- Neither is used for product queries where the local index is more accurate.

---

## 2. New Tech Stack / Libraries Added

| Technology | Why |
|---|---|
| **duckduckgo-search** (`ddgs`) | Free web search API — no key required |
| **Wikipedia API** (via `requests`) | Structured encyclopaedia summaries for medical concepts |

---

## 3. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `backend/dynamic_search/duckduckgo_search.py` | Calls DuckDuckGo and returns top-n web snippets |
| `backend/dynamic_search/wikipedia_service.py` | Fetches Wikipedia summary for a topic; returns title, summary, URL |
| `backend/dynamic_search/wikipedia_guard.py` | Guards Wikipedia use — checks intent and query for product fragments before allowing Wikipedia call |
| `backend/dynamic_search/web_summary.py` | Utility to format dynamic search snippets as context |
| `backend/search/dynamic_search.py` | `search(query)` — runs DuckDuckGo, returns `SearchResult` with source=`dynamic_search` |

### Modified Files

| File | Changes |
|---|---|
| `backend/search/orchestrator.py` | Routes `general_medical_query` and `category_query` to dynamic search; adds Wikipedia enrichment step after DuckDuckGo |
| `backend/intent_detector.py` | Added `GENERAL_MEDICAL` and `CATEGORY_QUERY` intent constants; added `_GENERAL_MEDICAL_TERMS` set including surgery lights, ABPM, arrhythmia, etc. |
| `backend/gemini_service.py` | Added `_build_wikipedia_prompt()` and `_build_web_prompt()` for dynamic search sources |

---

## 4. Architecture after this Stage

```
Query
 │
 ▼
Intent Detector
 │
 ├─ product / feature / specification / comparison
 │    → Hybrid Search (FAISS + BM25) + PDF Search
 │
 └─ general_medical / category
      → DuckDuckGo
      → Wikipedia Guard check
      → Wikipedia (if approved)
      → Context passed to Gemini / Response Refiner
```

---
---

# Stage 9 — Query Rewriter + Cross-Encoder Reranker

## 1. How was it implemented?

**Query Rewriter:**

Raw user queries often contain filler words, abbreviations, or informal phrasing that degrades FAISS retrieval quality. The query rewriter normalises them.

- `query_rewriter.py` receives the original query and intent.
- It strips filler words ("tell me about", "can you explain"), expands known abbreviations ("TC50" → "PageWriter TC50"), and produces a canonical retrieval query.
- It also generates query variants — alternative phrasings — which are each used to fetch additional candidate chunks that are then merged with the canonical results.

**Cross-Encoder Reranker:**

After hybrid search produces up to 10 candidate chunks, the reranker selects the best 5.

- `reranker.py` loads `cross-encoder/ms-marco-MiniLM-L-6-v2` from HuggingFace.
- It scores every (query, chunk) pair using the cross-encoder — this is more accurate than cosine similarity because it jointly encodes the query and document.
- Chunks are sorted by descending score. The top 5 are passed to the context builder.

**Why separate rewriting and reranking:**
- Query rewriting improves recall (more relevant candidates fetched).
- Reranking improves precision (most relevant candidates selected).
- Both are needed because FAISS+BM25 cast a wide net; the cross-encoder picks the best catch.

---

## 2. New Tech Stack / Libraries Added

| Technology | Why |
|---|---|
| **CrossEncoder** (`sentence-transformers`) | Joint query-document scoring — more accurate than embedding cosine similarity for final ranking |
| **`cross-encoder/ms-marco-MiniLM-L-6-v2`** | Small, fast cross-encoder model tuned for passage ranking |

---

## 3. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `backend/search/query_rewriter.py` | `rewrite(query, intent)` — strips filler, expands abbreviations, returns canonical query + variants |
| `backend/search/reranker.py` | `rerank(query, chunks, top_k=5)` — scores each chunk with cross-encoder, returns top-k |

### Modified Files

| File | Changes |
|---|---|
| `backend/search/orchestrator.py` | Calls `rewrite()` before FAISS search; calls `rerank()` after hybrid search; merges variant query results before reranking |
| `backend/search/product_search.py` | `exact_match()` extended for comparison queries — splits query into two sides and enriches bare model numbers with brand prefix (e.g. "TC70" → "PageWriter TC70") |

---

## 4. Architecture after this Stage

```
Query
 │
 ▼
Query Rewriter  →  canonical query + variants
 │
 ▼
Hybrid Search (canonical)
 + variant searches (each variant fetched and merged)
 │
 ▼
Merged candidate pool (up to ~20 chunks)
 │
 ▼
Cross-Encoder Reranker  →  top-5 most relevant chunks
 │
 ▼
PDF Search (product-filtered)
 │
 ▼
Context builder → Gemini / Response Refiner
```

---
---

# Stage 10 — Context Cleaner + Response Validator

## 1. How was it implemented?

**Context Cleaner (`pipeline/context_cleaner.py`):**

Raw retrieval chunks contain noise — page numbers, copyright notices, lone digits, URL lines, repeated sentences across chunks. This noise wastes Gemini context tokens and degrades response quality.

The cleaner runs in two passes:

1. **Per-chunk noise removal:** Every line is checked against noise patterns (lone digits, "Page X of Y", copyright notices, URLs, divider lines). Structural labels (Product, Category, Features, etc.) are always kept. Bullet markers are always kept. Only genuine noise lines are removed. Lines are re-joined with `\n` — never with space — to prevent word concatenation bugs.

2. **Cross-chunk deduplication:** Identical lines appearing in multiple chunks are removed. Structural section headers are exempt — they must appear in every chunk.

**Response Validator (`pipeline/response_validator.py`):**

After Gemini (or the refiner) generates a response, the validator checks it before returning to the user.

Checks performed:
- **Empty response** — rejected if answer is blank.
- **Too short** — rejected if fewer than 60 characters.
- **Fallback sentinel** — rejected if answer contains the generic error message.
- **Raw metadata** — rejected if multiple `Product Name:` / `Category:` / `Description:` label lines are found.
- **Out-of-scope sentinel with context** — rejected if Gemini returned "I could not find…" despite having retrieved context.
- **Product name absent** — for product/feature/spec queries, the product name must appear in the answer.

If validation fails, the pipeline re-runs `response_refiner.refine()` on the raw chunks as a recovery step.

---

## 2. New Tech Stack / Libraries Added

No new external libraries.

---

## 3. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `backend/pipeline/context_cleaner.py` | `clean_chunks(chunks)` — noise removal + cross-chunk deduplication. `clean_pdf_highlight(text)` — single PDF highlight cleaning |
| `backend/pipeline/response_validator.py` | `validate_response(answer, question, intent, matched_product, has_context)` → `ValidationResult(is_valid, reason)` |

### Modified Files

| File | Changes |
|---|---|
| `backend/app.py` | Calls `clean_chunks()` on `combined_context` before passing to Gemini; calls `validate_response()` after answer generation; on failure calls refiner retry |

---

## 4. Architecture after this Stage

```
Retrieval chunks
 │
 ▼
context_cleaner.clean_chunks()
 │  removes noise lines, deduplicates across chunks
 ▼
Combined context (clean)
 │
 ▼
Response Refiner / Gemini
 │
 ▼
response_validator.validate_response()
 │
 ├─ VALID  →  save + return
 └─ INVALID → refiner retry → return
```

---


---

# Stage 11 — Response Refiner

## 1. How was it implemented?

### Why Gemini became optional

The original architecture depended on Gemini for every response. When the Gemini API quota is exhausted (HTTP 429), the old fallback formatter produced broken output:

- Product names extracted as empty strings
- Features and specifications never parsed
- Long paragraphs of concatenated raw text
- Users seeing internal labels like `Product:`, `Category:`, `Description:`

The fix was to invert the dependency: the **Response Refiner** is the primary formatter. It runs on every request and always produces a complete, clean response. Gemini is called afterwards as an optional polish — if it succeeds and returns richer content, that is used instead. If Gemini fails for any reason, the refiner output is returned directly.

### How response refinement works without Gemini

The refiner (`response_refiner.py`) is a deterministic, rule-based Markdown generator. It:

1. Receives the `combined_context` list (formatted chunks from the retrieval pipeline).
2. Splits multi-product chunks separated by `\n\n---\n\n` into individual items.
3. Parses each chunk using section-based regex extractors.
4. Routes to the correct formatter based on `intent`.
5. Returns a complete, structured Markdown string.

### Chunk parsing

Each chunk produced by `_format_product_chunk()` in `app.py` has this structure:

```
📦 Product

PageWriter TC50

Category
Cardiology

Summary

The PageWriter TC50 is a 12-lead ECG system...

Features

- Wireless Connectivity: Built-in Wi-Fi for data transfer
- Touch Screen: 10.1 inch colour display

Specifications

- Display: 10.1 inch LCD
- Weight: 3.2 kg
```

The parsers extract each section:

- `_product_name()` — reads the line after `📦 Product`
- `_category()` — reads the line after `Category`
- `_description()` — reads the `Summary` section, splits into sentences, returns max 3
- `_features()` — reads `Features` section, returns list of `"Name: detail"` strings
- `_specs()` — reads `Specifications` section, returns list of `"Name: value"` strings
- `_wiki_summary()` — extracts and cleans Wikipedia/dynamic search text into 4 sentences max

### Formatter pipeline — one function per intent

**`format_product()`**
- Outputs: `# Product Name`, category, 3-sentence overview, `## Key Features` bullets, `## Specifications` table, `## Applications`, `## Advantages`.
- Never outputs raw labels. Never concatenates chunk fields.

**`format_features()`**
- Outputs: `# Features of Product` heading, then one bullet per feature in `**Name** — detail` format.
- Adds a one-sentence clinical benefit summary at the end.
- No description, no specifications.

**`format_specifications()`**
- Outputs: `# Technical Specifications — Product` heading, then a two-column Markdown table `| Parameter | Value |`.
- Each spec line `"Key: Value"` is split into table columns.

**`format_comparison()`**
- Collects up to 2 distinct products from the chunks.
- Outputs: `# P1 vs P2`, side-by-side table with category, overview, feature rows, spec rows.
- Outputs `## Key Differences` as bullets.
- Outputs `## Recommendation` paragraph.
- If only one product is found, shows a warning and displays that product's details.

**`format_general_medical()`**
- Matches the query against a built-in `_CONCEPTS` knowledge base (18 medical terms: ECG, ABPM, AED, arrhythmia, Holter, stress test, etc.).
- Outputs: `# Concept Name`, summary paragraph, `## Key Points` bullets, `## Common Uses` bullets, `## Benefits` bullets, `## Related Philips Products`.
- If Wikipedia text is available and richer than the built-in summary, it is used instead.
- For unknown concepts, uses Wikipedia text formatted into ≤2-sentence paragraphs.

**`format_category()`**
- Collects all distinct products from the chunks.
- Outputs: category intro paragraph, `## Products` list (name + description per product), `## Applications` bullets, `## Summary` table.

**`format_dynamic()`**
- Used when the source is `dynamic_search` and no concept match is found.
- Summarises Wikipedia/DuckDuckGo text into ≤2-sentence paragraphs.
- Never dumps raw snippets.

---

## 2. New Tech Stack / Libraries Added

No new external libraries — the refiner is pure Python with the `re` standard library.

---

## 3. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `backend/response_refiner.py` | Complete deterministic response engine — 1081 lines. Exports `format_product`, `format_features`, `format_specifications`, `format_comparison`, `format_category`, `format_general_medical`, `format_dynamic`, `refine` |

### Modified Files

| File | Changes |
|---|---|
| `backend/gemini_service.py` | `generate_answer()` now calls `response_refiner.refine()` first, then tries Gemini as optional polish. On any Gemini error, refiner output returned. `generate_answer_streaming()` same pattern — streams refiner output in 64-char chunks if Gemini fails |
| `backend/app.py` | Validator fallback path now calls `response_refiner.refine()` instead of individual `fallback_formatter` functions |
| `backend/fallback_formatter.py` | Kept as legacy module; parsers rewritten to handle formatted chunk structure; now secondary to `response_refiner` |
| `backend/intent_detector.py` | Added surgical lights, operating lights, OT equipment terms to `_GENERAL_MEDICAL_TERMS` |
| `backend/search/product_search.py` | `_split_comparison()` strips leading verbs and uses `_enrich_comparison_sides()` to prepend brand prefix to bare model numbers |

---

## 4. Architecture after this Stage

```
Retrieval result (chunks)
 │
 ▼
Context builder (_format_product_chunk × N)  →  combined_context
 │
 ▼
context_cleaner.clean_chunks()
 │
 ▼
response_refiner.refine()           ← PRIMARY — always runs, always produces output
 │  (deterministic Markdown)
 ▼
Gemini polish (optional)            ← only if quota available
 │  if Gemini returns content → use it
 │  if Gemini fails → use refiner output
 ▼
response_validator.validate_response()
 │
 ├─ VALID  → save_cached_answer() → return
 └─ INVALID → refiner retry on raw chunks → return
```

---
---

# Stage 12 — Final Production Pipeline

## 1. How was it implemented?

This is the complete, end-to-end pipeline as it exists in the final version. Every component built in Stages 1–11 is now integrated and operational.

**Complete request lifecycle:**

1. **User sends a question** via the floating chatbot (guest or authenticated).
2. **Authentication** — if `Authorization: Bearer <token>` is present, the backend verifies the JWT with Supabase and extracts `user_id`. Guests proceed without a user_id.
3. **Conversation management** — for authenticated users, a conversation is created or continued; the user message is saved.
4. **Intent detection** — the query is classified into one of six intents: `product_query`, `feature_query`, `specification_query`, `comparison_query`, `category_query`, `general_medical_query`.
5. **Cache lookup** — `get_cached_answer()` checks Supabase for a semantically similar past answer (cosine similarity ≥ 0.90). On a hit, the cached answer is returned immediately and the pipeline stops here.
6. **Query rewriting** — the query is normalised and query variants are generated.
7. **Search routing:**
   - `category_query` / `general_medical_query` → DuckDuckGo + Wikipedia
   - All other intents → exact name match → hybrid FAISS+BM25 → RRF fusion → cross-encoder reranker → PDF search
8. **Context building** — retrieved chunks are formatted with section headers. PDF chunks are added as a separate section.
9. **Context cleaning** — noise lines removed, cross-chunk duplicates removed.
10. **Response Refiner** — runs deterministically and produces a complete Markdown response.
11. **Gemini polish** — Gemini is called with an intent-specific prompt. If it returns a richer response, it replaces the refiner output. If Gemini is unavailable (quota, network error), the refiner output is used.
12. **Response validation** — answer checked for length, sentinel strings, raw metadata, product name presence. On failure, refiner retries on raw chunks.
13. **Cache save** — if `ENABLE_CACHE=True`, the answer is stored in Supabase with its embedding.
14. **Conversation save** — assistant message saved to the `messages` table.
15. **Documents** — `get_documents_by_product()` returns downloadable files linked to the matched product.
16. **Response returned** — `ChatResponse` with answer, source, matched_product, confidence, conversation_id, documents.

---

## 2. Complete Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React, CSS |
| **API** | FastAPI, Uvicorn |
| **Auth** | Supabase Auth (JWT), React Context |
| **Database** | Supabase (PostgreSQL) |
| **Semantic Search** | FAISS, SentenceTransformers (`all-MiniLM-L6-v2`) |
| **Keyword Search** | BM25 (`rank-bm25`) |
| **Reranking** | CrossEncoder (`ms-marco-MiniLM-L-6-v2`) |
| **PDF Processing** | pypdf, FAISS (separate index) |
| **Web Search** | DuckDuckGo Search (`ddgs`) |
| **Wikipedia** | Wikipedia REST API |
| **LLM (optional)** | Google Gemini 2.0 Flash |
| **Cache** | Supabase `cached_answers` table + pgvector |
| **Response Engine** | `response_refiner.py` (deterministic, no LLM) |
| **Streaming** | FastAPI `StreamingResponse` + Server-Sent Events (SSE) |

---

## 3. Final File Map

```
MediDevice_Chatbot/
├── .env                              ENABLE_CACHE, GEMINI_API_KEY_*, Supabase keys
├── backend/
│   ├── app.py                        Main FastAPI app — /chat, /chat/stream, /history, /preferences
│   ├── models.py                     Pydantic models
│   ├── intent_detector.py            Query classification (6 intent types)
│   ├── gemini_service.py             Gemini API — optional polish layer
│   ├── response_refiner.py           Primary response engine — deterministic Markdown
│   ├── fallback_formatter.py         Legacy formatter (secondary)
│   ├── cache_service.py              Semantic cache — lookup + save + ENABLE_CACHE flag
│   ├── chat_history.py               Conversation + message storage (Supabase)
│   ├── document_service.py           Document lookup by product
│   ├── logger.py                     Search event logging to file
│   ├── email_service.py              Contact form email dispatch
│   ├── download_service.py           OTP-gated document download flow
│   ├── database/
│   │   └── supabase_client.py        Supabase Python client initialisation
│   ├── search/
│   │   ├── orchestrator.py           smart_search() — main retrieval router
│   │   ├── product_search.py         exact_match, faiss_search, comparison_search
│   │   ├── hybrid_search.py          FAISS + BM25 + RRF fusion
│   │   ├── bm25_index.py             BM25Okapi index builder and scorer
│   │   ├── query_rewriter.py         Query normalisation and variant generation
│   │   ├── reranker.py               CrossEncoder reranker (top-5 selection)
│   │   ├── pdf_search.py             PDF FAISS index search (product-filtered)
│   │   ├── common.py                 SearchResult, normalise_query, deduplicate
│   │   └── dynamic_search.py        DuckDuckGo search wrapper
│   ├── dynamic_search/
│   │   ├── wikipedia_service.py      Wikipedia API fetch
│   │   ├── wikipedia_guard.py        Guards Wikipedia use (no product overrides)
│   │   └── duckduckgo_search.py      DuckDuckGo search
│   ├── pipeline/
│   │   ├── context_cleaner.py        Noise removal + cross-chunk deduplication
│   │   └── response_validator.py     Answer quality validation
│   ├── pdf_processing/
│   │   ├── extract_text.py           PDF → raw text
│   │   ├── clean_text.py             Raw text → clean text
│   │   ├── chunk_text.py             Clean text → chunks with metadata
│   │   ├── embed_chunks.py           Chunks → FAISS index
│   │   ├── faiss/pdf.index           PDF FAISS binary index
│   │   └── metadata/pdf_metadata.pkl Chunk metadata (document, page, product)
│   └── vector_db/
│       ├── faiss_index.bin           Product catalog FAISS index
│       └── product_chunks.pkl        Product text chunks
└── frontend/src/
    ├── App.js                        Root component, routing
    ├── context/AuthContext.jsx       Auth state (user, session, JWT)
    ├── lib/supabase.js               Supabase JS client
    ├── lib/guestSession.js           Guest session ID management
    ├── components/
    │   ├── FloatingChatbot.jsx       Floating chat widget (streaming, history, auth)
    │   ├── Navbar.jsx                Top navigation (auth-aware)
    │   ├── SignInPromptModal.jsx     Modal for guest → sign-in nudge
    │   ├── DownloadModal.jsx         OTP-gated document download UI
    │   └── [landing page sections]  Hero, FeaturedProducts, Footer, etc.
    └── pages/
        ├── Login.jsx                 Login page
        ├── Register.jsx              Registration page
        ├── ResourcesPage.jsx         Document library
        └── [other pages]
```

---

## 4. Final Architecture Diagram

```
User (Browser)
 │
 ├─ Guest ──────────────────────┐
 │   sessionStorage ID          │  No auth header
 │                              │  No conversation saved
 └─ Authenticated User          │
     JWT from Supabase Auth     │
     Authorization: Bearer      │
                                 ▼
                        FastAPI Backend (app.py)
                                 │
                         ┌───────┴──────────┐
                         │                  │
                    Verify JWT         Skip (guest)
                    get user_id
                         │
                         ▼
                  Intent Detector
                  (6 intent types)
                         │
                         ▼
                   Cache Lookup
                  (cosine ≥ 0.90)
                         │
              ┌──────────┴──────────┐
           HIT │                    │ MISS
              ▼                     ▼
        Return cached         Query Rewriter
        answer                (canonical + variants)
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
           product/feature/               general_medical/
           spec/comparison                category
                    │                               │
                    ▼                               ▼
           Hybrid Search                   DuckDuckGo
           FAISS + BM25                        +
           RRF Fusion                      Wikipedia Guard
                    │                      Wikipedia Fetch
                    ▼                               │
           CrossEncoder                            │
           Reranker (top-5)              ──────────┘
                    │
                    ▼
              PDF Search
           (product-filtered)
                    │
                    ▼
          Context Builder
        (_format_product_chunk)
                    │
                    ▼
         Context Cleaner
        (noise + dedup)
                    │
                    ▼
       Response Refiner          ← PRIMARY: always runs
       (deterministic Markdown)
                    │
                    ▼
      Gemini 2.0 Flash           ← OPTIONAL: polish only
      (if quota available)
                    │
                    ▼
       Response Validator
       (length, sentinel, metadata, product name)
                    │
              ┌─────┴─────┐
           VALID          INVALID
              │            │
              │       Refiner retry
              │            │
              └─────┬──────┘
                    ▼
           Cache Save (Supabase)
           Message Save (Supabase)
           Document Lookup
                    │
                    ▼
              ChatResponse
           (answer, source, product,
            category, confidence,
            conversation_id, documents)
                    │
                    ▼
         Frontend FloatingChatbot
         (SSE streaming / standard JSON)
                    │
                    ▼
              User sees
         formatted Markdown answer
```

---

*Documentation generated: 2026-07-04*
*Project: MediDevice Chatbot*
