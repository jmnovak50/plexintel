BEGIN;

-- Dimension 1385 is a user-preference dimension whose saved label has been
-- observed covering too many recommendation cards. Depublish it from
-- user-facing explanation chips while keeping the raw label row for review.

ALTER TABLE IF EXISTS public.embedding_labels
    ADD COLUMN IF NOT EXISTS explainable boolean,
    ADD COLUMN IF NOT EXISTS needs_review boolean DEFAULT false,
    ADD COLUMN IF NOT EXISTS updated_at timestamp without time zone DEFAULT now(),
    ADD COLUMN IF NOT EXISTS last_reviewed_at timestamp without time zone,
    ADD COLUMN IF NOT EXISTS review_attempt_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS next_review_at timestamp without time zone;

ALTER TABLE IF EXISTS public.embedding_label_history
    ADD COLUMN IF NOT EXISTS old_needs_review boolean,
    ADD COLUMN IF NOT EXISTS old_last_reviewed_at timestamp without time zone,
    ADD COLUMN IF NOT EXISTS old_review_attempt_count integer,
    ADD COLUMN IF NOT EXISTS old_next_review_at timestamp without time zone;

DO $$
BEGIN
    IF to_regclass('public.embedding_label_history') IS NOT NULL THEN
        INSERT INTO public.embedding_label_history (
            dimension,
            old_label,
            old_label_type,
            old_explainable,
            old_display_label,
            old_needs_review,
            old_last_reviewed_at,
            old_review_attempt_count,
            old_next_review_at,
            new_label,
            change_reason,
            changed_at
        )
        SELECT
            dimension,
            label,
            label_type,
            explainable,
            display_label,
            needs_review,
            last_reviewed_at,
            review_attempt_count,
            next_review_at,
            label,
            'manual_depublish:overbroad_user_dimension_1385',
            NOW()
        FROM public.embedding_labels
        WHERE dimension = 1385
          AND (
              explainable IS TRUE
              OR COALESCE(needs_review, false) IS NOT TRUE
          );
    END IF;
END $$;

UPDATE public.embedding_labels
SET
    explainable = FALSE,
    needs_review = TRUE,
    next_review_at = NULL,
    updated_at = NOW()
WHERE dimension = 1385;

COMMIT;
