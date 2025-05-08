# users.py
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

DB_URL = os.getenv("DATABASE_URL")

def get_or_create_user(username: str, email: str = None, token: str = None):
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
    result = cursor.fetchone()

    if result:
        user_id = result["user_id"]
        cursor.execute(
            """
            UPDATE users
            SET plex_email = %s,
                plex_token = %s,
                last_login = %s
            WHERE user_id = %s
            """,
            (email, token, datetime.utcnow(), user_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return user_id, False

    cursor.execute(
        """
        INSERT INTO users (username, plex_email, plex_token, created_at, last_login)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING user_id
        """,
        (username, email, token, datetime.utcnow(), datetime.utcnow())
    )
    user_id = cursor.fetchone()["user_id"]
    conn.commit()
    cursor.close()
    conn.close()
    return user_id, True
