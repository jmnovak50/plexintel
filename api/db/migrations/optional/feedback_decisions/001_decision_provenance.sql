-- Additive, operator-applied before deploying the feedback writer. No backfill,
-- historical edits, new table, or change to recommendation suppression.
ALTER TABLE public.user_feedback ADD COLUMN IF NOT EXISTS decision_provenance jsonb;
