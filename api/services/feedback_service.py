from collections.abc import Sequence
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from api.services.library_service import ensure_library_guid, load_library_item
from api.services.plex_service import add_to_plex_watchlist, remove_from_plex_watchlist


SHOW_MEDIA_TYPES = {"show", "series", "tv_show"}
LEAF_MEDIA_TYPES = {"movie", "episode"}
CANONICAL_FEEDBACK_ACTIONS = {
    "interested",
    "never_watch",
    "watched_like",
    "watched_dislike",
}
BULK_FEEDBACK_ACTIONS = {
    "interested",
    "never_watch",
}
PROTECTED_BULK_FEEDBACK_ACTIONS = {
    "watched_like",
    "watched_dislike",
}
LEGACY_FEEDBACK_ALIASES = {
    "up": "interested",
    "down": "never_watch",
}
FEEDBACK_REASON_SEEDS = (
    ("interested", "Want to watch", "interested", False),
    ("never_watch", "Never watch", "never_watch", True),
    ("watched_like", "Watched, liked", "watched_like", True),
    ("watched_dislike", "Watched, disliked", "watched_dislike", True),
)


def normalize_feedback_action(value: str, field_name: str = "feedback") -> str:
    normalized_value = (value or "").strip().lower()
    normalized_value = LEGACY_FEEDBACK_ALIASES.get(normalized_value, normalized_value)
    if normalized_value not in CANONICAL_FEEDBACK_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{field_name} must be one of "
                "'interested', 'never_watch', 'watched_like', 'watched_dislike'"
            ),
        )
    return normalized_value


def normalize_bulk_feedback_action(value: str, field_name: str = "feedback") -> str:
    normalized_value = normalize_feedback_action(value, field_name=field_name)
    if normalized_value not in BULK_FEEDBACK_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be 'interested' or 'never_watch' for bulk feedback",
        )
    return normalized_value


def action_label(action: Optional[str]) -> str:
    normalized_action = (action or "").strip().lower()
    return {
        "interested": "Want to watch",
        "never_watch": "Never watch",
        "watched_like": "Watched, liked",
        "watched_dislike": "Watched, disliked",
    }.get(normalized_action, normalized_action or "Unknown")


def seed_feedback_reasons(cur) -> None:
    for code, label, applies_to, suppress_default in FEEDBACK_REASON_SEEDS:
        cur.execute(
            """
            INSERT INTO public.feedback_reason (code, label, applies_to, suppress_default)
            SELECT %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM public.feedback_reason WHERE code = %s
            )
            """,
            (code, label, applies_to, suppress_default, code),
        )


def action_defaults(action: str) -> dict:
    normalized_action = normalize_feedback_action(action)
    suppress = True
    watchlist_status = "not_applicable"
    if normalized_action == "interested":
        watchlist_status = "unresolved"

    return {
        "feedback": normalized_action,
        "reason_code": normalized_action,
        "suppress": suppress,
        "plex_watchlist_status": watchlist_status,
    }


def get_latest_feedback(cur, username: str, rating_key: int) -> Optional[dict]:
    cur.execute(
        """
        SELECT
            id,
            username,
            rating_key,
            feedback,
            reason_code,
            suppress,
            created_at,
            source,
            plex_watchlist_status,
            plex_watchlist_synced_at,
            modified_at
        FROM public.user_feedback
        WHERE username = %s
          AND rating_key = %s
        ORDER BY COALESCE(modified_at, created_at, now()) DESC, id DESC
        LIMIT 1
        """,
        (username, rating_key),
    )
    return cur.fetchone()


def _build_feedback_response(
    username: str,
    rating_key: int,
    action: str,
    source: str,
    suppress: bool,
    plex_watchlist_status: str,
    plex_watchlist_synced_at,
    reason_code: Optional[str],
    title: Optional[str],
    media_type: Optional[str],
) -> dict:
    return {
        "username": username,
        "rating_key": rating_key,
        "feedback": action,
        "feedback_label": action_label(action),
        "source": source,
        "suppress": suppress,
        "reason_code": reason_code,
        "plex_watchlist_status": plex_watchlist_status,
        "plex_watchlist_synced_at": plex_watchlist_synced_at,
        "title": title,
        "media_type": media_type,
    }


def _upsert_feedback_row(
    cur,
    username: str,
    rating_key: int,
    action: str,
    *,
    source: str,
    plex_watchlist_status: str,
    plex_watchlist_synced_at,
):
    normalized_action = normalize_feedback_action(action)
    defaults = action_defaults(normalized_action)
    timestamp = datetime.utcnow()

    cur.execute(
        """
        INSERT INTO public.user_feedback (
            username,
            rating_key,
            feedback,
            reason_code,
            suppress,
            created_at,
            source,
            plex_watchlist_status,
            plex_watchlist_synced_at,
            modified_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (username, rating_key)
        DO UPDATE SET
            feedback = EXCLUDED.feedback,
            reason_code = EXCLUDED.reason_code,
            suppress = EXCLUDED.suppress,
            created_at = EXCLUDED.created_at,
            source = EXCLUDED.source,
            plex_watchlist_status = EXCLUDED.plex_watchlist_status,
            plex_watchlist_synced_at = EXCLUDED.plex_watchlist_synced_at,
            modified_at = EXCLUDED.modified_at
        RETURNING
            username,
            rating_key,
            feedback,
            reason_code,
            suppress,
            source,
            plex_watchlist_status,
            plex_watchlist_synced_at
        """,
        (
            username,
            rating_key,
            normalized_action,
            defaults["reason_code"],
            defaults["suppress"],
            timestamp,
            source,
            plex_watchlist_status,
            plex_watchlist_synced_at,
            timestamp,
        ),
    )
    return cur.fetchone()


def record_feedback(
    cur,
    username: str,
    rating_key: int,
    action: str,
    *,
    source: str = "ui",
    plex_token: Optional[str] = None,
) -> dict:
    normalized_action = normalize_feedback_action(action)
    seed_feedback_reasons(cur)

    item = ensure_library_guid(cur, rating_key)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    defaults = action_defaults(normalized_action)
    watchlist_status = defaults["plex_watchlist_status"]
    watchlist_synced_at = None

    if normalized_action == "interested":
        watchlist_result = add_to_plex_watchlist(
            plex_token,
            item.get("plex_guid"),
            item.get("media_type"),
        )
        watchlist_status = watchlist_result["status"]
        watchlist_synced_at = watchlist_result.get("synced_at")

    row = _upsert_feedback_row(
        cur,
        username,
        rating_key,
        normalized_action,
        source=source,
        plex_watchlist_status=watchlist_status,
        plex_watchlist_synced_at=watchlist_synced_at,
    )
    return _build_feedback_response(
        row["username"],
        row["rating_key"],
        row["feedback"],
        row.get("source") or source,
        bool(row["suppress"]),
        row.get("plex_watchlist_status") or "not_applicable",
        row.get("plex_watchlist_synced_at"),
        row.get("reason_code"),
        item.get("title"),
        item.get("media_type"),
    )


def record_bulk_feedback(
    cur,
    username: str,
    rating_key: int,
    action: str,
    *,
    source: str = "bulk",
) -> dict:
    normalized_action = normalize_bulk_feedback_action(action)
    seed_feedback_reasons(cur)
    target = resolve_bulk_target(cur, rating_key)

    cur.execute(
        """
        SELECT DISTINCT ON (rating_key)
            rating_key,
            feedback
        FROM public.user_feedback
        WHERE username = %s
          AND rating_key = ANY(%s)
        ORDER BY rating_key, COALESCE(modified_at, created_at, now()) DESC, id DESC
        """,
        (username, target["descendant_rating_keys"]),
    )
    existing_feedback = {
        row["rating_key"]: row["feedback"]
        for row in cur.fetchall()
    }

    updated_count = 0
    skipped_watched_count = 0
    for descendant_rating_key in target["descendant_rating_keys"]:
        current_feedback = existing_feedback.get(descendant_rating_key)
        if current_feedback in PROTECTED_BULK_FEEDBACK_ACTIONS:
            skipped_watched_count += 1
            continue
        if current_feedback == normalized_action:
            continue

        _upsert_feedback_row(
            cur,
            username,
            descendant_rating_key,
            normalized_action,
            source=source,
            plex_watchlist_status="not_applicable",
            plex_watchlist_synced_at=None,
        )
        updated_count += 1

    return {
        "target_rating_key": target["target_rating_key"],
        "target_media_type": target["target_media_type"],
        "target_title": target["target_title"],
        "feedback": normalized_action,
        "feedback_label": action_label(normalized_action),
        "descendant_total": len(target["descendant_rating_keys"]),
        "updated_count": updated_count,
        "skipped_watched_count": skipped_watched_count,
    }


def replace_feedback_rows(
    cur,
    username: str,
    rating_keys: Sequence[int],
    action: str,
    *,
    source: str = "ui",
    plex_token: Optional[str] = None,
) -> int:
    deduped_rating_keys = list(dict.fromkeys(int(key) for key in rating_keys if key is not None))
    if not deduped_rating_keys:
        return 0

    for rating_key in deduped_rating_keys:
        record_feedback(
            cur,
            username,
            rating_key,
            action,
            source=source,
            plex_token=plex_token,
        )
    return len(deduped_rating_keys)


def delete_feedback_row(
    cur,
    username: str,
    rating_key: int,
    *,
    plex_token: Optional[str] = None,
) -> dict:
    existing = get_latest_feedback(cur, username, rating_key)
    if not existing:
        return {"deleted": False, "watchlist_status": "not_found"}

    item = load_library_item(cur, rating_key)
    watchlist_status = "not_applicable"
    if existing.get("feedback") == "interested":
        watchlist_result = remove_from_plex_watchlist(
            plex_token,
            item.get("plex_guid") if item else None,
            item.get("media_type") if item else None,
        )
        watchlist_status = watchlist_result["status"]

    cur.execute(
        """
        DELETE FROM public.user_feedback
        WHERE username = %s
          AND rating_key = %s
        """,
        (username, rating_key),
    )

    return {
        "deleted": True,
        "watchlist_status": watchlist_status,
        "feedback": existing.get("feedback"),
    }


def resolve_bulk_target(cur, rating_key: int) -> dict:
    cur.execute(
        """
        SELECT rating_key, title, media_type
        FROM public.library
        WHERE rating_key = %s
        """,
        (rating_key,),
    )
    target = cur.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="Item not found")

    media_type = (target.get("media_type") or "").strip().lower()
    if media_type in SHOW_MEDIA_TYPES:
        target_media_type = "show"
        child_sql = """
            SELECT rating_key
            FROM public.library
            WHERE media_type = 'episode'
              AND show_rating_key = %s
            ORDER BY rating_key
        """
    elif media_type == "season":
        target_media_type = "season"
        child_sql = """
            SELECT rating_key
            FROM public.library
            WHERE media_type = 'episode'
              AND parent_rating_key = %s
            ORDER BY rating_key
        """
    else:
        raise HTTPException(status_code=400, detail="Bulk feedback is only supported for shows and seasons")

    cur.execute(child_sql, (rating_key,))
    descendant_rating_keys = [row["rating_key"] for row in cur.fetchall()]
    if not descendant_rating_keys:
        raise HTTPException(status_code=404, detail="No descendant episodes found")

    return {
        "target_rating_key": target["rating_key"],
        "target_media_type": target_media_type,
        "target_title": target.get("title") or "Untitled",
        "descendant_rating_keys": descendant_rating_keys,
    }
