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
-- Name: public; Type: SCHEMA; Schema: -; Owner: pg_database_owner
--

CREATE SCHEMA public;


ALTER SCHEMA public OWNER TO pg_database_owner;

--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: pg_database_owner
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: update_modified_at_column(); Type: FUNCTION; Schema: public; Owner: jmnovak
--

CREATE FUNCTION public.update_modified_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
   NEW.modified_at = now();
   RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_modified_at_column() OWNER TO jmnovak;

--
-- Name: vector_get(public.vector, integer); Type: FUNCTION; Schema: public; Owner: jmnovak
--

CREATE FUNCTION public.vector_get(embedding public.vector, index integer) RETURNS double precision
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN (embedding[index:index+1])[1];
END;
$$;


ALTER FUNCTION public.vector_get(embedding public.vector, index integer) OWNER TO jmnovak;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: actors; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.actors (
    id integer NOT NULL,
    name text
);


ALTER TABLE public.actors OWNER TO jmnovak;

--
-- Name: actors_id_seq; Type: SEQUENCE; Schema: public; Owner: jmnovak
--

CREATE SEQUENCE public.actors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.actors_id_seq OWNER TO jmnovak;

--
-- Name: actors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jmnovak
--

ALTER SEQUENCE public.actors_id_seq OWNED BY public.actors.id;


--
-- Name: directors; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.directors (
    id integer NOT NULL,
    name text
);


ALTER TABLE public.directors OWNER TO jmnovak;

--
-- Name: directors_id_seq; Type: SEQUENCE; Schema: public; Owner: jmnovak
--

CREATE SEQUENCE public.directors_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.directors_id_seq OWNER TO jmnovak;

--
-- Name: directors_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jmnovak
--

ALTER SEQUENCE public.directors_id_seq OWNED BY public.directors.id;


--
-- Name: embedding_labels; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.embedding_labels (
    dimension integer NOT NULL,
    label text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.embedding_labels OWNER TO jmnovak;

--
-- Name: genres; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.genres (
    id integer NOT NULL,
    name text
);


ALTER TABLE public.genres OWNER TO jmnovak;

--
-- Name: library; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.library (
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


ALTER TABLE public.library OWNER TO jmnovak;

--
-- Name: media_genres; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.media_genres (
    media_id integer NOT NULL,
    genre_id integer NOT NULL
);


ALTER TABLE public.media_genres OWNER TO jmnovak;

--
-- Name: recommendations; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.recommendations (
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


ALTER TABLE public.recommendations OWNER TO jmnovak;

--
-- Name: watch_history; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.watch_history (
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


ALTER TABLE public.watch_history OWNER TO jmnovak;

--
-- Name: users_v; Type: VIEW; Schema: public; Owner: jmnovak
--

CREATE VIEW public.users_v AS
 SELECT DISTINCT username,
    friendly_name
   FROM public.watch_history;


ALTER VIEW public.users_v OWNER TO jmnovak;

--
-- Name: expanded_recs_v; Type: VIEW; Schema: public; Owner: jmnovak
--

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


ALTER VIEW public.expanded_recs_v OWNER TO jmnovak;

--
-- Name: shap_impact; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.shap_impact (
    user_id text NOT NULL,
    rating_key integer NOT NULL,
    dimension integer NOT NULL,
    shap_value double precision NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    modified_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.shap_impact OWNER TO jmnovak;

--
-- Name: expanded_recs_w_label_v; Type: VIEW; Schema: public; Owner: jmnovak
--

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


ALTER VIEW public.expanded_recs_w_label_v OWNER TO jmnovak;

--
-- Name: genres_id_seq; Type: SEQUENCE; Schema: public; Owner: jmnovak
--

CREATE SEQUENCE public.genres_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.genres_id_seq OWNER TO jmnovak;

--
-- Name: genres_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jmnovak
--

ALTER SEQUENCE public.genres_id_seq OWNED BY public.genres.id;


--
-- Name: library_rating_key_seq; Type: SEQUENCE; Schema: public; Owner: jmnovak
--

CREATE SEQUENCE public.library_rating_key_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.library_rating_key_seq OWNER TO jmnovak;

--
-- Name: library_rating_key_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jmnovak
--

ALTER SEQUENCE public.library_rating_key_seq OWNED BY public.library.rating_key;


--
-- Name: media_actors; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.media_actors (
    media_id integer NOT NULL,
    actor_id integer NOT NULL
);


ALTER TABLE public.media_actors OWNER TO jmnovak;

--
-- Name: media_directors; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.media_directors (
    media_id integer NOT NULL,
    director_id integer NOT NULL
);


ALTER TABLE public.media_directors OWNER TO jmnovak;

--
-- Name: media_embeddings; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.media_embeddings (
    rating_key integer NOT NULL,
    embedding public.vector(768)
);


ALTER TABLE public.media_embeddings OWNER TO jmnovak;

--
-- Name: movies; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.movies (
    id integer NOT NULL,
    title text NOT NULL,
    year integer,
    duration integer,
    rating text,
    summary text
);


ALTER TABLE public.movies OWNER TO jmnovak;

--
-- Name: movies_id_seq; Type: SEQUENCE; Schema: public; Owner: jmnovak
--

CREATE SEQUENCE public.movies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.movies_id_seq OWNER TO jmnovak;

--
-- Name: movies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jmnovak
--

ALTER SEQUENCE public.movies_id_seq OWNED BY public.movies.id;


--
-- Name: recommendations_id_seq; Type: SEQUENCE; Schema: public; Owner: jmnovak
--

CREATE SEQUENCE public.recommendations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.recommendations_id_seq OWNER TO jmnovak;

--
-- Name: recommendations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jmnovak
--

ALTER SEQUENCE public.recommendations_id_seq OWNED BY public.recommendations.id;


--
-- Name: training_data; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.training_data (
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


ALTER TABLE public.training_data OWNER TO jmnovak;

--
-- Name: training_data_id_seq; Type: SEQUENCE; Schema: public; Owner: jmnovak
--

CREATE SEQUENCE public.training_data_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.training_data_id_seq OWNER TO jmnovak;

--
-- Name: training_data_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jmnovak
--

ALTER SEQUENCE public.training_data_id_seq OWNED BY public.training_data.id;


--
-- Name: user_embeddings; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.user_embeddings (
    username text NOT NULL,
    embedding public.vector(768)
);


ALTER TABLE public.user_embeddings OWNER TO jmnovak;

--
-- Name: users; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.users (
    user_id integer NOT NULL,
    username text NOT NULL,
    plex_email text,
    plex_token text,
    created_at timestamp with time zone DEFAULT now(),
    last_login timestamp with time zone,
    modified_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.users OWNER TO jmnovak;

--
-- Name: users_user_id_seq; Type: SEQUENCE; Schema: public; Owner: jmnovak
--

CREATE SEQUENCE public.users_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_user_id_seq OWNER TO jmnovak;

--
-- Name: users_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jmnovak
--

ALTER SEQUENCE public.users_user_id_seq OWNED BY public.users.user_id;


--
-- Name: watch_embeddings; Type: TABLE; Schema: public; Owner: jmnovak
--

CREATE TABLE public.watch_embeddings (
    watch_id integer NOT NULL,
    embedding public.vector(768)
);


ALTER TABLE public.watch_embeddings OWNER TO jmnovak;

--
-- Name: watch_history_watch_id_seq; Type: SEQUENCE; Schema: public; Owner: jmnovak
--

CREATE SEQUENCE public.watch_history_watch_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.watch_history_watch_id_seq OWNER TO jmnovak;

--
-- Name: watch_history_watch_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: jmnovak
--

ALTER SEQUENCE public.watch_history_watch_id_seq OWNED BY public.watch_history.watch_id;


--
-- Name: actors id; Type: DEFAULT; Schema: public; Owner: jmnovak
--

ALTER TABLE ONLY public.actors ALTER COLUMN id SET DEFAULT nextval('public.actors_id_seq'::regclass);


--
-- Name: directors id; Type: DEFAULT; Schema: public; Owner: jmnovak
--

ALTER TABLE ONLY public.directors ALTER COLUMN id SET DEFAULT nextval('public.directors_id_seq'::regclass);


--
-- Name: genres id; Type: DEFAULT; Schema: public; Owner: jmnovak
--

ALTER TABLE ONLY public.genres ALTER COLUMN id SET DEFAULT nextval('public.genres_id_seq'::regclass);


--
-- Name: library rating_key; Type: DEFAULT; Schema: public; Owner: jmnovak
--

ALTER TABLE ONLY public.library ALTER COLUMN rating_key SET DEFAULT nextval('public.library_rating_key_seq'::regclass);


--
-- Name: movies id; Type: DEFAULT; Schema: public; Owner: jmnovak
--

ALTER TABLE ONLY public.movies ALTER COLUMN id SET DEFAULT nextval('public.movies_id_seq'::regclass);


--
-- Name: recommendations id; Type: DEFAULT; Schema: public; Owner: jmnovak
--

ALTER TABLE ONLY public.recommendations ALTER COLUMN id SET DEFAULT nextval('public.recommendations_id_seq'::regclass);


--
-- Name: training_data id; Type: DEFAULT; Schema: public; Owner: jmnovak
--

ALTER TABLE ONLY public.training_data ALTER COLUMN id SET DEFAULT nextval('public.training_data_id_seq'::regclass);


--
-- Name: users user_id; Type: DEFAULT; Schema: public; Owner: jmnovak
--

ALTER TABLE ONLY public.users ALTER COLUMN user_id SET DEFAULT nextval('public.users_user_id_seq'::regclass);


--
-- Name: watch_history watch_id; Type: DEFAULT; Schema: public; Owner: jmnovak
--

ALTER TABLE ONLY public.watch_history ALTER COLUMN watch_id SET DEFAULT nextval('public.watch_history_watch_id_seq'::regclass);


--
-- PostgreSQL database dump complete
--

