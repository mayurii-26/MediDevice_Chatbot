-- ============================================================
-- PHASE 5.5 – Document Download Rate Limit Migration
-- Run once in Supabase SQL Editor (Dashboard → SQL Editor)
-- No new table required — uses existing document_download_requests
-- ============================================================

-- Fast index for the 24-hour rate-limit query:
--   WHERE user_id = $1
--     AND otp_verified = true
--     AND downloaded = true
--     AND downloaded_at >= now() - interval '24 hours'
CREATE INDEX IF NOT EXISTS idx_ddr_user_downloads_24h
    ON document_download_requests (user_id, downloaded_at)
    WHERE otp_verified = true AND downloaded = true;

-- ============================================================
-- Verification query (run after applying migration):
-- Should return your index in the result set.
-- ============================================================
-- SELECT indexname, indexdef
--   FROM pg_indexes
--  WHERE tablename = 'document_download_requests'
--    AND indexname  = 'idx_ddr_user_downloads_24h';
