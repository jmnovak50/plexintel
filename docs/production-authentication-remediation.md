# Production authentication remediation

**October 30, 2026 — operational corrections PASS.** One controlled restart completed at **12:14:01 CDT**. The authentication blockers are corrected; Content Discovery has **not** been deployed or enabled. The operator subsequently confirmed fresh Plex sign-in and administrator access.

## Causes and corrections

| Cause | Correction |
| --- | --- |
| A container credential path was used by the direct-Python service | Repointed `PLEXINTEL_AGENT_SERVICE_TOKEN_FILE` to the existing `/home/jmnovak/projects/plexintel/.secrets/agent-rest.token`. Its bytes, ownership, permissions and service scopes were preserved. The runtime-specific example in `docs/watch-history-playback.md` is corrected. |
| The explicitly configured browser signer was a known placeholder | Replaced only that signing credential with `secrets.token_urlsafe(48)` — 384 random bits. Existing browser cookies are invalidated. No unrelated credential was rotated. |
| Browser session cookies lacked `Secure` | Added `SESSION_COOKIE_SECURE` support in `api/main.py`, explicitly true in production. HttpOnly and SameSite=Lax remain. Development defaults are preserved. |
| Uvicorn trusted only loopback, so proxied HTTPS appeared as HTTP | Set `FORWARDED_ALLOW_IPS=127.0.0.1,::1,10.200.1.2`. The exact proxy address was independently confirmed through Docker network metadata and a tagged request reaching the backend. No wildcard/subnet trust, proxy ACL change or weaker Origin check was introduced. |
| Plex identity lookup logged raw account responses | Removed response-body and exception-content prints from `api/services/plex_service.py`; regression tests cover XML, JSON, malformed and denied responses. |

The authoritative configuration remains `/home/jmnovak/projects/plexintel/.env`, owner/group **1000:1000**, **0600**, Git-ignored. The systemd `EnvironmentFile` supplies it; dotenv does not override exported values. No competing signer definition or unit/drop-in change was introduced. Only four configuration keys changed: `SESSION_SECRET`, `PLEXINTEL_AGENT_SERVICE_TOKEN_FILE`, `SESSION_COOKIE_SECURE`, `FORWARDED_ALLOW_IPS`. All other parsed settings remain exact.

The existing REST credential is the local file described by the original provisioning procedure. Backend and adapter verification used that unchanged credential; the live external OpenWebUI instance's stored valve/token was not inspected or replaced.

## Controlled operation and recovery

The preflight verified the production database target/schema, quiet ML/dimension/discovery state and completed current ML/digest schedule slots. A shared pipeline lock covered the change/restart. The current application startup was checked for pending data repairs/settings changes before proceeding.

Byte-exact, verified configuration backup:

```text
/home/jmnovak/.local/state/plexintel/auth-remediation/20261030T121400-0500-d9614c/application-before.env
```

Backup directory **0700**, backup file **0400**, owner **1000**. The replacement was atomic and retained configuration mode **0600**. No database backup or restore was performed. Do not restore the weak signer to roll back an unrelated UI deployment.

Exactly one `sudo -n systemctl restart plexintel-backend.service` completed successfully. Backend PID changed **1638 → 169181**, health returned 200, and the effective process configuration matched the corrected file. The service unit, database credentials, Seerr provider file and served frontend remained unchanged. No additional restart or secret generation was needed.

The first post-restart collector incorrectly expected a Set-Cookie header on an unmodified GET and marked verification inconclusive. Installed Starlette emits a cookie only when the session changes. The discrepancy was resolved through source inspection and an isolated test of the **actual application's login handler and middleware**, with the provider/writer mocked; no production change was needed. The original collector receipt remains preserved alongside the final PASS audit.

## Verification

| Authentication path | Evidence |
| --- | --- |
| Old browser signer | Representative old cookie accepted before rotation; **401** afterward |
| New browser session | Administrator identity and discovery read endpoints **200**; operator confirmed normal fresh Plex login and administrator access |
| Administrator HTML / member HTML | **200 / 307 redirect**, respectively, through certificate-verified local production HTTPS proxy |
| Non-admin discovery API | **403** |
| Unauthenticated discovery / agent API | **401 / 401** |
| Existing service bearer | Previously **503**; now **200**, credential bytes unchanged |
| Invalid bearer | **401**, rather than configuration failure |
| Deterministic OpenWebUI adapter code | Actual authenticated read to production library statistics succeeded; no model/narration or write action |
| Legitimate HTTPS scope review | Previously **403**; now **200**; read-only plan only, no Seerr request/job |
| Cross-origin scope review | **403** |
| Secure cookie issuance | Actual-app synthetic Plex callback emits **Secure, HttpOnly, SameSite=Lax**; writer/provider mocked, application lifespan not started |
| Plex identity provider | One GET with an existing stored administrator token returned matching identity; no account data/token logged and no user row updated |
| Authentik/MCP | OAuth metadata unchanged; existing JWT validation regressions pass. No valid live Authentik token was supplied, so end-to-end JWT/client reauthentication is not claimed. |

**55 focused tests passed**, including actual login/cookie issuance, credential logging, session invalidation, role boundaries, REST scopes and MCP OAuth behavior. All real database connections and network transports were blocked for the tests. Synthetic/provider-mocked login is distinct from a fresh interactive Plex PIN login.

The public-edge hostname returned 403 to this host before reaching the backend. Local proxy verification used the real hostname/SNI and full certificate validation while routing to `192.168.1.9:443`. No TLS verification was bypassed and no edge access policy was changed. The operator subsequently confirmed their normal browser sign-in and administrator access. This is operator evidence, not an automated test of every external ingress path.

## Integrity and scope

The final read-only audit confirmed:

- **All 43 application tables match the pre-change logical row fingerprints.** Users, settings, models' stored inputs/results, recommendations and pipeline history remain intact.
- Application catalog/permissions and strict discovery schema match; discovery remains **962 titles, 1,049 observations, six runs**, with its identity sequence unchanged.
- Existing scheduling configuration and completed slots remain unchanged; no active/queued work was interrupted or new discovery job created.
- The served frontend matches its prior file manifest. No Content Discovery UI placement, acquisition, scoring, training or discovery synchronization occurred.
- Three advances of the existing `email_digest_runs_run_id_seq` were observed, consistent with the enabled poller's duplicate-slot insert attempts. No digest row was added; this bookkeeping is not a new delivery or data corruption.

The authorized restart executed existing application startup/bootstrap SQL. This report does not claim PostgreSQL received no writes; it establishes unchanged logical rows/catalog and accounts for sequence bookkeeping. Verification itself used read-only connections and non-writing requests.

Code/doc changes: `api/main.py`, `api/services/plex_service.py`, `tests/test_browser_auth_security.py`, the host-path guidance, and remediation/readiness reports. No commit or push was performed. Private sanitized evidence is under `artifacts/seerr-exploration/2026-10-30-auth-remediation/`; it includes the preflight, one-change receipt, original collector discrepancy, final integrity PASS and test results.

## Readiness and remaining concerns

**Authentication corrections: GO. Read-only Content Discovery deployment recommendation: GO**, with fresh browser login and administrator access confirmed by the operator. Deployment still requires separate authorization and post-deployment UI acceptance. All discovery execution, persistence and scheduling gates remain false.

Existing browser sessions must sign in again. The operator confirmed successful normal sign-in and administrator access. That normal login can update the user record; the exact-table audit above was completed before this expected user activity. External OpenWebUI/ChatGPT clients may need to reconnect after the restart; their existing credentials were preserved.

The previously exposed Tautulli credential remains a separate unresolved rotation concern. PostgreSQL superuser use remains the accepted temporary exception. Exact proxy-IP trust must be rechecked if the proxy container's address changes. Existing broader CORS policy was not redesigned. None of these was silently expanded into unrelated credential/service changes.
