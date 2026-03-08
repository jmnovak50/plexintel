from dotenv import load_dotenv
import os
import time
import requests
import json
import psycopg2
import argparse
import pandas as pd
from datetime import datetime
import psycopg2
from pgvector.psycopg2 import register_vector
from pgvector import Vector
# Ollama embedding client (NAS-hosted EmbeddingGemma)
from ollama_embeddings import embed_texts
from api.db.schema import ensure_app_schema
# Optional: batch sizing from env
EMBED_BATCH_SIZE = os.getenv("EMBED_BATCH_SIZE")

# ✅ Load environment variables
load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

DB_URL = os.getenv("DATABASE_URL")

TAUTULLI_API_URL = os.getenv("TAUTULLI_API_URL")
TAUTULLI_API_KEY = os.getenv("TAUTULLI_API_KEY")
TAUTULLI_URL = os.getenv("TAUTULLI_URL")

def safe_int(value):
    """Convert value to an integer safely, returning None if conversion fails."""
    if value in [None, "", " ", "None"]:  # Handle empty strings, spaces, and None
        return None
    try:
        return int(value)
    except ValueError:
        return None


# ✅ Fetch data from Tautulli API
import requests
import json
import psycopg2
import os

def clear_tautulli_cache():
    """
    Clear Tautulli's metadata cache so new/changed items show up.
    Uses the same TAUTULLI_URL and TAUTULLI_API_KEY as the rest of the script.
    """
    params = {
        "apikey": TAUTULLI_API_KEY,
        "cmd": "delete_cache",
    }
    try:
        resp = requests.get(f"{TAUTULLI_URL}/api/v2", params=params, timeout=30)
        resp.raise_for_status()
        print("✅ Cleared Tautulli cache via delete_cache")
    except Exception as e:
        print(f"❌ ERROR clearing Tautulli cache: {e}")

# ✅ Fetch data from Tautulli API
def fetch_tautulli_data(endpoint, params=None):
    if params is None:
        params = {}
    params["cmd"] = endpoint  
    params["apikey"] = os.getenv("TAUTULLI_API_KEY")

    try:
        response = requests.get(os.getenv("TAUTULLI_API_URL"), params=params)
        # print(f"🔍 DEBUG: API call to {endpoint} returned status {response.status_code}")

        try:
            data = response.json()
            # print(f"🔍 DEBUG: Raw API Response: {json.dumps(data, indent=2)}")
            return data.get("response", {}).get("data", {})
        except json.JSONDecodeError:
            # print(f"❌ ERROR: Invalid JSON response: {response.text}")
            return {}
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Network error occurred: {e}")
        return {}
    
# 👥 ---------- User sync helpers (Tautulli → users table) ----------

def fetch_tautulli_users():
    """
    Call Tautulli's get_users command and return the list of users.
    Uses the existing fetch_tautulli_data() helper.
    """
    data = fetch_tautulli_data("get_users")

    # Tautulli typically returns {"users": [ ... ]} inside data,
    # but some installs return the list directly.
    if isinstance(data, list):
        users = data
    elif isinstance(data, dict):
        users = data.get("users")
        if users is None and isinstance(data.get("data"), list):
            users = data["data"]
    else:
        print(f"⚠️ Unexpected payload type from get_users: {type(data)}")
        return []

    if not isinstance(users, list):
        print(f"⚠️ Unexpected payload from get_users: {data}")
        return []

    print(f"👥 Retrieved {len(users)} users from Tautulli.")
    return users


def sync_users_from_tautulli(conn, cursor):
    """
    Ensure every Tautulli user exists in our local `users` table.

    This version is conservative and only assumes a `username` column exists
    in the `users` table. It:
      - Pulls all users from Tautulli
      - Inserts missing usernames
      - Leaves existing rows alone

    If you later add more columns (friendly_name, email, tautulli_user_id, etc.)
    we can expand this function.
    """
    users = fetch_tautulli_users()
    if not users:
        print("⚠️ No users returned from Tautulli get_users; skipping user sync.")
        return

    print("👥 Syncing Tautulli users into the `users` table...")

    inserted = 0
    for u in users:
        if not isinstance(u, dict):
            print(f"⚠️ Skipping unexpected user entry: {u}")
            continue

        # Prefer username; fall back to friendly_name if needed
        username = u.get("username") or u.get("friendly_name")
        if username:
            username = str(username).strip()
        if not username:
            continue

        # Check if this user already exists
        cursor.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        exists = cursor.fetchone()
        if exists:
            continue

        # Insert new user row
        cursor.execute(
            """
            INSERT INTO users (username)
            VALUES (%s)
            """,
            (username,),
        )
        inserted += 1

    print(f"✅ User sync complete. Inserted {inserted} new user(s).")


# ✅ Connect to PostgreSQL Database
def connect_to_db():
    try:
        if DB_URL:
            conn = psycopg2.connect(DB_URL)
        else:
            conn = psycopg2.connect(**DB_CONFIG)
        # ✅ Tell psycopg2 how to handle pgvector's `vector` type
        register_vector(conn)

        cursor = conn.cursor()
        print("✅ Connected to PostgreSQL database")
        return conn, cursor
    except Exception as e:
        print(f"❌ ERROR: Could not connect to PostgreSQL: {e}")
        return None, None

    
def _media_text_for_embedding(row):
    """
    row = (rating_key, title, summary)
    Build a plain-text description for the embedding model.
    """
    rk, title, summary = row
    title = title or ""
    summary = summary or ""
    return f"{title} — {summary}".strip()

# ✅ Convert Unix timestamp to datetime
from datetime import datetime, UTC

def convert_timestamp(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp), UTC).strftime('%Y-%m-%d %H:%M:%S') if timestamp else None
    except (ValueError, TypeError):
        return None

# ✅ Convert value to integer
def convert_to_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None

# ✅ Fetch all paginated results from API
def fetch_paginated_data(endpoint):
    all_results = []
    start = 0
    count = 100  # Adjust if needed
    while True:
        params = {"start": start, "length": count}
        data = fetch_tautulli_data(endpoint, params)
        if not data or "recordsFiltered" in data and len(data.get("data", [])) == 0:
            break
        all_results.extend(data.get("data", []))
        start += count
    return all_results

import requests

def get_library_media_info(section_id, limit=None):
    """
    Fetches basic metadata for movies and TV shows from the Plex library.

    Args:
        section_id (int): The library section ID (1 for Movies, 2 for TV Shows)

    Returns:
        list: A list of media items with basic details (rating_key, title, year, added_at)
    """
    all_results = []
    start = 0
    page_size = 100  # Adjust as needed for performance

    while True:
        print(f"🔄 DEBUG: Fetching media info (section_id={section_id}, start={start})")
        params = {
            "section_id": section_id,
            "start": start,
            "length": page_size
        }
        data = fetch_tautulli_data("get_library_media_info", params)

        if not data or "data" not in data:
            print(f"⚠️ WARNING: No data returned for section_id={section_id}, start={start}")
            break

        media_items = data["data"]
        print(f"🔍 DEBUG: Retrieved {len(media_items)} items")

        if not media_items:
            print(f"⚠️ DEBUG: Empty media_items for section_id={section_id}, stopping.")
            break
        all_results.extend(media_items)

        # Pagination check: If results are less than page size, we are at the last page
        if limit and len(all_results) >= limit:
            all_results = all_results[:limit]
            break

        if len(media_items) < page_size:
            break

        start += page_size  # Move to next page

    print(f"✅ DEBUG: Fetched total {len(all_results)} items for section_id={section_id}")
    return all_results

def get_children_metadata(parent_rating_key):
    all_children = []
    start = 0
    page_size = 50  

    while True:
        print(f"🔄 Fetching children metadata for parent_rating_key={parent_rating_key}, start={start}")
        params = {
            "rating_key": parent_rating_key,
            "start": start,
            "length": page_size
        }
        data = fetch_tautulli_data("get_children_metadata", params)  

        # ✅ Ensure we're extracting from the correct key
        if not data or "children_list" not in data:
            print(f"⚠️ WARNING: No children found for parent_rating_key={parent_rating_key}")
            break

        children_list = data["children_list"]  # Extracting directly from children_list
        if not children_list:
            print(f"⚠️ No valid children data for parent_rating_key={parent_rating_key}")
            break

        print(f"📦 Batch received: {len(children_list)} items for parent_rating_key={parent_rating_key}")  # <-- Add this

        all_children.extend(children_list)

        if len(children_list) < page_size:
            break

        start += page_size  

    print(f"✅ Retrieved {len(all_children)} children for parent_rating_key={parent_rating_key}")
    return all_children



#def should_revise_metadata(metadata):
#    """
#    Determines if metadata requires revision.
#    Returns True if revision needed, otherwise False.
#    """
#    # Example condition: revise if crucial fields are missing or incomplete
#    required_fields = ['title', 'media_type', 'year']
#    return any(not metadata.get(field) for field in required_fields)


#def revise_metadata(metadata):
#    """
#    Perform necessary revisions to metadata.
#    Returns the revised metadata.
#    """
#    # Example revision logic
#    revised_metadata = metadata.copy()
#
#    if not revised_metadata.get('title'):
#        revised_metadata['title'] = "Unknown Title"
#
#    if not revised_metadata.get('media_type'):
#       revised_metadata['media_type'] = "movie"  # Default to 'movie' or other type
#
#    if not revised_metadata.get('year'):
#        revised_metadata['year'] = 0  # Default or placeholder year
#
#    print(f"🛠️ Revised metadata applied for rating_key={metadata.get('rating_key')}")
#    return revised_metadata


_METADATA_CACHE = {}

def get_metadata(rating_key):
    cache_key = safe_int(rating_key)
    if cache_key is not None and cache_key in _METADATA_CACHE:
        return _METADATA_CACHE[cache_key]

    print(f"🔄 Fetching detailed metadata for rating_key={rating_key}...")
    params = {"rating_key": rating_key}
    metadata = fetch_tautulli_data("get_metadata", params)

    if not metadata:
        print(f"⚠️ WARNING: No metadata found for rating_key={rating_key}. Trying cache clear...")
        clear_tautulli_cache()
        time.sleep(1)
        metadata = fetch_tautulli_data("get_metadata", params)
        if not metadata:
            print(f"❌ ERROR: Still no metadata found for rating_key={rating_key} after cache clear.")
            return None

    # -------------------------------------------------------------------------
    # 🧬 3-Tier Metadata Cascade (Episode -> Season -> Show)
    # -------------------------------------------------------------------------
    media_type = metadata.get("media_type")
    
    # Start with what the item itself has (often empty for episodes)
    final_genres = metadata.get("genres") or []
    final_actors = metadata.get("actors") or []
    final_directors = metadata.get("directors") or []
    
    if media_type == 'episode':
        grandparent_key = metadata.get('grandparent_rating_key')
        
        # 1. Level 1: Fetch Show (Grandparent) Metadata
        # We prioritize Show metadata for Genres and Actors because episodes usually lack them.
        if grandparent_key and (not final_genres or not final_actors):
            show_meta = get_metadata(grandparent_key)
            if show_meta:
                # Inherit Genres if missing (Crucial for "Comedy", "Sci-Fi" tags)
                if not final_genres:
                    final_genres = show_meta.get("genres", [])

                # Inherit Actors if missing (Crucial for "Steve Carell")
                if not final_actors:
                    final_actors = show_meta.get("actors", [])

    elif media_type == 'season':
        parent_key = metadata.get('parent_rating_key')
        
        # Level 1: Fetch Show (Parent of Season) Metadata
        if parent_key and (not final_genres or not final_actors):
            show_meta = get_metadata(parent_key)
            if show_meta:
                if not final_genres:
                    final_genres = show_meta.get("genres", [])
                if not final_actors:
                    final_actors = show_meta.get("actors", [])


    # -------------------------------------------------------------------------

    # ✅ Ensure correct extraction of season_number & episode_number
    if media_type == "episode":
        season_number = int(metadata["parent_media_index"]) if metadata.get("parent_media_index") else None
        episode_number = int(metadata["media_index"]) if metadata.get("media_index") else None
        show_rating_key = safe_int(metadata.get("grandparent_rating_key"))
    elif media_type == "season":
        season_number = int(metadata["media_index"]) if metadata.get("media_index") else None
        episode_number = None
        show_rating_key = safe_int(metadata.get("parent_rating_key"))
    elif media_type in ("show", "series"):
        season_number = None
        episode_number = None
        show_rating_key = safe_int(metadata.get("rating_key"))
    else:
        season_number = None
        episode_number = None
        show_rating_key = None

    out = {
        "rating_key": metadata.get("rating_key"),
        "title": metadata.get("title"),
        "summary": metadata.get("summary"),
        "rating": metadata.get("rating"),
        "added_at": metadata.get("added_at"),
        "year": int(metadata["year"]) if metadata.get("year") else None,
        "duration": int(metadata["duration"]) if metadata.get("duration") else None,
        "media_type": media_type,
        "parent_rating_key": metadata.get("parent_rating_key"),
        "show_rating_key": show_rating_key,
        "grandparent_title": metadata.get("grandparent_title"),  # TV Show name
        "parent_title": metadata.get("parent_title"),  # Season name
        "thumb_path": metadata.get("thumb"),
        "parent_thumb_path": metadata.get("parent_thumb"),
        "grandparent_thumb_path": metadata.get("grandparent_thumb"),
        "plex_guid": metadata.get("guid"),
        "season_number": season_number,
        "episode_number": episode_number,
        "genres": final_genres,    # ✅ Uses cascaded values
        "actors": final_actors,    # ✅ Uses cascaded values
        "directors": final_directors
    }

    out_key = safe_int(out.get("rating_key")) or cache_key
    if out_key is not None:
        _METADATA_CACHE[out_key] = out

    return out

# ✅ Fetch library metadata
def get_library_data(movies_limit=None, tv_limit=None):
    library_data = []

    # Fetch Movies (simple)
    movies = get_library_media_info(section_id=1, limit=movies_limit)
    print(f"🚨 DEBUG Movies fetched: {len(movies)}")  # Debug after movies fetched

    for movie in movies:
        metadata = get_metadata(movie["rating_key"])
        if metadata:
            library_data.append(metadata)
        else:
            print(f"⚠️ Movie metadata missing: rating_key={movie['rating_key']}")

    # Fetch TV Shows (complex hierarchy)
    tv_shows = get_library_media_info(section_id=2, limit=tv_limit)
    print(f"🚨 DEBUG TV Shows fetched: {len(tv_shows)}")  # Debug after TV Shows fetched

    for show in tv_shows:
        show_metadata = get_metadata(show["rating_key"])
        if show_metadata:
            library_data.append(show_metadata)
        else:
            print(f"⚠️ Show metadata missing: rating_key={show['rating_key']}")

        print(f"🔍 Fetching seasons for show: {show['title']} ({show['rating_key']})")
        seasons = get_children_metadata(show["rating_key"])  # ✅ Get Seasons
        seasons = [s for s in seasons if s.get("media_type") == "season"]  # ✅ Ensure only seasons
        print(f"🚨 DEBUG Seasons fetched for show {show['rating_key']}: {len(seasons)}")

        for season in seasons:
            # ✅ STORE SEASON METADATA (New for 3-Tier Model)
            season_metadata = get_metadata(season["rating_key"])
            if season_metadata:
                library_data.append(season_metadata)
            
            print(f"🔍 Fetching episodes for season: {season['title']} ({season['rating_key']})")
            episodes = get_children_metadata(season["rating_key"])  # ✅ Get Episodes
            episodes = [e for e in episodes if e.get("media_type") == "episode"]  # ✅ Ensure only episodes
            print(f"🚨 DEBUG Episodes fetched for season {season['rating_key']}: {len(episodes)}")

            for episode in episodes:
                episode_metadata = get_metadata(episode["rating_key"])
                if episode_metadata:
                    library_data.append(episode_metadata)  # ✅ Store Episodes
                else:
                    print(f"⚠️ Episode metadata missing: rating_key={episode['rating_key']}")

    return library_data

# ✅ Fetch watch history with pagination
def get_watch_history():
    return fetch_paginated_data("get_history")

# ✅ Store library metadata in PostgreSQL
def store_library_data(conn, cursor, library_data):
    print("📌 Full library_data before inserting:", library_data)

    if not library_data:
        print("⚠️ No library data found. Skipping library insert.")
        return

    insert_library = """
        INSERT INTO library (
            rating_key, title, year, duration, media_type, summary, rating, added_at, 
            season_number, episode_number, parent_rating_key, show_rating_key, show_title, episode_title, episode_summary,
            thumb_path, parent_thumb_path, grandparent_thumb_path, plex_guid
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, TO_TIMESTAMP(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (rating_key) DO UPDATE SET
            title = EXCLUDED.title,
            year = EXCLUDED.year,
            duration = EXCLUDED.duration,
            media_type = EXCLUDED.media_type,
            summary = EXCLUDED.summary,
            rating = EXCLUDED.rating,
            added_at = EXCLUDED.added_at,
            season_number = EXCLUDED.season_number,
            episode_number = EXCLUDED.episode_number,
            parent_rating_key = EXCLUDED.parent_rating_key,
            show_rating_key = EXCLUDED.show_rating_key,
            show_title = EXCLUDED.show_title,
            episode_title = EXCLUDED.episode_title,
            episode_summary = EXCLUDED.episode_summary,
            thumb_path = EXCLUDED.thumb_path,
            parent_thumb_path = EXCLUDED.parent_thumb_path,
            grandparent_thumb_path = EXCLUDED.grandparent_thumb_path,
            plex_guid = EXCLUDED.plex_guid;
    """

    successful_inserts = 0

    for item in library_data:
        # ✅ Ensure `rating_key` is assigned at the very beginning of the loop
        rating_key = item.get("rating_key")
        if not rating_key:
            print(f"⚠️ Skipped item missing rating_key: {item}")
            continue  # Prevents using `rating_key` before it's assigned

        # ✅ Extract values safely
        title = item.get("title")
        year = safe_int(item.get("year"))
        duration = safe_int(item.get("duration"))
        media_type = item.get("media_type")
        summary = item.get("summary")
        rating = item.get("rating")
        added_at = safe_int(item.get("added_at"))
        season_number = safe_int(item.get("season_number"))
        episode_number = safe_int(item.get("episode_number"))
        parent_rating_key = safe_int(item.get("parent_rating_key"))
        if media_type == 'episode':
            show_title = item.get("grandparent_title")
        elif media_type == 'season':
            show_title = item.get("parent_title") or item.get("grandparent_title")
        elif media_type in ('show', 'series'):
            show_title = item.get("title")
        else:
            show_title = None
        episode_title = item.get("title") if media_type == 'episode' else None
        episode_summary = summary if media_type == 'episode' else None
        show_rating_key = safe_int(item.get("show_rating_key"))
        thumb_path = item.get("thumb_path")
        parent_thumb_path = item.get("parent_thumb_path")
        grandparent_thumb_path = item.get("grandparent_thumb_path")
        plex_guid = item.get("plex_guid")

        # ✅ Print debug info AFTER values are assigned
        print(f"🔎 DEBUG: Checking extracted values for rating_key={rating_key}")
        print(f"   - season_number: {season_number}")
        print(f"   - episode_number: {episode_number}")

        # Extract lists for relationships
        genres = item.get("genres", [])
        actors = item.get("actors", [])
        directors = item.get("directors", [])

        # ✅ Now safe to print debug info (all variables exist)
        print("🚨 About to INSERT explicitly:", {
            "rating_key": rating_key,
            "title": title,
            "year": year,
            "duration": duration,
            "media_type": media_type,
            "summary": summary[:30] if summary else None,
            "rating": rating,
            "added_at": added_at,
            "season_number": season_number,
            "episode_number": episode_number,
            "parent_rating_key": parent_rating_key,
            "show_rating_key": show_rating_key,
            "show_title": show_title,
            "episode_title": episode_title,
            "episode_summary": episode_summary[:30] if episode_summary else None,
            "thumb_path": thumb_path,
            "parent_thumb_path": parent_thumb_path,
            "grandparent_thumb_path": grandparent_thumb_path,
            "plex_guid": plex_guid,
            "genres": genres,
            "actors": actors,
            "directors": directors
        })

        try:
            cursor.execute(insert_library, (
                rating_key, title, year, duration, media_type, summary, rating,
                added_at, season_number, episode_number, parent_rating_key,
                show_rating_key, show_title, episode_title, episode_summary,
                thumb_path, parent_thumb_path, grandparent_thumb_path, plex_guid
            ))

            # ✅ Store associated genres, actors, and directors (only if they exist)
            if genres:
                store_genres(conn, cursor, rating_key, genres)
            if actors:
                store_actors(conn, cursor, rating_key, actors)
            if directors:
                store_directors(conn, cursor, rating_key, directors)

            print(f"✅ Successfully inserted: {rating_key}")
            successful_inserts += 1
        except Exception as e:
            print(f"⚠️ EXCEPTION inserting rating_key={rating_key}: {e}")
            conn.rollback()
            
    print("🔎 Checking database commit…")
    conn.commit()
    print(f"✅ Stored {successful_inserts}/{len(library_data)} library items into database.")



def store_genres(conn, cursor, rating_key, genres):
    if not genres:
        return

    insert_genre = """
        INSERT INTO genres (name) 
        VALUES (%s) 
        ON CONFLICT (name) DO NOTHING;
    """
    insert_media_genre = """
        INSERT INTO media_genres (media_id, genre_id) 
        SELECT %s, id FROM genres WHERE name = %s
        ON CONFLICT DO NOTHING;
    """

    for genre in genres:
        try:
            cursor.execute(insert_genre, (genre,))  # Ensure genre exists
            cursor.execute(insert_media_genre, (rating_key, genre))  # Link to media
        except Exception as e:
            print(f"⚠️ ERROR inserting genre '{genre}' for rating_key={rating_key}: {e}")
            conn.rollback()

    conn.commit()



def store_actors(conn, cursor, rating_key, actors):
    if not actors:
        return

    insert_actor = """
        INSERT INTO actors (name) 
        VALUES (%s) 
        ON CONFLICT (name) DO NOTHING;
    """
    insert_media_actor = """
        INSERT INTO media_actors (media_id, actor_id) 
        SELECT %s, id FROM actors WHERE name = %s
        ON CONFLICT DO NOTHING;
    """

    for actor in actors:
        try:
            cursor.execute(insert_actor, (actor,))  # Ensure actor exists
            cursor.execute(insert_media_actor, (rating_key, actor))  # Link to media
        except Exception as e:
            print(f"⚠️ ERROR inserting actor '{actor}' for rating_key={rating_key}: {e}")
            conn.rollback()

    conn.commit()



def store_directors(conn, cursor, rating_key, directors):
    if not directors:
        return

    insert_director = """
        INSERT INTO directors (name) 
        VALUES (%s) 
        ON CONFLICT (name) DO NOTHING;
    """
    insert_media_director = """
        INSERT INTO media_directors (media_id, director_id) 
        SELECT %s, id FROM directors WHERE name = %s
        ON CONFLICT DO NOTHING;
    """

    for director in directors:
        try:
            cursor.execute(insert_director, (director,))  # Ensure director exists
            cursor.execute(insert_media_director, (rating_key, director))  # Link to media
        except Exception as e:
            print(f"⚠️ ERROR inserting director '{director}' for rating_key={rating_key}: {e}")
            conn.rollback()

    conn.commit()




# ✅ Store watch history in PostgreSQL
def store_watch_history(conn, cursor, watch_history):           
    insert_watch = """
        INSERT INTO watch_history (
            rating_key, watched_at, played_duration, percent_complete, watch_id, media_type, username,
            title, episode_title, season_number, episode_number, friendly_name, show_rating_key
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (watch_id) 
        DO UPDATE SET
                played_duration = EXCLUDED.played_duration, 
                percent_complete = EXCLUDED.percent_complete,
                watched_at = EXCLUDED.watched_at,
                show_rating_key = EXCLUDED.show_rating_key
"""
    for record in watch_history:
        watch_id = record.get("watch_id") or record.get("id")
        rating_key = record.get("rating_key")
        if watch_id is None or rating_key is None:
            print(f"⚠️ Skipping watch history insert due to missing watch_id or rating_key: {record}")
            continue
        show_rating_key = safe_int(record.get("grandparent_rating_key"))
        if show_rating_key is None and record.get("media_type") == "season":
            show_rating_key = safe_int(record.get("parent_rating_key"))
        if record.get("media_type") in ("show", "series"):
            show_rating_key = safe_int(record.get("rating_key"))
        try:
            cursor.execute(insert_watch, (
                rating_key, convert_timestamp(record.get("date")), record.get("play_duration"), 
                record.get("percent_complete"), watch_id, record.get("media_type"),
                record.get("user"), record.get("grandparent_title") if record.get("media_type") == "episode" else record.get("title"),
                record.get("title") if record.get("media_type") == "episode" else None,
                convert_to_int(record.get("parent_media_index")), convert_to_int(record.get("media_index")),
                record.get("friendly_name"),  # Added friendly_name here
                show_rating_key
            ))
        except Exception as e:
            print(f"❌ Error inserting watch history for watch_id={watch_id}: {e}")
            conn.rollback()

#def fetch_existing_library_data(cursor):
#    query = "SELECT rating_key, title FROM library WHERE media_type = 'show'"
#    cursor.execute(query)
#    
#    stored_shows = cursor.fetchall()  # Fetch list of tuples
#
#    # ✅ Convert list of tuples into a list of dictionaries
#    return [{"rating_key": row[0], "title": row[1]} for row in stored_shows]



#def get_incremental_library_data(cursor):
#    print("🔄 Checking for new or updated library items...")
#
#    # ✅ Query existing data from PostgreSQL
#    cursor.execute("SELECT rating_key, added_at FROM library")
#    existing_library = {row[0]: row[1] for row in cursor.fetchall()}  # Dictionary {rating_key: updated_at}
#
#    # ✅ Fetch latest library info from Tautulli
#    latest_library = get_library_media_info(section_id=1) + get_library_media_info(section_id=2)
#
#    # ✅ Identify new or updated items
#    to_process = []
#    for item in latest_library:
#        rating_key = item["rating_key"]
#        updated_at = int(item.get("updated_at", 0)) if item.get("updated_at") else 0  # Ensure int type
#
#        if rating_key not in existing_library:
#            print(f"🆕 New item: {item.get('title', rating_key)}")
#            to_process.append(item)
#        elif updated_at > (existing_library.get(rating_key) or 0):
#            print(f"🔄 Updated item: {item.get('title', rating_key)}")
#            to_process.append(item)
#
#    print(f"✅ Found {len(to_process)} new or updated media items.")
#    return to_process

def run_incremental_load():
    print("🔁 Running incremental update...")

    conn, cursor = connect_to_db()
    if not conn:
        print("❌ ERROR: Could not connect to database.")
        return
    
    # 0. Sync Plex/Tautulli users into the `users` table
    try:
        sync_users_from_tautulli(conn, cursor)
    except Exception as e:
        # Don't kill the whole incremental run if user sync fails,
        # but do log it so you can troubleshoot.
        print(f"⚠️ Failed to sync users from Tautulli: {e}")

    # 1. Fetch all current rating_keys from DB
    cursor.execute("SELECT rating_key FROM library")
    existing_keys = {str(row[0]) for row in cursor.fetchall()}
    queued_keys = set()
    new_items = []

    def append_new_item(item):
        rating_key = safe_int(item.get("rating_key")) if isinstance(item, dict) else None
        if rating_key is None:
            return
        rating_key_str = str(rating_key)
        if rating_key_str in existing_keys or rating_key_str in queued_keys:
            return
        new_items.append(item)
        queued_keys.add(rating_key_str)

    # 2. Get movies
    print("🎞️ Fetching movies...")
    movies = get_library_media_info(section_id=1)
    for movie in movies:
        append_new_item(movie)

    # 3. Get shows, seasons, and episodes via show → season → episode
    print("📺 Fetching shows, seasons, and episodes...")
    shows = get_library_media_info(section_id=2)
    for show in shows:
        append_new_item(show)
        show_key = show["rating_key"]
        seasons = get_children_metadata(show_key)
        for season in seasons:
            if season.get("media_type") != "season":
                continue
            append_new_item(season)
            season_key = season["rating_key"]
            episodes = get_children_metadata(season_key)
            for ep in episodes:
                if ep.get("media_type") == "episode":
                    append_new_item(ep)

    print(f"📌 New media items to insert: {len(new_items)}")

    # 4. Fetch detailed metadata for each new item
    enriched = []
    for item in new_items:
        metadata = get_metadata(item["rating_key"])
        if metadata:
            enriched.append(metadata)
        else:
            print(f"⚠️ Could not fetch metadata for rating_key={item['rating_key']}")

    if enriched:
        print(f"📥 Inserting {len(enriched)} new media entries...")
        store_library_data(conn, cursor, enriched)
    else:
        print("✅ No new content to add.")

    # 5. Repair missing parent header rows implied by already-ingested descendants.
    backfill_missing_header_records(conn, cursor)

    # 6. One-time backfill path for existing rows added before plex_guid existed.
    backfill_missing_plex_guids(conn, cursor)

    # 7. Sync new watch history
    sync_new_watch_history(conn, cursor)

    # 8. Optionally embed new stuff immediately after sync
    if os.getenv("ENABLE_EMBED_MEDIA", "1") == "1":
        generate_media_embeddings()

    if os.getenv("ENABLE_EMBED_WATCHES", "1") == "1":
        generate_watch_embeddings()

    conn.commit()
    conn.close()
    print("✅ Incremental update complete.")


def backfill_missing_header_records(conn, cursor):
    print("🧱 Checking for missing show and season header records...")
    cursor.execute(
        """
        WITH missing_seasons AS (
            SELECT DISTINCT e.parent_rating_key AS rating_key
            FROM library e
            LEFT JOIN library s ON s.rating_key = e.parent_rating_key
            WHERE e.media_type = 'episode'
              AND e.parent_rating_key IS NOT NULL
              AND s.rating_key IS NULL
        ),
        missing_shows_from_episodes AS (
            SELECT DISTINCT e.show_rating_key AS rating_key
            FROM library e
            LEFT JOIN library sh ON sh.rating_key = e.show_rating_key
            WHERE e.media_type = 'episode'
              AND e.show_rating_key IS NOT NULL
              AND sh.rating_key IS NULL
        ),
        missing_shows_from_seasons AS (
            SELECT DISTINCT s.parent_rating_key AS rating_key
            FROM library s
            LEFT JOIN library sh ON sh.rating_key = s.parent_rating_key
            WHERE s.media_type = 'season'
              AND s.parent_rating_key IS NOT NULL
              AND sh.rating_key IS NULL
        )
        SELECT DISTINCT rating_key
        FROM (
            SELECT rating_key FROM missing_seasons
            UNION ALL
            SELECT rating_key FROM missing_shows_from_episodes
            UNION ALL
            SELECT rating_key FROM missing_shows_from_seasons
        ) missing_headers
        WHERE rating_key IS NOT NULL
        ORDER BY rating_key
        """
    )
    missing_header_keys = [row[0] for row in cursor.fetchall()]

    if not missing_header_keys:
        print("✅ No missing show or season header records found.")
        return

    print(f"🧱 Backfilling {len(missing_header_keys)} missing show/season header records...")
    recovered_items = []
    for rating_key in missing_header_keys:
        metadata = get_metadata(rating_key)
        if metadata:
            recovered_items.append(metadata)
        else:
            print(f"⚠️ Could not backfill header metadata for rating_key={rating_key}")

    if not recovered_items:
        print("⚠️ Missing header records were detected, but no metadata could be recovered.")
        return

    store_library_data(conn, cursor, recovered_items)
    print(f"✅ Backfilled {len(recovered_items)} missing header records.")


def backfill_missing_plex_guids(conn, cursor):
    print("🪪 Checking for library rows missing plex_guid...")
    cursor.execute(
        """
        SELECT rating_key
        FROM library
        WHERE plex_guid IS NULL
        ORDER BY rating_key
        """
    )
    missing_guid_keys = [row[0] for row in cursor.fetchall()]

    if not missing_guid_keys:
        print("✅ No existing library rows need plex_guid backfill.")
        return

    print(f"🪪 Backfilling plex_guid for {len(missing_guid_keys)} existing library rows...")
    recovered_items = []
    for rating_key in missing_guid_keys:
        metadata = get_metadata(rating_key)
        if metadata:
            recovered_items.append(metadata)
        else:
            print(f"⚠️ Could not backfill metadata for rating_key={rating_key}")

    if not recovered_items:
        print("⚠️ plex_guid backfill found rows to repair, but no metadata could be recovered.")
        return

    store_library_data(conn, cursor, recovered_items)
    print(f"✅ Backfilled plex_guid metadata for {len(recovered_items)} library rows.")


def recover_missing_media(dry_run=False):
    print("🔍 Starting comprehensive media recovery process...")
    conn, cursor = connect_to_db()
    if not conn:
        print("❌ ERROR: Could not connect to database.")
        return

    all_rating_keys = set()

    # 1. Get all movie rating_keys
    print("🎞️ Collecting movies...")
    movies = get_library_media_info(section_id=1)
    all_rating_keys.update(str(item["rating_key"]) for item in movies)

    # 2. Get all episode rating_keys from shows
    print("📺 Collecting episodes from all shows...")
    shows = get_library_media_info(section_id=2)
    for show in shows:
        show_key = show["rating_key"]
        seasons = get_children_metadata(show_key)
        for season in seasons:
            if season.get("media_type") != "season":
                continue
            season_key = season["rating_key"]
            episodes = get_children_metadata(season_key)
            for ep in episodes:
                if ep.get("media_type") == "episode":
                    all_rating_keys.add(str(ep["rating_key"]))

    print(f"📦 Total media rating_keys found in Plex: {len(all_rating_keys)}")

    # 3. Get existing rating_keys from DB
    cursor.execute("SELECT rating_key FROM library")
    existing_keys = {str(row[0]) for row in cursor.fetchall()}

    # 4. Diff
    missing_keys = all_rating_keys - existing_keys
    print(f"🧩 Missing from DB: {len(missing_keys)}")

    # 5. Fetch metadata and recover
    recovered_items = []
    for rk in missing_keys:
        print(f"🔍 Attempting fetch for rating_key={rk}")
        metadata = get_metadata(rk)
        if metadata:
            print(f"[RECOVER] rating_key={metadata['rating_key']}, type={metadata.get('media_type')}, title={metadata.get('title')}")
            recovered_items.append(metadata)
        else:
            print(f"⚠️ Could not fetch metadata for rating_key={rk}")

    # 6. Insert or preview
    if recovered_items:
        if dry_run:
            print(f"\n📋 DRY RUN: Would recover {len(recovered_items)} items:")
            for item in recovered_items:
                print(f" - {item['media_type']} | {item['title']} (rating_key={item['rating_key']})")
        else:
            print(f"\n📥 Inserting {len(recovered_items)} recovered items into the database...")
            store_library_data(conn, cursor, recovered_items)
    else:
        print("✅ No recoverable items found.")

    conn.close()
    print("🔒 Database connection closed after recovery.")

#def sync_new_library_items(conn, cursor, dry_run=False):
#    print("🔄 Starting library sync for new media...")
#
#    all_rating_keys = set()
#
#    # 1. Fetch all movie rating_keys
#    print("🎞️ Fetching movies...")
#    movies = get_library_media_info(section_id=1)
#    all_rating_keys.update(str(item["rating_key"]) for item in movies)
#
#    # 2. Fetch all episode rating_keys
#    print("📺 Fetching episodes from shows...")
#    shows = get_library_media_info(section_id=2)
#    for show in shows:
#        show_key = show["rating_key"]
#        seasons = get_children_metadata(show_key)
#        for season in seasons:
#            if season.get("media_type") != "season":
#                continue
#            season_key = season["rating_key"]
#            episodes = get_children_metadata(season_key)
#            for ep in episodes:
#                if ep.get("media_type") == "episode":
#                    all_rating_keys.add(str(ep["rating_key"]))
#
#    print(f"📦 Total rating_keys from Plex: {len(all_rating_keys)}")
#
#    # 3. Get existing rating_keys from DB
#    cursor.execute("SELECT rating_key FROM library")
#    existing_keys = {str(row[0]) for row in cursor.fetchall()}
#
#    missing_keys = all_rating_keys - existing_keys
#    print(f"🧩 New media not in DB: {len(missing_keys)}")
#
#    # 4. Fetch and insert metadata for missing items
#    recovered_items = []
#    for rk in missing_keys:
#        print(f"🔍 Attempting fetch for rating_key={rk}")
#        metadata = get_metadata(rk)
#        if metadata:
#            recovered_items.append(metadata)
#        else:
#            print(f"⚠️ Could not fetch metadata for rating_key={rk}")
#
#    if recovered_items:
#        if dry_run:
#            print(f"\n📋 DRY RUN: Would insert {len(recovered_items)} items:")
#            for item in recovered_items:
#                print(f" - {item['media_type']} | {item['title']} (rating_key={item['rating_key']})")
#        else:
#            print(f"📥 Inserting {len(recovered_items)} items into library table...")
#            store_library_data(conn, cursor, recovered_items)
#    else:
#        print("✅ No new media to insert.")

from datetime import datetime, timezone
import json

def fetch_all_watch_history(after_ts):
    print(f"🕵️ Fetching all Tautulli history after {after_ts} (paginated)")
    all_rows = []
    start = 0
    page_size = 1000

    while True:
        response = fetch_tautulli_data("get_history", {
            "after": after_ts,
            "order_dir": "asc",
            "length": page_size,
            "start": start
        })
        rows = response.get("data", [])
        print(f"📦 Page {start // page_size + 1}: Retrieved {len(rows)} rows")

        if not rows:
            break

        all_rows.extend(rows)
        if len(rows) < page_size:
            break

        start += page_size

    return all_rows

def sync_new_watch_history(conn, cursor):
    print("🎬 Syncing new watch history...")

    cursor.execute("SELECT MAX(watched_at) FROM watch_history")
    last_seen = cursor.fetchone()[0]

    # Convert to UNIX seconds (Tautulli expects this)
    if last_seen is None:
        after_ts = 0
    else:
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        after_ts = int(last_seen.timestamp()) - 60

    rows = fetch_all_watch_history(after_ts)
    print(f"🧪 Tautulli returned {len(rows)} raw rows total")

    if not rows:
        print("✅ No new watch history found.")
        return

    valid_rows = []
    skipped_rows = []

    for r in rows:
        if r.get("id") and r.get("rating_key"):
            r["watch_id"] = r["id"]  # normalize for DB
            valid_rows.append(r)
        else:
            skipped_rows.append(r)

    print(f"📥 Found {len(valid_rows)} valid watch history rows. Inserting...")

    if skipped_rows:
        print(f"⚠️ Skipped {len(skipped_rows)} rows due to missing id or rating_key")
        print("⚠️ Example skipped row:")
        print(json.dumps(skipped_rows[0], indent=2))

    if valid_rows:
        latest_insert = max([r["date"] for r in valid_rows])
        print(f"🆕 Most recent fetched watched_at: {datetime.utcfromtimestamp(latest_insert)} UTC")

    store_watch_history(conn, cursor, valid_rows)

def generate_media_embeddings(batch_size: int = EMBED_BATCH_SIZE):
    """
    Generate embeddings for media items in `library` that are missing in `media_embeddings`.

    Assumes:
      - media_embeddings.embedding is pgvector `vector(768)`
      - Ollama (embeddinggemma) is reachable via embed_texts()
    """
    print("🧠 Generating media embeddings...")

    conn, cur = connect_to_db()
    if not conn:
        print("❌ ERROR: Could not connect to database.")
        return

    print("✅ Connected to PostgreSQL database")

    # Find library entries without embeddings
    cur.execute(
        """
        SELECT l.rating_key, l.title, COALESCE(l.summary, '')
        FROM library l
        LEFT JOIN media_embeddings me ON me.rating_key = l.rating_key
        WHERE me.rating_key IS NULL
        ORDER BY l.rating_key
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("✅ No media rows missing embeddings.")
        conn.close()
        return
    
    print(f"📦 Media items to embed: {len(rows)}")
    # ✅ Optional: list what will be embedded (like the old behavior)
    if os.getenv("LOG_EMBED_TITLES", "1").lower() in ("1", "true", "yes", "on"):
        for rk, title, _summary in rows:
            print(f"   🎬 {title} (rating_key={rk})")

    texts = [_media_text_for_embedding(r) for r in rows]
    
    raw_bs = batch_size
    try:
        norm_bs = int(str(raw_bs).strip().split()[0])
    except Exception:
        norm_bs = 128  # safe fallback

    vectors = embed_texts(texts, batch_size=batch_size)
    assert len(vectors) == len(rows)

    batch_size = norm_bs  # from here on, batch_size is a clean int

    # Insert in batches to keep transactions reasonable
    for i in range(0, len(rows), batch_size):
        part_rows = rows[i:i + batch_size]
        part_vecs = vectors[i:i + batch_size]
        with conn:
            with conn.cursor() as cur2:
                for (rk, _t, _s), vec in zip(part_rows, part_vecs):
                    cur2.execute(
                        """
                        INSERT INTO media_embeddings (rating_key, embedding)
                        VALUES (%s, %s)
                        ON CONFLICT (rating_key) DO NOTHING
                        """,
                        (rk, Vector(vec)),
                    )

    conn.close()
    print("✅ Media embeddings complete.")

def _watch_text_for_embedding(
    media_type,
    title,
    show_title,
    episode_title,
    year,
    rating,
    summary,
    username,
    percent,
    played_duration,
    season_number,
    episode_number,
    genres,
    actors,
    directors,
):
    def _clean(value):
        if value is None:
            return ""
        return str(value).strip()

    media_type = _clean(media_type).upper()
    title = _clean(title)
    show_title = _clean(show_title)
    episode_title = _clean(episode_title)
    year = _clean(year)
    rating = _clean(rating)
    summary = _clean(summary)

    if show_title or media_type == "EPISODE":
        base_title = show_title or title
        if episode_title:
            base_title = f"{base_title}: {episode_title}"
    else:
        base_title = title

    season_str = f"S{season_number}" if season_number is not None else ""
    episode_str = f"E{episode_number}" if episode_number is not None else ""
    se_str = f"{season_str}{episode_str}".strip()

    watch_str = f"watched {percent}%" if percent is not None else "watched"
    if played_duration is not None:
        minutes_played = played_duration // 60
        watch_str += f" for {minutes_played} minutes"

    label = f"[{media_type}]" if media_type else "[WATCH]"
    title_parts = [label, base_title]
    if se_str:
        title_parts.append(se_str)
    if year:
        title_parts.append(f"({year})")
    title_line = " ".join(p for p in title_parts if p)

    parts = [
        f"{title_line} by {username}, {watch_str}",
        f"Rating: {rating}" if rating else "",
        f"Genres: {genres}" if genres else "",
        f"Actors: {actors}" if actors else "",
        f"Directors: {directors}" if directors else "",
        f"Summary: {summary[:400]}" if summary else "",
    ]
    return ". ".join(p for p in parts if p).strip()

def generate_watch_embeddings(batch_size: int = 16):
    """
    Generate embeddings for watch_history rows that are missing watch_embeddings.
    Uses library + genre/actor/director context to build the text.
    Assumes watch_embeddings.embedding is vectors.vector(768).
    """
    print("🧠 Generating watch embeddings via Ollama (EmbeddingGemma)...")

    conn, cur = connect_to_db()
    if not conn:
        print("❌ ERROR: Could not connect to database.")
        return

    # Pull only watch rows that don't yet have an embedding
    cur.execute(
        """
        SELECT
            wh.watch_id,
            COALESCE(l.media_type, wh.media_type) AS media_type,
            COALESCE(l.title, wh.title) AS title,
            l.show_title,
            COALESCE(l.episode_title, wh.episode_title) AS episode_title,
            l.year,
            l.rating,
            COALESCE(l.summary, l.episode_summary) AS summary,
            wh.username,
            wh.percent_complete,
            wh.played_duration,
            wh.season_number,
            wh.episode_number,
            g.genre_tags,
            a.actor_tags,
            d.director_tags
        FROM watch_history wh
        JOIN library l ON wh.rating_key = l.rating_key
        LEFT JOIN (
            SELECT mg.media_id, STRING_AGG(g.name, ', ') AS genre_tags
            FROM media_genres mg
            JOIN genres g ON mg.genre_id = g.id
            GROUP BY mg.media_id
        ) g ON g.media_id = l.rating_key
        LEFT JOIN (
            SELECT ma.media_id, STRING_AGG(a.name, ', ') AS actor_tags
            FROM media_actors ma
            JOIN actors a ON ma.actor_id = a.id
            GROUP BY ma.media_id
        ) a ON a.media_id = l.rating_key
        LEFT JOIN (
            SELECT md.media_id, STRING_AGG(d.name, ', ') AS director_tags
            FROM media_directors md
            JOIN directors d ON md.director_id = d.id
            GROUP BY md.media_id
        ) d ON d.media_id = l.rating_key
        LEFT JOIN watch_embeddings we ON wh.watch_id::text = we.watch_id::text
        WHERE we.watch_id IS NULL
        """
    )
    rows = cur.fetchall()

    if not rows:
        print("✅ No watch rows missing embeddings.")
        conn.close()
        return

    print(f"🧠 Generating embeddings for {len(rows)} watch events...")

    texts = [
        _watch_text_for_embedding(
            media_type,
            title,
            show_title,
            episode_title,
            year,
            rating,
            summary,
            username,
            percent,
            played_duration,
            season_number,
            episode_number,
            genres,
            actors,
            directors,
        )
        for (
            watch_id, media_type, title, show_title, episode_title, year, rating, summary,
            username, percent, played_duration, season_number, episode_number,
            genres, actors, directors
        ) in rows
    ]

    vectors = embed_texts(texts, batch_size=batch_size)
    assert len(vectors) == len(rows)

    for i in range(0, len(rows), batch_size):
        part_rows = rows[i:i + batch_size]
        part_vecs = vectors[i:i + batch_size]
        with conn:
            with conn.cursor() as cur2:
                for (
                    (watch_id, _mt, _title, _show, _ep, _year, _rating, _summary,
                     _username, _percent, _pd, _sn, _en, _g, _a, _d),
                    vec,
                ) in zip(part_rows, part_vecs):
                    cur2.execute(
                        """
                        INSERT INTO watch_embeddings (watch_id, embedding)
                        VALUES (%s, %s)
                        ON CONFLICT (watch_id) DO NOTHING
                        """,
                        (watch_id, Vector(vec)),
                    )

    conn.close()
    print("✅ Watch embeddings complete.")

# ✅ Main execution
def main():
    print("🚀 Script started...")
    """
    Main function to fetch and store library data and watch history from Tautulli API to PostgreSQL.
    """
    print("🚀 Script started...")
    ensure_app_schema(DB_URL)
    conn, cursor = connect_to_db()
    if not conn:
        return

    try:
        # First, sync Plex/Tautulli users into our `users` table
        try:
            sync_users_from_tautulli(conn, cursor)
        except Exception as e:
            print(f"⚠️ Failed to sync users from Tautulli in full mode: {e}")

        # Fetch and store library data
        library_data = get_library_data(movies_limit=None, tv_limit=None)
        print(f"🚨 DEBUG: Retrieved library data count: {len(library_data)}")
        if len(library_data) == 0:
            print("🚨 DEBUG: Library data is EMPTY after get_library_data()!")
        store_library_data(conn, cursor, library_data)

        # Fetch and store watch history
        watch_history = get_watch_history()
        store_watch_history(conn, cursor, watch_history)

        # 🔥 Crucial: commit database changes after cursor block
        conn.commit()
        print("✅ Data committed successfully.")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()
            print("🔒 Database connection closed.")

# To run media recovery from CLI
# recover_missing_media()
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plex/Tautulli Media Metadata Importer")
    parser.add_argument(
        "--mode",
        choices=["full", "incremental", "recover", "embeddings", "watch_embeddings"],
        default="full",
        help="Select run mode: full (default), incremental, recover missing items, generate embeddings, or generate watch history embeddings",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="If set, missing items will only be printed and NOT inserted into the database",
    )
    args = parser.parse_args()

    print(f"🚀 Starting script in '{args.mode}' mode...")

    if args.mode == "full":
        main()
    elif args.mode == "incremental":
        run_incremental_load()
    elif args.mode == "recover":
        recover_missing_media(dry_run=args.dry_run)
    elif args.mode == "embeddings":
        # Media embeddings via Ollama + VectorChord
        generate_media_embeddings()
    elif args.mode == "watch_embeddings":
        # Watch embeddings via Ollama + VectorChord
        generate_watch_embeddings()
