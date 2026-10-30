# Content Discovery — read-only production deployment

**PASS — October 30, 2026.** The operator-authorized frontend deployment completed at **12:39:20 CDT** on `birch`; final database/service comparison passed after the browser checks. Open [Content Discovery](https://plexintel.kabolly.com/admin/discovery), or refresh the existing browser page to load its navigation.

## What changed

Installed the reviewed frontend package built from commit `bc0495ce1ea0f6c0d98dcc11092e0e4772618f2b`. The already-running backend includes the separately authorized authentication corrections; no further backend restart or application configuration change was needed.

Exact executed command, from `/home/jmnovak/projects/plexintel`:

```bash
plexenv/bin/python -B artifacts/seerr-exploration/2026-10-30-workspace-readiness/frontend-release.py deploy-readonly-approved
```

Exit **0**. New hashed assets were installed first, then `frontend/dist/index.html` was replaced atomically. Actual TLS-served HTML/JS/CSS/shared assets matched the staged manifest. The new bundles are `assets/index-BzMZUqlW.js` and `assets/index-IlcRsMcW.css`; prior assets remain available for cached clients and rollback.

The helper preserved byte copies of the current application/provider configuration in the private `artifacts/seerr-exploration/2026-10-30-workspace-readiness/approved-deployment-preservation/` directory (**0700**), files **0600**, owner **1000**. These are private configuration copies, not a database backup. The source files were not edited. Do not publish that directory.

## Acceptance and integrity

| Check | Result |
| --- | --- |
| Fresh production preflight | PASS: target/schema/source binding, completed pipeline slots, quiet active-work state, corrected authentication and disabled gates |
| Canonical inventory | **832 movies / 130 TV / 962 total**, unchanged |
| TV classification | **122 eligible / eight provisional**, uncertainty retained |
| Historical records | **1,049 observations / six runs**, unchanged; success and partial states remain distinct |
| Browser acceptance | **15 Firefox 158 checks passed**: overview/counts, admin navigation, paging, TV/provisional filters, unknown fields, search empty state, title provenance, six-run history, run diagnostics and disabled controls |
| API acceptance | Admin reads succeed; anonymous **401**, non-admin **403**; preview/persistence POSTs and scheduling PATCH are refused with **403**; workspace jobs remain **0** |
| Posters | One authenticated fixed-CDN thumbnail request returned **200**, valid JPEG and private cache headers; no Seerr call |
| Database preservation | All **43 application tables** match fresh pre-deployment logical row fingerprints; catalog/ACLs, discovery schema/history/sequence and scheduling configuration match |
| Services/configuration | Backend PID **169181**, start/restart state unchanged; database credentials, signer, service unit, token file and private provider file unchanged |
| Static rollback | Prior index/archive and original assets retained; no rollback was necessary |

Firefox used an ephemeral profile with a representative signed administrator session. Only the production hostname was resolved locally to the production TLS proxy; the real certificate was verified. The profile was removed afterward. This is deployed-browser evidence, separate from the operator's earlier successful normal Plex login, and does not claim a fresh test through every public ingress path.

The first browser pass reached history but timed out on an incorrect test close-button label. The selector was corrected and all 15 checks passed; no application change or redeployment occurred. Firefox environment warnings were not application authentication failures.

## Operational boundaries

All effective flags remain false:

```text
SEERR_DISCOVERY_WEB_PREVIEW_ENABLED=false     # absent; server default
SEERR_DISCOVERY_WEB_WRITES_ENABLED=false      # absent; server default
SEERR_DISCOVERY_SCHEDULING_ENABLED=false      # absent; server default
SEERR_DISCOVERY_ENABLED=false                # explicit private configuration
```

Scheduling intent remains inactive and no next discovery execution is registered. Scope review remains available because it is a local read-only operation. No discovery request, synchronization, acquisition, model job, schedule change, migration, backend restart or production database write was performed by the deployment/probes. Existing background services were left running; logical row/catalog preservation was independently checked rather than asserting unrelated services issued no SQL.

No commit, push, image build or Docker deployment occurred. The existing direct-Python backend and prior narrow authentication working-tree changes were preserved. This authorizes no later execution or scheduling activation.

The repository already tracks the previous `frontend/dist` build. Deployment therefore leaves its index modified and the two new hashed bundles untracked. Those files are the active served UI; no Git reset/cleanup, packaging change or commit was performed.

## Rollback and evidence

If subsequently needed under an operator rollback decision, from the repository root:

```bash
plexenv/bin/python -B artifacts/seerr-exploration/2026-10-30-workspace-readiness/frontend-release.py rollback-ui-approved
```

The guarded helper restores the old index atomically while retaining both asset generations. It does not restart the backend, alter discovery data, restore configuration or undo security remediation.

Private sanitized evidence: `artifacts/seerr-exploration/2026-10-30-discovery-readonly-deployment/` — deployment receipt, before/after table fingerprints and service/configuration comparisons, API checks, browser results/screenshot, served-asset checksums and poster check. Configuration values, credentials and session cookies are excluded from normal evidence.

**Read-only deployment: PASS.** Content Discovery is available to administrators. Execution, persistence, refresh jobs and scheduling remain disabled; any activation requires separate authorization. The separately recorded Tautulli credential concern and valid-live-token MCP/client acceptance limits are unchanged by this UI deployment.
