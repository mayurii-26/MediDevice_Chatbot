-- ============================================================
-- Admin Portal Analytics — DB Event Tracking Migration
-- Run once in Supabase SQL Editor
-- (Dashboard → SQL Editor → New query → paste → Run)
-- ============================================================


-- ── TABLE 1: query_logs ──────────────────────────────────────────────────
-- Every chatbot query, one row per request.
-- Replaces search_logs.txt as the authoritative analytics source.

CREATE TABLE IF NOT EXISTS public.query_logs (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    question        text        NOT NULL,
    intent          text        NOT NULL DEFAULT 'unknown',
    answer_source   text        NOT NULL DEFAULT 'unknown',
    -- answer_source values: faiss | bm25 | cache | wikipedia | dynamic_search
    --                       gemini | fallback_formatter | fallback | out_of_scope
    --                       purchase_intent_guard | sample_report_intent_guard
    conversation_id uuid        REFERENCES conversations(id) ON DELETE SET NULL,
    user_id         uuid        REFERENCES auth.users(id)    ON DELETE SET NULL,
    is_guest        boolean     NOT NULL DEFAULT false,
    confidence      float       NOT NULL DEFAULT 0.0,
    matched_product text,
    matched_category text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_query_logs_created_at
    ON public.query_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_query_logs_user_id
    ON public.query_logs (user_id)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_query_logs_intent
    ON public.query_logs (intent);

CREATE INDEX IF NOT EXISTS idx_query_logs_answer_source
    ON public.query_logs (answer_source);

CREATE INDEX IF NOT EXISTS idx_query_logs_matched_product
    ON public.query_logs (matched_product)
    WHERE matched_product IS NOT NULL;


-- ── TABLE 2: product_search_logs ─────────────────────────────────────────
-- Aggregated search count per product. One row per product — upserted.

CREATE TABLE IF NOT EXISTS public.product_search_logs (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    product_name    text        NOT NULL UNIQUE,
    search_count    integer     NOT NULL DEFAULT 1,
    last_searched   timestamptz NOT NULL DEFAULT now(),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_search_logs_product_name
    ON public.product_search_logs (product_name);

CREATE INDEX IF NOT EXISTS idx_product_search_logs_search_count
    ON public.product_search_logs (search_count DESC);


-- ── TABLE 3: comparison_logs ─────────────────────────────────────────────
-- Every comparison query, with comma-separated products compared.

CREATE TABLE IF NOT EXISTS public.comparison_logs (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    products_compared   text        NOT NULL,
    -- comma-separated, e.g. "PageWriter TC50, PageWriter TC70"
    user_id             uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    conversation_id     uuid        REFERENCES conversations(id) ON DELETE SET NULL,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comparison_logs_created_at
    ON public.comparison_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_comparison_logs_products
    ON public.comparison_logs (products_compared);


-- ── TABLE 4: specification_logs ──────────────────────────────────────────
-- Every specification query, one row per request.

CREATE TABLE IF NOT EXISTS public.specification_logs (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    product_name    text        NOT NULL,
    user_id         uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    conversation_id uuid        REFERENCES conversations(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_specification_logs_created_at
    ON public.specification_logs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_specification_logs_product_name
    ON public.specification_logs (product_name);


-- ── RLS: all analytics tables are service-role write, no public read ─────

ALTER TABLE public.query_logs            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.product_search_logs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comparison_logs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.specification_logs    ENABLE ROW LEVEL SECURITY;

-- Service role has full access to all analytics tables
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'query_logs', 'product_search_logs',
        'comparison_logs', 'specification_logs'
    ]
    LOOP
        EXECUTE format(
            'DROP POLICY IF EXISTS "service_role_full_access" ON public.%I;
             CREATE POLICY "service_role_full_access" ON public.%I
                 FOR ALL TO service_role USING (true) WITH CHECK (true);',
            tbl, tbl
        );
    END LOOP;
END $$;


-- ── Verification ─────────────────────────────────────────────────────────
SELECT table_name
FROM   information_schema.tables
WHERE  table_schema = 'public'
  AND  table_name   IN (
    'query_logs', 'product_search_logs',
    'comparison_logs', 'specification_logs'
  )
ORDER BY table_name;
