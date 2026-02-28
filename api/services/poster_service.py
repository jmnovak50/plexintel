from typing import Mapping, Optional, Any


def _normalize_path(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip()
    return normalized or None


def resolve_poster_path(
    media_type: Optional[str],
    thumb_path: Optional[str],
    parent_thumb_path: Optional[str],
    grandparent_thumb_path: Optional[str],
) -> Optional[str]:
    media_type_key = (media_type or "").strip().lower()

    thumb = _normalize_path(thumb_path)
    parent_thumb = _normalize_path(parent_thumb_path)
    grandparent_thumb = _normalize_path(grandparent_thumb_path)

    if media_type_key in {"movie", "show", "series"}:
        return thumb

    if media_type_key == "season":
        return thumb or parent_thumb

    if media_type_key == "episode":
        return parent_thumb or grandparent_thumb or thumb

    return thumb or parent_thumb or grandparent_thumb


def resolve_poster_path_from_row(row: Mapping[str, Any]) -> Optional[str]:
    return resolve_poster_path(
        media_type=row.get("media_type"),
        thumb_path=row.get("thumb_path"),
        parent_thumb_path=row.get("parent_thumb_path"),
        grandparent_thumb_path=row.get("grandparent_thumb_path"),
    )


def build_poster_url(rating_key: Any) -> Optional[str]:
    if rating_key is None:
        return None
    return f"/api/posters/{rating_key}"
