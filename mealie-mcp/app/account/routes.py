from __future__ import annotations

import hmac
import html
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import IntegrityError

from app.account.store import AccountStore, BrowserSession
from app.auth.account_oidc import AccountOIDC, AccountOIDCError, new_oauth_values
from app.auth.principal import Principal, principal_from_validated_identity
from app.config import Settings
from app.mealie.errors import MealieError, MealieNotFound
from app.services.connections import ConnectionCreate, ConnectionService, ConnectionView

SESSION_COOKIE = "mealie_mcp_account"
STATE_COOKIE = "mealie_mcp_oauth_state"
_SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}


def account_router(
    settings: Settings,
    store: AccountStore,
    oidc: AccountOIDC,
    connections: ConnectionService,
) -> APIRouter:
    router = APIRouter()

    @router.get("/account", response_class=HTMLResponse)
    async def account(request: Request) -> Response:
        session = await store.get_session(request.cookies.get(SESSION_COOKIE))
        if session is None:
            return _redirect("/account/login")
        return await _account_page(connections, _principal(settings, session), session)

    @router.get("/account/login")
    async def login() -> Response:
        state, nonce, verifier = new_oauth_values()
        await store.create_oauth_state(
            state,
            nonce,
            verifier,
            settings.account_oauth_state_ttl_seconds,
        )
        try:
            url = await oidc.authorization_url(state, nonce, verifier)
        except AccountOIDCError:
            return _error_page("Account sign-in is temporarily unavailable", 503)
        response = _redirect(url)
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
        cookie_state = request.cookies.get(STATE_COOKIE)
        if not state or not cookie_state or not hmac.compare_digest(state, cookie_state):
            return _callback_error(settings, "OIDC callback validation failed", 400)
        oauth_state = await store.consume_oauth_state(state)
        if oauth_state is None:
            return _callback_error(settings, "OIDC state is invalid or expired", 400)
        code = request.query_params.get("code")
        if request.query_params.get("error") or not code or len(code) > 4096:
            return _callback_error(settings, "OIDC sign-in was not completed", 400)
        try:
            id_token = await oidc.exchange_code(code, oauth_state.code_verifier)
            claims = await oidc.verify_id_token(id_token, oauth_state.nonce)
        except AccountOIDCError:
            claims = None
        subject = claims.get("sub") if claims is not None else None
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            return _callback_error(settings, "OIDC ID token validation failed", 400)
        session_token = await store.create_session(
            subject=subject,
            issuer=oidc.issuer,
            email=_optional_text(claims.get("email"), limit=320),
            preferred_username=_optional_text(claims.get("preferred_username"), limit=255),
            ttl_seconds=settings.account_session_ttl_seconds,
        )
        response = _redirect("/account")
        response.delete_cookie(
            STATE_COOKIE,
            path="/account/callback",
            secure=settings.account_cookie_secure,
            httponly=True,
            samesite="lax",
        )
        response.set_cookie(
            SESSION_COOKIE,
            session_token,
            max_age=settings.account_session_ttl_seconds,
            secure=settings.account_cookie_secure,
            httponly=True,
            samesite="lax",
            path="/account",
        )
        return response

    @router.post("/account/connect", response_class=HTMLResponse)
    async def connect(request: Request) -> Response:
        session = await store.get_session(request.cookies.get(SESSION_COOKIE))
        if session is None:
            return _redirect("/account/login")
        principal = _principal(settings, session)
        form = await request.form()
        if not _valid_csrf(session, form.get("csrf_token")):
            return _error_page("CSRF validation failed", 403)
        token = _form_text(form.get("api_token"), limit=4096)
        base_url = _form_text(form.get("base_url"), limit=2048)
        name = _form_text(form.get("name"), limit=120) or "Home"
        if not token or not base_url:
            return await _account_page(
                connections,
                principal,
                session,
                "Mealie URL and API token are required",
                400,
            )
        try:
            await connections.create(
                principal,
                ConnectionCreate(
                    name=name,
                    base_url=base_url,
                    api_token=SecretStr(token),
                    is_default=True,
                ),
            )
        except (MealieError, ValidationError, IntegrityError, ValueError):
            return await _account_page(
                connections,
                principal,
                session,
                "Mealie connection validation failed. Check the URL, token, and connection name.",
                422,
            )
        return _redirect("/account")

    @router.post("/account/disconnect", response_class=HTMLResponse)
    async def disconnect(request: Request) -> Response:
        authenticated = await _authenticated_form(request, settings, store)
        if isinstance(authenticated, Response):
            return authenticated
        session, principal, form = authenticated
        connection_id = _connection_id(form.get("connection_id"))
        if connection_id is None:
            return _error_page("Invalid connection identifier", 400)
        try:
            await connections.delete(principal, connection_id)
        except MealieNotFound:
            return await _account_page(connections, principal, session, "Mealie connection not found", 404)
        return _redirect("/account")

    @router.post("/account/validate", response_class=HTMLResponse)
    async def validate(request: Request) -> Response:
        authenticated = await _authenticated_form(request, settings, store)
        if isinstance(authenticated, Response):
            return authenticated
        session, principal, form = authenticated
        connection_id = _connection_id(form.get("connection_id"))
        if connection_id is None:
            return _error_page("Invalid connection identifier", 400)
        try:
            await connections.validate(principal, connection_id)
        except MealieNotFound:
            return await _account_page(connections, principal, session, "Mealie connection not found", 404)
        except (MealieError, ValueError):
            return await _account_page(
                connections,
                principal,
                session,
                "Mealie connection revalidation failed",
                422,
            )
        return _redirect("/account")

    return router


async def _authenticated_form(
    request: Request,
    settings: Settings,
    store: AccountStore,
) -> tuple[BrowserSession, Principal, Any] | Response:
    session = await store.get_session(request.cookies.get(SESSION_COOKIE))
    if session is None:
        return _redirect("/account/login")
    form = await request.form()
    if not _valid_csrf(session, form.get("csrf_token")):
        return _error_page("CSRF validation failed", 403)
    return session, _principal(settings, session), form


def _principal(settings: Settings, session: BrowserSession) -> Principal:
    return principal_from_validated_identity(
        namespace=settings.identity_namespace,
        default_tenant_id=settings.default_tenant_id,
        subject=session.subject,
        issuer=session.issuer,
        email=session.email,
    )


def _valid_csrf(session: BrowserSession, supplied: Any) -> bool:
    return isinstance(supplied, str) and hmac.compare_digest(session.csrf_token, supplied)


async def _account_page(
    connections: ConnectionService,
    principal: Principal,
    session: BrowserSession,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    values = await connections.list(principal)
    rendered = []
    for value in values:
        capabilities = await connections.capability_names(principal, value.id)
        rendered.append(_connection_html(value, capabilities, session.csrf_token))
    message = f'<p class="error">{html.escape(error)}</p>' if error else ""
    identity = session.preferred_username or session.email or session.subject
    connections_html = "".join(rendered) or "<p><strong>Mealie:</strong> Not connected</p>"
    document = f"""<!doctype html><html><head><meta charset="utf-8">
    <meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Mealie MCP Account</title><style>body{{font:16px system-ui;max-width:48rem;margin:3rem auto;padding:0 1rem}}
    label,input,button{{font:inherit}}input{{display:block;width:100%;padding:.6rem;margin:.4rem 0 1rem;box-sizing:border-box}}
    button{{padding:.6rem 1rem;margin-right:.4rem}}.error{{color:#a00}}dt{{font-weight:700}}dd{{margin:0 0 .7rem}}
    section{{border:1px solid #ccc;border-radius:.4rem;padding:1rem;margin:1rem 0}}</style></head><body>
    <h1>Mealie MCP Account</h1><p><strong>Authentik identity:</strong> {html.escape(identity)}</p>{message}
    {connections_html}<section><h2>Connect Mealie</h2><form method="post" action="/account/connect" autocomplete="off">
    <input type="hidden" name="csrf_token" value="{html.escape(session.csrf_token)}">
    <label>Mealie URL <input type="url" name="base_url" required placeholder="https://mealie.example.com"></label>
    <label>Mealie API Token <input type="password" name="api_token" required autocomplete="new-password"></label>
    <label>Connection Name <input type="text" name="name" value="Home" maxlength="120" required></label>
    <button type="submit">Connect Mealie</button></form></section></body></html>"""
    return _secure(HTMLResponse(document, status_code=status_code))


def _connection_html(value: ConnectionView, capabilities: list[str], csrf: str) -> str:
    capability_items = "".join(f"<li>{html.escape(item)}</li>" for item in capabilities)
    validated = value.last_validated_at.isoformat() if value.last_validated_at else "Not yet"
    return f"""<section><h2>{html.escape(value.name)}</h2><p><strong>Mealie:</strong> Connected</p><dl>
    <dt>Server</dt><dd>{html.escape(value.base_url)}</dd><dt>Status</dt><dd>{html.escape(value.status.value)}</dd>
    <dt>Version</dt><dd>{html.escape(value.mealie_version or "Unknown")}</dd>
    <dt>Last validated</dt><dd>{html.escape(validated)}</dd></dl><h3>Capabilities</h3><ul>{capability_items}</ul>
    <form method="post" action="/account/validate"><input type="hidden" name="csrf_token" value="{html.escape(csrf)}">
    <input type="hidden" name="connection_id" value="{value.id}"><button type="submit">Revalidate</button></form>
    <form method="post" action="/account/disconnect"><input type="hidden" name="csrf_token" value="{html.escape(csrf)}">
    <input type="hidden" name="connection_id" value="{value.id}"><button type="submit">Disconnect</button></form></section>"""


def _connection_id(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _form_text(value: Any, *, limit: int) -> str:
    return str(value).strip()[:limit] if isinstance(value, str) else ""


def _optional_text(value: Any, *, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:limit]


def _redirect(location: str) -> RedirectResponse:
    return _secure(RedirectResponse(location, status_code=303))


def _callback_error(settings: Settings, message: str, status_code: int) -> HTMLResponse:
    response = _error_page(message, status_code)
    response.delete_cookie(
        STATE_COOKIE,
        path="/account/callback",
        secure=settings.account_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


def _error_page(message: str, status_code: int) -> HTMLResponse:
    return _secure(
        HTMLResponse(
            '<!doctype html><html><head><meta charset="utf-8"><title>Mealie MCP Account</title>'
            f"</head><body><h1>Account error</h1><p>{html.escape(message)}</p></body></html>",
            status_code=status_code,
        )
    )


def _secure(response: Response) -> Any:
    response.headers.update(_SECURITY_HEADERS)
    return response
