from typing import Optional

from fastapi import HTTPException

DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 250
RECOMMENDATION_VIEWS = {"all", "movies", "shows", "seasons", "episodes"}
MEDIA_TYPE_VIEW_ALIASES = {
    "movie": "movies",
    "movies": "movies",
    "episode": "episodes",
    "episodes": "episodes",
    "show": "shows",
    "shows": "shows",
    "series": "shows",
    "season": "seasons",
    "seasons": "seasons",
}
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

# Combined embedding layout: media-side dimensions occupy 0-767 and
# user-preference dimensions occupy 768-1535.
TITLE_TRAIT_DIMENSION_PREDICATE = "si.dimension >= 0 AND si.dimension < 768"
TASTE_MATCH_DIMENSION_PREDICATE = "si.dimension >= 768 AND si.dimension < 1536"
EXPLANATION_LABEL_LIMIT = 3


def _positive_label_array_sql(
    dimension_predicate: str,
    *,
    rating_key_column: str = "recs.rating_key",
    username_column: str = "recs.username",
    limit: int = EXPLANATION_LABEL_LIMIT,
) -> str:
    """Return a correlated subquery yielding the top positive, explainable SHAP
    labels as ``text[]``.

    Labels are grouped by ``display_label`` and ordered by their max positive
    SHAP value (descending). ``dimension_predicate`` restricts which embedding
    dimensions contribute, letting callers separate media-side title traits from
    user-side taste matches. Missing labels collapse to an empty array rather
    than NULL so downstream consumers always receive an array.
    """
    return f"""(
                SELECT COALESCE(
                    ARRAY_AGG(top_labels.display_label ORDER BY top_labels.max_shap DESC),
                    ARRAY[]::text[]
                )
                FROM (
                    SELECT el.display_label, MAX(si.shap_value) AS max_shap
                    FROM public.shap_impact si
                    JOIN public.embedding_labels el ON si.dimension = el.dimension
                    WHERE si.rating_key = {rating_key_column}
                      AND si.user_id = {username_column}
                      AND si.shap_value > 0
                      AND el.explainable IS TRUE
                      AND el.display_label IS NOT NULL
                      AND BTRIM(el.display_label) <> ''
                      AND {dimension_predicate}
                    GROUP BY el.display_label
                    ORDER BY MAX(si.shap_value) DESC
                    LIMIT {int(limit)}
                ) top_labels
            )"""


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


def normalize_recommendation_view(view: Optional[str]) -> str:
    view_key = (view or "all").strip().lower()
    if view_key not in RECOMMENDATION_VIEWS:
        raise HTTPException(status_code=400, detail=f"Unsupported view: {view}")
    return view_key


def resolve_recommendation_view(
    *,
    view: Optional[str] = None,
    media_type: Optional[str] = None,
) -> str:
    if isinstance(view, str) and view.strip():
        return normalize_recommendation_view(view)
    media_type_key = (media_type or "").strip().lower()
    return MEDIA_TYPE_VIEW_ALIASES.get(media_type_key, "all")


def is_media_type_view_alias(media_type: Optional[str]) -> bool:
    media_type_key = (media_type or "").strip().lower()
    return media_type_key in MEDIA_TYPE_VIEW_ALIASES


def _append_score_filters(
    sql: str,
    params: list,
    column: str,
    score_min: Optional[float],
    score_max: Optional[float],
) -> str:
    if score_min is not None:
        sql += f" AND {column} >= %s"
        params.append(score_min)
    if score_max is not None:
        sql += f" AND {column} <= %s"
        params.append(score_max)
    return sql


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


def _build_recommendations_query(
    *,
    username: str,
    view: str,
    show_rating_key: Optional[int],
    season_rating_key: Optional[int],
    search: Optional[str],
    sort: Optional[list[str]],
    display_threshold: float,
    score_min: Optional[float] = None,
    score_max: Optional[float] = None,
    media_type_filter: Optional[str] = None,
) -> tuple[str, list]:
    view_key = normalize_recommendation_view(view)

    show_rating_key = show_rating_key if isinstance(show_rating_key, int) else None
    season_rating_key = season_rating_key if isinstance(season_rating_key, int) else None
    search = search if isinstance(search, str) else None
    sort = sort if isinstance(sort, list) else None
    media_type_filter = media_type_filter if isinstance(media_type_filter, str) else None

    if view_key == "shows":
        sql = _feedback_rollup_cte("show_rating_key", "group_rating_key") + """
            SELECT
                sr.friendly_name,
                sr.show_rating_key AS rating_key,
                sr.show_title AS title,
                vr.visible_rollup_score AS predicted_probability,
                NULL::text AS semantic_themes,
                ARRAY[]::text[] AS title_traits,
                ARRAY[]::text[] AS taste_match,
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
                NULL::text AS actors,
                NULL::text AS directors,
                NULL::text AS summary,
                NULL::int AS duration,
                NULL::double precision AS rating,
                NULL::timestamp AS added_at,
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
        params = [username, username, display_threshold, username]
        sql = _append_score_filters(sql, params, "vr.visible_rollup_score", score_min, score_max)
        sql = _append_search_filter(sql, params, search, ["sr.show_title", "sr.genres"])
        sql += _build_order_clause(sort)
        return sql, params

    if view_key == "seasons":
        sql = _feedback_rollup_cte("parent_rating_key", "group_rating_key") + """
            SELECT
                sr.friendly_name,
                sr.season_rating_key AS rating_key,
                sr.season_title AS title,
                vr.visible_rollup_score AS predicted_probability,
                NULL::text AS semantic_themes,
                ARRAY[]::text[] AS title_traits,
                ARRAY[]::text[] AS taste_match,
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
                NULL::text AS actors,
                NULL::text AS directors,
                NULL::text AS summary,
                NULL::int AS duration,
                NULL::double precision AS rating,
                NULL::timestamp AS added_at,
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
        params = [username, username, display_threshold, username]
        if show_rating_key is not None:
            sql += " AND sr.show_rating_key = %s"
            params.append(show_rating_key)
        sql = _append_score_filters(sql, params, "vr.visible_rollup_score", score_min, score_max)
        sql = _append_search_filter(sql, params, search, ["sr.season_title", "sr.show_title", "sr.genres"])
        sql += _build_order_clause(sort)
        return sql, params

    title_traits_sql = _positive_label_array_sql(TITLE_TRAIT_DIMENSION_PREDICATE)
    taste_match_sql = _positive_label_array_sql(TASTE_MATCH_DIMENSION_PREDICATE)
    sql = f"""
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
            {title_traits_sql} AS title_traits,
            {taste_match_sql} AS taste_match,
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
            recs.actors,
            recs.directors,
            recs.summary,
            recs.duration,
            recs.rating,
            recs.added_at,
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
    params = [username, username, display_threshold]
    if view_key == "movies":
        sql += " AND recs.media_type = 'movie'"
    elif view_key == "episodes":
        sql += " AND recs.media_type = 'episode'"
    elif media_type_filter:
        sql += " AND recs.media_type ILIKE %s"
        params.append(media_type_filter)
    else:
        sql += " AND recs.media_type IN ('movie', 'episode')"

    if show_rating_key is not None:
        sql += " AND recs.show_rating_key = %s"
        params.append(show_rating_key)
    if season_rating_key is not None:
        sql += " AND recs.parent_rating_key = %s"
        params.append(season_rating_key)

    sql = _append_score_filters(sql, params, "recs.predicted_probability", score_min, score_max)
    sql = _append_search_filter(
        sql,
        params,
        search,
        ["recs.title", "recs.show_title", "recs.genres", "recs.semantic_themes"],
    )
    sql += _build_order_clause(sort)
    return sql, params
