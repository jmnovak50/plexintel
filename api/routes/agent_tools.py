from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL")

router = APIRouter()


# ---------- Pydantic models (tool I/O contracts) ----------

class AgentRecommendation(BaseModel):
    # Core, always-present fields
    rating_key: int
    title: str
    media_type: str
    score: float  # predicted_probability

    # Optional metadata
    show_title: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    year: Optional[int] = None
    genres: Optional[str] = None        # comma-separated
    actors: Optional[str] = None        # comma-separated
    directors: Optional[str] = None     # comma-separated
    explanation: Optional[str] = None   # from semantic_themes

    # Enriched fields (from media_enriched_v / recs view)
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

    # duration is whatever you store in the view: seconds, minutes, etc.
    # If it's numeric, int/float is fine; if it's text, change to Optional[str].
    duration: Optional[int] = None

    genres: Optional[str] = None   # comma-separated
    actors: Optional[str] = None   # comma-separated
    directors: Optional[str] = None  # comma-separated



class LibrarySearchResponse(BaseModel):
    query: str
    count: int
    items: List[LibraryItem]


class FeedbackPayload(BaseModel):
    user: str
    rating_key: int
    thumb: str  # "up" or "down"
    # Kept for backwards compatibility with existing agent callers; ignored now.
    reasons: List[str] = Field(default_factory=list)
    note: Optional[str] = None



class FeedbackResponse(BaseModel):
    status: str
    message: str

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
# ---------- DB helper ----------

def get_conn():
    if not DB_URL:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)


# ---------- Tool endpoints ----------

@router.get("/recommendations", response_model=AgentRecommendationsResponse)
def agent_get_recommendations(
    user: str = Query(..., description="Username, e.g. jmnovak"),
    media_type: Optional[str] = Query(
        None, description="Optional filter: movie, episode, show, etc."
    ),
    limit: int = Query(100, ge=1, le=1000),
    min_score: Optional[float] = Query(
        None, ge=0.0, le=1.0, description="Optional min predicted_probability (0.0–1.0)"
    ),
    max_score: Optional[float] = Query(
        None, ge=0.0, le=1.0, description="Optional max predicted_probability (0.0–1.0)"
    ),
):
    """
    Thin wrapper over expanded_recs_w_label_v.

    Returns recommendations for a given user, optionally filtered by media_type.
    If media_type is provided, we only return rows where BOTH:
      - username = user
      - media_type ILIKE media_type
    If media_type is omitted, we only filter on username.
    """
    # Build base SQL
    sql = """
        SELECT
            rating_key,
            show_title,
            title,
            media_type,
            season_number,
            episode_number,
            year,
            genres,
            actors,
            directors,
            summary,
            duration,
            rating,
            added_at,
            predicted_probability,
            semantic_themes
        FROM expanded_recs_w_label_v
        WHERE username = %s
    """

    params: list = [user]

    # Optional media_type filter
    if media_type:
        # Use ILIKE for case-insensitive match; exact match is usually fine here
        sql += " AND media_type ILIKE %s"
        params.append(media_type)
        # Optional score range filter
    if min_score is not None:
        sql += " AND predicted_probability >= %s"
        params.append(min_score)

    if max_score is not None:
        sql += " AND predicted_probability <= %s"
        params.append(max_score)

    # Order + limit
    sql += """
        ORDER BY predicted_probability DESC
        LIMIT %s
    """
    params.append(limit)

    with get_conn() as conn:
        # If get_conn() doesn't already set RealDictCursor, change this to:
        # with conn.cursor(cursor_factory=RealDictCursor) as cur:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    items: List[AgentRecommendation] = []
    for r in rows:
        items.append(
            AgentRecommendation(
                rating_key=r["rating_key"],
                title=r["title"],
                media_type=r["media_type"],
                score=float(r["predicted_probability"]),
                show_title=r.get("show_title"),
                season_number=r.get("season_number"),
                episode_number=r.get("episode_number"),
                year=r.get("year"),
                genres=r.get("genres"),
                actors=r.get("actors"),
                directors=r.get("directors"),
                summary=r.get("summary"),
                duration=r.get("duration"),
                rating=normalize_float(r.get("rating")),
                added_at=r.get("added_at"),
                explanation=r.get("semantic_themes"),
            )
        )

    return AgentRecommendationsResponse(
        user=user,
        count=len(items),
        items=items,
    )

@router.get("/search", response_model=LibrarySearchResponse)
def agent_search_library(
    q: str = Query(..., description="Free text query over title / summary / genres / people."),
    media_type: Optional[str] = Query(
        None, description="Optional filter: movie, episode, show, etc."
    ),
    sort_by: str = Query(
        "title",
        description="Sort field: 'title' or 'year'",
        pattern="^(title|year)$",
    ),
    sort_dir: str = Query(
        "asc",
        description="Sort direction: 'asc' or 'desc'",
        pattern="^(asc|desc)$",
    ),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Agent-oriented search tool over media_enriched_v.

    Expects media_enriched_v to have:
      rating_key, media_type, show_title, title, summary,
      season_number, episode_number, rating, year, duration,
      genres, actors, directors.

    Search matches substrings across:
      title, show_title, summary, genres, actors, directors.
    """

    pattern = f"%{q}%"

    base_sql = """
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

    # 6 placeholders for the pattern fields
    params: List = [pattern, pattern, pattern, pattern, pattern, pattern]

    if media_type:
        base_sql += " AND media_type = %s"
        params.append(media_type)

    # Sorting
    if sort_by == "year":
        order_col = "year"
    else:
        order_col = "title"

    order_dir = "ASC" if sort_dir == "asc" else "DESC"

    base_sql += f" ORDER BY {order_col} {order_dir}, title ASC LIMIT %s"
    params.append(limit)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(base_sql, params)
            rows = cur.fetchall()

    items = [
        LibraryItem(
            rating_key=r["rating_key"],
            title=r["title"],
            media_type=r["media_type"],
            show_title=r.get("show_title"),
            summary=r.get("summary"),
            season_number=r.get("season_number"),
            episode_number=r.get("episode_number"),
            rating=normalize_float(r.get("rating")),
            year=r.get("year"),
            duration=r.get("duration"),
            genres=r.get("genres"),
            actors=r.get("actors"),
            directors=r.get("directors"),
        )
        for r in rows
    ]

    return LibrarySearchResponse(query=q, count=len(items), items=items)

@router.get("/items/{rating_key}", response_model=LibraryItem)
def agent_get_item(rating_key: int):
    """
    Fetch a single library item from media_enriched_v by rating_key.
    Returns the same shape as search results.
    """
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

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (rating_key,))
            r = cur.fetchone()

    if not r:
        raise HTTPException(status_code=404, detail="Item not found")

    return LibraryItem(
        rating_key=r["rating_key"],
        title=r["title"],
        media_type=r["media_type"],
        show_title=r.get("show_title"),
        summary=r.get("summary"),
        season_number=r.get("season_number"),
        episode_number=r.get("episode_number"),
        rating=normalize_float(r.get("rating")),
        year=r.get("year"),
        duration=r.get("duration"),
        genres=r.get("genres"),
        actors=r.get("actors"),
        directors=r.get("directors"),
    )

@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Submit thumbs feedback on an item from a user.",
)
def agent_submit_feedback(
    payload: FeedbackPayload,
):
    """Agent can log one-click thumbs feedback."""
    thumb = (payload.thumb or "").strip().lower()
    if thumb not in ("up", "down"):
        raise HTTPException(status_code=400, detail="thumb must be 'up' or 'down'")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Keep minimal internal reason rows present (handles truncated feedback_reason tables).
            seed_reasons = [
                ("thumb_up", "Thumbs up", "up", True),
                ("thumb_down", "Thumbs down", "down", True),
            ]
            for code, label, applies_to, suppress_default in seed_reasons:
                cur.execute(
                    """
                    INSERT INTO feedback_reason (code, label, applies_to, suppress_default)
                    SELECT %s, %s, %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM feedback_reason WHERE code = %s
                    )
                    """,
                    (code, label, applies_to, suppress_default, code),
                )

            reason_code = "thumb_up" if thumb == "up" else "thumb_down"
            cur.execute(
                """
                DELETE FROM user_feedback
                WHERE username = %s AND rating_key = %s
                """,
                (payload.user, payload.rating_key),
            )
            cur.execute(
                """
                INSERT INTO user_feedback (
                    username,
                    rating_key,
                    feedback,
                    reason_code,
                    suppress,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.user,
                    payload.rating_key,
                    thumb,
                    reason_code,
                    True,
                    datetime.utcnow(),
                ),
            )
        conn.commit()

    return FeedbackResponse(
        status="ok",
        message="Feedback recorded",
    )

@router.get("/users", response_model=AgentUsersResponse)
def agent_list_users(
    username: Optional[str] = Query(
        None,
        description="Optional substring match on username.",
    ),
    friendly_name: Optional[str] = Query(
        None,
        description="Optional substring match on friendly name.",
    ),
    limit: int = Query(
        200,
        ge=1,
        le=1000,
        description="Maximum number of users to return (1–1000).",
    ),
):
    """
    Return distinct users from users_v for agent tools.
    """
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

    with get_conn() as conn:
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

@router.get("/watch-history", response_model=WatchHistoryResponse)
async def agent_watch_history(
    user: Optional[str] = Query(
        None,
        description="Optional username; if omitted, returns watches for all users.",
    ),
    limit: int = Query(
        200,
        ge=1,
        le=200,
        description="Maximum number of rows to return (1–200).",
    ),
    engaged_only: bool = Query(
        False,
        description="If true, only include watches with >=50% completion.",
    ),
):

    """
    Return enriched watch-history records for an agent/tool.

    - If `user` is provided, results are filtered by that username.
    - If `user` is omitted, results include all users.
    - If `engaged_only` is true, only watches with >=50% completion are returned.
    """

    base_query = """
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

    # Optional filters
    if user is not None and user != "":
        conditions.append("username = %s")
        params.append(user)

    if engaged_only:
        conditions.append("engaged = TRUE")

    # Build WHERE clause only if there are conditions
    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)

    # Final ordering + limit
    base_query += " ORDER BY watched_at DESC NULLS LAST LIMIT %s"
    params.append(limit)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(base_query, params)
                rows = cur.fetchall()  # RealDictCursor -> list[dict]

        # Map rows into Pydantic models
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

    except Exception as e:
        logger.exception("Error fetching agent watch history")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch watch history: {e}",
        )
