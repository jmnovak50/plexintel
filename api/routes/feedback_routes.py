from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
from datetime import datetime
import os

router = APIRouter()

class FeedbackIn(BaseModel):
    username: str
    rating_key: int
    feedback: str  # 'up' or 'down'

@router.post("/feedback")
def submit_feedback(feedback: FeedbackIn):
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()

        thumb = (feedback.feedback or "").strip().lower()
        if thumb not in {"up", "down"}:
            raise HTTPException(status_code=400, detail="feedback must be 'up' or 'down'")

        # Keep minimal internal reason rows present (handles truncated feedback_reason tables).
        seed_reasons = [
            ("thumb_up", "Thumbs up", "up", True),
            ("thumb_down", "Thumbs down", "down", True),
        ]
        for code, label, applies_to, suppress_default in seed_reasons:
            cur.execute(
                """
                INSERT INTO feedback_reason (code, label, applies_to, suppress_default)
                SELECT %s, %s, %s, %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM feedback_reason WHERE code = %s
                )
                """,
                (code, label, applies_to, suppress_default, code),
            )

        # One-click thumbs always remove the item from future rec display/suppression.
        suppress = True
        reason_code = "thumb_up" if thumb == "up" else "thumb_down"

        # Keep one row per (username, rating_key) without relying on a DB unique index.
        cur.execute(
            """
            DELETE FROM user_feedback
            WHERE username = %s AND rating_key = %s
            """,
            (feedback.username, feedback.rating_key),
        )

        cur.execute("""
            INSERT INTO user_feedback (username, rating_key, feedback, reason_code, suppress, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            feedback.username,
            feedback.rating_key,
            thumb,
            reason_code,
            suppress,
            datetime.utcnow()
        ))

        conn.commit()
        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Feedback insert error:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if "conn" in locals() and conn:
            conn.close()
