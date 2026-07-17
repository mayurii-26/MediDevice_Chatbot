-- ============================================================
-- PHASE 5.4 – Secure Document Download Migration
-- Run once in Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- Table: secure_download_tokens
-- Stores HMAC-SHA256 hashes of single-use download tokens.
-- The raw token is NEVER stored — only the hash.
CREATE TABLE IF NOT EXISTS secure_download_tokens (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id  uuid        NOT NULL
                            REFERENCES document_download_requests(id)
                            ON DELETE CASCADE,
    token_hash  text        NOT NULL UNIQUE,   -- HMAC-SHA256 of the raw token
    expires_at  timestamptz NOT NULL,
    used        boolean     NOT NULL DEFAULT false,
    used_at     timestamptz,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Index for fast token lookups (called on every file-serve request)
CREATE INDEX IF NOT EXISTS idx_sdt_token_hash
    ON secure_download_tokens (token_hash);

-- Index for cleanup jobs (delete expired tokens)
CREATE INDEX IF NOT EXISTS idx_sdt_expires_at
    ON secure_download_tokens (expires_at);

-- Optional: auto-delete tokens older than 24 hours via pg_cron
-- (only if pg_cron extension is enabled in your Supabase project)
-- SELECT cron.schedule(
--     'cleanup-expired-tokens',
--     '0 * * * *',
--     $$DELETE FROM secure_download_tokens WHERE expires_at < now() - interval '24 hours'$$
-- );

-- Row Level Security: only service role can read/write
ALTER TABLE secure_download_tokens ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (backend uses service role key)
CREATE POLICY "service_role_full_access" ON secure_download_tokens
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Deny all access to anon / authenticated roles
-- (tokens are validated server-side only, never client-queried)
