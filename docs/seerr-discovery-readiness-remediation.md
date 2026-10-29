# Seerr discovery readiness remediation

**Current production status — October 28, 2026, 20:51 CDT:** Gate A completed: migration **002 committed**, strict V2 verification **PASS**, inventory empty, discovery **disabled**. See [Gate A verification](seerr-discovery-gate-a-verification.md). Earlier V1/preflight statements below are historical; do not rerun 001/002 or proceed to Gate B without separate authorization.

## Assessment

**CONDITIONAL GO for separately authorizing a V2 rollout and bounded synchronization.** No remaining correctness blocker was identified in the remediated scenarios. **Movies: GO on isolated correctness evidence. TV: GO under the conservative premiere-evidence contract below.** Current production still requires separately approved migration 002 and post-install verification before this runtime can synchronize. This is not authorization to migrate, enable or synchronize.

The final focused suite passed **271 tests**, including **58 new remediation regressions**; original movie regressions and captured replay remain compatible. A separate reviewer challenged the implementation and independently reproduced the TV corrections. No production database mutation, migration, synchronization, Seerr request/dry-run, scheduling, acquisition, model/scoring/recommendation change, credential/privilege change, service restart, commit or deployment was performed.

## Findings: exact changes

| Finding and source | Before | After |
| --- | --- | --- |
| Runtime contract — `api/db/seerr_discovery.py:require_unified_schema` | Table names and six column names could accept incomplete V2, missing keys or wrong types; HTTP/run writes could precede failure. | PostgreSQL catalogs validate three ordinary tables, all 68 columns/types/nullability/defaults/identity, 24 core constraints with exact PK/FK/uniqueness/check definitions and flags, constraint-index validity, identity-sequence generation/dependency, active FK triggers and origin replication mode. Rejects mixed/V1/partial states, unexpected unique indexes (including ones referenced by external FKs), RLS and user triggers. Runs before recovery/run insertion/HTTP; summary uses the same guard. No repair/bootstrap. |
| Season completeness — `api/services/seerr_client.py:tv_eligibility` | A nonempty nonspecial type, or any positive season number, could make incomplete series eligible. | Missing/null/malformed/empty seasons, missing Season 1, or unknown/invalid Season 1 date remain provisional. Eligible requires original premiere in scope plus a valid matching Season 1 premiere and no conflicting evidence. No engagement threshold or acquisition score. |
| Date evidence — client sanitizer, classifier, repository `metadata_values`/`_eligibility`, service `assess` | Season dates were discarded; summary/detail date differences did not affect classification. | Sanitized seasons retain native `airDate` and omitted/null/value/invalid state. `tv_metadata.season_premieres` and per-observation source snapshots retain evidence and source/fetch provenance. Date contradictions receive provisional diagnostics; each scope compares its own summary on fetch and cache reuse. |
| Missing summary premiere — `api/services/seerr_discovery.py:collect_scope` | Provisional diagnostic was placed in excluded pagination and the title was skipped without detail. | Valid typed IDs persist provisionally and receive bounded detail enrichment. `pagination.unresolved` preserves the initial diagnostic; detail can resolve it to eligible, leave it provisional, or establish exclusion. A failed detail call retains the candidate with partial-run accounting. |

A missing/null/invalid season collection preserves prior canonical season dates; explicit `[]` clears them. New snapshots preserve field uncertainty. Repeated identical date responses preserve fingerprints/change timestamps. Classification uses the observation's evidence rather than assuming retained canonical values were newly observed. Cache reuse retains original fetch age. Generic retrieval success is independent of whether every TV title has resolved eligibility.

## Final TV decision matrix

| Evidence | Actual result after remediation |
| --- | --- |
| Season 1 date matches original premiere inside scope | Eligible, unless other evidence contradicts it |
| Announced future original date, incomplete season evidence | Provisional; retained |
| Announced future date and matching dated Season 1 | Eligible within the explicit future scope |
| Missing/malformed summary original date | Persist, enrich, preserve unresolved diagnostic; detail determines outcome |
| Original date still unknown after detail | Provisional; no date inferred from seasons/episodes |
| Missing/null/malformed/empty seasons or Season 2 without Season 1 | Provisional despite nonempty type |
| Valid old original premiere and old Season 1, recent Season 2/episode | Excluded from a current new-series window |
| Recent original date but Season 1 dated 2019 | Provisional `season_premiere_conflict`, with both dates retained |
| Later season predates original/earlier season, or duplicate season numbers | Provisional conflict diagnostic |
| Summary and detail original dates disagree | Provisional `summary_detail_premiere_conflict`, even if both fit scope |
| Premiere and matching Season 1 inside an explicitly historical window | Eligible; late discovery allowed |
| Episode/season result instead of series | Invalid typed discovery row, not a new-series candidate; incomplete page accounting |
| Explicit TV special / nonempty season-0-only collection | Existing explicit-special/specials-only exclusions retained |
| Unknown library/request status | Preserved independently; does not force eligibility/exclusion |

Exact date agreement is deliberately conservative: regional/date-source differences can leave legitimate series provisional. Incomplete announcements are retained for later normal refresh, without guessing their eligibility. A dated Season 1 is supporting evidence, not proof of digital availability. Multiple seasons do not themselves disqualify a genuinely new original premiere. The existing specials-only heuristic remains a documented upstream-classification limitation, not a new engagement rule.

## Compatibility and schema implications

**Migrations 001, 002 and the original rollback SQL are unchanged. No new migration, column, table, schedule or data backfill was introduced.** Season dates fit the existing targeted TV JSONB extension and observation snapshots. `(media_type, tmdb_id)` remains the canonical, observation, enrichment/cache and refresh identity. Golden movie sanitization/fingerprint and populated-V1 migration tests remain intact; same-ID movie/TV records coexist without metadata crossover.

The runtime contract is intentionally strict and PostgreSQL-18-tested. Benign nonunique reporting indexes are allowed; changed columns/defaults/constraints require review rather than silent adoption. This is validation of the existing schema, not a second migration framework. Older cached TV snapshots without season dates become provisional until normal detail refresh; they are not reclassified as eligible from retained values. Movie behavior is unchanged apart from the required stronger shared schema validation.

During the preceding review, authorized read-only production checks on **October 28 at 20:06 CDT** confirmed `192.168.1.9:5432 / plexintel / jmnovak`, PostgreSQL 18.6, V1 present, V2 absent, and **0 runs / 0 movies / 0 observations**, with no discovery advisory lock or active discovery session observed. The effective URL matched the host backend. Discovery configuration loaded disabled with the approved source identity. Those are time-specific pre-remediation observations, not a new live-sync or production compatibility test of this remediation. No further production connection was needed for the fixes.

The accepted temporary **`jmnovak` superuser exception** remains unchanged; the connection is not least-privileged. The preceding review re-read the validated archive fully and verified SHA-256 `8754923a28ed13c140cb269e59b2389786e4d653e6cfbfcf14bb46fb06d52f1a`. It predates V1 and V2. Prior consistent restore evidence remains PASS for 40 table counts; no new restore was performed. PostgreSQL/extension binaries, role prerequisites, host/application files and lack of PITR remain documented recovery limitations.

## Validation and reproducibility

Private ignored evidence: `artifacts/seerr-exploration/2026-10-28-readiness-remediation/`.

- `focused-suite.txt`: **271 passed, no skips** — 79 original discovery, 68 updated unified, 58 remediation, 66 exploration/Phase 2/schema-runner cases.
- `captured-movie-replay.json`: **778 new/enriched movies**, then **778 cached**, zero updates; both success, **zero HTTP**.
- `synthetic-unified-replay.json`: **six typed titles** (one movie, five TV, including ID collision and resolved missing-summary date); TV **two eligible, two provisional, one excluded**; repeat six cached, zero new/updated; both success, **zero HTTP**.
- Schema tests cover missing tables, view impersonation, six-column partial V1 spoof, wrong column types/defaults, missing/weakened/unvalidated constraints, untyped PK/unique indexes, external-FK index masking, missing/altered identity sequence, disabled FK triggers, replication mode and RLS. Rejection preserves running records without recovery, inserts no run and calls no HTTP. A correctly migrated V2 succeeds; read-only validation restores caller search path.
- TV tests cover incomplete seasons with/without type, future announcements, invalid/missing Season 1 dates, established-series returning seasons, chronological/duplicate/summary-detail conflicts, cached assessment, date provenance/idempotency and missing-summary resolution/failure.
- Existing migration tests still cover empty/populated V1, preserved provenance/history/hash/timestamps, identity collision, drift rejection, atomic late-failure rollback and already-upgraded rejection.

Use the existing guarded disposable-cluster setup in [the persistence guide](seerr-discovery-persistence.md#validation-and-sample-evidence), then:

```bash
# Dedicated disposable Unix-socket-only cluster; never set this to production.
export SEERR_DISCOVERY_TEST_DSN='host=/tmp/plexintel-seerr-fixture.XXX port=55484 dbname=plexintel_seerr_fixture'
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' plexenv/bin/python -m pytest -q \
  tests/test_seerr_discovery.py tests/test_seerr_unified_discovery.py \
  tests/test_seerr_readiness_remediation.py tests/test_seerr_exploration.py \
  tests/test_seerr_phase2.py tests/test_schema_migrations.py
plexenv/bin/python -m tests.replay_seerr_discovery
plexenv/bin/python -m tests.replay_seerr_unified_discovery
```

Replays reset only the verified disposable fixture. Captured movie replay needs existing private Phase 1 data; synthetic replay is self-contained. The test cluster was stopped and removed after verification.

## Independent assessment and remaining conditions

The separately authorized reviewer used read-only source inspection and pure local reproductions. It confirmed the season/date/missing-summary corrections, and found additional unique-index/FK-trigger bypasses that were fixed and regression-tested. Final assessment is preserved in `independent-review.md`; no remaining correctness blocker in the requested scenarios.

**Movie synchronization:** GO for code correctness and preserved captured-data compatibility. **TV synchronization:** GO for the documented conservative classification, retaining unresolved candidates. **Current production execution:** blocked until separately authorized migration 002, exact post-install catalog/inventory/source verification, and explicit bounded first-sync approval. Neither fixture success nor eligible classification authorizes acquisition.

Before rollout, reconfirm target/current V1 state, disabled configuration, migration checksum, activity/locks and recovery integrity. After an approved atomic 002 transaction, verify catalogs plus the real runtime guard and unchanged pre-upgrade counts/provenance; remain disabled if verification fails. Nondestructive recovery is retaining V2 disabled, not running the V1-only rollback. No backend restart is needed merely to run the manual host CLI; deploying a different code revision is separately controlled.

For a future separately approved smoke test, use one one-day movie scope and one one-day TV scope, one page each, zero retries, bounded timeout/spacing and one **25-attempt combined invocation budget**. Explicitly approve that movies are enriched first and the cap may defer TV; alternatively use separate diagnostic runs with a clearly approved total budget rather than multiplying it implicitly. Expect auditable partial results when more pages exist; never expand automatically to force success. Follow with read-only typed inventory/observation/provenance and eligibility review. No such command was run or enabled here.

Remaining operational limitations: deployed Seerr response compatibility/authentication has not been exercised; upstream dates/classifications may be incomplete or wrong; exact-date comparison can increase provisional counts; retained discovery/observation history grows without a new retention policy. None is represented as verified production behavior.

Modified existing files: the three discovery Python modules, `tests/test_seerr_unified_discovery.py`, `tests/replay_seerr_unified_discovery.py`, `docs/seerr-discovery-persistence.md`, and `docs/seerr-unified-discovery.md`. New files: `tests/test_seerr_readiness_remediation.py` and this report. Private evidence is separate. Unrelated production/model/workflow files and all migration SQL remain unchanged.
