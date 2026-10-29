# Phase 3 discovery review remediation

The two required correctness findings are fixed. Discovery remains disabled; no production database connection, migration, sync, Seerr request, acquisition action, model job or schedule change was performed. Validation used fake responses and a disposable, TCP-disabled PostgreSQL 18 cluster, which has been stopped.

**Recommendation: GO for a bounded first manual production discovery sync after the existing operator rollout gates are satisfied.** This is a code-readiness recommendation, not production execution approval or evidence of deployed behavior. Configure and verify the permanent source ID/endpoint, confirm the intended database and restricted writer grants, approve/apply the existing optional schema if absent, and inspect the read-only summary before execution. Ambiguous/pre-fix inventory requires a separately reviewed provenance/adoption procedure; do not bypass the guard by editing run history. Keep automatic synchronization inactive.

## Changes

| Files modified | Result |
| --- | --- |
| `api/services/seerr_client.py` | Validates and loads `SEERR_DISCOVERY_SOURCE_ID`; preserves nested release collection presence, nulls and invalid shapes during sanitization. |
| `api/services/seerr_discovery.py` | Requires identity for writer execution and records it in run parameters. |
| `api/db/seerr_discovery.py` | Validates the single-source binding before recovery or writes; preserves unknown release events, distinguishes SQL NULL from JSONB `[]`, replaces complete populated collections; makes refresh ordering fair. Normalizes float columns before fingerprinting. |
| `scripts/sync_seerr_discovery.py` | Rejects missing writer identity before opening a database connection. |
| `deploy/seerr-discovery.env.example` | Documents the required permanent instance ID; remains disabled, with the ID unset/commented. |
| `tests/test_seerr_discovery.py` | Adds source isolation, nested collection transitions, repeated synchronization, fingerprint stability and refresh starvation regressions. |
| `tests/replay_seerr_discovery.py` | Assigns an explicit identity to the existing captured-data fixture. |
| `docs/seerr-discovery-persistence.md` | Updates identity, release, refresh and configuration contracts. |
| `docs/seerr-discovery-remediation.md` | This findings report and reproducibility/evidence references. |

The source binding uses the existing run `source_key` endpoint hash and `parameters.source_id`. Same-instance refresh, URL trailing-slash/`/api/v1` normalization, and credential rotation preserve the binding. A changed ID or endpoint, mixed historical source keys, or conflicting canonical enrichment provenance fails before HTTP, new run insertion, interrupted-run recovery, or inventory mutations. Missing legacy identity fails as ambiguous. Regression tests compare all three discovery tables before and after rejection, including initially failed enrichment and refresh-only operations.

Unknown release collections preserve previously known events, including known-empty events. Only a complete explicit collection can replace events: `results: []`, all explicitly empty country arrays, or fully populated arrays. An unknown/malformed country collection conservatively preserves the entire previous collection, even when other countries contain events. Initial unknown events are SQL NULL; authoritative empty events are JSONB `[]`. Presence states and sanitized source snapshots retain the reason. Repeated identical refreshes do not change the canonical fingerprint or metadata change timestamp; historical run observations append intentionally. Primary release dates are not digital availability dates.

The new idempotency assertions also exposed integer/float fingerprint drift (`0` versus PostgreSQL `0.0`). Normalizing double-precision fields before hashing fixes the spurious timestamp changes without changing scoring or model inputs.

## Schema and migration implications

No schema changes, new columns, additional tables, grants or migrations are required by this remediation. Existing JSONB and nullable event columns support the corrected contract. The optional initial/rollback SQL and shared migration runner are unchanged; the optional schema remains outside startup's migration glob. There is no automatic legacy-data adoption or repair. Previously misclassified empty collections cannot be inferred reliably without reviewing source snapshots or a later explicitly authorized refresh.

## Refresh starvation

The defect was reproducible within the existing batch feature: repeated failures never advanced `last_enriched_at`, so a low-ID failure backlog could consume every bounded refresh batch forever. The minimal fix orders already eligible records by `last_enrichment_attempt_at NULLS FIRST, tmdb_id`. Cooldown, freshness, batch size and request budgets are unchanged. Tests with three titles and a batch size of two prove both never-attempted priority and rotation of permanent failures across days. No queue, scheduler or index expansion was introduced. Arrival rates above processing capacity can still grow the backlog; large-inventory query plans remain a staging measurement.

## Quantified storage growth

The fixture replay used the captured configured/all-language union: 778 canonical titles and 1,110 observations per run. Two initial replay runs succeeded; a further ten runs reused cached metadata with zero HTTP. `pg_table_size`, `pg_indexes_size` and `pg_total_relation_size` measured allocated table/TOAST/index bytes before and after the ten runs.

| Measured allocated growth | Per cached run |
| --- | ---: |
| Observation table plus TOAST/indexes | 4.251 MiB |
| Canonical table plus TOAST/indexes | 2.605 MiB |
| Run table plus indexes | 0.008 MiB |
| Total | 6.864 MiB |

The three tables grew from 16,965,632 to 88,940,544 allocated bytes; observations grew from 2,220 to 13,320. This is a short burst including update churn and free/dead space, with no `VACUUM FULL`, rather than live retained payload alone. Linear extrapolation of this sample is approximately 2.45 GiB/year for **one identical two-scope run daily**, excluding WAL and backups. It is neither a steady-state forecast nor a capacity ceiling: normal vacuum/reuse, production settings, changed metadata, new titles, wider discovery horizons and execution frequency affect growth. It supersedes the earlier review's unverified 1–2 GiB/year sizing assumption as the available physical fixture evidence.

Cached observations still copy full detail snapshots; overlapping scopes still duplicate them. No storage redesign is needed for the bounded first manual run. Before recurring operation, measure physical table/TOAST/index sizes, vacuum/reuse and WAL on the intended deployment and set a storage budget. If measured growth warrants it, review change-only immutable snapshot references while preserving every membership and audit trail. No retention/deletion or compression policy was activated.

## Validation and reproduction

Final result: **145 passed, no skips, in 4.27 seconds** across discovery, Phase 1 exploration, Phase 2 analysis and shared schema-migration tests. The discovery module contributes 79 cases, including 59 isolated database cases. The first run exposed the float fingerprint defect; its log is retained separately. The final result includes the correction. `git diff --check` and whitespace checks of modified untracked files pass. Hash verification confirms all 1,131 original protected inputs and all 1,137 pre-remediation protected files are unchanged, including the prior analysis/review evidence and protected production/model files.

From the repository root, prepare the dedicated disposable cluster exactly as documented in [the persistence guide](seerr-discovery-persistence.md#validation-and-sample-evidence), then use its explicit DSN:

```bash
export SEERR_DISCOVERY_TEST_DSN='host=/tmp/plexintel-seerr-fixture.XXX port=55483 dbname=plexintel_seerr_fixture'
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' plexenv/bin/python -m pytest -q \
  tests/test_seerr_discovery.py tests/test_seerr_exploration.py \
  tests/test_seerr_phase2.py tests/test_schema_migrations.py

# Captured-data replay only; no HTTP. Uses and resets only the guarded fixture.
plexenv/bin/python -m tests.replay_seerr_discovery

# Reproduce the physical storage sample; resets only that same guarded fixture.
plexenv/bin/python artifacts/seerr-exploration/2026-10-28-phase3-remediation/measure-storage.py
```

Stop the disposable cluster afterward using the persistence guide. The local cluster used for this delivery is already stopped. Without the explicit fixture DSN, database tests skip; that result is not equivalent to the full integration validation above. No Docker execution is required.

Private local evidence is under `artifacts/seerr-exploration/2026-10-28-phase3-remediation/`:

- `test-results.txt`: final 145-pass result; `test-results-initial.txt`: initial idempotency failure evidence.
- `captured-replay-summary.json`: two successful captured-data runs, 778 new then 778 cached titles, zero HTTP.
- `storage-measurement.json` and `measure-storage.py`: measured sizes and fixture-only reproduction utility.
- `protected-baseline.json`, `protected-verification.json`: preservation evidence.
- `fixture-cleanup.json`: stopped disposable cluster.

## Remaining risks

- Identity is assigned by the operator; a replacement server behind the same endpoint and reused ID cannot be detected from movie/discovery responses. Legitimate endpoint changes also fail closed and require a separate review.
- Unknown country collections deliberately delay partially known event updates until a complete response arrives; retained events may be older than the latest successful detail fetch.
- The production target's permissions, deployment environment, actual live networking, long-term storage/vacuum behavior and larger refresh query plans were not validated by fixture tests.
- Live discovery remains non-atomic, and primary-date windows can miss late-cataloged old titles or announcements beyond the configured horizon. These pre-existing coverage limitations remain documented.

No production synchronization was performed, and no acquisition, recommendation, training, scoring or scheduled pipeline behavior changed.
