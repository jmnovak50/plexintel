# Gate B3-A — bounded production TV persistence validation

**PASS.** Exactly one authorized TV-only synchronization ran for **October 31, 2026**, page 1, all languages, original premiere ascending. It persisted **eight TV series and eight observations**; this was a nonempty persistence validation, not merely a successful empty response. No B3-B, B3-C, rerun or page expansion occurred.

## Pre-execution verification

Fresh independent read-only checks immediately before execution verified:

- Authenticated **192.168.1.9:5432 / plexintel / jmnovak**, PostgreSQL 18.6 primary, using the unchanged production connection matching the direct-host backend.
- Installed migrations 001 and 002: original commit/verification receipts, reviewed file hashes, exact V2 catalog and strict runtime compatibility guard. Required typed primary/foreign keys, observation uniqueness, constraints, indexes, identity sequence and ACLs remain compatible. No migration executed.
- B2 run `04a7bb18-290a-42f1-86be-c0698330e3a8`, all **20 movie canonical records and 20 observations**, including every saved field/fingerprint/timestamp, match accepted B2 evidence. Zero TV and no additional run existed. B2's terminal partial history was preserved.
- Approved source ID **`plexintel-seerr-primary`** and normalized endpoint binding **`4547479bd1da2cd5fab4ff1af5e07bb9617e2dd37900447eb261491ec5330139`** agree with persisted provenance. Existing endpoint/key reused privately; no credentials printed.
- Private configuration unchanged, owner 1000:1000, mode **0600**, actual loader **enabled=false**. The actual loader also resolved the exact prospective process-local TV configuration without HTTP: Oct 31 only, one page, 25 attempts, zero retries, 10-second timeout, one-second spacing, five-second Retry-After ceiling; no forced refresh.
- All **11 writer table/sequence privilege checks** pass; roles/ownership/grants unchanged. `jmnovak` remains the **accepted temporary superuser security exception**, not a least-privilege connection.
- Validated logical recovery archive checksum and prior isolated restore PASS/40 matching tables reconfirmed, with required extension dependencies present. Snapshot remains **October 28, 18:18:46 CDT**, before B2; it does not cover B2/B3-A or establish PITR/full application recovery. No backup/restore performed.
- Quiet window: no conflicting discovery writer/lock, active pipeline/model/discovery process or discovery schedule; backend active with unchanged PID/start/restart count. Existing application and schedule baselines match B2. Prior gate artifact manifests and reviewed runtime/schema inputs verify.

All prerequisites passed. The single-attempt launcher repeated the read-only checks immediately before launch, verified the reviewed command and protected inputs, and created an exclusive local attempt marker. It did not alter application code or writer behavior.

## Exact single execution

Executed once, **23:40:33–23:40:42 CDT, October 28, 2026**. Retained for audit only; **do not rerun**:

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=25 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type tv --start 2026-10-31 --end 2026-10-31 --language all --sort-by first_air_date.asc --max-pages 1 --json
```

| Result | Verified value |
| --- | --- |
| Run ID | `e0f62c8a-892d-47b6-a6ff-0944ab46af1d` |
| Process / durable result | **Exit 0 / success**, terminal completion recorded |
| Pagination | **1/1 pages**, 8/8 reported identities; 0 duplicates or invalid rows |
| Canonical delta | **8 new TV**, 0 movie changes, 0 existing/updated titles |
| Observations / memberships | **8 new discovery observations**, one per typed TV identity and scope |
| Detail enrichment | **8 successful**, 0 cached/failed/deferred/pending |
| Eligibility | **7 eligible, 1 provisional, 0 excluded** |
| Completeness | Discovery/enrichment complete; **eligibility incomplete**, explicitly recorded |
| HTTP | **9 of 25 attempts**: one TV page plus eight TV detail GETs; **0 retries** |
| API / page errors | **None** |
| Persistent enablement | **False**, unchanged |

HTTP accounting reconciles the unchanged reviewed client's attempt counter, durable run counters, one recorded page and eight persisted detail outcomes. No extra preview, status, detail or verification HTTP call was made. No acquisition endpoint was called.

## Persisted TV audit and uncertainty

| Typed identity | Title | Classification |
| --- | --- | --- |
| `tv:330628` | My Sweet Home | Eligible |
| `tv:337952` | 5 mins to vomit | Eligible |
| `tv:338309` | Boxing Stars | Eligible |
| `tv:338525` | Pulso Fílmico | **Provisional — season_premiere_conflict** |
| `tv:339379` | Griff Across the Alps | Eligible |
| `tv:339701` | ARMS AND COMPANY | Eligible |
| `tv:339978` | Cap sur l’Élysée | Eligible |
| `tv:340206` | Theatertijd | Eligible |

All seven eligible assessments have reason `original_series_premiere_in_window`. Pulso Fílmico retains original/discovery premiere **October 31**, conflicting Season 1 premiere **October 28**, sanitized season-date provenance, and the explicit provisional diagnosis. It was persisted without being declared eligible. The eight identities and 7/1 classification split match the historical B1 subset; no identity addition/removal was observed.

All eight standard/4K media statuses, request counts and request-state collections remain **unknown**: SQL NULL with explicit omitted-source states. They do not mean unavailable, absent, available or zero requests. All eight source episode-runtime collections are explicitly empty; that means no duration values were supplied, not zero-minute episodes. Movie-style runtime and release events remain NULL/**not applicable** for TV. No digital availability, engagement score or acquisition eligibility was inferred.

Canonical metadata projections, typed/source fingerprints, discovery/detail snapshots, fetch timestamps, season provenance and eligibility were recomputed offline and match persistence. Every new row binds to the authorized run/source. No episode or season records were created.

## Independent read-only verification and isolation

**49/49 reconciliation checks passed.** The strict post-install catalog guard and read-only SQL checks passed. The existing `--summary --json` command independently reports **28 titles: 20 movies, 8 TV**, and the same latest run.

- Database totals changed only as expected: **1→2 runs, 20→28 canonical titles, 20→28 observations**. Sequence advanced **20→28**, still internally owned and ahead of committed observation IDs.
- Canonical keys `(media_type,tmdb_id)` and run/type/ID/scope memberships are unique; zero orphan references or actual cross-media numeric collisions. No cross-source contamination or unfinished run remains.
- All 20 existing movie records, all 20 B2 observations and the complete B2 terminal run remain identical, including unknown fields and original provenance. No observation history was overwritten.
- All 40 unrelated application-table row counts, application schema, roles/ACLs/default grants, backend PID/start/restart count and cron/timer definitions remain unchanged. Counts/catalogs were compared; no exhaustive per-row checksum of unrelated tables was taken.
- Persistent private configuration and its hash remain unchanged and disabled. All **1,240 protected paths** captured before this task's execution remain unchanged, including implementation, model/data inputs and prior gate evidence.

The separate reviewer inspected saved evidence offline; its verdict is retained in `independent-review.md` in the evidence directory. It made no additional production or HTTP calls.

Expected source warnings remain: live pagination is not an atomic snapshot, and upstream region/account settings can affect the scope. No execution deviation or production integrity anomaly was found. A local reporting comparison initially treated equivalent timestamp strings (space versus ISO `T`) as different; normalization of those two timestamp fields resolved it without any database repair or additional live request. The original formatting-only result is retained for audit.

## Evidence and stop point

Private ignored directory: `/home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-28-gate-b3-a/`.

- `before.json`, `after.json`, `reviewed-inputs-before.txt`, `protected-baseline.json`: actual pre/post observations and reviewed-input provenance.
- `authorized-command.txt`, `execute-once.py`, `execution-attempt.json`, `execution-completed.json`, `execution.json`, `execution.log`, `exit-status.txt`: exact single execution, run and terminal accounting.
- `readonly-summary.json`, `assessment.json`, `persisted-tv-audit.json` / `.csv`: independent reporting, all 49 checks and every persisted TV identity/diagnostic.
- `readonly-observation-operation.py`, `offline-assessment-operation.py`: reproducible read-only observation/offline reconciliation logic. Offline assessment issues no DB/HTTP operations; do not invoke the execution launcher again.
- `reporting-normalization-note.json`, `assessment-initial-format-comparison.json`, `independent-review.md`, `final-boundary-check.json`, `artifacts-hashes.json`: reporting correction, review and final audit seals.

**B3-A PASS for actual TV persistence and the authorized boundary.** Production TV repeat/idempotency and incremental recovery remain unexecuted. No B3-B/C, migration, schedule, restart, acquisition, scoring, recommendation or training change occurred. Discovery remains persistently disabled. **Stop here; all further production activity requires separate authorization.**
