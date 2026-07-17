-- =============================================================================
-- MediDevice Chatbot — Database Migration
-- Run this entire script once in the Supabase SQL Editor
-- (Dashboard → SQL Editor → New query → paste → Run)
-- =============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE 1: user_preferences
-- Stores per-user personalisation: preferred category, recent products, etc.
-- One row per authenticated user (upserted on every preference update).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.user_preferences (
    user_id            uuid        PRIMARY KEY
                                   REFERENCES auth.users(id) ON DELETE CASCADE,
    preferred_category text,
    recent_products    text[]      DEFAULT '{}',
    favorite_products  text[]      DEFAULT '{}',
    last_active        timestamptz DEFAULT now(),
    created_at         timestamptz DEFAULT now()
);

-- Index: fast lookup by user_id (already covered by PK, but explicit for clarity)
-- Additional index on last_active for future analytics queries
CREATE INDEX IF NOT EXISTS idx_user_preferences_last_active
    ON public.user_preferences (last_active DESC);

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;

-- Drop existing policies before recreating (safe on first run too)
DROP POLICY IF EXISTS "Users can read own preferences"   ON public.user_preferences;
DROP POLICY IF EXISTS "Users can insert own preferences" ON public.user_preferences;
DROP POLICY IF EXISTS "Users can update own preferences" ON public.user_preferences;
DROP POLICY IF EXISTS "Service role has full access"     ON public.user_preferences;

-- Authenticated users: full access to their own row only
CREATE POLICY "Users can read own preferences"
    ON public.user_preferences FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own preferences"
    ON public.user_preferences FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own preferences"
    ON public.user_preferences FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Service role (used by the FastAPI backend with SUPABASE_SERVICE_ROLE_KEY)
-- bypasses RLS automatically, so no explicit policy is needed for it.
-- The policies above protect direct client access via the anon key.


-- ─────────────────────────────────────────────────────────────────────────────
-- TABLE 2: document_download_requests
-- Stores every download request with OTP state.
-- Works for both authenticated users (user_id) and guests (guest_session_id).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.document_download_requests (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Nullable: NULL for guest downloads
    user_id          uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    -- Present for guest sessions (format: "guest_<uuid>")
    guest_session_id text,
    -- Requester details (collected via the info form in DownloadModal)
    full_name        text        NOT NULL,
    email            text        NOT NULL,
    phone            text        NOT NULL,
    designation      text        NOT NULL,
    country          text        NOT NULL,
    -- Document being requested
    document_id      text        NOT NULL,
    document_name    text        NOT NULL,
    file_url         text        NOT NULL,
    -- OTP state machine
    otp_code         text        NOT NULL,
    otp_verified     boolean     NOT NULL DEFAULT false,
    otp_expiry       timestamptz NOT NULL,
    resend_count     integer     NOT NULL DEFAULT 0,
    -- Download tracking
    downloaded       boolean     NOT NULL DEFAULT false,
    downloaded_at    timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_ddr_user_id
    ON public.document_download_requests (user_id)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ddr_guest_session_id
    ON public.document_download_requests (guest_session_id)
    WHERE guest_session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ddr_email
    ON public.document_download_requests (email);

CREATE INDEX IF NOT EXISTS idx_ddr_created_at
    ON public.document_download_requests (created_at DESC);

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE public.document_download_requests ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can read own download requests" ON public.document_download_requests;
DROP POLICY IF EXISTS "Anyone can insert download requests"  ON public.document_download_requests;

-- Authenticated users can see their own rows
CREATE POLICY "Users can read own download requests"
    ON public.document_download_requests FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- Both guests (anon) and authenticated users can insert new requests.
-- The OTP is generated server-side and never returned to the client directly.
CREATE POLICY "Anyone can insert download requests"
    ON public.document_download_requests FOR INSERT
    TO anon, authenticated
    WITH CHECK (true);

-- NOTE: UPDATE and DELETE are intentionally restricted to the service role only.
-- The backend (service role key) handles OTP verification and marking downloaded.


-- =============================================================================
-- Verification queries — run after migration to confirm tables exist
-- =============================================================================

-- Should return 1 row for each table
SELECT table_name, table_type
FROM   information_schema.tables
WHERE  table_schema = 'public'
  AND  table_name   IN ('user_preferences', 'document_download_requests')
ORDER  BY table_name;
