# Daily pipeline hardening — November 10, 2026

Implementation and regression testing only. This change has not been deployed or qualified on a production run. Scheduling remains an operator-controlled step. No production records, predictions, vectors, labels or approved deployment receipts were changed by this work. Gemma 4 cloud labeling remains a separate manual capability.

The active daily path remains `pipeline_service → embeddinggemma2_migration.py daily → production_run.execute`. It includes ingestion, embedding refresh, training, scoring, validation and publication; **it is not a qualification or training-only command**. Do not invoke it to review this patch.

## Changes

| Failure boundary | Implemented behavior |
| --- | --- |
| A completed training stage survives a crash, but its connection-private training table does not | Reconstruct training rows from the saved snapshot and vectors through the same canonical builder. Require the exact original dataset hash, row count and exclusion counts before proceeding. Do not refit or overwrite the model, evaluation, dataset, dimensions or scoring artifacts. |
| An empty, partial or altered training table could be published | Save `training-materialization.json`, hash the actual stored rows during validation, then recheck before publication and inside the publication transaction while holding a training-table lock. Failure precedes rollback archival or live-table replacement. |
| A publication commits but final verification fails or its client disconnects | Recover from its durable publication/model receipt with verification only. Never hydrate, fit, score or publish again. Superseded or inconsistent receipts require operator review. New successful journals missing final verification are also eligible for this recovery. |
| A failed scheduled run is retried on every poll | Only an explicitly transient worker exit (`75`) permits a retry. Persistently count failures for the same schedule slot and enforce a delay and cap. Permanent, unknown, crashed/unclassified and exhausted failures require review. Check both before dispatch and under the existing execution lock. |
| Receipt mismatches are discovered only after expensive work | Check the existing approved source receipt, installation/control agreement and model policy before sync, collection or reconstruction. Never register or refresh an approval automatically. |
| The marker is absent or activation cannot be determined | Check control using a read-only connection. Refuse legacy fallback if an active generation exists, the control singleton is missing, a transition is present, or the lookup fails. A verified absent schema or inactive control still permits the legacy branch. |
| Context restoration consumes resources without a bounded checkpoint | Commit private restoration work in batches of 128 and retain own/global lock counts and peak process RSS in the run summary. Training integrity reads use a server-side cursor with 64-row batches. No PostgreSQL settings are changed. |

## Adversarial review corrections

The four review findings are addressed in this hardening implementation:

1. **Exact incumbent revision.** `production_run.execute()` acquires the execution lock before loading and verifying the incumbent. It pins generation, publication ID and model SHA in the journal. An unpublished resume must match all three; older saved runs lacking the pin require operator review. `promote()` requires the daily worker's pin and compares it with `production_state FOR UPDATE` inside the publication transaction, before source checking, archival or protected-table changes. Same-generation publication changes therefore fail closed. Training holds the existing execution lock, not publication-table/row locks; those are acquired only during cutover. Initial/manual generation publication retains its existing separately approved interface.
2. **Parent-run finalization.** Unexpected dispatch/controller errors best-effort finalize the parent and record a classified `controller_dispatch` failure. If that transaction fails, reconciliation can reclaim an old null-PID row only when its heartbeat is unchanged, its execution lock is free, and it has no stage/dispatch evidence. The conditional update repeats the ownership checks. A null PID with dispatch evidence might hide an unregistered live child and remains an operator hold. A controller already holding the execution lock can safely reconcile genuinely pre-dispatch rows before its duplicate-slot checks. Controller failure classification takes precedence over earlier worker/logical-stage exits.
3. **Complete daily failure boundary.** Daily connection creation, settings, Store initialization, execution and cleanup share one classified CLI boundary. Known SQLSTATEs and recognized libpq transport failures return 75; unknown uncoded `OperationalError`, contract and permanent errors return 78. A cleanup exception cannot mask the primary failure. Cleanup failure after a recorded publication/recovery returns an operator hold instead of automatically repeating completed work. No quality gate is changed.
4. **Distinct recovery outcome.** Verification-only recovery persists `summary.outcome=verification_only`; the CLI emits that outcome and `verification_only=true` and exits 76. The controller durably marks the parent and worker stage `verification_only`. This is terminal history for display/cancellation/retention, but is neither a completed schedule slot nor a failed retry attempt. The next eligible poll can perform the fresh workload. Verification-only success never launches fresh work in the recovery invocation itself. Without reliable original slot association, even a same-slot recovery conservatively does not assert fresh-slot completion. No schema change is required: existing status columns are text.

| CLI exit | Meaning | Parent outcome / schedule behavior |
| --- | --- | --- |
| 0 | Fresh daily workload completed | `success`; slot consumed |
| 75 | Classified transient failure | `failed`; existing cap/backoff applies |
| 76 | Existing publication verified only | `verification_only`; slot remains eligible |
| 78 | Permanent, contract, uncertain or unclassified failure | `failed`; operator review |

An ambiguous transition marker is never removed automatically. Both a retained dead-PID marker and a marker left by an actually SIGKILLed disposable test child block preflight before verification or pipeline work. Operator inspection/approval is required to resolve the marker, even if a database publication might have committed.

The materialization receipt binds the generation, feature contract, original dataset artifact/hash, row count, policy markers and an order-independent hash of every stored row. It includes labels, weights, numeric vectors, metadata and dependencies. Checks also reject duplicate canonical outcomes, target aliases in profile/watch dependencies, and future/unavailable watches.

The fit dataset hash retains its original float64 serialization. The separate materialization hash normalizes vectors to PostgreSQL's float32 storage and timestamps to UTC; this avoids confusing storage round-tripping with changes to fit inputs. Reconstructing an older saved run can create its missing sidecar only after proving its original dataset hash exactly. A permanent staging table cannot use this batched recovery helper.

## Model and policy invariants

Identity policy remains `verified-canonical-unseen-title/1.0`; supervision policy remains `canonical-retrospective-feedback/1.0`. The existing shared recovery resolver and all canonical target exclusions remain in use. The new generator extracts the existing text-row assembly without changing arithmetic or eligibility.

The committed-builder synthetic golden dataset hash remains:

`64fc3103e8ee1edc55f75e9702ace5e3c4ab711f70f0bee401120d13b5e36f2d`

Its numeric feature matrix and sample weights match the streamed reconstruction exactly. Text-only dimensions, vocabulary fitting, label mappings, engagement thresholds, weights, classifier settings, the 0.5 decision threshold and all existing model-quality gates are unchanged. Existing canonical production readers do not require a new staging-side receipt to serve the current model. This patch itself does not require model retraining.

Source hashing now also covers operational setting definitions in `app_settings.py`. These edits intentionally invalidate the previous writer source receipt; they do not approve a replacement receipt.

## Retry settings and recovery

| Setting | Default | Bounds | Meaning |
| --- | ---: | --- | --- |
| `pipeline.max_attempts` | 3 | 1–10 | Maximum failed scheduled attempts per slot, and maximum failed recoveries for an unpublished saved run. |
| `pipeline.retry_backoff_seconds` | 300 | 60–86,400 | Minimum time after a transient scheduled failure before another attempt. |

Environment aliases are `PIPELINE_MAX_ATTEMPTS` and `PIPELINE_RETRY_BACKOFF_SECONDS`. Adding definitions does not persist settings or enable scheduling. Worker exit `78` denotes a permanent/contract failure; unknown exit codes and missing exit codes also block automatic retry. Recognized SQLSTATE resource, serialization, deadlock, timeout and connection failures can be transient; SQLSTATE 57P01 is exercised by termination of the test's own backend. Uncoded connection refusal, timeout and transport-loss messages are explicitly recognized; other uncoded driver errors fail closed. Retries remain bounded even if a transient condition persists.

Logical progress rows have no subprocess exit code. Classification therefore prefers the `embeddinggemma2_generation` worker row over its logical-stage rows. Old failures without explicit transient classification remain blocked. Success and cancellation remain terminal for their schedule slot; existing locking, stale-worker reconciliation and retention of the current slot are preserved.

A saved unpublished run also retains failure attempts and an operator-review flag in its journal. Failed saved runs without explicit transient classification require review, including older failures. Fixing a permanent failure does not silently clear that flag. Committed-run recovery may verify its already-published receipt even when it needs operator review; it cannot start another production computation. If the database connection dies before an error can be journaled, the persisted promotion receipt determines whether commit recovery is possible. An uncertain publication is never guessed from timestamps.

Activation can catch up the current local daily/weekly slot after its nominal start time. Review that consequence before enabling scheduling. This patch does not change catch-up behavior or enable any timer.

## Regression validation

The added tests cover lost private tables after completed training, exact reconstruction without fitting/inference, older missing sidecars, count/hash/weight/label/dependency corruption, validation-to-publication mutation, empty training, and preservation of model/dataset receipts on mismatch. Real SQL tests use fictional records and connection-private PostgreSQL tables and sequences; synthetic models and a fake encoder exercise normal publication/rollback without modifying production.

Mocked orchestration covers post-commit verification failure, ambiguous commits, disconnected journals, verification-only recovery, stale receipts, early preflight rejection, retry caps/backoff across controller instances, no child launch for blocked slots, worker-versus-logical exit classification, cancellation compatibility and local-time catch-up. A pure golden test checks unchanged numeric predictors and weights. No provider request is part of these checks.

Final validation of the adversarial corrections:

- Focused offline suite: **343 passed, 33 skipped**. It includes the four corrected paths, canonical/numeric parity, application settings, pipeline scheduling/visibility and legacy guards.
- Full offline application suite: **1,062 passed, 294 skipped, 89 subtests passed** in 21.04 seconds, with one existing FastAPI/ORJSON deprecation warning. PostgreSQL/cloud test opt-ins were disabled and test authentication scopes pinned to `plexintel.read`. The successful full run used the normal runner outside the sandbox restriction that stalls TestClient setup.
- PostgreSQL-enabled materialization, text/multimodal publication/rollback and crash-recovery compatibility suite: **47 passed** in 211.40 seconds. Two subsequently added private-log SQL tests passed in **0.69 seconds**. These are 49 distinct successful compatibility checks across the two invocations; all writes were to synthetic connection-private tables. The 160-candidate tests exercised a committed 128-row prefix before interruption, mismatch and actual own-backend termination.
- During validation, the new batch tests initially patched the wrong import location, and an existing reconciliation assertion mistook a correlated stage-table subquery for a stage update. Those test issues were corrected; the final runs above passed.
- `git diff --check` passed. No production qualification, production fit, encoder/cloud request, deployment, receipt approval, scheduler change, commit or push occurred.

Reproduce the focused offline suite:

```bash
PYTHONDONTWRITEBYTECODE=1 PLEXINTEL_TEST_TEMP_DB=0 \
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' plexenv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_pipeline_hardening.py tests/test_canonical_identity.py \
  tests/test_pipeline_review_remediation.py \
  tests/test_embedding_generation*.py tests/test_training_leave_one_out.py \
  tests/test_pipeline_service.py tests/test_pipeline_scheduler.py \
  tests/test_pipeline_visibility.py tests/test_app_settings.py \
  tests/test_admin_settings_routes.py tests/test_backend_restart_guard.py
```

Separately opt in to database regression tests with `PLEXINTEL_TEST_TEMP_DB=1` for `tests/test_training_materialization_database.py`, `tests/test_embedding_generation_database.py` and `tests/test_embedding_generation_text_production.py`. They require network access to PostgreSQL but create only private test tables. Do not substitute the production daily pipeline for these tests.

Exact full offline reproduction, from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 PLEXINTEL_TEST_TEMP_DB=0 \
PLEXINTEL_LABELING_TEST_DATABASE_URL='' PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' \
PLEXINTEL_AGENT_SERVICE_SCOPES=plexintel.read \
  plexenv/bin/python -m pytest -q -p no:cacheprovider tests
```

The full suite's FastAPI TestClient requires a runner without the sandbox restriction that stalls its blocking portal. Do not interpret a sandbox stall as a test pass.

Exact isolated PostgreSQL reproduction:

```bash
PYTHONDONTWRITEBYTECODE=1 PLEXINTEL_TEST_TEMP_DB=1 \
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' \
  plexenv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_training_materialization_database.py \
  tests/test_embedding_generation_database.py \
  tests/test_embedding_generation_text_production.py
```

The `connection_loss` case calls **only** `pg_terminate_backend(pg_backend_pid())` on its own private-table test session. It deliberately loses that connection and all its temporary tables; it does not signal another PID or alter permanent records. The hard-kill test similarly kills only its own disposable subprocess, whose transition path is a pytest temporary file. All models/vectors used for fitting are synthetic fixture inputs; no production classifier is fitted or encoder contacted.

Targeted reproductions and their acceptance conditions:

| Regression | Test / expected result |
| --- | --- |
| Incumbent changes before lock acquisition | `test_incumbent_is_loaded_only_after_execution_lock`: load the new incumbent only after ownership is established. |
| Same-generation publication/model mismatch at cutover | `test_atomic_publication_rejects_exact_incumbent_mismatch_before_protected_writes`: reject both changed publication ID and changed model SHA; no archive/source hook or protected-table changes. |
| Activation failure and failed terminal update | `test_failed_activation_never_launches_child_and_finalizes_when_possible`: no child; classified failure if writable, otherwise safe orphan reconciliation. |
| Null-PID ownership race | `test_abandoned_null_pid_reconciliation_requires_old_unlocked_unchanged_owner`, `test_null_pid_with_dispatch_evidence_is_an_ambiguous_hold`: preserve live/fresh/advanced/ambiguous ownership. |
| Bootstrap/cleanup failures | `test_all_daily_bootstrap_and_cleanup_failures_are_classified`, `test_cleanup_loss_cannot_mask_permanent_primary_failure`, `test_cleanup_after_recorded_completion_cannot_automatically_repeat_work`: correct exit code, sanitized output and preserved primary failure. |
| Recovery across schedule days | `test_old_committed_recovery_is_durable_and_exposed_by_cli`, `test_recovery_only_parent_does_not_consume_fresh_slot`: exit/status 76 remains distinct and permits a later fresh workload. |
| Actual scheduler SQL | `test_predispatch_failure_and_orphan_reconciliation_use_atomic_real_sql`, `test_recovery_outcome_is_not_a_consumed_slot_or_retry_failure_in_real_sql`: conditional updates and slot/retry queries work against private PostgreSQL log tables. |
| Failure after a committed restoration batch | `test_restoration_failure_after_a_committed_128_row_batch`: 160 synthetic candidates yield more than 128 rows. Interrupt/mutate at row 129; the completed 128-row prefix remains, saved artifacts are unchanged, and a clean rerun restores the exact original hash/count. Own-backend termination produces an actual retryable driver failure after that same boundary. |
| Hard kill during publication barrier | `test_actual_killed_barrier_child_leaves_a_fail_closed_marker`: SIGKILL leaves the marker; preflight refuses work and preserves it. |

The new operational tests live in `tests/test_pipeline_review_remediation.py`; PostgreSQL cases live in `tests/test_training_materialization_database.py`. Select the listed nodes with `::test_name` to run one scenario. Existing `test_shared_stream_preserves_committed_dataset_hash_and_predictor_matrix` retains the numeric parity golden and sample-weight check.

Residual limits: these fixtures do not measure full-library lock duration, resource peaks or cross-process live cutover under real request load. The integrity scan still runs while cutover locks are held; hydration still retains complete source/checkpoint collections. November 10 lock exhaustion remains unresolved. True network failure during COMMIT, recovery of permanent journal tables across different production sessions, and rollback capacity require separately approved qualification. A missing historical incumbent pin, ambiguous null-PID dispatched worker or transition marker remains an explicit operator hold, not an automatic bypass.

## Remaining acceptance sequence

1. Review and approve this code separately from deployment. Preserve current production model/vector/prediction receipts and scheduler-disabled state.
2. Under separate deployment approval, deploy the reviewed source and explicitly register its exact receipt. Verify source/model/contract/policy compatibility and that current recommendations and explanation contexts remain available. An incorrect or absent receipt must reject a writer before source synchronization.
3. Under separate qualification approval, execute one controlled daily run with scheduling disabled. Verify complete training row/hash reconciliation, unchanged gates, canonical isolation, staged predictions/SHAP, archive/rollback checks and committed publication/model/config receipts. Observe lock/RSS telemetry through restoration and validation. An authorized interruption/resume must reuse training and leave its saved model/evaluation hashes intact; post-commit recovery must perform verification only.
4. Approve scheduler activation only after successful qualification. Verify once-per-slot execution, bounded transient retries and operator handling of permanent failure. Keep cloud labeling manual unless a separate privacy/cost/selection policy and integration are approved.

**Commit recommendation: GO for the reviewed/tested implementation. Deployment recommendation: NO-GO until separate approval and controlled qualification.** Scheduler activation remains a subsequent separately approved step. Temporary-fixture success is not a production capacity test. November 10 lock exhaustion remains an unresolved capacity/root-cause question; batching and telemetry do not prove it fixed. Historical metadata availability, retrospective-supervision assumptions, class imbalance and independent-test limitations are unchanged.
