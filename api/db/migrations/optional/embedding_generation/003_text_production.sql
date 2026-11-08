-- Operator-installed only. No startup installation or live data changes.
CREATE TABLE IF NOT EXISTS embedding_v2.text_training_rows (
    generation_id text NOT NULL REFERENCES embedding_v2.generations,
    owner text NOT NULL,
    media_key text NOT NULL,
    prediction_at timestamptz NOT NULL,
    label_available_at timestamptz NOT NULL,
    label integer NOT NULL CHECK(label IN (0,1)),
    embedding public.vector(1536) NOT NULL,
    features jsonb NOT NULL,
    dependencies jsonb NOT NULL,
    PRIMARY KEY(generation_id,owner,media_key)
);
-- Canonical production model/context, independent of shadow artifact lookup.
-- Vectors remain physically in public.media/watch/user_embeddings.
CREATE TABLE IF NOT EXISTS embedding_v2.production_state (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    generation_id text NOT NULL,
    contract jsonb NOT NULL,
    contract_hash text NOT NULL,
    snapshot jsonb NOT NULL,
    source_hash text NOT NULL,
    expected jsonb NOT NULL,
    model_sha256 text NOT NULL,
    model_bundle bytea NOT NULL,
    evaluation jsonb NOT NULL,
    published_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS embedding_v2.production_inputs (
    kind text NOT NULL CHECK(kind IN ('media_text','watch','user')),
    item_key text NOT NULL,
    record jsonb NOT NULL,
    PRIMARY KEY(kind,item_key)
);
-- Verified pre-transition model/control/context archive for C-to-B and rollback.
CREATE TABLE IF NOT EXISTS embedding_v2.production_rollback (
    promotion_id text PRIMARY KEY REFERENCES embedding_v2.promotions,
    control jsonb NOT NULL,
    state jsonb,
    inputs jsonb NOT NULL,
    model_bundle bytea,
    manifest_sha256 text NOT NULL
);
REVOKE ALL ON embedding_v2.text_training_rows, embedding_v2.production_state, embedding_v2.production_inputs, embedding_v2.production_rollback FROM PUBLIC;
