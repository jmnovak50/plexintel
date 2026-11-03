-- Manual, additive upgrade. Joint generations and their training rows remain
-- historical data; their vectors are never converted into independent vectors.
ALTER TABLE embedding_v2.items DROP CONSTRAINT IF EXISTS items_kind_check;
ALTER TABLE embedding_v2.items ADD CONSTRAINT items_kind_check
    CHECK(kind IN ('media','media_text','media_poster','watch','user'));
ALTER TABLE embedding_v2.items DROP CONSTRAINT IF EXISTS items_status_check;
ALTER TABLE embedding_v2.items ADD CONSTRAINT items_status_check
    CHECK(status IN ('pending','succeeded','failed','missing'));
ALTER TABLE embedding_v2.items ADD COLUMN IF NOT EXISTS modality_contract_hash text;
ALTER TABLE embedding_v2.items ADD COLUMN IF NOT EXISTS provenance jsonb;
ALTER TABLE embedding_v2.preparations DROP CONSTRAINT IF EXISTS preparations_kind_check;
ALTER TABLE embedding_v2.preparations ADD CONSTRAINT preparations_kind_check CHECK(kind IN ('media','media_text'));
ALTER TABLE embedding_v2.preparations ALTER COLUMN kind SET DEFAULT 'media_text';
CREATE TABLE IF NOT EXISTS embedding_v2.modality_training_rows (
    generation_id text NOT NULL REFERENCES embedding_v2.generations,
    owner text NOT NULL,
    media_key text NOT NULL,
    prediction_at timestamptz NOT NULL,
    label_available_at timestamptz NOT NULL,
    label integer NOT NULL CHECK(label IN (0,1)),
    media_text public.vector(768) NOT NULL,
    media_poster public.vector(768),
    user_embedding public.vector(768) NOT NULL,
    features jsonb NOT NULL,
    dependencies jsonb NOT NULL,
    PRIMARY KEY(generation_id,owner,media_key),
    CHECK(features ? 'poster_missing' AND jsonb_typeof(features->'poster_missing')='boolean'
        AND (media_poster IS NULL) = ((features->>'poster_missing')::boolean))
);
REVOKE ALL ON ALL TABLES IN SCHEMA embedding_v2 FROM PUBLIC;
CREATE TABLE IF NOT EXISTS embedding_v2.operator_reviews (
    review_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generation_id text NOT NULL REFERENCES embedding_v2.generations,
    gate text NOT NULL CHECK(gate IN ('text','poster','profiles','quality')),
    state_hash text NOT NULL,
    missing_art_limit integer NOT NULL DEFAULT 0 CHECK(missing_art_limit>=0),
    reason text NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS embedding_v2.stage_runs (
    run_id text PRIMARY KEY,
    generation_id text NOT NULL REFERENCES embedding_v2.generations,
    stage text NOT NULL,
    status text NOT NULL CHECK(status IN ('running','succeeded','failed','interrupted')),
    metrics jsonb NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);
CREATE TABLE IF NOT EXISTS embedding_v2.inference_requests (
    request_id text PRIMARY KEY,
    generation_id text NOT NULL,
    kind text NOT NULL CHECK(kind IN ('media_text','media_poster','watch')),
    item_key text NOT NULL,
    input_hash text NOT NULL,
    status text NOT NULL CHECK(status IN ('succeeded','failed','interrupted')),
    stats jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY(generation_id,kind,item_key) REFERENCES embedding_v2.items(generation_id,kind,item_key)
);
CREATE TABLE IF NOT EXISTS embedding_v2.preparation_attempts (
    attempt_id text PRIMARY KEY,
    generation_id text NOT NULL REFERENCES embedding_v2.generations,
    item_key text NOT NULL,
    stage text NOT NULL CHECK(stage IN ('metadata','poster')),
    status text NOT NULL CHECK(status IN ('succeeded','failed')),
    content_hash text,
    timing jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON ALL TABLES IN SCHEMA embedding_v2 FROM PUBLIC;
