from dotenv import load_dotenv
import os
import time
import requests
import json
import argparse
import sys
import pandas as pd
from datetime import datetime
from pgvector.psycopg2 import register_vector
from pgvector import Vector
# Ollama embedding client (NAS-hosted EmbeddingGemma)
from ollama_embeddings import embed_texts
from api.db.connection import connect_db
from api.services.app_settings import get_setting_value
from api.services.tautulli_api import (
    TautulliApiError,
    delete_tautulli_cache,
    tautulli_request,
)
from api.services.user_sync_service import (
    fetch_tautulli_users as fetch_tautulli_users_for_sync,
    sync_users_from_tautulli as sync_users_from_tautulli_for_contacts,
)

# ✅ Load environment variables
load_dotenv()

def safe_int(value):
    """Convert value to an integer safely, returning None if conversion fails."""
    if value in [None, "", " ", "None"]:  # Handle empty strings, spaces, and None
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def get_embed_batch_size() -> int:
    return get_setting_value("embeddings.batch_size", default=128)


def get_tautulli_api_url() -> str | None:
    return get_setting_value("tautulli.api_url")


def get_tautulli_api_key() -> str | None:
    return get_setting_value("tautulli.api_key")


def get_tautulli_base_url() -> str | None:
    return get_setting_value("tautulli.base_url")

def clear_tautulli_cache():
    """
    Clear Tautulli's metadata cache so new/changed items show up.
    Uses the same TAUTULLI_URL and TAUTULLI_API_KEY as the rest of the script.
    """
    try:
        delete_tautulli_cache(timeout=30)
        print("✅ Cleared Tautulli cache via delete_cache")
    except Exception as e:
        print(f"❌ ERROR clearing Tautulli cache: {e}")

# ✅ Fetch data from Tautulli API
def fetch_tautulli_data(endpoint, params=None):
    try:
        return tautulli_request(
            endpoint,
            params=dict(params or {}),
            timeout=30,
            require_data=True,
        )
    except TautulliApiError:
        print("Tautulli API request failed; no source payload logged")
        return {}
    
# 👥 ---------- User sync helpers (Tautulli → users table) ----------

def fetch_tautulli_users():
    users = fetch_tautulli_users_for_sync()
    print(f"👥 Retrieved {len(users)} users from Tautulli.")
    return users


def sync_users_from_tautulli(conn, cursor):
    result = sync_users_from_tautulli_for_contacts(conn=conn, cursor=cursor)
    print(
        "✅ User sync complete. "
        f"Inserted {result['inserted']} new user(s), updated {result['updated']} existing user(s)."
    )


# ✅ Connect to PostgreSQL Database
def connect_to_db():
    conn = None
    try:
        conn = connect_db()
        # ✅ Tell psycopg2 how to handle pgvector's `vector` type
        register_vector(conn)

        cursor = conn.cursor()
        print("✅ Connected to PostgreSQL database")
        return conn, cursor
    except Exception as e:
        if conn is not None:
            conn.close()
        print(f"Database connection unavailable: {type(e).__name__}")
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

def _metadata_pages(endpoint, params, collection, page_size):
    from api.services.metadata_collection import pages
    return pages(fetch_tautulli_data, endpoint, params, collection, page_size)


def get_library_media_info(section_id, limit=None):
    rows = _metadata_pages("get_library_media_info", {"section_id": section_id}, "data", 100)
    return rows[:limit] if limit is not None else rows

def get_children_metadata(parent_rating_key):
    from api.services.metadata_collection import children
    return children(fetch_tautulli_data, parent_rating_key)



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
_METADATA_DRY_RUN = False
_METADATA_CACHE_LIMIT = 128

def get_metadata(rating_key, *, parent_lookup=None, expected_type=None):
    from api.services.metadata_ingestion import normalize_metadata, integer, MetadataError
    key = integer(rating_key, required=True)
    if key in _METADATA_CACHE:
        if expected_type and _METADATA_CACHE[key]['media_type'] != expected_type:
            raise MetadataError('discovered_kind_mismatch')
        return _METADATA_CACHE[key]
    raw = fetch_tautulli_data("get_metadata", {"rating_key": key})
    if not raw:
        if not _METADATA_DRY_RUN:
            clear_tautulli_cache()
        raw = fetch_tautulli_data("get_metadata", {"rating_key": key})
    if not isinstance(raw, dict) or not raw:
        raise MetadataError("metadata_fetch_failed")
    if integer(raw.get('rating_key'), required=True) != key:
        raise MetadataError('requested_key_mismatch')
    if expected_type and raw.get('media_type') != expected_type:
        raise MetadataError('discovered_kind_mismatch')
    # Validate supplied child fields before a deferred parent can short-circuit
    # retrieval. Series inheritance is applied after resolving the parent.
    result = normalize_metadata(key, raw)
    show = None
    show_key = raw.get("grandparent_rating_key") if raw.get("media_type") == "episode" else raw.get("parent_rating_key") if raw.get("media_type") == "season" else None
    if show_key not in (None, ''):
        show_key = integer(show_key, required=True)
        if show_key == key:
            raise MetadataError("cyclic_parent")
        show = parent_lookup(show_key) if parent_lookup else None
        if show is None:
            show = get_metadata(show_key, parent_lookup=parent_lookup, expected_type='show')
    if show is not None: result = normalize_metadata(key, raw, show=show)
    _METADATA_CACHE[key] = result
    if len(_METADATA_CACHE) > _METADATA_CACHE_LIMIT:
        _METADATA_CACHE.pop(next(iter(_METADATA_CACHE)))
    return result

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
    result = fetch_watch_history_pages()
    if not result["ok"]:
        raise RuntimeError("Incomplete Tautulli history response")
    return result["rows"]

# ✅ Store library metadata in PostgreSQL
def store_library_data(conn, cursor, library_data, *, dry_run=False, operation_id=None):
    from api.services.metadata_collection import store_candidates
    return store_candidates(conn, library_data, dry_run=dry_run, operation_id=operation_id)



def store_genres(conn, cursor, rating_key, genres):
    # Compatibility helper: transaction ownership belongs to acceptance/correction.
    from api.services.metadata_ingestion import _write_relationships
    _write_relationships(cursor, rating_key, "genres", genres)



def store_actors(conn, cursor, rating_key, actors):
    from api.services.metadata_ingestion import _write_relationships
    _write_relationships(cursor, rating_key, "actors", actors)



def store_directors(conn, cursor, rating_key, directors):
    from api.services.metadata_ingestion import _write_relationships
    _write_relationships(cursor, rating_key, "directors", directors)




# ✅ Store watch history in PostgreSQL
def store_watch_history(conn, cursor, watch_history, *, source_grouping, raise_on_error=True):
    """Only explicitly grouped responses may reach the model-facing writer."""
    from api.services.watch_history_sync import persist_grouped_history
    return persist_grouped_history(conn, cursor, watch_history,
                                   source_grouping=source_grouping, raise_on_error=raise_on_error)

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

def run_incremental_load(*, embed=True, dry_run=False):
    if embed:
        from api.predictive.retired import assert_legacy_allowed
        assert_legacy_allowed()
    from api.services.metadata_collection import run
    return run(sys.modules[__name__], mode="incremental", dry_run=dry_run)


def backfill_missing_header_records(conn, cursor, *, dry_run=False):
    from api.services.metadata_collection import missing_headers, ingest_keys
    return ingest_keys(sys.modules[__name__], conn, missing_headers(cursor), dry_run=dry_run)


def backfill_missing_plex_guids(conn, cursor, *, dry_run=False):
    from api.services.metadata_collection import repair_guids
    return repair_guids(sys.modules[__name__], conn, dry_run=dry_run)


def backfill_actor_cast_order(*, rating_keys=None, operator="operator", reason="cast_order_preview", apply=False, dry_run=True, plans=None):
    from scripts.correct_metadata import order_repairs
    return order_repairs(sys.modules[__name__], rating_keys=rating_keys, operator=operator,
                         reason=reason, apply=apply and not dry_run, plans=plans)


def recover_missing_media(dry_run=False):
    from api.services.metadata_collection import run
    return run(sys.modules[__name__], mode="recover", dry_run=dry_run)

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

WATCH_HISTORY_PAGE_SIZE = 1000


def fetch_watch_history_pages(after_ts=None, page_size=WATCH_HISTORY_PAGE_SIZE):
    from api.services.watch_history_sync import iter_history_pages
    all_rows = []
    started = time.monotonic()
    pages = 0

    def result(ok):
        return {
            "ok": ok, "rows": all_rows,
            "error": None if ok else "Incomplete or invalid history pagination",
            "metrics": {
                "pages": pages, "rows": len(all_rows),
                "fetch_seconds": round(time.monotonic() - started, 4),
            },
        }

    def fetch_page(endpoint, params):
        nonlocal pages
        pages += 1
        return fetch_tautulli_data(endpoint, params)

    try:
        for rows in iter_history_pages(fetch_page, grouping=1, after=after_ts, page_size=page_size):
            all_rows.extend(rows)
        return result(True)
    except Exception:
        return result(False)


def fetch_all_watch_history(after_ts):
    result = fetch_watch_history_pages(after_ts=after_ts)
    if not result["ok"]:
        print(f"⚠️ Watch history fetch failed: {result['error']}")
        return []
    return result["rows"]


def normalize_watch_history_rows(rows):
    valid_rows = []
    upstream_watch_ids = set()
    malformed_rows = []

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            malformed_rows.append({"index": index, "reason": "row is not an object", "row": row})
            continue

        raw_watch_id = row.get("id")
        if raw_watch_id is None:
            raw_watch_id = row.get("watch_id")
        watch_id = safe_int(raw_watch_id)
        rating_key = safe_int(row.get("rating_key"))

        if watch_id is None or rating_key is None:
            malformed_rows.append({
                "index": index,
                "reason": "missing id/watch_id or rating_key",
                "row": row,
            })
            continue

        normalized = dict(row)
        normalized["watch_id"] = watch_id
        normalized["rating_key"] = rating_key
        valid_rows.append(normalized)
        upstream_watch_ids.add(watch_id)

    return valid_rows, upstream_watch_ids, malformed_rows


def purge_deleted_watch_history(cursor, upstream_watch_ids):
    upstream_ids = sorted(str(watch_id) for watch_id in upstream_watch_ids)
    deleted_embedding_rows = 0
    deleted_watch_rows = 0

    if upstream_ids:
        cursor.execute(
            """
            DELETE FROM watch_embeddings we
            USING watch_history wh
            WHERE we.watch_id::text = wh.watch_id::text
              AND NOT (wh.watch_id::text = ANY(%s))
            """,
            (upstream_ids,),
        )
        deleted_embedding_rows = cursor.rowcount or 0

        cursor.execute(
            """
            DELETE FROM watch_history
            WHERE NOT (watch_id::text = ANY(%s))
            """,
            (upstream_ids,),
        )
        deleted_watch_rows = cursor.rowcount or 0

    cursor.execute(
        """
        DELETE FROM watch_embeddings we
        WHERE NOT EXISTS (
            SELECT 1
            FROM watch_history wh
            WHERE wh.watch_id::text = we.watch_id::text
        )
        """
    )
    deleted_orphan_embeddings = cursor.rowcount or 0

    return {
        "deleted_watch_rows": deleted_watch_rows,
        "deleted_embedding_rows": deleted_embedding_rows,
        "deleted_orphan_embeddings": deleted_orphan_embeddings,
    }


def sync_new_watch_history(conn, cursor):
    """Reconcile recent events without treating upstream absence as a deletion."""
    from datetime import timedelta
    started = time.monotonic()
    cursor.execute("SELECT MAX(watched_at) FROM watch_history")
    latest = cursor.fetchone()[0]
    watermark_seconds = time.monotonic() - started
    days = max(1, int(os.getenv("WATCH_HISTORY_RECONCILIATION_DAYS", "30")))
    since = latest - timedelta(days=days) if latest else None
    # Tautulli accepts calendar dates in its own timezone, not Unix timestamps.
    after = (since - timedelta(days=1)).strftime("%Y-%m-%d") if since else None
    result = fetch_watch_history_pages(after_ts=after)
    metrics = {
        **result.get("metrics", {}), "rows": len(result["rows"]),
        "window_days": days, "watermark_seconds": round(watermark_seconds, 4),
    }

    def report(status, stats=None):
        print("Watch history sync metrics: " + json.dumps({
            **metrics, **(stats or {}), "status": status,
            "total_seconds": round(time.monotonic() - started, 4),
        }, sort_keys=True))

    if not result["ok"]:
        report("fetch_failed")
        print("Watch history synchronization failed: incomplete upstream history")
        return False
    persistence_started = time.monotonic()
    try:
        stats = store_watch_history(conn, cursor, result["rows"], source_grouping=1, raise_on_error=True)
        conn.commit()
    except Exception:
        conn.rollback()
        metrics["persistence_seconds"] = round(time.monotonic() - persistence_started, 4)
        report("rolled_back")
        print("Watch history synchronization failed; transaction rolled back")
        return False
    metrics["persistence_seconds"] = round(time.monotonic() - persistence_started, 4)
    report("committed", stats)
    return True


def run_watch_sessions(*, dry_run=False, since=None, until=None, page_size=1000, incremental=False):
    """Independent raw job. File/connection failures never print DSNs or passwords."""
    import psycopg2
    from api.services.private_config import PrivateConfigError, load_session_credentials
    from api.services.watch_session_sync import ingest_sessions
    conn = None
    try:
        load_session_credentials()
        conn = psycopg2.connect(os.environ["WATCH_SESSIONS_DATABASE_URL"], connect_timeout=10)
        return ingest_sessions(conn, dry_run=dry_run, since=since, until=until,
                               page_size=page_size, incremental=incremental)
    except PrivateConfigError:
        category = "private_credentials_invalid"
        print("Session configuration failed: verify the owner-only credential file and supported keys")
    except psycopg2.OperationalError as exc:
        category = "database_authentication_failed" if str(getattr(exc,"pgcode","") or "").startswith("28") else "database_connection_failed"
        print("Session database connection failed: verify credential, database, host reachability and pg_hba; no connection details logged")
    except Exception:
        category = "session_configuration_or_runtime_failed"
        print("Session operation failed: inspect configuration and sanitized ingestion diagnostics")
    finally:
        if conn is not None:
            conn.close()
    return {"failed": 0, "errors": 1, "busy": False, "error_category": category}


def generate_media_embeddings(batch_size: int | None = None):
    """
    Generate embeddings for media items in `library` that are missing in `media_embeddings`.

    Assumes:
      - media_embeddings.embedding is pgvector `vector(768)`
      - Ollama (embeddinggemma) is reachable via embed_texts()
    """
    from api.predictive.retired import assert_legacy_allowed
    assert_legacy_allowed()
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
    if get_setting_value("embeddings.log_titles", default=True):
        for rk, title, _summary in rows:
            print(f"   🎬 {title} (rating_key={rk})")

    texts = [_media_text_for_embedding(r) for r in rows]
    
    raw_bs = batch_size if batch_size is not None else get_embed_batch_size()
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

def generate_watch_embeddings(batch_size: int | None = None):
    """
    Generate embeddings for watch_history rows that are missing watch_embeddings.
    Uses library + genre/actor/director context to build the text.
    Assumes watch_embeddings.embedding is vectors.vector(768).
    """
    from api.predictive.retired import assert_legacy_allowed
    assert_legacy_allowed()
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
            SELECT ma.media_id, STRING_AGG(a.name, ', ' ORDER BY ma.cast_order NULLS LAST, a.name) AS actor_tags
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

    if batch_size is None:
        batch_size = get_embed_batch_size()

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
def main(*, dry_run=False):
    from api.services.metadata_collection import run
    return run(sys.modules[__name__], mode="full", dry_run=dry_run)

def cli(argv=None):
    parser = argparse.ArgumentParser(description="Plex/Tautulli importer: explicit acceptance, never implicit reimport")
    parser.add_argument("--mode", required=True, choices=["full", "incremental", "recover", "embeddings", "watch_embeddings", "backfill_cast_order", "watch-history-backfill", "watch-sessions-backfill", "watch-sessions-sync"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--since"); parser.add_argument("--until")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--no-embeddings", action="store_true")
    parser.add_argument("--rating-key", type=int, action="append")
    parser.add_argument("--operator"); parser.add_argument("--reason")
    parser.add_argument("--apply", action="store_true", help="Apply explicitly scoped cast-order repairs")
    parser.add_argument("--plan", help="Reviewed cast-order preview JSON; required for --apply")
    args = parser.parse_args(argv)
    try:
        if args.mode in ("watch-history-backfill", "watch-sessions-backfill", "watch-sessions-sync"):
            stats = run_watch_sessions(dry_run=args.dry_run, since=args.since, until=args.until,
                                      page_size=args.page_size, incremental=args.mode == "watch-sessions-sync")
            return 75 if stats.get("busy") else (1 if stats["failed"] or stats["errors"] else 0)
        if args.mode == "full": main(dry_run=args.dry_run)
        elif args.mode == "incremental": run_incremental_load(embed=not args.no_embeddings, dry_run=args.dry_run)
        elif args.mode == "recover": recover_missing_media(dry_run=args.dry_run)
        elif args.mode == "backfill_cast_order":
            if not args.rating_key or not args.operator or not args.reason:
                parser.error("cast-order preparation requires --rating-key, --operator and --reason")
            if args.apply and not args.plan:
                parser.error("--apply requires the reviewed --plan; use scripts/correct_metadata.py for explicit corrections")
            plans=None
            if args.plan:
                with open(args.plan) as handle: plans=json.load(handle)
            if isinstance(plans,dict): plans=[plans]
            plans = backfill_actor_cast_order(rating_keys=args.rating_key, operator=args.operator,
                       reason=args.reason, apply=args.apply, dry_run=args.dry_run or not args.apply, plans=plans)
            print(json.dumps(plans, indent=2, default=str))
        else:
            if args.dry_run:
                parser.error("retired numeric modes do not support a writable preview")
            if args.mode == "embeddings": generate_media_embeddings()
            else: generate_watch_embeddings()
        return 0
    except Exception as exc:
        from api.services.metadata_ingestion import error_code
        print("Importer failed: " + type(exc).__name__ + ": " + error_code(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
