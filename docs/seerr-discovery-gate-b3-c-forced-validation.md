# Gate B3-C — amended forced-refresh production validation

**PASS for the explicitly amended incremental/forced-refresh experiment.** Exactly one movie-only, two-page invocation returned **20 existing movies and 19 new movies**, retrieved all **39 details**, and preserved historical identities/observations and production isolation. **Natural TTL expiration was not validated.**

Run **`1d7e4429-3af2-4658-a51a-1689bde36499`**, **October 29, 2026, 00:47:44–00:48:24 CDT**. Terminal **partial / exit 2** correctly records incomplete, changing source pagination. There was no rerun, page expansion or remediation.

## Authorized amendment and fresh prerequisites

The operator removed the October 29, 22:08 timing/ordinary-expiry prerequisite and authorized adding **only `--refresh`** to the reviewed C-page command. The original natural-expiry package remains preserved as historical evidence. Acceptance here requires new and existing movie identities, genuine detail fetches via forced refresh, correct provenance/history/accounting and isolation. A real metadata delta is optional; natural expiry is expressly excluded from the conclusion.

Fresh read-only preflight immediately before execution confirmed **192.168.1.9:5432 / plexintel / jmnovak**, PostgreSQL **18.6** primary and the same effective URL as the direct-host backend. All **28 canonical rows, 48 observations and three terminal runs** matched the accepted B3-B baseline exactly. Approved source **`plexintel-seerr-primary`**, key **`4547479bd1da2cd5fab4ff1af5e07bb9617e2dd37900447eb261491ec5330139`**, remained bound throughout.

Migration 001/002 committed-install receipts, reviewed files and strict V2 catalog/runtime compatibility checks passed; all **11 required table/sequence ACL checks** passed. Existing roles/ownership/grants, protected application data counts/catalogs, backend PID/start/restart count and scheduling matched. No discovery writer, abandoned running run or conflicting pipeline/model job was present. Loopback backend health returned **HTTP 200**, `{ok:true, service:library-catalog}`, before and after; this health read is not a Seerr request.

The private loader confirmed **enabled=false**, unchanged owner 1000:1000/mode 0600/hash, cache settings and credentials. A local actual-implementation cache audit found **20 ordinarily cached movies and 20 forced-fetch decisions**. No TTL, database timestamp or persisted cache setting was modified to force eligibility. `jmnovak` remains the **accepted temporary superuser exception**, not least privilege; no credentials or privileges changed.

## Fresh PostgreSQL-consistent recovery point — PASS

Created one new owner-only archive using the established `pg_dump` custom-format convention and a shared exported **read-only production snapshot**. No existing archive was overwritten or deleted.

| Recovery evidence | Result |
| --- | --- |
| Archive | `/home/jmnovak/.local/state/plexintel/preflight-backups/plexintel-20261029T054550Z-e6b300.dump` |
| Snapshot | **October 29, 2026, 00:45:50 CDT** (`05:45:50 UTC`) |
| Size | **174,202,742 bytes**, mode 0600 |
| SHA-256 | `d9c6fd1cd0e5e081f0d2484d35092cd36576107bb8dd7bb25ed7dc121f38f67c` |
| Dump / archive listing / full archive read | **Exit 0**, completion and checksum verified |
| Isolated restore | **Exit 0**, single transaction into a new private Unix-socket-only PostgreSQL 18 cluster; TCP disabled |
| Restored comparison | **All 43 table counts** match: 40 application tables plus three discovery tables; full 28-title/48-observation/three-run records and observation sequence match |
| Schema/reads | Strict V2 compatibility, catalogs, constraints/indexes, ownership/grants and representative application reads pass |
| Cleanup | Isolated server stopped and its task-owned directory removed; production was never restored or restarted |

Available space passed the existing guard of at least five database sizes and 5 GiB. The restore used existing matching vector/vchord dependencies and isolated NOLOGIN placeholders for referenced role names, with no production role changes. The **32 previously reviewed VectorChord library-path spelling differences** (`$libdir/vchord` versus `vchord`) were normalized only for comparison, using the same verified binary and explicit prior function allowlist; other catalog differences were not tolerated.

This fresh recovery point covers the complete **pre-C** application/discovery state. It does not contain this new C run, cluster-global passwords/memberships, external models/filesystem, or a PITR chain. Full application startup/authentication and production restore were not tested. Detailed private source/restored snapshots, logs, checksum and recovery review accompany the archive; `recovery-readiness.json` links them in the execution evidence.

## Exact single command — audit only; do not rerun

Executed once from `/home/jmnovak/projects/plexintel` through the existing direct Python environment:

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=45 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type movie --start 2026-10-28 --end 2026-10-28 --language all --sort-by primary_release_date.asc --max-pages 2 --refresh --json
```

The launcher verified the original reviewed inputs, amended command, fresh validated archive and current read-only preflight, then created an exclusive attempt marker. No preliminary Seerr dry-run/status/detail call was issued. The persistent file stayed disabled.

| Metric | Actual |
| --- | ---: |
| Production synchronization invocations | **1** |
| Existing movies rediscovered/refreshed | **20** |
| New movies persisted | **19** |
| Unique movies / successful detail GETs | **39 / 39** |
| Cache hits / failed / deferred / pending details | **0 / 0 / 0 / 0** |
| HTTP attempts | **41 of 45: 2 page GETs + 39 detail GETs** |
| Retries / API errors | **0 / 0** |
| Canonical inventory | **28 → 47**: 39 movies, 8 TV |
| Observation history | **48 → 87**, 39 new run-specific memberships |
| Discovery runs | **3 → 4**, one new terminal UUID |
| Existing-title metadata changes | **0** |

HTTP accounting reconciles the reviewed client's attempt counter, CLI/durable run, fetched pages and persisted successful details. `--refresh` bypasses PlexIntel freshness/cooldown; it does not clear upstream Seerr/TMDB caches. Identical returned values do not negate the real detail retrieval evidence.

## Source drift, metadata and history

Seerr reported **111 total titles on page 1, 112 on page 2**, with six pages throughout. Both pages contained 20 raw rows. The collector suppressed **one duplicate**, yielding **40 raw rows → 39 unique persisted identities** (20 accepted on page 1, 19 on page 2). Diagnostics explicitly record `pagination_totals_changed` and `page_limit_exceeded`.

This is changing upstream pagination, not a duplicate canonical identity or forced target count. The unchanged collector records the duplicate count but does **not** retain the repeated ID or a complete raw response; that exact ID cannot be reconstructed from the sanitized durable output. No extra request was issued to investigate. Discovery coverage is incomplete and has no single atomic population denominator; enrichment is complete for all 39 retained identities.

All **20 existing movie fingerprints, detail values, metadata-change timestamps and immutable first-discovery provenance remained unchanged**. Their only canonical changes are `last_observed_at`, `last_enriched_at` and `last_enrichment_attempt_at`, advanced for the new observation and genuine detail fetch. New observations contain the fresh fetch times and correct prior/current fingerprints and changed-field diagnostics. The absence of an existing metadata delta is reported honestly: change detection remains supported by isolated tests, not a live changed-value claim.

All **three previous terminal runs, 48 historical observations and eight unselected TV canonical rows remain exact**, including the earlier provisional TV conflict. No title was deleted or collided under `(media_type,tmdb_id)`. New canonical rows bind to the new run/source; all 39 observations have the correct scope, `is_new` flags and enrichment outcomes. Observation sequence advanced **48 → 87**.

Unknown metadata remains unknown: **8 movie premiere dates, 14 movie runtimes, and all 47 standard media/request states remain unknown**; no omission was interpreted as absence, availability, ineligibility or zero requests. Movie primary release dates still do not establish digital availability. Full typed identity/metadata/fetch audits are saved in `persisted-movie-audit.json/.csv`.

## Read-only integrity audit and isolation

The original 25-block SQL was preserved. The execution copy records the operator amendment: `force_refresh=true`, no natural-age prerequisite, and forced-refresh labels; all real fetch/provenance/time checks remain. The precise source/amended hashes and changes are in `authorization-amendment.json`.

All **25 SELECT blocks executed read-only** with the actual new UUID and fresh pre-state; all **17 integrity-anomaly queries returned zero rows**. **38/38 offline reconciliation checks passed**, including metadata projections, source/canonical fingerprints, fetch timestamps, identity union, first provenance, old history and exact CLI/durable-run/summary agreement. The existing independent summary reader reports 47 titles: 39 movies and 8 TV.

Strict post-schema/ACL checks, 40 unrelated application-table counts, catalogs/roles/grants/default ACLs, backend health/process state, cron/timers, private configuration and protected source/data/prior-evidence hashes remain unchanged. Application isolation evidence compares counts/catalogs, not exhaustive per-row value checksums. No schema/application/model code, schedules, credentials, acquisition/recommendation behavior or backend services changed. Restoring model tables as data in an isolated database did not run scoring/training.

The separate reviewer assessed saved evidence offline and independently confirmed **PASS for incremental insertion and forced-refresh persistence mechanics, with no integrity blocker**. It reconciled all counts/history/timestamps, confirmed the SQL amendment, and independently checked the fresh archive size/SHA-256 and saved 43-table recovery evidence. It explicitly withheld complete-population, natural-TTL and changed-value claims. Its verdict is retained in `independent-review.md` in the evidence directory. No additional production or HTTP call was made by that review.

## Evidence, risks and recommendation

Private ignored execution directory:

`/home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-29-gate-b3-c-forced/`

It contains the authorization/SQL amendment, exact command and one-attempt marker, fresh recovery operation/result/readiness, complete pre/post snapshots, stdout/stderr/exit/run accounting, 25-query results, source/metadata audits, 38-check assessment, independent review, final boundary checks, sanitization check and checksum manifest. Private archive companions preserve full source/restored recovery evidence. Earlier archives and gate artifacts remain unchanged.

Remaining limits: **natural TTL expiry and live failure/interruption recovery were not exercised**, source pagination is non-atomic, the exact suppressed duplicate ID is unavailable, and current refreshed values were unchanged. The accepted superuser exception, logical-only recovery scope and separate authorization for broader operations remain in effect.

**Recommend closing the amended B3-C incremental/forced-refresh validation as PASS.** This supports the demonstrated controlled persistence mechanics; it does not authorize routine scheduling, broader ingestion, another run, natural-expiry validation, model changes or acquisition. Discovery remains persistently disabled. **Stop after this report; further production execution requires separate authorization.**
