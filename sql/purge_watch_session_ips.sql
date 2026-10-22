-- Explicitly scheduled by the operator using the restricted session-writer DSN.
-- Leaves session observations and model history intact; suppression is durable.
WITH cleared AS (
    UPDATE public.watch_sessions s
    SET ip_address = NULL,
        ip_suppressed_at = COALESCE(s.ip_suppressed_at, statement_timestamp())
    FROM public.watch_session_policy p
    WHERE p.singleton AND s.ip_address IS NOT NULL AND (
        p.ip_retention_days = 0 OR s.started_at IS NULL
        OR s.started_at > statement_timestamp()
        OR s.started_at < statement_timestamp() - make_interval(days => p.ip_retention_days))
    RETURNING 1
)
SELECT count(*) AS ip_addresses_cleared FROM cleared;
