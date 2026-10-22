"""REST identity verification; MCP authentication does not authorize this router."""
from dataclasses import dataclass
import hmac
import logging
import math
import time
import os
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPBearer
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services import mcp_auth
from api.services.private_config import PrivateConfigError, read_private_token

logger = logging.getLogger(__name__)
READ = 'plexintel.read'
READ_ALL = 'plexintel.read_all'
FEEDBACK = 'plexintel.feedback'
agent_bearer = HTTPBearer(auto_error=False, scheme_name='PlexIntelAgentBearer')


@dataclass(frozen=True)
class AgentPrincipal:
    method: str
    username: str | None = None
    is_admin: bool = False
    scopes: frozenset[str] = frozenset({READ})

    @property
    def can_read_all(self):
        return self.is_admin or (self.method == 'service' and READ_ALL in self.scopes)


def _deny(status=401, detail='Authentication required'):
    raise HTTPException(status, detail, headers={'WWW-Authenticate': 'Bearer'} if status==401 else None)


def require_agent_principal(request: Request, _bearer=Security(agent_bearer)) -> AgentPrincipal:
    authorization = request.headers.get('authorization')
    if authorization is not None:
        parts = authorization.split()
        if len(parts)!=2 or parts[0].lower()!='bearer':
            _deny()
        token = parts[1]
        credential_file = os.getenv('PLEXINTEL_AGENT_SERVICE_TOKEN_FILE')
        if credential_file:
            try:
                credential = read_private_token(credential_file)
            except PrivateConfigError:
                logger.error('Agent REST service credential configuration is invalid')
                _deny(503,'Authentication configuration unavailable')
            if hmac.compare_digest(token.encode(), credential.encode()):
                scopes=frozenset(os.getenv('PLEXINTEL_AGENT_SERVICE_SCOPES', READ).split())
                if READ not in scopes or not scopes <= {READ,READ_ALL}:
                    _deny(503,'Service scopes are not configured correctly')
                return AgentPrincipal('service',scopes=scopes)
        try:
            validation=mcp_auth.validate_bearer_token(token)
        except Exception:
            logger.error('Agent REST OAuth validation unavailable')
            _deny(503,'Authentication service unavailable')
        if validation.status == mcp_auth.MCPTokenStatus.CONFIGURATION_ERROR:
            _deny(503,'Authentication service unavailable')
        if validation.status == mcp_auth.MCPTokenStatus.INSUFFICIENT_SCOPE:
            _deny(403,'Insufficient scope')
        if validation.status != mcp_auth.MCPTokenStatus.VALID or not validation.context:
            _deny(403 if validation.status == mcp_auth.MCPTokenStatus.UNMAPPED_EMAIL else 401,
                  'Identity is not linked' if validation.status == mcp_auth.MCPTokenStatus.UNMAPPED_EMAIL else 'Invalid or expired credential')
        claims=validation.claims or {}
        # PyJWT checks expiration when present; REST also requires its presence.
        if not isinstance(claims.get('exp'),(int,float)) or isinstance(claims.get('exp'),bool) or not math.isfinite(claims['exp']) or claims['exp'] <= time.time():
            _deny(401,'Access token requires an expiration')
        scopes=frozenset(mcp_auth._extract_scopes(claims))
        context=validation.context
        if not context.plex_username or READ not in scopes:
            _deny(403,'Identity or scope is insufficient')
        return AgentPrincipal('jwt',context.plex_username,context.is_admin,scopes)

    # No forwarded email/user header or network address is an identity credential.
    session=request.scope.get('session') or {}
    if session.get('username') and session.get('user_id') and session.get('plex_token'):
        if not getattr(request.app.state, 'agent_session_auth_enabled', False):
            _deny(503,'Secure browser sessions are not configured')
        try:
            conn=connect_db(cursor_factory=RealDictCursor)
            try:
                with conn.cursor() as cur:
                    cur.execute('SELECT username, COALESCE(is_admin,false) AS is_admin FROM users WHERE username=%s AND user_id=%s',
                                (session['username'],session['user_id']))
                    user=cur.fetchone()
            finally:
                conn.close()
        except Exception:
            logger.error('Agent REST session identity lookup failed')
            _deny(503,'Authentication service unavailable')
        if user:
            return AgentPrincipal('session',user['username'],bool(user['is_admin']))
    _deny()


def authorize_user(principal, requested=None, *, all_users=False):
    requested=(requested or '').strip() or None
    if all_users:
        if requested is not None:
            raise HTTPException(400,'Specify user or all_users, not both')
        if not principal.can_read_all:
            _deny(403,'All-user access requires administrative or service entitlement')
        return None
    if requested is None:
        if principal.username:
            return principal.username
        raise HTTPException(400,'Specify an explicit user or all_users=true')
    if not principal.can_read_all and requested!=principal.username:
        _deny(403,'Not authorized for the requested user')
    return requested


def authorize_feedback(request,principal,username):
    if principal.method=='service':
        _deny(403,'Read-only service credentials cannot submit feedback')
    authorize_user(principal,username)
    if principal.method=='jwt' and FEEDBACK not in principal.scopes:
        _deny(403,'Feedback scope required')
    if principal.method=='session':
        origin=urlsplit(request.headers.get('origin',''))
        target=urlsplit(str(request.base_url))
        if (origin.scheme,origin.netloc)!=(target.scheme,target.netloc):
            _deny(403,'Same-origin browser request required')


def sanitize_agent_errors(function):
    """Sanitize related REST failures without logging SQL, credentials or payloads."""
    import functools
    import uuid
    @functools.wraps(function)
    def wrapped(*args,**kwargs):
        try:
            return function(*args,**kwargs)
        except HTTPException:
            raise
        except Exception as exc:
            incident=uuid.uuid4().hex[:12]
            logger.error('Agent REST request failed incident=%s operation=%s exception_class=%s sqlstate=%s',
                         incident,function.__name__,type(exc).__name__,getattr(exc,'pgcode',None))
            raise HTTPException(500,detail={'message':'Request could not be completed','incident':incident}) from None
    return wrapped
