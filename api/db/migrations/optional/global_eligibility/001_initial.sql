-- MANUAL REVIEW AND OPT-IN ONLY; not included in application startup migrations.
-- psql -X -v ON_ERROR_STOP=1 --single-transaction -f this-file
SET LOCAL lock_timeout = '5s';
SET LOCAL search_path = pg_catalog, public, pg_temp;
SELECT pg_advisory_xact_lock(184725, 41);

CREATE TABLE public.eligibility_policies (
    version bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text NOT NULL,
    policy_hash text NOT NULL,
    policy jsonb NOT NULL CHECK (jsonb_typeof(policy) = 'object')
);
CREATE TABLE public.eligibility_runs (
    run_id uuid PRIMARY KEY,
    evaluated_at timestamptz NOT NULL DEFAULT now(),
    evaluated_by text NOT NULL,
    policy_version bigint NOT NULL REFERENCES public.eligibility_policies(version),
    engine_version text NOT NULL,
    inventory_hash text NOT NULL,
    summary jsonb NOT NULL,
    previous_run_id uuid REFERENCES public.eligibility_runs(run_id),
    changes jsonb NOT NULL
);
CREATE TABLE public.eligibility_results (
    run_id uuid NOT NULL REFERENCES public.eligibility_runs(run_id),
    media_type text NOT NULL CHECK (media_type IN ('movie', 'tv')),
    tmdb_id bigint NOT NULL CHECK (tmdb_id > 0),
    title text,
    outcome text NOT NULL CHECK (outcome IN ('retained', 'excluded')),
    reasons jsonb NOT NULL CHECK (jsonb_typeof(reasons) = 'array'),
    uncertainties jsonb NOT NULL CHECK (jsonb_typeof(uncertainties) = 'array'),
    rule_outcomes jsonb NOT NULL CHECK (jsonb_typeof(rule_outcomes) = 'array'),
    input_snapshot jsonb NOT NULL CHECK (jsonb_typeof(input_snapshot) = 'object'),
    PRIMARY KEY (run_id, media_type, tmdb_id),
    FOREIGN KEY (media_type, tmdb_id) REFERENCES public.seerr_discovered_titles(media_type, tmdb_id)
);
CREATE INDEX eligibility_runs_latest_idx ON public.eligibility_runs(evaluated_at DESC, run_id);
CREATE INDEX eligibility_results_outcome_idx ON public.eligibility_results(run_id, outcome, media_type, tmdb_id);
CREATE INDEX eligibility_results_title_idx ON public.eligibility_results(run_id, title, media_type, tmdb_id);
REVOKE ALL ON public.eligibility_policies, public.eligibility_runs, public.eligibility_results FROM PUBLIC;
REVOKE ALL ON SEQUENCE public.eligibility_policies_version_seq FROM PUBLIC;
