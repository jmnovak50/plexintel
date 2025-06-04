# api/public_recommendation_routes.py

import os
import uuid
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter()

# 🔐 Load .env and API key
load_dotenv()
PUBLIC_API_KEY = os.getenv("PUBLIC_API_KEY")

# ✅ Validate API Key format + value
def validate_api_key(apikey: Optional[str]):
    try:
        if not apikey or str(uuid.UUID(apikey)) != PUBLIC_API_KEY:
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")

# 📦 Shared logic for both routes
def fetch_recommendations(username, genre, media_type, score_threshold, page, page_size):
    base_query = """
        FROM expanded_recs_w_label_v
        WHERE username = %s
    """
    params = [username]

    if genre:
        base_query += " AND genres ILIKE %s"
        params.append(f"%{genre}%")
    if media_type:
        base_query += " AND media_type = %s"
        params.append(media_type)
    if score_threshold is not None:
        base_query += " AND predicted_probability >= %s"
        params.append(score_threshold)

    offset = (page - 1) * page_size

    data_query = f"""
        SELECT rating_key, title, predicted_probability, semantic_themes, year, genres, show_title, media_type
        {base_query}
        ORDER BY predicted_probability DESC
        LIMIT %s OFFSET %s
    """
    count_query = f"SELECT COUNT(*) {base_query}"
    params_with_pagination = params + [page_size, offset]

    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(count_query, tuple(params))
        total = cur.fetchone()["count"]

        cur.execute(data_query, tuple(params_with_pagination))
        rows = cur.fetchall()

        return {
            "page": page,
            "page_size": page_size,
            "total_results": total,
            "total_pages": (total + page_size - 1) // page_size,
            "results": rows
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()

# 🚀 Clean public endpoint
@router.get("/api/public_recs")
def get_public_recs(
    username: str = Query(...),
    genre: Optional[str] = Query(None),
    media_type: Optional[str] = Query(None),
    score_threshold: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    apikey: Optional[str] = Query(None, alias="apikey")
):
    validate_api_key(apikey)
    return fetch_recommendations(username, genre, media_type, score_threshold, page, page_size)

# 🧭 Tautulli-style command router
@router.get("/api")
def tautulli_style_router(
    cmd: str = Query(...),
    apikey: str = Query(...),
    username: Optional[str] = Query(None),
    genre: Optional[str] = Query(None),
    media_type: Optional[str] = Query(None),
    score_threshold: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    validate_api_key(apikey)

    if cmd == "get_public_recs":
        if not username:
            raise HTTPException(status_code=400, detail="Missing required parameter: username")
        return fetch_recommendations(username, genre, media_type, score_threshold, page, page_size)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown command: {cmd}")
