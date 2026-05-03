from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from api.services.poster_service import fetch_poster_image_for_rating_key, resize_poster_image_to_width

router = APIRouter()


@router.get("/posters/{rating_key}")
def get_poster(
    rating_key: int,
    w: Annotated[int | None, Query(ge=1, le=1200)] = None,
    thumb: Annotated[bool, Query()] = False,
):
    try:
        payload = fetch_poster_image_for_rating_key(rating_key)
    except Exception as exc:
        detail = str(exc)
        if detail == "Poster proxy is not configured.":
            raise HTTPException(status_code=500, detail=detail) from exc
        raise HTTPException(status_code=502, detail=detail or "Unable to fetch poster from Tautulli.") from exc

    if not payload:
        raise HTTPException(status_code=404, detail="Poster not found.")

    poster_payload = payload
    width = 180 if thumb and w is None else w
    if width is not None:
        poster_payload = resize_poster_image_to_width(
            payload["content"],
            payload.get("content_type"),
            width=width,
        )

    return Response(
        content=poster_payload["content"],
        media_type=poster_payload["content_type"],
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        },
    )
