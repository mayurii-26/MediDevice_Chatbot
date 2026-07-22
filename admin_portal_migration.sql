-- ============================================================
-- Admin Portal Improvements Migration
-- Run once in Supabase SQL Editor
-- (Dashboard → SQL Editor → New query → paste → Run)
-- ============================================================

-- ── 1. Add new columns to contact_requests ──────────────────────────────
--
--  address         : full address text (street, city, state, country)
--  submission_type : which form submitted this — "General Support",
--                   "Pricing & Purchasing", "Sample Report Request", etc.
--
-- These are nullable so existing rows are not broken.

ALTER TABLE public.contact_requests
    ADD COLUMN IF NOT EXISTS address         text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS submission_type text NOT NULL DEFAULT 'General Support';

-- Index on submission_type for admin filtering
CREATE INDEX IF NOT EXISTS idx_contact_requests_submission_type
    ON public.contact_requests (submission_type);


-- ── 2. Verify contact_requests schema ───────────────────────────────────
SELECT column_name, data_type, is_nullable, column_default
FROM   information_schema.columns
WHERE  table_schema = 'public'
  AND  table_name   = 'contact_requests'
ORDER  BY ordinal_position;


-- ── 3. Backfill any nulls on old rows ───────────────────────────────────
UPDATE public.contact_requests
SET    address         = ''               WHERE address IS NULL;

UPDATE public.contact_requests
SET    submission_type = 'General Support' WHERE submission_type IS NULL;


-- ── 4. Verify final table structure ─────────────────────────────────────
SELECT table_name
FROM   information_schema.tables
WHERE  table_schema = 'public'
  AND  table_name   = 'contact_requests';
