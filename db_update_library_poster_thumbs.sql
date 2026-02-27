BEGIN;

ALTER TABLE public.library
    ADD COLUMN IF NOT EXISTS thumb_path text;

ALTER TABLE public.library
    ADD COLUMN IF NOT EXISTS parent_thumb_path text;

ALTER TABLE public.library
    ADD COLUMN IF NOT EXISTS grandparent_thumb_path text;

COMMIT;
