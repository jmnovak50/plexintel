from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = os.getenv("DATABASE_URL")  # already used elsewhere in PlexIntel
router = APIRouter()

BASE = """
SELECT rating_key, title, year, media_type, duration, added_at, changed_at,
       genres_arr, actors_arr, directors_arr,
       rating, summary, season_number, episode_number,
       show_title, episode_title, episode_summary,
       series_title, season_episode_code, display_title
FROM library_catalog_v
"""

def q(sql: str, params=()):
    with psycopg2.connect(DB_URL, cursor_factory=RealDictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

@router.get("/health")
def health():
    return {"ok": True, "service": "library-catalog"}

@router.get("/recent")
def recent(limit: int = 50):
    rows = q(BASE + " ORDER BY changed_at DESC NULLS LAST LIMIT %s", (limit,))
    return {"items": rows}

@router.get("/by_id/{rating_key}")
def by_id(rating_key: int):
    rows = q(BASE + " WHERE rating_key = %s", (rating_key,))
    if not rows:
        raise HTTPException(404, "Not found")
    return rows[0]

@router.get("/search")
def search(
    title: Optional[str] = None,
    media_type: Optional[str] = Query(None, pattern="^(movie|episode|series)$"),
    genre: Optional[str] = None,
    person: Optional[str] = None,   # matches actor or director
    year_gte: Optional[int] = None,
    year_lte: Optional[int] = None,
    duration_lte: Optional[int] = None,
    limit: int = 50
):
    clauses: list[str] = []
    params: list = []
    if title:
        clauses += ["LOWER(title) LIKE LOWER(%s)"]; params += [f"%{title}%"]
    if media_type:
        clauses += ["media_type = %s"]; params += [media_type]
    if genre:
        clauses += ["%s = ANY(genres_arr)"]; params += [genre]
    if person:
        clauses += ["(%s = ANY(actors_arr) OR %s = ANY(directors_arr))"]; params += [person, person]
    if year_gte is not None:
        clauses += ["year >= %s"]; params += [year_gte]
    if year_lte is not None:
        clauses += ["year <= %s"]; params += [year_lte]
    if duration_lte is not None:
        clauses += ["duration IS NOT NULL AND duration <= %s"]; params += [duration_lte]

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = BASE + where + " ORDER BY changed_at DESC NULLS LAST LIMIT %s"
    rows = q(sql, (*params, limit))
    return {"items": rows}
