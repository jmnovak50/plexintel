BEGIN;

ALTER TABLE public.library
    ADD COLUMN IF NOT EXISTS show_rating_key integer;

ALTER TABLE public.watch_history
    ADD COLUMN IF NOT EXISTS show_rating_key integer;

CREATE INDEX IF NOT EXISTS recommendations_username_rating_key_idx
    ON public.recommendations (username, rating_key);

CREATE INDEX IF NOT EXISTS recommendations_username_score_idx
    ON public.recommendations (username, predicted_probability DESC);

CREATE INDEX IF NOT EXISTS library_show_rating_key_idx
    ON public.library (show_rating_key);

CREATE INDEX IF NOT EXISTS watch_history_username_rating_key_idx
    ON public.watch_history (username, rating_key);

CREATE INDEX IF NOT EXISTS watch_history_username_show_rating_key_idx
    ON public.watch_history (username, show_rating_key);

DROP VIEW IF EXISTS public.show_rollups_v CASCADE;
DROP VIEW IF EXISTS public.season_rollups_v CASCADE;
DROP VIEW IF EXISTS public.expanded_recs_w_label_v CASCADE;

CREATE VIEW public.expanded_recs_w_label_v AS
 SELECT r.rating_key,
    r.username,
    uv.friendly_name,
    r.scored_at,
    m.media_type,
    m.show_title,
    m.title,
    m.season_number,
    m.episode_number,
    m.parent_rating_key,
    m.show_rating_key,
    m.rating,
    m.year,
    m.summary,
    m.duration,
    m.added_at,
    g.genres,
    a.actors,
    d.directors,
    r.predicted_probability,
    ( SELECT string_agg(DISTINCT el.label, ', '::text) AS string_agg
           FROM (( SELECT si.dimension
                   FROM public.shap_impact si
                  WHERE ((si.rating_key = r.rating_key) AND (si.user_id = r.username))
                 LIMIT 5) top_dims
             JOIN public.embedding_labels el ON ((top_dims.dimension = el.dimension)))
          WHERE (el.label IS NOT NULL)) AS semantic_themes
   FROM public.recommendations r
     JOIN public.library m ON (r.rating_key = m.rating_key)
     JOIN public.users_v uv ON (r.username = uv.username)
     LEFT JOIN ( SELECT mg.media_id,
            string_agg(DISTINCT g.name, ', '::text) AS genres
           FROM public.media_genres mg
             JOIN public.genres g ON (mg.genre_id = g.id)
          GROUP BY mg.media_id) g ON (g.media_id = m.rating_key)
     LEFT JOIN ( SELECT ma.media_id,
            string_agg(DISTINCT a.name, ', '::text) AS actors
           FROM public.media_actors ma
             JOIN public.actors a ON (ma.actor_id = a.id)
          GROUP BY ma.media_id) a ON (a.media_id = m.rating_key)
     LEFT JOIN ( SELECT md.media_id,
            string_agg(DISTINCT d.name, ', '::text) AS directors
           FROM public.media_directors md
             JOIN public.directors d ON (md.director_id = d.id)
          GROUP BY md.media_id) d ON (d.media_id = m.rating_key)
  WHERE NOT (EXISTS ( SELECT 1
           FROM public.watch_history w
          WHERE ((w.username = r.username) AND (w.rating_key = r.rating_key) AND (((w.percent_complete IS NOT NULL) AND
            (CASE
                WHEN (w.percent_complete > (1)::double precision) THEN (w.percent_complete / (100.0)::double precision)
                ELSE w.percent_complete
            END >= (0.5)::double precision)) OR ((w.played_duration IS NOT NULL) AND (m.duration IS NOT NULL) AND (m.duration > 0) AND ((w.played_duration)::double precision / ((m.duration)::double precision / (1000.0)::double precision)) >= (0.5)::double precision))))));

CREATE VIEW public.show_rollups_v AS
 WITH episode_recs AS (
         SELECT r.username,
            r.rating_key,
            r.predicted_probability,
            r.scored_at,
            r.show_rating_key,
            r.show_title
           FROM public.expanded_recs_w_label_v r
          WHERE ((r.media_type = 'episode'::text) AND (r.show_rating_key IS NOT NULL))
        ), ranked AS (
         SELECT episode_recs.username,
            episode_recs.rating_key,
            episode_recs.predicted_probability,
            episode_recs.scored_at,
            episode_recs.show_rating_key,
            episode_recs.show_title,
            row_number() OVER (PARTITION BY episode_recs.username, episode_recs.show_rating_key ORDER BY episode_recs.predicted_probability DESC) AS rn,
            count(*) OVER (PARTITION BY episode_recs.username, episode_recs.show_rating_key) AS cnt,
            max(episode_recs.scored_at) OVER (PARTITION BY episode_recs.username, episode_recs.show_rating_key) AS last_scored_at
           FROM episode_recs
        ), topk AS (
         SELECT ranked.username,
            ranked.rating_key,
            ranked.predicted_probability,
            ranked.scored_at,
            ranked.show_rating_key,
            ranked.show_title,
            ranked.rn,
            ranked.cnt,
            ranked.last_scored_at,
            GREATEST(1, (ceil(((ranked.cnt)::double precision * (0.2)::double precision)))::integer) AS top_k
           FROM ranked
        ), rollup AS (
         SELECT topk.username,
            topk.show_rating_key,
            max(topk.show_title) AS show_title,
            avg(topk.predicted_probability) FILTER (WHERE (topk.rn <= topk.top_k)) AS rollup_score,
            max(topk.cnt) AS episode_count,
            max(topk.top_k) AS top_k,
            max(topk.last_scored_at) AS scored_at
           FROM topk
          GROUP BY topk.username, topk.show_rating_key
        ), with_genres AS (
         SELECT rollup.username,
            rollup.show_rating_key,
            rollup.show_title,
            rollup.rollup_score,
            rollup.episode_count,
            rollup.top_k,
            rollup.scored_at,
            g.genres,
            ls.year
           FROM (rollup
             LEFT JOIN ( SELECT mg.media_id,
                    string_agg(DISTINCT g.name, ', '::text) AS genres
                   FROM (public.media_genres mg
                     JOIN public.genres g ON ((mg.genre_id = g.id)))
                  GROUP BY mg.media_id) g ON ((g.media_id = rollup.show_rating_key)))
             LEFT JOIN public.library ls ON ((ls.rating_key = rollup.show_rating_key))
        )
 SELECT x.username,
    uv.friendly_name,
    x.show_rating_key,
    x.show_title,
    x.year,
    x.genres,
    x.rollup_score,
    x.episode_count,
    x.top_k,
    x.scored_at,
    x.score_percentile,
        CASE
            WHEN (x.score_percentile <= (0.2)::double precision) THEN '0-20'::text
            WHEN (x.score_percentile <= (0.5)::double precision) THEN '21-50'::text
            WHEN (x.score_percentile <= (0.8)::double precision) THEN '51-80'::text
            ELSE '81-100'::text
        END AS score_band
   FROM (( SELECT with_genres.username,
            with_genres.show_rating_key,
            with_genres.show_title,
            with_genres.rollup_score,
            with_genres.episode_count,
            with_genres.top_k,
            with_genres.scored_at,
            with_genres.genres,
            with_genres.year,
            percent_rank() OVER (PARTITION BY with_genres.username ORDER BY with_genres.rollup_score) AS score_percentile
           FROM with_genres) x
     JOIN public.users_v uv ON ((uv.username = x.username)));

CREATE VIEW public.season_rollups_v AS
 WITH episode_recs AS (
         SELECT r.username,
            r.rating_key,
            r.predicted_probability,
            r.scored_at,
            r.show_rating_key,
            r.show_title,
            r.parent_rating_key AS season_rating_key
           FROM public.expanded_recs_w_label_v r
          WHERE ((r.media_type = 'episode'::text) AND (r.parent_rating_key IS NOT NULL))
        ), ranked AS (
         SELECT episode_recs.username,
            episode_recs.rating_key,
            episode_recs.predicted_probability,
            episode_recs.scored_at,
            episode_recs.show_rating_key,
            episode_recs.show_title,
            episode_recs.season_rating_key,
            row_number() OVER (PARTITION BY episode_recs.username, episode_recs.season_rating_key ORDER BY episode_recs.predicted_probability DESC) AS rn,
            count(*) OVER (PARTITION BY episode_recs.username, episode_recs.season_rating_key) AS cnt,
            max(episode_recs.scored_at) OVER (PARTITION BY episode_recs.username, episode_recs.season_rating_key) AS last_scored_at
           FROM episode_recs
        ), topk AS (
         SELECT ranked.username,
            ranked.rating_key,
            ranked.predicted_probability,
            ranked.scored_at,
            ranked.show_rating_key,
            ranked.show_title,
            ranked.season_rating_key,
            ranked.rn,
            ranked.cnt,
            ranked.last_scored_at,
            GREATEST(1, (ceil(((ranked.cnt)::double precision * (0.2)::double precision)))::integer) AS top_k
           FROM ranked
        ), rollup AS (
         SELECT topk.username,
            topk.season_rating_key,
            max(topk.show_rating_key) AS show_rating_key,
            max(topk.show_title) AS show_title,
            avg(topk.predicted_probability) FILTER (WHERE (topk.rn <= topk.top_k)) AS rollup_score,
            max(topk.cnt) AS episode_count,
            max(topk.top_k) AS top_k,
            max(topk.last_scored_at) AS scored_at
           FROM topk
          GROUP BY topk.username, topk.season_rating_key
        ), with_meta AS (
         SELECT rollup.username,
            rollup.season_rating_key,
            rollup.show_rating_key,
            rollup.show_title,
            rollup.rollup_score,
            rollup.episode_count,
            rollup.top_k,
            rollup.scored_at,
            s.title AS season_title,
            s.season_number,
            s.year,
            g.genres
           FROM (rollup
             LEFT JOIN public.library s ON ((s.rating_key = rollup.season_rating_key)))
             LEFT JOIN ( SELECT mg.media_id,
                    string_agg(DISTINCT g.name, ', '::text) AS genres
                   FROM (public.media_genres mg
                     JOIN public.genres g ON ((mg.genre_id = g.id)))
                  GROUP BY mg.media_id) g ON ((g.media_id = rollup.season_rating_key))
        )
 SELECT x.username,
    uv.friendly_name,
    x.show_rating_key,
    x.show_title,
    x.season_rating_key,
    x.season_title,
    x.season_number,
    x.year,
    x.genres,
    x.rollup_score,
    x.episode_count,
    x.top_k,
    x.scored_at,
    x.score_percentile,
        CASE
            WHEN (x.score_percentile <= (0.2)::double precision) THEN '0-20'::text
            WHEN (x.score_percentile <= (0.5)::double precision) THEN '21-50'::text
            WHEN (x.score_percentile <= (0.8)::double precision) THEN '51-80'::text
            ELSE '81-100'::text
        END AS score_band
   FROM (( SELECT with_meta.username,
            with_meta.season_rating_key,
            with_meta.show_rating_key,
            with_meta.show_title,
            with_meta.rollup_score,
            with_meta.episode_count,
            with_meta.top_k,
            with_meta.scored_at,
            with_meta.season_title,
            with_meta.season_number,
            with_meta.year,
            with_meta.genres,
            percent_rank() OVER (PARTITION BY with_meta.username ORDER BY with_meta.rollup_score) AS score_percentile
           FROM with_meta) x
     JOIN public.users_v uv ON ((uv.username = x.username)));

COMMIT;
