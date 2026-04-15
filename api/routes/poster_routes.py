from fastapi import APIRouter, HTTPException, Request, Response
from api.services.poster_service import fetch_poster_image_for_rating_key

router = APIRouter()


@router.get("/posters/{rating_key}")
def get_poster(rating_key: int, request: Request):
    token = request.session.get("plex_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = fetch_poster_image_for_rating_key(rating_key)
    except Exception as exc:
        detail = str(exc)
        if detail == "Poster proxy is not configured.":
            raise HTTPException(status_code=500, detail=detail) from exc
        raise HTTPException(status_code=502, detail=detail or "Unable to fetch poster from Tautulli.") from exc

    if not payload:
        raise HTTPException(status_code=404, detail="Poster not found.")

    return Response(
        content=payload["content"],
        media_type=payload["content_type"],
        headers={"Cache-Control": "private, max-age=3600"},
    )
