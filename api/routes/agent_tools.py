from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.db.connection import connect_db
from api.services.agent_tool_service import (
    AgentRecommendationsResponse,
    AgentUsersResponse,
    LibraryItem,
    LibrarySearchResponse,
    WatchHistoryResponse,
    get_agent_library_item,
    get_agent_recommendations,
    get_agent_watch_history,
    list_agent_users,
    search_agent_library,
)
from api.services.feedback_service import normalize_feedback_action, record_feedback

router = APIRouter()


class FeedbackPayload(BaseModel):
    user: str
    rating_key: int
    thumb: str
    reasons: list[str] = Field(default_factory=list)
    note: Optional[str] = None


class FeedbackResponse(BaseModel):
    status: str
    message: str


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
    return get_agent_recommendations(
        user=user,
        media_type=media_type,
        limit=limit,
        min_score=min_score,
        max_score=max_score,
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
    return search_agent_library(
        q=q,
        media_type=media_type,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
    )


@router.get("/items/{rating_key}", response_model=LibraryItem)
def agent_get_item(rating_key: int):
    return get_agent_library_item(rating_key=rating_key)


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Submit explicit feedback on an item from a user.",
)
def agent_submit_feedback(payload: FeedbackPayload):
    action = normalize_feedback_action(payload.thumb, field_name="thumb")

    with connect_db() as conn:
        with conn.cursor() as cur:
            record_feedback(
                cur,
                payload.user,
                payload.rating_key,
                action,
                source="agent",
                plex_token=None,
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
    return list_agent_users(username=username, friendly_name=friendly_name, limit=limit)


@router.get("/watch-history", response_model=WatchHistoryResponse)
def agent_watch_history(
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
    return get_agent_watch_history(user=user, limit=limit, engaged_only=engaged_only)
