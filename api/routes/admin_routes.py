from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel
import subprocess

router = APIRouter()

# Whitelisted scripts that can be run
ALLOWED_SCRIPTS = {
    "train_model.py",
    "build_training_data.py",
    "score_model.py",
    "build_user_embeddings.py",
    "fetch_tautulli_data.py",
    "label_embeddings.py",
    "run_daily_pipeline.sh"
}

class ScriptRequest(BaseModel):
    script: str

import psycopg2
from psycopg2.extras import RealDictCursor
import os

DB_URL = os.getenv("DATABASE_URL")

def get_current_user(request: Request):
    username = request.session.get("username")
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/admin/run-script")
async def run_script(req: ScriptRequest, request: Request, user=Depends(get_current_user)):
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    if req.script not in ALLOWED_SCRIPTS:
        raise HTTPException(status_code=400, detail=f"Script '{req.script}' not allowed")

    try:
        result = subprocess.run(
            ["python3", req.script] if req.script.endswith(".py") else ["bash", req.script],
            capture_output=True,
            text=True,
            check=False
        )
        return {
            "script": req.script,
            "exit_code": result.returncode,
            "stdout": result.stdout[-5000:],  # Limit output to last 5K chars
            "stderr": result.stderr[-5000:]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
