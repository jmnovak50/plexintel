BEGIN;

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
            string_agg(DISTINCT a.name, ', '::text) AS actors
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
                     WHEN w.percent_complete > (1)::double precision
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

COMMIT;
