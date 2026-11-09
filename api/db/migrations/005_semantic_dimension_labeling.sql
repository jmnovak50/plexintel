-- Coordinate interpretations are scoped to an encoder generation, never inferred
-- from the integer dimension alone. Historical labels remain unassociated.
ALTER TABLE public.embedding_labels ADD COLUMN IF NOT EXISTS config_id text;
ALTER TABLE public.embedding_labels ADD COLUMN IF NOT EXISTS generation_id text;
ALTER TABLE public.embedding_labels ADD COLUMN IF NOT EXISTS contract_hash text;
ALTER TABLE public.embedding_labels ADD COLUMN IF NOT EXISTS encoder_digest text;
ALTER TABLE public.embedding_labels ADD COLUMN IF NOT EXISTS interpretation_model text;

CREATE TABLE IF NOT EXISTS public.embedding_label_batches (
    batch_id text PRIMARY KEY,
    config_id text NOT NULL,
    generation_id text NOT NULL,
    model text NOT NULL,
    dimensions jsonb NOT NULL,
    forecast jsonb NOT NULL,
    pricing jsonb NOT NULL,
    budget_usd numeric,
    status text NOT NULL DEFAULT 'running',
    summary jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS public.embedding_label_requests (
    request_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id text NOT NULL REFERENCES public.embedding_label_batches(batch_id),
    dimension integer NOT NULL CHECK(dimension BETWEEN 0 AND 1535),
    side text NOT NULL CHECK(side IN ('media','user')),
    attempt integer NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    input_tokens bigint,
    cached_input_tokens bigint,
    output_tokens bigint,
    estimated_input_tokens bigint NOT NULL,
    reserved_input_tokens bigint NOT NULL,
    reserved_output_tokens bigint NOT NULL,
    estimated_cost_usd numeric NOT NULL,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
CREATE INDEX IF NOT EXISTS dimension_label_batch_usage
    ON public.embedding_label_requests(batch_id,request_id);

CREATE OR REPLACE FUNCTION public.selected_embedding_labels(
    prediction_user text, prediction_title integer,
    dimension_start integer DEFAULT 0, dimension_end integer DEFAULT 2147483647,
    label_limit integer DEFAULT 3
) RETURNS TABLE(display_label text, max_shap double precision, dimensions integer[])
LANGUAGE sql STABLE AS $$
    SELECT el.display_label, MAX(si.shap_value), ARRAY_AGG(DISTINCT si.dimension)
    FROM public.shap_impact si
    JOIN public.embedding_labels el ON el.dimension=si.dimension
    JOIN public.embedding_feature_config c ON c.active
    WHERE si.user_id=prediction_user AND si.rating_key=prediction_title
      AND si.dimension>=dimension_start AND si.dimension<dimension_end
      AND si.shap_value>0 AND el.explainable IS TRUE
      AND COALESCE(el.needs_review,false) IS NOT TRUE
      AND NULLIF(BTRIM(el.display_label),'') IS NOT NULL
      AND (c.metadata->>'generation_id' IS NULL OR (
          c.metadata->>'ordering'='media_text,user'
          AND el.config_id=c.config_id
          AND el.generation_id=c.metadata->>'generation_id'
          AND el.contract_hash=c.metadata->>'contract_hash'
          AND el.encoder_digest=c.metadata->>'encoder_digest'
          AND EXISTS (
              SELECT 1 FROM public.shap_prediction_context context
              JOIN public.recommendations r ON r.username=context.username
                  AND r.rating_key=context.rating_key AND r.scored_at=context.scored_at
              WHERE context.username=prediction_user AND context.rating_key=prediction_title
                AND context.config_id=c.config_id
                AND context.model_version=c.metadata->>'model_sha256'
          )
      ))
      AND NOT EXISTS (
          SELECT 1 FROM public.embedding_dimension_admin a
          WHERE a.config_id=c.config_id AND a.dimension=si.dimension AND a.suppressed
      )
    GROUP BY el.display_label ORDER BY MAX(si.shap_value) DESC LIMIT label_limit
$$;
