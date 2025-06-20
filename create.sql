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
    m.rating,
    m.year,
    string_agg(DISTINCT g.name, ', '::text) AS genres,
    r.predicted_probability,
    ( SELECT string_agg(DISTINCT el.label, ', '::text) AS string_agg
           FROM (( SELECT si.dimension
                   FROM public.shap_impact si
                  WHERE ((si.rating_key = r.rating_key) AND (si.user_id = r.username))
                 LIMIT 5) top_dims
             JOIN public.embedding_labels el ON ((top_dims.dimension = el.dimension)))
          WHERE (el.label IS NOT NULL)) AS semantic_themes
   FROM ((((public.recommendations r
     JOIN public.library m ON ((r.rating_key = m.rating_key)))
     JOIN public.users_v uv ON ((r.username = uv.username)))
     LEFT JOIN public.media_genres mg ON ((mg.media_id = m.rating_key)))
     LEFT JOIN public.genres g ON ((mg.genre_id = g.id)))
  GROUP BY r.rating_key, r.username, uv.friendly_name, r.scored_at, m.media_type, m.show_title, m.title, m.season_number, m.episode_number, m.year, m.rating, r.predicted_probability
  ORDER BY r.predicted_probability DESC;



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
-- PostgreSQL database dump complete
--

