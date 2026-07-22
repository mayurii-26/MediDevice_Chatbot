-- ============================================================
-- unanswered_queries table
-- Healthcare-only queries that the chatbot could not resolve.
-- Deduplicated by normalised question text — times_asked increments.
-- Run once in Supabase SQL Editor.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.unanswered_queries (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- The exact question text (first time seen)
    query           text        NOT NULL,

    -- Lowercase-trimmed version used as the dedup key
    query_normalised text       NOT NULL UNIQUE,

    -- Who asked it most recently
    user_id         uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    is_guest        boolean     NOT NULL DEFAULT false,

    -- How many times this exact question was asked (unanswered)
    times_asked     integer     NOT NULL DEFAULT 1,

    -- Why we couldn't answer: "No Knowledge Match" | "Low Confidence" | "Unknown Device"
    reason          text        NOT NULL DEFAULT 'No Knowledge Match',

    -- Admin triage workflow
    status          text        NOT NULL DEFAULT 'Pending'
                                CHECK (status IN ('Pending', 'Reviewed', 'Resolved')),

    -- Timestamps
    first_asked_at  timestamptz NOT NULL DEFAULT now(),
    last_asked_at   timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_unanswered_queries_last_asked
    ON public.unanswered_queries (last_asked_at DESC);

CREATE INDEX IF NOT EXISTS idx_unanswered_queries_status
    ON public.unanswered_queries (status);

CREATE INDEX IF NOT EXISTS idx_unanswered_queries_times_asked
    ON public.unanswered_queries (times_asked DESC);

CREATE INDEX IF NOT EXISTS idx_unanswered_queries_normalised
    ON public.unanswered_queries (query_normalised);

-- RLS: service role writes; no public read
ALTER TABLE public.unanswered_queries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_full_access" ON public.unanswered_queries;
CREATE POLICY "service_role_full_access"
    ON public.unanswered_queries FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Verification
SELECT table_name, column_name, data_type
FROM   information_schema.columns
WHERE  table_schema = 'public'
  AND  table_name   = 'unanswered_queries'
ORDER  BY ordinal_position;
