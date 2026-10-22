"""Playback acquisition and persistence only; no model or embedding operations."""
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
import math

PLAYBACK_FIELDS = (
    "ip_address", "player", "platform", "product", "device",
    "platform_version", "product_version", "session_id",
)
COLUMNS = (
    "rating_key", "watched_at", "played_duration", "percent_complete", "watch_id",
    "media_type", "username", "title", "episode_title", "season_number",
    "episode_number", "friendly_name", "show_rating_key",
) + PLAYBACK_FIELDS


def integer(value):
    if isinstance(value, bool):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError, OverflowError):
        return None


def text(value):
    if not isinstance(value, str) or "\x00" in value:
        return None
    return value.strip() or None


def utc(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def map_history(row):
    if not isinstance(row, dict):
        return None
    # Current Tautulli emits id and row_id; watch_id supports normalized callers.
    event_id = next((row[k] for k in ("id", "row_id", "watch_id") if row.get(k) is not None), None)
    watch_id, rating_key = integer(event_id), integer(row.get("rating_key"))
    if watch_id is None or watch_id <= 0 or rating_key is None or rating_key <= 0:
        return None  # Excludes active sessions with no durable history id.
    values = dict.fromkeys(COLUMNS)
    values.update(watch_id=watch_id, rating_key=rating_key)
    timestamp = integer(row.get("date"))
    try:
        values["watched_at"] = datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None) if timestamp is not None else None
    except (OverflowError, OSError, ValueError):
        pass
    values["played_duration"] = integer(row.get("play_duration"))
    try:
        percent = float(row.get("percent_complete"))
        values["percent_complete"] = percent if math.isfinite(percent) else None
    except (ValueError, TypeError, OverflowError):
        pass
    media_type = text(row.get("media_type"))
    values.update(
        media_type=media_type, username=text(row.get("user")),
        friendly_name=text(row.get("friendly_name")),
        title=text(row.get("grandparent_title") if media_type == "episode" else row.get("title")),
        episode_title=text(row.get("title")) if media_type == "episode" else None,
        season_number=integer(row.get("parent_media_index")),
        episode_number=integer(row.get("media_index")),
        show_rating_key=integer(row.get("grandparent_rating_key")),
    )
    if media_type == "season":
        values["show_rating_key"] = integer(row.get("parent_rating_key"))
    elif media_type in ("show", "series"):
        values["show_rating_key"] = rating_key
    supplied = set()
    for field in PLAYBACK_FIELDS:
        if field not in row:
            continue
        raw = row[field]
        # An explicit JSON null clears optional playback context. Empty or malformed
        # values mean unknown and preserve existing evidence.
        if raw is None:
            supplied.add(field)
            continue
        value = text(raw)
        if field == "session_id" and isinstance(raw, int) and not isinstance(raw, bool):
            value = str(raw)
        if field == "ip_address" and value:
            try:
                if "/" in value or "%" in value:
                    value = None  # host addresses only, no CIDRs or interface scopes
                else:
                    value = str(ip_address(value))
            except ValueError:
                value = None
        if value is not None:
            values[field] = value
            supplied.add(field)
    return values, supplied


def persist_grouped_history(conn, cursor, rows, *, source_grouping, raise_on_error=True):
    """Legacy model projection only. Raw callers have no access to this writer."""
    if source_grouping != 1:
        raise ValueError("Model-facing history requires grouping=1")
    columns = COLUMNS[:13]
    # Exactly the four fields updated by the pre-enhancement implementation.
    mutable = ("played_duration", "percent_complete", "watched_at", "show_rating_key")
    stats = dict(inserted=0, updated=0, unchanged=0, skipped=0, failed=0)
    for row in rows:
        mapped = map_history(row)
        if mapped is None:
            stats["skipped"] += 1
            continue
        members = group_members(row)
        if members is None:
            raise ValueError("Grouped history requires complete source group_ids/group_count")
        values, _ = mapped
        expressions = {c: f"EXCLUDED.{c}" for c in mutable}
        updates = ", ".join(f"{c} = {v}" for c, v in expressions.items())
        changes = " OR ".join(f"watch_history.{c} IS DISTINCT FROM {v}" for c, v in expressions.items())
        cursor.execute("SAVEPOINT grouped_history_record")
        try:
            cursor.execute(
                "INSERT INTO public.watch_history (" + ", ".join(columns) + ") VALUES (" +
                ", ".join(["%s"] * len(columns)) + ") ON CONFLICT (watch_id) DO UPDATE SET " +
                updates + " WHERE watch_history.rating_key = EXCLUDED.rating_key AND "
                "watch_history.username IS NOT DISTINCT FROM EXCLUDED.username AND (" + changes +
                ") RETURNING (xmax = 0)", tuple(values[c] for c in columns),
            )
            result = cursor.fetchone()
            if result is None:
                cursor.execute("SELECT rating_key, username FROM public.watch_history WHERE watch_id = %s", (values["watch_id"],))
                old = cursor.fetchone()
                outcome = "unchanged" if old == (values["rating_key"], values["username"]) else "skipped"
            else:
                outcome = "inserted" if result[0] else "updated"
            cursor.execute("RELEASE SAVEPOINT grouped_history_record")
            stats[outcome] += 1
        except Exception:
            cursor.execute("ROLLBACK TO SAVEPOINT grouped_history_record")
            cursor.execute("RELEASE SAVEPOINT grouped_history_record")
            stats["failed"] += 1
            if raise_on_error:
                raise RuntimeError("Grouped history database write failed") from None
    return stats


def group_members(row):
    """Explicit upstream membership only; reference_id is not a watch_id."""
    if not isinstance(row, dict) or not isinstance(row.get("group_ids"), str):
        return None
    parts = row["group_ids"].split(",")
    members = [integer(part.strip()) for part in parts]
    count = integer(row.get("group_count"))
    if (not members or any(m is None or m <= 0 for m in members)
            or len(set(members)) != len(members) or count != len(members)):
        return None
    source_id = next((integer(row[k]) for k in ("id", "row_id", "watch_id") if row.get(k) is not None), None)
    return members if source_id in members else None


def iter_history_pages(fetch, *, grouping, after=None, before=None, page_size=1000, reference_id=None):
    if grouping not in (0, 1):
        raise ValueError("Explicit source grouping 0 or 1 is required")
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000")
    start, total, seen = 0, None, set()
    while True:
        params = dict(start=start, length=page_size, order_column="date", order_dir="asc",
                      grouping=grouping, include_activity=0)
        if reference_id is not None:
            params["reference_id"] = reference_id
        if after is not None:
            params["after"] = after
        if before is not None:
            params["before"] = before
        response = fetch("get_history", params)
        if not isinstance(response, dict) or not isinstance(response.get("data"), list):
            raise RuntimeError("History page missing a list 'data' payload")
        rows = response["data"]
        count = integer(response.get("recordsFiltered", response.get("recordsTotal")))
        if count is None or count < 0 or (total is not None and count != total):
            raise RuntimeError("Invalid or changing history count; repeat this date window")
        total = count
        for row in rows:
            mapped = map_history(row)
            if mapped:
                event_id = mapped[0]["watch_id"]
                if event_id in seen:
                    raise RuntimeError("History shifted during pagination; repeat this date window")
                seen.add(event_id)
        if len(rows) > page_size or start + len(rows) > total:
            raise RuntimeError("History exceeded reported count")
        if not rows and start < total:
            raise RuntimeError(f"Incomplete history: got {start} of {total}")
        if rows:
            yield rows
        start += len(rows)
        if start == total:
            return
        # Servers can cap page size below the requested size.

