--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5 (Debian 17.5-1.pgdg120+1)
-- Dumped by pg_dump version 17.0

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
--

CREATE SCHEMA IF NOT EXISTS public;



--
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
--

DROP FUNCTION IF EXISTS public.update_modified_at_column() CASCADE;
CREATE FUNCTION public.update_modified_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
   NEW.modified_at = now();
   RETURN NEW;
END;
$$;



--
--

DROP FUNCTION IF EXISTS public.vector_get(embedding CASCADE;
CREATE FUNCTION public.vector_get(embedding public.vector, index integer) RETURNS double precision
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN (embedding[index:index+1])[1];
END;
$$;



SET default_tablespace = '';

SET default_table_access_method = heap;

--
--

CREATE TABLE IF NOT EXISTS public.actors (
    id integer NOT NULL,
    name text
);



--
--

CREATE SEQUENCE IF NOT EXISTS public.actors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.actors_id_seq OWNED BY public.actors.id;


--
--

CREATE TABLE IF NOT EXISTS public.directors (
    id integer NOT NULL,
    name text
);



--
--

CREATE SEQUENCE IF NOT EXISTS public.directors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.directors_id_seq OWNED BY public.directors.id;


--
--

CREATE TABLE IF NOT EXISTS public.embedding_labels (
    dimension integer NOT NULL,
    label text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);



--
--

CREATE TABLE IF NOT EXISTS public.genres (
    id integer NOT NULL,
    name text
);



--
--

CREATE TABLE IF NOT EXISTS public.library (
    rating_key integer NOT NULL,
    title text,
    year integer,
    duration integer,
    added_at timestamp without time zone,
    media_type text,
    rating text,
    summary text,
    season_number integer,
    episode_number integer,
    parent_rating_key integer,
    show_rating_key integer,
    show_title text,
    episode_title text,
    episode_summary text
);



--
--

CREATE TABLE IF NOT EXISTS public.media_genres (
    media_id integer NOT NULL,
    genre_id integer NOT NULL
);



--
--

CREATE TABLE IF NOT EXISTS public.recommendations (
    id integer NOT NULL,
    username text NOT NULL,
    rating_key integer NOT NULL,
    predicted_probability double precision NOT NULL,
    model_name text DEFAULT 'xgb_model'::text,
    scored_at timestamp without time zone DEFAULT now(),
    rank integer,
    was_recommended boolean DEFAULT false,
    shown_at timestamp without time zone,
    watched_after boolean,
    explanation text,
    cosine_similarity double precision,
    embedding_theme text
);



--
--

CREATE TABLE IF NOT EXISTS public.watch_history (
    watch_id integer NOT NULL,
    username text,
    title text,
    media_type text,
    watched_at timestamp without time zone,
    played_duration integer,
    percent_complete double precision,
    rating_key integer,
    show_rating_key integer,
    episode_title text,
    season_number integer,
    episode_number integer,
    friendly_name text
);



--
--

DROP VIEW IF EXISTS public.users_v CASCADE;
CREATE VIEW public.users_v AS
 SELECT DISTINCT username,
    friendly_name
   FROM public.watch_history;



--
--

DROP VIEW IF EXISTS public.expanded_recs_v CASCADE;
CREATE VIEW public.expanded_recs_v AS
 SELECT r.rating_key,
    r.username,
    uv.friendly_name,
    r.scored_at,
    m.media_type,
    m.show_title,
    m.title,
    m.season_number,
    m.episode_number,
    m.year,
    string_agg(DISTINCT g.name, ', '::text) AS genres,
    r.predicted_probability
   FROM ((((public.recommendations r
     JOIN public.library m ON ((r.rating_key = m.rating_key)))
     JOIN public.users_v uv ON ((r.username = uv.username)))
     LEFT JOIN public.media_genres mg ON ((mg.media_id = m.rating_key)))
     LEFT JOIN public.genres g ON ((mg.genre_id = g.id)))
  GROUP BY r.rating_key, r.username, uv.friendly_name, r.scored_at, m.media_type, m.show_title, m.title, m.season_number, m.episode_number, m.year, r.predicted_probability
  ORDER BY r.predicted_probability DESC;



--
--

CREATE TABLE IF NOT EXISTS public.shap_impact (
    user_id text NOT NULL,
    rating_key integer NOT NULL,
    dimension integer NOT NULL,
    shap_value double precision NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    modified_at timestamp without time zone DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_shap_impact_user_rating_dimension_ux
    ON public.shap_impact (user_id, rating_key, dimension);

CREATE INDEX IF NOT EXISTS idx_shap_impact_user_rating_key
    ON public.shap_impact (user_id, rating_key);

CREATE TABLE IF NOT EXISTS public.shap_dimension_stats_current (
    dimension integer PRIMARY KEY,
    usage_count integer NOT NULL DEFAULT 0,
    sum_abs_shap double precision NOT NULL DEFAULT 0,
    avg_abs_shap double precision NOT NULL DEFAULT 0,
    combined_score double precision NOT NULL DEFAULT 0,
    user_count integer NOT NULL DEFAULT 0,
    modified_at timestamp without time zone NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_shap_dimension_stats_current_score
    ON public.shap_dimension_stats_current (combined_score DESC);



--
--

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
                  ORDER BY abs(si.shap_value) DESC
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


--
--

DROP VIEW IF EXISTS public.show_rollups_v CASCADE;
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


--
--

DROP VIEW IF EXISTS public.season_rollups_v CASCADE;
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



--
--

CREATE SEQUENCE IF NOT EXISTS public.genres_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.genres_id_seq OWNED BY public.genres.id;


--
--

CREATE SEQUENCE IF NOT EXISTS public.library_rating_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.library_rating_key_seq OWNED BY public.library.rating_key;


--
--

CREATE TABLE IF NOT EXISTS public.media_actors (
    media_id integer NOT NULL,
    actor_id integer NOT NULL
);



--
--

CREATE TABLE IF NOT EXISTS public.media_directors (
    media_id integer NOT NULL,
    director_id integer NOT NULL
);



--
--

CREATE TABLE IF NOT EXISTS public.media_embeddings (
    rating_key integer NOT NULL,
    embedding public.vector(768)
);



--
--

CREATE TABLE IF NOT EXISTS public.movies (
    id integer NOT NULL,
    title text NOT NULL,
    year integer,
    duration integer,
    rating text,
    summary text
);



--
--

CREATE SEQUENCE IF NOT EXISTS public.movies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.movies_id_seq OWNED BY public.movies.id;


--
--

CREATE SEQUENCE IF NOT EXISTS public.recommendations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.recommendations_id_seq OWNED BY public.recommendations.id;


--
--

CREATE TABLE IF NOT EXISTS public.training_data (
    id integer NOT NULL,
    username text,
    rating_key integer,
    label integer,
    embedding public.vector(768),
    genre_tags text,
    actor_tags text,
    director_tags text,
    played_duration integer,
    media_duration integer,
    engagement_ratio double precision,
    watch_sim double precision,
    release_year integer,
    season_number integer,
    episode_number integer
);



--
--

CREATE SEQUENCE IF NOT EXISTS public.training_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.training_data_id_seq OWNED BY public.training_data.id;


--
--

CREATE TABLE IF NOT EXISTS public.user_embeddings (
    username text NOT NULL,
    embedding public.vector(768)
);



--
--

CREATE TABLE IF NOT EXISTS public.users (
    user_id integer NOT NULL,
    username text NOT NULL,
    plex_email text,
    plex_token text,
    created_at timestamp with time zone DEFAULT now(),
    last_login timestamp with time zone,
    modified_at timestamp with time zone DEFAULT now()
);



--
--

CREATE SEQUENCE IF NOT EXISTS public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
--

CREATE TABLE IF NOT EXISTS public.watch_embeddings (
    watch_id integer NOT NULL,
    embedding public.vector(768)
);



--
--

CREATE SEQUENCE IF NOT EXISTS public.watch_history_watch_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;



--
--

ALTER SEQUENCE public.watch_history_watch_id_seq OWNED BY public.watch_history.watch_id;


--
--

ALTER TABLE ONLY public.actors ALTER COLUMN id SET DEFAULT nextval('public.actors_id_seq'::regclass);


--
--

ALTER TABLE ONLY public.directors ALTER COLUMN id SET DEFAULT nextval('public.directors_id_seq'::regclass);


--
--

ALTER TABLE ONLY public.genres ALTER COLUMN id SET DEFAULT nextval('public.genres_id_seq'::regclass);


--
--

ALTER TABLE ONLY public.library ALTER COLUMN rating_key SET DEFAULT nextval('public.library_rating_key_seq'::regclass);


--
--

ALTER TABLE ONLY public.movies ALTER COLUMN id SET DEFAULT nextval('public.movies_id_seq'::regclass);


--
--

ALTER TABLE ONLY public.recommendations ALTER COLUMN id SET DEFAULT nextval('public.recommendations_id_seq'::regclass);


--
--

ALTER TABLE ONLY public.training_data ALTER COLUMN id SET DEFAULT nextval('public.training_data_id_seq'::regclass);


--
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
--

ALTER TABLE ONLY public.watch_history ALTER COLUMN watch_id SET DEFAULT nextval('public.watch_history_watch_id_seq'::regclass);


--
--

CREATE INDEX IF NOT EXISTS recommendations_username_rating_key_idx ON public.recommendations (username, rating_key);

CREATE INDEX IF NOT EXISTS recommendations_username_score_idx ON public.recommendations (username, predicted_probability DESC);

CREATE INDEX IF NOT EXISTS library_show_rating_key_idx ON public.library (show_rating_key);

CREATE INDEX IF NOT EXISTS watch_history_username_rating_key_idx ON public.watch_history (username, rating_key);

CREATE INDEX IF NOT EXISTS watch_history_username_show_rating_key_idx ON public.watch_history (username, show_rating_key);


--
-- PostgreSQL database dump complete
--
