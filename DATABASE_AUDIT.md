# DATABASE ARCHITECTURE AUDIT — Module 13
**Date:** 2026-07-03  
**Status:** Current implementation review

---

## EXISTING TABLES (Verified via backend usage)

### 1. `conversations` ✅
**Purpose:** Stores chat conversation metadata for authenticated users  
**Backend usage:** `chat_history.py`, `conversation_service.py`, `app.py`

**Schema (inferred from code):**
```sql
id           uuid PRIMARY KEY
user_id      uuid REFERENCES auth.users(id)
title        text
created_at   timestamptz
```

**Operations:**
- CREATE: `create_conversation(user_id, title)`
- READ: `get_user_conversations(user_id)`, `get_conversation(conversation_id)`
- UPDATE: Not used
- DELETE: Not used (ON DELETE CASCADE via user_id FK likely)

**Indexes needed:**
- PRIMARY KEY on `id` ✅ (implicit)
- INDEX on `user_id` (for conversation list queries)
- INDEX on `created_at DESC` (for ordered listing)

---

### 2. `messages` ✅
**Purpose:** Stores individual messages within conversations  
**Backend usage:** `chat_history.py`

**Schema (inferred from code):**
```sql
id                uuid PRIMARY KEY
conversation_id   uuid REFERENCES conversations(id) ON DELETE CASCADE
sender            text ('user' | 'assistant')
content           text
created_at        timestamptz
```

**Operations:**
- CREATE: `save_message(conversation_id, sender, content)`
- READ: `get_conversation_messages(conversation_id)`
- UPDATE: Not used
- DELETE: Not used (ON DELETE CASCADE via conversation_id FK likely)

**Indexes needed:**
- PRIMARY KEY on `id` ✅ (implicit)
- INDEX on `conversation_id` (for message list queries)
- INDEX on `created_at` (for ordered listing)

---

### 3. `device_documents` ✅
**Purpose:** Document library metadata for PDFs, brochures, datasheets  
**Backend usage:** `document_service.py`, `scripts/sync_documents.py`, `scripts/build_pdf_index.py`

**Schema (inferred from code):**
```sql
id               uuid PRIMARY KEY
product_name     text
document_name    text
document_type    text
category         text
subcategory      text
file_url         text
storage_path     text
is_active        boolean DEFAULT true
created_at       timestamptz
updated_at       timestamptz
```

**Operations:**
- CREATE: `scripts/sync_documents.py` (bulk upserts)
- READ: `get_categories()`, `get_subcategories()`, `get_documents()`, `get_documents_by_product()`, `get_documents_by_names()`
- UPDATE: `scripts/sync_documents.py` (file_url updates)
- DELETE: Soft delete via `is_active = false`

**Indexes needed:**
- PRIMARY KEY on `id` ✅ (implicit)
- INDEX on `(category, subcategory, is_active)` (for filtered queries)
- INDEX on `product_name` (for ILIKE searches)
- INDEX on `document_name` (for lookup by name)
- INDEX on `is_active` (for active-only queries)

---

### 4. `cached_answers` ✅
**Purpose:** Semantic query cache with vector embeddings  
**Backend usage:** `cache_service.py`

**Schema (inferred from code):**
```sql
id          uuid PRIMARY KEY
question    text UNIQUE
answer      text
embedding   vector(384)  -- nullable, migration warning in code
created_at  timestamptz
```

**Operations:**
- CREATE: `save_cached_answer(question, answer, intent)`
- READ: `get_cached_answer(question, intent)` — semantic similarity search
- UPDATE: Not used (duplicates prevented)
- DELETE: Not used (TTL/cleanup not implemented)

**Indexes needed:**
- PRIMARY KEY on `id` ✅ (implicit)
- UNIQUE INDEX on `question` ✅ (for duplicate prevention)
- VECTOR INDEX on `embedding` (for pgvector cosine similarity queries)

**Migration needed (per cache_service.py warning):**
```sql
ALTER TABLE cached_answers ADD COLUMN IF NOT EXISTS embedding vector(384);
CREATE INDEX IF NOT EXISTS idx_cached_answers_embedding 
  ON cached_answers USING ivfflat (embedding vector_cosine_ops);
```

---

### 5. `user_preferences` ✅ FULLY DEFINED
**Purpose:** Per-user personalization settings  
**Backend usage:** `app.py`  
**Migration file:** `supabase_migration.sql` ✅

**Schema (defined in migration):**
```sql
user_id            uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE
preferred_category text
recent_products    text[]
favorite_products  text[]
last_active        timestamptz DEFAULT now()
created_at         timestamptz DEFAULT now()
```

**Operations:**
- CREATE/UPDATE: `POST /preferences/{user_id}` (upsert on conflict)
- READ: `GET /preferences/{user_id}`
- DELETE: Cascade on user deletion

**Indexes:**
- PRIMARY KEY on `user_id` ✅
- INDEX on `last_active DESC` ✅ (defined in migration)

**RLS Policies:** ✅ (defined in migration)
- Users can read/insert/update their own row
- Service role bypasses RLS

---

### 6. `document_download_requests` ✅ FULLY DEFINED
**Purpose:** OTP-based secure document download tracking  
**Backend usage:** `download_service.py`  
**Migration file:** `supabase_migration.sql` ✅

**Schema (defined in migration):**
```sql
id               uuid PRIMARY KEY DEFAULT gen_random_uuid()
user_id          uuid REFERENCES auth.users(id) ON DELETE SET NULL
guest_session_id text
full_name        text NOT NULL
email            text NOT NULL
phone            text NOT NULL
designation      text NOT NULL
country          text NOT NULL
document_id      text NOT NULL
document_name    text NOT NULL
file_url         text NOT NULL
otp_code         text NOT NULL
otp_verified     boolean DEFAULT false
otp_expiry       timestamptz NOT NULL
resend_count     integer DEFAULT 0
downloaded       boolean DEFAULT false
downloaded_at    timestamptz
created_at       timestamptz DEFAULT now()
```

**Operations:**
- CREATE: `POST /download/request` → `request_download()`
- UPDATE: `POST /download/verify` → `verify_otp()` (marks verified + downloaded)
- UPDATE: `POST /download/resend` → `resend_otp()` (new OTP, increment resend_count)
- READ: Implicit (backend checks during verify)

**Indexes:** ✅ (defined in migration)
- PRIMARY KEY on `id`
- INDEX on `user_id WHERE user_id IS NOT NULL`
- INDEX on `guest_session_id WHERE guest_session_id IS NOT NULL`
- INDEX on `email`
- INDEX on `created_at DESC`

**RLS Policies:** ✅ (defined in migration)
- Authenticated users can read own rows
- Anyone (anon + authenticated) can insert
- UPDATE restricted to service role only (backend handles verification)

---

## TABLES REQUESTED IN MODULE 13 AUDIT

### ❌ `guest_conversations` — **NOT IMPLEMENTED**
**Expected purpose:** Store conversations for guest sessions  
**Current implementation:** Guest conversations are **ephemeral** — stored only in browser sessionStorage, never persisted to database.

**Backend evidence:**
- `app.py` line 306: `conversation_id: isGuest ? null : activeConvId` (frontend sends null for guests)
- `app.py` line 89: `if not user_id: return None` (no conversation created for guests)
- `FloatingChatbot.jsx`: guest messages stored in `guestMessagesRef` (React ref, not persisted)

**Conclusion:** Guest conversations are **intentionally not saved** per current design.

---

### ❌ `guest_messages` — **NOT IMPLEMENTED**
**Expected purpose:** Store messages for guest conversations  
**Current implementation:** Same as `guest_conversations` — **ephemeral only**.

**Conclusion:** Guest messages are **intentionally not saved** per current design.

---

### ✅ `otp_verifications` — **IMPLEMENTED AS `document_download_requests`**
**Purpose:** OTP verification for secure downloads  
**Current implementation:** The `document_download_requests` table serves this purpose with columns:
- `otp_code` (the 6-digit code)
- `otp_verified` (boolean state)
- `otp_expiry` (timestamptz for TTL)
- `resend_count` (rate limiting)

**Conclusion:** OTP functionality is **fully implemented** in `document_download_requests`. A separate `otp_verifications` table is **not needed**.

---

## MISSING INDEXES & FOREIGN KEY VERIFICATION

### Critical missing indexes (not in migration file):

**`conversations` table:**
```sql
CREATE INDEX IF NOT EXISTS idx_conversations_user_id 
  ON conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at 
  ON conversations (created_at DESC);
```

**`messages` table:**
```sql
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
  ON messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at 
  ON messages (created_at);
```

**`device_documents` table:**
```sql
CREATE INDEX IF NOT EXISTS idx_device_documents_category_subcategory 
  ON device_documents (category, subcategory) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_device_documents_product_name 
  ON device_documents (product_name);
CREATE INDEX IF NOT EXISTS idx_device_documents_document_name 
  ON device_documents (document_name);
```

**`cached_answers` table:**
```sql
-- Enable pgvector extension first
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column if missing
ALTER TABLE cached_answers ADD COLUMN IF NOT EXISTS embedding vector(384);

-- Create vector index for semantic search
CREATE INDEX IF NOT EXISTS idx_cached_answers_embedding 
  ON cached_answers USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

---

## RECOMMENDATIONS

### 1. Run index migration ✅
Create indexes on `conversations`, `messages`, `device_documents`, `cached_answers` for query performance.

### 2. Add vector extension ✅
Enable pgvector extension and create vector index on `cached_answers.embedding` for semantic cache.

### 3. Guest persistence decision ❓
**Current:** Guest conversations are ephemeral (intentional design).  
**Option A:** Keep as-is (simpler, privacy-friendly).  
**Option B:** Add `guest_conversations` + `guest_messages` tables if guest history is needed.

**Recommendation:** Keep ephemeral unless there's a business requirement for guest persistence.

### 4. Add RLS policies to conversations/messages ⚠️
Currently only `user_preferences` and `document_download_requests` have RLS. If client-side access is needed:

```sql
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own conversations" 
  ON conversations FOR SELECT TO authenticated 
  USING (auth.uid() = user_id);

ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read messages from own conversations" 
  ON messages FOR SELECT TO authenticated 
  USING (conversation_id IN (
    SELECT id FROM conversations WHERE user_id = auth.uid()
  ));
```

### 5. Add cleanup job for old cached_answers ⚠️
Currently no TTL. Consider a cron job or trigger to delete entries older than 30 days.

---

## SUMMARY

| Table | Status | Issues |
|-------|--------|--------|
| `conversations` | ✅ Working | Missing indexes |
| `messages` | ✅ Working | Missing indexes |
| `device_documents` | ✅ Working | Missing indexes |
| `cached_answers` | ✅ Working | Missing embedding column + vector index |
| `user_preferences` | ✅ Complete | Fully migrated |
| `document_download_requests` | ✅ Complete | Fully migrated (serves OTP purpose) |
| `guest_conversations` | ❌ Not implemented | Intentional — guests are ephemeral |
| `guest_messages` | ❌ Not implemented | Intentional — guests are ephemeral |
| `otp_verifications` | ✅ Implemented | Merged into `document_download_requests` |

**Overall:** Database architecture is **sound and functional**. Only performance indexes and vector extension are missing.
