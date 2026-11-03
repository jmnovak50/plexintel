-- Manual installation only. Never imported by application schema bootstrap.
CREATE SCHEMA IF NOT EXISTS embedding_v2;
CREATE TABLE IF NOT EXISTS embedding_v2.generations (
    generation_id text PRIMARY KEY,
    contract jsonb NOT NULL,
    contract_hash text NOT NULL,
    scope text NOT NULL CHECK (scope IN ('full','bounded','test')),
    status text NOT NULL DEFAULT 'building' CHECK (status IN ('building','validated','active','retired')),
    parent_id text REFERENCES embedding_v2.generations,
    base_generation text REFERENCES embedding_v2.generations,
    source_hash text NOT NULL,
    snapshot jsonb NOT NULL,
    expected jsonb NOT NULL,
    validation jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS embedding_v2.items (
    generation_id text NOT NULL REFERENCES embedding_v2.generations,
    kind text NOT NULL CHECK (kind IN ('media','watch','user')),
    item_key text NOT NULL,
    owner text,
    media_key text,
    source jsonb NOT NULL,
    semantic_hash text NOT NULL,
    input_hash text,
    poster jsonb,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','succeeded','failed')),
    embedding public.vector(768),
    attempts integer NOT NULL DEFAULT 0,
    error text,
    timing jsonb,
    generated_at timestamptz,
    origin_generation text REFERENCES embedding_v2.generations,
    PRIMARY KEY (generation_id,kind,item_key),
    CHECK ((status='succeeded') = (embedding IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS embedding_v2.dependencies (
    generation_id text NOT NULL,
    child_kind text NOT NULL,
    child_key text NOT NULL,
    parent_kind text NOT NULL,
    parent_key text NOT NULL,
    parent_input_hash text NOT NULL,
    PRIMARY KEY(generation_id,child_kind,child_key,parent_kind,parent_key),
    FOREIGN KEY(generation_id,child_kind,child_key) REFERENCES embedding_v2.items(generation_id,kind,item_key) ON DELETE CASCADE,
    FOREIGN KEY(generation_id,parent_kind,parent_key) REFERENCES embedding_v2.items(generation_id,kind,item_key)
);
CREATE TABLE IF NOT EXISTS embedding_v2.artifacts (
    generation_id text NOT NULL REFERENCES embedding_v2.generations,
    name text NOT NULL,
    sha256 text NOT NULL,
    metadata jsonb NOT NULL,
    data bytea NOT NULL,
    PRIMARY KEY(generation_id,name)
);
CREATE TABLE IF NOT EXISTS embedding_v2.training_rows (
    generation_id text NOT NULL REFERENCES embedding_v2.generations,
    owner text NOT NULL,
    media_key text NOT NULL,
    prediction_at timestamptz NOT NULL,
    label_available_at timestamptz NOT NULL,
    label integer NOT NULL CHECK (label IN (0,1)),
    embedding public.vector(1536) NOT NULL,
    features jsonb NOT NULL,
    dependencies jsonb NOT NULL,
    PRIMARY KEY(generation_id,owner,media_key)
);
CREATE TABLE IF NOT EXISTS embedding_v2.predictions (
    generation_id text NOT NULL REFERENCES embedding_v2.generations,
    owner text NOT NULL,
    media_key text NOT NULL,
    probability double precision NOT NULL CHECK(probability>=0 AND probability<=1),
    cosine double precision NOT NULL,
    rank integer NOT NULL,
    shap jsonb NOT NULL DEFAULT '[]',
    PRIMARY KEY(generation_id,owner,media_key)
);
CREATE TABLE IF NOT EXISTS embedding_v2.control (
    singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
    active_generation text REFERENCES embedding_v2.generations,
    previous_generation text REFERENCES embedding_v2.generations,
    legacy_model_sha256 text,
    deployed_code_sha256 text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO embedding_v2.control(singleton) VALUES(true) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS embedding_v2.rollback_rows (
    promotion_id text NOT NULL,
    table_name text NOT NULL,
    ordinal bigint GENERATED ALWAYS AS IDENTITY,
    row_data jsonb NOT NULL,
    PRIMARY KEY(promotion_id,table_name,ordinal)
);
CREATE TABLE IF NOT EXISTS embedding_v2.promotions (
    promotion_id text PRIMARY KEY,
    generation_id text NOT NULL REFERENCES embedding_v2.generations,
    previous_generation text,
    archive_counts jsonb NOT NULL,
    archive_hashes jsonb NOT NULL,
    legacy_model_sha256 text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    rolled_back_at timestamptz
);
-- Immutable typed copy of every previous vector population, in addition to the
-- complete row-level undo archive. Initial promotion never discards legacy data.
CREATE TABLE IF NOT EXISTS embedding_v2.retained_vectors (
    promotion_id text NOT NULL REFERENCES embedding_v2.promotions,
    kind text NOT NULL,
    item_key text NOT NULL,
    embedding public.vector(768) NOT NULL,
    PRIMARY KEY(promotion_id,kind,item_key)
);
CREATE INDEX IF NOT EXISTS embedding_v2_pending ON embedding_v2.items(generation_id,kind,status,item_key);
CREATE TABLE IF NOT EXISTS embedding_v2.preparations (
    generation_id text NOT NULL,
    kind text NOT NULL DEFAULT 'media' CHECK(kind='media'),
    item_key text NOT NULL,
    stage text NOT NULL CHECK(stage IN ('metadata','poster')),
    status text NOT NULL CHECK(status IN ('succeeded','failed')),
    content_hash text,
    provenance jsonb NOT NULL,
    timing jsonb NOT NULL,
    prepared_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(generation_id,item_key,stage),
    FOREIGN KEY(generation_id,kind,item_key) REFERENCES embedding_v2.items(generation_id,kind,item_key)
);
CREATE TABLE IF NOT EXISTS embedding_v2.poster_cache (
    source_id text PRIMARY KEY,
    provenance jsonb NOT NULL
);
REVOKE ALL ON SCHEMA embedding_v2 FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA embedding_v2 FROM PUBLIC;
