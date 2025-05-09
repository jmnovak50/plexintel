from fastapi import APIRouter, Request, HTTPException
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
def get_recommendations(request: Request):
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

        cur.execute("""
            SELECT friendly_name, rating_key, title, predicted_probability, semantic_themes, year, genres, show_title, season_number, episode_number, media_type, scored_at
            FROM expanded_recs_w_label_v
            WHERE username = %s
            ORDER BY predicted_probability DESC
        """, (plex_username,))

        rows = cur.fetchall()
        print(f"📦 Found {len(rows)} recs for {plex_username}")
        colnames = [desc[0] for desc in cur.description]
        result = [dict(zip(colnames, row)) for row in rows]

        return {
            "username": plex_username,
            "recommendations": rows,  # your recs list
            "last_updated": rows[0]["scored_at"] if rows else None
}

    except Exception as e:
        print("💥 Database error:", str(e))
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

