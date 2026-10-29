-- Explicit destructive rollback of DISCOVERY DATA ONLY; export first and obtain approval.
-- Not included by the application startup migration glob.
SET LOCAL lock_timeout = '5s';
SET LOCAL search_path = pg_catalog, public, pg_temp;
SELECT pg_advisory_xact_lock(184725, 30);
DROP TABLE IF EXISTS public.seerr_discovery_observations;
DROP TABLE IF EXISTS public.seerr_discovered_movies;
DROP TABLE IF EXISTS public.seerr_discovery_runs;
-- No CASCADE and no changes to library, model, history, recommendation or schedule data.
