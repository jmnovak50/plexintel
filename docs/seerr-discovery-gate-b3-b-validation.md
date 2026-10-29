# Gate B3-B — production movie rediscovery validation

**PASS for the stable cached movie-repeat validation and authorized safety boundary.** Exactly one invocation repeated the original October 28 movie scope, page 1. The same **20 existing movies** were returned, all **20 details reused from cache**. No additional canonical title or detail GET was required.

Run **`6b94d68a-cd67-4570-bc9c-ccdb14087bc5`**, October 29, 2026, **00:03:36–00:03:37 CDT**. Expected **terminal partial / exit 2** reflects `page_limit_exceeded`, not an integrity failure. Coverage remains **20/111 reported titles, page 1/6**. No B3-C, TV repeat, rerun or expansion occurred.

## Fresh prerequisite verification

Read-only checks immediately before launch, **00:03:35 CDT**, confirmed:

- Production **192.168.1.9:5432 / plexintel / jmnovak**, PostgreSQL 18.6 primary, using the same production connection as the direct-host backend.
- Every field of all **28 canonical rows, 28 observations and both historical runs** matches accepted B3-B preparation evidence. B2's 20 movies and B3-A's eight TV identities/source memberships remain intact; both runs are terminal.
- Approved source ID **`plexintel-seerr-primary`** and key **`4547479bd1da2cd5fab4ff1af5e07bb9617e2dd37900447eb261491ec5330139`** agree throughout persisted provenance.
- Migration 001/002 commit/verification receipts, reviewed runtime/schema/helper and gate manifests verify; exact installed V2 catalog and strict runtime guard pass. All **11 required table/sequence ACL checks** pass; roles, ownership and grants unchanged.
- Actual private configuration loader confirms disabled; owner 1000:1000/mode 0600/file hash unchanged. The actual loader resolves the prospective command's exact movie/date/language/page/budget/retry/timeout/spacing limits locally without HTTP.
- Validated recovery archive checksum, prior isolated restore PASS/40 matching tables and required vector/vchord dependencies remain valid. Snapshot remains **October 28, 18:18:46 CDT**, before B2/A/B; it does not cover those discovery changes, establish PITR or prove full application recovery. No backup/restore performed.
- No conflicting discovery process/advisory lock, unfinished discovery run or active pipeline/model job. Backend active, and existing application counts/catalogs/permissions/schedules match the reviewed baseline.

`jmnovak` remains the **accepted temporary PostgreSQL superuser exception**; least-privilege separation remains deferred. No credential or privilege change occurred.

At **00:03:36 CDT**, a local cache-only audit classified **all 20 movies as cached** under the unchanged 24-hour TTL. The launcher checked the exact command, accepted package/SQL hashes and protected inputs, repeated the independent read-only preflight, and created an exclusive single-attempt marker before launching one child process. No preliminary Seerr request was made.

## Exact authorized execution — audit only

Executed once from `/home/jmnovak/projects/plexintel`; **do not rerun**:

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=25 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type movie --start 2026-10-28 --end 2026-10-28 --language all --sort-by primary_release_date.asc --max-pages 1 --json
```

| Result | Verified value |
| --- | --- |
| Terminal / process outcome | **Partial / exit 2**, completion recorded |
| Run records | **2 → 3**, exactly one new UUID |
| Canonical titles | **28 → 28**: 20 movies, 8 TV; no identity added/lost/duplicated |
| Observations | **28 → 48**, 20 new run-specific movie memberships |
| New / existing / updated-title counters | **0 / 20 / 0** |
| Detail outcomes | **20 cached**, 0 success/failure/deferred/pending |
| HTTP accounting | **1 of 25 attempts**, movie discovery GET only; **0 detail GETs, 0 retries** |
| API errors | **None** |
| Pagination | One page fetched, six/111 reported; only `page_limit_exceeded` |
| Completeness | Discovery false, enrichment true |
| Persistent discovery | **Disabled**, exact configuration hash unchanged |

HTTP accounting reconciles the unchanged reviewed client's counters, durable run, one recorded page and all 20 cached outcomes. No additional live preview, status, enrichment or acquisition request was issued. The result is a supported **stable cached repeat**, not a source-drift or expired-cache case: returned identities and discovery summaries match the prior movie capture, and every cache entry was valid at actual execution time.

## Metadata, identity and history invariants

The only changed canonical field is **`last_observed_at` on the 20 returned movies**. It advances to the corresponding new discovery observation within the run interval. Discovery dates and `source_metadata.discovery` happened to remain identical; the implementation permits them to change when the source changes. The zero updated-title counter does not mean no SQL UPDATE/bookkeeping occurred.

For all 20 movies, detail metadata, metadata/source fingerprints, first-discovery run/time, metadata-change time, last-enriched time and last-attempt time remain unchanged. New cached observations retain the **original B2 detail-fetch timestamps, October 28 at 22:07:18–22:07:37 CDT**, rather than relabeling those details as freshly retrieved. Each new observation is `is_new=false`, `enrichment_outcome=cached`, with no changed fields and the same prior/current fingerprint.

All **28 prior observations** and both prior run records remain exactly unchanged, including B2's terminal partial result. Membership history is retained; new observations are expected under the new run ID. All **eight TV canonical rows** remain exact, including B3-A's seven eligible/one provisional assessments and season-date conflict history.

Unknown metadata stays unknown: eight movie detail premiere dates and ten runtimes remain NULL; all 28 standard/4K media statuses and request counts/states remain unknown. No missing value was interpreted as absence, availability, ineligibility or zero requests. No digital availability or engagement/acquisition eligibility was inferred.

## Independent read-only verification

The **unchanged, independently reviewed SQL file** from the accepted package was executed with the **actual new run ID and fresh pre-execution baseline**:

`artifacts/seerr-exploration/2026-10-28-gate-b3-b-preparation/post-run-verification.sql`

All **22 SELECT blocks executed in a forced read-only transaction**; all **14 anomaly queries returned zero rows**. This was actual post-run verification, not EXPLAIN-only validation. Checks covered old history, canonical identity union, typed keys, source/scope bindings, cached fields/fetch age, unselected TV data, time accounting, duplicates/orphans and unfinished runs. The sequence advanced **28 → 48**, matching committed observations.

**41/41 offline reconciliation checks passed.** Canonical/source fingerprints were recomputed; CLI JSON, durable run, reviewed SQL results and the existing independent `--summary --json` reader agree. Summary: **28 titles, 20 movies, 8 TV**, same latest run. No duplicate identity, cross-source contamination, orphan reference or unfinished run was observed.

Post-run strict catalog/ACL inspection and before/after comparison confirm unchanged application schema, roles/ownership/grants/default ACLs, **40 unrelated application-table row counts**, backend PID/start/restart count and cron/timer definitions. This is count/catalog verification, not an exhaustive per-row checksum of unrelated application data. All **1,291 protected source/configuration/data/prior-evidence paths** remain unchanged. No implementation or model input was edited.

The separately authorized independent reviewer assessed the saved evidence offline and independently confirmed **PASS for the authorized B3-B movie repeat, with no blocker found**. It confirmed the same 20 cached movies, one GET, exact observation/run deltas, unchanged detail/fetch provenance and prior history/TV, and correct page-cap partial/exit 2. Its verdict is retained in `independent-review.md` in the execution evidence directory. It made no further database/network calls or edits.

Expected source warnings remain: pagination is not an atomic snapshot and upstream region/account settings can affect scope. No unexpected API, accounting, metadata, schema or production-isolation anomaly was found.

## Evidence and stop point

Private ignored directory:

`/home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-29-gate-b3-b/`

- `before.json`, `after.json`, `reviewed-inputs-before.txt`, `protected-baseline.json`: fresh target/schema/ACL/recovery/source/isolation checks and full row snapshots.
- `authorized-command.txt`, `execute-once.py`, `execution-attempt.json`, `execution-completed.json`, `execution.json`, `execution.log`, `exit-status.txt`: exact single execution and accounting.
- `pre-execution-cache-audit.json`, `canonical-field-differences.json`, `cached-movie-audit.json/.csv`: every returned identity, preserved detail age and allowed bookkeeping change.
- `execute-reviewed-sql-readonly.py`, `post-run-verification.json`, `readonly-summary.json`, `offline-assessment-operation.py`, `assessment.json`: actual reviewed SQL results and all 41 audit checks. The offline assessment issues no DB/HTTP call; do not invoke the execution launcher again.
- `independent-review.md`, `final-boundary-check.json`, `sanitization-check.json`, `artifacts-hashes.json`: review and final evidence seal; no configured endpoint/key exposed.

**B3-B PASS for one nonempty stable cached movie repeat and the authorized bounds.** Full-date discovery coverage, a production TV repeat and B3-C remain unvalidated/unexecuted. No forced refresh, migration, service/scheduling/configuration change, acquisition/download, recommendation/scoring/labeling/training action or unrelated mutation occurred. Persistent discovery remains disabled. **Stop here; further production execution requires separate authorization.**
