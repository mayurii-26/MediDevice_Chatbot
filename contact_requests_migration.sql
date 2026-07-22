-- ============================================================
-- Admin Portal — contact_requests table migration
-- Run once in Supabase SQL Editor
-- (Dashboard → SQL Editor → New query → paste → Run)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.contact_requests (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text        NOT NULL,
    email       text        NOT NULL,
    phone       text        NOT NULL DEFAULT '',
    hospital    text        NOT NULL DEFAULT '',
    message     text        NOT NULL,
    reason      text        NOT NULL DEFAULT 'General Inquiry',
    status      text        NOT NULL DEFAULT 'Pending'
                            CHECK (status IN ('Pending', 'In Progress', 'Resolved')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_contact_requests_status
    ON public.contact_requests (status);

CREATE INDEX IF NOT EXISTS idx_contact_requests_created_at
    ON public.contact_requests (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_contact_requests_email
    ON public.contact_requests (email);

-- RLS: service role has full access; anon/authenticated can only insert
ALTER TABLE public.contact_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anyone can submit contact request" ON public.contact_requests;
DROP POLICY IF EXISTS "Service role full access"          ON public.contact_requests;

CREATE POLICY "Anyone can submit contact request"
    ON public.contact_requests FOR INSERT
    TO anon, authenticated
    WITH CHECK (true);

CREATE POLICY "Service role full access"
    ON public.contact_requests FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Verification
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name = 'contact_requests';
