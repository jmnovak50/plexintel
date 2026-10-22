-- OPTIONAL operator-run grants after 004_watch_sessions.sql; not run at startup.
-- Creates capability roles only, never changes existing service/superuser roles.
DO $$
DECLARE name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['plexintel_session_writer', 'plexintel_history_reader'] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', name);
        ELSIF EXISTS (SELECT FROM pg_roles WHERE rolname = name AND
                      (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls)) THEN
            RAISE EXCEPTION 'Existing capability role has unexpected privileges; review manually';
        END IF;
    END LOOP;
END $$;
GRANT USAGE ON SCHEMA public TO plexintel_session_writer, plexintel_history_reader;
GRANT SELECT, INSERT, UPDATE ON public.watch_sessions TO plexintel_session_writer;
GRANT SELECT, INSERT, DELETE ON public.watch_session_memberships TO plexintel_session_writer;
GRANT SELECT ON public.watch_session_policy TO plexintel_session_writer;
GRANT SELECT (watch_id, username, rating_key) ON public.watch_history TO plexintel_session_writer;
GRANT SELECT (watch_id, username, friendly_name, rating_key, watched_at,
    played_duration, media_duration, percent_complete, engaged, media_type,
    show_title, title, season_number, episode_number, summary, rating, year,
    genres, actors, directors) ON public.watch_history_enriched_v TO plexintel_history_reader;
GRANT SELECT ON public.watch_history_playback_v TO plexintel_history_reader;
-- Trigger execution does not require granting the trigger function to callers.
-- Provision separate LOGIN roles and membership using operator-managed credentials.
-- Do not grant these capabilities to a superuser and treat that as isolation.
