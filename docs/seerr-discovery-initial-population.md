# Phase 3 — initial seven-day discovery population

**Initial population: PASS — recommend closure. Routine operations: CONDITIONAL GO for separately approved activation.**

Scope: **October 26–November 1, 2026 inclusive**, all-language movies followed by TV, using the direct-host Python CLI. Persistent discovery remains **disabled**. No schedule or Phase 4 work was activated.

## Preflight and accepted recovery exception

Fresh preflight at **October 29, 2026, 07:52:01 CDT** verified production `192.168.1.9:5432 / plexintel / jmnovak`, PostgreSQL 18.6 primary, unchanged effective backend connection, reviewed 001/002 install provenance and strict V2 schema. All **11 writer ACL checks** passed. All **47 canonical rows, 87 observations and four historical runs** matched accepted B3-C exactly, including source/first provenance and metadata. No writer, abandoned running run, model process or conflicting pipeline was present. The application health GET returned 200; backend PID/start/restart state and schedules matched prior evidence.

The earlier 07:16 attempt stopped before execution while scoring was active. The subsequent pipeline completed successfully at **07:43:58 CDT**. Its completed application state became the fresh baseline; normal intervening application row-count changes were not mistaken for discovery mutations. The temporary `recommendations_new` table was gone and the application catalog again matched C. Earlier stopped-attempt evidence and the previous report are preserved.

Database size was **1,093,736,127 bytes**; local host available space **847,047,569,408 bytes**, passing the existing capacity threshold. This measures the host filesystem; it is not a separate remote database-volume free-space claim. Real configuration loader, owner 1000:1000/mode 0600/hash, approved source `plexintel-seerr-primary`, ordinary 24-hour cache TTL and disabled persistent state passed.

**No new backup was created**, following the operator prohibition. After the recovery gap was explained, the operator explicitly accepted the existing recovery point for this population run. This is an accepted exception to the original fresh-backup prerequisite, not a claim that a fresh point was established.

Existing archive: `/home/jmnovak/.local/state/plexintel/preflight-backups/plexintel-20261029T054550Z-e6b300.dump`. Snapshot **October 29, 00:45:50 CDT**, SHA-256 `d9c6fd1cd0e5e081f0d2484d35092cd36576107bb8dd7bb25ed7dc121f38f67c`. Archive hash and matching extension binary were rechecked; earlier isolated 43-table restore validation remained valid evidence. The archive contains **28 titles / 48 observations / three runs**, predating B3-C and the morning application pipeline. A database-wide restore would lose those later updates. No new restore, PITR chain or production rollback was performed or authorized.

`jmnovak` remains the **accepted temporary PostgreSQL superuser exception**. Least-privilege separation is deferred; no role, credential or privilege was changed.

## Commands and workload

Historical B1 evidence estimated 811 movies/41 pages and 125 TV/seven pages: approximately **937 attempts with the existing cache, 984 if all details required fetching**. These estimates fit existing configured limits of **10,000 attempts per invocation / 500 pages per scope**. Actual counts are source results, not targets. Native 14-day splitting produces one seven-day scope per media here. Transport used zero retries, 10-second timeout, one-second spacing and a five-second Retry-After ceiling. Ordinary cache/TTL rules were retained; no forced refresh or content filter was applied.

Executed commands from `/home/jmnovak/projects/plexintel` — **audit only, do not rerun**:

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=10000 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type movie --start 2026-10-26 --end 2026-11-01 --language all --sort-by primary_release_date.asc --json
```

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=10000 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type tv --start 2026-10-26 --end 2026-11-01 --language all --sort-by first_air_date.asc --json
```

The launcher created an exclusive per-media attempt marker. TV required complete movie pagination/enrichment plus passing SQL and offline integrity audits; safeguards were checked again before TV. No synchronization was automatically repeated.

## Results

| Metric | Movie | TV |
| --- | ---: | ---: |
| Run ID | `c648b0a6-40d3-4dde-b16e-861c4ffa664f` | `2011fe8a-9f0d-4c8b-8d7c-43c8cf4b48d4` |
| Terminal status / exit | success / 0 | success / 0 |
| Candidates observed | 832 | 130 |
| New canonical titles | 793 | 122 |
| Previously known titles observed | 39 | 8 |
| Existing records with changed fields | 0 | 0 |
| Existing fingerprint changes | 0 | 0 |
| Details fetched successfully | 793 | 122 |
| Cached details reused | 39 | 8 |
| Failed / deferred / pending details | 0 / 0 / 0 | 0 / 0 / 0 |
| HTTP attempts / retries | 835 / 0 | 129 / 0 |
| Pages fetched / expected | 42 / 42 | 7 / 7 |
| Coverage | COMPLETE | COMPLETE |
| Integrity checks | 27/27 | 27/27 |

Movie ran **October 29, 2026, 07:52:03 CDT–October 29, 2026, 08:05:57 CDT**. Actual scope and every page are retained in `movie-execution.json`; per-candidate metadata, provenance, unknown states, changes and enrichment outcomes are retained in JSON/CSV.

TV ran **October 29, 2026, 08:06:40 CDT–October 29, 2026, 08:08:48 CDT**. Actual scope and every page are retained in `tv-execution.json`; per-candidate metadata, provenance, unknown states, changes and enrichment outcomes are retained in JSON/CSV.

## Canonical inventory and historical observations

| Inventory | Before | After |
| --- | ---: | ---: |
| Movies | 39 | 832 |
| TV | 8 | 130 |
| Total titles | 47 | 962 |
| Observations | 87 | 1049 |
| Runs | 4 | 6 |

Each successful rediscovery adds run-specific memberships while preserving canonical typed identity. Audits reconcile the exact identity union, first-discovery time/run, source binding, old terminal runs, every prior observation and untouched/unselected rows. Cached detail values/fetch timestamps remain unchanged; newly fetched metadata is projected and fingerprinted independently. Existing metadata changes are accepted only when supported by returned sanitized source evidence; missing values are not fabricated.

## Pagination, enrichment and uncertainty

- **movie**: source total 832, raw rows 832, unique source results 832, retained titles 832, duplicate rows 0, invalid rows 0; pagination complete=True. Summary exclusions 0; unresolved summary-date diagnostics 0. Pagination errors: `[]`.
- **movie unknowns** among retained run candidates: premiere date 29, runtime 242, standard media status 832, request count 832. API/enrichment errors: `[]`.
- **tv**: source total 130, raw rows 130, unique source results 130, retained titles 130, duplicate rows 0, invalid rows 0; pagination complete=True. Summary exclusions 0; unresolved summary-date diagnostics 0. Pagination errors: `[]`.
- **tv unknowns** among retained run candidates: premiere date 5, runtime not_applicable, standard media status 130, request count 130. API/enrichment errors: `[]`.

A complete result requires the native pagination integrity rules, every reported page, stable totals, zero duplicate/invalid identities, reconciled unique totals and complete enrichment. Fetching only a configured cap would not pass. Source pagination is still not an atomic snapshot; equal-count substitutions and upstream account/region settings can remain undetectable.

Missing status is **unknown**, not absence, availability, ineligibility or zero requests. Missing runtime/date and failed enrichment preserve uncertainty. Primary movie release dates do not establish digital availability. Missing TV summary dates receive detail enrichment; conservative TV eligibility is distinct from retrieval completeness. Provisional records remain in the inventory with diagnostics. Confirmed summary exclusions remain in pagination audit evidence; no engagement/content eligibility filter was activated.

## TV classification

Run-level classifications: **122 eligible, 8 provisional, 0 excluded**. Complete per-title reasons and retained series/season date evidence: `tv-eligibility.json`.

| Provisional TV identity | Title | Reason |
| --- | --- | --- |
| (`tv`, 289517) | Dead-End Job | `season_premiere_conflict` |
| (`tv`, 338525) | Pulso Fílmico | `season_premiere_conflict` |
| (`tv`, 339670) | Fracture américaine | `season_premiere_conflict` |
| (`tv`, 340297) | 谈话到此结束 | `original_premiere_unknown` |
| (`tv`, 340302) | 邻里风波，当善意不再廉价 | `original_premiere_unknown` |
| (`tv`, 340325) | Er Du Jomfru? | `original_premiere_unknown` |
| (`tv`, 340344) | Double Jeu | `original_premiere_unknown` |
| (`tv`, 340356) | Kick!? Off The LA | `original_premiere_unknown` |

## Read-only integrity and production isolation

For each executed run, **24 independent SELECT blocks** executed in a forced read-only transaction, including **16 integrity-anomaly result sets**. Offline reconciliation checked full metadata projections, fingerprints, cache/fetch times, source/scope membership and CLI/durable accounting. Overall recorded integrity is **PASS**. No writer was used for verification.

The final capture compares the fresh application table counts/catalog, roles/ACLs, backend PID/start/restarts/health, schedules, persistent credentials/configuration and protected tracked inputs. This establishes count/catalog isolation, not exhaustive application row-value checksums. No schema/migration/application code, media/user embeddings, model/scoring/training, acquisition/Radarr behavior, credentials, services or schedules were changed. Existing model jobs were not invoked. Inline enablement existed only in each manual child; the owner-only file remained false. No backup was created and no automatic restore/repair/rerun occurred.

## Coverage gaps and separate routine-operation plan

Both specified seven-day scopes are fully collected and enrichment-accounted. Recommend closing **Phase 3 initial population**, with the accepted older-recovery-point and superuser exceptions retained.

- **Daily proposal, inactive:** UTC today minus 14 through plus 90 days inclusive, all-language movie and TV release-window discovery, native 14-day slices and ordinary caching. Explicitly assess budgets and quiet windows before activation. A release-window search is not a comprehensive feed of newly cataloged TMDB titles; missing/older/far-future release dates and upstream source settings can leave gaps.
- **First wider fill, separately authorized:** current seven-day density extrapolated over 105 dates suggests roughly 12,480 movies and 1,950 TV candidates before drift; an uncached movie invocation could exceed 10,000 attempts. Native window splitting does not reset a global invocation budget. Stage reviewed explicit date slices rather than silently truncating or increasing limits. No wider population ran here.
- **Periodic wider sweeps, proposal:** separately reviewed monthly historical/far-future slices, sized from observed density, cache misses and page counts. No backfill or schedule was enabled.
- **Refresh:** ordinary rediscovery follows the existing 24-hour TTL and one-hour failed-attempt cooldown. Separately authorize `--enrich-due` for out-of-window stored titles after inspecting due counts/batch size. No routine forced refresh; refresh-only observations do not establish new-series premiere eligibility.
- **Failures/recovery:** monitor partial/failed/running runs, pagination drift, missing pages, failures/deferred details and budgets. Preserve committed history; investigate read-only and authorize later executions separately. A later run starts at page 1 with a new UUID and ordinary cache/cooldown. An abandoned running run requires explicit recovery review, not direct status edits or an automatic production restore.
- **Observation growth:** rediscovery appends per-run/per-scope observations, including cached detail snapshots. Current seven-day density extrapolated uniformly suggests approximately 14,430 observations/day for a 105-day daily union, or 5.27 million/year before sweeps, refresh jobs and drift. This is a planning estimate, not a guaranteed population or disk forecast. Canonical uniqueness does not bound historical storage. Measure actual table/index/TOAST size, rates and backup capacity before routine activation; no retention/schema change is included.

Final measured discovery relation sizes (table includes TOAST):

| Relation | Table/TOAST bytes | Index bytes | Total bytes |
| --- | ---: | ---: | ---: |
| seerr_discovered_titles | 4,571,136 | 253,952 | 4,825,088 |
| seerr_discovery_observations | 4,038,656 | 376,832 | 4,415,488 |
| seerr_discovery_runs | 65,536 | 32,768 | 98,304 |

These are observed post-run allocated relation sizes, not a measured before/after byte delta. Current observation storage averages approximately 4,209 allocated bytes per row including indexes/TOAST; at the illustrative 5.27-million/year scenario that is about 22.2 GB/year for observations alone. Payload variation, compression, index growth, dead space, sweeps and backups can change this substantially; it is not a capacity guarantee.

## Routine activation sequence — separate approval required

1. Approve staged wider-horizon population with explicit per-run scopes and budgets; do not treat this seven-day completion as 105-day coverage.
2. Agree the ongoing recovery/RPO policy, quiet window, request/runtime ceilings and storage monitoring. The older-recovery-point exception here is limited to this population run; the superuser exception remains documented.
3. Review complete/partial/failure monitoring, enrichment cooldown/recovery procedures and observation growth against actual wider-horizon measurements.
4. Only under separate approval, configure routine daily and periodic execution. Scheduling, backfill, persistent enablement and Phase 4 remain inactive in this assignment.

## Evidence and final recommendation

Private ignored execution evidence: `/home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-29-initial-population-execution`. It includes the accepted recovery exception, exact commands/one-attempt markers, fresh pre/post snapshots, CLI stdout/stderr and exit statuses, full candidate JSON/CSV, TV diagnoses when executed, SQL/results, offline audits, configuration/protected-file checks, sanitization and hash manifest. Earlier stopped attempts and Gate B3-C evidence remain intact.

**Initial population PASS; routine synchronization CONDITIONAL GO only after separate operating-budget, recovery/RPO, monitoring/storage and scheduling approval.** No routine activation or Phase 4 execution is authorized or performed.
