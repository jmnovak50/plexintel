# users.py
from datetime import datetime

from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db


def get_or_create_user(username: str, email: str = None, token: str = None, friendly_name: str = None):
    conn = connect_db(cursor_factory=RealDictCursor)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()

    if result:
        user_id = result["user_id"]
        cursor.execute(
            """
            UPDATE users
            SET plex_email = %s,
                friendly_name = COALESCE(%s, friendly_name),
                plex_token = %s,
                last_login = %s,
                modified_at = %s
            WHERE user_id = %s
            """,
            (email, friendly_name, token, datetime.utcnow(), datetime.utcnow(), user_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return user_id, False

    cursor.execute(
        """
        INSERT INTO users (username, plex_email, friendly_name, plex_token, created_at, last_login, modified_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING user_id
        """,
        (username, email, friendly_name, token, datetime.utcnow(), datetime.utcnow(), datetime.utcnow())
    )
    user_id = cursor.fetchone()["user_id"]
    conn.commit()
    cursor.close()
    conn.close()
    return user_id, True


def get_user_by_email(email: str) -> dict | None:
    normalized = (email or "").strip()
    if not normalized:
        return None

    conn = connect_db(cursor_factory=RealDictCursor)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute(
            """
            SELECT user_id, username, plex_email, friendly_name, COALESCE(is_admin, FALSE) AS is_admin
            FROM users
            WHERE LOWER(BTRIM(plex_email)) = LOWER(BTRIM(%s))
            LIMIT 1
            """,
            (normalized,),
        )
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def resolve_plex_username(email: str) -> str | None:
    user = get_user_by_email(email)
    if not user:
        return None
    username = user.get("username")
    return str(username).strip() if username else None
