from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.routes.admin_routes import get_current_user, require_admin
from api.services.digest_service import (
    DigestConfigError,
    generate_digest_preview,
    get_digest_content,
    get_digest_history,
    get_unsubscribe_target,
    get_user_email_preferences,
    save_digest_content,
    send_test_digest,
    unsubscribe_by_token,
    update_user_email_preferences,
)

router = APIRouter()


class DigestContentUpdateRequest(BaseModel):
    message_html: str = ""


class DigestPreviewRequest(BaseModel):
    sample_username: str
    message_html: str | None = None


class DigestTestSendRequest(BaseModel):
    target: str = Field(default="self")
    sample_username: str
    message_html: str | None = None


class EmailPreferenceUpdateRequest(BaseModel):
    digest_enabled: bool


@router.get("/admin/digest/content")
def admin_get_digest_content(admin_user=Depends(require_admin)):
    return {
        "requested_by": admin_user["username"],
        **get_digest_content(),
    }


@router.put("/admin/digest/content")
def admin_save_digest_content(req: DigestContentUpdateRequest, admin_user=Depends(require_admin)):
    try:
        content = save_digest_content(req.message_html, admin_user["username"])
    except DigestConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "requested_by": admin_user["username"],
        **content,
    }


@router.post("/admin/digest/preview")
def admin_preview_digest(req: DigestPreviewRequest, admin_user=Depends(require_admin)):
    try:
        preview = generate_digest_preview(req.sample_username, message_html=req.message_html)
    except DigestConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed generating digest preview: {exc}") from exc

    return {
        "requested_by": admin_user["username"],
        **preview,
    }


@router.post("/admin/digest/test-send")
def admin_test_send_digest(req: DigestTestSendRequest, admin_user=Depends(require_admin)):
    try:
        result = send_test_digest(
            target=req.target,
            sample_username=req.sample_username,
            triggered_by=admin_user["username"],
            message_html=req.message_html,
        )
    except DigestConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Digest test send failed: {exc}") from exc

    return {
        "requested_by": admin_user["username"],
        **result,
    }


@router.get("/admin/digest/history")
def admin_digest_history(admin_user=Depends(require_admin)):
    history = get_digest_history()
    return {
        "requested_by": admin_user["username"],
        **history,
    }


@router.get("/me/email-preferences")
def my_email_preferences(user=Depends(get_current_user)):
    prefs = get_user_email_preferences(user["user_id"])
    display_name = user.get("friendly_name") or user["username"]
    return {
        "username": user["username"],
        "friendly_name": user.get("friendly_name"),
        "display_name": display_name,
        "email": user.get("plex_email"),
        "has_email": bool((user.get("plex_email") or "").strip()),
        "digest_enabled": bool(prefs["digest_enabled"]),
    }


@router.put("/me/email-preferences")
def update_my_email_preferences(req: EmailPreferenceUpdateRequest, user=Depends(get_current_user)):
    prefs = update_user_email_preferences(user["user_id"], digest_enabled=req.digest_enabled)
    return {
        "username": user["username"],
        "email": user.get("plex_email"),
        "has_email": bool((user.get("plex_email") or "").strip()),
        "digest_enabled": bool(prefs["digest_enabled"]),
    }


@router.get("/digest/unsubscribe/{token}")
def get_unsubscribe_details(token: str):
    target = get_unsubscribe_target(token)
    if not target:
        raise HTTPException(status_code=404, detail="Unsubscribe link is invalid or expired.")

    display_name = target.get("friendly_name") or target.get("username")
    return {
        "username": target["username"],
        "display_name": display_name,
        "email": target.get("plex_email"),
        "digest_enabled": bool(target.get("digest_enabled")),
    }


@router.post("/digest/unsubscribe/{token}")
def unsubscribe_via_link(token: str):
    target = unsubscribe_by_token(token)
    if not target:
        raise HTTPException(status_code=404, detail="Unsubscribe link is invalid or expired.")

    display_name = target.get("friendly_name") or target.get("username")
    return {
        "username": target["username"],
        "display_name": display_name,
        "email": target.get("plex_email"),
        "digest_enabled": bool(target.get("digest_enabled")),
    }
