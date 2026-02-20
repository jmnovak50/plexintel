import os
import subprocess
from typing import Optional

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor

from api.db.users import get_or_create_user
from api.services.plex_service import get_plex_user_info

router = APIRouter()

# Whitelisted scripts that can be run
ALLOWED_SCRIPTS = {
    "train_model.py",
    "build_training_data.py",
    "score_model.py",
    "build_user_embeddings.py",
    "fetch_tautulli_data.py",
    "label_embeddings.py",
    "run_daily_pipeline.sh",
}

DB_URL = os.getenv("DATABASE_URL")


class ScriptRequest(BaseModel):
    script: str


def _require_db_url() -> str:
    if not DB_URL:
        raise HTTPException(status_code=500, detail="DATABASE_URL not configured")
    return DB_URL


def _load_user_record(username: str) -> Optional[dict]:
    conn = psycopg2.connect(_require_db_url(), cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, username, is_admin, created_at, last_login
                FROM users
                WHERE username = %s
                """,
                (username,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def get_current_user(request: Request):
    username = request.session.get("username")
    if not username:
        token = request.session.get("plex_token")
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        plex_user = get_plex_user_info(token)
        if not plex_user or not plex_user.get("username"):
            raise HTTPException(status_code=401, detail="Unable to resolve authenticated user")

        username = plex_user["username"]
        user_id, _ = get_or_create_user(
            username=username,
            email=plex_user.get("email"),
            token=token,
        )
        request.session["username"] = username
        request.session["user_id"] = user_id

    try:
        user = _load_user_record(username)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def require_admin(user=Depends(get_current_user)):
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/admin/me")
def admin_me(user=Depends(get_current_user)):
    return {
        "username": user["username"],
        "is_admin": bool(user["is_admin"]),
        "created_at": user.get("created_at"),
        "last_login": user.get("last_login"),
    }


@router.get("/admin/users")
def admin_list_users(user=Depends(require_admin)):
    try:
        conn = psycopg2.connect(_require_db_url(), cursor_factory=RealDictCursor)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.username,
                    u.is_admin,
                    u.created_at,
                    u.last_login,
                    COALESCE(r.recommendation_count, 0) AS recommendation_count,
                    COALESCE(f.feedback_count, 0) AS feedback_count
                FROM users u
                LEFT JOIN (
                    SELECT username, COUNT(*)::int AS recommendation_count
                    FROM recommendations
                    GROUP BY username
                ) r ON r.username = u.username
                LEFT JOIN (
                    SELECT username, COUNT(*)::int AS feedback_count
                    FROM user_feedback
                    GROUP BY username
                ) f ON f.username = u.username
                ORDER BY
                    u.is_admin DESC,
                    COALESCE(u.last_login, u.created_at) DESC NULLS LAST,
                    u.username ASC
                """
            )
            users = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if "conn" in locals() and conn:
            conn.close()

    return {
        "count": len(users),
        "requested_by": user["username"],
        "users": users,
    }


@router.get("/admin/recommendations")
def admin_get_recommendations(
    target_username: str = Query(...),
    view: str = Query("all"),
    show_rating_key: Optional[int] = Query(None),
    season_rating_key: Optional[int] = Query(None),
    admin_user=Depends(require_admin),
):
    try:
        conn = psycopg2.connect(_require_db_url(), cursor_factory=RealDictCursor)
        with conn.cursor() as cur:
            view_key = (view or "all").lower()
            if view_key not in {"all", "movies", "shows", "seasons", "episodes"}:
                raise HTTPException(status_code=400, detail=f"Unsupported view: {view}")

            if view_key == "shows":
                sql = """
                    SELECT friendly_name,
                           show_rating_key AS rating_key,
                           show_title AS title,
                           rollup_score AS predicted_probability,
                           NULL::text AS semantic_themes,
                           year,
                           genres,
                           show_title,
                           NULL::int AS season_number,
                           NULL::int AS episode_number,
                           'show'::text AS media_type,
                           scored_at,
                           score_band,
                           show_rating_key,
                           NULL::int AS parent_rating_key
                    FROM show_rollups_v
                    WHERE username = %s
                    ORDER BY rollup_score DESC
                """
                params = [target_username]
            elif view_key == "seasons":
                sql = """
                    SELECT friendly_name,
                           season_rating_key AS rating_key,
                           season_title AS title,
                           rollup_score AS predicted_probability,
                           NULL::text AS semantic_themes,
                           year,
                           genres,
                           show_title,
                           season_number,
                           NULL::int AS episode_number,
                           'season'::text AS media_type,
                           scored_at,
                           score_band,
                           show_rating_key,
                           show_rating_key AS parent_rating_key
                    FROM season_rollups_v
                    WHERE username = %s
                """
                params = [target_username]
                if show_rating_key is not None:
                    sql += " AND show_rating_key = %s"
                    params.append(show_rating_key)
                sql += " ORDER BY rollup_score DESC"
            else:
                sql = """
                    SELECT friendly_name,
                           rating_key,
                           title,
                           predicted_probability,
                           semantic_themes,
                           year,
                           genres,
                           show_title,
                           season_number,
                           episode_number,
                           media_type,
                           scored_at,
                           NULL::text AS score_band,
                           show_rating_key,
                           parent_rating_key
                    FROM expanded_recs_w_label_v
                    WHERE username = %s
                """
                params = [target_username]
                if view_key == "movies":
                    sql += " AND media_type = 'movie'"
                elif view_key == "episodes":
                    sql += " AND media_type = 'episode'"
                else:
                    sql += " AND media_type IN ('movie', 'episode')"

                if show_rating_key is not None:
                    sql += " AND show_rating_key = %s"
                    params.append(show_rating_key)
                if season_rating_key is not None:
                    sql += " AND parent_rating_key = %s"
                    params.append(season_rating_key)

                sql += " ORDER BY predicted_probability DESC"

            cur.execute(sql, tuple(params))
            rec_rows = cur.fetchall()

            cur.execute(
                """
                SELECT DISTINCT rating_key
                FROM user_feedback
                WHERE username = %s
                """,
                (target_username,),
            )
            feedback_keys = [row["rating_key"] for row in cur.fetchall()]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if "conn" in locals() and conn:
            conn.close()

    return {
        "requested_by": admin_user["username"],
        "username": target_username,
        "recommendations": rec_rows,
        "last_updated": rec_rows[0]["scored_at"] if rec_rows else None,
        "feedback_keys": feedback_keys,
    }


@router.get("/admin/feedback")
def admin_feedback_history(
    target_username: str = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    admin_user=Depends(require_admin),
):
    try:
        conn = psycopg2.connect(_require_db_url(), cursor_factory=RealDictCursor)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    f.id,
                    f.username,
                    f.rating_key,
                    f.feedback,
                    f.reason_code,
                    fr.label AS reason_label,
                    f.suppress,
                    f.created_at,
                    l.media_type,
                    l.title,
                    l.show_title
                FROM user_feedback f
                LEFT JOIN feedback_reason fr ON fr.code = f.reason_code
                LEFT JOIN library l ON l.rating_key = f.rating_key
                WHERE f.username = %s
                ORDER BY f.created_at DESC
                LIMIT %s
                """,
                (target_username, limit),
            )
            rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if "conn" in locals() and conn:
            conn.close()

    return {
        "requested_by": admin_user["username"],
        "username": target_username,
        "count": len(rows),
        "feedback": rows,
    }


@router.post("/admin/run-script")
async def run_script(req: ScriptRequest, admin_user=Depends(require_admin)):
    if req.script not in ALLOWED_SCRIPTS:
        raise HTTPException(status_code=400, detail=f"Script '{req.script}' not allowed")

    try:
        result = subprocess.run(
            ["python3", req.script] if req.script.endswith(".py") else ["bash", req.script],
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "requested_by": admin_user["username"],
            "script": req.script,
            "exit_code": result.returncode,
            "stdout": result.stdout[-5000:],  # Limit output to last 5K chars
            "stderr": result.stderr[-5000:],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
