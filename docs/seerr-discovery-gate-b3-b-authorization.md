# Gate B3-B — reviewed authorization package

**GO to request separate authorization for exactly one B-movie repeat, conditional on fresh pre-execution checks. B3-B was not executed and is not authorized by this preparation task.** No live Seerr request or production write occurred. Persistent discovery remains disabled.

This package implements **B-movie** from [the accepted B3 plan](seerr-discovery-gate-b3-plan.md). B-TV is an optional, separately authorized repeat and is **excluded** here. No B3-C, refresh, additional page/date, scheduling or automatic progression is included.

## Verified production baseline

**Read-only observation: October 28, 2026, 23:52:34 CDT.** A connection forced read-only and a repeatable-read transaction independently compared every canonical row, observation and run against the accepted B3-A snapshot, and the B2 subset against original B2 evidence.

| Check | Current evidence |
| --- | --- |
| Target | `192.168.1.9:5432 / plexintel / jmnovak`, PostgreSQL 18.6 primary; same effective URL as direct-host backend |
| Inventory | **28 typed canonical titles: 20 movies and 8 TV; 28 observations; 2 terminal runs**, all fields/timestamps/fingerprints unchanged |
| B2 | `04a7bb18-290a-42f1-86be-c0698330e3a8`, terminal partial; 20 movies/20 successful observations, recorded 21 HTTP attempts/zero retries |
| B3-A | `e0f62c8a-892d-47b6-a6ff-0944ab46af1d`, success; 8 TV/8 successful observations, recorded 9 HTTP attempts/zero retries; 7 eligible/1 provisional |
| Source | Every run/known canonical enrichment binds to `plexintel-seerr-primary` and key `4547479bd1da2cd5fab4ff1af5e07bb9617e2dd37900447eb261491ec5330139` |
| Schema | Committed 001/002 receipts and prior gate manifests verify; reviewed SQL/runtime unchanged; exact V2 catalog and strict runtime compatibility guard pass; sequence 28/is_called=true |
| ACLs | All 11 table SELECT/INSERT/UPDATE and sequence USAGE/SELECT checks pass; roles/grants/ownership unchanged |
| Private configuration | Actual loader disabled; owner 1000:1000, mode 0600, exact file hash unchanged; existing endpoint/key reused privately |
| Isolation | Backend PID 1633/start/restart count unchanged; same 40 application-table counts, unrelated schema/roles/ACLs/default grants and schedule definitions; no active conflicting writer/pipeline/model process |
| Recovery | Validated archive checksum and prior isolated restore PASS/40 matching tables reconfirmed; required vector/vchord dependencies present |

All **14 offline baseline checks passed**, including independent metadata/source-fingerprint recomputation and source binding. `canonical-baseline-audit.json/.csv` records all 28 identities and memberships, not a sample. B2's eight unknown premiere dates/ten unknown runtimes and all 28 unknown media/request statuses remain intact. B3-A's provisional date conflict remains unchanged.

`jmnovak` remains a PostgreSQL **superuser**, the accepted temporary security exception; this is not least privilege. Hardening remains deferred. No role, privilege or credential change is proposed.

Recovery evidence remains the validated logical archive `plexintel-20261028T231846Z-08d8dc.dump`, SHA-256 `8754923a28ed13c140cb269e59b2389786e4d653e6cfbfcf14bb46fb06d52f1a`. Its snapshot is **October 28, 18:18:46 CDT**, before B2 and B3-A. It proves the previously tested database recovery scope, not coverage of these discovery runs, PITR, image consistency or full application recovery. No restore/backup was performed here. Reassess age and accepted recovery-point coverage before a future write; stop if unacceptable, without attempting repair or a new backup under this authorization.

## Exact bounded command — proposal only

Working directory `/home/jmnovak/projects/plexintel`; direct host `plexenv`, no Docker. This is the unchanged B-movie command from the accepted plan. **Do not run it under this prompt.**

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=25 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --media-type movie --start 2026-10-28 --end 2026-10-28 --language all --sort-by primary_release_date.asc --max-pages 1 --json
```

Scope key: `11f0c306e3ee8d54e487e574396055b28229a5a72a61e85120248ab219e3d0f9`, the original B2 movie scope. Page 1 always starts afresh. Hard limit **25 total attempts**, zero retries, 10-second request timeout, one-second spacing and five-second Retry-After ceiling. No `--refresh` or `--enrich-due`. Process-local enablement does not edit the file. A dry run would issue HTTP and is not part of preparation or a proposed preliminary check.

At the snapshot, **all 20 movies are cache-eligible** under the actual 24-hour TTL. Their expiry times span **October 29, 22:07:18.286136–22:07:37.190507 CDT**, with eligibility requiring age strictly less than 24 hours. Recompute cache actions at execution time; do not extend TTL or misrepresent old fetches as new.

| Live condition | Expected behavior under this same command |
| --- | --- |
| Same 20 returned, all fresh | **1 HTTP page GET**, 20 cached observations, no detail GETs; totals **28 titles / 48 observations / 3 runs** |
| Some returned identities new or cache expired | One page plus necessary detail GETs, within 25. Ordinary 20-row page implies at most 21 attempts. Newly fetched details may legitimately update metadata; report separately from pure cache proof |
| Larger page or source/API failure | Budget/page bounds still hold; reconcile failures/deferred work. No retry, expansion or forced refresh |

The plan permits natural TTL-based fetching within the fixed command. A later authorization limited specifically to a fully cached repeat must stop if that cache prerequisite changes. Source population/order is unknown during preparation because HTTP is forbidden; counts above are conditional expectations, not target numbers.

## Intended database effects and idempotency

**Code findings**, not an additional live repeat:

- Every invocation creates **a new run and new run-specific observations**. Zero new observations is not the expected stable-repeat result. Uniqueness is `(run_id,media_type,tmdb_id,scope_key)`; canonical identity is `(media_type,tmdb_id)`.
- For baseline canonical keys S and returned retained keys R, canonical after-state is **S∪R**. New canonical keys are R−S; existing keys R∩S. Under this one scope, new observation count is |R|. No missing title is removed.
- Existing first-discovered time/run and typed identity remain immutable. All 28 prior observations and both prior runs remain exact. Membership is historical observation evidence, not a separate current-membership table; a title absent from the new page retains its earlier membership/history.
- A cached returned movie updates **last observation**, discovery-date evidence when supplied, and `source_metadata.discovery`. Thus canonical rows are touched even when `new_titles=updated_titles=0`. This is expected rediscovery bookkeeping.
- Cache reuse preserves canonical detail-derived fields, detail snapshot/fingerprint, metadata-change time, last-enrichment/attempt times and the original observation detail-fetch age. New observations contain the cached detail and old `detail_observed_at`; `observed_at` records the new discovery time. It does not make the metadata fresh.
- Natural detail fetches advance attempt/enrichment/detail-fetch times. Identical projected metadata retains its change time/fingerprint; a genuine metadata delta records changed fields and an appropriate new fingerprint/change time. Compare source-derived projections and provenance before accepting a change.
- **All eight TV canonical rows and B3-A history remain exact**, including the provisional conflict. Numeric TMDB overlap across movie/TV is valid under typed keys; contamination or overwriting the TV row is not.
- Missing metadata/status stays unknown. A cached summary does not repair an unknown detail premiere/runtime or imply digital availability. A failed fetch preserves prior metadata and records a real failed attempt; budget exhaustion before GET records deferred work without inventing an attempt. No unknown status means absence, availability or zero requests.

Canonical upserts can issue UPDATE statements for existing rows even with unchanged fingerprints. Logical idempotency concerns identity, field/provenance semantics and correct history, not zero SQL writes or zero physical row versions.

## Fresh execution prerequisites and acceptance criteria

Future authorization must approve **one foreground invocation of the exact command**, plus read-only pre/post verification. It must not implicitly approve B-TV, C or a retry. Before using it:

1. Recheck target/backend URL, exact installed catalog and runtime/helper hashes, 001/002 receipts, required writer ACLs, approved source binding and private loader disabled state. Never print credentials.
2. Capture a **fresh** full baseline, not just this preparation snapshot. Require the accepted 28-title/28-observation/two-run inventory and exact B2/B3-A records, no abandoned run, active writer/advisory lock, conflicting pipeline/model work or discovery schedule. Stop for any unexplained drift; do not repair it.
3. Revalidate recovery evidence/dependencies and acceptable recovery-point age. Capture protected application counts/catalogs, backend and schedules. Recompute movie cache eligibility and document the anticipated path under the proposed approval.
4. Resolve exactly one movie/day/all-language scope and the real loader's effective bounds locally, without HTTP. The Retry-After ceiling is verified from the actual command/configuration; it is not a stored run parameter. Create a new owner-only evidence directory and exclusive single-attempt marker only after every prerequisite passes.
5. Run once, preserve stdout/stderr/exit/run ID, then verify read-only and stop. A partially committed run is not permission to retry.

**PASS:** nonempty overlap with existing movie identities demonstrates repeat processing; exact identity union, new run/membership accounting, cache/fetch timestamps/fingerprints and all isolation/history invariants reconcile. The strongest expected result is the stable 20-title cached case above. Report deviations and the number of existing identities actually exercised; source additions/removals alone are not duplicates or automatic corruption.

Expected historical cap outcome is **terminal partial / exit 2**, solely `page_limit_exceeded`, with enrichment complete; B2 reported six pages/111 titles. This is acceptable bounded coverage. If the source now fits a single page, correctly recorded success/exit 0 is acceptable. No claim of full-date coverage for a capped prefix.

**INCONCLUSIVE:** empty response or no existing identities returned; safe containment with unexpected API/deferred/failed enrichment; or insufficient evidence for the requested repeat claim. Persisted work remains auditable; do not call a new-title-only or expired-cache run a fully cached rediscovery proof.

**FAIL:** duplicate/overwritten identities, wrong source/scope, altered old history/TV rows, unexplained metadata/fetch timestamps, missing accounting or violated bounds/isolation. Exit 1 or 75 requires investigation, not a retry; inspect durable progress since the process exit alone does not prove no writes. Do not perform rollback SQL, privilege changes or migration/restore under this gate.

## Exact post-run verification SQL

Prepared SQL: [post-run-verification.sql](/home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-28-gate-b3-b-preparation/post-run-verification.sql). **22 SELECT blocks validated with PostgreSQL EXPLAIN, without ANALYZE**, in a forced read-only transaction; no fictitious B3-B verdict was evaluated. No production records were created by validation.

Independent review caught an initial mixed-case block marker that combined two result sets. It is corrected; validation now rejects unrecognized markers or multiple statements per block. The initial check evaluated only a read-only numeric-overlap diagnostic beyond its EXPLAIN statements; it made no write or Seerr call. Original validation evidence is retained. All 22 corrected blocks were subsequently validated separately with EXPLAIN only.

The SQL checks the actual new run, complete observations/outcomes, exact preservation of both prior runs/all prior observations, canonical identity union, immutable provenance, cached detail/age preservation, unchanged unselected TV/movies, source binding, scope, duplicates/orphans, unfinished runs and sequence. It uses typed `jsonb_populate_recordset` to normalize baseline timestamps rather than comparing serialization separators.

For a future authorized post-check, bind:

- `run_id`: **new B3-B UUID** from the actual execution; never an old gate UUID.
- `before_titles`, `before_runs`, `before_observations`: `psycopg2.extras.Json` arrays from the fresh pre-execution snapshot. Do not replace them with post-state records.

Use the existing connector privately with `default_transaction_read_only=on`, repeatable-read/read-only, a 15-second statement timeout and two-second lock timeout. Execute each named block separately; no temporary table, schema object or baseline write is needed. Example reader body, for later use inside that guarded connection:

```python
params = dict(run_id=new_run_uuid,
    before_titles=Json(before['canonical_titles']),
    before_runs=Json(before['discovery_runs']),
    before_observations=Json(before['observations']))
parts = re.split(r'^-- check: ([a-z_]+)\n', sql_path.read_text(), flags=re.MULTILINE)
assert len(re.findall(r'^-- check:', sql_path.read_text(), flags=re.MULTILINE)) == len(parts[1::2])
assert all(q.count(';') == 1 and q.strip().endswith(';') for q in parts[2::2])
with connection.cursor() as cur:
    for name, statement in zip(parts[1::2], parts[2::2]):
        cur.execute(statement, params)
        save_sanitized_result(name, cur.fetchall())
connection.rollback()
```

Anomaly queries must return no rows; inventory/outcome/diagnostic queries require interpretation, not empty results. A numeric cross-media overlap is diagnostic, not itself a PK violation. Also re-run the exact reviewed catalog comparison/strict runtime guard, 11 ACL checks, actual private loader and independent existing `--summary --json` reader. Compare canonical projections/fingerprints and every observation to captured details offline.

Reconcile CLI JSON, durable terminal run and summary: same UUID, scope/parameters, source, counts, pagination/completeness/errors/warnings. For a one-page stable cached repeat, HTTP attempts must be **1**, cached **20**, success/failed/deferred/pending **0**, new/updated canonical **0**, existing **20**, movie count **20** and TV count **0**. Observation count grows by 20, including cached snapshots; B2/B3-A history does not change. With actual fetches, account for each GET and its outcome; no more than 25 attempts/zero retries.

Finally compare all preexisting TV records, protected application row counts/schema/ACLs, backend state and schedules, disabled config/file hash and protected source/evidence hashes. Application checks cover counts/catalogs, not an exhaustive checksum of every unrelated row. Sequence may have safe gaps after a rolled-back operation; it must remain properly owned and ahead of committed observation IDs. Save typed audits and a private SHA-256 manifest, then stop.

## Independent review, evidence and recommendation

The explicitly requested separate reviewer reviewed source and prior captures offline and confirmed the intended new-run observation semantics, cache timestamp preservation, mutable discovery bookkeeping despite zero updated-title counts, strict TTL boundary, unchanged TV/history and separate B-TV authorization. It found the SQL marker issue described above, then confirmed **22 recognized, single-statement blocks with 22 PASS validation results**. Final independent verdict: **GO to request separate approval of one B-movie execution, conditional on fresh checks; no remaining package blocker**. It made no database/network calls or edits. Findings are retained in `independent-review.md` in the evidence directory.

Final read-only comparison at **23:58:22 CDT** again matched all 28 canonical rows/28 observations/two runs and the target/schema/roles/ACLs/application counts/backend/schedules/configuration baseline. The quiet window remained clear. This preparation created no discovery record.

Private evidence: `artifacts/seerr-exploration/2026-10-28-gate-b3-b-preparation/`: `before.json`, `baseline-assessment.json` (14 checks), `canonical-baseline-audit.json/.csv`, `cache-audit.json`, reviewed input/manifest verification, `proposed-command.txt`, prepared SQL and EXPLAIN-only evidence. Existing 276-test/captured replay evidence remains unchanged; no new synchronization or model test job was run here.

**GO to seek one B-movie execution approval, with fresh prerequisites. NO-GO to execute under this preparation prompt.** No implementation, migration, persistent configuration, service, schedule, acquisition, scoring, recommendation or training changes were made. No HTTP or production write occurred. Stop after this package; separate explicit authorization is required to execute.
