import os
from typing import Optional

import psycopg2
import requests
from fastapi import APIRouter, HTTPException, Query, Request
from pgvector.psycopg2 import register_vector
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services.poster_service import build_poster_url
from api.services.app_settings import get_setting_value

router = APIRouter()


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


def _feedback_rollup_cte(group_column: str, group_alias: str) -> str:
    return f"""
        WITH latest_feedback AS (
            SELECT DISTINCT ON (rating_key)
                rating_key,
                feedback,
                suppress,
                reason_code,
                plex_watchlist_status
            FROM public.user_feedback
            WHERE username = %s
            ORDER BY rating_key, COALESCE(modified_at, created_at, now()) DESC, id DESC
        ),
        descendant_feedback AS (
            SELECT
                l.{group_column} AS {group_alias},
                COUNT(*)::int AS descendant_episode_count,
                COUNT(f.rating_key)::int AS descendant_feedback_total_count,
                COUNT(*) FILTER (
                    WHERE f.feedback IN ('interested', 'watched_like')
                )::int AS descendant_feedback_up_count,
                COUNT(*) FILTER (
                    WHERE f.feedback IN ('never_watch', 'watched_dislike')
                )::int AS descendant_feedback_down_count,
                COUNT(*) FILTER (WHERE f.feedback = 'interested')::int AS descendant_interested_count,
                COUNT(*) FILTER (WHERE f.feedback = 'never_watch')::int AS descendant_never_watch_count,
                COUNT(*) FILTER (WHERE f.feedback = 'watched_like')::int AS descendant_watched_like_count,
                COUNT(*) FILTER (WHERE f.feedback = 'watched_dislike')::int AS descendant_watched_dislike_count
            FROM public.library l
            LEFT JOIN latest_feedback f ON f.rating_key = l.rating_key
            WHERE l.media_type = 'episode'
              AND l.{group_column} IS NOT NULL
            GROUP BY l.{group_column}
        )
    """


@router.get("/recommendations")
def get_recommendations(
    request: Request,
    view: str = Query("all"),
    show_rating_key: Optional[int] = Query(None),
    season_rating_key: Optional[int] = Query(None),
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

        view_key = (view or "all").lower()
        if view_key not in {"all", "movies", "shows", "seasons", "episodes"}:
            raise HTTPException(status_code=400, detail=f"Unsupported view: {view}")

        display_threshold = get_default_display_threshold() if min_probability is None else min_probability

        if view_key == "shows":
            sql = _feedback_rollup_cte("show_rating_key", "group_rating_key") + """
                SELECT
                    sr.friendly_name,
                    sr.show_rating_key AS rating_key,
                    sr.show_title AS title,
                    sr.rollup_score AS predicted_probability,
                    NULL::text AS semantic_themes,
                    sr.year,
                    sr.genres,
                    sr.show_title,
                    NULL::int AS season_number,
                    NULL::int AS episode_number,
                    'show'::text AS media_type,
                    sr.scored_at,
                    sr.score_band,
                    sr.show_rating_key,
                    NULL::int AS parent_rating_key,
                    sr.poster_path,
                    COALESCE(df.descendant_episode_count, 0) AS descendant_episode_count,
                    COALESCE(df.descendant_feedback_up_count, 0) AS descendant_feedback_up_count,
                    COALESCE(df.descendant_feedback_down_count, 0) AS descendant_feedback_down_count,
                    COALESCE(df.descendant_feedback_total_count, 0) AS descendant_feedback_total_count,
                    COALESCE(df.descendant_interested_count, 0) AS descendant_interested_count,
                    COALESCE(df.descendant_never_watch_count, 0) AS descendant_never_watch_count,
                    COALESCE(df.descendant_watched_like_count, 0) AS descendant_watched_like_count,
                    COALESCE(df.descendant_watched_dislike_count, 0) AS descendant_watched_dislike_count,
                    NULL::text AS feedback_state,
                    FALSE AS feedback_suppress,
                    NULL::text AS feedback_reason_code,
                    'not_applicable'::text AS plex_watchlist_status
                FROM show_rollups_v sr
                LEFT JOIN descendant_feedback df ON df.group_rating_key = sr.show_rating_key
                WHERE sr.username = %s
                  AND sr.rollup_score >= %s
                  AND COALESCE(df.descendant_episode_count, 0) > COALESCE(df.descendant_feedback_total_count, 0)
                ORDER BY sr.rollup_score DESC
            """
            params = [plex_username, plex_username, display_threshold]
        elif view_key == "seasons":
            sql = _feedback_rollup_cte("parent_rating_key", "group_rating_key") + """
                SELECT
                    sr.friendly_name,
                    sr.season_rating_key AS rating_key,
                    sr.season_title AS title,
                    sr.rollup_score AS predicted_probability,
                    NULL::text AS semantic_themes,
                    sr.year,
                    sr.genres,
                    sr.show_title,
                    sr.season_number,
                    NULL::int AS episode_number,
                    'season'::text AS media_type,
                    sr.scored_at,
                    sr.score_band,
                    sr.show_rating_key,
                    sr.show_rating_key AS parent_rating_key,
                    sr.poster_path,
                    COALESCE(df.descendant_episode_count, 0) AS descendant_episode_count,
                    COALESCE(df.descendant_feedback_up_count, 0) AS descendant_feedback_up_count,
                    COALESCE(df.descendant_feedback_down_count, 0) AS descendant_feedback_down_count,
                    COALESCE(df.descendant_feedback_total_count, 0) AS descendant_feedback_total_count,
                    COALESCE(df.descendant_interested_count, 0) AS descendant_interested_count,
                    COALESCE(df.descendant_never_watch_count, 0) AS descendant_never_watch_count,
                    COALESCE(df.descendant_watched_like_count, 0) AS descendant_watched_like_count,
                    COALESCE(df.descendant_watched_dislike_count, 0) AS descendant_watched_dislike_count,
                    NULL::text AS feedback_state,
                    FALSE AS feedback_suppress,
                    NULL::text AS feedback_reason_code,
                    'not_applicable'::text AS plex_watchlist_status
                FROM season_rollups_v sr
                LEFT JOIN descendant_feedback df ON df.group_rating_key = sr.season_rating_key
                WHERE sr.username = %s
                  AND sr.rollup_score >= %s
                  AND COALESCE(df.descendant_episode_count, 0) > COALESCE(df.descendant_feedback_total_count, 0)
            """
            params = [plex_username, plex_username, display_threshold]
            if show_rating_key is not None:
                sql += " AND sr.show_rating_key = %s"
                params.append(show_rating_key)
            sql += " ORDER BY sr.rollup_score DESC"
        else:
            sql = """
                WITH latest_feedback AS (
                    SELECT DISTINCT ON (rating_key)
                        rating_key,
                        feedback,
                        suppress,
                        reason_code,
                        plex_watchlist_status
                    FROM public.user_feedback
                    WHERE username = %s
                    ORDER BY rating_key, COALESCE(modified_at, created_at, now()) DESC, id DESC
                )
                SELECT
                    recs.friendly_name,
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
                    recs.parent_rating_key,
                    recs.poster_path,
                    NULL::int AS descendant_episode_count,
                    NULL::int AS descendant_feedback_up_count,
                    NULL::int AS descendant_feedback_down_count,
                    NULL::int AS descendant_feedback_total_count,
                    NULL::int AS descendant_interested_count,
                    NULL::int AS descendant_never_watch_count,
                    NULL::int AS descendant_watched_like_count,
                    NULL::int AS descendant_watched_dislike_count,
                    lf.feedback AS feedback_state,
                    CASE
                        WHEN lf.feedback = 'interested' THEN TRUE
                        ELSE COALESCE(lf.suppress, FALSE)
                    END AS feedback_suppress,
                    lf.reason_code AS feedback_reason_code,
                    lf.plex_watchlist_status
                FROM expanded_recs_w_label_v recs
                LEFT JOIN latest_feedback lf ON lf.rating_key = recs.rating_key
                WHERE recs.username = %s
                  AND recs.predicted_probability >= %s
                  AND CASE
                      WHEN lf.feedback = 'interested' THEN TRUE
                      ELSE COALESCE(lf.suppress, FALSE)
                  END = FALSE
            """
            params = [plex_username, plex_username, display_threshold]
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

            sql += " ORDER BY recs.predicted_probability DESC"

        cur.execute(sql, tuple(params))
        rec_rows = cur.fetchall()
        for row in rec_rows:
            row["poster_url"] = build_poster_url(row.get("rating_key"))
            row.pop("poster_path", None)

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
