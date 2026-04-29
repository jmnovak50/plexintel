ALTER TABLE public.training_data
ADD COLUMN IF NOT EXISTS engagement_type text,
ADD COLUMN IF NOT EXISTS watch_count integer,
ADD COLUMN IF NOT EXISTS max_single_session_seconds integer,
ADD COLUMN IF NOT EXISTS total_played_seconds integer;

CREATE INDEX IF NOT EXISTS idx_training_data_user_media
ON public.training_data (username, rating_key);
