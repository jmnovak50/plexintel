from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.db.users import get_or_create_user
from api.services.feedback_service import (
    delete_feedback_row,
    normalize_bulk_feedback_action,
    normalize_feedback_action,
    record_bulk_feedback,
    record_feedback,
)
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
        action = normalize_feedback_action(feedback.feedback, field_name="feedback")
        plex_token = request.session.get("plex_token")

        conn = connect_db(cursor_factory=RealDictCursor)
        with conn:
            with conn.cursor() as cur:
                feedback_row = record_feedback(
                    cur,
                    username,
                    feedback.rating_key,
                    action,
                    source="ui",
                    plex_token=plex_token,
                )

        return {
            "status": "ok",
            "feedback": feedback_row,
        }

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
        action = normalize_bulk_feedback_action(feedback.feedback, field_name="feedback")

        conn = connect_db(cursor_factory=RealDictCursor)
        with conn:
            with conn.cursor() as cur:
                result = record_bulk_feedback(
                    cur,
                    username,
                    feedback.rating_key,
                    action,
                    source="bulk",
                )

        return {
            "status": "ok",
            **result,
        }

    except HTTPException:
        raise
    except Exception as exc:
        print("Bulk feedback insert error:", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if "conn" in locals() and conn:
            conn.close()


@router.delete("/feedback/{rating_key}")
def remove_feedback(request: Request, rating_key: int, username: str | None = None):
    try:
        resolved_username = _resolve_username(request, username or "", require_session=False)
        plex_token = request.session.get("plex_token")

        conn = connect_db(cursor_factory=RealDictCursor)
        with conn:
            with conn.cursor() as cur:
                result = delete_feedback_row(
                    cur,
                    resolved_username,
                    rating_key,
                    plex_token=plex_token,
                )

        return {
            "status": "ok",
            **result,
        }

    except HTTPException:
        raise
    except Exception as exc:
        print("Feedback delete error:", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        if "conn" in locals() and conn:
            conn.close()
