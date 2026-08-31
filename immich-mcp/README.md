# Immich MCP

A thin, typed Python MCP resource server for Immich. Phase 1 exposes public album shares; `/mcp` is protected by Authentik OAuth/OIDC. It deliberately does **not** translate Authentik tokens into private Immich access because current Immich has no supported per-user token exchange.

## 1. Architecture

FastAPI hosts health/readiness, public share helpers, and a no-JavaScript gallery. MCP Python SDK 2.1 provides stateless Streamable HTTP at `/mcp` and RFC 9728 protected-resource metadata. `ImmichClient` is the only layer that calls Immich and uses async `httpx`.

See [architecture.md](architecture.md) for the researched auth decision and source links.

```text
ChatGPT/OpenWebUI -> Authentik Authorization Code + PKCE -> access token
ChatGPT/OpenWebUI -> /mcp (Bearer token) -> validated sub/scopes -> MCP tools
public share key  -> typed ImmichClient -> configured IMMICH_BASE_URL only
```

## 2. Security model

* Authentik signs users in and issues audience-restricted access tokens. This server validates discovery issuer, JWKS signature/algorithm, `iss`, `aud`, `exp`, `nbf`, and scopes.
* `sub` is the user identity. `email` and `preferred_username` are attributes only.
* `/mcp` requires `immich.read`; health and public share routes do not. Public routes still require an existing Immich share capability and cannot expand it.
* A supplied share URL must exactly match the configured Immich origin. Only the extracted key is used; the supplied URL is never fetched.
* There is no global Immich API key, admin impersonation, browser-cookie scraping, or external bearer-token forwarding.
* Tokens and keys are not logged by application code. The container disables Uvicorn access logging because routes containing share keys would otherwise log them. Configure reverse-proxy access-log redaction too.
* TLS verification is on by default. Disabling it is intended only for a controlled development CA scenario.

## 3. Authentik setup

Create a dedicated Authentik OAuth2/OpenID Provider for the MCP resource; do not reuse Immich's own OIDC client.

1. Create an OAuth2/OpenID Provider using Authorization Code. Require PKCE (`S256`) for public clients; use a confidential client for OpenWebUI static OAuth.
2. Set the exact redirect URIs shown by each MCP client. ChatGPT provides its callback during custom-app creation. OpenWebUI uses its configured public `WEBUI_URL` callback and registers/uses the static client through its Integration UI.
3. Add a scope mapping named `immich.read`; ensure it is emitted in the access token's `scope` claim.
4. Configure the access-token audience as the value used for `OIDC_AUDIENCE` (typically `immich-mcp`). The access token—not merely the ID token—must be a signed JWT with this audience.
5. Include standard `sub`; optionally map `email` and `preferred_username`.
6. If the client needs long-lived connectivity, enable refresh tokens and advertise/allow `offline_access` in Authentik. Add it to the client request without adding it to `OIDC_REQUIRED_SCOPE`.
7. Set `OIDC_ISSUER` to the exact discovery issuer, normally `https://auth.example.com/application/o/immich-mcp/`. Confirm `${OIDC_ISSUER}.well-known/openid-configuration` returns the same exact `issuer` and an issuer-hosted `jwks_uri`.

`OIDC_CLIENT_ID` identifies the expected MCP application/client configuration and is the default audience. `OIDC_CLIENT_SECRET` is accepted for deployment parity but is not used by this resource server to validate JWTs; the OAuth client (ChatGPT/OpenWebUI) holds its own secret when confidential.

## 4. Immich assumptions

Immich is an upstream API and is not modified. Album shares must support:

* `GET /api/shared-links/me` with `x-immich-share-key`
* `GET /api/timeline/buckets` and `/api/timeline/bucket` with the same share header
* `GET /api/assets/{id}` under share authorization
* `GET /api/assets/{id}/thumbnail?key=...`

The implementation intentionally ignores an empty embedded `assets` list for album shares and enumerates the timeline. Password-protected share login is not implemented.

## 5. Environment variables

Copy `.env.example` to `.env`. Required values are `IMMICH_BASE_URL`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_AUDIENCE`, and `MCP_PUBLIC_URL`. `MCP_PUBLIC_URL` must be the externally visible URL including `/mcp`. Set `ALLOWED_HOSTS` to the Host headers your proxy sends and `ALLOWED_ORIGINS` to any browser origins allowed to call MCP (server-to-server clients normally omit `Origin`).

Timeout/retry and payload controls are documented in `.env.example`. Retries apply only to safe GET operations and only to network failures, 429, and selected 5xx responses.

## 6. Docker deployment

```bash
cd immich-mcp
cp .env.example .env
docker build --pull -t immich-mcp:local .
docker run --rm --name immich-mcp --env-file .env \
  -p 127.0.0.1:8000:8000 immich-mcp:local
```

Or:

```bash
cd immich-mcp
docker compose build --pull
docker compose up -d
docker compose logs -f immich-mcp
```

Terminate TLS at a trusted reverse proxy, forward only to `127.0.0.1:8000`, preserve the public Host header, and redact `/simple-share/*` and `/public/shared-albums/*` paths from proxy logs.

## 7. MCP client configuration

Conceptual configuration (clients with JSON configuration support):

```json
{
  "mcpServers": {
    "immich": {
      "transport": "streamable-http",
      "url": "https://mcp.example.com/mcp",
      "oauth": {
        "issuer": "https://auth.example.com/application/o/immich-mcp/",
        "clientId": "CLIENT_CONFIGURED_FOR_THIS_MCP_CLIENT",
        "scopes": ["openid", "profile", "email", "offline_access", "immich.read"]
      }
    }
  }
}
```

The JSON shape is client-specific; the protocol endpoint and OAuth values are the invariant parts. The server advertises Authentik through `/.well-known/oauth-protected-resource/mcp`.

## 8. ChatGPT and OpenWebUI notes

For ChatGPT, enable developer mode, create a custom app, enter `https://mcp.example.com/mcp`, select OAuth, complete authorization, then scan tools. Add the exact callback ChatGPT displays to the Authentik provider. ChatGPT remote MCP requires a publicly reachable HTTPS endpoint (or an approved secure tunnel). Refresh-token support generally requires `offline_access` to be advertised and issued.

For OpenWebUI 0.6.31+, set a persistent `WEBUI_SECRET_KEY`, then go to **Admin Settings → Integrations → External Tool Servers**, choose **MCP (Streamable HTTP)**, and use **OAuth 2.1 (Static)** because this server/Authenik setup does not expose dynamic client registration. Enter the MCP URL, Authentik client ID/secret, and Authentik issuer as OAuth Server URL; request `openid profile email offline_access immich.read`. Leave the OAuth resource parameter on Automatic unless Authentik policy requires otherwise. Each OpenWebUI user authorizes their own Authentik identity.

## 9. Public-share behavior

MCP tools:

* `get_shared_album`
* `list_shared_album_assets`
* `get_shared_asset_metadata`
* `get_shared_asset_image`
* `get_shared_album_gallery`

The image tool emits native `ImageContent` and preserves `image/webp`, `image/jpeg`, or the actual upstream type. Gallery responses inline at most `GALLERY_INLINE_IMAGE_LIMIT` thumbnails and return metadata/tool references for the rest. REST helpers are `/public/shared-albums/{key}` and `/public/shared-albums/{key}/assets`. `/simple-share/{key}` is a basic HTML gallery whose image proxy remains constrained by that share.

## 10. Private-library limitation

Phase 3 is not enabled. Immich currently starts its own OIDC flow at `/api/oauth/authorize`, completes it at `/api/oauth/callback`, maps `sub`, and issues a new opaque Immich session. It does not document accepting external Authentik bearer tokens or exchanging a token issued to this MCP audience for an Immich session.

The clean boundary is `PrivateImmichCredentialProvider` in `app/immich/albums.py`. Private tools will only be added when that provider can obtain a supported, revocable per-user credential. A global admin key is not an acceptable substitute.

## 11. curl tests

```bash
curl -fsS https://mcp.example.com/health
curl -fsS https://mcp.example.com/ready
curl -fsS https://mcp.example.com/public/shared-albums/SHARE_KEY
curl -fsS https://mcp.example.com/public/shared-albums/SHARE_KEY/assets
curl -fsS https://mcp.example.com/simple-share/SHARE_KEY
```

Protected-resource discovery:

```bash
curl -fsS https://mcp.example.com/.well-known/oauth-protected-resource/mcp
```

MCP initialization with a real Authentik access token:

```bash
curl -i https://mcp.example.com/mcp \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

Run tests locally:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```
