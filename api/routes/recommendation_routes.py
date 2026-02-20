from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional
import requests
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

DB_URL = os.getenv("DATABASE_URL")

def get_plex_username(token: str) -> str:
    headers = {
        "Accept": "application/json",
        "X-Plex-Token": token,
    }
    resp = requests.get("https://plex.tv/users/account.json", headers=headers)

    if resp.status_code != 200:
        raise HTTPException(status_code=403, detail="Failed to fetch Plex username")

    try:
        return resp.json()["user"]["username"]
    except Exception as e:
        print("❌ Failed to parse Plex username response:", resp.text)
        raise HTTPException(status_code=500, detail="Malformed response from Plex")

@router.get("/recommendations")
def get_recommendations(
    request: Request,
    view: str = Query("all"),
    show_rating_key: Optional[int] = Query(None),
    season_rating_key: Optional[int] = Query(None),
):
    print("📥 Session:", request.session)

    token = request.session.get("plex_token")
    print("🔑 Token from session:", token)

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        plex_username = get_plex_username(token)
        print("👤 Resolved Plex username:", plex_username)
    except Exception as e:
        print("❌ Error resolving Plex username:", str(e))
        raise HTTPException(status_code=403, detail="Invalid token")

    try:
        conn = psycopg2.connect(DB_URL)
        register_vector(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        view_key = (view or "all").lower()
        if view_key not in {"all", "movies", "shows", "seasons", "episodes"}:
            raise HTTPException(status_code=400, detail=f"Unsupported view: {view}")

        if view_key == "shows":
            sql = """
                SELECT friendly_name,
                       show_rating_key AS rating_key,
                       show_title AS title,
                       rollup_score AS predicted_probability,
                       NULL::text AS semantic_themes,
                       year,
                       genres,
                       show_title,
                       NULL::int AS season_number,
                       NULL::int AS episode_number,
                       'show'::text AS media_type,
                       scored_at,
                       score_band,
                       show_rating_key,
                       NULL::int AS parent_rating_key
                FROM show_rollups_v
                WHERE username = %s
                ORDER BY rollup_score DESC
            """
            params = [plex_username]
        elif view_key == "seasons":
            sql = """
                SELECT friendly_name,
                       season_rating_key AS rating_key,
                       season_title AS title,
                       rollup_score AS predicted_probability,
                       NULL::text AS semantic_themes,
                       year,
                       genres,
                       show_title,
                       season_number,
                       NULL::int AS episode_number,
                       'season'::text AS media_type,
                       scored_at,
                       score_band,
                       show_rating_key,
                       show_rating_key AS parent_rating_key
                FROM season_rollups_v
                WHERE username = %s
            """
            params = [plex_username]
            if show_rating_key is not None:
                sql += " AND show_rating_key = %s"
                params.append(show_rating_key)
            sql += " ORDER BY rollup_score DESC"
        else:
            sql = """
                SELECT friendly_name,
                       rating_key,
                       title,
                       predicted_probability,
                       semantic_themes,
                       year,
                       genres,
                       show_title,
                       season_number,
                       episode_number,
                       media_type,
                       scored_at,
                       NULL::text AS score_band,
                       show_rating_key,
                       parent_rating_key
                FROM expanded_recs_w_label_v
                WHERE username = %s
            """
            params = [plex_username]
            if view_key == "movies":
                sql += " AND media_type = 'movie'"
            elif view_key == "episodes":
                sql += " AND media_type = 'episode'"
            else:
                sql += " AND media_type IN ('movie', 'episode')"

            if show_rating_key is not None:
                sql += " AND show_rating_key = %s"
                params.append(show_rating_key)
            if season_rating_key is not None:
                sql += " AND parent_rating_key = %s"
                params.append(season_rating_key)

            sql += " ORDER BY predicted_probability DESC"

        # Main recommendations query
        cur.execute(sql, tuple(params))
        rec_rows = cur.fetchall()

        print(f"📦 Found {len(rec_rows)} recs for {plex_username}")

        # ✅ Fetch feedback before closing the connection
        cur.execute("""
            SELECT DISTINCT rating_key
            FROM user_feedback
            WHERE username = %s
        """, (plex_username,))
        feedback_keys = [row["rating_key"] for row in cur.fetchall()]

        return {
            "username": plex_username,
            "recommendations": rec_rows,
            "last_updated": rec_rows[0]["scored_at"] if rec_rows else None,
            "feedback_keys": feedback_keys
        }

    except Exception as e:
        import traceback
        print("💥 Database error:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    finally:
        if 'cur' in locals() and not cur.closed:
            cur.close()
        if 'conn' in locals() and not conn.closed:
            conn.close()
