from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.services.app_settings import get_setting_value
from api.services.fintel_service import check_fintel_health, fetch_fintel_recommendations


router = APIRouter(prefix="/api/fintel/v1", tags=["fintel"])


class FIntelRecommendation(BaseModel):
    rating_key: int
    title: str
    year: int | None = None
    media_type: str
    probability: float = Field(ge=0.0, le=1.0)
    tmdb_id: str | None = None
    imdb_id: str | None = None
    tvdb_id: str | None = None


class FIntelRecommendationsResponse(BaseModel):
    username: str
    recommendations: list[FIntelRecommendation]


class FIntelHealthResponse(BaseModel):
    status: str
    database: str
    schema_version: int


def require_fintel_api_key(
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    expected = get_setting_value("public_api.api_key")
    if not isinstance(expected, str) or not expected.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FIntel API authentication is not configured",
        )
    if not isinstance(api_key, str) or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


@router.get("/health", response_model=FIntelHealthResponse)
def get_fintel_health(
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> FIntelHealthResponse:
    require_fintel_api_key(api_key)
    check_fintel_health()
    return FIntelHealthResponse(status="ok", database="ok", schema_version=1)


@router.get("/recommendations", response_model=FIntelRecommendationsResponse)
def get_fintel_recommendations(
    username: Annotated[str, Query(min_length=1, max_length=255)],
    media_type: Annotated[str, Query(pattern="^movie$")] = "movie",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> FIntelRecommendationsResponse:
    require_fintel_api_key(api_key)
    normalized_username = username.strip()
    if not normalized_username:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="username is required")

    recommendations = fetch_fintel_recommendations(
        username=normalized_username,
        media_type=media_type,
        limit=limit,
    )
    return FIntelRecommendationsResponse(
        username=normalized_username,
        recommendations=[FIntelRecommendation.model_validate(item) for item in recommendations],
    )
