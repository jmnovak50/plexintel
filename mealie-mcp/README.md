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

The current deployment provides strict isolation among multiple users inside
one configured logical tenant. The connection schema is one-to-many and keeps
tenant predicates explicit, but commercial tenant provisioning, membership,
invitation, subscription, and billing workflows are intentionally deferred.

MCP clients and the browser account page use separate Authentik applications.
Both applications must use the same stable subject mode, specifically Authentik
user UUIDs. After each issuer independently validates its own token, the service
reconciles identity from `IDENTITY_NAMESPACE + sub`. The validated issuer stays
on the principal for audit and never becomes part of the persistent user ID.

Connection lookup always applies `tenant_id` and `user_id`. The selected row
contains an encrypted Mealie token and a validated origin. The token is
decrypted just before one downstream request and is never returned by the REST
API or MCP, logged, put in OIDC, or included in an exception. There is no global
`MEALIE_API_TOKEN` setting.

Supplied Mealie origins are checked at registration and before every request.
Redirects are rejected, responses are bounded, and only safe reads receive a
bounded retry. SaaS mode rejects private and special-use networks. Self-hosted
mode permits private networks only through an operator CIDR/hostname allowlist.
Cloud metadata hostnames and addresses are unconditional denials in both modes;
an operator allowlist cannot override them. SaaS configuration rejects private
CIDR, hostname, and cleartext HTTP exceptions at startup.

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

The supported end-user onboarding page is `/account`. The management API is
documented at `/api/docs`; MCP is at `/mcp`; liveness and readiness are
`/health` and `/ready`.

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

Create two OAuth2/OpenID providers and applications for this service.

For the MCP resource-server application:

1. Use Authorization Code flow with PKCE support and an asymmetric signing key.
2. Set the provider/client ID as `OIDC_AUDIENCE`.
3. Give access tokens a stable subject (Authentik's user UUID mode is preferred).
4. Add a custom `mealie.read` scope mapping and include it in access tokens.
5. Set `OIDC_ISSUER` to the exact issuer shown by Authentik's discovery page,
   including the application/provider path.
6. Add the MCP client's exact callback URI to Authentik. Keep client secrets in
   Authentik/client configuration, not this service.

For the browser account application:

1. Use a separate confidential Authorization Code provider with PKCE support.
2. Use an asymmetric signing key and scopes `openid profile email`; it does not
   need `mealie.read`.
3. Configure its exact issuer, client ID, client secret, and `/account/callback`
   URI through the `ACCOUNT_*` settings.
4. Select the same **Based on user UUID** Subject mode as the MCP provider.

Changing either provider to a different subject mode breaks account-to-MCP
identity reconciliation even when both logins belong to the same person.

The service is an OAuth resource server. It does not mint tokens or proxy an
authorization flow. The official MCP SDK publishes protected-resource metadata
that points clients at the configured Authentik issuer.

Verify discovery before connecting a client:

```bash
curl -fsS https://auth.example.com/application/o/mealie-mcp/.well-known/openid-configuration
curl -fsS https://mealie-mcp.example.com/.well-known/oauth-protected-resource/mcp
```

## Connecting a Mealie account

Users should visit `https://mealie-mcp.example.com/account`. The service sends
the browser through the separate Authentik account application using
Authorization Code, PKCE S256, state, and nonce. The resulting browser session
is an opaque cookie whose keyed hash and identity are stored in PostgreSQL.
OAuth access and ID tokens are not retained.

The account page submits the Mealie origin and API token directly to the
existing `ConnectionService`. The browser never receives the stored plaintext
or encrypted credential. It can display only safe connection metadata,
revalidate owned connections, or disconnect them. Every POST action requires a
session-bound CSRF token.

The bearer-authenticated API remains available for administrative clients.

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
only when TLS is genuinely unavailable. SaaS mode rejects these settings at
startup and requires public HTTPS destinations. Metadata targets remain blocked
even when a self-hosted private-network rule would otherwise contain their
address.

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
local references, normalizes and hashes the document, and scans all operations
for conservative matches to curated capabilities. Exact known paths are strong
evidence, while route movement requires matching path semantics plus a known
operation ID or allowlisted tag. Parameters, required inputs, request bodies,
and successful JSON response schemas must also be compatible. Tied or weak
matches are withheld rather than guessed.

Application services use stable semantic parameter names. The descriptor maps
them to the selected Mealie schema, for example `page_size` to `perPage`,
`pageSize`, or `page_size`, and `slug` to the route's actual placeholder. A
declared parameter with an incompatible type makes that capability unavailable.
External references and malformed or unresolved local JSON pointers reject the
document. Recursive component graphs are valid and remain unexpanded during
that whole-document check. When curated capability matching actually follows a
root reference chain, cycle detection and a depth limit still prevent unsafe or
unbounded semantic dereferencing.

The compact descriptor and schema hash are cached in PostgreSQL. Revalidation
reports added and removed curated capabilities. Cached metadata remains useful
for health display during a failure but does not make a failed validation pass.
No bundled upstream snapshot is trusted at runtime. Schema A/B/C/D fixtures
test compatible additions, route and parameter movement, ambiguity, schema
incompatibility, unknown endpoints, and required-operation loss.

## Adding a Mealie capability

1. Add a semantic capability specification in `app/mealie/capabilities.py`.
   Include known-safe paths and operation IDs, semantic tags/path evidence,
   parameter aliases and types, and the expected response shape.
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
