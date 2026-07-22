-- ============================================================
-- MediDevice Admin Portal — Missing Tables Migration
-- 
-- INSTRUCTIONS:
--   1. Open: https://supabase.com/dashboard/project/mykxoqthaqzimzjviyaq/sql/new
--   2. Paste this ENTIRE file into the SQL editor
--   3. Click "Run" (or press Ctrl+Enter)
--   4. Wait for "Success. No rows returned."
--   5. Run verify_migration.py to confirm everything works
-- ============================================================


-- ============================================================
-- PART 1: CREATE unanswered_queries TABLE
-- (was never created — migration file existed but was never run)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.unanswered_queries (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- The exact question text (first time seen)
    query            text        NOT NULL,

    -- Lowercase + punctuation-stripped version — deduplication key
    query_normalised text        NOT NULL UNIQUE,

    -- Who asked it most recently
    user_id          uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    is_guest         boolean     NOT NULL DEFAULT false,

    -- How many times this exact question was asked (unanswered)
    times_asked      integer     NOT NULL DEFAULT 1,

    -- Why we couldn't answer from internal KB:
    --   "Web Search Response"      → dynamic_search / wikipedia answered it
    --   "General Medical Fallback" → fallback / fallback_formatter
    --   "Out of Scope"             → guard or orchestrator rejected it
    --   "No Product Match"         → any other non-KB source
    reason           text        NOT NULL DEFAULT 'No Product Match',

    -- Admin triage workflow
    status           text        NOT NULL DEFAULT 'Pending'
                                 CHECK (status IN ('Pending', 'Reviewed', 'Resolved')),

    -- Timestamps
    first_asked_at   timestamptz NOT NULL DEFAULT now(),
    last_asked_at    timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

-- Indexes for admin portal queries (sorted by last_asked DESC, filtered by status)
CREATE INDEX IF NOT EXISTS idx_unanswered_queries_last_asked
    ON public.unanswered_queries (last_asked_at DESC);

CREATE INDEX IF NOT EXISTS idx_unanswered_queries_status
    ON public.unanswered_queries (status);

CREATE INDEX IF NOT EXISTS idx_unanswered_queries_times_asked
    ON public.unanswered_queries (times_asked DESC);

CREATE INDEX IF NOT EXISTS idx_unanswered_queries_normalised
    ON public.unanswered_queries (query_normalised);


-- ============================================================
-- PART 2: ROW-LEVEL SECURITY for unanswered_queries
-- Service role can read/write. No public access.
-- ============================================================

ALTER TABLE public.unanswered_queries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_full_access" ON public.unanswered_queries;
CREATE POLICY "service_role_full_access"
    ON public.unanswered_queries FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);


-- ============================================================
-- PART 3: ADD version COLUMN to cached_answers
-- (table exists but is missing this column — causes cache errors)
-- ============================================================

ALTER TABLE public.cached_answers
    ADD COLUMN IF NOT EXISTS version integer;

-- Backfill existing rows with version = 1
UPDATE public.cached_answers
SET    version = 1
WHERE  version IS NULL;


-- ============================================================
-- PART 4: ADD embedding COLUMN to cached_answers (if missing)
-- (may already exist — ADD COLUMN IF NOT EXISTS is safe)
-- ============================================================

-- Note: vector(384) requires pgvector extension.
-- If this line errors, comment it out — the backend handles missing embedding column.
-- ALTER TABLE public.cached_answers ADD COLUMN IF NOT EXISTS embedding vector(384);


-- ============================================================
-- PART 5: SCHEMA CACHE RELOAD
-- Forces PostgREST to pick up the new table immediately.
-- ============================================================

NOTIFY pgrst, 'reload schema';


-- ============================================================
-- PART 6: VERIFICATION — confirm everything was created
-- ============================================================

SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns c
     WHERE c.table_schema = 'public' AND c.table_name = t.table_name) AS column_count
FROM information_schema.tables t
WHERE table_schema = 'public'
  AND table_name IN ('unanswered_queries', 'cached_answers', 'contact_requests', 'query_logs')
ORDER BY table_name;

-- Show unanswered_queries columns
SELECT column_name, data_type, is_nullable, column_default
FROM   information_schema.columns
WHERE  table_schema = 'public'
  AND  table_name   = 'unanswered_queries'
ORDER  BY ordinal_position;

-- Show cached_answers columns (confirm version is present)
SELECT column_name, data_type, is_nullable
FROM   information_schema.columns
WHERE  table_schema = 'public'
  AND  table_name   = 'cached_answers'
ORDER  BY ordinal_position;
