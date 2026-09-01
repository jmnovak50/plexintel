import hmac
import html
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.auth.account_oidc import AccountOIDC, new_oauth_values
from app.config import Settings
from app.credentials.models import BrowserIdentity, BrowserSession
from app.credentials.sqlite import SQLiteCredentialProvider
from app.immich.client import ImmichClient, ImmichError, InvalidImmichCredential
from app.immich.models import PrivateImmichCredential

SESSION_COOKIE = "immich_mcp_account"
STATE_COOKIE = "immich_mcp_oauth_state"


def account_router(
    settings: Settings,
    provider: SQLiteCredentialProvider,
    client: ImmichClient,
    oidc: AccountOIDC,
) -> APIRouter:
    router = APIRouter()

    @router.get("/account", response_class=HTMLResponse)
    async def account(request: Request) -> Response:
        session = await provider.browser_session(request.cookies.get(SESSION_COOKIE))
        if session is None:
            return RedirectResponse("/account/login", status_code=303)
        status = await provider.status_for(session.identity)
        return _account_page(session, status)

    @router.get("/account/login")
    async def login() -> RedirectResponse:
        state, nonce, verifier = new_oauth_values()
        await provider.create_oauth_state(
            state, nonce, verifier, settings.account_oauth_state_ttl_seconds
        )
        url = await oidc.authorization_url(state, nonce, verifier)
        response = RedirectResponse(url, status_code=303)
        response.set_cookie(
            STATE_COOKIE,
            state,
            max_age=settings.account_oauth_state_ttl_seconds,
            secure=settings.account_cookie_secure,
            httponly=True,
            samesite="lax",
            path="/account/callback",
        )
        return response

    @router.get("/account/callback")
    async def callback(request: Request) -> Response:
        state = request.query_params.get("state")
        code = request.query_params.get("code")
        cookie_state = request.cookies.get(STATE_COOKIE)
        if (
            not state
            or not code
            or not cookie_state
            or not hmac.compare_digest(state, cookie_state)
            or request.query_params.get("error")
        ):
            return _error_page("OIDC callback validation failed", 400)
        oauth_state = await provider.consume_oauth_state(state)
        if oauth_state is None:
            return _error_page("OIDC state is invalid or expired", 400)
        try:
            token = await oidc.exchange_code(code, oauth_state.code_verifier)
            id_token = token.get("id_token")
            if not isinstance(id_token, str):
                return _error_page("OIDC provider did not return an ID token", 400)
            claims = await oidc.verifier.verify_id_token(
                id_token,
                audience=str(settings.account_oidc_client_id),
                nonce=oauth_state.nonce,
            )
        except Exception:
            return _error_page("OIDC sign-in could not be completed", 400)
        if claims is None:
            return _error_page("OIDC ID token validation failed", 400)
        identity = BrowserIdentity(
            identity_namespace=settings.identity_namespace,
            issuer=str(claims["iss"]),
            subject=str(claims["sub"]),
            email=_optional_text(claims.get("email")),
            preferred_username=_optional_text(claims.get("preferred_username")),
        )
        session_id, _ = await provider.create_browser_session(
            identity, settings.account_session_ttl_seconds
        )
        response = RedirectResponse("/account", status_code=303)
        response.delete_cookie(STATE_COOKIE, path="/account/callback")
        response.set_cookie(
            SESSION_COOKIE,
            session_id,
            max_age=settings.account_session_ttl_seconds,
            secure=settings.account_cookie_secure,
            httponly=True,
            samesite="lax",
            path="/account",
        )
        return response

    @router.post("/account/connect", response_class=HTMLResponse)
    async def connect(request: Request) -> Response:
        session = await provider.browser_session(request.cookies.get(SESSION_COOKIE))
        if session is None:
            return RedirectResponse("/account/login", status_code=303)
        form = await request.form()
        if not _valid_csrf(session, form.get("csrf_token")):
            return _error_page("CSRF validation failed", 403)
        raw_key = form.get("api_key")
        api_key = str(raw_key).strip() if raw_key is not None else ""
        if not api_key:
            return _account_page(
                session, await provider.status_for(session.identity), "API key is required", 400
            )
        credential = PrivateImmichCredential(kind="api_key", token=api_key)
        try:
            immich_user = await client.get_current_user(credential)
        except InvalidImmichCredential:
            return _account_page(
                session, await provider.status_for(session.identity), "Immich rejected this API key", 400
            )
        except ImmichError:
            return _account_page(
                session,
                await provider.status_for(session.identity),
                "Immich could not validate this key or the key lacks user.read permission",
                502,
            )
        await provider.store_api_key(session.identity, api_key, immich_user)
        return RedirectResponse("/account", status_code=303)

    @router.post("/account/disconnect")
    async def disconnect(request: Request) -> Response:
        session = await provider.browser_session(request.cookies.get(SESSION_COOKIE))
        if session is None:
            return RedirectResponse("/account/login", status_code=303)
        form = await request.form()
        if not _valid_csrf(session, form.get("csrf_token")):
            return _error_page("CSRF validation failed", 403)
        await provider.delete_for(session.identity)
        return RedirectResponse("/account", status_code=303)

    return router


def _valid_csrf(session: BrowserSession, supplied: Any) -> bool:
    return isinstance(supplied, str) and hmac.compare_digest(session.csrf_token, supplied)


def _account_page(
    session: BrowserSession, status: Any, error: str | None = None, status_code: int = 200
) -> HTMLResponse:
    identity = session.identity.preferred_username or session.identity.email or session.identity.subject
    message = f'<p class="error">{html.escape(error)}</p>' if error else ""
    if status is None:
        immich = f"""
        <p><strong>Immich:</strong> Not connected</p>
        <form method="post" action="/account/connect" autocomplete="off">
          <input type="hidden" name="csrf_token" value="{html.escape(session.csrf_token)}">
          <label>Immich API Key <input type="password" name="api_key" required autocomplete="off"></label>
          <button type="submit">Connect Immich</button>
        </form>"""
    else:
        immich = f"""
        <p><strong>Immich:</strong> Connected</p>
        <dl><dt>User</dt><dd>{html.escape(status.immich_name or status.immich_user_id or "Unknown")}</dd>
        <dt>Email</dt><dd>{html.escape(status.immich_email or "Not provided")}</dd>
        <dt>Validated on connect</dt><dd>{html.escape(status.validated_at_on_connect.isoformat())}</dd></dl>
        <p>Disconnecting removes this API key from Immich MCP. It does not delete the key from Immich.</p>
        <form method="post" action="/account/disconnect">
          <input type="hidden" name="csrf_token" value="{html.escape(session.csrf_token)}">
          <button type="submit">Disconnect Immich</button>
        </form>"""
    document = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="referrer" content="no-referrer">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>Immich MCP Account</title>
    <style>body{{font:16px system-ui;max-width:42rem;margin:3rem auto;padding:0 1rem}}label,input,button{{font:inherit}}input{{display:block;width:100%;padding:.6rem;margin:.4rem 0 1rem;box-sizing:border-box}}button{{padding:.6rem 1rem}}.error{{color:#a00}}dt{{font-weight:700}}dd{{margin:0 0 .7rem}}</style></head>
    <body><h1>Immich MCP Account</h1><p><strong>Authentik identity:</strong> {html.escape(identity)}</p>
    {message}{immich}</body></html>"""
    return HTMLResponse(
        document,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _error_page(message: str, status_code: int) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><title>Immich MCP Account</title><h1>Account error</h1><p>{html.escape(message)}</p>",
        status_code=status_code,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)
