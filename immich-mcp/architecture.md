# Immich MCP architecture and decisions

Research snapshot: 2026-08-31, against Immich `main` and MCP Python SDK 2.1.

## Boundaries

The service is a thin resource server in front of one configured Immich origin. It never uses a caller-supplied host as an HTTP target. Public share keys are capability credentials and are forwarded only to `IMMICH_BASE_URL`. Authentik is the OAuth/OIDC authorization server for `/mcp`; Immich remains an upstream application and photo API.

```text
MCP client -- Authentik access token --> /mcp -- validated identity --> tools
                                                          |
public share key -----------------------------------------+--> configured Immich
```

Health, readiness, public-share REST helpers, and the optional simple HTML gallery are outside MCP OAuth. Those public routes can only exercise permissions already granted by an Immich share key. The key is never logged at INFO level.

## Current Immich auth findings

Immich is an OIDC relying party/client, not an OAuth authorization server:

* `POST /api/oauth/authorize` asks Immich to initiate its own OIDC Authorization Code + PKCE flow and returns the upstream IdP authorization URL.
* `POST /api/oauth/callback` accepts the callback URL, state, and verifier. Immich exchanges the code with the IdP, maps the OIDC `sub` to its own user, and creates a random, opaque Immich session token.
* Authenticated Immich API requests accept an Immich session through `x-immich-user-token`, `x-immich-session-token`, Bearer, or the `immich_access_token` cookie. They also accept an Immich API key. Shared-link routes accept their own share credential.
* Immich stores a hash of the random session token. The IdP token retained on the session is used for logout; it is not the Immich API session token.
* There is no documented token-exchange, on-behalf-of, JWT bearer grant, or session-delegation endpoint that turns an arbitrary Authentik access token issued to this MCP resource into an Immich user session.
* Consequently, sending the MCP's Authentik bearer token to Immich is unsupported and will not authenticate unless it accidentally equals an opaque Immich session. Automating Immich's browser callback inside the MCP server would conflate OAuth clients, redirect URIs, state, and sessions and is not a supported delegation protocol.

Decision: external Authentik tokens are still never translated or forwarded to Immich. Private access instead uses a separately consented, least-privilege Immich API key created by each user. The key is encrypted locally and selected only after Authentik token validation. No MCP tool accepts a key or an identity selector.

Primary sources:

* Immich `oauth.controller.ts`: https://github.com/immich-app/immich/blob/main/server/src/controllers/oauth.controller.ts
* Immich `auth.service.ts`: https://github.com/immich-app/immich/blob/main/server/src/services/auth.service.ts
* Immich `oauth.repository.ts`: https://github.com/immich-app/immich/blob/main/server/src/repositories/oauth.repository.ts
* Immich OpenAPI: https://github.com/immich-app/immich/blob/main/open-api/immich-openapi-specs.json
* Immich OAuth documentation: https://docs.immich.app/administration/oauth

## Current Immich API-key findings

Research snapshot: current stable Immich `v3.1.0` API and source on 2026-09-02.

Immich API keys use the `x-api-key` header. The supported identity check is `GET /api/users/me`. The read-only private surface used by this service is:

| Operation | Current endpoint | API-key permission |
| --- | --- | --- |
| Validate key/current user | `GET /api/users/me` | `user.read` |
| List albums | `GET /api/albums` | `album.read` |
| Read album | `GET /api/albums/{id}` | `album.read` |
| List album assets | `POST /api/search/metadata`, flat filter `albumIds` | `asset.read` |
| Exact filename lookup | `POST /api/search/metadata`, flat `originalFileName` and optional `albumIds` | `asset.read` |
| Asset metadata | `GET /api/assets/{id}` | `asset.read` |
| Thumbnail/preview | `GET /api/assets/{id}/thumbnail` | `asset.view` |
| Original image | `GET /api/assets/{id}/original` | `asset.download` |
| Metadata search/recent assets | `POST /api/search/metadata` | `asset.read` |
| Natural-language smart search | `POST /api/search/smart` | `asset.read` |

The current album response no longer embeds its asset list, and there is no read endpoint named
`/albums/{id}/assets`. Stable Immich v3.1 metadata search uses flat `albumIds`, `order`, and
one-based `page` fields and returns `nextPage`. The structured `filter`, `orderBy`, and `cursor`
shape is part of the v3.2 release-candidate line and is not sent to stable v3.1. Filename lookup
uses v3.1's case-insensitive substring metadata filter, then requires a case-insensitive complete
filename match in the MCP client; duplicate full-name matches are returned explicitly.

Minimum recommended permissions for every tool in this release are `user.read`, `album.read`, `asset.read`, `asset.view`, and `asset.download`. Omit `asset.download` if original-image retrieval is not wanted; thumbnails continue to work. No create, update, upload, delete, sharing, or admin permission is requested.

Primary implementation contracts:

* Immich OpenAPI: https://github.com/immich-app/immich/blob/main/open-api/immich-openapi-specs.json
* Immich album controller: https://github.com/immich-app/immich/blob/main/server/src/controllers/album.controller.ts
* Immich search controller: https://github.com/immich-app/immich/blob/main/server/src/controllers/search.controller.ts
* Immich auth service: https://github.com/immich-app/immich/blob/main/server/src/services/auth.service.ts

## Private identity and authorization boundary

```text
strictly verified application issuer + sub
              |
              v
       identity namespace + sub
              |
              v
encrypted SQLite credential record
              |
              v
that user's x-api-key --> configured Immich
```

Authentik answers “who is this MCP user?” The Immich API key answers “what may this user access in Immich?” The browser account flow uses its own Authentik client, Authorization Code, PKCE, state, nonce, and a server-side opaque session. OAuth tokens and Immich keys are never stored in the browser cookie.

The MCP verifier discovers only `OIDC_ISSUER` and validates access tokens against `OIDC_AUDIENCE`. A separate verifier discovers only `ACCOUNT_OIDC_ISSUER` and validates account ID tokens against `ACCOUNT_OIDC_CLIENT_ID`. Issuers and discovery documents are never interchangeable.

After validation, persistent credential identity is `(IDENTITY_NAMESPACE, sub)`. This intentionally permits two trusted Authentik applications with different per-provider issuers to find the same user's record. It does not weaken issuer checks: an unvalidated `sub` never reaches lookup. Email and `preferred_username` remain display metadata only.

Both Authentik providers must use the same subject mode for the same directory user. Configure **Based on user UUID** on both providers; this is stable and does not depend on mutable email or username. Authentik's current implementation resolves this mode from the user's UUID, while issuer selection remains provider-specific. See the official [OAuth provider documentation](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/), [`SubModes` definitions](https://github.com/goauthentik/authentik/blob/main/authentik/common/oauth/constants.py), and [ID-token subject resolution](https://github.com/goauthentik/authentik/blob/main/authentik/providers/oauth2/id_token.py).

Legacy SQLite databases using primary key `(issuer, subject)` are transactionally migrated at startup. Each row is assigned the configured namespace, the encrypted API key and timestamps are copied unchanged, and its issuer is retained as `source_issuer`. Duplicate subjects across legacy issuers make the migration fail closed before mutation because they cannot be merged without an operator decision. The legacy `last_validated_at` column is retained for compatibility but means “validated when connected or reconnected”; the account UI now labels it accordingly.

## Public share behavior

Album links are resolved with `GET /api/shared-links/me` and `x-immich-share-key`. The embedded `assets` list is not trusted for album enumeration. The client requests every `/api/timeline/buckets` result and every corresponding `/api/timeline/bucket`, then converts parallel arrays into ordinary asset objects. Missing arrays are allowed; every present parallel array must have the same length as `id`, otherwise the upstream response is rejected as malformed.

Pagination wrappers (`items`, `results`, or `buckets`, with `nextPage`/`nextCursor`) are accepted defensively for future API changes. Current list/vector responses remain the primary supported format.

## MCP and OIDC

The Python MCP SDK runs Streamable HTTP at `/mcp` and publishes RFC 9728 protected-resource metadata. The MCP server is only a resource server: MCP clients perform Authorization Code flow (PKCE for public clients) directly with Authentik using its discovery document. Tokens are validated locally against discovered JWKS, with signature algorithm, issuer, audience, `exp`, `nbf`, and required scopes enforced. `sub` is the stable identity within the configured namespace; email and preferred username are optional attributes.

## Threat controls

* Exact configured origin matching for supplied share URLs; URL credentials are rejected.
* Fixed upstream base URL, fixed API paths, encoded identifiers, TLS verification by default.
* Timeouts, bounded GET-only retries, streaming response-size limits, gallery image limits. Image requests reject an oversized declared length before reading and stop iteration immediately when an undeclared/incorrect-length body exceeds `MAX_IMAGE_BYTES`.
* No token/share-key logging; sanitized upstream errors.
* Fernet-authenticated encryption at rest; SQLite records are keyed only by identity namespace plus validated subject.
* Opaque HMAC-indexed browser sessions, short-lived OAuth state/PKCE records, secure cookies, and CSRF checks.
* Readiness verifies SQLite itself but never a particular user's credential.
* Native MCP `ImageContent` preserves the upstream `Content-Type`.
* Public HTML uses the same client and an image proxy authorized by the same share key.
