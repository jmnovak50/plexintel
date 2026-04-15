from __future__ import annotations

import secrets
import smtplib
import ssl
from datetime import datetime, time as time_of_day, timedelta
from email.message import EmailMessage
from email.utils import make_msgid
from html import escape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from psycopg2 import IntegrityError
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services.app_settings import get_setting_value
from api.services.poster_service import build_poster_url, fetch_poster_image_for_rating_key
from api.services.user_sync_service import sync_users_from_tautulli


WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

ALLOWED_HTML_TAGS = {
    "p",
    "div",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "s",
    "strike",
    "del",
    "ul",
    "ol",
    "li",
    "a",
    "img",
    "blockquote",
}
VOID_TAGS = {"br", "img"}
SKIP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed"}
ALLOWED_HTML_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
}
URL_ATTRIBUTES = {"href", "src"}


class DigestConfigError(ValueError):
    pass


class HtmlSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in SKIP_CONTENT_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0 or normalized_tag not in ALLOWED_HTML_TAGS:
            return

        rendered_attrs: list[str] = []
        for attr_name, raw_value in attrs:
            if attr_name not in ALLOWED_HTML_ATTRIBUTES.get(normalized_tag, set()):
                continue
            value = (raw_value or "").strip()
            if not value:
                continue
            if attr_name in URL_ATTRIBUTES and not _is_safe_external_url(value):
                continue
            rendered_attrs.append(f' {attr_name}="{escape(value, quote=True)}"')

        self._parts.append(f"<{normalized_tag}{''.join(rendered_attrs)}>")

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in SKIP_CONTENT_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth > 0 or normalized_tag not in ALLOWED_HTML_TAGS or normalized_tag in VOID_TAGS:
            return
        self._parts.append(f"</{normalized_tag}>")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        self._parts.append(escape(data))

    def get_html(self) -> str:
        return "".join(self._parts).strip()


class HtmlToTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._list_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "br":
            self._parts.append("\n")
        elif normalized_tag in {"p", "div", "blockquote"}:
            self._parts.append("\n")
        elif normalized_tag in {"ul", "ol"}:
            self._parts.append("\n")
            self._list_depth += 1
        elif normalized_tag == "li":
            indent = "  " * max(self._list_depth - 1, 0)
            self._parts.append(f"\n{indent}- ")

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag in {"p", "div", "blockquote"}:
            self._parts.append("\n")
        elif normalized_tag in {"ul", "ol"} and self._list_depth > 0:
            self._list_depth -= 1
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        joined = "".join(self._parts)
        collapsed_lines = [line.rstrip() for line in joined.splitlines()]
        cleaned_lines: list[str] = []
        previous_blank = False
        for line in collapsed_lines:
            blank = not line.strip()
            if blank and previous_blank:
                continue
            cleaned_lines.append(line)
            previous_blank = blank
        return "\n".join(cleaned_lines).strip()


def _is_safe_external_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def sanitize_rich_html(raw_html: str | None) -> str:
    parser = HtmlSanitizer()
    parser.feed(raw_html or "")
    parser.close()
    return parser.get_html()


def html_to_plain_text(raw_html: str | None) -> str:
    parser = HtmlToTextParser()
    parser.feed(raw_html or "")
    parser.close()
    return parser.get_text()


def _build_display_name(username: str | None, friendly_name: str | None) -> str:
    normalized_username = (username or "").strip()
    normalized_friendly_name = (friendly_name or "").strip()
    if normalized_friendly_name and normalized_username:
        return f"{normalized_friendly_name} ({normalized_username})"
    if normalized_friendly_name:
        return normalized_friendly_name
    return normalized_username or "Plex user"


def _fetch_digest_user(conn, *, username: str | None = None, user_id: int | None = None) -> dict[str, Any] | None:
    if username is None and user_id is None:
        raise ValueError("username or user_id is required")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if username is not None:
            cur.execute(
                """
                SELECT user_id, username, friendly_name, plex_email, is_admin, modified_at
                FROM public.users
                WHERE username = %s
                """,
                (username,),
            )
        else:
            cur.execute(
                """
                SELECT user_id, username, friendly_name, plex_email, is_admin, modified_at
                FROM public.users
                WHERE user_id = %s
                """,
                (user_id,),
            )
        row = cur.fetchone()
    return row


def _ensure_preference_row(conn, user_id: int) -> dict[str, Any]:
    token = secrets.token_urlsafe(24)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO public.user_email_preferences (user_id, digest_enabled, unsubscribe_token, created_at, updated_at)
            VALUES (%s, TRUE, %s, now(), now())
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, token),
        )
        cur.execute(
            """
            SELECT user_id, digest_enabled, unsubscribe_token, created_at, updated_at
            FROM public.user_email_preferences
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if row and not row.get("unsubscribe_token"):
            refreshed_token = secrets.token_urlsafe(24)
            cur.execute(
                """
                UPDATE public.user_email_preferences
                SET unsubscribe_token = %s, updated_at = now()
                WHERE user_id = %s
                RETURNING user_id, digest_enabled, unsubscribe_token, created_at, updated_at
                """,
                (refreshed_token, user_id),
            )
            row = cur.fetchone()
    conn.commit()
    return row


def get_user_email_preferences(user_id: int) -> dict[str, Any]:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        return _ensure_preference_row(conn, user_id)
    finally:
        conn.close()


def update_user_email_preferences(user_id: int, *, digest_enabled: bool) -> dict[str, Any]:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        _ensure_preference_row(conn, user_id)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE public.user_email_preferences
                SET digest_enabled = %s, updated_at = now()
                WHERE user_id = %s
                RETURNING user_id, digest_enabled, unsubscribe_token, created_at, updated_at
                """,
                (digest_enabled, user_id),
            )
            row = cur.fetchone()
        conn.commit()
        return row
    finally:
        conn.close()


def get_unsubscribe_target(token: str) -> dict[str, Any] | None:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    u.user_id,
                    u.username,
                    u.friendly_name,
                    u.plex_email,
                    p.digest_enabled,
                    p.unsubscribe_token
                FROM public.user_email_preferences p
                JOIN public.users u ON u.user_id = p.user_id
                WHERE p.unsubscribe_token = %s
                """,
                (token,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def unsubscribe_by_token(token: str) -> dict[str, Any] | None:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE public.user_email_preferences
                SET digest_enabled = FALSE, updated_at = now()
                WHERE unsubscribe_token = %s
                RETURNING user_id, digest_enabled, unsubscribe_token
                """,
                (token,),
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return None
        return get_unsubscribe_target(token)
    finally:
        conn.close()


def get_digest_content() -> dict[str, Any]:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT content_id, message_html, updated_at, updated_by
                FROM public.email_digest_content
                WHERE content_id = 1
                """
            )
            row = cur.fetchone()
        if row:
            return row
        return {"content_id": 1, "message_html": "", "updated_at": None, "updated_by": None}
    finally:
        conn.close()


def save_digest_content(message_html: str | None, updated_by: str | None) -> dict[str, Any]:
    sanitized_html = sanitize_rich_html(message_html)
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO public.email_digest_content (content_id, message_html, updated_at, updated_by)
                VALUES (1, %s, now(), %s)
                ON CONFLICT (content_id) DO UPDATE SET
                    message_html = EXCLUDED.message_html,
                    updated_at = EXCLUDED.updated_at,
                    updated_by = EXCLUDED.updated_by
                RETURNING content_id, message_html, updated_at, updated_by
                """,
                (sanitized_html, updated_by),
            )
            row = cur.fetchone()
        conn.commit()
        return row
    finally:
        conn.close()


def _get_digest_settings() -> dict[str, Any]:
    return {
        "enabled": bool(get_setting_value("digest.enabled", default=False)),
        "frequency": get_setting_value("digest.frequency", default="weekly"),
        "weekly_day": get_setting_value("digest.weekly_day", default="monday"),
        "send_time": get_setting_value("digest.send_time", default="09:00"),
        "timezone": get_setting_value("digest.timezone", default="America/Chicago"),
        "top_movies": int(get_setting_value("digest.top_movies", default=25) or 0),
        "top_shows": int(get_setting_value("digest.top_shows", default=10) or 0),
        "base_url": get_setting_value("digest.base_url", default="http://localhost:8489"),
    }


def _get_smtp_settings() -> dict[str, Any]:
    server = get_setting_value("smtp.server")
    port = get_setting_value("smtp.port", default=465)
    from_email = get_setting_value("smtp.from_email")
    from_name = get_setting_value("smtp.from_name", default="PlexIntel")
    encryption = get_setting_value("smtp.encryption", default="ssl_tls")
    username = get_setting_value("smtp.username")
    password = get_setting_value("smtp.password")
    reply_to = get_setting_value("smtp.reply_to")

    if not server:
        raise DigestConfigError("SMTP Server is required")
    if not port:
        raise DigestConfigError("SMTP Port is required")
    if not from_email:
        raise DigestConfigError("From Email is required")
    if encryption not in {"none", "starttls", "ssl_tls"}:
        raise DigestConfigError("Encryption must be None, TLS/STARTTLS, or SSL/TLS")
    if password and not username:
        raise DigestConfigError("SMTP Username is required when SMTP Password is set")

    return {
        "server": server,
        "port": int(port),
        "username": username,
        "password": password,
        "encryption": encryption,
        "from_email": from_email,
        "from_name": from_name or "PlexIntel",
        "reply_to": reply_to,
    }


def _build_subject(*, frequency: str, is_test: bool) -> str:
    label = "Daily Picks" if frequency == "daily" else "Weekly Picks"
    subject = f"PlexIntel {label}"
    if is_test:
        subject = f"[TEST] {subject}"
    return subject


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
                COUNT(f.rating_key)::int AS descendant_feedback_total_count
            FROM public.library l
            LEFT JOIN latest_feedback f ON f.rating_key = l.rating_key
            WHERE l.media_type = 'episode'
              AND l.{group_column} IS NOT NULL
            GROUP BY l.{group_column}
        )
    """


def fetch_top_movie_recommendations(conn, username: str, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            WITH latest_feedback AS (
                SELECT DISTINCT ON (rating_key)
                    rating_key,
                    feedback,
                    suppress
                FROM public.user_feedback
                WHERE username = %s
                ORDER BY rating_key, COALESCE(modified_at, created_at, now()) DESC, id DESC
            )
            SELECT
                recs.rating_key,
                recs.title,
                recs.year,
                recs.genres,
                recs.semantic_themes,
                recs.predicted_probability
            FROM public.expanded_recs_w_label_v recs
            LEFT JOIN latest_feedback lf ON lf.rating_key = recs.rating_key
            WHERE recs.username = %s
              AND recs.media_type = 'movie'
              AND CASE
                    WHEN lf.feedback = 'interested' THEN TRUE
                    ELSE COALESCE(lf.suppress, FALSE)
                  END = FALSE
            ORDER BY recs.predicted_probability DESC
            LIMIT %s
            """,
            (username, username, limit),
        )
        return cur.fetchall()


def fetch_top_show_recommendations(conn, username: str, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    sql = _feedback_rollup_cte("show_rating_key", "group_rating_key") + """
        SELECT
            sr.show_rating_key AS rating_key,
            sr.show_title AS title,
            sr.year,
            sr.genres,
            sr.rollup_score AS predicted_probability
        FROM public.show_rollups_v sr
        LEFT JOIN descendant_feedback df ON df.group_rating_key = sr.show_rating_key
        WHERE sr.username = %s
          AND COALESCE(df.descendant_episode_count, 0) > COALESCE(df.descendant_feedback_total_count, 0)
        ORDER BY sr.rollup_score DESC
        LIMIT %s
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (username, username, limit))
        return cur.fetchall()


def _build_item_subtitle(item: dict[str, Any]) -> str:
    subtitle_parts = [
        str(item["year"]) if item.get("year") is not None else None,
        item.get("genres"),
        item.get("semantic_themes"),
    ]
    return " | ".join(part for part in subtitle_parts if part)


def _decorate_items_with_proxy_posters(items: list[dict[str, Any]]) -> None:
    for item in items:
        item["poster_src"] = build_poster_url(item.get("rating_key"))


def _decorate_items_with_inline_posters(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inline_images: list[dict[str, Any]] = []
    for item in items:
        rating_key = item.get("rating_key")
        if rating_key is None:
            item["poster_src"] = None
            continue
        try:
            payload = fetch_poster_image_for_rating_key(rating_key, allow_unconfigured=True)
        except Exception:
            payload = None
        if not payload:
            item["poster_src"] = None
            continue

        cid = make_msgid()[1:-1]
        item["poster_src"] = f"cid:{cid}"
        inline_images.append(
            {
                "cid": cid,
                "content": payload["content"],
                "content_type": payload["content_type"],
                "filename": f"poster-{rating_key}",
            }
        )
    return inline_images


def _render_item_card(item: dict[str, Any]) -> str:
    score_pct = float(item.get("predicted_probability") or 0) * 100
    title = escape(item.get("title") or "Untitled")
    subtitle = _build_item_subtitle(item)
    poster_src = item.get("poster_src")
    if poster_src:
        poster_html = (
            f"<img src=\"{escape(poster_src, quote=True)}\" alt=\"{title} poster\" width=\"100%\" "
            "style=\"display:block;width:100%;height:auto;aspect-ratio:2 / 3;object-fit:cover;background:#e2e8f0;"
            "border-radius:8px 8px 0 0;\" />"
        )
    else:
        poster_html = (
            "<div style=\"height:168px;background:#e2e8f0;border-radius:8px 8px 0 0;color:#64748b;"
            "font-size:12px;line-height:168px;text-align:center;\">Poster unavailable</div>"
        )

    return (
        "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" "
        "style=\"border:1px solid #e2e8f0;border-radius:8px;background:#ffffff;\">"
        "<tr><td style=\"padding:0;\">"
        f"{poster_html}"
        "</td></tr>"
        "<tr><td style=\"padding:12px;vertical-align:top;\">"
        f"<div style=\"font-size:15px;font-weight:700;line-height:1.35;color:#0f172a;\">{title}</div>"
        f"<div style=\"margin-top:6px;font-size:13px;color:#475569;\">Match score: {score_pct:.1f}%</div>"
        f"{f'<div style=\"margin-top:6px;font-size:12px;line-height:1.45;color:#64748b;\">{escape(subtitle)}</div>' if subtitle else ''}"
        "</td></tr>"
        "</table>"
    )


def _render_item_grid(items: list[dict[str, Any]], kind_label: str) -> str:
    if not items:
        return ""

    rows: list[str] = []
    for index in range(0, len(items), 2):
        left = _render_item_card(items[index])
        right = _render_item_card(items[index + 1]) if index + 1 < len(items) else ""
        rows.append(
            (
                "<tr>"
                f"<td width=\"50%\" valign=\"top\" style=\"padding:0 8px 16px 0;\">{left}</td>"
                f"<td width=\"50%\" valign=\"top\" style=\"padding:0 0 16px 8px;\">{right}</td>"
                "</tr>"
            )
        )

    return (
        f"<h2 style=\"margin:28px 0 12px 0;font-size:18px;color:#0f172a;\">{escape(kind_label)}</h2>"
        "<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" "
        "style=\"border-collapse:collapse;table-layout:fixed;\">"
        f"{''.join(rows)}"
        "</table>"
    )


def _render_digest_html(
    *,
    recipient_user: dict[str, Any],
    rendered_for_user: dict[str, Any],
    preference_row: dict[str, Any],
    message_html: str,
    digest_settings: dict[str, Any],
    movies: list[dict[str, Any]],
    shows: list[dict[str, Any]],
    subject: str,
    is_test: bool,
) -> str:
    base_url = digest_settings["base_url"].rstrip("/")
    recipient_display = _build_display_name(recipient_user.get("username"), recipient_user.get("friendly_name"))
    rendered_display = _build_display_name(rendered_for_user.get("username"), rendered_for_user.get("friendly_name"))
    test_banner = ""
    if is_test:
        test_banner = (
            "<div style=\"margin:0 0 20px 0;padding:12px 16px;border-radius:8px;background:#fff7ed;"
            "border:1px solid #fdba74;color:#9a3412;font-size:14px;\">"
            f"Test email delivered to {escape(recipient_display)} and rendered using the digest for {escape(rendered_display)}."
            "</div>"
        )

    body_blocks = [
        test_banner,
        f"<p style=\"margin:0 0 16px 0;color:#0f172a;font-size:15px;\">Hi {escape(rendered_display)},</p>",
        (
            "<p style=\"margin:0 0 16px 0;color:#475569;font-size:14px;\">"
            "Here are your latest PlexIntel picks.</p>"
        ),
    ]
    if message_html:
        body_blocks.append(
            "<div style=\"margin:0 0 20px 0;padding:16px;border:1px solid #dbeafe;border-radius:8px;background:#eff6ff;\">"
            f"{message_html}"
            "</div>"
        )
    body_blocks.append(_render_item_grid(movies, "Top Movies"))
    body_blocks.append(_render_item_grid(shows, "Top Shows"))
    body_blocks.append(
        (
            f"<p style=\"margin:28px 0 0 0;\">"
            f"<a href=\"{escape(base_url + '/recs', quote=True)}\" "
            "style=\"display:inline-block;border-radius:6px;background:#0f172a;color:#ffffff;padding:10px 14px;"
            "text-decoration:none;font-weight:600;\">Open PlexIntel</a>"
            "</p>"
        )
    )
    body_blocks.append(
        (
            "<p style=\"margin:24px 0 0 0;font-size:12px;color:#64748b;\">"
            f"Prefer not to receive these? "
            f"<a href=\"{escape(base_url + '/digest/unsubscribe/' + preference_row['unsubscribe_token'], quote=True)}\">Unsubscribe</a>."
            "</p>"
        )
    )

    return (
        "<!doctype html>"
        "<html><body style=\"margin:0;padding:24px;background:#f8fafc;font-family:Arial,Helvetica,sans-serif;\">"
        "<div style=\"max-width:680px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;"
        "border-radius:12px;padding:28px;\">"
        f"<h1 style=\"margin:0 0 20px 0;font-size:24px;color:#0f172a;\">{escape(subject)}</h1>"
        f"{''.join(block for block in body_blocks if block)}"
        "</div></body></html>"
    )


def _render_digest_text(
    *,
    recipient_user: dict[str, Any],
    rendered_for_user: dict[str, Any],
    preference_row: dict[str, Any],
    message_html: str,
    digest_settings: dict[str, Any],
    movies: list[dict[str, Any]],
    shows: list[dict[str, Any]],
    subject: str,
    is_test: bool,
) -> str:
    recipient_display = _build_display_name(recipient_user.get("username"), recipient_user.get("friendly_name"))
    rendered_display = _build_display_name(rendered_for_user.get("username"), rendered_for_user.get("friendly_name"))
    lines = [subject, "", f"Hi {rendered_display},", "", "Here are your latest PlexIntel picks.", ""]
    if is_test:
        lines.extend(
            [
                f"Test email delivered to {recipient_display} and rendered using the digest for {rendered_display}.",
                "",
            ]
        )
    if message_html:
        lines.extend([html_to_plain_text(message_html), ""])
    if movies:
        lines.append("Top Movies")
        for item in movies:
            score_pct = float(item.get("predicted_probability") or 0) * 100
            lines.append(f"- {item.get('title') or 'Untitled'} ({score_pct:.1f}%)")
        lines.append("")
    if shows:
        lines.append("Top Shows")
        for item in shows:
            score_pct = float(item.get("predicted_probability") or 0) * 100
            lines.append(f"- {item.get('title') or 'Untitled'} ({score_pct:.1f}%)")
        lines.append("")
    base_url = digest_settings["base_url"].rstrip("/")
    lines.append(f"Open PlexIntel: {base_url}/recs")
    lines.append(f"Unsubscribe: {base_url}/digest/unsubscribe/{preference_row['unsubscribe_token']}")
    return "\n".join(lines).strip()


def _build_preview_payload(
    conn,
    *,
    rendered_for_user: dict[str, Any],
    recipient_user: dict[str, Any],
    message_html: str | None,
    is_test: bool,
    poster_mode: str = "proxy",
) -> dict[str, Any]:
    preference_row = _ensure_preference_row(conn, recipient_user["user_id"])
    digest_settings = _get_digest_settings()
    subject = _build_subject(frequency=digest_settings["frequency"], is_test=is_test)
    sanitized_message_html = sanitize_rich_html(message_html) if message_html is not None else get_digest_content()["message_html"]
    movies = [dict(item) for item in fetch_top_movie_recommendations(conn, rendered_for_user["username"], digest_settings["top_movies"])]
    shows = [dict(item) for item in fetch_top_show_recommendations(conn, rendered_for_user["username"], digest_settings["top_shows"])]
    inline_images: list[dict[str, Any]] = []

    if poster_mode == "cid":
        inline_images.extend(_decorate_items_with_inline_posters(movies))
        inline_images.extend(_decorate_items_with_inline_posters(shows))
    else:
        _decorate_items_with_proxy_posters(movies)
        _decorate_items_with_proxy_posters(shows)

    html = _render_digest_html(
        recipient_user=recipient_user,
        rendered_for_user=rendered_for_user,
        preference_row=preference_row,
        message_html=sanitized_message_html,
        digest_settings=digest_settings,
        movies=movies,
        shows=shows,
        subject=subject,
        is_test=is_test,
    )
    text = _render_digest_text(
        recipient_user=recipient_user,
        rendered_for_user=rendered_for_user,
        preference_row=preference_row,
        message_html=sanitized_message_html,
        digest_settings=digest_settings,
        movies=movies,
        shows=shows,
        subject=subject,
        is_test=is_test,
    )
    return {
        "subject": subject,
        "html": html,
        "text": text,
        "message_html": sanitized_message_html,
        "rendered_for": {
            "username": rendered_for_user["username"],
            "friendly_name": rendered_for_user.get("friendly_name"),
            "display_name": _build_display_name(rendered_for_user.get("username"), rendered_for_user.get("friendly_name")),
        },
        "recipient": {
            "username": recipient_user["username"],
            "friendly_name": recipient_user.get("friendly_name"),
            "display_name": _build_display_name(recipient_user.get("username"), recipient_user.get("friendly_name")),
            "email": recipient_user.get("plex_email"),
        },
        "counts": {"movies": len(movies), "shows": len(shows)},
        "inline_images": inline_images,
    }


def generate_digest_preview(sample_username: str, *, message_html: str | None = None) -> dict[str, Any]:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        rendered_for_user = _fetch_digest_user(conn, username=sample_username)
        if not rendered_for_user:
            raise DigestConfigError(f"Unknown sample user: {sample_username}")
        return _build_preview_payload(
            conn,
            rendered_for_user=rendered_for_user,
            recipient_user=rendered_for_user,
            message_html=message_html,
            is_test=False,
        )
    finally:
        conn.close()


def _decode_smtp_error(error: Any) -> str:
    if isinstance(error, bytes):
        return error.decode("utf-8", errors="replace")
    return str(error or "").strip()


def _describe_smtp_auth_error(exc: smtplib.SMTPAuthenticationError) -> str:
    smtp_error = _decode_smtp_error(getattr(exc, "smtp_error", ""))
    guidance = (
        "SMTP authentication failed. Gmail and Google Workspace accounts usually require an App Password, "
        "SMTP relay, or OAuth. A normal Google account password will be rejected."
    )
    if smtp_error:
        return f"{guidance} Upstream response: {smtp_error}"
    return guidance


def _send_email(
    smtp_settings: dict[str, Any],
    *,
    recipient_email: str,
    subject: str,
    html_body: str,
    text_body: str,
    inline_images: list[dict[str, Any]] | None = None,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{smtp_settings['from_name']} <{smtp_settings['from_email']}>"
    message["To"] = recipient_email
    if smtp_settings.get("reply_to"):
        message["Reply-To"] = smtp_settings["reply_to"]
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    html_part = message.get_payload()[-1]
    for inline_image in inline_images or []:
        content_type = (inline_image.get("content_type") or "image/jpeg").split("/", 1)
        maintype = content_type[0] if len(content_type) == 2 else "image"
        subtype = content_type[1] if len(content_type) == 2 else "jpeg"
        html_part.add_related(
            inline_image["content"],
            maintype=maintype,
            subtype=subtype,
            cid=f"<{inline_image['cid']}>",
            filename=inline_image.get("filename"),
        )

    encryption = smtp_settings["encryption"]
    timeout = 30
    if encryption == "ssl_tls":
        with smtplib.SMTP_SSL(smtp_settings["server"], smtp_settings["port"], context=ssl.create_default_context(), timeout=timeout) as server:
            if smtp_settings.get("username"):
                try:
                    server.login(smtp_settings["username"], smtp_settings.get("password") or "")
                except smtplib.SMTPAuthenticationError as exc:
                    raise DigestConfigError(_describe_smtp_auth_error(exc)) from exc
            server.send_message(message)
        return

    with smtplib.SMTP(smtp_settings["server"], smtp_settings["port"], timeout=timeout) as server:
        if encryption == "starttls":
            server.starttls(context=ssl.create_default_context())
        if smtp_settings.get("username"):
            try:
                server.login(smtp_settings["username"], smtp_settings.get("password") or "")
            except smtplib.SMTPAuthenticationError as exc:
                raise DigestConfigError(_describe_smtp_auth_error(exc)) from exc
        server.send_message(message)


def _record_run_start(
    conn,
    *,
    delivery_type: str,
    schedule_key: str | None,
    triggered_by: str | None,
    sample_username: str | None,
    subject: str,
) -> int | None:
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO public.email_digest_runs (
                    delivery_type,
                    schedule_key,
                    triggered_by,
                    sample_username,
                    subject,
                    status,
                    started_at
                )
                VALUES (%s, %s, %s, %s, %s, 'started', now())
                RETURNING run_id
                """,
                (delivery_type, schedule_key, triggered_by, sample_username, subject),
            )
            row = cur.fetchone()
            conn.commit()
            if not row:
                return None
            return row["run_id"] if isinstance(row, dict) else row[0]
        except IntegrityError:
            conn.rollback()
            return None


def _record_delivery(
    conn,
    *,
    run_id: int,
    delivery_type: str,
    recipient_username: str | None,
    recipient_email: str,
    rendered_for_username: str | None,
    status: str,
    error_message: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.email_digest_deliveries (
                run_id,
                delivery_type,
                recipient_username,
                recipient_email,
                rendered_for_username,
                status,
                error_message,
                sent_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            """,
            (run_id, delivery_type, recipient_username, recipient_email, rendered_for_username, status, error_message),
        )
    conn.commit()


def _finalize_run(
    conn,
    *,
    run_id: int,
    status: str,
    recipient_count: int,
    success_count: int,
    failure_count: int,
    notes: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE public.email_digest_runs
            SET
                status = %s,
                recipient_count = %s,
                success_count = %s,
                failure_count = %s,
                notes = %s,
                completed_at = now()
            WHERE run_id = %s
            """,
            (status, recipient_count, success_count, failure_count, notes, run_id),
        )
    conn.commit()


def _list_admin_users(conn) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT user_id, username, friendly_name, plex_email, is_admin
            FROM public.users
            WHERE is_admin = TRUE
            ORDER BY username ASC
            """
        )
        return cur.fetchall()


def _list_digest_recipients(conn) -> list[dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT user_id, username, friendly_name, plex_email, is_admin
            FROM public.users
            WHERE plex_email IS NOT NULL
              AND BTRIM(plex_email) <> ''
            ORDER BY username ASC
            """
        )
        users = cur.fetchall()

    recipients: list[dict[str, Any]] = []
    for user in users:
        preference_row = _ensure_preference_row(conn, user["user_id"])
        if not preference_row["digest_enabled"]:
            continue
        recipients.append({**user, "preference": preference_row})
    return recipients


def send_test_digest(
    *,
    target: str,
    sample_username: str,
    triggered_by: str,
    message_html: str | None = None,
) -> dict[str, Any]:
    smtp_settings = _get_smtp_settings()
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        sync_note = None
        try:
            sync_users_from_tautulli()
        except Exception as exc:
            sync_note = f"Tautulli sync skipped: {exc}"
        sample_user = _fetch_digest_user(conn, username=sample_username)
        if not sample_user:
            raise DigestConfigError(f"Unknown sample user: {sample_username}")

        if target not in {"self", "all_admins"}:
            raise DigestConfigError("Unsupported test target")

        if target == "self":
            admin_users = [_fetch_digest_user(conn, username=triggered_by)]
        else:
            admin_users = _list_admin_users(conn)

        admin_users = [user for user in admin_users if user]
        with_email: list[dict[str, Any]] = []
        skipped_admins: list[str] = []
        for admin_user in admin_users:
            email = (admin_user.get("plex_email") or "").strip()
            if email:
                with_email.append(admin_user)
            else:
                skipped_admins.append(admin_user["username"])

        if target == "self" and not with_email:
            raise DigestConfigError("The current admin account does not have an email address.")
        if target == "all_admins" and not with_email:
            raise DigestConfigError("No admin accounts have email addresses.")

        subject = _build_subject(frequency=_get_digest_settings()["frequency"], is_test=True)
        run_id = _record_run_start(
            conn,
            delivery_type="test",
            schedule_key=None,
            triggered_by=triggered_by,
            sample_username=sample_username,
            subject=subject,
        )
        if run_id is None:
            raise DigestConfigError("Unable to create test digest run.")

        recipient_count = len(with_email)
        success_count = 0
        failure_count = 0
        for admin_user in with_email:
            preview = _build_preview_payload(
                conn,
                rendered_for_user=sample_user,
                recipient_user=admin_user,
                message_html=message_html,
                is_test=True,
                poster_mode="cid",
            )
            try:
                _send_email(
                    smtp_settings,
                    recipient_email=admin_user["plex_email"],
                    subject=preview["subject"],
                    html_body=preview["html"],
                    text_body=preview["text"],
                    inline_images=preview.get("inline_images"),
                )
                _record_delivery(
                    conn,
                    run_id=run_id,
                    delivery_type="test",
                    recipient_username=admin_user["username"],
                    recipient_email=admin_user["plex_email"],
                    rendered_for_username=sample_username,
                    status="sent",
                )
                success_count += 1
            except Exception as exc:
                _record_delivery(
                    conn,
                    run_id=run_id,
                    delivery_type="test",
                    recipient_username=admin_user["username"],
                    recipient_email=admin_user["plex_email"],
                    rendered_for_username=sample_username,
                    status="failed",
                    error_message=str(exc),
                )
                failure_count += 1
        status = "completed" if failure_count == 0 else "completed_with_failures"
        notes = None
        if skipped_admins:
            notes = f"Skipped admins without email: {', '.join(skipped_admins)}"
        if sync_note:
            notes = f"{notes}. {sync_note}" if notes else sync_note
        _finalize_run(
            conn,
            run_id=run_id,
            status=status,
            recipient_count=recipient_count,
            success_count=success_count,
            failure_count=failure_count,
            notes=notes,
        )
        return {
            "run_id": run_id,
            "delivery_type": "test",
            "target": target,
            "sample_username": sample_username,
            "subject": subject,
            "recipient_count": recipient_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "skipped_admins": skipped_admins,
        }
    finally:
        conn.close()


def _get_schedule_slot(now_utc: datetime | None = None) -> dict[str, Any]:
    digest_settings = _get_digest_settings()
    tz = ZoneInfo(digest_settings["timezone"])
    now_local = (now_utc or datetime.now(tz)).astimezone(tz)
    hour_str, minute_str = digest_settings["send_time"].split(":")
    scheduled_time = time_of_day(hour=int(hour_str), minute=int(minute_str))

    if digest_settings["frequency"] == "daily":
        slot_date = now_local.date()
        slot_dt = datetime.combine(slot_date, scheduled_time, tzinfo=tz)
        if slot_dt > now_local:
            slot_dt -= timedelta(days=1)
        schedule_key = f"daily:{slot_dt.date().isoformat()}:{digest_settings['send_time']}:{digest_settings['timezone']}"
        return {"slot_dt": slot_dt, "schedule_key": schedule_key, "due": True}

    target_weekday = WEEKDAY_INDEX[digest_settings["weekly_day"]]
    days_back = (now_local.weekday() - target_weekday) % 7
    slot_date = now_local.date() - timedelta(days=days_back)
    slot_dt = datetime.combine(slot_date, scheduled_time, tzinfo=tz)
    if slot_dt > now_local:
        slot_dt -= timedelta(days=7)
    schedule_key = f"weekly:{slot_dt.date().isoformat()}:{digest_settings['send_time']}:{digest_settings['timezone']}"
    return {"slot_dt": slot_dt, "schedule_key": schedule_key, "due": True}


def run_scheduled_digest(*, force: bool = False, triggered_by: str | None = None) -> dict[str, Any]:
    digest_settings = _get_digest_settings()
    if not digest_settings["enabled"] and not force:
        return {"status": "disabled"}

    smtp_settings = _get_smtp_settings()
    schedule_slot = _get_schedule_slot()
    subject = _build_subject(frequency=digest_settings["frequency"], is_test=False)

    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        sync_note = None
        try:
            sync_users_from_tautulli()
        except Exception as exc:
            sync_note = f"Tautulli sync skipped: {exc}"
        schedule_key = None if force else schedule_slot["schedule_key"]
        run_id = _record_run_start(
            conn,
            delivery_type="scheduled",
            schedule_key=schedule_key,
            triggered_by=triggered_by,
            sample_username=None,
            subject=subject,
        )
        if run_id is None:
            return {"status": "already_sent", "schedule_key": schedule_key}

        recipients = _list_digest_recipients(conn)
        recipient_count = len(recipients)
        success_count = 0
        failure_count = 0

        saved_message_html = get_digest_content()["message_html"]
        for recipient in recipients:
            preview = _build_preview_payload(
                conn,
                rendered_for_user=recipient,
                recipient_user=recipient,
                message_html=saved_message_html,
                is_test=False,
                poster_mode="cid",
            )
            if preview["counts"]["movies"] == 0 and preview["counts"]["shows"] == 0 and not preview["message_html"]:
                _record_delivery(
                    conn,
                    run_id=run_id,
                    delivery_type="scheduled",
                    recipient_username=recipient["username"],
                    recipient_email=recipient["plex_email"],
                    rendered_for_username=recipient["username"],
                    status="skipped",
                    error_message="No digest content to send.",
                )
                continue
            try:
                _send_email(
                    smtp_settings,
                    recipient_email=recipient["plex_email"],
                    subject=preview["subject"],
                    html_body=preview["html"],
                    text_body=preview["text"],
                    inline_images=preview.get("inline_images"),
                )
                _record_delivery(
                    conn,
                    run_id=run_id,
                    delivery_type="scheduled",
                    recipient_username=recipient["username"],
                    recipient_email=recipient["plex_email"],
                    rendered_for_username=recipient["username"],
                    status="sent",
                )
                success_count += 1
            except Exception as exc:
                _record_delivery(
                    conn,
                    run_id=run_id,
                    delivery_type="scheduled",
                    recipient_username=recipient["username"],
                    recipient_email=recipient["plex_email"],
                    rendered_for_username=recipient["username"],
                    status="failed",
                    error_message=str(exc),
                )
                failure_count += 1

        status = "completed" if failure_count == 0 else "completed_with_failures"
        _finalize_run(
            conn,
            run_id=run_id,
            status=status,
            recipient_count=recipient_count,
            success_count=success_count,
            failure_count=failure_count,
            notes=sync_note,
        )
        return {
            "status": status,
            "run_id": run_id,
            "schedule_key": schedule_key,
            "recipient_count": recipient_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "subject": subject,
        }
    finally:
        conn.close()


def get_digest_history(*, limit_runs: int = 20, limit_deliveries: int = 100) -> dict[str, Any]:
    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    run_id,
                    delivery_type,
                    schedule_key,
                    triggered_by,
                    sample_username,
                    subject,
                    status,
                    recipient_count,
                    success_count,
                    failure_count,
                    notes,
                    started_at,
                    completed_at
                FROM public.email_digest_runs
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (limit_runs,),
            )
            runs = cur.fetchall()
            cur.execute(
                """
                SELECT
                    delivery_id,
                    run_id,
                    delivery_type,
                    recipient_username,
                    recipient_email,
                    rendered_for_username,
                    status,
                    error_message,
                    sent_at
                FROM public.email_digest_deliveries
                ORDER BY sent_at DESC
                LIMIT %s
                """,
                (limit_deliveries,),
            )
            deliveries = cur.fetchall()
        return {"runs": runs, "deliveries": deliveries}
    finally:
        conn.close()
