from fastapi import APIRouter, Request, HTTPException
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv
import traceback
from typing import Any

load_dotenv()

router = APIRouter()

DB_URL = os.getenv("DATABASE_URL")
model = None


def get_model() -> Any:
    global model
    if model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise HTTPException(
                status_code=503,
                detail="RAG embeddings are unavailable in this container image",
            ) from exc
        model = SentenceTransformer("all-mpnet-base-v2")
    return model

@router.post("/rag-query")
async def rag_query(request: Request):
    try:
        data = await request.json()
        query = data["query"]
        username = data.get("username", "jmnovak")

        # Connect to DB
        conn = psycopg2.connect(DB_URL)
        register_vector(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Embed the user query
        query_embedding = get_model().encode(query).tolist()

        # Query for most similar media
        cur.execute("""
            SELECT m.title, m.year, m.media_type, m.genres
            FROM expanded_recs_w_label_v m
            LIMIT 5
        """, (query_embedding,))
        rows = cur.fetchall()

        context = "\n".join(
            f"{row['title']} ({row['year']}, {row['media_type']}), genres: {row['genres']}"
            for row in rows
        )

        return { "context": context }

    except HTTPException:
        raise
    except Exception as e:
        print("💥 Error in /api/rag-query:", repr(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="RAG query failed")

    finally:
        if 'cur' in locals() and not cur.closed:
            cur.close()
        if 'conn' in locals() and not conn.closed:
            conn.close()
