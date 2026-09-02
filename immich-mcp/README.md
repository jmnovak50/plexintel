# Immich MCP

A thin, typed Python MCP server for public Immich shares and read-only private libraries. FastAPI hosts stateless Streamable HTTP at `/mcp`; Authentik authenticates the MCP user; each user separately connects their own least-privilege Immich API key at `/account`.

## Architecture

Authentication and Immich authorization are deliberately separate:

```text
ChatGPT/OpenWebUI -> Authentik MCP OAuth -> verified issuer + sub -> Immich MCP
                                                        |
                                        IDENTITY_NAMESPACE + sub
                                                        |
                                                        v
                                      encrypted SQLite credential record
                                                        |
                                                        v
                                          that user's Immich API key -> Immich
```

Authentik answers “who is this MCP user?” The selected Immich API key answers “what may this user access in Immich?” The LLM never supplies an API key, username, email, or subject used to select a credential. Public share keys remain independent capability credentials and retain the existing Phase 1 behavior. See [architecture.md](architecture.md) for the current Immich OpenAPI/source findings.

## Security model

- `/mcp` validates Authentik JWT signatures through the `OIDC_ISSUER` discovery/JWKS document and enforces issuer, audience, `exp`, `nbf`, and `immich.read` scope.
- `/account` independently discovers and validates against `ACCOUNT_OIDC_ISSUER`; it uses a dedicated Authentik OIDC client with Authorization Code, PKCE S256, state, nonce, signed ID-token validation, and an opaque server-side session. Discovery documents are never shared between the two applications.
- Credential lookup uses `IDENTITY_NAMESPACE + sub`, not OAuth issuer, email, or username. Each token's own issuer is still strictly validated before its `sub` may enter that namespace.
- Browser cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` by default. POSTs require CSRF tokens. OAuth tokens and Immich keys are never stored in cookies.
- Immich API keys are encrypted with Fernet before SQLite persistence. Keys, ciphertext, OAuth tokens, authorization codes, and share keys are excluded from application logs and tool results.
- No global Immich administrator key exists. No Authentik token is forwarded or exchanged with Immich. No write tool is registered.
- Caller-provided share URLs must match `IMMICH_BASE_URL` exactly. TLS verification, fixed timeouts, GET-only retries, bounded streaming image limits, pagination limits, and sanitized errors are enabled.
- Uvicorn access logging is disabled. Apply equivalent reverse-proxy redaction for `/account/callback`, `/account/connect`, `/simple-share/*`, and `/public/shared-albums/*`.

## Current Immich API and permissions

The implementation was checked against the current stable Immich `v3.1.0` API and source on
2026-09-02. API keys use `x-api-key`.

| Operation | Immich endpoint | Required permission |
| --- | --- | --- |
| Connect/current user | `GET /api/users/me` | `user.read` |
| List/read albums | `GET /api/albums`, `GET /api/albums/{id}` | `album.read` |
| List album assets | `POST /api/search/metadata`, flat `albumIds` filter | `asset.read` |
| Exact filename lookup | `POST /api/search/metadata`, flat `originalFileName` and optional `albumIds` | `asset.read` |
| Metadata/search/recent | `GET /api/assets/{id}`, `POST /api/search/metadata`, `POST /api/search/smart` | `asset.read` |
| Thumbnail/preview | `GET /api/assets/{id}/thumbnail` | `asset.view` |
| Original image | `GET /api/assets/{id}/original` | `asset.download` |

Select these read permissions for the complete tool set:

```text
user.read
album.read
asset.read
asset.view
asset.download
```

Omit `asset.download` if original retrieval is not wanted; thumbnails continue to work. Do not select create, update, upload, delete, sharing, user-administration, or admin permissions.

Create an API key in each user's Immich account settings, assign the permissions above, copy it once, and connect it through `/account`. A revoked key produces a reconnect message; MCP does not delete or rotate keys inside Immich.

## Authentik setup

Create two Authentik OAuth2/OpenID providers/applications. Do not reuse Immich's own OIDC client.

### MCP OAuth client

1. Enable Authorization Code. Require PKCE S256 for public clients; OpenWebUI can use a confidential/static client.
2. Register the exact callback URI displayed by each MCP client.
3. Add and emit a scope mapping named `immich.read`.
4. Issue a signed JWT access token with audience equal to `OIDC_AUDIENCE`.
5. Include `sub`; optionally include `email` and `preferred_username`.
6. If refresh is needed, allow `offline_access`, but do not add it to `OIDC_REQUIRED_SCOPE`.
7. Set `OIDC_ISSUER` to the exact discovery issuer. Discovery must return the same issuer and an issuer-origin `jwks_uri`.

### Account-page OIDC client

1. Create a separate confidential Authorization Code client.
2. Register exactly `ACCOUNT_REDIRECT_URI`, such as `https://mcp.example.com/account/callback`.
3. Allow `openid profile email`; this application sends PKCE S256.
4. Set `ACCOUNT_OIDC_ISSUER` to this provider's exact issuer, then configure `ACCOUNT_OIDC_CLIENT_ID` and `ACCOUNT_OIDC_CLIENT_SECRET`.
5. In both Authentik providers, select the same **Subject mode**. Prefer **Based on user UUID** for a stable, non-email identifier. Both applications must emit the same `sub` for one user. Do not use email or username as the reconciliation key.

Authentik normally uses a per-provider issuer such as `/application/o/immich-mcp/` and `/application/o/immich-mcp-account/`; different issuers are expected. Strict issuer validation remains separate for each application. `IDENTITY_NAMESPACE=authentik` deliberately joins their already-validated subjects in the credential store. If the providers emit different `sub` values, linking cannot work and the server will not fall back to email.

The account client creates only a short-lived local browser session after ID-token validation. Its access and refresh tokens are discarded.

## Per-user account linking

1. Visit `ACCOUNT_PUBLIC_URL` and sign in directly to Authentik.
2. Paste your own Immich API key into the browser form.
3. The server validates it through `/api/users/me`, encrypts it, and stores it under `IDENTITY_NAMESPACE` plus the signed-in `sub`.
4. Return to the MCP client. Private tools now resolve that record from the verified MCP request identity.

The page never displays the key again. Disconnect removes only MCP's encrypted copy; revoke it separately in Immich when appropriate.

## Environment variables

Copy `.env.example` to `.env` and set all blank secrets.

| Variable | Purpose |
| --- | --- |
| `IMMICH_BASE_URL` | One fixed Immich origin |
| `OIDC_ISSUER` | Exact Authentik discovery issuer |
| `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` | MCP OAuth client metadata |
| `OIDC_AUDIENCE`, `OIDC_REQUIRED_SCOPE` | Required MCP token audience/scopes |
| `MCP_PUBLIC_URL` | External URL including `/mcp` |
| `CREDENTIAL_DB_PATH` | SQLite path; default `/data/credentials.sqlite3` |
| `CREDENTIAL_ENCRYPTION_KEY` | Required Fernet key |
| `IDENTITY_NAMESPACE` | Stable local identity domain shared by the two trusted Authentik applications; default `authentik` |
| `ACCOUNT_OIDC_ISSUER` | Exact, separately discovered issuer for the account application |
| `ACCOUNT_OIDC_CLIENT_ID`, `ACCOUNT_OIDC_CLIENT_SECRET` | Dedicated account OIDC client |
| `ACCOUNT_REDIRECT_URI`, `ACCOUNT_PUBLIC_URL` | Trusted account callback/page URLs |
| `ACCOUNT_SESSION_SECRET` | At least 32 random characters for session/state HMACs |
| `ACCOUNT_COOKIE_SECURE` | Keep `true` in production |
| `MAX_IMAGE_BYTES`, `PRIVATE_TOOL_MAX_ITEMS` | Tool payload/result limits |

Generate secrets:

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
openssl rand -base64 48
```

Private access fails startup configuration validation if required settings are missing or the Fernet key is malformed.

## Docker deployment and migration

Compose mounts a named volume at `/data`; the image creates it for the non-root user. From the existing installation:

```bash
cd immich-mcp
cp .env.example .env.new
# Merge the new credential/account variables into the existing .env.
# Generate both secrets, then configure both Authentik clients.
docker compose build --pull
docker compose up -d
docker compose logs -f immich-mcp
```

Direct Docker run:

```bash
cd immich-mcp
docker build --pull -t immich-mcp:local .
docker volume create immich_mcp_data
docker run -d --name immich-mcp --restart unless-stopped \
  --env-file .env -p 127.0.0.1:8000:8000 \
  --read-only --tmpfs /tmp:size=16m,noexec,nosuid \
  -v immich_mcp_data:/data immich-mcp:local
```

Terminate TLS at a trusted reverse proxy, preserve the public Host header, and forward only to `127.0.0.1:8000`.

Backup warning: the database is useless without its Fernet key. The database and key together grant access to every stored Immich API key. Back them up separately with equivalent secret controls. Losing or rotating the key without migrating ciphertext makes existing records unrecoverable.

On first startup after this correction, an existing `(issuer, subject)` credential table is migrated in place and transactionally to `(identity_namespace, subject)`. Ciphertext and metadata are preserved, the old issuer is retained as `source_issuer` for audit, and existing rows receive the configured `IDENTITY_NAMESPACE`. If the old table contains the same `subject` under multiple issuers, startup stops before changing the table because choosing one credential would discard or overwrite data; resolve those duplicate rows manually, then restart. Back up the SQLite database before upgrading. Changing `IDENTITY_NAMESPACE` later does not rewrite records and will make the old namespace's credentials unavailable until explicitly migrated.

## MCP clients

The exact JSON shape varies by client:

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

Protected-resource metadata is at `/.well-known/oauth-protected-resource/mcp`.

### OpenWebUI flow

The administrator adds this server once as a Streamable HTTP external tool server, chooses OAuth 2.1 Static against Authentik, supplies the MCP client ID/secret and issuer, requests `openid profile email offline_access immich.read`, and grants access to intended groups.

Each user authorizes the connector, opens `/account`, signs in with the same Authentik identity, and pastes their own Immich key. Never put a shared Immich key in the OpenWebUI connector.

### ChatGPT implications

A ChatGPT-authenticated `IDENTITY_NAMESPACE + sub` resolves the same record as the account application even when their validated issuers differ. The user links `/account` separately; there is no ChatGPT-specific identity logic. Current official OpenAI guidance places developer mode under **Settings → Security and login**, then adds the `/mcp` endpoint from ChatGPT Plugins; availability can depend on workspace policy. Public deployment needs a stable HTTPS Streamable HTTP endpoint, while Secure MCP Tunnel is appropriate for developer-mode testing. See [OpenAI's MCP server guide](https://developers.openai.com/plugins/build/mcp-server) and [Connect and test your plugin](https://developers.openai.com/plugins/deploy/connect-chatgpt).

## MCP tools

Public shares (unchanged):

- `get_shared_album`
- `list_shared_album_assets`
- `get_shared_asset_metadata`
- `get_shared_asset_image`
- `get_shared_album_gallery`

Authenticated private library:

- `get_immich_connection_status`
- `list_albums`
- `get_album`
- `list_album_assets`
- `get_asset_metadata`
- `get_asset_thumbnail`
- `get_asset_image`
- `search_assets`
- `get_recent_assets`

Image tools return native MCP `ImageContent` with Immich's MIME type. Image bodies are streamed: an oversized `Content-Length` is rejected before reading, and responses without a length are stopped as soon as accumulated decoded bytes exceed `MAX_IMAGE_BYTES`. Search supports current smart text search plus city, country, person ID, capture-date range, media type, favorite status, and a bounded limit. List/search/recent tools return compact metadata and never inline images.

## Public shares

Album shares resolve through `/api/shared-links/me`; assets are enumerated through every timeline bucket because current Immich can return an empty embedded `assets` list. Parallel arrays are defensively normalized. REST helpers remain at `/public/shared-albums/{key}` and `/public/shared-albums/{key}/assets`; `/simple-share/{key}` remains a no-JavaScript gallery constrained by the same share.

## Health, readiness, and curl

`/health` only confirms the process is alive. `/ready` checks both independent OIDC discovery/JWKS documents, Immich ping, and SQLite; it never depends on a user's key.

```bash
curl -fsS https://mcp.example.com/health
curl -fsS https://mcp.example.com/ready
curl -fsS https://mcp.example.com/public/shared-albums/SHARE_KEY
curl -fsS https://mcp.example.com/public/shared-albums/SHARE_KEY/assets
curl -fsS https://mcp.example.com/.well-known/oauth-protected-resource/mcp
```

MCP initialization with an Authentik access token:

```bash
curl -i https://mcp.example.com/mcp \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

Tests:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

## Known limitations

- Users must create, paste, rotate, and revoke their own Immich keys; Immich has no delegated Authentik-token exchange for this service.
- SQLite/Fernet targets one service instance sharing one volume. Multiple replicas need a coordinated store and key-management plan.
- Images are rejected above `MAX_IMAGE_BYTES`; use thumbnails for large originals. A malicious compressed HTTP body can expand while decoding, but the limit is applied to the decoded bytes retained for MCP and streaming stops immediately when it is crossed.
- `IDENTITY_NAMESPACE` is a local trust boundary. Only configure both issuer applications into one namespace when they are controlled by the same Authentik deployment and guaranteed to emit the same stable `sub` semantics.
- Search uses current Immich v3.2 structured filters. Older releases using only deprecated flat filters may need an adapter.
- The minimal account UI rotates a key by reconnecting with its replacement.
- Password-protected public share login is not implemented.
