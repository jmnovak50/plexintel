from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services.recommendation_filter_service import (
    latest_feedback_cte,
    leaf_feedback_join,
    leaf_feedback_visibility_clause,
)

logger = logging.getLogger(__name__)


class AgentRecommendation(BaseModel):
    rating_key: int
    title: str
    media_type: str
    score: float

    show_title: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    year: Optional[int] = None
    genres: Optional[str] = None
    actors: Optional[str] = None
    directors: Optional[str] = None
    explanation: Optional[str] = None
    summary: Optional[str] = None
    duration: Optional[int] = None
    rating: float | None = None
    added_at: Optional[datetime] = None


class AgentRecommendationsResponse(BaseModel):
    user: str
    count: int
    items: List[AgentRecommendation]


class LibraryItem(BaseModel):
    rating_key: int
    title: str
    media_type: str

    show_title: Optional[str] = None
    summary: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    rating: Optional[float] = None
    year: Optional[int] = None
    duration: Optional[int] = None
    genres: Optional[str] = None
    actors: Optional[str] = None
    directors: Optional[str] = None


class LibrarySearchResponse(BaseModel):
    query: str
    count: int
    items: List[LibraryItem]


class RecentLibraryItem(BaseModel):
    rating_key: int
    title: str
    media_type: str

    show_title: Optional[str] = None
    summary: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    rating: Optional[float] = None
    year: Optional[int] = None
    duration: Optional[int] = None
    genres: Optional[str] = None
    actors: Optional[str] = None
    directors: Optional[str] = None
    added_at: Optional[datetime] = None
    changed_at: Optional[datetime] = None


class RecentLibraryAdditionsResponse(BaseModel):
    media_type: Optional[str]
    days: Optional[int]
    count: int
    items: List[RecentLibraryItem]


class AgentUser(BaseModel):
    username: str
    friendly_name: Optional[str]


class AgentUsersResponse(BaseModel):
    count: int
    items: List[AgentUser]


class WatchHistoryItem(BaseModel):
    watch_id: int
    username: str
    friendly_name: Optional[str]
    rating_key: int
    watched_at: Optional[datetime]
    played_duration: Optional[int]
    media_duration: Optional[int]
    percent_complete: Optional[float]
    engaged: Optional[bool]
    media_type: Optional[str]
    show_title: Optional[str]
    title: Optional[str]
    summary: Optional[str]
    season_number: Optional[int]
    episode_number: Optional[int]
    rating: float | None = None
    year: Optional[int]
    genres: Optional[str]
    actors: Optional[str]
    directors: Optional[str]


class WatchHistoryResponse(BaseModel):
    user: Optional[str]
    engaged_only: bool
    count: int
    results: list[WatchHistoryItem]


def normalize_float(value):
    if value in (None, "", " "):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _get_conn():
    return connect_db(cursor_factory=RealDictCursor)


def get_agent_recommendations(
    *,
    user: str,
    media_type: Optional[str] = None,
    limit: int = 100,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
) -> AgentRecommendationsResponse:
    sql = latest_feedback_cte() + """
        SELECT
            recs.rating_key,
            recs.show_title,
            recs.title,
            recs.media_type,
            recs.season_number,
            recs.episode_number,
            recs.year,
            recs.genres,
            recs.actors,
            recs.directors,
            recs.summary,
            recs.duration,
            recs.rating,
            recs.added_at,
            recs.predicted_probability,
            recs.semantic_themes
        FROM expanded_recs_w_label_v recs
    """ + leaf_feedback_join("recs") + """
        WHERE recs.username = %s
    """ + leaf_feedback_visibility_clause()

    params: list[object] = [user, user]

    if media_type:
        sql += " AND recs.media_type ILIKE %s"
        params.append(media_type)
    if min_score is not None:
        sql += " AND recs.predicted_probability >= %s"
        params.append(min_score)
    if max_score is not None:
        sql += " AND recs.predicted_probability <= %s"
        params.append(max_score)

    sql += " ORDER BY recs.predicted_probability DESC LIMIT %s"
    params.append(limit)

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    items = [
        AgentRecommendation(
            rating_key=row["rating_key"],
            title=row["title"],
            media_type=row["media_type"],
            score=float(row["predicted_probability"]),
            show_title=row.get("show_title"),
            season_number=row.get("season_number"),
            episode_number=row.get("episode_number"),
            year=row.get("year"),
            genres=row.get("genres"),
            actors=row.get("actors"),
            directors=row.get("directors"),
            summary=row.get("summary"),
            duration=row.get("duration"),
            rating=normalize_float(row.get("rating")),
            added_at=row.get("added_at"),
            explanation=row.get("semantic_themes"),
        )
        for row in rows
    ]

    return AgentRecommendationsResponse(user=user, count=len(items), items=items)


def search_agent_library(
    *,
    q: str,
    media_type: Optional[str] = None,
    sort_by: str = "title",
    sort_dir: str = "asc",
    limit: int = 20,
) -> LibrarySearchResponse:
    pattern = f"%{q}%"
    sql = """
        SELECT
            rating_key,
            media_type,
            show_title,
            title,
            summary,
            season_number,
            episode_number,
            rating,
            year,
            duration,
            genres,
            actors,
            directors
        FROM media_enriched_v
        WHERE (
            title ILIKE %s
            OR show_title ILIKE %s
            OR summary ILIKE %s
            OR genres ILIKE %s
            OR actors ILIKE %s
            OR directors ILIKE %s
        )
    """

    params: List[object] = [pattern, pattern, pattern, pattern, pattern, pattern]

    if media_type:
        sql += " AND media_type = %s"
        params.append(media_type)

    order_col = "year" if sort_by == "year" else "title"
    order_dir = "ASC" if sort_dir == "asc" else "DESC"
    sql += f" ORDER BY {order_col} {order_dir}, title ASC LIMIT %s"
    params.append(limit)

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    items = [
        LibraryItem(
            rating_key=row["rating_key"],
            title=row["title"],
            media_type=row["media_type"],
            show_title=row.get("show_title"),
            summary=row.get("summary"),
            season_number=row.get("season_number"),
            episode_number=row.get("episode_number"),
            rating=normalize_float(row.get("rating")),
            year=row.get("year"),
            duration=row.get("duration"),
            genres=row.get("genres"),
            actors=row.get("actors"),
            directors=row.get("directors"),
        )
        for row in rows
    ]

    return LibrarySearchResponse(query=q, count=len(items), items=items)


def get_agent_library_item(*, rating_key: int) -> LibraryItem:
    sql = """
        SELECT
            rating_key,
            media_type,
            show_title,
            title,
            summary,
            season_number,
            episode_number,
            rating,
            year,
            duration,
            genres,
            actors,
            directors
        FROM media_enriched_v
        WHERE rating_key = %s
    """

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (rating_key,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Item not found")

    return LibraryItem(
        rating_key=row["rating_key"],
        title=row["title"],
        media_type=row["media_type"],
        show_title=row.get("show_title"),
        summary=row.get("summary"),
        season_number=row.get("season_number"),
        episode_number=row.get("episode_number"),
        rating=normalize_float(row.get("rating")),
        year=row.get("year"),
        duration=row.get("duration"),
        genres=row.get("genres"),
        actors=row.get("actors"),
        directors=row.get("directors"),
    )


def get_recent_library_additions(
    *,
    media_type: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 50,
) -> RecentLibraryAdditionsResponse:
    if days is not None and days < 1:
        raise HTTPException(status_code=400, detail="days must be >= 1")

    sql = """
        SELECT
            rating_key,
            media_type,
            show_title,
            title,
            summary,
            season_number,
            episode_number,
            rating,
            year,
            duration,
            genres,
            actors,
            directors,
            added_at,
            changed_at
        FROM library_catalog_v
        WHERE rating_key IS NOT NULL
    """

    params: list[object] = []

    if media_type:
        sql += " AND media_type ILIKE %s"
        params.append(media_type)
    if days is not None:
        sql += " AND COALESCE(added_at, changed_at) >= NOW() - (%s * INTERVAL '1 day')"
        params.append(days)

    sql += """
        ORDER BY COALESCE(added_at, changed_at) DESC NULLS LAST, rating_key DESC
        LIMIT %s
    """
    params.append(limit)

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    items = [
        RecentLibraryItem(
            rating_key=row["rating_key"],
            title=row["title"],
            media_type=row["media_type"],
            show_title=row.get("show_title"),
            summary=row.get("summary"),
            season_number=row.get("season_number"),
            episode_number=row.get("episode_number"),
            rating=normalize_float(row.get("rating")),
            year=row.get("year"),
            duration=row.get("duration"),
            genres=row.get("genres"),
            actors=row.get("actors"),
            directors=row.get("directors"),
            added_at=row.get("added_at"),
            changed_at=row.get("changed_at"),
        )
        for row in rows
    ]

    return RecentLibraryAdditionsResponse(
        media_type=media_type,
        days=days,
        count=len(items),
        items=items,
    )


def list_agent_users(
    *,
    username: Optional[str] = None,
    friendly_name: Optional[str] = None,
    limit: int = 200,
) -> AgentUsersResponse:
    sql = """
        SELECT
            username,
            friendly_name
        FROM users_v
        WHERE username IS NOT NULL
    """
    params: list[object] = []

    if username:
        sql += " AND username ILIKE %s"
        params.append(f"%{username}%")
    if friendly_name:
        sql += " AND friendly_name ILIKE %s"
        params.append(f"%{friendly_name}%")

    sql += " ORDER BY username ASC LIMIT %s"
    params.append(limit)

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    items = [
        AgentUser(
            username=row["username"],
            friendly_name=row.get("friendly_name"),
        )
        for row in rows
    ]
    return AgentUsersResponse(count=len(items), items=items)


def get_agent_watch_history(
    *,
    user: Optional[str] = None,
    limit: int = 200,
    engaged_only: bool = False,
) -> WatchHistoryResponse:
    sql = """
        SELECT
            watch_id,
            username,
            friendly_name,
            rating_key,
            watched_at,
            played_duration,
            media_duration,
            percent_complete,
            engaged,
            media_type,
            show_title,
            title,
            summary,
            season_number,
            episode_number,
            rating,
            year,
            genres,
            actors,
            directors
        FROM watch_history_enriched_v
    """

    conditions: list[str] = []
    params: list[object] = []

    if user:
        conditions.append("username = %s")
        params.append(user)
    if engaged_only:
        conditions.append("engaged = TRUE")

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY watched_at DESC NULLS LAST LIMIT %s"
    params.append(limit)

    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as exc:
        logger.exception("Error fetching agent watch history")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch watch history: {exc}",
        ) from exc

    items = [
        WatchHistoryItem(
            **{
                **row,
                "rating": normalize_float(row.get("rating")),
            }
        )
        for row in rows
    ]

    return WatchHistoryResponse(
        user=user,
        engaged_only=engaged_only,
        count=len(items),
        results=items,
    )
