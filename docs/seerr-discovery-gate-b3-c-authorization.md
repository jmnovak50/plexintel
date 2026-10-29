# Gate B3-C — incremental synchronization and recovery authorization package

**Conditional GO to seek separate approval of one C-page execution after natural metadata TTL expiry. NO-GO for execution now:** this is preparation only, and the 20 existing movies are currently cached. No Seerr HTTP, production synchronization/write, migration, configuration/service/schedule change or model/acquisition operation occurred.

The proposal uses the **unchanged C-page command** from [the accepted B3 plan](seerr-discovery-gate-b3-plan.md). It minimizes production invocations by combining old-title natural re-enrichment and a larger discovery prefix in one future manual run. It does not minimize HTTP calls. No C-refresh invocation, forced refresh, failure injection or automated wait/schedule is included.

## 1. Independently verified baseline

**Production observation, October 29, 2026, 00:13:35 CDT:** a forced read-only, repeatable-read inspection compared all fields to accepted B3-B evidence.

| Gate | Current result |
| --- | --- |
| Production connection | `192.168.1.9:5432 / plexintel / jmnovak`, PostgreSQL 18.6 primary; same effective connection as the direct-host backend |
| Canonical inventory | **28 titles: 20 movies and 8 TV**, all fields/identities/fingerprints match B3-B |
| History | **48 observations / 3 terminal runs**, every prior record unchanged; no duplicate/orphan/unfinished run |
| B2 / A / B | `04a7bb18-290a-42f1-86be-c0698330e3a8` partial; `e0f62c8a-892d-47b6-a6ff-0944ab46af1d` success; `6b94d68a-cd67-4570-bc9c-ccdb14087bc5` partial |
| Source | Every run and canonical enrichment uses `plexintel-seerr-primary`, key `4547479bd1da2cd5fab4ff1af5e07bb9617e2dd37900447eb261491ec5330139` |
| Schema/permissions | Original 001/002 committed-install receipts and reviewed file hashes verify; exact V2 catalog/strict runtime guard and all 11 required table/sequence ACL checks pass; sequence 48/is_called=true |
| Configuration | Actual loader disabled, owner 1000:1000/mode 0600/hash unchanged; endpoint/key reused privately; cache enabled, TTL 24 h, failed-attempt cooldown 1 h |
| Isolation | Same backend PID/start/restart count, 40 application-table counts, unrelated catalog/roles/ACLs/default grants and schedules; no conflicting writer, running pipeline/model job or discovery timer |
| Recovery evidence | Validated logical archive checksum and prior isolated restore PASS/40 matching tables, with required vector/vchord dependencies present |

All **17 baseline checks passed**, including canonical/source-fingerprint recomputation. `jmnovak` remains the **accepted temporary PostgreSQL superuser exception**, not a least-privileged connection; role separation remains deferred. No credentials or privileges changed.

The validated archive remains `plexintel-20261028T231846Z-08d8dc.dump`, SHA-256 `8754923a28ed13c140cb269e59b2389786e4d653e6cfbfcf14bb46fb06d52f1a`; its snapshot is **October 28, 18:18:46 CDT**, before all discovery writes. It does not recover B2/A/B inventory, establish PITR or prove complete application recovery. No backup/restore was performed here. At the earliest suggested execution window it would be about **28 hours old**. Recovery readiness for that future window is **not yet PASS**: the operator must accept that recovery point or separately authorize and validate a newer PostgreSQL-consistent backup. Do not silently infer coverage from archive existence or preparation approval.

## 2. Evidence matrix

| Behavior | Already verified in production | Isolated evidence, including this task | Remaining live claim |
| --- | --- | --- | --- |
| New canonical titles/enrichment | B2 inserted 20 movies; A added 8 TV | Latest B3-B snapshot plus composed second page adds 20 movies without overwriting old records | Movie additions mixed with existing-title refresh in a two-page invocation |
| Repeat identities/observations | B: same 20 movies, one GET, 20 new observations; 28 titles retained | Latest captured history remains exact across new invocations | Do not repeat a fully cached run solely to re-prove B |
| Changed detail metadata | No live detail delta has been proven; B used cache | Natural TTL test hides a synthetic synopsis delta before expiry, then records exactly one changed fingerprint/time after expiry, without `--refresh` | Real upstream deltas cannot be guaranteed; a fresh identical response proves refresh, not a change |
| Natural cache expiration | Production cache reuse/fetch age proven; no expired-existing-title GET yet | Latest 28-title baseline naturally expires: 40 detail fetches, 42 adapter calls, one changed old title, 20 new titles | C should exercise returned existing movies through the ordinary expiry path |
| Incomplete pagination | B2/B correctly recorded page 1/6 and terminal partial; B2 history survived A/B | Two-page composed replay retains earlier partial history and adds memberships | Bounded first-two-page continuation, with truthful remaining incompleteness |
| Budget exhaustion | Hard budgets recorded, never exhausted live | Real GET client with mock session stops at two attempts; 19 deferred titles get no fabricated attempt time; later isolated run progresses | No deliberate production exhaustion proposed |
| Transient detail failure/cooldown | B1 had failures; targeted GETs resolved them, but no persistence-failure cycle proven | Latest fixture: one failed detail preserves metadata; cooldown defers only that title; ordinary eligibility later fetches it | No production failure injection or immediate retry |
| Abandoned `running` run recovery | No production interruption or abandoned run | Latest fixture retains pending observations; wrong-source run cannot recover/write/call HTTP; correct-source later run reconciles only abandoned history | Intentionally not exercised by C; any unexpected running run is a preflight stop |
| Unknown metadata/source identity | B2/A/B retained null statuses, date/runtime gaps, typed keys and source binding | Existing and new tests cover collections, source guards, collisions and old history | Preserve these invariants for whatever source returns; no availability/acquisition inference |

The second-page fixture is **composed** from B2 page-1 data and 20 other B1 captures for the same day. It is not evidence of actual current Seerr page-2 membership/order. No live source population was queried during preparation.

## 3. Smallest proposed production validation

Perform **one movie-only C-page invocation** in a future manually approved quiet window, after all 20 existing movie entries become fetch-eligible through ordinary TTL expiration.

- Date range: **2026-10-28 through 2026-10-28**; language **all**; ascending primary release date; page cap **2**.
- Same scope key as B2/B: `11f0c306e3ee8d54e487e574396055b28229a5a72a61e85120248ab219e3d0f9`. The CLI **starts again at page 1**; it does not resume page 2 or reuse an old run ID.
- Hard budget **45 total HTTP attempts**, retries **0**, timeout **10 seconds**, spacing **1 second**, Retry-After ceiling **5 seconds**. One new run only; no `--refresh`/`--enrich-due`/TV scope.
- Current last-enriched values expire between **October 29, 22:07:18.286136 and 22:07:37.190507 CDT**. Suggested earliest manual time: **October 29, 22:08 CDT**. This creates no timer, reservation, sleep or permission to execute. Recompute actual `cache_action(..., force=False)` immediately before execution; all 20 old movie rows must return `fetch` under the unchanged 24-hour TTL, successful prior status and source binding.
- A run while those movies remain fresh would exercise a different branch and repeat already proven cache behavior. It is not the stronger validation proposed here; do not change TTL or force refresh to bypass the condition.

**Exact command — proposal only; do not execute under this task:**

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=45 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type movie --start 2026-10-28 --end 2026-10-28 --language all --sort-by primary_release_date.asc --max-pages 2 --json
```

Run from `/home/jmnovak/projects/plexintel` using the direct host environment. Inline enablement is process-local; persistent configuration remains false. No preliminary dry-run/status/detail request is included; a dry run issues HTTP.

Under an unchanged 20-row-per-page population, expect **40 unique movies**, including the 20 existing ones and 20 new ones. After expiry all 40 require details: **2 page GETs + 40 detail GETs = 42 attempts**, within 45. Expected totals: **48 canonical titles, 88 observations, four runs**. These are conditional counts, not targets or caps imposed on titles. Different page size/membership, duplicates or invalid metadata must be reported; the hard page/attempt limits still apply. The timeout bounds individual requests, not end-to-end wall time.

## 4. Expected effects and acceptance

Let S be the fresh pre-state canonical typed-key set and R the retained keys returned by the two pages. Require canonical after-state **S∪R**, new keys **R−S**, and exactly one new observation per `(new_run_id,media_type,tmdb_id,scope_key)`. Under one scope that is |R| observations, not zero; new observations are correct even for unchanged metadata.

All three prior terminal run rows and all **48 prior observations** must remain exact. First-discovery run/time and typed `(media_type,tmdb_id)` identity remain immutable. All eight unselected TV rows, including their provisional diagnosis/season provenance, remain exact. Missing titles are not deleted; earlier memberships remain in history.

Returned old movies advance discovery bookkeeping and, on successful natural fetch, last-enriched/attempt time and observation detail-fetch time. Identical projected metadata retains fingerprint and metadata-change time; a changed projection updates them and records changed fields. Cache age changes only after a real detail fetch. New titles acquire their own provenance. Recompute projections/fingerprints from sanitized detail/discovery evidence; never assume a summary change refreshed canonical detail metadata.

Unknown dates/runtime/media/request statuses remain explicitly unknown, not absence, ineligibility, availability or zero requests. Unknown release collections preserve prior events; authoritative complete emptiness follows the already reviewed source semantics. Historical snapshots retain previous values when current metadata changes. Primary release date does not establish digital availability. No engagement/model scoring or acquisition criterion is introduced.

**PASS for incremental/refresh mechanics:** positive overlap with existing movie keys, at least one genuinely new movie key, successful ordinary TTL-based detail retrieval for returned existing movies, and reconciled identity/provenance/history/budget/isolation invariants. Report exactly how many old/new keys were exercised. A real metadata delta is an additional observation, **not guaranteed**. If every fresh response is identical, report metadata-change handling as isolated-test evidence, not live proof.

**INCONCLUSIVE for an unexercised objective:** no new keys, no old-key overlap, no successful old-title detail fetch, an empty response, or safely contained API/deferred/failed work preventing the intended validation. Source drift is not automatically corruption. Do not automatically expand/rerun to manufacture coverage.

**FAIL:** wrong source/scope/bounds, duplicate/overwritten/lost identities, changed immutable history/TV rows, unexplained fingerprint/fetch timestamps, missing accounting or production-isolation violations.

Expected terminal outcome remains **partial / exit 2** if the source still reports six pages/111 titles: page 1+2 is incomplete but can have enrichment complete. The only expected page error is `page_limit_exceeded`. If the entire source now fits within two pages, correctly accounted success/exit 0 is acceptable. Exit 1, lock exit 75 or other errors require read-only investigation; no automatic retry. Provisional TV semantics are unaffected because TV is not queried.

## 5. Fresh preflight and exact read-only verification SQL

Before using future approval, independently revalidate target/backend URL, 001/002 provenance, reviewed runtime/migration/SQL hashes, strict installed catalog, required ACLs, source bindings, owner-only disabled config, recovery readiness/RPO, exact 28-title/48-observation/three-run accepted baseline, absence of `running` runs/writer locks/conflicting jobs, and unchanged protected service/schedule/application state. Stop for any material or ambiguous difference; no repairs under the approval. Then verify all 20 old movie cache actions are ordinary `fetch`, resolve exactly one proposed scope locally, capture a fresh full baseline and create a single-attempt marker in a new private evidence directory.

Prepared SQL: [post-run-verification.sql](/home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-29-gate-b3-c-preparation/post-run-verification.sql). **25 single-statement SELECT blocks passed EXPLAIN-only validation** in a forced read-only production session. No future C verdict was evaluated. Original B3-B SQL/evidence remains unchanged.

For an approved future post-check, execute each named block separately in a forced read-only/repeatable-read transaction using the existing connector privately, 15-second statement timeout and two-second lock timeout. Bind `run_id` to the **actual new C UUID**, and `before_titles`, `before_runs`, `before_observations` to `psycopg2.extras.Json` arrays from the **fresh pre-execution snapshot**, not post-state or reconstructed data. Assert every marker is recognized and each block has exactly one statement before execution.

The SQL covers prior run/observation equality; canonical identity union/first provenance; unchanged unselected TV/movies; scope/source bindings; observation uniqueness/orphans; run memberships and detail outcomes; unknown-field audit; sequence; exact C limits; natural TTL fetch age and metadata-change timestamp semantics. Clean-case anomaly sets must be empty. Classify nonempty fetch diagnostics as operational incompleteness versus actual integrity failures; do not label legitimate source changes corruption. Numeric cross-media ID overlap is diagnostic, not a violation of the composite key.

Additionally run the exact catalog/runtime guard and 11 ACL checks and existing read-only `--summary --json` report. Reconcile full CLI/durable run/summary IDs, parameters, counts, pagination, status, errors and warnings. Validate all source/canonical fingerprints and actual metadata projections offline. For a clean all-fetched 40-title prefix, require 40 successful details, zero cache/failure/deferred/pending, 42 attempts/zero retries; classify old updates from real deltas rather than forcing an update count.

Compare all preexisting history/TV records, protected application counts/schema/roles/ACLs, backend PID/start/restart count, cron/timers, config hash/disabled state and source/evidence files. Application comparison covers counts/catalogs, not exhaustive row-value checksums. Sequence may contain safe gaps after rollback but must stay owned and ahead of committed IDs. Save sanitized stdout/stderr, exit/run ID, every typed identity/outcome/change diagnostic, pre/post snapshots and SHA-256 manifest, then stop.

## 6. Recovery behavior and stop procedure

**Terminal partial versus abandoned running:** ordinary later synchronization creates a new run and observations. It never rewrites a completed B2/B3-B partial into success. The current gate must not deliberately create a `running` remainder. Any unexpected running run during preflight is a stop, not permission to invoke automatic recovery.

**Budget exhaustion:** the client checks its global attempt budget before GET. Already committed pages/enrichments remain; unfetched details are deferred without a fabricated attempt timestamp. A subsequent separately authorized run starts at page 1, applies ordinary cache/cooldown logic and adds its own observations. It does not resume a cursor or guarantee the upstream page population is unchanged.

**Transient failure:** a real failed GET preserves prior canonical detail values, records failed status/error/attempt time, and observes the one-hour failed-attempt cooldown. A within-cooldown later run records deferred work; no immediate retry is proposed. Partial progress is not absence or ineligibility.

**Interruption:** after acquiring the exclusive session lock, the implementation validates schema and source before reconciling only abandoned `running` runs. Committed observations determine recovered title/enrichment counts; the abandoned run becomes partial if it has titles, failed if empty, with explicit interruption/recovery diagnostics. Original pending observations remain. A new invocation gets a new run ID. Recovery cannot reconstruct unrecorded HTTP attempts or a complete lost pagination trace; never invent zero requests or complete coverage for the interrupted run.

Operator procedure after an unexpected outcome:

1. Preserve the single-attempt evidence and inspect actual process/lock/run state read-only. Do not retry, kill/restart a production service or alter records to make the gate pass.
2. Reconcile committed canonical/observation sets, fetch outcomes, missing metadata and available request accounting. If a writer remains active or state is ambiguous, stop without cleanup mutation.
3. For terminal partial work, leave history intact. For an abandoned running record, prepare a distinct recovery authorization/baseline describing expected history reconciliation and unknown HTTP accounting. Neither case is covered by the original one-attempt approval.
4. Only after separate approval may a normal reviewed writer acquire the lock, revalidate source/schema and perform its built-in recovery/ordinary eligibility checks. No direct run-status DML, injected failure, fabricated title, V1 rollback SQL or full-database restore is authorized here.
5. Data-integrity or unacceptable recovery-point concerns require their own corrective approval. Discovery remains persistently disabled throughout.

## 7. Isolated validation and independent review

**282 focused tests passed, zero skipped**, plus both existing captured-movie and synthetic-unified replays, **zero actual HTTP**. The dedicated UTF-8 PostgreSQL 18 fixture used a private `/tmp/plexintel-seerr-fixture.*` socket, exact `plexintel_seerr_fixture` name and TCP disabled; guards verify target/data directory before DDL. Production `DATABASE_URL` was cleared; real requests were blocked. Only the disposable database received test writes/migrations. It was stopped and removed after validation.

Six new regressions in [test_seerr_gate_b3_c.py](/home/jmnovak/projects/plexintel/tests/test_seerr_gate_b3_c.py) copy the latest B3-B 28-title/48-observation/three-run snapshot, rebinding only fixture provenance to a fictional source:

1. Fresh two-page composition: 20 cached + 20 new, 22 adapter calls; prior terminal history/TV unchanged.
2. Naturally expired two-page composition: 40 details, 42 adapter calls; 20 new titles and exactly one synthetic existing metadata delta, without forced refresh.
3. Changed source detail is hidden by fresh cache, then observed after natural expiry, with correct change/fetch timestamps.
4. Failed detail preserves metadata; cooldown defers only that title; later ordinary eligibility retrieves it.
5. Real client's two-attempt mock budget defers 19 without false attempts; a later isolated run progresses and preserves terminal partial history.
6. Abandoned pending run: wrong source fails before recovery/HTTP; correct source later reconciles pending counts while preserving the 48 original observations, three terminal runs and all TV data.

Existing tests cover zero/unknown release collections, missing/contradictory TV evidence, typed collisions, schema/ACL/source guard ordering, transaction rollback and empty/mixed inventory cases. These prove controlled mechanics, not live failure recovery or a real upstream metadata delta.

Reproduce with a new guarded TCP-disabled UTF-8 fixture per the [existing persistence instructions](seerr-discovery-persistence.md), frozen B1/B2/B3-B captures and `SEERR_DISCOVERY_TEST_DSN` set only to that fixture:

```bash
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' plexenv/bin/python -B -m pytest -q tests/test_seerr_discovery.py tests/test_seerr_unified_discovery.py tests/test_seerr_readiness_remediation.py tests/test_seerr_exploration.py tests/test_seerr_phase2.py tests/test_schema_migrations.py tests/test_seerr_gate_b3.py tests/test_seerr_gate_b3_c.py
plexenv/bin/python -B -m tests.replay_seerr_discovery
plexenv/bin/python -B -m tests.replay_seerr_unified_discovery
```

The saved task runner records the HTTP-blocked wrapper used. The private fixture descriptor was removed after cleanup; recreate an independent fixture before reproducing. Do not point tests at production or treat captured source facts as current.

The explicitly requested separate reviewer endorsed the unchanged C-page command with the natural-expiry manual window as a way to combine remaining live paths in one invocation, while flagging unguaranteed source deltas/new IDs and the future backup-age gate. Its final offline review independently matched the saved B3-B baseline, confirmed all 25 separately recognized SQL blocks and the 282-test evidence, and concluded **preparation GO, no remaining blocker**. It confirmed the terminal-partial/abandoned-run distinction and unrecoverable HTTP accounting limitation. No database/network call or edit was made by the reviewer. Findings are retained in `independent-review.md` in the evidence directory.

Final read-only observation at **October 29, 00:21:31 CDT** again matched all 28 canonical rows, 48 observations, three runs and the 12 target/schema/ACL/application/service/schedule/configuration baseline groups. No discovery record was created during preparation.

## 8. Recommendation and authorization boundary

**Preparation: GO. Proposed future C-page: conditional GO after all natural-TTL, recovery/RPO and fresh baseline/quiet-window checks pass. Execution now: NO-GO.** The earliest suggested time is October 29 at 22:08 CDT, subject to fresh eligibility and explicit approval, not an automatically scheduled operation.

The future approval must authorize **exactly one** execution of the section 3 command, max two pages/45 attempts, zero retries, natural TTL behavior, no forced refresh, plus read-only pre/post audit. It does not authorize another run to obtain a metadata delta, recover a failure, finish pagination, repeat TV or activate scheduling.

Evidence directory: `artifacts/seerr-exploration/2026-10-29-gate-b3-c-preparation/`: live `before.json`/baseline assessment/cache audit, reviewed hashes, prepared command/SQL and EXPLAIN results, isolated tests/replays/logs/cleanup, independent review and final boundary/manifest. No production data/configuration/service, model or acquisition changes were made. **Stop after this package. C execution requires separate explicit authorization.**
