-- =============================================================================
-- MediDevice Chatbot — Index & Performance Migration
-- Run this in Supabase SQL Editor after the main migration
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 1: Enable pgvector extension for semantic cache
-- ─────────────────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS vector;


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 2: Add embedding column to cached_answers (if missing)
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.cached_answers 
  ADD COLUMN IF NOT EXISTS embedding vector(384);


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 3: Create indexes on conversations table
-- ─────────────────────────────────────────────────────────────────────────────

-- Fast lookup of user's conversations
CREATE INDEX IF NOT EXISTS idx_conversations_user_id 
  ON public.conversations (user_id);

-- Fast ordered listing (most recent first)
CREATE INDEX IF NOT EXISTS idx_conversations_created_at 
  ON public.conversations (created_at DESC);


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 4: Create indexes on messages table
-- ─────────────────────────────────────────────────────────────────────────────

-- Fast lookup of messages in a conversation
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id 
  ON public.messages (conversation_id);

-- Fast ordered message listing (chronological)
CREATE INDEX IF NOT EXISTS idx_messages_created_at 
  ON public.messages (created_at);


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 5: Create indexes on device_documents table
-- ─────────────────────────────────────────────────────────────────────────────

-- Fast lookup by category/subcategory for document library browsing
CREATE INDEX IF NOT EXISTS idx_device_documents_category_subcategory 
  ON public.device_documents (category, subcategory) 
  WHERE is_active = true;

-- Fast product name searches (used in get_documents_by_product)
CREATE INDEX IF NOT EXISTS idx_device_documents_product_name 
  ON public.device_documents (product_name);

-- Fast document name lookups (used in get_documents_by_names)
CREATE INDEX IF NOT EXISTS idx_device_documents_document_name 
  ON public.device_documents (document_name);

-- Active documents filter
CREATE INDEX IF NOT EXISTS idx_device_documents_is_active 
  ON public.device_documents (is_active);


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 6: Create vector index on cached_answers for semantic search
-- ─────────────────────────────────────────────────────────────────────────────

-- IVFFlat index for fast approximate nearest neighbor search
-- lists parameter: sqrt(total_rows) is a good starting point, 100 is safe default
CREATE INDEX IF NOT EXISTS idx_cached_answers_embedding 
  ON public.cached_answers 
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);


-- ─────────────────────────────────────────────────────────────────────────────
-- STEP 7: Verify all indexes were created
-- ─────────────────────────────────────────────────────────────────────────────

-- Run this to confirm:
SELECT 
  schemaname,
  tablename,
  indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN (
    'conversations',
    'messages', 
    'device_documents',
    'cached_answers',
    'user_preferences',
    'document_download_requests'
  )
ORDER BY tablename, indexname;


-- =============================================================================
-- OPTIONAL: Row Level Security for conversations & messages
-- Only needed if client-side (anon key) direct access is required.
-- Currently backend uses service role key which bypasses RLS.
-- =============================================================================

-- Uncomment if needed:
/*
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own conversations" ON public.conversations;
CREATE POLICY "Users can read own conversations" 
  ON public.conversations FOR SELECT 
  TO authenticated 
  USING (auth.uid() = user_id);

ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read messages from own conversations" ON public.messages;
CREATE POLICY "Users can read messages from own conversations" 
  ON public.messages FOR SELECT 
  TO authenticated 
  USING (
    conversation_id IN (
      SELECT id FROM conversations WHERE user_id = auth.uid()
    )
  );
*/
