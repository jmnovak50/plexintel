-- Additive; no historical evidence or model associations are inferred.
CREATE TABLE IF NOT EXISTS public.embedding_feature_config (
    config_id text PRIMARY KEY,
    metadata jsonb NOT NULL,
    active boolean NOT NULL DEFAULT false,
    registered_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS embedding_feature_config_active
    ON public.embedding_feature_config (active) WHERE active;
CREATE TABLE IF NOT EXISTS public.embedding_dimension_admin (
    config_id text NOT NULL REFERENCES public.embedding_feature_config(config_id),
    dimension integer NOT NULL,
    paused boolean NOT NULL DEFAULT false,
    suppressed boolean NOT NULL DEFAULT false,
    investigation_reason text,
    investigation_status text NOT NULL DEFAULT 'clear',
    version integer NOT NULL DEFAULT 0,
    PRIMARY KEY (config_id, dimension)
);
CREATE TABLE IF NOT EXISTS public.embedding_dimension_actions (
    action_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    config_id text NOT NULL,
    dimension integer NOT NULL,
    actor text NOT NULL,
    action text NOT NULL,
    reason text NOT NULL,
    before_state jsonb NOT NULL,
    after_state jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dimension_actions_history
    ON public.embedding_dimension_actions(config_id, dimension, action_id DESC);
CREATE TABLE IF NOT EXISTS public.embedding_dimension_reviews (
    review_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    config_id text NOT NULL,
    dimension integer NOT NULL,
    requested_by text NOT NULL,
    reason text NOT NULL,
    status text NOT NULL DEFAULT 'queued',
    requested_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    outcome text,
    error text
);
CREATE UNIQUE INDEX IF NOT EXISTS dimension_review_pending
    ON public.embedding_dimension_reviews(config_id, dimension)
    WHERE status IN ('queued', 'running');
CREATE TABLE IF NOT EXISTS public.embedding_dimension_assessments (
    assessment_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    config_id text NOT NULL,
    dimension integer NOT NULL,
    source text NOT NULL,
    provider text,
    model text,
    prompt jsonb NOT NULL,
    result jsonb NOT NULL,
    saved boolean NOT NULL,
    outcome text NOT NULL,
    before_state jsonb,
    after_state jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dimension_assessment_history
    ON public.embedding_dimension_assessments(config_id, dimension, assessment_id DESC);
CREATE INDEX IF NOT EXISTS shap_dimension_prediction
    ON public.shap_impact(dimension, user_id, rating_key) INCLUDE (shap_value, modified_at);
CREATE INDEX IF NOT EXISTS recommendations_user_score_explorer
    ON public.recommendations(username, predicted_probability DESC, rating_key);

-- One selection implementation for API groups, legacy semantic themes and explorer.
-- Dimensions attribute a selected wording; they do not multiply its display count.
CREATE OR REPLACE FUNCTION public.selected_embedding_labels(
    prediction_user text, prediction_title integer,
    dimension_start integer DEFAULT 0, dimension_end integer DEFAULT 2147483647,
    label_limit integer DEFAULT 3
) RETURNS TABLE(display_label text, max_shap double precision, dimensions integer[])
LANGUAGE sql STABLE AS $$
    SELECT el.display_label, MAX(si.shap_value), ARRAY_AGG(DISTINCT si.dimension)
    FROM public.shap_impact si
    JOIN public.embedding_labels el ON el.dimension = si.dimension
    WHERE si.user_id = prediction_user AND si.rating_key = prediction_title
      AND si.dimension >= dimension_start AND si.dimension < dimension_end
      AND si.shap_value > 0 AND el.explainable IS TRUE
      AND COALESCE(el.needs_review, false) IS NOT TRUE
      AND el.display_label IS NOT NULL AND BTRIM(el.display_label) <> ''
      AND NOT EXISTS (
          SELECT 1 FROM public.embedding_dimension_admin a
          JOIN public.embedding_feature_config c USING(config_id)
          WHERE c.active AND a.dimension = si.dimension AND a.suppressed
      )
    GROUP BY el.display_label
    ORDER BY MAX(si.shap_value) DESC
    LIMIT label_limit
$$;

-- Prospective only: populated alongside new SHAP writes, never backfilled.
CREATE TABLE IF NOT EXISTS public.shap_prediction_context (
    username text NOT NULL,
    rating_key integer NOT NULL,
    config_id text NOT NULL,
    model_version text NOT NULL,
    scored_at timestamp NOT NULL,
    generated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(username, rating_key)
);
CREATE INDEX IF NOT EXISTS shap_context_configuration_model
    ON public.shap_prediction_context(config_id, model_version, username, rating_key);
ALTER TABLE public.embedding_dimension_assessments
    ADD COLUMN IF NOT EXISTS review_id bigint REFERENCES public.embedding_dimension_reviews(review_id);
CREATE INDEX IF NOT EXISTS dimension_assessment_request
    ON public.embedding_dimension_assessments(review_id) WHERE review_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS dimension_label_lookup
    ON public.embedding_labels(dimension, updated_at DESC);
CREATE INDEX IF NOT EXISTS dimension_review_history
    ON public.embedding_dimension_reviews(config_id, dimension, review_id DESC);
