BEGIN;

ALTER TABLE public.media_actors
    ADD COLUMN IF NOT EXISTS cast_order integer;

CREATE OR REPLACE VIEW public.expanded_recs_w_label_v AS
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
        CASE
            WHEN (m.media_type = ANY (ARRAY['movie'::text, 'show'::text, 'series'::text])) THEN m.thumb_path
            WHEN (m.media_type = 'season'::text) THEN COALESCE(m.thumb_path, m.parent_thumb_path)
            WHEN (m.media_type = 'episode'::text) THEN COALESCE(m.parent_thumb_path, m.grandparent_thumb_path, m.thumb_path)
            ELSE COALESCE(m.thumb_path, m.parent_thumb_path, m.grandparent_thumb_path)
        END AS poster_path,
    g.genres,
    a.actors,
    d.directors,
    r.predicted_probability,
    ( SELECT string_agg(top_labels.label, ', '::text ORDER BY top_labels.max_shap DESC) AS string_agg
           FROM ( SELECT el.label,
                    max(si.shap_value) AS max_shap
                   FROM public.shap_impact si
                     JOIN public.embedding_labels el ON (si.dimension = el.dimension)
                  WHERE ((si.rating_key = r.rating_key) AND (si.user_id = r.username) AND (si.shap_value > (0)::double precision) AND (el.label IS NOT NULL))
                  GROUP BY el.label
                  ORDER BY (max(si.shap_value)) DESC
                 LIMIT 3) top_labels) AS semantic_themes
   FROM public.recommendations r
     JOIN public.library m ON (r.rating_key = m.rating_key)
     JOIN public.users_v uv ON (r.username = uv.username)
     LEFT JOIN ( SELECT mg.media_id,
            string_agg(DISTINCT g.name, ', '::text) AS genres
           FROM public.media_genres mg
             JOIN public.genres g ON (mg.genre_id = g.id)
          GROUP BY mg.media_id) g ON (g.media_id = m.rating_key)
     LEFT JOIN ( SELECT ma.media_id,
            string_agg(a.name, ', '::text ORDER BY ma.cast_order NULLS LAST, a.name) AS actors
           FROM public.media_actors ma
             JOIN public.actors a ON (ma.actor_id = a.id)
          GROUP BY ma.media_id) a ON (a.media_id = m.rating_key)
     LEFT JOIN ( SELECT md.media_id,
            string_agg(DISTINCT d.name, ', '::text) AS directors
           FROM public.media_directors md
             JOIN public.directors d ON (md.director_id = d.id)
          GROUP BY md.media_id) d ON (d.media_id = m.rating_key)
  WHERE NOT EXISTS (
           SELECT 1
           FROM public.watch_history w
           WHERE w.username = r.username
             AND w.rating_key = r.rating_key
             AND (
               (
                 w.percent_complete IS NOT NULL
                 AND (
                   CASE
                     WHEN w.percent_complete >= (1)::double precision
                       THEN w.percent_complete / (100.0)::double precision
                     ELSE w.percent_complete
                   END
                 ) >= (0.5)::double precision
               )
               OR (
                 w.played_duration IS NOT NULL
                 AND m.duration IS NOT NULL
                 AND m.duration > 0
                 AND ((w.played_duration)::double precision / ((m.duration)::double precision / (1000.0)::double precision)) >= (0.5)::double precision
               )
             )
        );

CREATE OR REPLACE VIEW public.media_enriched_v AS
 SELECT m.rating_key,
    m.media_type,
    m.show_title,
    m.title,
    m.summary,
    m.season_number,
    m.episode_number,
    m.rating,
    m.year,
    m.duration,
    g_agg.genres,
    a_agg.actors,
    d_agg.directors
   FROM public.library m
     LEFT JOIN ( SELECT mg.media_id,
            string_agg(DISTINCT g.name, ', '::text) AS genres
           FROM public.media_genres mg
             JOIN public.genres g ON (g.id = mg.genre_id)
          GROUP BY mg.media_id) g_agg ON (g_agg.media_id = m.rating_key)
     LEFT JOIN ( SELECT ma.media_id,
            string_agg(a.name, ', '::text ORDER BY ma.cast_order NULLS LAST, a.name) AS actors
           FROM public.media_actors ma
             JOIN public.actors a ON (a.id = ma.actor_id)
          GROUP BY ma.media_id) a_agg ON (a_agg.media_id = m.rating_key)
     LEFT JOIN ( SELECT md.media_id,
            string_agg(DISTINCT d.name, ', '::text) AS directors
           FROM public.media_directors md
             JOIN public.directors d ON (d.id = md.director_id)
          GROUP BY md.media_id) d_agg ON (d_agg.media_id = m.rating_key);

CREATE OR REPLACE VIEW public.library_catalog_v AS
 WITH g AS (
         SELECT mg.media_id AS rating_key,
            array_agg(DISTINCT g_1.name ORDER BY g_1.name) AS genres_arr_raw,
            string_agg(DISTINCT g_1.name, ', '::text ORDER BY g_1.name) AS genres
           FROM public.media_genres mg
             JOIN public.genres g_1 ON (g_1.id = mg.genre_id)
          GROUP BY mg.media_id
        ), a AS (
         SELECT ma.media_id AS rating_key,
            array_agg(ac.name ORDER BY ma.cast_order NULLS LAST, ac.name) AS actors_arr_raw,
            string_agg(ac.name, ', '::text ORDER BY ma.cast_order NULLS LAST, ac.name) AS actors
           FROM public.media_actors ma
             JOIN public.actors ac ON (ac.id = ma.actor_id)
          GROUP BY ma.media_id
        ), d AS (
         SELECT md.media_id AS rating_key,
            array_agg(DISTINCT di.name ORDER BY di.name) AS directors_arr_raw,
            string_agg(DISTINCT di.name, ', '::text ORDER BY di.name) AS directors
           FROM public.media_directors md
             JOIN public.directors di ON (di.id = md.director_id)
          GROUP BY md.media_id
        )
 SELECT m.rating_key,
    m.title,
    m.year,
    m.media_type,
    m.duration,
    m.added_at,
    COALESCE(g.genres_arr_raw, ARRAY[]::text[]) AS genres_arr,
    COALESCE(g.genres, ''::text) AS genres,
    COALESCE(a.actors_arr_raw, ARRAY[]::text[]) AS actors_arr,
    COALESCE(a.actors, ''::text) AS actors,
    COALESCE(d.directors_arr_raw, ARRAY[]::text[]) AS directors_arr,
    COALESCE(d.directors, ''::text) AS directors,
    m.rating,
    m.summary,
    m.season_number,
    m.episode_number,
    m.show_title,
    COALESCE(m.episode_title, m.title) AS episode_title,
    m.episode_summary,
        CASE
            WHEN ((m.media_type = 'episode'::text) AND (m.season_number IS NOT NULL) AND (m.episode_number IS NOT NULL)) THEN ((('S'::text || to_char(m.season_number, 'FM00'::text)) || 'E'::text) || to_char(m.episode_number, 'FM00'::text))
            ELSE NULL::text
        END AS season_episode_code,
        CASE
            WHEN (m.media_type = 'episode'::text) THEN COALESCE(m.show_title, m.title)
            ELSE m.title
        END AS series_title,
        CASE
            WHEN (m.media_type = 'episode'::text) THEN TRIM(BOTH ' '::text FROM (((COALESCE(m.show_title, m.title) ||
            CASE
                WHEN ((m.season_number IS NOT NULL) AND (m.episode_number IS NOT NULL)) THEN ((((' '::text || 'S'::text) || to_char(m.season_number, 'FM00'::text)) || 'E'::text) || to_char(m.episode_number, 'FM00'::text))
                ELSE ''::text
            END) || ' · '::text) || COALESCE(m.episode_title, m.title)))
            WHEN (m.media_type = 'movie'::text) THEN (((m.title || ' ('::text) || COALESCE((m.year)::text, '?'::text)) || ')'::text)
            ELSE m.title
        END AS display_title,
    lower(m.title) AS title_ci,
    m.added_at AS changed_at,
    m.thumb_path,
    m.parent_thumb_path,
    m.grandparent_thumb_path
   FROM public.library m
     LEFT JOIN g ON (g.rating_key = m.rating_key)
     LEFT JOIN a ON (a.rating_key = m.rating_key)
     LEFT JOIN d ON (d.rating_key = m.rating_key);

COMMIT;
