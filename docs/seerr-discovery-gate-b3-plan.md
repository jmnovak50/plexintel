# Gate B3 authorization package — TV, repeats and incremental discovery

**Planning complete; no B3 execution authorized or performed. Recommend GO for seeking approval of Scenario A alone, conditional on fresh pre-execution checks.** Do not run the writer commands below under this planning authorization. Scenarios B, C and every subsequent invocation require separate approval. Persistent discovery remains disabled.

Evidence classes below are explicit: **production observation**, **code finding**, **isolated test**, or **live assumption**. Historical captures do not establish today's Seerr population. `--dry-run` performs HTTP; it is not permitted during this task.

## 1. Verified production baseline

**Production observation, October 28, 2026 at 22:50 CDT:** a repeatable-read transaction forced read-only at connection and transaction level verified:

| Gate | Verified result |
| --- | --- |
| Target | `192.168.1.9:5432 / plexintel / jmnovak`, PostgreSQL 18.6, primary; same effective connection as host backend |
| Schema | Installed V2 exactly matches the reviewed 001→002 catalog and current strict runtime guard: 3 tables, 68 columns, 24 core constraints plus NOT NULL constraints, 11 indexes and owned identity sequence |
| Provenance | Reviewed migration/runtime/helper checksums remain valid; prior committed-install receipts and Gate A verification remain authoritative; no migration rerun |
| Run | Only `04a7bb18-290a-42f1-86be-c0698330e3a8`; terminal `partial`, completion timestamp present, `page_limit_exceeded` |
| Durable inventory | 20 movies, 0 TV; 20 discovery observations, one scope membership per movie; all 20 enrichment outcomes successful |
| HTTP history | B2 recorded 21 attempts of 25, zero retries; 1/6 pages, 20/111 reported titles; discovery incomplete, enrichment complete |
| Unknown metadata | 8 canonical movie premiere dates NULL, 10 runtimes NULL, all 20 media/request statuses unknown; independent discovery date retained |
| Identity | `plexintel-seerr-primary`, bound source key `4547479bd1da2cd5fab4ff1af5e07bb9617e2dd37900447eb261491ec5330139` in run and canonical enrichment provenance |
| Sequence | `last_value=20`, `is_called=true` |
| Configuration | Actual loader: `enabled=false`; existing owner 1000:1000, mode 0600, file hash unchanged; movie default, all languages, cache enabled, TTL 24 h, failure cooldown 1 h |
| Writer ACLs | All 11 required table SELECT/INSERT/UPDATE and sequence USAGE/SELECT checks pass; ownership/ACLs unchanged |
| Existing services/data | Backend active, PID 1633, same start/restart count; all 40 application table counts, unrelated schema/roles/ACLs/default grants and cron/timer definitions match B2 |
| Quiet window | No running pipeline/model/discovery process observed; no discovery timer or writer/advisory-lock conflict |

All canonical fields, observations and run records match the saved B2 audit, including original timestamps and fingerprints. No intervening discovery mutation was observed. B1 (17 files), targeted B1 (16 files) and B2 (16 files) manifests all verify without mismatch. Of 1,196 paths in B2's pre-execution protected-file manifest, 1,195 still match; the sole differing path is the rollout document already declared changed in B2's final report, which this B3 task did not edit. Existing B1 source drift remains documented: B2 had 19 B1 identities plus movie 1811154; it is not silently added to the original capture. No new upstream drift can be assessed without HTTP, which was forbidden here.

`jmnovak` is still a PostgreSQL **superuser**, an explicitly accepted temporary security exception. This is not least privilege. Role separation remains deferred; no privilege or credential change is proposed.

The validated logical recovery archive remains checksum-valid, with the prior isolated restore PASS and 40 matching tables. Snapshot: October 28, **18:18:46 CDT**, before B2. Required vector/vchord binaries remain present. This task did not repeat a restore or establish PITR, image consistency or full application recovery. A full restore of that archive loses later changes, including B2; operator must reassess recovery-point age before a future write and approve a newer consistent backup separately if required.

Evidence directory: `artifacts/seerr-exploration/2026-10-28-gate-b3-plan/`. `baseline.json` holds the sanitized live snapshot, `prior-evidence-verification.json` the manifest checks, and `after.json` the final read-only snapshot. Original evidence was preserved. Supporting reports: [B2 validation](seerr-discovery-gate-b2-validation.md), [B1 reconciliation](seerr-discovery-gate-b1-targeted-verification.md), [rollout](seerr-discovery-production-rollout.md), [unified semantics](seerr-unified-discovery.md).

## 2. Exact proposed execution sequence

1. Obtain explicit approval for **one Scenario A invocation** with the exact command/bounds in section 4. Recheck section 6 immediately before it; any drift pauses for assessment rather than adjusting the command silently.
2. Capture a fresh read-only pre-state, hashes and baseline identity sets. Create an exclusive local attempt marker in a new owner-only evidence directory. Execute the approved command once in the foreground; preserve stdout JSON, stderr, exit code and run ID. No shell retry loop.
3. Run section 7 read-only verification, reconcile sets/accounting, verify persistent disablement and isolation, produce A PASS/FAIL, and **stop**. Empty results do not validate TV persistence and do not authorize a different date.
4. After reviewing A, seek separate approval for one B-movie repeat. If TV repeat validation is desired, approve B-TV independently after A. Neither approval is implied by the other.
5. Only after the applicable repeats pass, consider independent C-page or C-refresh approval. Keep failure injection local. Review and stop after each invocation; this document does not authorize a batch or automatic progression.

No broad collection or scheduled operation is proposed. Do not use a preliminary dry-run, status request or ad hoc detail request; those would consume additional live HTTP outside these commands.

## 3. Separate scenario authorization boundaries

| Scenario | Proposed scope and historical expectation | Independent authorization and verdict boundary |
| --- | --- | --- |
| A: TV insertion, recommended first | TV only, Oct 31, all languages, ascending original premiere, page 1. B1 contains 8 identities: 7 eligible, 1 provisional; historically 9 calls including details | Exactly one invocation, 25 attempts maximum. Validate TV storage/uncertainty without modifying the 20 movies. Unknown population may yield partial/empty results; no automatic scope expansion |
| B-movie: rediscovery | Repeat B2 Oct 28 movie scope/page 1. If stable and cache-fresh, 20 existing titles, 20 **new** observations, 1 HTTP call | One separate invocation, 25 attempts. No forced refresh. New upstream identities are reconciled, not automatically called duplicates |
| B-TV: optional separate repeat | Repeat A's scope after A; historical expectation 8 cached TV titles, 8 new observations, 1 HTTP call | Own approval and post-check, 25 attempts; not bundled with B-movie or A |
| C-page: incremental prefix | Oct 28 movies, first **two** pages. Synthetic composition of B2 page 1 and 20 additional B1 captures exercises 40 identities | Own approval, 45 attempts. CLI starts again at page 1; no page-2 resume flag. Live second-page membership is unknown |
| C-refresh: changed-detail path | Oct 28 movies, page 1, explicit refresh | Own approval, 25 attempts; bypasses PlexIntel TTL/cooldown. A genuine upstream change is not guaranteed; no production metadata editing to create one |
| C-failure: budgets/interruption/failed GET | Existing isolated tests cover request exhaustion, failed enrichment, rollback and abandoned-running recovery | **No production command proposed.** Deliberate failure injection would require a new explicit authorization and reviewed procedure |

**Historical A identities:** TV 330628 My Sweet Home; 337952 5 mins to vomit; 338309 Boxing Stars; 338525 Pulso Fílmico; 339379 Griff Across the Alps; 339701 ARMS AND COMPANY; 339978 Cap sur l’Élysée; 340206 Theatertijd. The conflict is Pulso Fílmico: summary/detail original Oct 31 versus Season 1 Oct 28; retain provisional `season_premiere_conflict`. Dates and provenance are in `captured-tv-scope.json`.

The B1 TV histogram is Oct 26:24, Oct 27:26, Oct 28:14, Oct 29:17, Oct 30:27, Oct 31:8, Nov 1:9. Oct 31 is the smallest historically populated one-page scope containing a provisional case. This is a subset of a captured week, **not** a captured live one-day endpoint response or a guaranteed current count. Local page expansion similarly composes captures to test mechanics; it does not establish live page ordering.

## 4. Exact proposed commands and limits — DO NOT EXECUTE NOW

Use the existing host working directory `/home/jmnovak/projects/plexintel` and direct `plexenv/bin/python -B`. Existing endpoint/key are read privately. Inline enablement lasts only for the process; the file remains false. Each block is a **separate authorization**, never a sequential shell script.

**A only — recommended first:**

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=25 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type tv --start 2026-10-31 --end 2026-10-31 --language all --sort-by first_air_date.asc --max-pages 1 --json
```

**B-movie only — after separate approval:**

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=25 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type movie --start 2026-10-28 --end 2026-10-28 --language all --sort-by primary_release_date.asc --max-pages 1 --json
```

**B-TV only:** the exact A command, once, after a separate explicit repeat approval; record a new attempt marker/run ID. It is not an automatic second invocation of A.

**C-page only — after separate approval:**

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=45 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type movie --start 2026-10-28 --end 2026-10-28 --language all --sort-by primary_release_date.asc --max-pages 2 --json
```

**C-refresh only — after separate approval:**

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=25 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type movie --start 2026-10-28 --end 2026-10-28 --language all --sort-by primary_release_date.asc --max-pages 1 --refresh --json
```

Ordinary 20-row pages imply A/B/C-refresh at most 21 actual calls and C-page at most 42 if every detail needs fetching; the hard guards remain 25/45 even if page sizes change. C-page with 20 fresh old and 20 new titles uses 22 calls. Budgets count **all attempts**, not successful calls alone. Zero retries also forbids automatic Retry-After repetition. No detail call for cached records. These are request bounds, not strict wall-clock deadlines: a requests timeout is not an end-to-end process timer. No automatic kill/restart is proposed.

## 5. Expected mutations and invariants

**Code findings** (`api/services/seerr_discovery.py`, `api/db/seerr_discovery.py`, `api/services/seerr_client.py`):

- Only the three discovery tables and observation identity sequence are writable. No schema/grant changes. A creates one run, typed TV canonical rows, per-scope observations and enrichment bookkeeping; existing movies remain byte-equivalent. No season/episode entities are created.
- Canonical key is `(media_type,tmdb_id)`; movie/TV numeric collisions remain separate. First-discovery run/time stay immutable. Source guards reject changed or ambiguous endpoint/ID before recovery, run writes or HTTP. No silent inventory adoption.
- An observation is unique on `(run_id,media_type,tmdb_id,scope_key)`. A new invocation deliberately creates a new history row for each retained identity/scope, including cached identities. Membership is represented by discovery observations, not a separate current-membership table; nonappearance in another result does not delete a title or prove withdrawal.
- For pre-state canonical set S and returned retained keys R, post-state is S∪R; new keys R−S; existing R∩S. New discovery observations equal distinct run/type/ID/scope memberships. Under one scope this is |R|. Classifications may retain detail-excluded candidates for audit; summary-confirmed exclusions are instead recorded in pagination diagnostics.
- For a stable fresh repeat, new/updated canonical counts are zero; last-observed advances, first provenance persists. Cached detail, fingerprint, metadata-change timestamp, enrichment/attempt time and original detail-fetch time remain unchanged. Current summaries are stored as discovery evidence; they do not silently become fresh detail metadata.
- On an actual refresh, last-enriched/attempt and detail-observed time advance. Identical projected metadata preserves fingerprint and metadata-updated time; changed projection updates fingerprint/metadata-updated time and observation `changed_fields`. Refresh does not bypass Seerr/TMDB's own caches.
- Movie eligible/provisional/excluded counters are not applicable and remain zero. Unknown movie premiere/runtime remains nullable; valid discovery date does not repair a missing detail date or establish digital availability.
- TV **eligible** requires reliable in-window original premiere and consistent dated Season 1 evidence. **Provisional** retains incomplete, malformed or contradictory evidence with explicit reason; it is not eligible. **Excluded/ineligible** requires affirmative special/returning/out-of-window evidence; detail exclusions remain auditable. A successful detail request and even a successful run do not imply eligibility.
- Missing/null/failed metadata and media/request status stay **unknown**, never available, absent, unrequested or ineligible by default. Movie release collections preserve unknown versus known-empty semantics. TV movie-style runtime/release events remain not applicable; episode runtime and season-date provenance live in TV metadata.
- Old B2 terminal partial run and its 20 observations are immutable during normal A/B/C. Only abandoned `running` runs can be reconciled after lock/schema/source validation. A new run is not a continuation sharing B2's run ID.

Growth is deliberate: stable A then B-movie then B-TV historically adds 8 canonical TV titles, 3 run rows and 36 observations (totals 28 titles/4 runs/56 observations). C-page would add 40 observations and up to 40 canonical identities (historically 20 new); it does not force a target count. Detail snapshots make history larger than canonical counts; this bounded package does not establish indefinite retention or authorize scheduling.

## 6. Pre-execution safety checks — refresh before each approval is used

1. Reverify prior gate manifests, reviewed migration/runtime/helper hashes and exact installed V2 catalog with the strict catalog guard. Stop for drift, new triggers/RLS/constraints or unresolved prior run. No migrations or automatic schema bootstrap.
2. Verify actual server/database/session user and backend connection match the section 1 target. Recheck required ACLs and the accepted superuser exception. Do not create roles or alter credentials.
3. Load owner-only private configuration using the real loader without constructing a Seerr client. Require `config.enabled is False`; approved ID/key binding exactly match every run and known canonical provenance. Confirm no inherited environment overrides change scope, cache, TTL or source. Do not print URL/key.
4. Capture current canonical/observation/run records, exact sets, timestamps and fingerprints; compare to the last accepted stage. For A require the B2 20/20/1 baseline and zero TV. Later cases require their separately accepted baseline, not the original empty inventory gate or the original B2 row counts.
5. Check no writer/advisory lock, active discovery or model/pipeline work, no discovery scheduling and no enabled DDL event trigger. Inspect backend PID/start/restart count and schedule definitions without restarting anything. Immediately recheck quietness before execution; the production advisory lock is the final concurrency protection, not a promise that a sampled quiet state persists.
6. Verify recovery archive hash, prior restore evidence and dependencies. Document age, pre-B2 coverage and operator acceptance of recovery point; stop if required recovery coverage is no longer acceptable. Do not perform an unapproved backup/restore or assume the old archive covers new runs.
7. Resolve exact scope through `build_scopes` locally, confirm one media type/one scope, explicit page/attempt/timeout/retry bounds and no `--enrich-due` or forced refresh unless specifically approved. Confirm enough local evidence storage and capture the exact command before the single attempt.

The saved `readonly-baseline.py after` is a read-only B2-comparison observer with no HTTP; its B2 comparisons apply **only before A**. After a legitimate A, a B2 comparison must differ for discovery data; use the freshly accepted stage snapshot and section 7 instead. The observer's `status=PASS` means inspection completed; separately require every applicable comparison to be true. Do not reuse B2's empty-inventory writer precondition or invoke any migration helper's apply mode.

## 7. Post-execution read-only verification and SQL

Read-only CLI reporting, with no inline enablement and no HTTP:

```bash
plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --summary --json
```

Use the existing Python connector/`DATABASE_URL` privately, connect with `default_transaction_read_only=on`, 15-second statement timeout and 2-second lock timeout, and use a repeatable-read read-only transaction. The SQL below is also suitable for an already correctly authenticated psql session. Set psql `run_id` to the single captured UUID, not the B2 UUID. Never echo a credential-bearing DSN.

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SHOW transaction_read_only;
SELECT host(inet_server_addr()), inet_server_port(), current_database(),
       current_user, session_user, pg_is_in_recovery();

SELECT media_type, count(*) FROM public.seerr_discovered_titles GROUP BY media_type;
SELECT * FROM public.seerr_discovery_runs ORDER BY started_at,run_id;
SELECT media_type,tmdb_id,first_discovery_run_id,first_discovered_at,last_observed_at,
       last_enriched_at,last_enrichment_attempt_at,metadata_updated_at,
       metadata_source_key,metadata_fingerprint,premiere_date,discovery_premiere_date,
       runtime,media_status,media_status_4k,media_state,field_states,tv_metadata
FROM public.seerr_discovered_titles ORDER BY media_type,tmdb_id;

SELECT run_id,media_type,scope_key,observation_kind,enrichment_outcome,
       eligibility->>'state' AS eligibility,count(*) AS memberships,
       count(DISTINCT tmdb_id) AS identities,
       count(*) FILTER (WHERE is_new) AS new_identities
FROM public.seerr_discovery_observations
GROUP BY run_id,media_type,scope_key,observation_kind,enrichment_outcome,eligibility->>'state'
ORDER BY run_id,media_type,scope_key,enrichment_outcome,eligibility;

SELECT * FROM public.seerr_discovery_observations
WHERE run_id=:'run_id'::uuid ORDER BY media_type,tmdb_id,scope_key;
SELECT media_type,tmdb_id,count(*) FROM public.seerr_discovered_titles
GROUP BY media_type,tmdb_id HAVING count(*)<>1;
SELECT run_id,media_type,tmdb_id,scope_key,count(*)
FROM public.seerr_discovery_observations
GROUP BY run_id,media_type,tmdb_id,scope_key HAVING count(*)<>1;
SELECT count(*) AS orphan_observations FROM public.seerr_discovery_observations o
LEFT JOIN public.seerr_discovered_titles t USING(media_type,tmdb_id)
LEFT JOIN public.seerr_discovery_runs r USING(run_id)
WHERE t.tmdb_id IS NULL OR r.run_id IS NULL;
SELECT run_id,status,completed_at FROM public.seerr_discovery_runs WHERE status='running';
SELECT DISTINCT source_key,parameters->>'source_id',parameters->>'source_key'
FROM public.seerr_discovery_runs;
SELECT DISTINCT metadata_source_key FROM public.seerr_discovered_titles;

SELECT conrelid::regclass,conname,contype,convalidated,pg_get_constraintdef(oid)
FROM pg_constraint WHERE conrelid IN ('public.seerr_discovery_runs'::regclass,
 'public.seerr_discovered_titles'::regclass,'public.seerr_discovery_observations'::regclass)
ORDER BY conrelid,conname;
SELECT i.indrelid::regclass,i.indexrelid::regclass,i.indisvalid,i.indisready,
       i.indisunique,pg_get_indexdef(i.indexrelid)
FROM pg_index i WHERE i.indrelid IN ('public.seerr_discovery_runs'::regclass,
 'public.seerr_discovered_titles'::regclass,'public.seerr_discovery_observations'::regclass)
ORDER BY i.indrelid,i.indexrelid;
SELECT last_value,is_called FROM public.seerr_discovery_observations_observation_id_seq;
ROLLBACK;
```

Additionally rerun the exact reviewed catalog comparison, runtime compatibility guard and 11 ACL checks; textual listings alone are insufficient. Compare protected application counts/schema/roles/ACLs/schedules/backend/configuration to the fresh pre-state. A real unrelated scheduled change is an anomaly to investigate, not evidence that discovery caused it or a reason to overwrite it.

Offline reconcile captured CLI JSON, stderr and durable run row: same ID, parameters, source binding, counters, pagination, terminal status/completed time, errors and warnings. Match observations to R, detail fetch/cache age and canonical fingerprints; aggregate distinct identities for run counters, not raw repeated history across runs. Require one new run and the exact per-scope observation delta; compare preexisting observations/B2 run unchanged. Verify zero orphans/duplicates, no hidden media type, and S∪R set equality. Identity sequence need not be gapless after a failed transaction; it must remain safely owned and ahead of committed IDs.

For A specifically, all preexisting movie records and B2 history must remain identical. Audit every TV assessment reason and season provenance, including unresolved dates. For B compare every immutable field, changed field and fetch timestamp under cache/refresh semantics, allowing documented upstream population changes. An empty A, unexpected HTTP error, missing detail or missing run accounting blocks acceptance of that scenario even if safety limits held.

Save sanitized snapshots, complete typed identity audit, exit status, run ID, request accounting, uncertainty diagnostics, comparison results and SHA-256 manifest in a new private stage directory. No additional live call to explain a discrepancy without fresh authorization.

## 8. Recovery and stop conditions

- Stop/NO-GO before execution for target, source, ACL, schema, reviewed-code, recovery, persistent-enable-state or accepted-baseline mismatch; occupied lock; active conflicting job; or missing authorization. Do not repair by rebinding inventory, granting privileges or applying SQL.
- During the one command, hard client bounds apply. Retain partial progress/history rather than rerun. After any transport/auth/rate-limit/malformed-page/detail error, record the actual outcome and stop this gate for review. No manual retry, page/date expansion or silent fallback.
- A transport failure preserves prior detail metadata, marks a real failed attempt and observes cooldown. Budget exhaustion before GET instead records deferred work and does not fabricate an attempt time. Both are distinguishable from absent metadata or ineligibility.
- Page transactions are atomic, not the entire invocation: earlier committed pages and completed enrichments can remain after later failure. Canonical records absent from a subsequent page are not deleted.
- Terminal B2/other partial runs remain unchanged. A later **separately authorized** invocation gets a new run/observations; stale `running` history is reconciled under the writer lock only after schema/source guards. Do not manually mark runs or kill a production writer to test this.
- On integrity failure, leave discovery disabled, preserve evidence and inspect read-only. No automatic rollback SQL, full-database restore or migration rollback. The old V1 `rollback.sql` is destructive and not a V2 data-recovery procedure. A restore or corrective production DML requires separate reviewed authorization.

## 9. Partial outcomes and exit codes

| Outcome | Interpretation/action |
| --- | --- |
| Exit 0, `success` | Discovery pages and enrichment complete for scope. Does not establish all TV eligibility; provisional evidence can coexist with success and `eligibility_complete=false` |
| Exit 2, `partial`, only expected `page_limit_exceeded` | Acceptable bounded safety result if all retrieved identities, enrichment outcomes, source and isolation checks reconcile. Coverage remains incomplete; no extra page authorized |
| Exit 2, other partial/failed | Preserve durable work; distinguish safely contained API/budget failure from integrity failure. Scenario acceptance withheld pending review; no automatic follow-up |
| Exit 1 | Configuration/database/internal failure; inspect persisted state, since exit alone does not prove no committed rows |
| Exit 75 | Writer lock already held; no retry; stop and investigate |

A historically fits one page, so normally expects success/exit 0, 7 eligible/1 provisional and eligibility incomplete. If the live population exceeds a page, an accurately reported cap partial is acceptable for the bounded persistence check. For B-movie and C-page the historical six-page population implies expected cap partial/exit 2. Provisional classifications alone do not mean failed enrichment; unknown media/request status never determines run success or acquisition readiness.

## 10. Isolated validation, risks and unresolved assumptions

**Isolated tests:** 276 passed, no skipped tests: existing 271 plus five captured B3 regressions. All used a dedicated `/tmp/plexintel-seerr-fixture.*` PostgreSQL 18 cluster, TCP disabled, database `plexintel_seerr_fixture`; fixture guards verify database name/socket/data directory before DDL. Real `requests.Session.request` was blocked during the suite and replays. Only the disposable database received writes/migrations. It is not the production host/backend.

New tests in `tests/test_seerr_gate_b3.py` seed copied B2 rows (rebound only in memory to a fictional fixture source, never production credentials), then verify:

1. B2 movie repeat: 20 cached, zero new/updated canonical, 20 new observations, original partial history intact; eight unknown dates/ten runtimes and unknown statuses retained.
2. Identical forced detail refresh: fetch age advances, fingerprints/change times remain stable.
3. One synthetic detail delta: exactly one canonical update and explicit changed-fields observation.
4. Captured Oct 31 TV insert then cached repeat: eight TV identities, seven eligible/one provisional, 16 added observations across two runs, all movies untouched.
5. Composed page expansion: 20 cached plus 20 new captured movies, two page reads/22 adapter calls, 40 new observations; B2 terminal partial unchanged.

Existing tests independently cover movie/TV numeric collisions, source ID/endpoint mismatches before writes/HTTP, schema catalog incompatibility, observation uniqueness, release unknown/empty semantics, missing summary dates, failed/budget-deferred enrichments, interrupted mixed runs, page-transaction rollback and safe subsequent runs. These are **fixture results**, not live B3 success claims.

Both existing offline replays passed: captured movie replay and combined synthetic movie/TV replay, zero actual HTTP. Logs: `pytest.log`, `pytest.xml`, `isolated-results.json`, `captured-movie-replay.json`, `synthetic-unified-replay.json`. Initial local fixture setup used SQL_ASCII and rejected an international captured title before synchronization; the disposable database was recreated UTF-8 and the five capture tests and complete suite then passed. `captured-tests.log` preserves that setup error; no production effect.

Reproduce with an independently created, guarded TCP-disabled UTF-8 fixture (see existing persistence/test fixture instructions), frozen B1/B2 artifact directories and `SEERR_DISCOVERY_TEST_DSN` pointing only to that fixture:

```bash
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' plexenv/bin/python -B -m pytest -q tests/test_seerr_discovery.py tests/test_seerr_unified_discovery.py tests/test_seerr_readiness_remediation.py tests/test_seerr_exploration.py tests/test_seerr_phase2.py tests/test_schema_migrations.py tests/test_seerr_gate_b3.py
plexenv/bin/python -B -m tests.replay_seerr_discovery
plexenv/bin/python -B -m tests.replay_seerr_unified_discovery
```

The saved `run-isolated-validation.py` records the HTTP-blocked wrapper actually used; it expects the task's fixture descriptor and does not create a production connection. Disposable cluster cleanup is recorded separately. Do not point any test/replay at `DATABASE_URL` or an application database.

| Risk / live assumption | Treatment |
| --- | --- |
| Current Seerr population/order differs from B1/B2 | No HTTP during planning; compare live sets under the authorized budget later. Missing/new IDs are source variation, not automatic corruption |
| Actual one-day endpoint/page size differs from subset replay | Captured A and composed C are test scenarios; hard page/attempt caps remain authoritative |
| TV real persistence untested | Execute A first only after approval; retain conflict diagnosis without declaring eligible |
| TTL expiry/source cache masks expected change | Recompute cache expectations at execution; C-refresh distinct authorization; true changed-source behavior remains partly a live assumption |
| Observation history grows per repeat | Expected bounded growth above; no indefinite schedules/retention policy implied |
| Backup age and pre-B2 coverage | Prior recoverability verified, newer production state not covered by archive; operator reassesses acceptable RPO before write |
| Superuser writer | Accepted temporary exception, deferred least-privilege hardening; unchanged ACLs |
| Nonatomic upstream pagination / changing page boundaries | Explicit warnings; duplicate/missing/page-total diagnostics retained, no completeness claim for capped prefix |
| Production quietness can change | Fresh checks plus writer advisory lock; stop for conflict, do not modify services/schedules |
| No guaranteed production numeric collision, metadata delta or failure | Isolated tests establish mechanics; do not inject production records/failures to manufacture evidence |

## 11. Independent review

The separately authorized independent reviewer inspected source semantics and B1 captures offline, with no DB/network access or edits. It recommended **A first: Oct 31 TV, one page/25 attempts**, and confirmed new-run observations on repeat, cache timestamp preservation, immutable terminal B2 history, page-1 restart on page-cap expansion, and the need to keep deliberate exhaustion/interruption local. It then reviewed the completed plan, verification SQL, commands, saved production baseline and 276-test evidence: **no correctness or authorization blocker found**. It independently confirmed the B2 record comparison and required retaining the private-capture prerequisite for reproducing tests. Its wording correction to the disabled-state check is applied. Results are retained in `independent-review.md` in the evidence directory.

Final read-only check at **22:54:57 CDT** again matches the B2 baseline, with all **17 boundary checks PASS**. The disposable cluster was stopped and removed. Neither successful isolated tests nor this review establishes live TV persistence or authorizes B3.

## 12. Recommendation and stop point

**GO for requesting authorization of Scenario A only, conditional on fresh checks in section 6. NO-GO for executing B3 under this planning request.** TV is the remaining unvalidated production persistence path; the historical Oct 31 scope exercises it and a known date-conflict diagnostic with a small single-page population.

Additional approval must explicitly authorize **exactly one** foreground TV-only execution of the section 4 A command: Oct 31, all languages, ascending original premiere, max one page, 25 total attempts, zero retries, 10-second timeout, one-second spacing and five-second Retry-After ceiling; discovery-only writes plus read-only pre/post audit; process-local enablement; no reruns, expanded scope or progression. A PASS does not authorize B or C.

This task changes only the plan, isolated test code and local evidence. Production schema/data/configuration/services/schedules, acquisition, recommendations, scoring and training remain unchanged. No Seerr HTTP, production writer, migration, sync, restart or deployment was executed. Stop here.
