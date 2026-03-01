from collections.abc import Sequence
from datetime import datetime

from fastapi import HTTPException


SHOW_MEDIA_TYPES = {"show", "series", "tv_show"}


def normalize_thumb(value: str, field_name: str = "feedback") -> str:
    thumb = (value or "").strip().lower()
    if thumb not in {"up", "down"}:
        raise HTTPException(status_code=400, detail=f"{field_name} must be 'up' or 'down'")
    return thumb


def seed_thumb_reasons(cur) -> None:
    seed_reasons = [
        ("thumb_up", "Thumbs up", "up", True),
        ("thumb_down", "Thumbs down", "down", True),
    ]
    for code, label, applies_to, suppress_default in seed_reasons:
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


def replace_feedback_rows(cur, username: str, rating_keys: Sequence[int], thumb: str) -> int:
    normalized_thumb = normalize_thumb(thumb)
    deduped_rating_keys = list(dict.fromkeys(int(key) for key in rating_keys if key is not None))
    if not deduped_rating_keys:
        return 0

    seed_thumb_reasons(cur)

    reason_code = "thumb_up" if normalized_thumb == "up" else "thumb_down"
    cur.execute(
        """
        DELETE FROM public.user_feedback
        WHERE username = %s
          AND rating_key = ANY(%s)
        """,
        (username, deduped_rating_keys),
    )
    cur.execute(
        """
        INSERT INTO public.user_feedback (
            username,
            rating_key,
            feedback,
            reason_code,
            suppress,
            created_at
        )
        SELECT %s, rating_key, %s, %s, %s, %s
        FROM unnest(%s::int[]) AS rating_key
        """,
        (
            username,
            normalized_thumb,
            reason_code,
            True,
            datetime.utcnow(),
            deduped_rating_keys,
        ),
    )
    return len(deduped_rating_keys)


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
