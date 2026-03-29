import requests
from fastapi import APIRouter, HTTPException, Request, Response
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services.app_settings import get_setting_value
from api.services.poster_service import resolve_poster_path_from_row

router = APIRouter()


def _is_image_response(response: requests.Response) -> bool:
    content_type = (response.headers.get("Content-Type") or "").lower()
    return response.status_code == 200 and content_type.startswith("image/")


def _fetch_tautulli_image(poster_path: str) -> requests.Response:
    last_error = None
    tautulli_url = get_setting_value("tautulli.base_url")
    tautulli_api_url = get_setting_value("tautulli.api_url")
    tautulli_api_key = get_setting_value("tautulli.api_key")

    if tautulli_url:
        proxy_url = f"{tautulli_url.rstrip('/')}/pms_image_proxy"
        try:
            direct_response = requests.get(
                proxy_url,
                params={"img": poster_path, "apikey": tautulli_api_key},
                allow_redirects=False,
                timeout=20,
            )
            if _is_image_response(direct_response):
                return direct_response
        except requests.RequestException as exc:
            last_error = exc

    if tautulli_api_url:
        try:
            api_response = requests.get(
                tautulli_api_url,
                params={
                    "cmd": "pms_image_proxy",
                    "apikey": tautulli_api_key,
                    "img": poster_path,
                },
                timeout=20,
            )
            if _is_image_response(api_response):
                return api_response
        except requests.RequestException as exc:
            last_error = exc

    if last_error:
        raise last_error

    raise HTTPException(status_code=502, detail="Unable to fetch poster from Tautulli.")


@router.get("/posters/{rating_key}")
def get_poster(rating_key: int, request: Request):
    token = request.session.get("plex_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    tautulli_url = get_setting_value("tautulli.base_url")
    tautulli_api_url = get_setting_value("tautulli.api_url")
    tautulli_api_key = get_setting_value("tautulli.api_key")

    if not tautulli_api_key or (not tautulli_url and not tautulli_api_url):
        raise HTTPException(status_code=500, detail="Poster proxy is not configured.")

    conn = None
    cur = None
    try:
        conn = connect_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT media_type, thumb_path, parent_thumb_path, grandparent_thumb_path
            FROM library
            WHERE rating_key = %s
            """,
            (rating_key,),
        )
        row = cur.fetchone()
    except Exception as exc:
        print("💥 Poster lookup DB error:", repr(exc))
        raise HTTPException(status_code=500, detail="Failed to fetch poster metadata.")
    finally:
        if cur is not None and not cur.closed:
            cur.close()
        if conn is not None and not conn.closed:
            conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Poster not found.")

    poster_path = resolve_poster_path_from_row(row)
    if not poster_path:
        raise HTTPException(status_code=404, detail="Poster not found.")

    try:
        image_response = _fetch_tautulli_image(poster_path)
    except HTTPException:
        raise
    except requests.RequestException as exc:
        print("💥 Poster proxy upstream error:", repr(exc))
        raise HTTPException(status_code=502, detail="Unable to fetch poster from Tautulli.")

    content_type = image_response.headers.get("Content-Type", "image/jpeg")
    return Response(
        content=image_response.content,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )
