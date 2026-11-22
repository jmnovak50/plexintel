-- Explicit operator application only; intentionally outside the startup glob.
SET LOCAL lock_timeout = '5s';
CREATE TABLE public.metadata_ingestion_events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    operation_id uuid NOT NULL,
    rating_key integer NOT NULL CHECK (rating_key > 0),
    operation text NOT NULL CHECK (operation IN ('ingest','complete','correct')),
    outcome text NOT NULL CHECK (outcome IN ('applied','failed')),
    contract_version text NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT statement_timestamp(),
    source_observed_at timestamptz,
    operator text NOT NULL,
    reason text NOT NULL,
    before_hash text,
    after_hash text,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    changes jsonb NOT NULL DEFAULT '{}'::jsonb
);
-- No FK: failed titles may not exist and pipeline logs may be pruned.
CREATE INDEX metadata_ingestion_title_idx
    ON public.metadata_ingestion_events(rating_key,event_id DESC);
CREATE UNIQUE INDEX metadata_ingestion_applied_operation_idx
    ON public.metadata_ingestion_events(operation_id,rating_key)
    WHERE outcome='applied';
COMMENT ON TABLE public.metadata_ingestion_events IS
    'Append-only application receipts; absence of acceptance evidence means historical completeness unknown. No legacy seeding.';
