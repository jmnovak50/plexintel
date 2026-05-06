import subprocess
from typing import Optional

import psycopg2
import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.db.users import get_or_create_user
from api.services.app_settings import (
    SettingsValidationError,
    get_settings_payload,
    save_settings,
    test_ollama_settings,
    test_tautulli_settings,
)
from api.services.plex_service import get_plex_user_info
from api.services.recommendation_filter_service import (
    latest_feedback_cte,
    leaf_feedback_join,
    leaf_feedback_visibility_clause,
)
from api.routes.recommendation_routes import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    _append_paging,
    _append_search_filter,
    _build_order_clause,
    _decorate_recommendation_rows,
    _page_rows,
)

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
    "run_email_digest.py",
}

class ScriptRequest(BaseModel):
    script: str


class SettingsUpdateRequest(BaseModel):
    updates: dict[str, bool | int | float | str | None] = Field(default_factory=dict)
    clear_keys: list[str] = Field(default_factory=list)


class SettingsTestRequest(BaseModel):
    updates: dict[str, bool | int | float | str | None] = Field(default_factory=dict)
    clear_keys: list[str] = Field(default_factory=list)


def _build_user_display_name(username: Optional[str], friendly_name: Optional[str]) -> Optional[str]:
    normalized_username = (username or "").strip()
    normalized_friendly_name = (friendly_name or "").strip()

    if normalized_friendly_name and normalized_username:
        return f"{normalized_friendly_name} ({normalized_username})"
    if normalized_friendly_name:
        return normalized_friendly_name
    if normalized_username:
        return normalized_username
    return None


def _load_user_record(username: str) -> Optional[dict]:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(ufv.user_id, u.user_id) AS user_id,
                    u.username,
                    COALESCE(NULLIF(BTRIM(u.friendly_name), ''), ufv.friendly_name) AS friendly_name,
                    u.plex_email,
                    u.is_admin,
                    COALESCE(ufv.created_at, u.created_at) AS created_at,
                    COALESCE(ufv.last_login, u.last_login) AS last_login,
                    COALESCE(ufv.modified_at, u.modified_at) AS modified_at
                FROM users u
                LEFT JOIN users_full_v ufv ON ufv.username = u.username
                WHERE u.username = %s
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
        "friendly_name": user.get("friendly_name"),
        "display_name": _build_user_display_name(user.get("username"), user.get("friendly_name")),
        "plex_email": user.get("plex_email"),
        "is_admin": bool(user["is_admin"]),
        "created_at": user.get("created_at"),
        "last_login": user.get("last_login"),
    }


@router.get("/admin/users")
def admin_list_users(user=Depends(require_admin)):
    try:
        conn = connect_db(cursor_factory=RealDictCursor)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    uv.user_id,
                    uv.username,
                    COALESCE(NULLIF(BTRIM(u.friendly_name), ''), uv.friendly_name) AS friendly_name,
                    u.plex_email,
                    COALESCE(u.is_admin, FALSE) AS is_admin,
                    uv.created_at,
                    uv.last_login,
                    COALESCE(r.recommendation_count, 0) AS recommendation_count,
                    COALESCE(f.feedback_count, 0) AS feedback_count
                FROM users_full_v uv
                LEFT JOIN users u ON u.username = uv.username
                LEFT JOIN (
                    SELECT username, COUNT(*)::int AS recommendation_count
                    FROM recommendations
                    GROUP BY username
                ) r ON r.username = uv.username
                LEFT JOIN (
                    SELECT username, COUNT(*)::int AS feedback_count
                    FROM user_feedback
                    GROUP BY username
                ) f ON f.username = uv.username
                ORDER BY
                    COALESCE(u.is_admin, FALSE) DESC,
                    COALESCE(uv.last_login, uv.created_at) DESC NULLS LAST,
                    COALESCE(NULLIF(BTRIM(uv.friendly_name), ''), uv.username) ASC,
                    uv.username ASC
                """
            )
            users = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if "conn" in locals() and conn:
            conn.close()

    for row in users:
        row["display_name"] = _build_user_display_name(row.get("username"), row.get("friendly_name"))

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
    search: Optional[str] = Query(None),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(0, ge=0),
    sort: Optional[list[str]] = Query(None),
    min_probability: Optional[float] = Query(None, ge=0.0, le=1.0),
    admin_user=Depends(require_admin),
):
    try:
        conn = connect_db(cursor_factory=RealDictCursor)
        with conn.cursor() as cur:
            view_key = (view or "all").lower()
            if view_key not in {"all", "movies", "shows", "seasons", "episodes"}:
                raise HTTPException(status_code=400, detail=f"Unsupported view: {view}")

            show_rating_key = show_rating_key if isinstance(show_rating_key, int) else None
            season_rating_key = season_rating_key if isinstance(season_rating_key, int) else None
            search = search if isinstance(search, str) else None
            sort = sort if isinstance(sort, list) else None
            min_probability = min_probability if isinstance(min_probability, (int, float)) else None

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
                """
                params = [target_username]
                if min_probability is not None:
                    sql += " AND rollup_score >= %s"
                    params.append(min_probability)
                sql = _append_search_filter(sql, params, search, ["show_title", "genres"])
                sql += _build_order_clause(sort)
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
                if min_probability is not None:
                    sql += " AND rollup_score >= %s"
                    params.append(min_probability)
                sql = _append_search_filter(sql, params, search, ["season_title", "show_title", "genres"])
                sql += _build_order_clause(sort)
            else:
                sql = latest_feedback_cte() + """
                    SELECT recs.friendly_name,
                           recs.rating_key,
                           recs.title,
                           recs.predicted_probability,
                           recs.semantic_themes,
                           recs.year,
                           recs.genres,
                           recs.show_title,
                           recs.season_number,
                           recs.episode_number,
                           recs.media_type,
                           recs.scored_at,
                           NULL::text AS score_band,
                           recs.show_rating_key,
                           recs.parent_rating_key
                    FROM expanded_recs_w_label_v recs
                """ + leaf_feedback_join("recs") + """
                    WHERE recs.username = %s
                """ + leaf_feedback_visibility_clause()
                params = [target_username, target_username]
                if view_key == "movies":
                    sql += " AND recs.media_type = 'movie'"
                elif view_key == "episodes":
                    sql += " AND recs.media_type = 'episode'"
                else:
                    sql += " AND recs.media_type IN ('movie', 'episode')"

                if show_rating_key is not None:
                    sql += " AND recs.show_rating_key = %s"
                    params.append(show_rating_key)
                if season_rating_key is not None:
                    sql += " AND recs.parent_rating_key = %s"
                    params.append(season_rating_key)
                if min_probability is not None:
                    sql += " AND recs.predicted_probability >= %s"
                    params.append(min_probability)

                sql = _append_search_filter(
                    sql,
                    params,
                    search,
                    ["recs.title", "recs.show_title", "recs.genres", "recs.semantic_themes"],
                )
                sql += _build_order_clause(sort)

            sql = _append_paging(sql, params, limit=limit, offset=offset)
            cur.execute(sql, tuple(params))
            fetched_rows = cur.fetchall()
            rec_rows, has_more, next_offset = _page_rows(fetched_rows, limit=limit, offset=offset)
            _decorate_recommendation_rows(rec_rows)

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
        "has_more": has_more,
        "next_offset": next_offset,
        "limit": limit,
        "offset": offset,
    }


@router.get("/admin/feedback")
def admin_feedback_history(
    target_username: str = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    admin_user=Depends(require_admin),
):
    try:
        conn = connect_db(cursor_factory=RealDictCursor)
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
                    f.plex_watchlist_status,
                    f.plex_watchlist_synced_at,
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


@router.get("/admin/settings")
def admin_get_settings(admin_user=Depends(require_admin)):
    return {
        "requested_by": admin_user["username"],
        "sections": get_settings_payload(),
    }


@router.put("/admin/settings")
def admin_save_settings(req: SettingsUpdateRequest, admin_user=Depends(require_admin)):
    try:
        save_settings(
            updates=req.updates,
            clear_keys=req.clear_keys,
            updated_by=admin_user["username"],
        )
    except SettingsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed saving settings: {exc}") from exc

    return {
        "requested_by": admin_user["username"],
        "sections": get_settings_payload(),
    }


@router.post("/admin/settings/test/tautulli")
def admin_test_tautulli(req: SettingsTestRequest, admin_user=Depends(require_admin)):
    try:
        result = test_tautulli_settings(updates=req.updates, clear_keys=req.clear_keys)
    except SettingsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Tautulli test failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tautulli test failed: {exc}") from exc

    return {
        "requested_by": admin_user["username"],
        **result,
    }


@router.post("/admin/settings/test/ollama")
def admin_test_ollama(req: SettingsTestRequest, admin_user=Depends(require_admin)):
    try:
        result = test_ollama_settings(updates=req.updates, clear_keys=req.clear_keys)
    except SettingsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Ollama test failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ollama test failed: {exc}") from exc

    return {
        "requested_by": admin_user["username"],
        **result,
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
