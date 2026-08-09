# ChatGPT MCP OAuth Setup

PlexIntel is the OAuth resource server; Authentik remains the authorization server. PlexIntel does not provide login, consent, client registration, authorization, or token endpoints.

## Public endpoints

- Canonical MCP Streamable HTTP: `https://plexintel.kabolly.com/mcp`
- Protected-resource metadata: `https://plexintel.kabolly.com/.well-known/oauth-protected-resource`
- Compatibility metadata: `https://plexintel.kabolly.com/.well-known/oauth-protected-resource/mcp`

Both metadata URLs return the same resource, authorization-server issuer, and scopes.

## PlexIntel settings

Enter these in the PlexIntel admin settings interface:

```text
mcp.enabled = true
mcp.auth_mode = jwt_or_static
mcp.oauth.resource_url = https://plexintel.kabolly.com/mcp
mcp.oauth.audience = https://plexintel.kabolly.com/mcp
mcp.oauth.required_scopes = plexintel.read
mcp.oauth.issuer_url = https://auth.kabolly.com/application/o/plexintel-chatgpt/
mcp.oauth.email_claim = email
```

Keep the existing `mcp.api_key` and `mcp.trusted_user_email_header = X-OpenWebUI-User-Email` for OpenWebUI. The issuer must exactly match the access token's `iss`, including its trailing slash. The slashless audience/resource must appear in `aud`; and `scope` (or `scp`) must contain `plexintel.read`. The canonical MCP HTTP endpoint is also slashless; `/mcp/` remains accepted for backward compatibility without redirecting.

## Authentik work outside this repository

Create a dedicated OAuth/OIDC provider and application for ChatGPT. It must:

- expose OAuth or OIDC discovery and JWKS below the configured issuer;
- support authorization code with PKCE (`S256`);
- allow the exact ChatGPT callback shown on the ChatGPT app-management page—copy it there rather than guessing it;
- grant `plexintel.read` separately from identity scopes such as `openid`, `email`, and `profile`;
- put the user's email in the configured email claim;
- accept ChatGPT's `resource=https://plexintel.kabolly.com/mcp` on authorization and token requests;
- copy that resource into the JWT access token's `aud` claim;
- support a ChatGPT-compatible client registration/identification option (preconfigured client, CIMD, or DCR) and advertise compatible token endpoint authentication methods.

The last two items must be verified against the Authentik version in production. PlexIntel cannot make Authentik copy the OAuth `resource` parameter into `aud`.

## Connect from ChatGPT Developer Mode

1. In ChatGPT on the web, enable Developer mode under **Settings → Security and login**.
2. Open app/plugin management, create a developer-mode app, and enter `https://plexintel.kabolly.com/mcp` as the remote MCP URL.
3. Select **Mixed Authentication** and the client-identification method configured in Authentik.
4. Copy ChatGPT's displayed callback URL into Authentik's redirect-URI allowlist.
5. Invoke a protected tool, complete Authentik login/consent when prompted, then refresh the app's tools.
6. Confirm all nine tools appear as read-only and request `plexintel.read`.

PlexIntel intentionally permits unauthenticated MCP `initialize`, the required initialized notification, and `tools/list`. These responses contain only server capabilities, instructions, and tool names, descriptions, schemas, annotations, and OAuth metadata—never PlexIntel user or library data. Every listed data tool advertises OAuth with `plexintel.read`, and authentication is enforced before its handler can access PlexIntel services or the database.

ChatGPT may therefore finish initial plugin creation without opening Authentik. OAuth linking can begin when ChatGPT first invokes a protected tool and receives its tool-level `mcp/www_authenticate` challenge. Keep ChatGPT's callback registered in Authentik using **Strict** redirect-URI matching.

## Verify discovery and challenges

```bash
curl -i https://plexintel.kabolly.com/.well-known/oauth-protected-resource
curl -i https://plexintel.kabolly.com/.well-known/oauth-protected-resource/mcp
curl -i -X POST https://plexintel.kabolly.com/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

The metadata responses must be JSON, never SPA HTML. The canonical `/mcp` request and backward-compatible `/mcp/` request must both reach the same MCP transport without redirecting. Use a stateful MCP client for the discovery sequence so it sends `initialize`, `notifications/initialized`, and `tools/list` according to the negotiated protocol. Those discovery operations must succeed without authentication.

An unauthenticated `tools/call` must return an MCP tool error whose `_meta["mcp/www_authenticate"]` contains a challenge resembling:

```text
Bearer resource_metadata="https://plexintel.kabolly.com/.well-known/oauth-protected-resource", scope="plexintel.read", error="insufficient_scope", error_description="Sign in to PlexIntel to continue"
```

With a short-lived test access token (do not save or paste it into documentation):

```bash
curl -i -X POST https://plexintel.kabolly.com/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $PLEXINTEL_TEST_ACCESS_TOKEN" \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

## Troubleshooting

| Symptom | Check |
|---|---|
| Wrong issuer / `401` | JWT `iss` must exactly match the dedicated provider issuer, including the trailing slash. |
| Wrong audience / `401` | JWT `aud` must contain exactly the configured audience/resource; Authentik must propagate ChatGPT's `resource`. |
| Missing scope / `403` | Grant `plexintel.read`; identity scopes alone are insufficient. |
| Valid token but user tools fail | JWT email is not mapped in `users.plex_email`; sync the Plex email. A trusted header cannot replace JWT identity. |
| Metadata URL returns SPA HTML | Deploy the backend route before the root static mount and ensure the reverse proxy sends `/.well-known/*` to PlexIntel. |
| ChatGPT never opens linking UI | Check protected-resource JSON, each tool's OAuth `securitySchemes`, and tool errors for `_meta["mcp/www_authenticate"]`. |
