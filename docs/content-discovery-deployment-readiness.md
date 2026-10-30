# Content Discovery workspace — read-only deployment readiness

**Deployment completed:** the operator subsequently authorized the read-only UI. It was installed and verified **October 30, 2026, 12:39 CDT**, without another restart or configuration change. See [deployment PASS report](content-discovery-readonly-deployment.md). The preparation instructions and pending-state language below are historical; do not rerun the deployment. All discovery execution/scheduling gates remain disabled.

Original assessment: **October 30, 2026, 09:10–09:17 CDT**, on `birch`. **Current recommendation: GO for separately authorized read-only deployment**, following the completed authentication corrections and operator-confirmed fresh Plex login/admin access. Post-deployment UI acceptance remains pending. No secret value is reproduced here.

**Current authentication status:** the subsequent operational authorization corrected the host credential path, rotated the signer, enabled HTTPS session cookies, restricted forwarded-header trust to the verified proxy and loopback, and removed credential-bearing Plex response logging. One backend restart completed **12:14:01 CDT**; verification passed. See [completed authentication remediation](production-authentication-remediation.md). The earlier stopped attempt is historical. No UI deployment occurred.

During the original readiness assignment, no production deployment, restart, configuration edit, database write, migration, discovery request/job, acquisition, model execution, schedule change or database backup was performed. A disposable PostgreSQL fixture was created, tested, stopped and removed. The separately authorized subsequent authentication changes are documented above; historical runtime/security descriptions below are point-in-time findings.

## Readiness matrix

| Gate | Result | Evidence / required action |
| --- | --- | --- |
| Git provenance | PASS | Local `HEAD`, local `origin/main` and a fresh read-only GitHub `ls-remote` agree on `bc0495ce1ea0f6c0d98dcc11092e0e4772618f2b`; branch `main`, clean at entry. No fetch, pull, checkout, commit or push. |
| Implementation coverage | PASS | All seven requested workspace capabilities exist; source map below. |
| Database/schema/source | PASS | Verified production target, exact V2 catalog, compatible application columns, SELECT permissions and approved source binding. No migration needed. |
| Canonical inventory/history | PASS | 962 titles, 1,049 observations, six runs; every full discovery row matches the accepted population snapshot. |
| Original settings incident | PASS, with explained later defaults | Exact unauthorized records are absent; all 96 unrelated settings remain exact. Ten null/default discovery rows now exist; their keys are not absent. They do not activate scheduling. |
| Discovery gates and scheduling | PASS | Three web gates absent/default false; private discovery flag explicitly false; no active intent, registered discovery jobs, running discovery run or writer lock. |
| Existing pipeline/backend | PASS at inspection | Healthy, current API routes loaded, latest pipeline successful; earlier failure remains recorded. No active pipeline at inspection. |
| Authorization and disabled operations | PASS in isolated checks | Existing session/admin dependencies, non-admin denial and backend gates verified. Live unauthenticated requests return 401. Normal fresh browser login and existing administrator access are operator-confirmed; the new UI acceptance remains pending. |
| Session-signing security | **PASS after remediation** | Random 384-bit signer loaded; old cookies rejected, fresh signed admin sessions accepted. Normal interactive Plex login and administrator access are operator-confirmed. |
| Agent credential path | **PASS after remediation** | Existing token/scopes preserved; direct-Python host path corrected; bearer/adapter reads now succeed. |
| Previously exposed Tautulli credential | Unresolved security risk | Recommend rotation and consumer verification under separate authorization; redaction did not revoke the exposed key. No provider call or rotation performed here. |
| Reverse proxy / cookies | Verified locally through production TLS proxy | Exact proxy/loopback trust; same-origin plan succeeds, cross-origin fails. Actual-app login test verifies Secure/HttpOnly/SameSite=Lax. Normal browser login/admin access are operator-confirmed; automated ingress coverage remains limited to the documented proxy checks. |
| Tests and staged build | PASS | 395 Python tests, six UI tests, TypeScript, targeted ESLint and Vite build; 22 additional offline boundary checks and isolated static deployment/rollback simulation. |
| Deployment | Prepared, **not authorized** | Static package and rollback copy preserved. Corrected backend already has routes; no further restart is needed for the static UI swap itself. |

## Committed implementation review

The intended commit was verified against `jmnovak50/plexintel` on GitHub without modifying local refs. Its commit message still says cleanup was pending; that historical message is superseded by the approved cleanup receipt and current read-only checks, not rewritten.

| Capability | Source locations reviewed |
| --- | --- |
| Overview; searchable/filterable, sorted and paginated movie/TV inventory | `frontend/src/pages/AdminDiscovery.tsx`; `api/services/discovery_workspace.py` |
| Typed title detail, metadata uncertainty and discovery provenance | Same files; `api/routes/discovery_admin_routes.py` |
| Canonical execution history, scope memberships and diagnostics | Same files; `api/services/discovery_workflow.py` for workspace job history |
| Effective settings and scheduling views | `AdminDiscovery.tsx`; `discovery_workflow.py`; `api/services/app_settings.py` |
| Guarded manual controls, admin authorization and origin checks | `discovery_admin_routes.py`; `discovery_workflow.py` |
| Existing scheduler integration, disabled by default | `api/services/pipeline_scheduler.py`; `discovery_workflow.py` |
| ML/discovery cancellation separation | `api/services/pipeline_service.py`; `api/routes/pipeline_admin_routes.py` |
| Distinct navigation and application route | `frontend/src/components/AdminNav.tsx`; `frontend/src/App.tsx`; backend registration in `api/main.py` |

Also reviewed [implementation and incident report](content-discovery-workspace.md). No working application code, schema or migration was changed for this readiness assignment.

## Current production baseline and changes since development

The following baseline is the original 09:10 assessment. The later auth-only restart changed the backend PID to **169181** and loaded the corrected authentication configuration; all 43 application tables, catalog, discovery inventory, schedules and served frontend subsequently matched exactly. Use the linked remediation report for current authentication state.

- Host: `birch`; direct Python **3.13.5** from `/home/jmnovak/projects/plexintel/plexenv`; repository is the service working directory.
- Unit: `/etc/systemd/system/plexintel-backend.service`, user `jmnovak`, `EnvironmentFile=/home/jmnovak/projects/plexintel/.env`.
- Active command: `/home/jmnovak/projects/plexintel/plexenv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8489`, executed by the virtualenv Python. No `--reload` flag. Do not use `run_backend.sh`, which includes development reload behavior.
- Current backend PID **1638**, started **October 30, 08:27:26 CDT**, `NRestarts=2`. Host boot was **08:26:56 CDT**. This supersedes yesterday's PID/start baseline and occurred before this assignment. Neither PID nor restart state changed during this inspection.
- Local `/api/library/health`: **200**, expected library-catalog response. Active OpenAPI already includes discovery routes. `/admin/discovery` currently returns the **old** served `frontend/dist/index.html`; the new workspace build has not been installed.
- The service loads source from this checkout. Start time, unchanged checkout and active route signatures are consistent with the intended source. There is no application commit-attestation endpoint; this is not a cryptographic attestation of every in-memory module.
- Latest pipeline: run **321**, success, **07:31:42–08:12:21 CDT**. Earlier run **320** failed; its existing failure was not erased or diagnosed by running model work. No active pipeline/discovery job was found. Existing pipeline scheduling remains enabled by its existing default and was not edited.
- Read-only user/root crontab inspection found no discovery entries; system timer inspection found no discovery timer. No active discovery or resource-intensive model script was found. These inspections registered or changed nothing.
- Four administrator accounts and 31 non-admin accounts exist. No account identity, cookie or Plex token was printed or used to impersonate a production user.

PostgreSQL: **192.168.1.9:5432 / plexintel / jmnovak**, PostgreSQL **18.6**, primary/online; effective service connection matches existing `DATABASE_URL`. Inspections used read-only transactions, bounded statement/lock timeouts and rollback/close. `jmnovak` remains a **superuser**, the previously accepted temporary security exception; this is not a least-privileged database connection.

The exact reviewed V2 catalog matches migrations 001/002, including types, typed PK/FK relationships, integrity/uniqueness constraints, indexes, ACLs and identity sequence. Catalog SHA-256: `e207edf33855a481b740eb9d1193f124000bdc5edc2ffce13dbad9c6fb80af66`. Required existing `app_settings`/`pipeline_runs` columns and table SELECT permissions are present. No new migration, privilege change, write probe or sequence advancement is needed.

Database size was approximately **1.11 GB**; host filesystem available space approximately **846 GB**. This confirms local staging capacity, not free space on the PostgreSQL server's separate data volume. No storage change is needed for this read-only UI.

| Canonical baseline | Current value | Integrity |
| --- | --- | --- |
| Movies / TV / total | 832 / 130 / **962** | Full rows exact to accepted population snapshot |
| Observations | **1,049** | Full rows exact; no orphaned observations |
| Runs | **6** | Full rows exact: three success, three partial; no running run |
| TV classification | **122 eligible, eight provisional** | Actual latest discovery observation semantics; uncertainty retained |
| Duplicate typed identities | **0** | `(media_type, tmdb_id)` remains canonical |
| Source binding | `plexintel-seerr-primary` | All runs use the approved binding; normalized endpoint hash checked privately |

### Incident verification and ten later default rows

The approved cleanup receipt confirms two exact deletions at **October 29, 23:08:59 CDT**. Current inspection independently confirms that neither original `true`/`13:00`, `admin_ui`/`admin` record remains.

The same **keys have subsequently been recreated** among ten metadata-only discovery setting rows, timestamped **October 30, 01:12:42.103906 CDT**. Every one has `raw_value=NULL`, `source=default`, `updated_by=NULL`, and an empty description. This is consistent with the existing startup `sync_setting_descriptions()` path; the specific earlier process/operator that invoked it is not established by row metadata. Their creation predates the current host boot and this inspection. Do not attribute it to this morning's boot merely because startup can create them.

The original 96 settings match the post-cleanup full-row fingerprint exactly: `47af1448565e5162b1f051d5befad330`. Total settings are now **106**, not 96. The initial audit correctly flagged that difference; the separate investigation reconciles it. Literal absence of the two keys is **not** claimed. Effective daily/sweep/refresh intent is false, with no next discovery execution.

An isolated reproduction confirmed startup creates these ten null/default rows without enabling schedules. They already exist in production, so no missing discovery settings row would be introduced by another startup. Existing general startup still executes its customary schema/settings bootstrap; that is another reason not to restart unnecessarily or describe startup as database-write-free.

## Read-only safety, authentication and proxy findings

| Variable | Production source | Effective value |
| --- | --- | --- |
| `SEERR_DISCOVERY_WEB_PREVIEW_ENABLED` | Absent from service environment and repository dotenv; server default | false |
| `SEERR_DISCOVERY_WEB_WRITES_ENABLED` | Absent from service environment and repository dotenv; server default | false |
| `SEERR_DISCOVERY_SCHEDULING_ENABLED` | Absent from service environment and repository dotenv; server default | false |
| `SEERR_DISCOVERY_ENABLED` | Explicit in owner-only private provider file; no enabling override | false |

Private file: `/home/jmnovak/.config/plexintel/seerr-discovery.env`, owner/group **1000:1000**, **0600**. Real configuration loading succeeded without HTTP. The endpoint/key were neither returned nor printed. No persistent configuration change is necessary for the proposed UI deployment.

Every discovery API route uses existing session `require_admin`. Anonymous requests are 401 and non-admin sessions are 403 in isolated route checks. Live unauthenticated overview, inventory, settings, history and job GETs all returned 401. Normal browser login and existing administrator access were subsequently confirmed by the operator. New workspace UI acceptance remains pending; controlled representative signed-cookie probes are documented separately in the remediation report.

The **explicit** session secret is neither absent nor the development fallback, but it matches a common placeholder and fails the application's 32-character signer check. The existing `app.state.agent_session_auth_enabled` check does not protect `require_admin`; a signed `username` session is resolved against the user table. A predictable signer therefore undermines administrator authentication despite role lookups. **Minimum correction:** separately authorize a cryptographically random signer of at least 32 characters in the existing configuration, preserve other values, and restart the existing service only under that authorization. Existing cookies will be invalidated; administrators must sign in again. Do not restore the compromised/weak signer during UI rollback. No session configuration or authentication code was changed here.

Normal login creates username-bearing sessions. Workspace data readers use forced read-only/repeatable-read transactions, no DDL/bootstrap, and explicit public configuration projections. Their production projections were exercised with HTTP blocked, with no data change. The pre-existing token-only session fallback in `get_current_user()` can resolve Plex identity and call `get_or_create_user`; therefore a universal claim that **all authentication GETs** are mutation-free would be inaccurate. Test read-only page acceptance with a normal completed login, and keep login/session normalization distinct from discovery persistence.

Preview and persistence POSTs return 403 before database/job/thread access with these gates. Scheduling PATCH returns 403, and the disabled dispatcher returns before configuration or database access. Page effects request local read endpoints only; they do not call Seerr, submit plans/jobs or save settings automatically. Explicit scope review is a read-only POST and remains available. Posters can initiate bounded TMDB CDN requests through the fixed-host proxy; those are not Seerr calls. No poster/provider request was made during preparation.

Proxy host configuration preserves Host and sets `X-Forwarded-Proto`, routes HTTPS to the existing host backend and forces HTTP to HTTPS. Uvicorn's configured/default trusted forwarding peer is **127.0.0.1**; the actual container/host proxy peer was not proven trusted. Do not assume external HTTPS Origin matches the effective backend scheme. Verify authenticated `/plan` same-origin behavior after separate authorization; writes remain gated even if forwarding differs. Keep spoofed/untrusted forwarded headers untrusted.

Existing session cookies are HttpOnly and SameSite=Lax, but `https_only` is not set, so `Secure` is absent. Existing permissive credentialed CORS configuration was not redesigned. Recommend a separate, narrowly reviewed cookie/proxy hardening change; do not bundle it silently with a frontend swap or weaken origin checks. TLS configuration inspection is not a live browser/certificate/session acceptance result.

The earlier **Tautulli API key exposure should be treated as compromised**. Recommend operator-controlled rotation, updating every actual consumer and verifying access under separate authorization. Redacted saved logs do not revoke a key already emitted into a session. No credential value, provider lookup, test request or rotation occurred in this assignment.

## Current validation and staged artifacts

The full relevant earlier test selection was rerun, rather than trusting its previous result:

- **395 Python tests passed**, zero failures/skips; one harmless anyio pytest assertion-rewrite warning. Discovery, unified TV, readiness/captured/schema regressions, workspace/API/workflow, pipeline services/routes/scheduler and settings were included.
- **Six React SSR/state tests passed**. These are not browser end-to-end tests.
- TypeScript project validation passed; targeted ESLint passed with zero errors/warnings.
- Vite **6.3.4** production build passed using existing Node **26.13.0** at `/opt/homebridge/bin/node`; no dependency installation. Advisory warnings: old Browserslist data and an output directory outside the project. No packages were updated.
- **22 additional offline authorization/gate checks passed**, using synthetic cookies only, all database access forbidden and HTTP forbidden. A sandbox-local ASGI attempt was interrupted when it stalled; the bounded host-context rerun passed. No production mutation attempt occurred.
- Prepared deployment/rollback was simulated successfully in an isolated temporary filesystem, including weak-signer rejection before writes, exact asset checks, owner-only config preservation and restoring the prior index.

The test runner installed an exact fixture DSN guard **before application imports**, rejected a production-shaped DSN before the driver, blocked live HTTP and stubbed unrelated Tautulli context. Every shared alias is also guarded/mocked in workspace tests. The disposable TCP-disabled PostgreSQL 18 fixture was `/tmp/plexintel-seerr-fixture.o1zn07fu`, exact database `plexintel_seerr_fixture`; it has been stopped and removed. Do not run this suite against production or assume plain pytest automatically applies the full runner-wide guard to every unrelated test file.

Private, ignored evidence/package directory, owner-only:

`artifacts/seerr-exploration/2026-10-30-workspace-readiness/`

| Artifact | Purpose |
| --- | --- |
| `production-before.json`, `production-after.json`, `baseline-investigation.json` | Sanitized live state, original drift detection/reconciliation, exact history/settings preservation |
| `security-startup-review.json`, `readonly-boundary-checks.json` | Signer classification, isolated startup effects and authorization/gate evidence |
| `run-isolated-tests.py`, `pytest.log`, `pytest.xml`, `python-test-result.json` | Reproducible guarded Python selection and results |
| `frontend-tests.log`, `frontend-build.log`, `frontend-validation.json` | UI tests, build and TypeScript/lint receipts |
| `staged-frontend.tar.gz`, `staged-frontend-manifest.json` | New five-file frontend package and file hashes |
| `current-frontend.tar.gz`, `current-frontend-manifest.json` | Exact current five-file frontend rollback copy; not a database backup |
| `frontend-release.py`, `test-prepared-release.py`, `prepared-release-test.json` | Prepared operator action, isolated simulation and results |
| `fixture*.json`, setup/server logs | Isolated fixture identity and cleanup |
| `scheduler-process-audit.json` | User/root discovery cron counts, timer inspection and active script check |
| `sanitization-check.json`, `artifacts-hashes.json`, `deployment-packages.sha256` | Credential scan, evidence integrity and package checksums |

Build output also remains at `/tmp/plexintel-content-discovery-readiness-20261030`; use the preserved package if temporary output disappears. Active `frontend/dist` hashes stayed exact throughout preparation. The staged JS is `assets/index-BzMZUqlW.js`; CSS is `assets/index-IlcRsMcW.css`. No Docker image was built or published.

Reproduce tests only after creating a **new** disposable fixture using `prepare-fixture.py`; `run-isolated-tests.py` reads that directory's `fixture.json`. It deliberately cannot use production. Then stop/remove only that owned fixture. Frontend commands used:

```bash
cd /home/jmnovak/projects/plexintel
/opt/homebridge/bin/node tests/frontend_discovery.test.cjs
cd frontend
/opt/homebridge/bin/node node_modules/typescript/bin/tsc -b
/opt/homebridge/bin/node node_modules/eslint/bin/eslint.js src/pages/AdminDiscovery.tsx src/components/DiscoveryState.tsx src/lib/discoveryFormatting.ts src/components/AdminNav.tsx src/App.tsx
/opt/homebridge/bin/node node_modules/vite/bin/vite.js build --outDir /tmp/plexintel-content-discovery-readiness-20261030
```

## Exact proposed deployment procedure — do not execute yet

Session-signing remediation and its separately authorized restart are complete. Normal browser sign-in is now operator-confirmed. Before separately approving the UI swap, recheck the four disabled gates, source binding, current inventory, health and quiet pipeline state. Do not rotate again or repeat the restart. This report is **not** permission to deploy, edit configuration or restart a service.

The existing backend already exposes the reviewed discovery routes. **No backend file placement, pip install, migration or restart is necessary for the static UI swap.** If that runtime fact changes, stop and reassess; do not execute a blind `git pull`, invoke `run_backend.sh` or restart merely because this document mentions the unit. For a separately approved configuration reload, the established service command is `sudo systemctl restart plexintel-backend.service`; it is **not authorized or executed by this assignment** and is not part of the static release command below.

After all blockers are cleared and the operator explicitly authorizes read-only UI deployment:

```bash
set -euo pipefail
cd /home/jmnovak/projects/plexintel
test "$(git rev-parse HEAD)" = bc0495ce1ea0f6c0d98dcc11092e0e4772618f2b
cd artifacts/seerr-exploration/2026-10-30-workspace-readiness
sha256sum -c deployment-packages.sha256
cd /home/jmnovak/projects/plexintel
plexenv/bin/python -B artifacts/seerr-exploration/2026-10-30-workspace-readiness/frontend-release.py deploy-readonly-approved
systemctl is-active plexintel-backend.service
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8489/api/library/health
```

The prepared helper refuses a changed commit, changed active frontend, unsafe source/gates, inactive service, unremediated short signer, package mismatch or previously attempted deployment. It copies the current `.env` and private provider configuration **only when deployment is explicitly invoked**, into owner-only `approved-deployment-preservation/` within the private evidence directory; existing effective configuration files are not edited. Do not publish that directory. It installs new hashed assets before an **atomic index replacement**, retains old assets for cached clients, and makes no database or service call beyond read-only service inspection. A helper guard passing does not substitute for the required fresh operational/authentication checks.

Immediately perform the acceptance checks below and read-only inventory/settings/gate reconciliation. Do not test success by enabling a gate or submitting a live job. No SQL migration/install/restore belongs in this procedure.

## Exact UI rollback procedure — separate operator decision

If the approved UI deployment fails acceptance, preserve evidence and obtain/execute the operator's rollback decision. The previously prepared rollback only restores frontend presentation; it does not remove the already loaded discovery API, restore database state or undo security remediation.

```bash
set -euo pipefail
cd /home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-30-workspace-readiness
sha256sum -c deployment-packages.sha256
cd /home/jmnovak/projects/plexintel
plexenv/bin/python -B artifacts/seerr-exploration/2026-10-30-workspace-readiness/frontend-release.py rollback-ui-approved
systemctl is-active plexintel-backend.service
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8489/api/library/health
```

Rollback atomically restores the exact old index only if the active index is the reviewed staged build and all prior assets are intact. Both asset generations remain to support cached pages; later asset deletion requires a separate housekeeping decision. No restart is required. **Never roll back the database, discovery records or a corrected session signer to undo a UI release.** If a different active build/configuration is encountered, stop rather than overwrite it.

## Post-deployment acceptance checklist

These checks remain **pending**; no deployed-browser success is claimed.

- [ ] Sign in normally after session remediation. Administrator can open `/admin/discovery`; anonymous/non-admin cannot retrieve administrative data. Existing ML Pipeline and other admin navigation remain usable.
- [ ] Overview matches fresh SQL counts (currently 832 movies, 130 TV, 962 total), 1,049 observations, six runs; latest/last complete status definitions match scope semantics. Eight provisional TV titles and their reasons remain visible.
- [ ] Movie and TV lists load; test literal search, language/media/date/classification/status filters, sorting and next/previous pages. Typed title identity, first-discovery timestamps, native TV metadata and provenance are correct.
- [ ] Title details/history load; unknown date/runtime/media/request values remain unknown. Poster loads through fixed TMDB proxy or hides/falls back safely. A poster request is not acquisition or a Seerr API call.
- [ ] All six runs are visible; three historical partial runs remain partial and three successful runs remain successful. Inspect original scopes, pagination/errors/warnings and bounded memberships.
- [ ] Settings show sanitized effective configuration. Preview/persistence and schedule activation are unavailable; every next execution is null. Scope review stays local/read-only and passes legitimate same-origin handling.
- [ ] Verify backend gate enforcement as an authenticated admin using approved non-writing checks: preview/persistence POSTs and scheduling PATCH must return 403 without creating a job or changing a row. Preserve before/after job/settings counts. No enabled gates or live preview needed.
- [ ] Test non-admin direct API access and cross-origin rejection. Confirm actual HTTPS cookie/proxy behavior; do not weaken Host/Origin checks to make a test pass.
- [ ] Reconcile discovery full-row history, settings and no new workspace jobs. Confirm all four gates remain false, private configuration untouched, service restart count stable across the UI swap, and normal existing ML scheduling unchanged.

## Remaining decisions and final recommendation

**GO for separately authorizing read-only deployment**, following completed authentication corrections, final integrity PASS and operator-confirmed fresh login/admin access. Deployment authorization and post-deployment UI acceptance remain pending. Tautulli key rotation remains separate; no unrelated credential was changed.

The UI remains based on the intended commit; the subsequently authorized narrow authentication corrections are uncommitted working-tree changes described in the remediation report. Private preparation artifacts remain ignored. No commit or push was performed.

With browser confirmation received, recommend separately authorizing **the read-only UI deployment only**, using the staged package. Keep all four discovery gates false; do not activate preview, persistence or scheduling. No eligibility/Phase 4 functionality, acquisition, model work or routine synchronization is included. Stop here pending deployment authorization.
