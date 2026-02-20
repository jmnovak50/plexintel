from fastapi import FastAPI, Query, Request
from fastapi.responses import ORJSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
import psycopg2
import os
from dotenv import load_dotenv

from api.routes import auth_routes
from api.routes import plex_oauth_routes
from api.routes import feedback_routes  # <- wherever your route is
from api.routes import admin_routes
from api.routes import rag_routes
from api.routes import library_catalog
from api.routes import agent_tools
from api.routes.recommendation_routes import router as rec_router
from api.routes.public_recommendation_routes import router as public_router
from api.services.plex_service import get_plex_user_info
from api.db.users import get_or_create_user

load_dotenv()

app = FastAPI()


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as ex:
            # Preserve API 404 behavior.
            if ex.status_code == 404 and not path.startswith("api/"):
                return await super().get_response("index.html", scope)
            raise


def _has_admin_session(request: Request) -> bool:
    username = request.session.get("username")
    token = request.session.get("plex_token")

    if not username and token:
        plex_user = get_plex_user_info(token)
        if plex_user and plex_user.get("username"):
            username = plex_user["username"]
            user_id, _ = get_or_create_user(
                username=username,
                email=plex_user.get("email"),
                token=token,
            )
            request.session["username"] = username
            request.session["user_id"] = user_id

    if not username:
        return False

    conn = None
    cur = None
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute("SELECT is_admin FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        return bool(row and row[0])
    except Exception:
        return False
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # or ["https://<your-openwebui-host>"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(admin_routes.router, prefix="/api")
app.include_router(rag_routes.router, prefix="/api")
app.include_router(library_catalog.router, prefix="/api/library", tags=["library"])
app.include_router(agent_tools.router, prefix="/api/agent", tags=["agent-tools"])


@app.get("/admin", include_in_schema=False)
async def admin_entry(request: Request):
    if not _has_admin_session(request):
        return RedirectResponse(url="/", status_code=307)
    return FileResponse("frontend/dist/index.html")


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

# ✅ Serve everything in the built frontend directory so favicon and other assets resolve
app.mount(
    "/",
    SPAStaticFiles(directory="frontend/dist", html=True),
    name="frontend",
)

@app.on_event("startup")
def startup_log():
    print("🚀 Backend started with session middleware active.")
