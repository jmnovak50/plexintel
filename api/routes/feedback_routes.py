import os

import psycopg2
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor

from api.db.users import get_or_create_user
from api.services.feedback_service import normalize_thumb, replace_feedback_rows, resolve_bulk_target
from api.services.plex_service import get_plex_user_info


router = APIRouter()


class FeedbackIn(BaseModel):
    username: str
    rating_key: int
    feedback: str


def _resolve_username(request: Request, payload_username: str, require_session: bool = False) -> str:
    session_username = request.session.get("username")
    if session_username:
        return session_username

    token = request.session.get("plex_token")
    if token:
        plex_user = get_plex_user_info(token)
        if not plex_user or not plex_user.get("username"):
            if require_session:
                raise HTTPException(status_code=401, detail="Unable to resolve authenticated user")
        else:
            username = plex_user["username"]
            user_id, _ = get_or_create_user(
                username=username,
                email=plex_user.get("email"),
                token=token,
            )
            request.session["username"] = username
            request.session["user_id"] = user_id
            return username

    if require_session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    username = (payload_username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    return username


@router.post("/feedback")
def submit_feedback(request: Request, feedback: FeedbackIn):
    try:
        username = _resolve_username(request, feedback.username)
        thumb = normalize_thumb(feedback.feedback, field_name="feedback")

        conn = psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)
        with conn:
            with conn.cursor() as cur:
                replace_feedback_rows(cur, username, [feedback.rating_key], thumb)

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as exc:
        print("Feedback insert error:", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if "conn" in locals() and conn:
            conn.close()


@router.post("/feedback/bulk")
def submit_bulk_feedback(request: Request, feedback: FeedbackIn):
    try:
        username = _resolve_username(request, feedback.username, require_session=True)
        thumb = normalize_thumb(feedback.feedback, field_name="feedback")

        conn = psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)
        with conn:
            with conn.cursor() as cur:
                target = resolve_bulk_target(cur, feedback.rating_key)
                affected_count = replace_feedback_rows(
                    cur,
                    username,
                    target["descendant_rating_keys"],
                    thumb,
                )

        return {
            "status": "ok",
            "target_rating_key": target["target_rating_key"],
            "target_media_type": target["target_media_type"],
            "target_title": target["target_title"],
            "feedback": thumb,
            "affected_count": affected_count,
        }

    except HTTPException:
        raise
    except Exception as exc:
        print("Bulk feedback insert error:", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if "conn" in locals() and conn:
            conn.close()
