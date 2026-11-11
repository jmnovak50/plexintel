# Restoration defect closure and real-data fit readiness

November 11, 2026, America/Chicago. Working tree: `restoration/simple-predictive-pipeline`, based on `63c116e`. This supplements the historical [acceptance report](restoration-acceptance.md). This report accompanies the reviewed correction commit. No production writes, inference requests, model publication, deployment, scheduling, schema retirement or push occurred.

## Corrections

**Production-compatible source projection.** `api/predictive/source.py` no longer selects nonexistent `watch_history.observed_at`. The actual reader succeeded in a read-only production transaction: 8,420 media, 9,949 events, 2,513 feedback records. Public storage alone supplies no established completion/observation availability for these events. The reader leaves it absent; it does not substitute `watched_at`, ingestion time, runtime or playback duration. The existing grouped-history verifier supplies independently verified starts/stops during collection. Missing availability remains unknown and cannot enter historical profiles or mature a watch-derived label. Retained verified receipts may supplement a frozen evaluation only when the stored event fields match exactly.

The PostgreSQL fixture now uses the production-compatible watch schema, without its former artificial observation column. Synthetic upstream timing is explicit replay evidence outside that table. Existing temporal cutoffs, label maturity, canonical grouping and leave-one-title-out arithmetic remain intact.

**Legacy labeling entry closed.** The admin-whitelisted `label_embeddings.py` now always delegates to `dimension_label_batch`; it has no provider executor, schema initializer, marker branch or retired-runtime import. Its harmless sample/format helpers remain for existing callers. Legacy configuration registration uses the fail-closed retired-writer guard; the web error directs operators to read-only predictor verification rather than this obsolete repair route. Architecture tests now traverse the admin subprocess allowlist as well as ordinary imports.

Every current batch execution, including manual CLI and review-worker execution, obtains the standing authorization policy and uses the existing reservation ledger. Manual work shares `daily-semantic-labeling/1`, persistent cumulative cost/request totals, per-prompt limits and fresh locked policy admission before each request. A manual per-batch budget can only lower the standing cap. Manual assessments retain `manual-batch` provenance; daily assessments retain `daily-pipeline`. Dry runs, exports and usage reports remain non-inferencing. Existing label compatibility and publication isolation rules were not changed. Historical reference functions in the retired batch implementation are not dispatched by its CLI.

**Settings reconciliation.** Relevant effective settings were read without writes. These are the actual nondefaults and their treatment:

| Setting | Configured value | Treatment |
| --- | --- | --- |
| `training.engagement_threshold` | 0.60 | Explicitly checked against the approved 0.60 label contract; the generic UI default of 0.70 is not silently substituted. |
| `scoring.shap_max_items` | 750 | Honored in global explanation targeting. As before, per-media-type mode uses the separate movie/TV/overall allocations. |
| `scoring.shap_raw_max_dims` | 40 | Applied as the raw embedding-contribution cap. |
| `scoring.shap_raw_cumabs_target` | 0.95 | Applied with the configured minimum dimension count, stopping at the cap if coverage cannot be reached. This is retained in-sample contribution coverage, not semantic validation. |
| `scoring.shap_prune_days` | 1 | No historical SHAP population exists in the accepted current-snapshot architecture: publication atomically replaces explanations. There are no older snapshots to age-prune. This historical-retention knob cannot preserve one day of previous publications without reintroducing history; no history subsystem was added. |
| `pipeline.run_time` | 07:03 | Existing scheduler/settings path remains responsible; untouched and not activated. |

The profile threshold and movie/TV waiting periods currently resolve to 0.5 / 21 / 14. They now flow into preparation and the contract instead of being discarded. Nondefault regression fixtures exercise stronger profile qualification and longer waiting periods. The existing per-media explanation policy selects movies, representatives of displayed TV shows (top-20%-episode mean), and additional overall items. Explanation selection affects neither probabilities nor recommendation ranks; tests compare those outputs directly.

Predictor settings now require a successful authoritative database read. Configured changes incompatible with this approved fixed label/weight contract fail explicitly before collection: changed 0.60 training threshold, disabled feedback/sample weighting, changed watch/candidate thresholds or changed fixed feedback weights. Supporting a different supervised policy requires separate review. No settings were altered to make these checks pass.

**Bounded memory.** Normal training checks each full dependency graph and retains its exact hash rather than all historical profile/watch links. The detailed pure-builder mode remains available for audit probes. Grouped reconstruction does the same. Numeric feature matrices are preallocated rather than assembled through a full population of Python scalar lists. Ranking retains only key/probability/cosine tuples; features are reconstructed in bounded batches for explanation targets. Vector loading, association reading and publication verification use server cursors. Vector reuse consumes old cache entries; the source reader's existing snapshot is reused for its initial drift signature. Catalog iteration retains only necessary identity/revision fields.

Association preparation retains only the serializer's first 20 unique normalized cast names, with the existing ordering and validation; it does not apply SQL truncation before deduplication. Full association values still participate in a streaming source-drift digest. Its internal format is explicitly `public-source-signature/2`; this is a source receipt change, not a numeric feature or embedding-text change. Tests change an actor beyond the serializer limit and prove that source drift is still detected while the serialized embedding input remains identical. No persistent cache, schema or staging subsystem was added.

## Real observations reconciled

The same approved frozen public records and matched retained timing/vector receipts were consumed by the shared current planner. No new fit or embedding request was used to establish these counts.

| Population | Positive | Negative | Total |
| --- | ---: | ---: | ---: |
| Complete corrected plan | 8,475 | 827 | 9,302 |
| Chronological fit | 4,585 | 678 | 5,263 |
| Chronological validation | 1,726 | 135 | 1,861 |
| Show-held-out fit | 3,791 | 557 | 4,348 |
| Show-held-out validation | 432 | 31 | 463 |

There are zero duplicate user/canonical-title outcomes. At the incumbent cutoff all 9,301 outcomes reconcile with stored labels and sample weights, with zero missing identities or label/weight mismatches. One subsequent positive feedback observation explains 9,302 instead of 9,301; counts were not forced to match.

Current observation/source populations: 7,008 first-recorded-watch outcomes; 2,136 retrospective declarations (2,135 watched-like and one watched-dislike); 158 pre-viewing rejections. Exclusions: eight unresolved identities, 553 outside label policy, 42 without sufficient prior history. The 211 recorded-watch feedback records are auxiliary evidence, not 211 additional lost outcomes. The grouped split loses another six observations for profile support. The chronological boundary remains `2026-03-16T04:14:10+00:00`; 2,178 earlier observations have labels not mature before that boundary.

Retrospective declarations use submission as their observation cutoff and the later of creation/modification as label availability; actual first-viewing dates remain unknown. The historical metadata/revision limitations and repeated-validation limitations remain. Historical split-model metrics and saved incumbent all-data scores in the earlier acceptance report are **not results of a newly trained restored model**.

## Regression evidence

Final focused suite: **259 passed in 42.35 seconds**, including real temporary PostgreSQL checks. Full offline suite: **1,195 passed, 328 skipped, 89 subtests passed in 25.40 seconds**; one existing FastAPI response deprecation warning. Optional SQL/integration skips in the offline run are distinct from the focused SQL checks above. `git diff --check` passed. The focused PostgreSQL suite covers actual-schema source reading, publication/repeat vector reuse, rollback after more than 128 staged rows, source/incumbent drift, physical vector mismatch, genuine backend loss at/after commit, last-good restoration, canonical aliases, retrospective feedback timestamps, settings, strict authorization, revocations, budget reductions, policy races, restart-persistent accounting, compatible label reuse and mocked authorized provider behavior. No real cloud request occurred.

The new compact-row tests compare exact numeric matrices, labels, weights, `watch_sim` and complete dependency hashes with detailed assembly. Existing real-pattern alias fixtures remain anonymized. The expanded architectural closure test finds no active retired-schema/runtime dependency, including admin subprocess entry points. Retained real-data feature sampling from the acceptance report remains bounded evidence, not exhaustive feature reconstruction.

Initial failures were investigated and resolved: compact output was initially applied to the detailed audit API (restored as its default, with compact mode explicit in production preparation); intentional manual SQL batch fixtures initially lacked the newly required standing authorization (now supply a synthetic coherent policy while exercising the actual ledger). One interim connection-loss test encountered the source-change publication guard while application edits were still occurring; its isolated rerun passed. Final source was held fixed for the final regression runs.

Reproduce offline from this worktree, using the shared virtual environment and no production DB destination:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
DATABASE_URL='postgresql:///postgres?host=/tmp/nonexistent' \
SESSION_COOKIE_SECURE=true SESSION_SECRET=synthetic-offline-session-key \
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' PLEXINTEL_AGENT_SERVICE_SCOPES=plexintel.read \
/home/jmnovak/projects/plexintel/plexenv/bin/python -m pytest -q -p no:cacheprovider tests
```

Temporary PostgreSQL checks use the existing disposable PostgreSQL 18 + pgvector cluster, Unix socket `/tmp/plexintel-restoration-pg-Ak2JfR/socket`, port 55439, no TCP, 64 MiB shared buffers, 4 MiB work memory, 12 connections. Each predictor test creates/drops its own database; labeling tests use isolated schemas/temp relations. The cluster is stopped after testing. Never substitute a production DSN.

```bash
export DATABASE_URL='postgresql:///postgres?host=/tmp/plexintel-restoration-pg-Ak2JfR/socket&port=55439'
export PLEXINTEL_RESTORATION_TEST_DSN="$DATABASE_URL"
export PLEXINTEL_LABELING_TEST_DATABASE_URL="$DATABASE_URL"
export PLEXINTEL_TEST_TEMP_DB=1
# Preserve the offline environment flags above.
/home/jmnovak/projects/plexintel/plexenv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_predictive_publication.py tests/test_predictive_restoration_fixes.py \
  tests/test_predictive_identity.py tests/test_predictive_architecture.py \
  tests/test_labeling_policy.py tests/test_pipeline_labeling.py \
  tests/test_semantic_labeling.py tests/test_dimension_label_export.py
```

## Smallest safe real-data fit path

No complete real-data fit was admitted. The initial ten-sample preflight measured minimum available memory of 3,245,376 KiB against an unchanged 20% host reserve of 3,321,513 KiB: already 76,137 KiB below reserve. After stopping the disposable test cluster, another ten-sample admission check measured 3,596,752 KiB available, leaving 275,239 KiB above reserve, short of the 1,048,576 KiB worker allowance. Both returned HOLD. A transient higher reading does not provide a reliable worker allocation. The bounded metadata reconciliation peaked at 286,208 KiB RSS; that is **not** a full-fit peak or a before/after benchmark.

Prepared private artifact-only procedure: `.secrets/restoration-acceptance/isolated_fit.py`. Admission only ran; its fit worker did not run. It reuses the existing retained source/hash validator and physical vectors, uses the shared compact feature assembly and unchanged three-fit training/evaluation functions, persists only isolated model/report files, and has no production writer or embedding/provider invocation. No disposable production-sized database or upstream ingestion replay is needed. The worker branch is prepared and syntax checked, but has not been execution-qualified on all real rows.

Provisional worker allowance is 1 GiB RSS, with a 1.5 GiB address-space ceiling and the existing two XGBoost threads. This bounds a proposed execution; it is not a measured guarantee. The conservative budget accommodates the measured scalar/receipt analysis, about 57 MiB for the dense final feature matrix, vector/profile arrays, grouped rows and native fitting allocations. The latter still require measurement. Admission requires at least 4,370,089 KiB (about 4.17 GiB) available while preserving the 20% reserve. The parent stops the worker if its RSS allowance or host reserve is breached. No swap-backed fit or relaxed reserve was attempted.

After sufficient headroom exists, from this worktree:

```bash
PYTHONDONTWRITEBYTECODE=1 /home/jmnovak/projects/plexintel/plexenv/bin/python \
  .secrets/restoration-acceptance/isolated_fit.py
# Only after admission is GO, execute the bounded, isolated fits:
PYTHONDONTWRITEBYTECODE=1 /home/jmnovak/projects/plexintel/plexenv/bin/python \
  .secrets/restoration-acceptance/isolated_fit.py --execute
```

The isolated evaluation records chronological/show-held-out class performance, calibration, ranking limitations, SHAP group contributions, dataset/model hashes and software/source settings. The final all-data fit has no independent held-out accuracy score. After a successful fit, complete bounded representative-user top-20 and saved-incumbent comparisons on identical candidate populations, including probability concentration and show/movie diversity. Do not infer relevance from SHAP, retrospective fit quality or rank similarity. No diversity caps, threshold search or hyperparameter adjustment is part of this procedure.

The approximately 33-minute historical runtime reference and 40-minute daily qualification limit remain unchanged and unmeasured for this corrected implementation. Source/API latency, complete real fit resource use and operational publication timing remain qualification work, not defects proven by this assessment.

Decision: **GO for review of the corrected implementation; HOLD for executing a full real-data fit on current host headroom; NO-GO for production qualification/promotion until the real fit, common-candidate analysis and operational acceptance pass.** This is not authorization to deploy, publish, schedule or issue cloud requests.

Private evidence is under `.secrets/restoration-acceptance/`: `fixed-source-schema-validation.json`, `effective-policy.json`, `fixed-policy-reconciliation.json`, `fixed-fit-resource-admission.json` and the prior pinned vector/feature receipts. Test logs are `/tmp/plexintel-restoration-focused.log` and `/tmp/plexintel-restoration-offline.log`. Private input/user manifests are not committed or printed in this report.

## Focused pre-commit review

The same assistant performed a separate correctness pass over the actual diffs, surrounding source/recovery code, provider reservation boundaries and the regression assertions. This is not an external independent audit. No material correctness issue was found in the corrections. The review specifically checked raw-versus-enriched source signatures, cursor lifetime across transactions, exact compact dependency hashes, canonical watch exclusion, unchanged numeric matrix construction, explanation-only selection changes, manual assessment provenance and fresh authorization on every provider reservation. Fresh focused review regressions passed: 137 passed, 22 optional SQL checks skipped; the prior final disposable-PostgreSQL suite passed all 259 checks. A fresh full offline result is recorded in the commit validation below.

Code review acceptance concerns implementation correctness. The reconciled 9,302 observations establish confidence in preparation, not in predictive accuracy. The next work is exclusively isolated real-data fitting and prediction analysis, with negative-class limitations and episode concentration explicitly assessed. No perfect-prediction standard, architecture expansion or new model features are proposed.

Commit validation: the fresh full offline suite passed **1,195 tests**, with **328 skips**, **89 passed subtests**, and the existing deprecation warning in **23.12 seconds**. `git diff --check` passed. The focused review found no new material defect; commit on the restoration branch is GO. This does not qualify production deployment or establish prediction quality.
