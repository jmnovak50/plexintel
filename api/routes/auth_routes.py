# auth_routes.py
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from api.services.plex_service import create_plex_pin, poll_plex_pin, get_plex_user_info
from api.db.users import get_or_create_user

router = APIRouter()

class AuthStartResponse(BaseModel):
    code: str
    pin_id: int
    verification_url: str

@router.get("/start", response_model=AuthStartResponse)
def start_auth():
    pin = create_plex_pin()
    return {
        "code": pin["code"],
        "pin_id": pin["id"],
        "verification_url": f"https://plex.tv/link?code={pin['code']}"
    }

class AuthStatusResponse(BaseModel):
    user_id: int
    username: str
    new_user: bool

@router.get("/status/{pin_id}")
def check_auth_status(pin_id: int, request: Request):
    from api.services.plex_service import poll_plex_pin
    token = poll_plex_pin(pin_id)
    if token:
        request.session["plex_token"] = token
        plex_user = get_plex_user_info(token)
        if not plex_user or not plex_user.get("username"):
            raise HTTPException(status_code=401, detail="Failed to resolve Plex user")

        user_id, new_user = get_or_create_user(
            username=plex_user["username"],
            email=plex_user.get("email"),
            token=token,
        )
        request.session["username"] = plex_user["username"]
        request.session["user_id"] = user_id
        return {
            "authenticated": True,
            "auth_token": token,  # ✅ This must exist for frontend redirect
            "username": plex_user["username"],
            "user_id": user_id,
            "new_user": new_user,
        }
    return {"authenticated": False}
