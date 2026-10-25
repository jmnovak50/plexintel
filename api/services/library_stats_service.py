"""Read-only aggregation over independently ingested library entities."""
from datetime import datetime, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from api.db.connection import connect_db

LibraryStatsMediaType = Literal["movie", "show", "season", "episode"]
LibraryStatsCategory = Literal["movies", "shows", "seasons", "episodes"]


class LibraryStatsPeriod(BaseModel):
    since: datetime | None
    until: datetime


class LibraryStatsResponse(BaseModel):
    period: LibraryStatsPeriod
    media_type: LibraryStatsMediaType | None
    counts: dict[LibraryStatsCategory, Annotated[int, Field(ge=0)]] = Field(description="Exact counts for selected supported categories.")
    total: int = Field(ge=0)
    unsupported_categories: list[LibraryStatsMediaType]
    added_at_timezone: str = Field(description="Database session timezone used by library epoch ingestion.")
    scope: Literal["synced_library_inventory"] = "synced_library_inventory"


def get_library_stats(
    *, since: datetime | None = None, until: datetime | None = None,
    media_type: LibraryStatsMediaType | None = None,
) -> LibraryStatsResponse:
    def utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    since = utc(since) if since is not None else None
    until = utc(until) if until is not None else datetime.now(timezone.utc)
    if since is not None and since >= until:
        raise HTTPException(400, "since must be earlier than until")
    categories = {"movie": "movies", "show": "shows", "season": "seasons", "episode": "episodes"}
    if media_type is not None and media_type not in categories:
        raise HTTPException(400, "media_type must be movie, show, season, or episode")

    # No enriched views/joins: a Plex rating_key is the ingestion/upsert identity.
    # Both show spellings occur in the ingestion code; never infer parent dates.
    sql = """
        SELECT
            COUNT(DISTINCT rating_key) FILTER (WHERE media_type = 'movie') AS movies,
            COUNT(DISTINCT rating_key) FILTER (WHERE media_type IN ('show', 'series')) AS shows,
            COUNT(DISTINCT rating_key) FILTER (WHERE media_type = 'season') AS seasons,
            COUNT(DISTINCT rating_key) FILTER (WHERE media_type = 'episode') AS episodes,
            current_setting('TimeZone') AS added_at_timezone
        FROM public.library
        WHERE
    """
    # Ingestion casts TO_TIMESTAMP(epoch) to a naive timestamp using the database
    # session timezone. Convert bounds on the parameter side, preserving index use.
    bound = "(%s::timestamptz AT TIME ZONE current_setting('TimeZone'))"
    params: list[object] = []
    if since is None:
        sql += f" (added_at < {bound} OR added_at IS NULL)"
        params.append(until)
    else:
        sql += f" added_at >= {bound} AND added_at < {bound}"
        params.extend([since, until])
    if media_type == "show":
        sql += " AND media_type IN ('show', 'series')"
    elif media_type is not None:
        sql += " AND media_type = %s"
        params.append(media_type)

    conn = connect_db(cursor_factory=RealDictCursor)
    try:
        conn.set_session(readonly=True)
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
    finally:
        conn.close()
    # Naive storage loses which occurrence of a repeated DST hour an item used.
    # Do not return a seemingly exact count for a boundary inside that hour.
    try:
        storage_zone = ZoneInfo(row["added_at_timezone"])
    except ZoneInfoNotFoundError:
        raise HTTPException(503, "Library storage timezone is not supported") from None
    for value in (since, until):
        if value is None:
            continue
        local = value.astimezone(storage_zone)
        if local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset():
            raise HTTPException(400, "Time bounds inside a repeated daylight-saving hour cannot be resolved from library timestamps")
    selected = [categories[media_type]] if media_type else list(categories.values())
    counts = {category: row[category] for category in selected}
    return LibraryStatsResponse(
        period=LibraryStatsPeriod(since=since, until=until), media_type=media_type,
        counts=counts, total=sum(counts.values()), unsupported_categories=[],
        added_at_timezone=row["added_at_timezone"],
    )
