# Phase 3 initial discovery population — stopped at preflight

**NO-GO for execution and routine activation. Initial population is incomplete.**

On **October 29, 2026, 07:16:26 CDT**, the required quiet-window check detected an active **`score_model.py` process, PID `1300206`**. The observer exited 1 with `active_model_or_discovery_process`. Execution stopped before either synchronization. No waiting, automatic retry, Seerr HTTP request, database writer, backup, or remediation followed.

The operator subsequently instructed **“dont create a backup.”** No backup had been attempted; none was created. The unexecuted backup template was removed from this task's evidence directory. Existing backups were not changed. This instruction cancels backup creation; it does not establish a fresh recovery point or make the incomplete preflight pass.

## Preflight evidence

The repository, direct-Python CLI, persistence/unified design, rollout runbook, original C authorization and final forced-refresh execution evidence were reviewed. Historical statements about an empty/V1 inventory or an uninstalled migration are superseded by the actual installed V2 schema and accepted C evidence. No previous experiment was repeated.

| Prerequisite | Observed result |
| --- | --- |
| Effective database target | Verified backend connection matches `192.168.1.9:5432 / plexintel / jmnovak`; primary PostgreSQL 18.6 |
| Installed migrations | Original committed 001 receipt/corrected verification and Gate A 002 commit/verification checked; reviewed input hashes passed |
| Runtime/catalog compatibility | Strict V2 PASS; catalog SHA-256 `e207edf33855a481b740eb9d1193f124000bdc5edc2ffce13dbad9c6fb80af66` |
| Accepted inventory | **47 canonical titles: 39 movies, 8 TV; 87 observations; four terminal runs** |
| Complete historical records | All canonical rows, observations and runs exactly match accepted C `after.json`, including metadata, first provenance and timestamps |
| Identity/history integrity | No duplicate typed titles or observation memberships; no orphaned observations/first runs; sequence 87, called |
| Source binding | Approved `plexintel-seerr-primary`; all run bindings and canonical metadata source keys agree with configured endpoint hash |
| Writer permissions | All 11 existing table/sequence privilege checks passed |
| Writer security | `jmnovak` is a superuser: **accepted temporary security exception**, with least-privilege separation deferred; privileges unchanged by this task |
| Persistent discovery configuration | Real loader confirms **false**, unchanged file hash, owner 1000:1000, mode 0600, source identity, 24-hour TTL and cache enabled |
| Discovery concurrency | No discovery advisory lock/active database writer or unresolved `running` discovery run observed |
| Application health | HTTP 200, `{ok:true, service:library-catalog}`; backend PID 1633, start/restart state unchanged |
| Quiet execution window | **FAILED:** scoring process present, although the pipeline-run table had no `running` row |
| Application baseline | Full observed counts/catalog captured; **differs from C** and cannot be claimed unchanged |
| Fresh recovery point | **Not attempted**, then explicitly prohibited by operator; no fresh recovery validation |
| Current capacity, schedules and final readiness | Not reached before stop; no PASS inferred |

The current application has **41 ordinary public application tables**, compared with 40 at C. Thirteen captured table-count entries differ, including newly observed `recommendations_new`. These differences coexist with the active scoring process and represent intervening application activity; their cause and final state were not independently reconciled. Discovery records themselves match C exactly. This task neither triggered nor modified that application/model activity.

## Workload and supported command preparation

The accepted B1 seven-day evidence contains **811 movies / 41 pages** and **125 TV / seven pages**. These are historical estimates, not current counts or population targets. With the 39 movies/eight TV still fresh and rediscovered, estimated requests are **813 movie + 124 TV = 937**; with all details requiring retrieval, approximately **984**. Live source growth, overlap and cache eligibility can change those numbers.

The actual loader currently supplies **10,000 attempts per invocation**, **500 pages per scope**, native **14-day window splitting**, and ordinary **24-hour metadata TTL**. The seven-day selection fits one scope per media type. The historical workload fits these limits; no safety limit increase was proposed. Existing transport protections would be narrowed to zero retries, timeout 10 seconds, spacing one second and Retry-After maximum five seconds. No forced refresh, enrichment-only job or content filter is proposed.

**No synchronization command was executed.** The following are prepared commands only, subject to a newly successful preflight and an explicit resolution of recovery readiness. Do not run them as a continuation of this stopped attempt.

```bash
# Repository root; proposal only. Movie first; audit completion before TV.
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=10000 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type movie --start 2026-10-26 --end 2026-11-01 --language all --sort-by primary_release_date.asc --json

# Only after the movie result and independent read-only audit pass.
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=10000 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type tv --start 2026-10-26 --end 2026-11-01 --language all --sort-by first_air_date.asc --json
```

Omitting the experimental page cap retains the configured safety ceiling of 500, rather than requesting unlimited pagination. Reaching that ceiling is incomplete coverage. Request budgets apply to each invocation across every native window, page, detail and retry. Splitting into native windows does not reset that budget within an invocation.

Actual production-reading command executed once:

```bash
plexenv/bin/python -B artifacts/seerr-exploration/2026-10-29-initial-population/observe.py before
```

It used forced read-only repeatable-read PostgreSQL transactions with statement/lock timeouts, the existing catalog guards and host service checks. The only HTTP call was the local application health GET, not Seerr. Subsequent reconciliation read saved evidence and the private configuration locally; it made no additional production database calls.

## Movie, TV and inventory results

| Metric | Accepted baseline / observed preflight | Added by this task |
| --- | ---: | ---: |
| Canonical movies | 39 | 0 |
| Canonical TV | 8 | 0 |
| Canonical total | 47 | 0 |
| Historical observations | 87 | 0 |
| Discovery runs | 4 | 0 |
| Existing titles independently matched to C | 47 | — |
| New/updated metadata records | No synchronization | 0 |
| Cached/fetched/failed/deferred enrichments | No synchronization | 0 each |
| Seerr requests/pages | No synchronization | 0 / 0 |

There are no new run IDs, terminal outcomes or post-execution results. This is a **preflight NO-GO**, not a failed or empty discovery run. Both requested seven-day movie and TV scopes remain **uncollected by this assignment**. Earlier bounded prefixes and B1's read-only preview do not constitute complete canonical coverage.

The existing eight TV observations retain **seven eligible and one provisional** classifications. The provisional B3-A title, Pulso Fílmico (`tv`, `338525`), retains its conflicting original/season-1 date evidence. These are existing observations, not new seven-day TV results.

## Integrity and production isolation

Saved-snapshot reconciliation verifies exact preservation relative to accepted C of all 47 canonical records, 87 observations and four runs. It consequently verifies their typed identities, immutable first-discovery timestamps, metadata, provisional diagnostics, unknown states and source provenance. No new membership, metadata overwrite or enrichment occurred.

Missing media/request status remains unknown, not absence, availability, ineligibility or zero requests. Missing runtime/date and failed enrichment must retain their uncertainty. Movie primary dates do not imply digital availability. TV premiere eligibility is the existing conservative original-series assessment; provisional candidates remain auditable rather than being silently discarded. No new eligibility/content filter was introduced.

This assignment made **zero production database writes**, Seerr/acquisition requests, migrations, model/scoring invocations, service restarts, persistent configuration changes or schedule changes. Existing active scoring was observed, not started or stopped by this task. An unchanged application-data claim would be inappropriate given the captured intervening changes. No post-sync isolation audit is claimed because execution never occurred. New files are reporting/private evidence only; existing implementation and earlier evidence remain untouched.

## Separate routine-operations proposal — inactive

Initial-population closure and routine activation are **not recommended yet**. After a separately accepted completed population and recovery/quiet-window resolution, prepare manual operations before considering any schedule:

- **Daily release coverage:** all-language movies and TV, UTC anchor minus 14 days through plus 90 days, inclusive: 105 dates. Use the existing 14-day splitting and ordinary cache rules. Record every window, page and terminal status. A release-window search is not a feed of genuinely new TMDB catalog entries; newly cataloged titles with dates outside the horizon can be missed.
- **First broader fill:** obtain separate authorization and estimate each media workload. Extrapolating the historical seven-day density gives roughly 12,165 movies and 1,875 TV matches over 105 days, before pagination—an uncertain planning estimate that could exceed 10,000 attempts for an uncached movie invocation. Stage explicitly bounded date ranges if needed; do not silently truncate or merely raise budgets. Once populated, cache reuse can reduce detail traffic but does not remove page/observation work.
- **Periodic wider sweeps:** propose monthly historical and farther-forward windows, separated into reviewed, manageable date slices. Measure actual density and cache misses first. No wider sweep, interval or schedule is activated here; sparse/missing dates and upstream query/account semantics remain coverage limitations.
- **Metadata refresh:** ordinary rediscovery uses TTL/cooldown. A separately authorized `--enrich-due` operation can refresh stored titles outside current windows with the existing batch bound. Inspect due counts first; no default `--refresh`. Refresh observations do not establish new-release discovery eligibility.
- **Retry/recovery:** leave partial/failed terminal histories intact. Inspect durable pages, observations, failures and request accounting read-only before authorizing another execution. A later approved run starts at page 1 with a new run ID, cache and cooldown; it is not cursor resumption. An abandoned `running` run requires explicit recovery review; do not directly edit status, automatically restore or launch a repair.
- **Monitoring:** require both discovery and enrichment completion, reconciled raw/unique counts, stable per-page totals, no duplicates/invalid IDs/missing pages, correct scopes/source binding and terminal accounting. Alert on partial/failed/running runs, source drift, deferred/failing details and budget/page limits. Provisional eligibility alone is not retrieval failure. A cap reached with pages left is never success.
- **Storage:** canonical identity deduplicates; per-run/per-scope observations intentionally append, including detail snapshots on cached rediscovery. At the historical density, a 105-day daily sweep could create approximately 14,040 observations/day or 5.12 million/year, before wider/refresh jobs and population drift. This is an order-of-magnitude workload estimate, not a measured PostgreSQL byte forecast. Measure relation/index/TOAST sizes and observations per actual invocation; budget for append growth and backups before routine activation. No retention deletion or partition/schema change is authorized.

Future post-run acceptance must independently reconcile CLI/durable runs, complete pagination, candidate identity unions, new/known counts, enrichment/cache outcomes and provisional TV reasons; preserve old history/first provenance; recheck schema/source/ACLs/unknown semantics; and compare a fresh application baseline. Any movie integrity or coverage failure stops TV. No automatic rerun is authorized to manufacture completeness.

## Evidence and recommendation

Private ignored evidence:

`artifacts/seerr-exploration/2026-10-29-initial-population/`

`before.json` preserves the full read-only discovery/application observation and stop reason; `assessment.json` records exact C reconciliation, current disabled configuration, source and ACL checks, application-count differences and incomplete gates. `workload-plan.json`, `stop-record.json`, protected-input references, sanitization results and SHA-256 manifest complete the audit. The observer script was not rerun after its safety stop. No backup attempt marker or synchronization launcher/output exists.

**Initial population: NOT COMPLETE. Execution: NO-GO. Routine synchronization: NO-GO pending successful initial population and operational approval.** A future attempt needs a verified quiet window, reconciliation of intervening application state, a complete fresh preflight and an explicitly agreed recovery-readiness approach consistent with the no-backup instruction. This task will not create a backup, waive recovery safeguards, wait for the pipeline, retry execution, schedule discovery or advance to Phase 4.
