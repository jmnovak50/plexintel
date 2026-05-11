from __future__ import annotations

from html import escape, unescape
from typing import Any, Callable, Optional

from api.services.poster_service import build_public_poster_url


def _display_title(title: str | None, rating_key: int) -> str:
    safe_title = unescape(title or "").strip()
    return safe_title or f"rating_key {rating_key}"


def _markdown_alt_text(title: str) -> str:
    return f"Poster for {title}".replace("\\", "\\\\").replace("]", "\\]")


def build_poster_markup_payload(
    rating_key: int,
    *,
    title: str | None = None,
    media_type: str | None = None,
    width: int = 180,
    url_builder: Callable[..., str | None] = build_public_poster_url,
) -> dict[str, Any]:
    display_title = _display_title(title, rating_key)
    poster_url = url_builder(rating_key, width=width)
    escaped_url = escape(poster_url or "", quote=True)
    escaped_title = escape(display_title, quote=True)

    return {
        "title": display_title,
        "rating_key": rating_key,
        "media_type": media_type,
        "poster_url": poster_url,
        "image_url": poster_url,
        "url": poster_url,
        "markdown": f"![{_markdown_alt_text(display_title)}]({poster_url})",
        "html": (
            f"<img src=\"{escaped_url}\" alt=\"Poster for {escaped_title}\" "
            f"width=\"{width}\" />"
        ),
    }


def coerce_gallery_entries(
    rating_keys: Optional[list[int]] = None,
    items: Optional[list[dict[str, Any]]] = None,
    *,
    max_items: int = 50,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for item in items or []:
        if not isinstance(item, dict):
            continue
        rating_key = item.get("rating_key")
        if rating_key is None:
            rating_key = item.get("ratingKey")
        if rating_key is None:
            continue
        try:
            normalized_rating_key = int(rating_key)
        except (TypeError, ValueError):
            continue
        title = item.get("title") or item.get("name")
        media_type = item.get("media_type") or item.get("mediaType")
        entries.append(
            {
                "rating_key": normalized_rating_key,
                "title": str(title) if title else None,
                "media_type": str(media_type) if media_type else None,
            }
        )

    for rating_key in rating_keys or []:
        try:
            normalized_rating_key = int(rating_key)
        except (TypeError, ValueError):
            continue
        if any(entry["rating_key"] == normalized_rating_key for entry in entries):
            continue
        entries.append({"rating_key": normalized_rating_key, "title": None, "media_type": None})

    return entries[:max_items]


def build_poster_gallery_payload(
    entries: list[dict[str, Any]],
    *,
    width: int = 180,
    url_builder: Callable[..., str | None] = build_public_poster_url,
) -> dict[str, Any]:
    poster_items = [
        build_poster_markup_payload(
            entry["rating_key"],
            title=entry.get("title"),
            media_type=entry.get("media_type"),
            width=width,
            url_builder=url_builder,
        )
        for entry in entries
    ]

    markdown = "\n\n".join(
        f"### {item['title']}\n{item['markdown']}" for item in poster_items
    )

    return {
        "count": len(poster_items),
        "items": poster_items,
        "markdown": markdown,
    }
