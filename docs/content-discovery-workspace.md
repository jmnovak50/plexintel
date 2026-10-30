# Content Discovery administrative workspace

Implementation prepared on October 29, 2026. **Read-only UI deployed and verified October 30, 2026.** Discovery execution, persistence and scheduling remain disabled. See [deployment PASS report](content-discovery-readonly-deployment.md). Implementation-time and pre-activation statements below are historical; this deployment did not authorize execution or scheduling.

Administrators receive `/admin/discovery` in the existing navigation, with Overview, Discovered Titles, Execution History, and Settings & Scheduling. The implementation uses React Router, AppShell/Tailwind styles, FastAPI session administration, existing PostgreSQL connection/settings conventions, and the host pipeline scheduler. No second web application, scheduling service, acquisition integration, model stage, or canonical discovery schema is introduced.

## Current implementation status

| Capability | Implementation | Initial operational state |
| --- | --- | --- |
| Overview and inventory | Database-backed counts, filters, sorting, pagination | Read-only after deployment |
| Movie/TV details | Typed identities, structured metadata, uncertainty, provenance and bounded membership history | Read-only after deployment |
| Execution history | Canonical run status, original scope/parameters, pagination diagnostics, membership pages | Read-only after deployment |
| Scope review | Validates dates/media/languages and instance ceilings; shows known matches | No Seerr requests or writes |
| Preview jobs | Asynchronous GET-only Seerr collection; workspace job history only | Server gate off |
| Persistence jobs | Asynchronous existing synchronization service and canonical repository | Server gate off; private enablement and explicit confirmation also required |
| Daily/sweep/refresh schedules | Existing scheduler loop and job history; separate slot identities | Server gate off; all new setting defaults false |
| Provider/scope defaults, metadata policy and API limits | Actual private configuration/environment loader | Read-only in UI |
| Scheduling intent | Existing `app_settings` registry, parser and audit author | Editing gated off |
| Job cancellation/replay | Not implemented for discovery workers | ML cancellation refuses discovery jobs; stale work needs operator review |

**Production exception during development:** an early test wrote two production scheduling-intent rows before a missing shared settings-writer mock was corrected. This breached the task boundary; it is not presented as a successful production-isolation result. The operator subsequently approved an exact two-row correction, which committed and passed verification. See the incident section. The implementation has not enabled discovery execution or scheduling.

## Architecture and ownership

- `api/services/discovery_workspace.py`: forced read-only, repeatable-read projections with 15-second statement and two-second lock timeouts. No lazy DDL/settings bootstrap on reads. Existing strict V2 catalog validation runs before queries.
- `api/services/discovery_workflow.py`: request validation, effective settings, feature gates, plan review, asynchronous independent workflow, pipeline-job progress and schedule dispatch.
- `api/routes/discovery_admin_routes.py`: session-admin routes, bounded inputs, same-origin mutation protection, sanitized errors and fixed-origin poster proxy.
- `frontend/src/pages/AdminDiscovery.tsx` and `components/DiscoveryState.tsx`: native administration UI, server pagination, explicit unknown/loading/empty/error states, guarded form submission and job polling.
- `frontend/src/lib/discoveryFormatting.ts`: shared unknown/completeness presentation; `deploy/content-discovery.env.example`: inactive server-gate template, not an installed configuration.
- Existing `app_settings.py`, `pipeline_scheduler.py` and `pipeline_service.py`: scheduling-intent definitions, disabled dispatch hook, and protection against misleading ML cancellation of discovery jobs.

Canonical `(media_type, tmdb_id)` identities, Seerr source binding, detail sanitization, TTL/cooldown, advisory writer lock `(184725,30)`, persistence transactions and partial accounting remain in the established services. They were not modified. Schema migrations 001/002 are unchanged. **No new migration or index is required by this implementation.**

Jobs reuse `pipeline_runs`, with `delivery_type` `content_discovery_preview` or `content_discovery_persist`. Notes hold bounded operation/request/progress/result summaries and the canonical run UUID when persistence occurs. They do not duplicate canonical title/detail history. Each daily, sweep or refresh slot has its own job ID and canonical run ID. Refresh uses the existing `enrich_due` branch and preserves discovery timestamps.

## Definitions and operator workflows

Overview counts are actual PostgreSQL results, not the earlier 962-title reference figures:

- Inventory totals count canonical typed rows. First-24-hour/seven-day counts use `first_discovered_at` against rolling timestamp windows; they are not release-date counts.
- Refresh due counts the inventory against the configured source binding, TTL, failed-attempt cooldown and cache policy. It is a due-work estimate, not a promise that one bounded refresh job processes the whole queue.
- TV classification uses the **latest release-discovery observation** ordered by `observed_at`, then observation ID. Refresh-only observations do not supersede release-window classifications. Classification provenance/fetch times are returned; history remains separately inspectable. This is not global content eligibility or acquisition approval. Multiple historical scopes are not collapsed into an “ever eligible” decision.
- Last complete discovery requires operation `discover`, terminal `success`, and both completeness flags. It applies only to that run's scopes. A successful TV run does not imply complete movie coverage.
- Duration is elapsed start-to-completion, or start-to-current-time for a running run. HTTP attempts/retries are displayed only when recorded. Unknown historical accounting remains unknown.
- `partial`, `failed`, `running` and `success` remain distinct. Reaching a page cap cannot establish completeness. Expected partial tests remain historical partials.

Inventory filters cover text, media type, language, release date, first-discovered timestamps, enrichment status, TV classification, known/unknown media status, known request presence and observed empty requests. Timestamp filters require a timezone and use inclusive `from` / exclusive `to`; date-release bounds are inclusive. Browser local dates/times are converted to UTC timestamps for requests and displayed in the browser's local timezone.

Unknown status/runtime/dates remain unknown; a known zero request count is distinct from unknown requests. TV runtime/release-events are not applicable; episode runtime and season evidence remain native TV metadata. Primary movie dates do not establish digital availability. Title details expose structured genres/cast/crew/release/season evidence, field presence, first provenance and paginated memberships. Raw sanitized source is excluded by default; administrators may explicitly request one title's `diagnostics=true`.

The media-state `known` filter means an explicit valid source status code was observed, not that the title is available. A source code can itself mean unknown; raw codes and field presence are preserved. `unknown` selects missing current codes. Neither filter authorizes acquisition.

Selecting a canonical run displays original query parameters, per-scope page results, warnings/errors and paginated new/existing memberships. Preview jobs appear in workspace job history, not canonical discovery history. Stale heartbeat is explicitly diagnostic, not an invented terminal outcome.

Manual workflow:

1. Select media, explicit inclusive dates, languages, page ceiling and request budget.
2. Review scope without HTTP. Known canonical matches are shown separately from the unknown upstream population; no fabricated workload percentage or API estimate is supplied.
3. After separate server activation, submit GET-only preview or confirm persistence. Persistence confirmation names the scope and limits.
4. Inspect progress and the terminal job/canonical run. Partial results require review; the UI does not automatically resubmit, expand pages, refresh forcibly, or continue incomplete coverage.

## Endpoint contract

All paths below are under `/api/admin/discovery`, require the existing session `require_admin`, and bound pages to 100 records (default 25).

| Method/path | Purpose |
| --- | --- |
| GET `/overview` | Inventory, TV classifications, latest/last complete/running run, active workspace job and diagnostics |
| GET `/titles` | Server filtering, whitelisted sorting, total and page |
| GET `/titles/{movie\|tv}/{tmdb_id}` | One typed title and paginated provenance; optional explicit diagnostics |
| GET `/titles/{movie\|tv}/{tmdb_id}/poster` | Authenticated, bounded fixed-host TMDB thumbnail proxy |
| GET `/runs` | Canonical runs, optional status filter, paginated |
| GET `/runs/{uuid}` | Original scope, pagination diagnostics and paginated memberships |
| GET `/settings` | Nonsecret effective instance configuration, scheduling intent, gates and next executions |
| PATCH `/settings` | Allowlisted scheduling intent; gated |
| POST `/plan` | Validate/review scope; no Seerr HTTP or database mutation |
| POST `/jobs` | Validate/gate and submit an asynchronous preview/persistence workflow |
| GET `/jobs`, `/jobs/{integer}` | Shared pipeline-job progress/history, bounded |

Mutation routes additionally require an `Origin` matching the effective request scheme/host and `X-Discovery-Action: 1`; cross-site fetch metadata is refused. Configure trusted reverse-proxy Host/scheme forwarding correctly. Roles and gates cannot be supplied by the browser. Structured errors expose fixed categories rather than SQL, credentials, private endpoint URLs or response bodies.

Posters use a validated persisted TMDB image path, fixed `image.tmdb.org` origin, no redirects, an eight-second timeout, image MIME allowlist and two-MiB body ceiling. No Seerr API credential, endpoint or requester identity reaches the browser. Successful image data uses bounded in-process caching and private HTTP caching. Unknown/missing images fall back without implying a missing library item. No source poster was fetched during testing.

## Configuration precedence and gates

Provider credentials, source identity, discovery defaults, cache policy and safety configuration remain authoritative in the supported owner-only private file and process environment. The existing loader gives **environment precedence over private-file values**, then defaults. The CLI is unchanged. The UI does not store an API key or overwrite that file. Editing those instance policies through generic `app_settings` would create a conflicting source of truth, so they are read-only here; a future unified configuration-owner change would need separate review.

Manual request media/language/date overrides are explicit scopes; request/page ceilings may only **narrow** the loaded instance limits. Web requests additionally cap attempts at 10,000 and generated query scopes at 128; wider work must be staged explicitly. Scope review does not imply source completeness. The same request budget covers all native date windows, pages, details and retries.

| Server variable | Default | Effect |
| --- | --- | --- |
| `SEERR_DISCOVERY_WEB_PREVIEW_ENABLED` | false | Allow asynchronous Seerr preview jobs |
| `SEERR_DISCOVERY_WEB_WRITES_ENABLED` | false | Permit persistence submissions, additionally requiring existing instance enabled=true and explicit manual confirmation |
| `SEERR_DISCOVERY_SCHEDULING_ENABLED` | false | Allow scheduling management/dispatch, additionally requiring writes gate and instance enablement for dispatch |

Gates accept the literal `true` case-insensitively. They are not editable through the UI. The existing `PIPELINE_SCHEDULER_ENABLED` must also allow the shared scheduler owner. No environment/private configuration was changed in this implementation.

Scheduling intent uses new nonsecret `app_settings` keys:

- `discovery.timezone`: default UTC.
- `discovery.{daily,sweep,refresh}.enabled`: default false.
- `discovery.{daily,sweep,refresh}.time`: defaults 09:00, 10:00, 11:00 respectively.
- `discovery.sweep.day`: Monday=0 through Sunday=6, default Sunday.
- `discovery.sweep.lookback` / `.lookahead`: default 365 / 365 days.

The existing registry/parser/settings writer supplies validation, source, author and update timestamps. Rows override defaults; null/absent scheduling values use documented defaults. No Seerr credential or ingestion policy is bootstrapped into these keys. The broader existing admin Settings page can save inactive scheduling intent, but cannot bypass server execution gates. This workspace's mutation endpoint itself refuses changes while scheduling management is gated off.

## Existing pipeline/scheduler integration

The existing scheduler calls the new dispatcher after its ML scheduling pass. When discovery gates are disabled, dispatch returns **before configuration or database access**. It creates no new asyncio task, cron entry, timer or scheduling service. Long ML runs may miss a discovery slot; there is no automatic catch-up.

- Daily: configured 14-day lookback / 90-day lookahead by default, movies and TV, instance languages, native date slicing. Wider uncached workloads can exceed instance budgets; independently size and authorize them before enabling schedules.
- Sweep: separately bounded weekly date horizon, movies and TV, instance languages.
- Refresh: daily optional bounded `enrich_due`, including out-of-window stored titles; no forced refresh or window membership claim.

IANA timezone slots skip nonexistent spring-forward wall times and use the first occurrence of a repeated autumn hour. A deterministic slot key/request UUID prevents duplicate execution. Dispatch occurs only within five minutes of the slot; missed schedules are not backfilled. A partial/failed slot is not automatically retried. Each operation has a separate slot identity.

Submission serializes its duplicate check with PostgreSQL advisory transaction lock `(184725,31)` and uses the existing pipeline file lock across the full worker lifetime. This coordinates discovery with resource-intensive ML pipeline/cron execution, addressing the observed scoring conflict without blocking browsing or unrelated lightweight operations. Registered active pipeline runs and standalone existing ML script process markers are checked. The original discovery advisory lock additionally protects canonical writes against external discovery CLI processes.

The job is committed before the existing daemon-thread pattern starts work. Callbacks update heartbeat/progress in the shared pipeline history; terminal notes retain bounded counts, errors and canonical run linkage. The worker directly calls the existing discovery service; it never builds browser-supplied shell commands or calls model stages.

Idempotent retries of the **same submission UUID and exact request/user** return the same job. Changing scope with the same UUID produces 409. Different submissions cannot concurrently acquire the shared resource lock. An unfinalized canonical run blocks web submission for explicit operator recovery review; the web UI is not an implicit authorization to repair old runs.

## Performance/schema review

No canonical schema changes or production migrations were made. Existing typed PK/FK/uniqueness, title/date/language and title-observation indexes support bounded joins and histories. Inventory lists never select large source JSON. The latest classification lookup uses the typed title-observation index; only small eligibility/provenance fields are projected. Full detail/source extraction occurs for one selected title; run memberships and title histories are paginated. Dashboard refresh does not scan large source snapshots.

Substring text search uses bound/escaped `ILIKE`; it may scan the narrow canonical relation at larger scale. Offset pagination and exact total counts also have scaling costs. Do not claim a production query-plan benchmark or invent an index requirement from the small reference inventory. Measure actual latency/EXPLAIN before separately reviewing a trigram index or cursor pagination. Read queries have explicit timeouts.

Shared pipeline job retention can remove old workspace job summaries under the existing policy; canonical discovery run/observation history remains independent and immutable. Discovery observations continue growing under the existing model. Scheduling activation requires a measured wider-window HTTP/storage plan; no retention deletion or backfill is included here.

## Validation

The test fixture is a **new**, TCP-disabled PostgreSQL 18 cluster under `/tmp/plexintel-seerr-fixture.*`, exact database `plexintel_seerr_fixture`. Existing guarded migration fixtures apply 001/002 there only. After the incident, the suite-wide connector rejects every target other than that exact fixture before connecting; new tests also guard/mimic every shared connection alias. Live HTTP is blocked. Unrelated recommendation poster/server context is stubbed rather than invoking Tautulli.

Verified results:

- **395 Python tests passed**: discovery, unified TV, readiness remediation, captured fixture regressions, new workspace/API/workflow tests, pipeline services/routes/scheduler and application settings.
- **Six React server-rendered UI-state/formatting tests passed**: loading, empty, escaped errors, ready state, unknown versus zero/false, and partial versus complete status.
- TypeScript project check passed; Vite production build passed into **`/tmp/plexintel-discovery-workspace-build`**. Existing `frontend/dist` was not replaced. The local Node runtime was used directly; no dependency installation or service change was needed.
- Targeted ESLint checks passed with no errors or warnings. The disposable cluster was stopped and removed after validation.

Coverage includes admin/session refusal, same-origin mutation checks, typed collisions, literal search/filters/paging, title/run provenance, unknown/provisional metadata, historical read immutability, disabled gates before job creation, confirmation/ceiling validation, duplicate/concurrent requests, shared ML lock/process conflicts, slot idempotency/disabled defaults/DST, isolated preview/persistence and refusal of implicit recovery. SQL tests use synthetic/captured responses, never live Seerr.

Reproduce with a **new guarded isolated fixture**, not production credentials:

```bash
# SEERR_DISCOVERY_TEST_DSN must identify the verified, TCP-disabled fixture.
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' plexenv/bin/python -B -m pytest -q tests/test_content_discovery.py
/opt/homebridge/bin/node tests/frontend_discovery.test.cjs
cd frontend
/opt/homebridge/bin/node node_modules/typescript/bin/tsc -b
/opt/homebridge/bin/node node_modules/vite/bin/vite.js build --outDir /tmp/plexintel-discovery-workspace-build
```

The saved development runner documents the stronger suite-wide DB/HTTP guard used for the full 395-test run. Node's absolute path is this host's available runtime, not a new runtime requirement. No full browser interaction/screenshot, deployed UI or live production endpoint validation is claimed.

## Development isolation incident — approved cleanup completed

At **October 29, 08:37:19.912384 CDT**, an early new settings test mocked workspace/pipeline connections but missed `app_settings.connect_db`. The shared settings writer used the existing production URL and wrote:

| Key | Value | Source / author |
| --- | --- | --- |
| `discovery.daily.enabled` | `true` | `admin_ui` / `admin` |
| `discovery.daily.time` | `13:00` | `admin_ui` / `admin` |

This was an unauthorized production mutation. Testing paused; read-only investigation confirmed the two rows, and a metadata-only audit found no other settings updated since 08:11 CDT. Both keys are absent from the earlier validated archive; that archive is not an immediate pretest snapshot. No discovery synchronization, acquisition, model operation, backend restart, migration or deliberate schedule activation occurred. The execution gates and private enabled=false remain safeguards; the stored true intent must not be mistaken for an enabled operational schedule.

A separate read-only runtime check confirmed the backend PID/start/restart state matches the population baseline, its command has no reload flag, all three server discovery feature flags are false, and persistent discovery remains false. Editing the checkout did not hot-reload or activate this workspace.

The final read-only preservation check passed strict V2 validation and compared **every canonical row, observation and run** to the accepted population snapshot: **962 titles, 1,049 observations and six runs remain exact**. That discovery-data result does not erase or excuse the two settings mutations above.

The code/test mock was corrected. New tests reject non-fixture connections independently of module aliases, and a regression explicitly verifies rejection of a production-shaped DSN. The subsequent broad suite ran with an exact fixture guard and all HTTP blocked.

A blocked unrelated Tautulli request exposed an existing credential in its failure traceback within this session. Saved logs were redacted, and that external lookup is stubbed in the offline runner. No credential was rotated or repeated in this report.

Following explicit operator approval, the exact two-row corrective cleanup committed successfully on **October 29, 2026, 23:08:59 CDT**. It required exact value/source/author/timestamp matches under row locks and exactly two returned keys before commit. Post-commit reads confirmed both keys absent, all **96 other settings unchanged** by full-row fingerprint, and discovery counts unchanged at **962 titles / 1,049 observations / six runs**. Persistent discovery remains false; no synchronization, schedule activation, backup or service control occurred. The original breach remains recorded rather than being reclassified as successful isolation. Private evidence includes `approved-cleanup-attempt.json`, `approved-cleanup-result.json`, the exact guarded operation and the original SQL proposal:

`artifacts/seerr-exploration/2026-10-29-workspace-development/`

Do not state that production settings remained untouched: two unauthorized writes were followed by an explicitly approved corrective deletion. The two incident rows are now absent, so the new scheduling keys again fall back to their disabled defaults. No credential rotation occurred; the earlier session traceback disclosure remains a separate recorded concern.

## Production activation requirements and remaining limits

**Implementation prepared; corrective settings cleanup PASS. Deployment and production activation still require separate authorization.**

1. Corrective settings cleanup is complete and verified. Before a future deployment, reconfirm private discovery remains disabled, effective web/scheduling gates are false, and scheduling intent is inactive. Review the recorded credential-trace concern separately.
2. Review the implementation, current strict V2 schema/source binding, existing pipeline schema/ACLs and inactive settings. No optional canonical migration is needed.
3. Separately approve deployment/build placement and backend restart. None occurred here. Verify admin/non-admin behavior, actual inventory/history definitions, posters, filters and unknown states with the deployed read-only workspace first.
4. Before enabling previews, authorize a bounded GET-only test and its workspace job-history writes. Before persistence or scheduling, approve scope/budgets, quiet window, recovery/RPO, monitoring and observation storage. An older recovery-point exception from the population task is not standing authorization here.
5. Enable only the individually approved server gates and per-operation intent. Do not bundle scheduler activation with UI deployment or begin Phase 4/acquisition work.

The inherited daemon-thread execution model is not a durable queue: backend/process loss can leave a started job and possibly an unfinished canonical run. The UI displays stale heartbeat; it never invents completion, automatically repairs history or replays work. Safe restart/recovery requires operator review and existing canonical recovery procedures. Discovery workers cannot be cancelled through the ML process-group endpoint. Submission locking assumes the existing single-host/shared-lock deployment convention; multi-host orchestration needs separate design. These are explicit operational limitations, not a new scheduling architecture.
