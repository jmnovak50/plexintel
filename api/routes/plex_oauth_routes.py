# Updated plex_oauth_routes.py for real OAuth redirect flow
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from api.services.plex_service import poll_plex_pin
from typing import Optional
import httpx, os
from api.db.users import get_or_create_user

router = APIRouter()

PLEX_CLIENT_ID = os.getenv("PLEX_CLIENT_ID")
PLEX_PRODUCT = os.getenv("PLEX_PRODUCT", "PlexIntel")
REDIRECT_URI = os.getenv("PLEX_REDIRECT_URI", "http://localhost:8489/api/auth/redirect")

# # STEP 1: Redirect user to Plex OAuth authorize endpoint
# @router.get("/login")
# def login_with_plex():
#     url = (
#         f"https://plex.tv/api/v2/oauth/authorize?client_id={PLEX_CLIENT_ID}"
#         f"&response_type=code&redirect_uri={REDIRECT_URI}"
#     )
#     return RedirectResponse(url)

# # STEP 2: Handle callback and exchange code for token
# @router.get("/redirect")
# def handle_redirect(code: str):
#     data = {
#         "code": code,
#         "client_id": PLEX_CLIENT_ID,
#         "redirect_uri": REDIRECT_URI,
#         "grant_type": "authorization_code"
#     }

#     headers = {
#         "Accept": "application/json",
#         "X-Plex-Product": PLEX_PRODUCT,
#         "X-Plex-Client-Identifier": PLEX_CLIENT_ID,
#     }

#     token_resp = httpx.post("https://plex.tv/api/v2/oauth/token", data=data, headers=headers)
#     if token_resp.status_code != 200:
#         raise HTTPException(status_code=401, detail="Failed to get Plex token")

#     token_json = token_resp.json()
#     auth_token = token_json["access_token"]

    # Get Plex user info
    # user_info = httpx.get("https://plex.tv/users/account", headers={"X-Plex-Token": auth_token})
    # if user_info.status_code != 200:
    #     raise HTTPException(status_code=401, detail="Invalid Plex token")

    # plex_user = user_info.json()["user"]

    # user_id, new_user = get_or_create_user(
    #     username=plex_user["username"],
    #     email=plex_user.get("email"),
    #     token=auth_token
    # )

    # return RedirectResponse(url=f"/welcome?user={plex_user['username']}")

@router.get("/initiate")
def initiate_login(request: Request, pin_id: Optional[int] = None):
    from api.services.plex_service import create_plex_pin, get_existing_pin  # assuming you define this

    if pin_id:
        pin = get_existing_pin(pin_id)  # 🔁 You'll implement this
    else:
        pin = create_plex_pin()
        print("DEBUG PLEX PIN:", pin)


    client_id = pin["clientIdentifier"]
    code = pin["code"]
    real_pin_id = pin["id"]

    base_url = str(request.base_url).rstrip("/")
    forward_url = f"{base_url}/post-login?pin_id={real_pin_id}"

    redirect_url = (
        f"https://app.plex.tv/auth#"
        f"?clientID={client_id}"
        f"&code={code}"
        f"&context%5Bdevice%5D%5Bproduct%5D={PLEX_PRODUCT}"
        f"&forwardUrl={forward_url}"
    )

    return {
        "pin_id": real_pin_id,
        "code": code,
        "redirect_url": redirect_url
    }

from fastapi import Request
from fastapi.responses import JSONResponse

@router.get("/status/{pin_id}")
def check_auth_status(pin_id: int, request: Request):
    token = poll_plex_pin(pin_id)
    if token:
        request.session["plex_token"] = token
        return {"authenticated": True, "auth_token": token}  # 👈 ADD auth_token here
    return {"authenticated": False}






