from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any
from urllib.parse import urlsplit

from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services.app_settings import get_setting_value
from api.services.library_service import fetch_tautulli_metadata
from api.services.recommendation_query_service import _build_recommendations_query


EXTERNAL_ID_CACHE_TTL_SECONDS = 24 * 60 * 60
EXTERNAL_ID_CACHE_MAX_ENTRIES = 10_000


@dataclass(frozen=True)
class ExternalIds:
    tmdb_id: str | None = None
    imdb_id: str | None = None
    tvdb_id: str | None = None


_external_id_cache: OrderedDict[int, tuple[float, ExternalIds]] = OrderedDict()
_external_id_cache_lock = Lock()


def clear_external_id_cache() -> None:
    """Clear cached Tautulli identifier lookups (primarily for tests)."""
    with _external_id_cache_lock:
        _external_id_cache.clear()


def _clean_guid_value(value: str) -> str | None:
    cleaned = value.split("?", 1)[0].strip().strip("/")
    return cleaned or None


def parse_external_ids(metadata: dict[str, Any] | None) -> ExternalIds:
    """Extract stable external provider IDs from modern and legacy Plex GUIDs."""
    if not metadata:
        return ExternalIds()

    raw_guids = metadata.get("guids")
    candidates: list[str] = []
    if isinstance(raw_guids, (list, tuple)):
        candidates.extend(value for value in raw_guids if isinstance(value, str))

    primary_guid = metadata.get("guid")
    if isinstance(primary_guid, str):
        candidates.append(primary_guid)

    identifiers: dict[str, str] = {}
    legacy_prefixes = {
        "com.plexapp.agents.themoviedb": "tmdb",
        "com.plexapp.agents.imdb": "imdb",
        "com.plexapp.agents.thetvdb": "tvdb",
    }

    for raw_guid in candidates:
        parsed = urlsplit(raw_guid)
        scheme = parsed.scheme.lower()
        provider = scheme if scheme in {"tmdb", "imdb", "tvdb"} else legacy_prefixes.get(scheme)
        if provider is None or provider in identifiers:
            continue

        value = _clean_guid_value(parsed.netloc + parsed.path)
        if value:
            identifiers[provider] = value

    return ExternalIds(
        tmdb_id=identifiers.get("tmdb"),
        imdb_id=identifiers.get("imdb"),
        tvdb_id=identifiers.get("tvdb"),
    )


def _get_cached_external_ids(rating_key: int) -> ExternalIds | None:
    now = time.monotonic()
    with _external_id_cache_lock:
        cached = _external_id_cache.get(rating_key)
        if cached is None:
            return None
        cached_at, identifiers = cached
        if now - cached_at >= EXTERNAL_ID_CACHE_TTL_SECONDS:
            del _external_id_cache[rating_key]
            return None
        _external_id_cache.move_to_end(rating_key)
        return identifiers


def _cache_external_ids(rating_key: int, identifiers: ExternalIds) -> None:
    with _external_id_cache_lock:
        _external_id_cache[rating_key] = (time.monotonic(), identifiers)
        _external_id_cache.move_to_end(rating_key)
        while len(_external_id_cache) > EXTERNAL_ID_CACHE_MAX_ENTRIES:
            _external_id_cache.popitem(last=False)


def resolve_external_ids(rating_key: int) -> ExternalIds:
    cached = _get_cached_external_ids(rating_key)
    if cached is not None:
        return cached

    try:
        metadata = fetch_tautulli_metadata(rating_key)
    except Exception:
        return ExternalIds()

    if not metadata:
        return ExternalIds()

    identifiers = parse_external_ids(metadata)
    _cache_external_ids(rating_key, identifiers)
    return identifiers


def check_fintel_health() -> None:
    conn = connect_db()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
    finally:
        if cur is not None:
            cur.close()
        conn.close()


def fetch_fintel_recommendations(*, username: str, media_type: str, limit: int) -> list[dict[str, Any]]:
    if media_type != "movie":
        raise ValueError("Only media_type=movie is supported in FIntel Phase 1")

    display_threshold = float(get_setting_value("recommendations.display_threshold", default=0.70))
    sql, params = _build_recommendations_query(
        username=username,
        view="movies",
        show_rating_key=None,
        season_rating_key=None,
        search=None,
        sort=None,
        display_threshold=display_threshold,
    )
    sql += " LIMIT %s"
    params.append(limit)

    conn = connect_db(cursor_factory=RealDictCursor)
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    finally:
        if cur is not None:
            cur.close()
        conn.close()

    recommendations: list[dict[str, Any]] = []
    for row in rows:
        rating_key = int(row["rating_key"])
        identifiers = resolve_external_ids(rating_key)
        recommendations.append(
            {
                "rating_key": rating_key,
                "title": row.get("title") or "",
                "year": int(row["year"]) if row.get("year") is not None else None,
                "media_type": "movie",
                "probability": float(row["predicted_probability"]),
                "tmdb_id": identifiers.tmdb_id,
                "imdb_id": identifiers.imdb_id,
                "tvdb_id": identifiers.tvdb_id,
            }
        )

    return recommendations
