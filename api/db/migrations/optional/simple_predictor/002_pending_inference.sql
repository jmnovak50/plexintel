-- Apply explicitly before deploying the durable-inference worker. Never run at job startup.
-- One latest candidate per modality/source, independent of predictive executions.
CREATE TABLE public.pending_embedding_inference (
    modality text NOT NULL CHECK (modality IN ('media_text','watch')),
    source_key integer NOT NULL,
    input_hash text NOT NULL CHECK (input_hash ~ '^[a-f0-9]{64}$'),
    modality_contract_hash text NOT NULL CHECK (modality_contract_hash ~ '^[a-f0-9]{64}$'),
    encoder_digest text NOT NULL CHECK (encoder_digest ~ '^[a-f0-9]{64}$'),
    embedding public.vector(768) NOT NULL,
    vector_sha256 text NOT NULL CHECK (vector_sha256 ~ '^[a-f0-9]{64}$'),
    PRIMARY KEY (modality,source_key)
);
