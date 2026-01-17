# ollama_embeddings.py
"""
Lightweight client for NAS-hosted Ollama embeddings (EmbeddingGemma).
- Uses /api/embed (new endpoint) with batching, retries, and keep-alive
- Controlled via env vars so you can toggle without code edits

ENV (all optional):
  OLLAMA_HOST       e.g. http://192.168.1.123:31770  (default: http://localhost:11434)
  OLLAMA_MODEL      e.g. embeddinggemma               (default: embeddinggemma)
  OLLAMA_THREADS    e.g. 16                           (default: auto)
  EMBED_BATCH_SIZE  e.g. 256                          (default: 128)
  OLLAMA_TIMEOUT_S  e.g. 60                           (default: 60)
"""
from __future__ import annotations
import os, time, json, math
import requests
from typing import Iterable, List

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.1.123:31770")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "embeddinggemma")
raw_default_bs = os.getenv("EMBED_BATCH_SIZE", "128")
EMBED_BATCH_SIZE = int(str(raw_default_bs).strip().split()[0])
OLLAMA_TIMEOUT_S = int(os.getenv("OLLAMA_TIMEOUT_S", "300"))
OLLAMA_THREADS = os.getenv("OLLAMA_THREADS")  # string or None

class OllamaError(RuntimeError):
    pass


def chunks(seq, batch):
    # Ensure batch is always an int
    batch = int(batch)
    for i in range(0, len(seq), batch):
        yield seq[i : i + batch]


def _post_embed(inputs: List[str]) -> List[List[float]]:
    payload = {"model": OLLAMA_MODEL, "input": inputs, "keep_alive": "15m"}
    if OLLAMA_THREADS:
        # llama.cpp-compatible hint; Ollama will ignore if unsupported
        payload["num_thread"] = int(OLLAMA_THREADS)
    r = requests.post(f"{OLLAMA_HOST}/api/embed", json=payload, timeout=OLLAMA_TIMEOUT_S)
    if r.status_code >= 400:
        raise OllamaError(f"Ollama error {r.status_code}: {r.text[:200]}")
    data = r.json()
    embs = data.get("embeddings") or []
    if not embs or not isinstance(embs, list):
        raise OllamaError(f"No embeddings returned; response={json.dumps(data)[:200]}")
    return embs


def embed_texts(
    texts: List[str],
    batch_size: int | None = None,
    max_retries: int = 3,
    backoff_s: float = 1.0
) -> List[List[float]]:
    """Embed a list of strings with batching + basic retries.
    Returns a list of vectors (same order/length as input).
    """
    if not texts:
        return []

    # -------------------------
    # NORMALIZE BATCH SIZE HERE
    # -------------------------
    # batch_size may be:
    #   - None
    #   - an int
    #   - a string like "128"
    #   - or a string like "128 (default: 128)" ← problematic
    raw_bs = batch_size if batch_size is not None else EMBED_BATCH_SIZE

    # Extract the first numeric chunk safely
    # e.g. "128 (default: 128)" → "128"
    try:
        bs = int(str(raw_bs).strip().split()[0])
    except Exception:
        # hard fallback if parsing fails
        bs = 128

    out: List[List[float]] = []

    for part in chunks(texts, bs):
        attempt = 0
        while True:
            try:
                out.extend(_post_embed(part))
                break
            except Exception as e:
                attempt += 1
                if attempt > max_retries:
                    raise
                time.sleep(backoff_s * (2 ** (attempt - 1)))

    return out



# ------------------------------------------------------------------------------
# fetch_tautulli_data.py — integration additions
# (Drop the following into your existing script. Search for the markers.)
# ------------------------------------------------------------------------------

# === [IMPORTS — add near other imports] ===
# import os
# from pgvector import Vector
# from ollama_embeddings import embed_texts

# === [CONFIG (optional)] ===
# ENABLE_EMBED_MEDIA   = os.getenv("ENABLE_EMBED_MEDIA", "1") == "1"
# ENABLE_EMBED_WATCHES = os.getenv("ENABLE_EMBED_WATCHES", "1") == "1"
# EMBED_BATCH_SIZE     = int(os.getenv("EMBED_BATCH_SIZE", "128"))

# === [HELPERS] ===
# def _media_text_for_embedding(row):
#     # row: (rating_key, title, summary)
#     rk, title, summary = row
#     title = title or ""
#     summary = summary or ""
#     return f"{title} — {summary}".strip()

# def embed_new_media(conn, cursor, batch_size: int = EMBED_BATCH_SIZE):
#     """Create media_embeddings for library rows missing vectors."""
#     cursor.execute(
#         """
#         SELECT l.rating_key, l.title, COALESCE(l.summary, '')
#         FROM library l
#         LEFT JOIN media_embeddings me ON me.rating_key = l.rating_key
#         WHERE me.rating_key IS NULL
#         ORDER BY l.rating_key
#         """
#     )
#     rows = cursor.fetchall()
#     if not rows:
#         print("✅ No new media to embed.")
#         return
#     print(f"🧠 Embedding {len(rows)} media rows…")
#     texts = [_media_text_for_embedding(r) for r in rows]
#     vectors = embed_texts(texts, batch_size=batch_size)
#     assert len(vectors) == len(rows)
#     # Insert in chunks within transactions
#     for i in range(0, len(rows), batch_size):
#         part_rows = rows[i:i+batch_size]
#         part_vecs = vectors[i:i+batch_size]
#         with conn:
#             with conn.cursor() as cur:
#                 for (rk, _t, _s), vec in zip(part_rows, part_vecs):
#                     cur.execute(
#                         "INSERT INTO media_embeddings (rating_key, embedding) VALUES (%s, %s) ON CONFLICT (rating_key) DO NOTHING",
#                         (rk, Vector(vec)),
#                     )
#     print("✅ Media embeddings up to date.")

# def embed_new_watches(conn, cursor, batch_size: int = EMBED_BATCH_SIZE):
#     """Create watch_embeddings for watch_history rows missing vectors.
#     Uses the linked library title/summary as the textual basis.
#     """
#     cursor.execute(
#         """
#         SELECT wh.watch_id, l.title, COALESCE(l.summary, '')
#         FROM watch_history wh
#         LEFT JOIN watch_embeddings we ON we.watch_id = wh.watch_id
#         JOIN library l ON l.rating_key = wh.rating_key
#         WHERE we.watch_id IS NULL
#         ORDER BY wh.watch_id
#         """
#     )
#     rows = cursor.fetchall()
#     if not rows:
#         print("✅ No new watch rows to embed.")
#         return
#     print(f"🧠 Embedding {len(rows)} watch rows…")
#    
#     texts = [f"{t or ''} — {s or ''}" for _wid, t, s in rows]
#     vectors = embed_texts(texts, batch_size=batch_size)
#     assert len(vectors) == len(rows)
#     for i in range(0, len(rows), batch_size):
#         part_rows = rows[i:i+batch_size]
#         part_vecs = vectors[i:i+batch_size]
#         with conn:
#             with conn.cursor() as cur:
#                 for (watch_id, _t, _s), vec in zip(part_rows, part_vecs):
#                     cur.execute(
#                         "INSERT INTO watch_embeddings (watch_id, embedding) VALUES (%s, %s) ON CONFLICT (watch_id) DO NOTHING",
#                         (watch_id, Vector(vec)),
#                     )
#     print("✅ Watch embeddings up to date.")

# === [CALL SITES] ===
# After inserting new library rows:
#     store_library_data(conn, cursor, enriched)
#     if ENABLE_EMBED_MEDIA:
#         embed_new_media(conn, cursor)
#
# After sync_new_watch_history(conn, cursor):
#     if ENABLE_EMBED_WATCHES:
#         embed_new_watches(conn, cursor)


# ------------------------------------------------------------------------------
# build_user_embeddings.py — optimized join + logging (drop-in replacement)
# ------------------------------------------------------------------------------

# build_user_embeddings.py (REPLACEMENT)
from dotenv import load_dotenv
import os
import psycopg2
import numpy as np
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from pgvector import Vector

# ✅ Load environment variables
load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

DB_URL = os.getenv("DATABASE_URL")

EMBEDDING_DIMENSION = 768
ENGAGEMENT_THRESHOLD = float(os.getenv("ENGAGEMENT_THRESHOLD", "0.5"))


def fetch_user_vectors(conn):
    """Fetch engaged watches joined directly to media embeddings to avoid N queries."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                wh.username,
                me.embedding
            FROM watch_history wh
            JOIN library l ON wh.rating_key = l.rating_key
            JOIN media_embeddings me ON me.rating_key = l.rating_key
            WHERE l.duration > 0
              AND wh.played_duration IS NOT NULL
              AND (wh.played_duration::float / (l.duration / 1000.0)) > %s
            """,
            (ENGAGEMENT_THRESHOLD,),
        )
        return cur.fetchall()


def build_user_embeddings(user_rows, conn):
    users = {}
    for row in user_rows:
        u = row["username"]
        v = np.array(row["embedding"], dtype=float)
        users.setdefault(u, []).append(v)

    with conn.cursor() as cur:
        for u, vecs in users.items():
            if not vecs:
                continue
            avg = np.mean(vecs, axis=0)
            # (Optional) L2 normalize for cosine-ready vectors
            norm = np.linalg.norm(avg)
            if norm > 0:
                avg = avg / norm
            print(f"✅ {u} — vectors: {len(vecs)} — norm: {np.linalg.norm(avg):.4f}")
            cur.execute(
                """
                INSERT INTO user_embeddings (username, embedding)
                VALUES (%s, %s)
                ON CONFLICT (username) DO UPDATE SET embedding = EXCLUDED.embedding
                """,
                (u, Vector(avg.tolist())),
            )
    conn.commit()


def main():
    if DB_URL:
        conn = psycopg2.connect(DB_URL)
    else:
        conn = psycopg2.connect(**DB_CONFIG)
    register_vector(conn)

    print("🔍 Fetching engaged user vectors (joined with media_embeddings)…")
    rows = fetch_user_vectors(conn)
    print(f"🎬 Aggregating {len(rows)} engaged vectors across users…")

    build_user_embeddings(rows, conn)
    conn.close()


if __name__ == "__main__":
    main()
