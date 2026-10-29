-- Read-only V2 visibility. Requires separately approved 002; NOT for installed V1.
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SELECT run_id,started_at,completed_at,status,operation,discovery_complete,enrichment_complete,
       parameters,pagination,counts,errors,warnings
FROM public.seerr_discovery_runs ORDER BY started_at DESC LIMIT 5;

SELECT media_type,tmdb_id,title,premiere_date,discovery_premiere_date,original_language,
       first_discovered_at,last_observed_at,last_enriched_at,enrichment_status
FROM public.seerr_discovered_titles
ORDER BY first_discovered_at DESC,media_type,tmdb_id LIMIT 25;

-- Inventory includes excluded TV audit evidence; counts are not acquisition approval.
SELECT media_type,enrichment_status,COUNT(*) AS titles,
       COUNT(*) FILTER (WHERE last_enriched_at IS NULL OR last_enriched_at < now()-interval '24 hours') AS old_or_missing
FROM public.seerr_discovered_titles GROUP BY media_type,enrichment_status;

SELECT media_type,tmdb_id,COUNT(DISTINCT run_id) AS runs,COUNT(DISTINCT scope_key) AS queries,
       MIN(observed_at) AS first_membership,MAX(observed_at) AS last_membership
FROM public.seerr_discovery_observations WHERE observation_kind='discovery'
GROUP BY media_type,tmdb_id ORDER BY last_membership DESC LIMIT 25;

SELECT o.media_type,o.tmdb_id,t.title,o.scope_name,o.observation_kind,o.eligibility,
       o.is_new,o.changed_fields,o.enrichment_outcome,o.enrichment_error
FROM public.seerr_discovery_observations o
JOIN public.seerr_discovered_titles t USING(media_type,tmdb_id)
WHERE o.run_id=(SELECT run_id FROM public.seerr_discovery_runs ORDER BY started_at DESC LIMIT 1)
ORDER BY o.media_type,o.tmdb_id,o.scope_name;

-- Summary-level exclusions (including unknown dates) may have no canonical row.
SELECT r.run_id,p->>'media_type' AS media_type,p->>'scope_key' AS scope_key,
       p->'excluded' AS excluded_summary_rows,p->'invalid_rows' AS invalid_row_count
FROM public.seerr_discovery_runs r CROSS JOIN LATERAL jsonb_array_elements(r.pagination) p
WHERE r.run_id=(SELECT run_id FROM public.seerr_discovery_runs ORDER BY started_at DESC LIMIT 1);
ROLLBACK;
