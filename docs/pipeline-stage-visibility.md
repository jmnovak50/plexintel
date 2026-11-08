# Pipeline stage visibility after Gemma 2

## Production investigation — November 8, 2026

The latest manual web run is **326**, November 7 **09:28:09–10:06:31 CST**
(38 minutes 22 seconds), exit code 0 and status `success`. Its final stdout receipt
links it unambiguously to production run
`45143c11-afbc-4edf-ac3e-e1a72fd67b30`, encoder generation
`782a70b2-6be2-4948-88ce-53495153df49`, publication
`bc5a097d-bc87-4b00-aba1-74e6a040f305` and classifier SHA256
`8101467369399c7a6c62d486a94887f0cb3c0c646d52a0f4c60ae0980f06f519`.
The canonical production state still identifies that publication/model. Database
population checks agree with its journal. No run was executed to investigate this.

| Work actually executed | Recorded seconds | Outcome |
|---|---:|---|
| Incremental Tautulli/library sync | 131.85 | 4 new media identities, 19 new history events |
| Snapshot/working context | 119.43 | Existing compatible vectors hydrated; no new permanent generation |
| Rich metadata preparation | 122.18 | Canonical input changes checked |
| Media-text inference | 113.06 | 4 new + 224 regenerated; 8,186 reused; total 8,414 |
| Watch-text inference | 139.27 | 16 new + 253 regenerated; 9,357 reused; total 9,626 |
| User profiles | 8.64 | 18 rebuilt, 13 reused; total 31 |
| Historical training data, model fitting and evaluation | 501.10 combined | 9,303 rows; 533 label-policy exclusions, 42 limited-history exclusions |
| Scoring and SHAP | 883.52 combined | 224,330 recommendations, 31 users, zero limited-history scoring skips |
| Pre-publication vector/provenance validation | 19.56 | All required populations complete, zero failed/pending |
| Atomic publication | Not separately measured | Committed; current canonical publication matches receipt |
| Separate final verification after commit | Not recorded | Did not exist in that orchestration |

Quality gates passed: chronological balanced accuracy **0.5771**, AP **0.9712**;
show-heldout balanced accuracy **0.6495**. Production holds 930,000 SHAP contribution
rows and 23,250 explanation contexts. Of 19 new watch events, 16 were library-linked
and three joined quarantine: **277 events for the same 153 absent titles** remain
preserved. Poster inference was zero. The layout remains all 768 media-text axes
followed by all 768 semantic-user axes, plus engineered features.

The old `production_runs.finished_at` is transaction-start `now()` inside the
publication transaction, not the observed commit end. Do not use its difference
from `created_at` as complete wall time; the web run's completion is authoritative
for this investigation. No separate dataset/SHAP/publication durations can be
recovered honestly from this journal.

## Root cause and before/after comparison

Commit `00a420c` changed `build_pipeline_stages()` in
`api/services/pipeline_service.py` to return one
`embeddinggemma2_generation` subprocess whenever an encoder generation is active.
That safely retained a single lock and coordinated transaction, but created just
one `public.pipeline_run_stages` record. The text-only migration continued using
that dispatch. The CLI emits internal JSON progress and durable production-run
checkpoints; the web monitor neither consumed those events nor joined the journal.
`AdminPipeline.tsx` displayed only the stored subprocess rows and raw output tails.

Previous web run 325 exposes eight separate legacy subprocess stages:
`tautulli_incremental`, `library_embeddings`, `watch_embeddings`, `user_embeddings`,
`training_data`, `train_model`, `score_model`, `batch_label`. All eight succeeded.
Gemma 2 run 326 performed its supported production stages but lost this monitoring
granularity. It did not silently skip ingestion, profiles, training or SHAP.

Semantic dimension labeling **was intentionally retired**, not accidentally
replaced by SHAP. The existing migration document's artifact/label section and
legacy writer guards explicitly block the old semantic labeler for the new space.
The configured `pipeline.labeling_enabled` remains true, but applies only to the
inactive legacy branch. Current semantic label tables are empty by design. Raw
feature identities, dimension groups and SHAP remain available. This fix displays
that policy explicitly and does not invoke the old labeler or transfer old labels.

## Implemented monitoring contract

One worker, one shared execution lock and the existing subprocess/process-group
cancellation mechanism remain. New versioned JSON events
`plexintel.pipeline-stage/1` describe these ten logical stages:

1. Tautulli/library synchronization.
2. Media-text refresh, including working context and metadata preparation.
3. Watch-text refresh.
4. User-profile reconstruction.
5. Leakage-safe training data preparation.
6. Model fitting and chronological/show-heldout quality validation.
7. Recommendation feature construction, prediction and ranking.
8. SHAP computation and persistence of staged prediction rows.
9. Vector validation, rollback archival and atomic production publication.
10. Read-only verification of the committed physical vectors, classifier and explanation configuration.

Scoring and SHAP retain their existing per-user interleaving. Disjoint measured
spans accumulate separately; paused stages do not accrue another stage's time.
No ranking, label, weighting, model-feature or encoder contract changes are made.
A private-SQL parity test compares all predictions/ranks/SHAP with and without the
observer and requires exact equality.

The parent reads the disk-backed stdout using `os.pread`, which cannot move the
file offset shared with the writing child. Input buffering, line sizes and event
payloads are bounded; partial UTF-8, malformed/noise lines and oversized lines are
handled without treating them as stage success. Complete stdout/stderr still go
to the existing pipeline log. The poll/cancel/heartbeat loop retains its child PID
and reports the active logical key. Scoring-refresh indicators cover scoring,
SHAP, publication and final verification.

Live stage rows use the existing `pipeline_run_stages` table. A tagged, bounded
JSON payload in `stdout_tail` contains metrics and elapsed time; no schema migration
is required. Counts distinguish inferred/new/regenerated/rebuilt/reused work,
checkpoint reuse, failures, training exclusions, users/predictions, SHAP coverage,
quality metrics and final verification. Only allowlisted numeric metrics enter
structured events; user identities and source metadata are not copied into them.
Future run journals retain the measured stage details and total wall time.

A cancellation marks the active observed stage cancelled and unreached stages
skipped. If a worker exits successfully without complete observations, missing
stages are `not_recorded`, never fabricated successes. Observation failures are
logged and do not strand the child or disable cancellation. The original outer
worker row and output remain inspectable. A failed post-publication verification
is visible as a failed final stage; the committed publication receipt remains
available for operator recovery.

## Historical compatibility

`pipeline_visibility.enrich_runs()` adds optional `stage_details` to list/detail
API responses without changing original `stages` records. An exact UUID from a
stored receipt identifies a production journal; timestamps are never used to guess
a match. Historical combined timings are labeled as such. Missing independent
SHAP/dataset times and post-commit verification remain explicit unknowns. Runs
without receipts retain their original logs and an availability note. Legacy
multi-subprocess runs retain their existing stages.

`AdminPipeline.tsx` renders readable names, statuses, durations, metrics, policy
notes and expandable stage/worker logs. Existing trigger, cancel, purge and polling
controls remain. There is no new labeling action or poster workload.

## Validation and deployment

The implementation was deployed after explicit operator approval for the
visibility-only backend/frontend deployment and backend restart. Automatic
approval review initially rejected deployment because the original authorization
covered code/tests only; no deployment action executed on that rejected attempt.
The operator then approved the concrete deployment, restart and receipt refresh.

- Application regression: **770 passed, 256 skipped, 89 subtests passed**, one
  existing FastAPI/ORJSON warning, 17.34 seconds.
- Focused pipeline/observer/production-contract suite with real, connection-private
  PostgreSQL fixtures: **65 passed**, 30.75 seconds. Includes synthetic subprocess
  observation/cancellation, exact prediction/rank/SHAP parity, resume, publication
  and rollback tests. No production pipeline or production classifier fit occurs
  in these fixtures.
- Frontend presentation: **4 tests passed**, including historical unknown timings,
  metric formatting, ten-stage names and active/paused duration handling.
- TypeScript passed; Vite built 1,761 modules successfully. The existing
  Browserslist age warning was retained; no dependencies were installed.
- Read-only integration against real run 326 produced ten logical stage details,
  exact recorded counts and explicit combined/unknown durations.
- Live authenticated list/detail API checks passed after deployment: run 326 has
  ten projected stages; run 325 retains all eight legacy stages. Original run 326
  still has its one stored worker record, unchanged; no history rewrite occurred.
- Live admin status reports the unchanged model/publication. Unauthorized pipeline
  access is rejected. The `/admin/pipeline` and Dimension Explorer SPA routes and
  served JS/CSS checksums passed. There was no interactive browser engine; these
  are HTTP, build and formatter checks, not a visual browser-automation claim.
- All **18,071 production vectors** (8,414 media, 9,626 watch, 31 user) passed
  read-only canonical native-hash/provenance verification during acceptance.

Deployed code receipt:
`5102c3598aa00ef1e36c5de897964d55ff3954447731c9f8338de5be2ff936b1`.
Only `embedding_v2.control.deployed_code_sha256` was refreshed, conditionally on the
unchanged model/publication and previous verified code receipt. This is code
deployment metadata, not a generation/model publication. Semantic encoder/input
hashes are unchanged, so existing embeddings are not invalidated.

The shared pipeline lock protected deployment. Only the PlexIntel backend was
restarted; Ollama and Plex were not restarted. Pipeline run count remains **3**,
the latest run remains **326**, and scheduling remains **disabled**. No production
pipeline, model cutover, embedding refresh, labeling or poster inference was run.
Final backend health: active, PID **74474**, automatic restart count **0**.
Future live streaming has been tested with synthetic subprocesses/private tables;
it will be exercised by the next independently authorized real pipeline run.

Private deployment evidence and verified prior source/UI rollback copies:
`artifacts/embeddinggemma2/deployment-backups/pipeline-visibility-20261108T173649Z/`.
The deployment helper compares publication, classifier hash, vector/prediction/
SHAP populations, scheduling and run counts before/after, verifies a fresh
authenticated receipt, and has a prior-runtime/UI restoration path on failure.
No rollback was needed. No commit or push was performed.

An unrestricted pytest invocation also collected unrelated archived operational
scripts and vendored projects lacking their own dependencies; acceptance uses
the project application `tests/` suite. An inherited service-scope environment
setting was isolated to fixture defaults for regression execution; production
authentication settings were not changed.

## Code references

- [pipeline_service.py:822](../api/services/pipeline_service.py#L822): `build_pipeline_stages()`,
  `PipelineStageObserver`, `_run_stage_process()`, scoring-refresh status,
  `get_pipeline_runs()` and `get_pipeline_run()`.
- [progress.py:40](../api/embedding_generation/progress.py#L40): `Reporter`, `EventReader` and the
  versioned ten-stage contract.
- [production_run.py:152](../api/embedding_generation/production_run.py#L152): `execute()` stage boundaries,
  checkpoint/reuse counts, quality checks, publication and final verification.
- [text_production.py:119](../api/embedding_generation/text_production.py#L119): `train_text()` separates dataset
  preparation from fitting without changing either feature contract.
- [model.py:286](../api/embedding_generation/model.py#L286): `score()` measures its existing scoring and
  SHAP work separately while preserving all predictions and contribution values.
- `scripts/embeddinggemma2_migration.py`: `daily()` retains old summary fields and
  additionally reports complete wall time and the labeling policy.
- [pipeline_visibility.py:19](../api/services/pipeline_visibility.py#L19): `historical_details()` and `enrich_runs()`
  perform read-only exact-receipt projection; no timestamp inference/backfill.
- `api/routes/pipeline_admin_routes.py`: optional stage-detail serialization.
- `frontend/src/pages/AdminPipeline.tsx` and `frontend/src/utils/pipelineStages.ts`:
  readable stage cards, metrics, durations and preserved original worker logs.
- `tests/test_pipeline_visibility.py`, `tests/test_pipeline_service.py`,
  `tests/test_embedding_generation_text_production.py` and
  `frontend/tests/pipelineStages.test.mjs`: observation/compatibility coverage.
