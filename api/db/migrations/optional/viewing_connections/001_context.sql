-- Explicit activation only: outside the startup migration glob. No source backfill.
SET LOCAL lock_timeout = '5s';
CREATE TABLE public.viewing_connection_state (
 scope text NOT NULL CHECK(scope IN ('catalog','viewer')),
 owner text NOT NULL,
 revision bigint NOT NULL DEFAULT 1,
 PRIMARY KEY(scope,owner),
 CHECK((scope='catalog' AND owner='') OR (scope='viewer' AND owner<>''))
);
INSERT INTO public.viewing_connection_state(scope,owner) VALUES('catalog','');
CREATE TABLE public.viewing_connection_context (
 username text NOT NULL,
 target_identity text NOT NULL,
 policy_version text NOT NULL,
 catalog_revision bigint NOT NULL,
 viewer_revision bigint NOT NULL,
 status text NOT NULL CHECK(status IN ('ready','none')),
 connection jsonb,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(username,target_identity),
 CHECK((status='ready' AND connection IS NOT NULL) OR (status='none' AND connection IS NULL))
);
COMMENT ON TABLE public.viewing_connection_context IS
 'Current viewer-private factual connection or explicit no-result, independent of prediction rows. No copied history or scores.';
-- Generations are transactional counters, never sequence/MAX commit watermarks.
-- Transition tables coalesce bulk changes to one increment per affected viewer.
CREATE FUNCTION public.viewing_connection_invalidate() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE people text[]; person text; changed boolean;
BEGIN
 IF TG_OP='TRUNCATE' THEN
  INSERT INTO public.viewing_connection_state(scope,owner) VALUES('catalog','')
   ON CONFLICT(scope,owner) DO UPDATE SET revision=viewing_connection_state.revision+1;
  RETURN NULL;
 END IF;
 IF TG_TABLE_NAME='metadata_ingestion_events' AND TG_OP='INSERT' THEN
  EXECUTE 'SELECT EXISTS(SELECT 1 FROM new_rows WHERE outcome=''applied'')' INTO changed;
  IF NOT changed THEN RETURN NULL; END IF;
 END IF;
 IF TG_OP='INSERT' THEN EXECUTE 'SELECT EXISTS(SELECT 1 FROM new_rows)' INTO changed;
 ELSIF TG_OP='DELETE' THEN EXECUTE 'SELECT EXISTS(SELECT 1 FROM old_rows)' INTO changed;
 ELSE EXECUTE 'SELECT EXISTS((SELECT * FROM new_rows EXCEPT SELECT * FROM old_rows) UNION ALL (SELECT * FROM old_rows EXCEPT SELECT * FROM new_rows))' INTO changed;
 END IF;
 IF NOT changed THEN RETURN NULL; END IF;
 IF TG_ARGV[0]='viewer' THEN
  IF TG_OP='INSERT' THEN EXECUTE 'SELECT array_agg(DISTINCT username ORDER BY username) FROM new_rows WHERE username IS NOT NULL AND username<>'''' ' INTO people;
  ELSIF TG_OP='DELETE' THEN EXECUTE 'SELECT array_agg(DISTINCT username ORDER BY username) FROM old_rows WHERE username IS NOT NULL AND username<>'''' ' INTO people;
  ELSE EXECUTE 'SELECT array_agg(DISTINCT username ORDER BY username) FROM (SELECT username FROM new_rows UNION SELECT username FROM old_rows) x WHERE username IS NOT NULL AND username<>'''' ' INTO people;
  END IF;
  FOREACH person IN ARRAY coalesce(people,ARRAY[]::text[]) LOOP
   INSERT INTO public.viewing_connection_state(scope,owner) VALUES('viewer',person)
    ON CONFLICT(scope,owner) DO UPDATE SET revision=viewing_connection_state.revision+1;
   -- Account deletion/rename also removes private contexts for that old account.
   IF TG_TABLE_NAME='users' AND TG_OP IN ('DELETE','UPDATE') THEN
    DELETE FROM public.viewing_connection_context c WHERE c.username=person
      AND NOT EXISTS(SELECT 1 FROM public.users u WHERE u.username=person);
   END IF;
  END LOOP;
 ELSE
  INSERT INTO public.viewing_connection_state(scope,owner) VALUES('catalog','')
   ON CONFLICT(scope,owner) DO UPDATE SET revision=viewing_connection_state.revision+1;
 END IF;
 RETURN NULL;
END $$;
DO $$
DECLARE t text; scope_name text;
BEGIN
 FOREACH t IN ARRAY ARRAY['watch_history','user_feedback','users','library','actors','directors','genres','media_actors','media_directors','media_genres','metadata_ingestion_events'] LOOP
  scope_name:=CASE WHEN t IN ('watch_history','user_feedback','users') THEN 'viewer' ELSE 'catalog' END;
  EXECUTE format('CREATE TRIGGER viewing_connection_insert AFTER INSERT ON public.%I REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION public.viewing_connection_invalidate(%L)',t,scope_name);
  EXECUTE format('CREATE TRIGGER viewing_connection_update AFTER UPDATE ON public.%I REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows FOR EACH STATEMENT EXECUTE FUNCTION public.viewing_connection_invalidate(%L)',t,scope_name);
  EXECUTE format('CREATE TRIGGER viewing_connection_delete AFTER DELETE ON public.%I REFERENCING OLD TABLE AS old_rows FOR EACH STATEMENT EXECUTE FUNCTION public.viewing_connection_invalidate(%L)',t,scope_name);
  EXECUTE format('CREATE TRIGGER viewing_connection_truncate AFTER TRUNCATE ON public.%I FOR EACH STATEMENT EXECUTE FUNCTION public.viewing_connection_invalidate(%L)',t,scope_name);
 END LOOP;
END $$;

-- Reverse credit lookup for page-sized relational intersections.
CREATE INDEX viewing_connection_actor_reverse ON public.media_actors(actor_id,media_id);
CREATE INDEX viewing_connection_director_reverse ON public.media_directors(director_id,media_id);
CREATE INDEX viewing_connection_genre_reverse ON public.media_genres(genre_id,media_id);
