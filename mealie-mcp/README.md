# Mealie MCP Service

This is a FastAPI application that gives each authenticated user a curated MCP
interface to that user's own Mealie connection. Authentik identifies the
service user. A separately supplied Mealie API token is encrypted in PostgreSQL
and forwarded only to that user's validated Mealie origin. Mealie continues to
enforce its user, household, and group permissions.

The first release is deliberately read-only:

* `search_recipes`
* `get_recipe`
* `get_meal_plan`
* `get_shopping_lists`
* `get_shopping_list`

The live Mealie OpenAPI schema is interpreted below this facade. It selects a
small allowlist of capabilities and never creates arbitrary MCP tools. See the
full [architecture proposal](docs/architecture-proposal.md).

## Security and identity model

An OIDC access token is validated using discovery and JWKS, an asymmetric
algorithm allowlist, exact issuer, audience, expiry, and required scopes. The
validated `sub` is mapped to stable internal tenant/user UUIDs. Email is display
metadata and is not an authorization key.

Connection lookup always applies `tenant_id` and `user_id`. The selected row
contains an encrypted Mealie token and a validated origin. The token is
decrypted just before one downstream request and is never returned by the REST
API or MCP, logged, put in OIDC, or included in an exception. There is no global
`MEALIE_API_TOKEN` setting.

Supplied Mealie origins are checked at registration and before every request.
Redirects are rejected, responses are bounded, and only safe reads receive a
bounded retry. SaaS mode rejects private and special-use networks. Self-hosted
mode permits private networks only through an operator CIDR/hostname allowlist.
Public SaaS deployment also needs network-level egress filtering to close the
DNS resolution time-of-check/time-of-use gap.

## Local development

Python 3.12+ and PostgreSQL are required.

```bash
cd mealie-mcp
python -m venv .venv
.venv/bin/pip install -e '.[test]'
cp .env.example .env
# edit .env; generate a unique Fernet key and configure Authentik
docker compose up -d postgres
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:create_app --factory --reload
```

Run checks with:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check app tests
.venv/bin/ruff format --check app tests
```

The management API is documented at `/api/docs`; MCP is at `/mcp`; liveness
and readiness are `/health` and `/ready`.

## Docker deployment

Copy `.env.example` to `.env`, set all placeholder values, and set a separate
`POSTGRES_PASSWORD` in the shell or Compose environment. Then run:

```bash
docker compose up --build -d
```

The application container runs Alembic before starting. Put it behind a TLS
reverse proxy and set `MCP_PUBLIC_URL`, `MCP_ALLOWED_HOSTS`, and
`MCP_ALLOWED_ORIGINS` to the externally visible values. Do not expose
PostgreSQL publicly.

## Authentik configuration

Create an OAuth2/OpenID Provider and application for this service:

1. Use Authorization Code flow with PKCE support and an asymmetric signing key.
2. Set the provider/client ID as `OIDC_AUDIENCE`.
3. Give access tokens a stable subject (Authentik's user UUID mode is preferred).
4. Add a custom `mealie.read` scope mapping and include it in access tokens.
5. Set `OIDC_ISSUER` to the exact issuer shown by Authentik's discovery page,
   including the application/provider path.
6. Add the MCP client's exact callback URI to Authentik. Keep client secrets in
   Authentik/client configuration, not this service.

The service is an OAuth resource server. It does not mint tokens or proxy an
authorization flow. The official MCP SDK publishes protected-resource metadata
that points clients at the configured Authentik issuer.

Verify discovery before connecting a client:

```bash
curl -fsS https://auth.example.com/application/o/mealie-mcp/.well-known/openid-configuration
curl -fsS https://mealie-mcp.example.com/.well-known/oauth-protected-resource/mcp
```

## Connecting a Mealie account

Obtain a long-lived API token from the user's own Mealie profile. Submit it once
over TLS to the management API:

```bash
curl -fsS https://mealie-mcp.example.com/api/v1/mealie-connections \
  -H 'Authorization: Bearer <OIDC_ACCESS_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"name":"Home","base_url":"https://mealie.example.com","api_token":"<MEALIE_TOKEN>"}'
```

The response contains validation metadata and capability names but never the
token. Credential rotation uses `PUT /api/v1/mealie-connections/{id}/credential`;
there is no credential read endpoint. A replacement is validated before the
old encrypted token is changed.

For a LAN Mealie instance, use `DEPLOYMENT_MODE=self_hosted`, explicitly list
its network in `MEALIE_PRIVATE_NETWORKS`, and enable `MEALIE_ALLOW_HTTP=true`
only when TLS is genuinely unavailable. SaaS mode ignores this convenience and
requires public HTTPS destinations.

## ChatGPT and Claude

Create a remote MCP connector whose server URL is:

```text
https://mealie-mcp.example.com/mcp
```

Use OAuth and the Authentik client/provider created for the connector. Register
the exact callback URI displayed by the client in Authentik; callback formats
are client-owned and may change. Request `openid`, `profile`, and `mealie.read`
(plus `offline_access` if refresh tokens are desired and permitted). The MCP
client receives only Authentik tokens. It never receives the Mealie token.

The deployment must be reachable over trusted HTTPS. `MCP_PUBLIC_URL` must
exactly match the connector URL, and the public hostname must be in
`MCP_ALLOWED_HOSTS`.

## OpenWebUI

Add a Streamable HTTP MCP server/tool connection pointing to the same `/mcp`
URL. Configure OAuth/OIDC against the Authentik provider when the OpenWebUI
version supports remote MCP OAuth. If an installed OpenWebUI release supports
only a static bearer header, supply a short-lived Authentik access token for
testing rather than a Mealie token. The production setup should use its OAuth
flow so each OpenWebUI user remains a distinct service principal.

Do not configure this service as an OpenAPI tool server. Its stable product
contract is MCP; `/api/v1` is the user connection control plane.

## OpenAPI capability discovery

Connection validation fetches the same-origin `/openapi.json`, permits only
local references, normalizes and hashes the document, and resolves curated
capabilities by allowlisted HTTP method/path plus operation metadata. It then
calls the resolved current-user operation using the submitted token.

The compact descriptor and schema hash are cached in PostgreSQL. Revalidation
reports added and removed curated capabilities. Cached metadata remains useful
for health display during a failure but does not make a failed validation pass.
No bundled upstream snapshot is trusted at runtime. Minimal schema A/B/C
fixtures test compatible additions and required-operation loss.

## Adding a Mealie capability

1. Add a semantic capability specification in `app/mealie/capabilities.py`.
   Include only known-safe method/path candidates and required path parameters.
2. Add compatibility fixtures for supported Mealie schema shapes and a fixture
   where the operation disappears or becomes incompatible.
3. Add request construction to an application service. Its public arguments
   should describe user intent, not arbitrary OpenAPI parameters.
4. Test isolation, response bounding, errors, and retry semantics. Mutations
   require duplicate/partial-failure analysis and are never retried by default.
5. Only then expose the service through a curated MCP tool.

## Adding an MCP tool

Add domain behavior under `app/services`, then register a thin presenter in
`app/mcp/server.py`. A tool may resolve the current `Principal` and call its
service. It must not access the connection repository, secret provider, HTTP
client, URL, or Authorization header directly. Keep results bounded and add a
real MCP transport test in addition to service tests.

## License provenance

The design reviewed `amercat37/mealie-mcp-server` and `2fst4u/mealie-mcp`, both
MIT licensed. Their source was not copied. Mealie is AGPL-3.0 and is accessed as
an independent HTTP service; full upstream schemas or source are not vendored.
The official Python MCP SDK is MIT and is used as a dependency. Details and
reviewed ideas are recorded in the architecture proposal.
