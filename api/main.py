from fastapi import FastAPI, Query
from fastapi.responses import ORJSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import psycopg2
import os
from dotenv import load_dotenv

from api.routes import auth_routes
from api.routes import plex_oauth_routes
from api.routes import feedback_routes  # <- wherever your route is
from api.routes.recommendation_routes import router as rec_router
from api.routes.public_recommendation_routes import router as public_router

load_dotenv()

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-secret-key")  # fallback for dev
)

# 👇 ADD THIS TO WIRE UP THE ROUTES
app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
app.include_router(plex_oauth_routes.router, prefix="/api/auth", tags=["auth"])
app.include_router(rec_router, prefix="/api")               # ✅ only once
app.include_router(public_router)                           # ✅ public routes, no prefix
app.include_router(feedback_routes.router, prefix="/api")


# ✅ Define route BEFORE mounting static
@app.get("/api/recs")
async def get_recommendations(username: str = Query(...)):
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()

        query = """
            SELECT rating_key, username, friendly_name, scored_at, media_type, show_title, title,
                   season_number, episode_number, year, genres, predicted_probability, semantic_themes
            FROM expanded_recs_w_label_v
            WHERE username = %s
            ORDER BY predicted_probability DESC
        """
        cur.execute(query, (username,))
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        results = [dict(zip(columns, row)) for row in rows]

        cur.close()
        conn.close()
        return ORJSONResponse(content=results)

    except Exception as e:
        print("❌ ERROR during /api/recs:", e)
        return ORJSONResponse(content={"error": str(e)}, status_code=500)

from fastapi.responses import FileResponse

# ✅ Mount the static frontend *after* the route
app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")

@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    file_path = os.path.join("frontend", "dist", "index.html")
    return FileResponse(file_path)

@app.on_event("startup")
def startup_log():
    print("🚀 Backend started with session middleware active.")
