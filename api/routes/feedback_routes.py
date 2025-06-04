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
    reason_code: str

@router.post("/feedback")
def submit_feedback(feedback: FeedbackIn):
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()

        # Look up suppress_default for the reason code
        cur.execute("""
            SELECT suppress_default FROM feedback_reason WHERE code = %s
        """, (feedback.reason_code,))
        result = cur.fetchone()
        if result is None:
            raise HTTPException(status_code=400, detail="Invalid reason code")
        suppress = result[0]

        cur.execute("""
            INSERT INTO user_feedback (username, rating_key, feedback, reason_code, suppress, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            feedback.username,
            feedback.rating_key,
            feedback.feedback,
            feedback.reason_code,
            suppress,
            datetime.utcnow()
        ))

        conn.commit()
        return {"status": "ok"}

    except Exception as e:
        print("❌ Feedback insert error:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
