-- FORWARD ONLY; manual approval required. Never run on the production database implicitly.
-- 001_initial.sql is immutable. This one DO statement is atomic, even in autocommit;
-- operators should still use psql --single-transaction -v ON_ERROR_STOP=1.
DO $seerr_unified_upgrade$
DECLARE
    mismatch boolean;
    previous_owner oid;
BEGIN
    PERFORM set_config('lock_timeout', '5s', true);
    PERFORM set_config('search_path', 'pg_catalog, public, pg_temp', true);
    PERFORM pg_advisory_xact_lock(184725, 30);
    IF to_regclass('public.seerr_discovered_titles') IS NOT NULL THEN
        RAISE EXCEPTION 'seerr_unified_schema_already_present';
    END IF;
    IF to_regclass('public.seerr_discovered_movies') IS NULL
       OR to_regclass('public.seerr_discovery_runs') IS NULL
       OR to_regclass('public.seerr_discovery_observations') IS NULL THEN
        RAISE EXCEPTION 'seerr_unified_upgrade_requires_v1_schema';
    END IF;
    LOCK TABLE public.seerr_discovery_runs, public.seerr_discovered_movies,
               public.seerr_discovery_observations IN ACCESS EXCLUSIVE MODE;

    -- Fail closed on drift, including same-count but different definitions.
    WITH expected(name,kind) AS (VALUES
            ('seerr_discovered_movies', 'r'),
            ('seerr_discovered_movies_pkey', 'i'),
            ('seerr_discovery_observations', 'r'),
            ('seerr_discovery_observations_observation_id_seq', 'S'),
            ('seerr_discovery_observations_pkey', 'i'),
            ('seerr_discovery_observations_run_id_tmdb_id_scope_key_key', 'i'),
            ('seerr_discovery_runs', 'r'),
            ('seerr_discovery_runs_latest_idx', 'i'),
            ('seerr_discovery_runs_pkey', 'i'),
            ('seerr_movies_first_seen_idx', 'i'),
            ('seerr_movies_language_date_idx', 'i'),
            ('seerr_movies_last_seen_idx', 'i'),
            ('seerr_movies_refresh_idx', 'i'),
            ('seerr_observations_movie_idx', 'i'),
            ('seerr_observations_scope_idx', 'i')
    ), actual AS (
        SELECT c.relname::text,c.relkind::text FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE left(c.relname,6)='seerr_'
    )
    SELECT EXISTS((SELECT * FROM expected EXCEPT SELECT * FROM actual)
                  UNION ALL (SELECT * FROM actual EXCEPT SELECT * FROM expected)) INTO mismatch;
    IF mismatch OR EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                          WHERE left(c.relname,6)='seerr_' AND n.nspname<>'public') THEN
        RAISE EXCEPTION 'seerr_unified_upgrade_unexpected_v1_objects';
    END IF;
    WITH expected(table_name,name,position,type,not_null,identity,default_sql) AS (VALUES
            ('seerr_discovery_runs', 'run_id', 1, 'uuid', true, '', NULL),
            ('seerr_discovery_runs', 'started_at', 2, 'timestamp with time zone', true, '', NULL),
            ('seerr_discovery_runs', 'completed_at', 3, 'timestamp with time zone', false, '', NULL),
            ('seerr_discovery_runs', 'status', 4, 'text', true, '', NULL),
            ('seerr_discovery_runs', 'operation', 5, 'text', true, '', NULL),
            ('seerr_discovery_runs', 'source_key', 6, 'text', true, '', NULL),
            ('seerr_discovery_runs', 'parameters', 7, 'jsonb', true, '', NULL),
            ('seerr_discovery_runs', 'pagination', 8, 'jsonb', true, '', '''[]'''),
            ('seerr_discovery_runs', 'counts', 9, 'jsonb', true, '', '''{}'''),
            ('seerr_discovery_runs', 'discovery_complete', 10, 'boolean', true, '', 'false'),
            ('seerr_discovery_runs', 'enrichment_complete', 11, 'boolean', true, '', 'false'),
            ('seerr_discovery_runs', 'errors', 12, 'jsonb', true, '', '''[]'''),
            ('seerr_discovery_runs', 'warnings', 13, 'jsonb', true, '', '''[]'''),
            ('seerr_discovered_movies', 'tmdb_id', 1, 'bigint', true, '', NULL),
            ('seerr_discovered_movies', 'title', 2, 'text', false, '', NULL),
            ('seerr_discovered_movies', 'original_title', 3, 'text', false, '', NULL),
            ('seerr_discovered_movies', 'synopsis', 4, 'text', false, '', NULL),
            ('seerr_discovered_movies', 'original_language', 5, 'text', false, '', NULL),
            ('seerr_discovered_movies', 'release_date', 6, 'date', false, '', NULL),
            ('seerr_discovered_movies', 'discovery_release_date', 7, 'date', false, '', NULL),
            ('seerr_discovered_movies', 'runtime', 8, 'integer', false, '', NULL),
            ('seerr_discovered_movies', 'genres', 9, 'jsonb', false, '', NULL),
            ('seerr_discovered_movies', 'directors', 10, 'text[]', false, '', NULL),
            ('seerr_discovered_movies', 'cast_members', 11, 'jsonb', false, '', NULL),
            ('seerr_discovered_movies', 'crew_members', 12, 'jsonb', false, '', NULL),
            ('seerr_discovered_movies', 'production_countries', 13, 'jsonb', false, '', NULL),
            ('seerr_discovered_movies', 'production_companies', 14, 'jsonb', false, '', NULL),
            ('seerr_discovered_movies', 'popularity', 15, 'double precision', false, '', NULL),
            ('seerr_discovered_movies', 'vote_count', 16, 'bigint', false, '', NULL),
            ('seerr_discovered_movies', 'vote_average', 17, 'double precision', false, '', NULL),
            ('seerr_discovered_movies', 'release_events', 18, 'jsonb', false, '', NULL),
            ('seerr_discovered_movies', 'media_status', 19, 'integer', false, '', NULL),
            ('seerr_discovered_movies', 'media_status_4k', 20, 'integer', false, '', NULL),
            ('seerr_discovered_movies', 'media_state', 21, 'jsonb', true, '', '''{}'''),
            ('seerr_discovered_movies', 'first_discovered_at', 22, 'timestamp with time zone', true, '', NULL),
            ('seerr_discovered_movies', 'first_discovery_run_id', 23, 'uuid', true, '', NULL),
            ('seerr_discovered_movies', 'last_observed_at', 24, 'timestamp with time zone', true, '', NULL),
            ('seerr_discovered_movies', 'last_enriched_at', 25, 'timestamp with time zone', false, '', NULL),
            ('seerr_discovered_movies', 'last_enrichment_attempt_at', 26, 'timestamp with time zone', false, '', NULL),
            ('seerr_discovered_movies', 'metadata_updated_at', 27, 'timestamp with time zone', true, '', NULL),
            ('seerr_discovered_movies', 'enrichment_status', 28, 'text', true, '', '''pending'''),
            ('seerr_discovered_movies', 'enrichment_error', 29, 'text', false, '', NULL),
            ('seerr_discovered_movies', 'metadata_source_key', 30, 'text', false, '', NULL),
            ('seerr_discovered_movies', 'metadata_fingerprint', 31, 'text', true, '', NULL),
            ('seerr_discovered_movies', 'field_states', 32, 'jsonb', true, '', '''{}'''),
            ('seerr_discovered_movies', 'source_metadata', 33, 'jsonb', true, '', '''{}'''),
            ('seerr_discovery_observations', 'observation_id', 1, 'bigint', true, 'd', NULL),
            ('seerr_discovery_observations', 'run_id', 2, 'uuid', true, '', NULL),
            ('seerr_discovery_observations', 'tmdb_id', 3, 'bigint', true, '', NULL),
            ('seerr_discovery_observations', 'scope_key', 4, 'text', true, '', NULL),
            ('seerr_discovery_observations', 'scope_name', 5, 'text', true, '', NULL),
            ('seerr_discovery_observations', 'observation_kind', 6, 'text', true, '', NULL),
            ('seerr_discovery_observations', 'query_parameters', 7, 'jsonb', true, '', NULL),
            ('seerr_discovery_observations', 'observed_at', 8, 'timestamp with time zone', true, '', NULL),
            ('seerr_discovery_observations', 'discovery_metadata', 9, 'jsonb', true, '', NULL),
            ('seerr_discovery_observations', 'detail_metadata', 10, 'jsonb', false, '', NULL),
            ('seerr_discovery_observations', 'detail_observed_at', 11, 'timestamp with time zone', false, '', NULL),
            ('seerr_discovery_observations', 'enrichment_outcome', 12, 'text', true, '', '''pending'''),
            ('seerr_discovery_observations', 'enrichment_error', 13, 'text', false, '', NULL),
            ('seerr_discovery_observations', 'source_fingerprint', 14, 'text', true, '', NULL),
            ('seerr_discovery_observations', 'prior_metadata_fingerprint', 15, 'text', false, '', NULL),
            ('seerr_discovery_observations', 'metadata_fingerprint', 16, 'text', true, '', NULL),
            ('seerr_discovery_observations', 'changed_fields', 17, 'text[]', true, '', '''{}'''),
            ('seerr_discovery_observations', 'is_new', 18, 'boolean', true, '', NULL)
    ), actual AS (
        SELECT c.relname::text,a.attname::text,a.attnum::integer,
               format_type(a.atttypid,a.atttypmod),a.attnotnull,a.attidentity::text,
               regexp_replace(pg_get_expr(d.adbin,d.adrelid),'::(jsonb|text(\[\])?)','','g')
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE n.nspname='public' AND c.relname IN
          ('seerr_discovery_runs','seerr_discovered_movies','seerr_discovery_observations')
          AND a.attnum>0 AND NOT a.attisdropped
    )
    SELECT EXISTS((SELECT * FROM expected EXCEPT SELECT * FROM actual)
                  UNION ALL (SELECT * FROM actual EXCEPT SELECT * FROM expected)) INTO mismatch;
    IF mismatch THEN RAISE EXCEPTION 'seerr_unified_upgrade_v1_column_drift'; END IF;
    WITH expected(table_name,name,kind,definition) AS (VALUES
            ('seerr_discovered_movies', 'seerr_discovered_movies_cast_members_check', 'c', 'CHECK (((cast_members IS NULL) OR (jsonb_typeof(cast_members) = ''array''::text)))'),
            ('seerr_discovered_movies', 'seerr_discovered_movies_check', 'c', 'CHECK ((last_observed_at >= first_discovered_at))'),
            ('seerr_discovered_movies', 'seerr_discovered_movies_enrichment_status_check', 'c', 'CHECK ((enrichment_status = ANY (ARRAY[''pending''::text, ''success''::text, ''failed''::text])))'),
            ('seerr_discovered_movies', 'seerr_discovered_movies_first_discovery_run_id_fkey', 'f', 'FOREIGN KEY (first_discovery_run_id) REFERENCES seerr_discovery_runs(run_id)'),
            ('seerr_discovered_movies', 'seerr_discovered_movies_genres_check', 'c', 'CHECK (((genres IS NULL) OR (jsonb_typeof(genres) = ''array''::text)))'),
            ('seerr_discovered_movies', 'seerr_discovered_movies_pkey', 'p', 'PRIMARY KEY (tmdb_id)'),
            ('seerr_discovered_movies', 'seerr_discovered_movies_runtime_check', 'c', 'CHECK ((runtime > 0))'),
            ('seerr_discovered_movies', 'seerr_discovered_movies_tmdb_id_check', 'c', 'CHECK ((tmdb_id > 0))'),
            ('seerr_discovery_observations', 'seerr_discovery_observations_enrichment_outcome_check', 'c', 'CHECK ((enrichment_outcome = ANY (ARRAY[''pending''::text, ''success''::text, ''cached''::text, ''failed''::text, ''deferred''::text])))'),
            ('seerr_discovery_observations', 'seerr_discovery_observations_observation_kind_check', 'c', 'CHECK ((observation_kind = ANY (ARRAY[''discovery''::text, ''refresh''::text])))'),
            ('seerr_discovery_observations', 'seerr_discovery_observations_pkey', 'p', 'PRIMARY KEY (observation_id)'),
            ('seerr_discovery_observations', 'seerr_discovery_observations_run_id_fkey', 'f', 'FOREIGN KEY (run_id) REFERENCES seerr_discovery_runs(run_id)'),
            ('seerr_discovery_observations', 'seerr_discovery_observations_run_id_tmdb_id_scope_key_key', 'u', 'UNIQUE (run_id, tmdb_id, scope_key)'),
            ('seerr_discovery_observations', 'seerr_discovery_observations_tmdb_id_fkey', 'f', 'FOREIGN KEY (tmdb_id) REFERENCES seerr_discovered_movies(tmdb_id)'),
            ('seerr_discovery_runs', 'seerr_discovery_runs_check', 'c', 'CHECK (((status = ''running''::text) = (completed_at IS NULL)))'),
            ('seerr_discovery_runs', 'seerr_discovery_runs_check1', 'c', 'CHECK (((status <> ''success''::text) OR (discovery_complete AND enrichment_complete)))'),
            ('seerr_discovery_runs', 'seerr_discovery_runs_operation_check', 'c', 'CHECK ((operation = ANY (ARRAY[''discover''::text, ''enrich''::text])))'),
            ('seerr_discovery_runs', 'seerr_discovery_runs_pkey', 'p', 'PRIMARY KEY (run_id)'),
            ('seerr_discovery_runs', 'seerr_discovery_runs_status_check', 'c', 'CHECK ((status = ANY (ARRAY[''running''::text, ''success''::text, ''partial''::text, ''failed''::text])))')
    ), actual AS (
        SELECT c.relname::text,k.conname::text,k.contype::text,pg_get_constraintdef(k.oid)
        FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname IN
          ('seerr_discovery_runs','seerr_discovered_movies','seerr_discovery_observations')
          AND k.contype<>'n'
    )
    SELECT EXISTS((SELECT * FROM expected EXCEPT SELECT * FROM actual)
                  UNION ALL (SELECT * FROM actual EXCEPT SELECT * FROM expected)) INTO mismatch;
    IF mismatch OR EXISTS(SELECT 1 FROM pg_constraint k WHERE k.conrelid IN
         ('public.seerr_discovery_runs'::regclass,'public.seerr_discovered_movies'::regclass,
          'public.seerr_discovery_observations'::regclass) AND
          (NOT k.convalidated OR k.condeferrable OR k.condeferred)) THEN
        RAISE EXCEPTION 'seerr_unified_upgrade_v1_constraint_drift';
    END IF;
    WITH expected(name,definition) AS (VALUES
            ('seerr_discovered_movies_pkey', 'CREATE UNIQUE INDEX seerr_discovered_movies_pkey ON public.seerr_discovered_movies USING btree (tmdb_id)'),
            ('seerr_discovery_observations_pkey', 'CREATE UNIQUE INDEX seerr_discovery_observations_pkey ON public.seerr_discovery_observations USING btree (observation_id)'),
            ('seerr_discovery_observations_run_id_tmdb_id_scope_key_key', 'CREATE UNIQUE INDEX seerr_discovery_observations_run_id_tmdb_id_scope_key_key ON public.seerr_discovery_observations USING btree (run_id, tmdb_id, scope_key)'),
            ('seerr_discovery_runs_latest_idx', 'CREATE INDEX seerr_discovery_runs_latest_idx ON public.seerr_discovery_runs USING btree (started_at DESC)'),
            ('seerr_discovery_runs_pkey', 'CREATE UNIQUE INDEX seerr_discovery_runs_pkey ON public.seerr_discovery_runs USING btree (run_id)'),
            ('seerr_movies_first_seen_idx', 'CREATE INDEX seerr_movies_first_seen_idx ON public.seerr_discovered_movies USING btree (first_discovered_at DESC)'),
            ('seerr_movies_language_date_idx', 'CREATE INDEX seerr_movies_language_date_idx ON public.seerr_discovered_movies USING btree (original_language, release_date)'),
            ('seerr_movies_last_seen_idx', 'CREATE INDEX seerr_movies_last_seen_idx ON public.seerr_discovered_movies USING btree (last_observed_at DESC)'),
            ('seerr_movies_refresh_idx', 'CREATE INDEX seerr_movies_refresh_idx ON public.seerr_discovered_movies USING btree (enrichment_status, last_enriched_at)'),
            ('seerr_observations_movie_idx', 'CREATE INDEX seerr_observations_movie_idx ON public.seerr_discovery_observations USING btree (tmdb_id, observed_at DESC)'),
            ('seerr_observations_scope_idx', 'CREATE INDEX seerr_observations_scope_idx ON public.seerr_discovery_observations USING btree (scope_key, run_id)')
    ), actual AS (
        SELECT indexname::text,indexdef FROM pg_indexes WHERE schemaname='public'
        AND tablename IN ('seerr_discovery_runs','seerr_discovered_movies','seerr_discovery_observations')
    )
    SELECT EXISTS((SELECT * FROM expected EXCEPT SELECT * FROM actual)
                  UNION ALL (SELECT * FROM actual EXCEPT SELECT * FROM expected)) INTO mismatch;
    IF mismatch OR EXISTS(SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid=i.indrelid
                          WHERE c.oid IN ('public.seerr_discovery_runs'::regclass,
                          'public.seerr_discovered_movies'::regclass,'public.seerr_discovery_observations'::regclass)
                          AND (NOT i.indisvalid OR NOT i.indisready)) THEN
        RAISE EXCEPTION 'seerr_unified_upgrade_v1_index_drift';
    END IF;
    SELECT relowner INTO previous_owner FROM pg_class WHERE oid='public.seerr_discovery_runs'::regclass;
    IF EXISTS(SELECT 1 FROM pg_class c WHERE left(c.relname,6)='seerr_' AND c.relowner<>previous_owner)
       OR EXISTS(SELECT 1 FROM pg_constraint k WHERE k.confrelid='public.seerr_discovered_movies'::regclass
                  AND k.conrelid<>'public.seerr_discovery_observations'::regclass)
       OR EXISTS(SELECT 1 FROM pg_depend d JOIN pg_rewrite r ON r.oid=d.objid
                  WHERE d.refobjid='public.seerr_discovered_movies'::regclass AND d.classid='pg_rewrite'::regclass)
       OR EXISTS(SELECT 1 FROM pg_trigger t WHERE t.tgrelid IN
                  ('public.seerr_discovery_runs'::regclass,'public.seerr_discovered_movies'::regclass,
                   'public.seerr_discovery_observations'::regclass) AND NOT t.tgisinternal) THEN
        RAISE EXCEPTION 'seerr_unified_upgrade_unexpected_owner_or_dependency';
    END IF;
    IF pg_get_serial_sequence('public.seerr_discovery_observations','observation_id') IS DISTINCT FROM
       'public.seerr_discovery_observations_observation_id_seq'
       OR NOT EXISTS(SELECT 1 FROM pg_sequence WHERE seqrelid='public.seerr_discovery_observations_observation_id_seq'::regclass
                     AND seqtypid='bigint'::regtype AND seqstart=1 AND seqincrement=1 AND seqmin=1
                     AND seqmax=9223372036854775807 AND seqcache=1 AND NOT seqcycle)
       OR NOT EXISTS(SELECT 1 FROM pg_depend d JOIN pg_attribute a ON a.attrelid=d.refobjid AND a.attnum=d.refobjsubid
                     WHERE d.objid='public.seerr_discovery_observations_observation_id_seq'::regclass
                     AND d.refobjid='public.seerr_discovery_observations'::regclass AND a.attname='observation_id' AND d.deptype='i') THEN
        RAISE EXCEPTION 'seerr_unified_upgrade_v1_sequence_drift';
    END IF;

    -- Retain all run/source metadata, timestamps, fingerprints and existing ACLs.
    ALTER TABLE public.seerr_discovered_movies RENAME TO seerr_discovered_titles;
    ALTER TABLE public.seerr_discovered_titles RENAME COLUMN release_date TO premiere_date;
    ALTER TABLE public.seerr_discovered_titles RENAME COLUMN discovery_release_date TO discovery_premiere_date;
    ALTER TABLE public.seerr_discovered_titles
        ADD COLUMN media_type text NOT NULL DEFAULT 'movie',
        ADD COLUMN tv_metadata jsonb,
        ADD CONSTRAINT seerr_titles_media_type_check CHECK (media_type IN ('movie','tv')),
        ADD CONSTRAINT seerr_titles_tv_metadata_check CHECK (tv_metadata IS NULL OR (media_type='tv' AND jsonb_typeof(tv_metadata)='object')),
        ADD CONSTRAINT seerr_titles_tv_release_events_check CHECK (media_type='movie' OR release_events IS NULL);
    ALTER TABLE public.seerr_discovery_observations
        ADD COLUMN media_type text NOT NULL DEFAULT 'movie',
        ADD COLUMN eligibility jsonb,
        ADD CONSTRAINT seerr_observations_media_type_check CHECK (media_type IN ('movie','tv')),
        ADD CONSTRAINT seerr_observations_eligibility_check CHECK (eligibility IS NULL OR
            (media_type='tv' AND jsonb_typeof(eligibility)='object' AND eligibility ? 'state'
             AND jsonb_typeof(eligibility->'state')='string'
             AND eligibility->>'state' IN ('eligible','provisional','excluded')));
    ALTER TABLE public.seerr_discovery_observations
        DROP CONSTRAINT seerr_discovery_observations_tmdb_id_fkey,
        DROP CONSTRAINT seerr_discovery_observations_run_id_tmdb_id_scope_key_key;
    ALTER TABLE public.seerr_discovered_titles DROP CONSTRAINT seerr_discovered_movies_pkey;
    ALTER TABLE public.seerr_discovered_titles ADD CONSTRAINT seerr_discovered_titles_pkey PRIMARY KEY (media_type,tmdb_id);
    ALTER TABLE public.seerr_discovery_observations
        ADD CONSTRAINT seerr_observations_title_fkey FOREIGN KEY (media_type,tmdb_id)
            REFERENCES public.seerr_discovered_titles(media_type,tmdb_id),
        ADD CONSTRAINT seerr_observations_run_title_scope_key UNIQUE (run_id,media_type,tmdb_id,scope_key);
    -- No implicit default for new identities: typed writers must supply it explicitly.
    ALTER TABLE public.seerr_discovered_titles ALTER COLUMN media_type DROP DEFAULT;
    ALTER TABLE public.seerr_discovery_observations ALTER COLUMN media_type DROP DEFAULT;
    ALTER INDEX public.seerr_movies_first_seen_idx RENAME TO seerr_titles_first_seen_idx;
    ALTER INDEX public.seerr_movies_last_seen_idx RENAME TO seerr_titles_last_seen_idx;
    DROP INDEX public.seerr_movies_refresh_idx;
    CREATE INDEX seerr_titles_refresh_idx ON public.seerr_discovered_titles(last_enrichment_attempt_at NULLS FIRST,media_type,tmdb_id);
    DROP INDEX public.seerr_movies_language_date_idx;
    CREATE INDEX seerr_titles_language_date_idx ON public.seerr_discovered_titles(media_type,original_language,premiere_date);
    DROP INDEX public.seerr_observations_movie_idx;
    CREATE INDEX seerr_observations_title_idx ON public.seerr_discovery_observations(media_type,tmdb_id,observed_at DESC);
END
$seerr_unified_upgrade$;
