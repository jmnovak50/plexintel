-- Production incremental journal: no new permanent shadow generation per run.
ALTER TABLE embedding_v2.production_state ADD COLUMN IF NOT EXISTS publication_id text;
CREATE TABLE IF NOT EXISTS embedding_v2.production_runs (
    run_id text PRIMARY KEY,
    generation_id text NOT NULL,
    base_model_sha256 text NOT NULL,
    status text NOT NULL CHECK(status IN ('running','failed','succeeded')),
    snapshot jsonb,
    stages jsonb NOT NULL DEFAULT '{}',
    summary jsonb,
    error text,
    promotion_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);
CREATE TABLE IF NOT EXISTS embedding_v2.production_run_items (
    run_id text NOT NULL REFERENCES embedding_v2.production_runs,
    kind text NOT NULL CHECK(kind IN ('media_text','watch','user')),
    item_key text NOT NULL,
    record jsonb NOT NULL,
    embedding public.vector(768),
    preparation jsonb,
    PRIMARY KEY(run_id,kind,item_key)
);
CREATE TABLE IF NOT EXISTS embedding_v2.production_run_requests (
    request_id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES embedding_v2.production_runs,
    kind text NOT NULL CHECK(kind IN ('media_text','watch')),
    item_key text NOT NULL,
    status text NOT NULL,
    stats jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS embedding_v2.production_run_artifacts (
    run_id text NOT NULL REFERENCES embedding_v2.production_runs,
    name text NOT NULL,
    sha256 text NOT NULL,
    metadata jsonb NOT NULL,
    data bytea NOT NULL,
    PRIMARY KEY(run_id,name)
);
CREATE TABLE IF NOT EXISTS embedding_v2.production_run_predictions (
    run_id text NOT NULL REFERENCES embedding_v2.production_runs,
    owner text NOT NULL,
    media_key text NOT NULL,
    probability double precision NOT NULL,
    cosine double precision NOT NULL,
    rank integer NOT NULL,
    shap jsonb NOT NULL,
    PRIMARY KEY(run_id,owner,media_key)
);
REVOKE ALL ON embedding_v2.production_runs, embedding_v2.production_run_items, embedding_v2.production_run_requests, embedding_v2.production_run_artifacts, embedding_v2.production_run_predictions FROM PUBLIC;
