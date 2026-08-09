# Open WebUI MCP OAuth Setup

PlexIntel can identify the active Open WebUI user for MCP tool calls and map their email to a Plex username via `users.plex_email`.

## Important: Open WebUI MCP Auth Options

Open WebUI MCP connections support **Bearer**, **OAuth 2.1**, and **OAuth 2.1 (Static)**. They do **not** expose the `system_oauth` mode used by OpenAI-compatible connections.

That means the practical Open WebUI setup for PlexIntel today is:

| Field | Value |
|-------|-------|
| Type | MCP Streamable HTTP |
| URL | `http://192.168.1.9:8489/mcp/` |
| Auth | **Bearer** |
| Key | Your PlexIntel `MCP_API_KEY` |
| Custom Headers | `{"X-OpenWebUI-User-Email": "{{USER_EMAIL}}"}` |

Open WebUI expands `{{USER_EMAIL}}` to the logged-in user's email on each MCP request. PlexIntel uses that header to resolve `jmnovak` from `jason@sheffieldave.com`.

Requires Open WebUI **v0.9.6+** for MCP custom-header template expansion.

## Prerequisites

On the Raspberry Pi running PlexIntel:

```env
MCP_ENABLED=true
MCP_AUTH_MODE=jwt_or_static
MCP_OAUTH_ISSUER_URL=https://auth.kabolly.com/application/o/<dedicated-chatgpt-provider>/
MCP_OAUTH_RESOURCE_URL=https://plexintel.kabolly.com/mcp/
MCP_OAUTH_AUDIENCE=https://plexintel.kabolly.com/mcp/
MCP_OAUTH_REQUIRED_SCOPES=plexintel.read
MCP_OAUTH_EMAIL_CLAIM=email
MCP_TRUSTED_USER_EMAIL_HEADER=X-OpenWebUI-User-Email
MCP_API_KEY=replace-me
```

Admin UI equivalents:

- MCP Auth Mode: `jwt_or_static`
- MCP OAuth Issuer URL: the dedicated ChatGPT Authentik provider issuer
- Trusted User Email Header: `X-OpenWebUI-User-Email`

Verify each household user has a synced Plex email:

```sql
SELECT username, plex_email FROM users ORDER BY username;
```

Example mapping:

```text
username | plex_email
---------|-------------------------
jmnovak  | jason@sheffieldave.com
```

## Why Use Bearer Auth in Open WebUI?

PlexIntel now implements the OAuth resource-server surface for ChatGPT, but Open WebUI does not need to participate in that browser flow. Its existing Bearer integration remains simpler and preserves per-user mapping through its header template.

If Open WebUI sends only the static service key without the custom header, PlexIntel receives **no user identity**. That produces errors like:

```text
user is required when MCP auth does not provide a mapped Plex user
```

Use **Bearer + `{{USER_EMAIL}}` header** instead.

## Optional JWT Path

PlexIntel validates Authentik JWTs directly for ChatGPT. The trusted Open WebUI email header is ignored for JWT-authenticated requests: JWT identity always comes from the verified token. An unmapped JWT email cannot be replaced with the header.

If you do send JWTs:

- Issuer must match `MCP_OAUTH_ISSUER_URL` (trailing slash differences are tolerated)
- Audience must match `MCP_OAUTH_AUDIENCE`, or the resource URL when that override is blank
- Every application scope in `MCP_OAUTH_REQUIRED_SCOPES` must be present

Changing PlexIntel's JWT issuer to the dedicated ChatGPT Authentik provider does not affect Open WebUI's static-key path. Both clients coexist when `MCP_AUTH_MODE=jwt_or_static`: ChatGPT uses a JWT, while Open WebUI uses the opaque `MCP_API_KEY` plus its trusted email header.

## Migration Path

1. Keep `MCP_AUTH_MODE=jwt_or_static`
2. In Open WebUI MCP connection:
   - Auth: **Bearer**
   - Key: PlexIntel `MCP_API_KEY`
   - Headers: `{"X-OpenWebUI-User-Email": "{{USER_EMAIL}}"}`
3. Restart/reload PlexIntel if needed
4. Ask in chat: "What are my top 10 recommended movies?"
5. Confirm PlexIntel logs show the caller email instead of only the client IP

## Expected Behavior

After setup:

- "What should I watch?" auto-scopes to the authenticated Plex user
- The LLM does not need to pass a `user` argument for first-person requests
- Non-admin users cannot query another user's recommendations or watch history
- Admin users (`users.is_admin = true`) can still query other users explicitly

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `No authenticated Plex user is mapped for this MCP request` | Missing custom header `{"X-OpenWebUI-User-Email": "{{USER_EMAIL}}"}` or Open WebUI version < 0.9.6 |
| `No Plex user found for jason@sheffieldave.com` | `plex_email` not synced for that Authentik email |
| Tool works but asks who you are | MCP auth succeeded as static service token only; header not forwarded |
| OAuth 2.1 selected in Open WebUI | Use the established Bearer + header configuration unless you intentionally configure a separate Open WebUI OAuth flow |
| `401 Invalid or expired MCP bearer token` | A JWT-shaped token was sent but failed validation; check issuer URL |

To inspect what PlexIntel receives, check backend logs for MCP request lines. Successful user mapping logs the caller email.
