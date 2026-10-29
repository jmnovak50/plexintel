# Gate B2 — one bounded production persistence validation

**PASS for the explicitly authorized safety boundary and persistence validation.** Exactly one movie-only execution ran for **October 28, 2026**, page 1 only. No rerun, retry, TV execution, expanded date/page scope or subsequent gate occurred.

The CLI correctly returned **exit 2 / terminal `partial`** because `page_limit_exceeded` was expected. Discovery coverage is incomplete: **20 of 111 reported titles**, page **1 of 6**. This PASS does not assert complete discovery coverage, TV production persistence or idempotency.

## Pre-execution conditions — PASS

Read-only preflight at **22:06 CDT on October 28, 2026** verified:

- Original B1 and targeted-follow-up artifact hashes, original full pagination evidence, exact 936-identity reconciliation and final audit records. The operator accepted B1 as PASS; original partial CLI/error history remains preserved.
- Validated logical recovery archive checksum `8754923a28ed13c140cb269e59b2389786e4d653e6cfbfcf14bb46fb06d52f1a`, prior isolated-restore PASS/40 matching tables, and required vector/vchord recovery dependencies. Existing snapshot remains October 28 at **18:18:46 CDT**; its age and full-host/PITR limitations are unchanged. No backup was overwritten or new restore performed.
- Authenticated **192.168.1.9:5432 / plexintel / jmnovak**, PostgreSQL **18.6**, online and not in recovery. Effective URL matched the active host backend; no credentials were printed.
- Migration 001's original commit/corrected verification, migration 002's confirmed Gate A commit, unchanged reviewed SQL/runtime checksums, exact V2 catalog and actual runtime guard. No migration was rerun.
- All **11 writer privilege checks**: SELECT/INSERT/UPDATE on the three discovery tables, USAGE/SELECT on the observation sequence. Canonical ownership/ACLs match; `jmnovak` remains the **accepted temporary superuser exception**, not least privilege. No grants/roles/credentials changed.
- Empty discovery state: **0 runs / 0 titles / 0 observations**; sequence **1 / is_called=false**. No existing inventory/source history needed adoption. The first authorized run establishes the approved binding.
- Private configuration owner 1000:1000, mode `0600`, unchanged file hash and **enabled=false**. Approved ID `plexintel-seerr-primary`; normalized source key `4547479bd1da2cd5fab4ff1af5e07bb9617e2dd37900447eb261491ec5330139`.
- Exact effective scope: **movie only**, one-day **2026-10-28**, language **all**, primary release ascending, **one page**, **25 total HTTP attempts**, **zero retries**, timeout **10 s**, spacing **1 s**, retry-after ceiling **5 s**, Python **`-B`**. No implicit TV scope or broad defaults were inherited.
- Quiet execution window: no active discovery writer/advisory-lock conflict, running pipeline/model process, discovery schedule/timer or enabled DDL event trigger. Existing backend active; unrelated application/schema/role/schedule baselines captured.

No precondition mismatch was observed. No Seerr preflight/status/preview request was issued; the authorized command accounts for all Seerr calls in this task.

## Exact single execution

Started **22:07:17 CDT**, completed **22:07:37 CDT**, October 28. A local exclusive execution marker prevents an accidental second attempt. The following command was executed once; retained here for audit only, **do not rerun**:

```bash
SEERR_DISCOVERY_ENABLED=true SEERR_DISCOVERY_MAX_REQUESTS=25 SEERR_DISCOVERY_RETRIES=0 SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1 SEERR_DISCOVERY_MAX_RETRY_AFTER=5 plexenv/bin/python -B scripts/sync_seerr_discovery.py --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env --execute --start 2026-10-28 --end 2026-10-28 --language all --sort-by primary_release_date.asc --max-pages 1 --json
```

Process-local enablement did not edit the private file. No alternate writer, instrumentation wrapper, page expansion or retry was used.

| Result | Verified value |
| --- | --- |
| Run ID | `04a7bb18-290a-42f1-86be-c0698330e3a8` |
| Process exit | **2**, expected partial result |
| Durable terminal status | **partial**, completed timestamp present; no running/abandoned run |
| Source ID/key | Exactly approved ID/key; run parameters, run source and canonical enrichment provenance agree |
| Canonical rows | **20 new movies**, 0 existing/updated, 0 TV |
| Observations | **20**, same typed IDs/run/scope; all `is_new=true` |
| Detail outcomes | **20 success**, 0 cached, failed, deferred or pending |
| HTTP accounting | **21 attempts**: one movie page plus 20 detail GETs; **0 retries**; below 25 |
| Pagination | One page fetched; six pages / 111 titles reported; 91 reported titles not retrieved |
| Discovery completeness | **false**, correctly recorded |
| Enrichment completeness | **true** for the 20 persisted titles |
| Page diagnostic | Only `page_limit_exceeded` |
| API/enrichment errors | **none** |
| Other warnings | `live_pagination_is_not_an_atomic_snapshot`; `upstream_region_and_account_settings_can_change_scope` |

HTTP accounting comes from the unchanged reviewed GET-only client, persisted run counters, CLI result and 20 successful detail outcomes; no additional Seerr request was made for verification. The hard budget counts attempts, including failed attempts had any occurred. Requester identities, credentials and internal service identifiers are excluded by the source sanitizer.

## Read-only reconciliation and unknown metadata

**31 offline reconciliation checks passed.** Strict post-run schema verification passed, and CLI output matches the durable run counts, terminal flags, parameters, pagination, errors and warnings. All 20 canonical `(media_type,tmdb_id)` keys are unique and match the 20 observation keys. Observation run/scope uniqueness and first-discovery membership reconcile. Source fingerprints, canonical metadata fingerprints, detail/discovery snapshots and fetch provenance match; sequence state is **20 / is_called=true**. No orphan, duplicate or cross-type contamination was found.

All discovery summary dates remain **2026-10-28**. Metadata normalization and the persisted values agree:

| Persisted uncertainty | Count | Meaning |
| --- | ---: | --- |
| Unknown detailed movie premiere | **8** | Nullable canonical date; valid discovery date remains independently retained |
| Unknown movie runtime | **10** | Source zero becomes `NULL`/`zero_unknown`; no default duration or zero-minute claim |
| Unknown standard/4K media status | **20** | SQL NULL and explicit source-omitted state |
| Unknown request count/status | **20** | `request_count=NULL`, requests `omitted`; not fabricated zero requests |

These gaps did not remove candidates or imply library absence, ineligibility, unrequested status or availability. Movie primary-release metadata does not establish digital availability. Movie eligible/provisional/excluded counters are zero because that TV classification is not applied to movies; this does not mean these movies were classified ineligible. No engagement score, recommendation or acquisition action occurred.

**Source change versus B1:** 19 persisted identities were in the original B1 capture. The additional live identity, **movie 1811154 — Anthony Lin's The Lull**, has an in-window discovery date **2026-10-28**; its detail premiere/runtime remain unknown. This is recorded as changing upstream data, not silently added scope or a claim that the old snapshot was exhaustive forever. The original B1 evidence and window were not modified, and no extra request was made to investigate the new identity.

## Production isolation and independent review

Before/after read-only comparisons confirm:

- Unrelated application schema, roles, ownership/ACLs and default grants unchanged.
- Row counts for **40 existing application tables unchanged**.
- Backend remains active with **PID 1633**, the same start time and restart count; no restart/redeployment.
- User/root cron and system/user timer definitions unchanged; no schedule registration.
- Source configuration and its exact file hash unchanged; actual loader confirms **persistently disabled** after the child process exits.
- Recovery archive and reviewed implementation/migration inputs unchanged.

The only authorized production data mutations were the discovery run, its 20 canonical titles, 20 observations, enrichment bookkeeping and observation identity-sequence advancement. No unrelated DML/DDL, schema migration, acquisition, model/scoring/training job, embedding/recommendation change, credential change, commit or push was performed.

A separate reviewer inspected the saved evidence **offline**, found no accounting anomaly and independently assessed **PASS for the bounded movie persistence check**. The reviewer made no database/network calls or edits. This review does not authorize a repeat, full collection, TV writer or later gate.

## Audit evidence and stop point

Owner-only ignored evidence directory:

`/home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-28-gate-b2/`

- `before.json`: all prerequisite checks, recovery/source/configuration/ACL/quiet-window evidence and pre-write baselines.
- `execution-attempt.json`, `authorized-command.txt`, `exit-status.txt`: single-attempt boundary and exact command/status.
- `execution.json`, `execution.log`: unmodified CLI output and structured progress/terminal log.
- `after.json`: read-only production schema, run, canonical/observation data and before/after comparisons.
- `assessment.json`: 31 checks, HTTP and identity reconciliation, expected partial outcome and PASS assessment.
- `persisted-title-audit.json` / `.csv`: all 20 typed identities and nullable metadata/provenance.
- `independent-review.md`, `final-boundary-check.json`, `artifacts-hashes.json`: independent review and source/configuration/original-evidence integrity records.

**B2 bounded validation: PASS. Coverage remains deliberately partial. Persistent discovery remains disabled. Stop here.** Any rerun, additional page/date, TV execution, idempotency check, broader population sync or scheduling requires separate explicit authorization.
