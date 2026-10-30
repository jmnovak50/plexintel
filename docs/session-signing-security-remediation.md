# Production session-signing remediation — stopped before change

**Historical attempt, superseded:** the subsequent broader operational authorization completed the signer/path/proxy corrections and one restart. See [completed production authentication remediation](production-authentication-remediation.md). The stopped attempt below remains preserved as historical evidence.

**October 30, 2026 — NO-GO.** Rotation stopped at an existing agent-authentication prerequisite failure, as instructed. The session signer remains unchanged; no configuration backup, secret replacement, backend restart, UI deployment or production test write occurred.

## Verified configuration and impact

- Authoritative source: `/home/jmnovak/projects/plexintel/.env`, owner/group **1000:1000**, **0600**, ignored by Git and not tracked. Exactly one `SESSION_SECRET` assignment exists.
- `plexintel-backend.service` reads that file through `EnvironmentFile`. There is no competing unit definition, drop-in or passed manager variable. `api/main.py` loads dotenv with `override=False`; the running process value matches the file. The predictable signer is an explicit installation setting, not an absent-variable fallback. Its original selection is not established by available evidence.
- The identified consumer is the direct-Python backend, PID **1638**, started **08:27:26 CDT**. Its registered unit references the same file. Other protected process environments were not generally readable; no claim of a host-wide secret-reuse audit is made.
- Replacing the signer would invalidate existing browser cookies and require normal Plex sign-in again. Existing Authentik JWT signing keys, REST service bearer credentials and MCP JWT configuration are separate. Restart would briefly interrupt HTTP/MCP connections; MCP HTTP is stateless.
- A strong signer also changes the existing agent browser-session safety check from disabled to enabled. Fresh, properly populated sessions can then use that existing authentication path. No code or authorization policy change is proposed.

## Safety checks and blocking finding

The backend is healthy (**HTTP 200**). No active ML pipeline, discovery writer, digest delivery, queued/running dimension review or conflicting application advisory lock was found. Today's ML slot already completed successfully as run **321**. The enabled weekly digest slot already completed; its existing poller still compares Tautulli users before checking slot completion. This behavior was assessed, not disabled or invoked by a test.

Read-only checks found no pending startup data repair or settings bootstrap change. Logical fingerprints were captured for **all 43 application tables** and matched again immediately before the operation reached its authentication prerequisite. PostgreSQL identity and strict discovery schema matched the accepted target. Discovery remains **962 titles / 1,049 observations / six runs**; the source binding and disabled gates remain intact.

**Blocker:** effective `PLEXINTEL_AGENT_SERVICE_TOKEN_FILE` points to:

```text
/app/.secrets/agent-rest.token
```

That file does not exist on this direct-Python host. The real owner-only credential loader rejects it. A GET-only bearer configuration probe returned **503**; an unauthenticated agent request returned **401**. In `api/services/agent_auth.py`, an invalid configured service credential causes failure before JWT fallback, so this is an existing agent REST authentication problem, not merely an unavailable optional test credential. MCP uses a separate authentication path.

The guarded operation stopped **before backup creation, secret generation/replacement or restart**. It did not repair this unrelated configuration automatically. An earlier harmless stop involved a changing count of unreadable unrelated process environments; investigation confirmed all substantive runtime fields were unchanged, and the diagnostic count was removed from the operational equality check. Neither stop changed production.

An existing candidate file is present at `/home/jmnovak/projects/plexintel/.secrets/agent-rest.token`: regular file, owner/group **1000:1000**, **0600**, readable, and valid under the credential format rules. Its identity against the intended external consumer has **not** been established; its existence alone does not authorize repointing production.

## Validation results

| Check | Result |
| --- | --- |
| Focused synthetic login/session, REST bearer and MCP OAuth tests | **50 passed**, all real database and network transports blocked |
| Synthetic fresh Plex callback, new-cookie acceptance, old-cookie rejection and admin/member separation | PASS in isolated ASGI checks; provider and user writer mocked |
| Representative old-signer cookie before any change | Accepted by the existing backend; cookie and identity were kept out of evidence/output |
| Actual old-cookie invalidation / new signer loaded | **Not performed**; no rotation |
| Live fresh Plex login | **Not performed**; operator agreed to confirm after a future completed restart |
| Existing production bearer authentication | **FAIL: 503**, missing configured host credential file |
| Valid live Authentik/MCP token after restart | Not performed; no restart or supplied access token |
| Final production boundary | PASS: signer file, backend state, private provider file and served frontend unchanged; all discovery gates false |

The first isolated test run had one environment-dependent failure because production service scopes were inherited. The runner now explicitly supplies synthetic scopes and credentials; the rerun passed all 50 tests. No application behavior was changed to satisfy a test, and no production integration test wrote application data.

## Required next authorization

The smallest proposed follow-up is to verify the existing local token against its intended consumer, then separately approve correcting **only the credential-file path** to the verified host location, alongside the already requested session-signing remediation. This need not rotate the service credential. Do not create a replacement token or assume the candidate matches.

After that prerequisite is resolved and authorized, take a byte-verified owner-only configuration backup, replace only the signer with `secrets.token_urlsafe(48)`, perform one controlled backend restart and repeat the read-only authentication/integrity checks. Never restore the weak signer automatically. A real Plex login updates the user record, so the operator's normal browser confirmation remains distinct from isolated/no-write integration testing.

Remaining security concerns: the current weak signer is still active; the previously exposed Tautulli credential remains unrotated; existing cookies lack `Secure`; proxy trust/origin handling still needs acceptance. The existing Plex helper also logs raw account responses, which should receive separate sanitization review. None of these was silently changed or tested by retrieving a live provider account response.

Sanitized evidence: `artifacts/seerr-exploration/2026-10-30-session-signing/`, including preflight/table fingerprints, the exact pre-change stops, credential-file metadata, focused test results and final boundary verification. No old/new secret, token or cookie is included in this report.

**NO-GO for read-only Content Discovery deployment.** Resolve the agent credential-path prerequisite and complete signer rotation/authentication verification first. Deployment remains separately authorized; discovery execution and scheduling remain disabled.
