from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, Query, Request
from pgvector.psycopg2 import register_vector
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services.poster_service import (
    build_plex_item_url_from_context,
    build_poster_url,
    get_plex_item_url_context,
)
from api.services.app_settings import get_setting_value
from api.services.recommendation_query_service import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    _append_paging,
    _append_search_filter,
    _build_order_clause,
    _build_recommendations_query,
    _feedback_rollup_cte,
    _page_rows,
)

router = APIRouter()


def _decorate_recommendation_rows(rows: list[dict]) -> None:
    plex_context = get_plex_item_url_context()
    for row in rows:
        row["poster_url"] = build_poster_url(row.get("rating_key"))
        row["plex_item_url"] = build_plex_item_url_from_context(
            row.get("rating_key"),
            web_base_url=plex_context["web_base_url"] or "",
            server_identifier=plex_context["server_identifier"],
        )
        row.pop("poster_path", None)


def get_default_display_threshold() -> float:
    return float(get_setting_value("recommendations.display_threshold", default=0.70))


def get_plex_username(token: str) -> str:
    headers = {
        "Accept": "application/json",
        "X-Plex-Token": token,
    }
    resp = requests.get("https://plex.tv/users/account.json", headers=headers)

    if resp.status_code != 200:
        raise HTTPException(status_code=403, detail="Failed to fetch Plex username")

    try:
        return resp.json()["user"]["username"]
    except Exception:
        print("Failed to parse Plex username response:", resp.text)
        raise HTTPException(status_code=500, detail="Malformed response from Plex")


@router.get("/recommendations")
def get_recommendations(
    request: Request,
    view: str = Query("all"),
    show_rating_key: Optional[int] = Query(None),
    season_rating_key: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(0, ge=0),
    sort: Optional[list[str]] = Query(None),
    min_probability: Optional[float] = Query(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum raw predicted_probability to display. Defaults to recommendations.display_threshold.",
    ),
):
    print("Session:", request.session)

    token = request.session.get("plex_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        plex_username = get_plex_username(token)
        print("Resolved Plex username:", plex_username)
    except Exception as exc:
        print("Error resolving Plex username:", str(exc))
        raise HTTPException(status_code=403, detail="Invalid token")

    try:
        conn = connect_db()
        register_vector(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        min_probability = min_probability if isinstance(min_probability, (int, float)) else None
        display_threshold = get_default_display_threshold() if min_probability is None else min_probability

        sql, params = _build_recommendations_query(
            username=plex_username,
            view=view,
            show_rating_key=show_rating_key,
            season_rating_key=season_rating_key,
            search=search,
            sort=sort,
            display_threshold=display_threshold,
        )

        sql = _append_paging(sql, params, limit=limit, offset=offset)
        cur.execute(sql, tuple(params))
        fetched_rows = cur.fetchall()
        rec_rows, has_more, next_offset = _page_rows(fetched_rows, limit=limit, offset=offset)
        _decorate_recommendation_rows(rec_rows)

        print(f"Found {len(rec_rows)} recs for {plex_username}")

        cur.execute(
            """
            WITH latest_feedback AS (
                SELECT DISTINCT ON (rating_key)
                    rating_key
                FROM public.user_feedback
                WHERE username = %s
                ORDER BY rating_key, COALESCE(modified_at, created_at, now()) DESC, id DESC
            )
            SELECT rating_key
            FROM latest_feedback
            """,
            (plex_username,),
        )
        feedback_keys = [row["rating_key"] for row in cur.fetchall()]

        return {
            "username": plex_username,
            "recommendations": rec_rows,
            "last_updated": rec_rows[0]["scored_at"] if rec_rows else None,
            "feedback_keys": feedback_keys,
            "display_threshold": display_threshold,
            "has_more": has_more,
            "next_offset": next_offset,
            "limit": limit,
            "offset": offset,
            "threshold_note": "Raw predicted_probability values are stored unchanged; this threshold only filters display results.",
        }

    except HTTPException:
        raise
    except Exception as exc:
        import traceback

        print("Database error:", repr(exc))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(exc)}")

    finally:
        if "cur" in locals() and not cur.closed:
            cur.close()
        if "conn" in locals() and not conn.closed:
            conn.close()
