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

router = APIRouter()

DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 250
SORTABLE_COLUMNS = {
    "title",
    "show_title",
    "season_number",
    "episode_number",
    "year",
    "predicted_probability",
    "media_type",
    "score_band",
}


def _normalize_sort(sort: Optional[list[str]]) -> list[tuple[str, str]]:
    normalized: list[tuple[str, str]] = []
    if not isinstance(sort, list):
        return normalized
    for item in sort:
        if not isinstance(item, str):
            continue
        raw_column, separator, raw_direction = item.partition(":")
        column = raw_column.strip()
        direction = raw_direction.strip().lower() if separator else "asc"
        if column not in SORTABLE_COLUMNS:
            continue
        if direction not in {"asc", "desc"}:
            direction = "asc"
        normalized.append((column, direction))
    return normalized[:3]


def _build_order_clause(sort: Optional[list[str]], default_column: str = "predicted_probability") -> str:
    normalized_sort = _normalize_sort(sort)
    sort_parts = [
        f"{column} {direction.upper()} NULLS LAST"
        for column, direction in normalized_sort
    ]
    if default_column not in [column for column, _direction in normalized_sort]:
        sort_parts.append(f"{default_column} DESC NULLS LAST")
    sort_parts.append("rating_key ASC")
    return " ORDER BY " + ", ".join(sort_parts)


def _escape_like(value: str) -> str:
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _append_search_filter(
    sql: str,
    params: list,
    search: Optional[str],
    columns: list[str],
) -> str:
    if not isinstance(search, str):
        return sql
    normalized = search.strip()
    if not normalized:
        return sql
    pattern = f"%{_escape_like(normalized)}%"
    sql += " AND (" + " OR ".join([f"{column} ILIKE %s ESCAPE E'\\\\'" for column in columns]) + ")"
    params.extend([pattern] * len(columns))
    return sql


def _append_paging(sql: str, params: list, *, limit: int, offset: int) -> str:
    params.extend([limit + 1, offset])
    return sql + " LIMIT %s OFFSET %s"


def _page_rows(rows: list[dict], *, limit: int, offset: int) -> tuple[list[dict], bool, Optional[int]]:
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    next_offset = offset + limit if has_more else None
    return page_rows, has_more, next_offset


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
                    WHERE COALESCE(f.suppress, FALSE) = TRUE
                )::int AS descendant_feedback_suppress_count,
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
        ),
        visible_recommendation_descendants AS (
            SELECT
                recs.rating_key,
                recs.username,
                recs.predicted_probability,
                recs.scored_at,
                recs.show_rating_key,
                recs.parent_rating_key,
                recs.{group_column} AS {group_alias},
                ROW_NUMBER() OVER (
                    PARTITION BY recs.username, recs.{group_column}
                    ORDER BY recs.predicted_probability DESC
                ) AS visible_rank,
                (COUNT(*) OVER (
                    PARTITION BY recs.username, recs.{group_column}
                ))::int AS visible_episode_count,
                MAX(recs.scored_at) OVER (
                    PARTITION BY recs.username, recs.{group_column}
                ) AS visible_last_scored_at
            FROM public.expanded_recs_w_label_v recs
            LEFT JOIN latest_feedback lf ON lf.rating_key = recs.rating_key
            WHERE recs.username = %s
              AND recs.media_type = 'episode'
              AND recs.predicted_probability >= %s
              AND recs.{group_column} IS NOT NULL
              AND CASE
                    WHEN lf.feedback = 'interested' THEN FALSE
                    ELSE COALESCE(lf.suppress, FALSE)
                  END = FALSE
        ),
        visible_recommendation_topk AS (
            SELECT
                visible_recommendation_descendants.*,
                GREATEST(
                    1,
                    CEIL(visible_episode_count::double precision * 0.2)::int
                ) AS visible_top_k
            FROM visible_recommendation_descendants
        ),
        visible_recommendation_rollup AS (
            SELECT
                username,
                {group_alias},
                AVG(predicted_probability) FILTER (
                    WHERE visible_rank <= visible_top_k
                ) AS visible_rollup_score,
                MAX(visible_episode_count)::int AS visible_recommendation_episode_count,
                COUNT(DISTINCT parent_rating_key) FILTER (
                    WHERE parent_rating_key IS NOT NULL
                )::int AS visible_recommendation_season_count,
                MAX(visible_top_k)::int AS visible_top_k,
                MAX(visible_last_scored_at) AS visible_scored_at
            FROM visible_recommendation_topk
            GROUP BY username, {group_alias}
        ),
        visible_recommendation_scored AS (
            SELECT
                visible_recommendation_rollup.*,
                PERCENT_RANK() OVER (
                    PARTITION BY username
                    ORDER BY visible_rollup_score
                ) AS visible_score_percentile
            FROM visible_recommendation_rollup
        )
    """


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

        view_key = (view or "all").lower()
        if view_key not in {"all", "movies", "shows", "seasons", "episodes"}:
            raise HTTPException(status_code=400, detail=f"Unsupported view: {view}")

        show_rating_key = show_rating_key if isinstance(show_rating_key, int) else None
        season_rating_key = season_rating_key if isinstance(season_rating_key, int) else None
        search = search if isinstance(search, str) else None
        sort = sort if isinstance(sort, list) else None
        min_probability = min_probability if isinstance(min_probability, (int, float)) else None
        display_threshold = get_default_display_threshold() if min_probability is None else min_probability

        if view_key == "shows":
            sql = _feedback_rollup_cte("show_rating_key", "group_rating_key") + """
                SELECT
                    sr.friendly_name,
                    sr.show_rating_key AS rating_key,
                    sr.show_title AS title,
                    vr.visible_rollup_score AS predicted_probability,
                    NULL::text AS semantic_themes,
                    sr.year,
                    sr.genres,
                    sr.show_title,
                    NULL::int AS season_number,
                    NULL::int AS episode_number,
                    'show'::text AS media_type,
                    vr.visible_scored_at AS scored_at,
                    CASE
                        WHEN vr.visible_score_percentile <= 0.2 THEN '0-20'
                        WHEN vr.visible_score_percentile <= 0.5 THEN '21-50'
                        WHEN vr.visible_score_percentile <= 0.8 THEN '51-80'
                        ELSE '81-100'
                    END AS score_band,
                    sr.show_rating_key,
                    NULL::int AS parent_rating_key,
                    sr.poster_path,
                    COALESCE(df.descendant_episode_count, 0) AS descendant_episode_count,
                    COALESCE(df.descendant_feedback_up_count, 0) AS descendant_feedback_up_count,
                    COALESCE(df.descendant_feedback_down_count, 0) AS descendant_feedback_down_count,
                    COALESCE(df.descendant_feedback_total_count, 0) AS descendant_feedback_total_count,
                    COALESCE(df.descendant_feedback_suppress_count, 0) AS descendant_feedback_suppress_count,
                    COALESCE(df.descendant_interested_count, 0) AS descendant_interested_count,
                    COALESCE(df.descendant_never_watch_count, 0) AS descendant_never_watch_count,
                    COALESCE(df.descendant_watched_like_count, 0) AS descendant_watched_like_count,
                    COALESCE(df.descendant_watched_dislike_count, 0) AS descendant_watched_dislike_count,
                    COALESCE(vr.visible_recommendation_episode_count, 0) AS visible_recommendation_episode_count,
                    COALESCE(vr.visible_recommendation_season_count, 0) AS visible_recommendation_season_count,
                    NULL::text AS feedback_state,
                    FALSE AS feedback_suppress,
                    NULL::text AS feedback_reason_code,
                    'not_applicable'::text AS plex_watchlist_status
                FROM show_rollups_v sr
                JOIN visible_recommendation_scored vr
                  ON vr.username = sr.username
                 AND vr.group_rating_key = sr.show_rating_key
                LEFT JOIN descendant_feedback df ON df.group_rating_key = sr.show_rating_key
                WHERE sr.username = %s
            """
            params = [plex_username, plex_username, display_threshold, plex_username]
            sql = _append_search_filter(sql, params, search, ["sr.show_title", "sr.genres"])
            sql += _build_order_clause(sort)
        elif view_key == "seasons":
            sql = _feedback_rollup_cte("parent_rating_key", "group_rating_key") + """
                SELECT
                    sr.friendly_name,
                    sr.season_rating_key AS rating_key,
                    sr.season_title AS title,
                    vr.visible_rollup_score AS predicted_probability,
                    NULL::text AS semantic_themes,
                    sr.year,
                    sr.genres,
                    sr.show_title,
                    sr.season_number,
                    NULL::int AS episode_number,
                    'season'::text AS media_type,
                    vr.visible_scored_at AS scored_at,
                    CASE
                        WHEN vr.visible_score_percentile <= 0.2 THEN '0-20'
                        WHEN vr.visible_score_percentile <= 0.5 THEN '21-50'
                        WHEN vr.visible_score_percentile <= 0.8 THEN '51-80'
                        ELSE '81-100'
                    END AS score_band,
                    sr.show_rating_key,
                    sr.show_rating_key AS parent_rating_key,
                    sr.poster_path,
                    COALESCE(df.descendant_episode_count, 0) AS descendant_episode_count,
                    COALESCE(df.descendant_feedback_up_count, 0) AS descendant_feedback_up_count,
                    COALESCE(df.descendant_feedback_down_count, 0) AS descendant_feedback_down_count,
                    COALESCE(df.descendant_feedback_total_count, 0) AS descendant_feedback_total_count,
                    COALESCE(df.descendant_feedback_suppress_count, 0) AS descendant_feedback_suppress_count,
                    COALESCE(df.descendant_interested_count, 0) AS descendant_interested_count,
                    COALESCE(df.descendant_never_watch_count, 0) AS descendant_never_watch_count,
                    COALESCE(df.descendant_watched_like_count, 0) AS descendant_watched_like_count,
                    COALESCE(df.descendant_watched_dislike_count, 0) AS descendant_watched_dislike_count,
                    COALESCE(vr.visible_recommendation_episode_count, 0) AS visible_recommendation_episode_count,
                    COALESCE(vr.visible_recommendation_season_count, 0) AS visible_recommendation_season_count,
                    NULL::text AS feedback_state,
                    FALSE AS feedback_suppress,
                    NULL::text AS feedback_reason_code,
                    'not_applicable'::text AS plex_watchlist_status
                FROM season_rollups_v sr
                JOIN visible_recommendation_scored vr
                  ON vr.username = sr.username
                 AND vr.group_rating_key = sr.season_rating_key
                LEFT JOIN descendant_feedback df ON df.group_rating_key = sr.season_rating_key
                WHERE sr.username = %s
            """
            params = [plex_username, plex_username, display_threshold, plex_username]
            if show_rating_key is not None:
                sql += " AND sr.show_rating_key = %s"
                params.append(show_rating_key)
            sql = _append_search_filter(sql, params, search, ["sr.season_title", "sr.show_title", "sr.genres"])
            sql += _build_order_clause(sort)
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
                    NULL::int AS descendant_feedback_suppress_count,
                    NULL::int AS descendant_interested_count,
                    NULL::int AS descendant_never_watch_count,
                    NULL::int AS descendant_watched_like_count,
                    NULL::int AS descendant_watched_dislike_count,
                    NULL::int AS visible_recommendation_episode_count,
                    NULL::int AS visible_recommendation_season_count,
                    lf.feedback AS feedback_state,
                    CASE
                        WHEN lf.feedback = 'interested' THEN FALSE
                        ELSE COALESCE(lf.suppress, FALSE)
                    END AS feedback_suppress,
                    lf.reason_code AS feedback_reason_code,
                    lf.plex_watchlist_status
                FROM expanded_recs_w_label_v recs
                LEFT JOIN latest_feedback lf ON lf.rating_key = recs.rating_key
                WHERE recs.username = %s
                  AND recs.predicted_probability >= %s
                  AND CASE
                      WHEN lf.feedback = 'interested' THEN FALSE
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
