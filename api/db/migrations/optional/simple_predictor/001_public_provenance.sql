-- Operator-applied during the separately approved cutover, never at job startup.
-- One current provenance record per existing vector; no lifecycle tables.
ALTER TABLE public.media_embeddings ADD COLUMN IF NOT EXISTS provenance jsonb;
ALTER TABLE public.watch_embeddings ADD COLUMN IF NOT EXISTS provenance jsonb;
ALTER TABLE public.user_embeddings ADD COLUMN IF NOT EXISTS provenance jsonb;
-- Drop the obsolete fixed typmod without replacing any stored vector values.
ALTER TABLE public.training_data ALTER COLUMN embedding TYPE public.vector;
ALTER TABLE public.training_data ADD COLUMN IF NOT EXISTS sample_weight double precision;
ALTER TABLE public.training_data ADD COLUMN IF NOT EXISTS diagnostics jsonb;
ALTER TABLE public.embedding_labels ADD COLUMN IF NOT EXISTS feature_space_id text;
ALTER TABLE public.embedding_label_batches ADD COLUMN IF NOT EXISTS feature_space_id text;
ALTER TABLE public.embedding_label_batches ALTER COLUMN generation_id DROP NOT NULL;
-- Existing source keys are the current-store identities. Fail on duplicate
-- legacy vectors rather than silently choosing or deleting one at cutover.
CREATE UNIQUE INDEX IF NOT EXISTS predictor_media_key ON public.media_embeddings(rating_key);
CREATE UNIQUE INDEX IF NOT EXISTS predictor_watch_key ON public.watch_embeddings(watch_id);
CREATE UNIQUE INDEX IF NOT EXISTS predictor_user_key ON public.user_embeddings(username);
