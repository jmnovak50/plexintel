-- psql -X -v ON_ERROR_STOP=1 --single-transaction -f this-file
SET LOCAL lock_timeout = '5s';
SET LOCAL search_path = pg_catalog, public, pg_temp;

CREATE TABLE IF NOT EXISTS public.watch_session_policy (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    ip_retention_days integer NOT NULL DEFAULT 0 CHECK (ip_retention_days BETWEEN 0 AND 365)
);
INSERT INTO public.watch_session_policy (singleton, ip_retention_days)
VALUES (true, 0) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS public.watch_sessions (
    source_event_id bigint PRIMARY KEY CHECK (source_event_id > 0),
    source_reference_id bigint,
    source_user_id bigint,
    username text,
    friendly_name text,
    rating_key integer NOT NULL,
    media_type text,
    title text,
    watched_at timestamptz,
    started_at timestamptz,
    stopped_at timestamptz,
    played_duration integer,
    percent_complete double precision,
    ip_address inet,
    player text,
    platform text,
    product text,
    device text,
    platform_version text,
    product_version text,
    session_id text,
    ip_suppressed_at timestamptz
);
-- Source references are observations, not FKs: deleted media/users and unmatched
-- raw events must remain observable. No assumed reference_id = watch_id mapping.
CREATE TABLE IF NOT EXISTS public.watch_session_memberships (
    watch_id integer NOT NULL REFERENCES public.watch_history(watch_id) ON DELETE CASCADE,
    source_event_id bigint NOT NULL REFERENCES public.watch_sessions(source_event_id) ON DELETE CASCADE,
    PRIMARY KEY (watch_id, source_event_id),
    UNIQUE (source_event_id)
);
CREATE INDEX IF NOT EXISTS watch_sessions_started_idx ON public.watch_sessions(started_at);
-- Efficient retention sweep without scanning sessions which have no retained IP.
CREATE INDEX IF NOT EXISTS watch_sessions_retained_ip_idx ON public.watch_sessions(started_at)
    WHERE ip_address IS NOT NULL;

CREATE OR REPLACE FUNCTION public.enforce_watch_session_ip_policy()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE days integer;
BEGIN
    -- ON CONFLICT runs BEFORE INSERT before finding the existing row. An omitted
    -- start must preserve known evidence, while a genuinely unknown start fails closed.
    IF TG_OP = 'INSERT' AND NEW.started_at IS NULL THEN
        SELECT s.started_at INTO NEW.started_at FROM public.watch_sessions s
        WHERE s.source_event_id = NEW.source_event_id AND s.rating_key = NEW.rating_key
          AND s.username IS NOT DISTINCT FROM NEW.username;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF NEW.source_event_id IS DISTINCT FROM OLD.source_event_id
           OR NEW.rating_key IS DISTINCT FROM OLD.rating_key
           OR NEW.username IS DISTINCT FROM OLD.username THEN
            RAISE EXCEPTION 'Session source identity is immutable';
        END IF;
        -- A corrected timestamp cannot rejuvenate an old observation's IP.
        NEW.started_at := LEAST(OLD.started_at, NEW.started_at);
        NEW.ip_suppressed_at := COALESCE(OLD.ip_suppressed_at, NEW.ip_suppressed_at);
        IF OLD.ip_address IS NOT NULL AND NEW.ip_address IS NULL THEN
            NEW.ip_suppressed_at := COALESCE(NEW.ip_suppressed_at, statement_timestamp());
        END IF;
    END IF;
    SELECT ip_retention_days INTO STRICT days FROM public.watch_session_policy WHERE singleton;
    IF days = 0 OR NEW.started_at IS NULL OR NEW.started_at > statement_timestamp()
       OR NEW.started_at < statement_timestamp() - make_interval(days => days)
       OR NEW.ip_suppressed_at IS NOT NULL THEN
        NEW.ip_address := NULL;
        NEW.ip_suppressed_at := COALESCE(NEW.ip_suppressed_at, statement_timestamp());
    END IF;
    RETURN NEW;
END $$;
-- Replace the trigger transactionally without touching history or existing views.
CREATE OR REPLACE TRIGGER watch_session_ip_policy
BEFORE INSERT OR UPDATE ON public.watch_sessions
FOR EACH ROW EXECUTE FUNCTION public.enforce_watch_session_ip_policy();

-- Reports choose one verified source member, never duplicate a grouped row.
-- Latest started_at, then highest source_event_id; NULL starts sort last.
CREATE OR REPLACE VIEW public.watch_history_playback_v AS
SELECT w.watch_id, representative.player, representative.platform, representative.product,
       representative.device, representative.platform_version, representative.product_version
FROM public.watch_history w
LEFT JOIN LATERAL (
    SELECT s.player, s.platform, s.product, s.device, s.platform_version, s.product_version
    FROM public.watch_session_memberships link
    JOIN public.watch_sessions s USING (source_event_id)
    WHERE link.watch_id = w.watch_id AND s.rating_key = w.rating_key
      AND s.username IS NOT DISTINCT FROM w.username
    ORDER BY s.started_at DESC NULLS LAST, s.source_event_id DESC
    LIMIT 1
) representative ON true;

REVOKE ALL ON public.watch_sessions, public.watch_session_memberships,
    public.watch_session_policy, public.watch_history_playback_v FROM PUBLIC;
REVOKE ALL ON FUNCTION public.enforce_watch_session_ip_policy() FROM PUBLIC;
-- No changes to watch_history, deployed reporting/recommendation views or roles.
