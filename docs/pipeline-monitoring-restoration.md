# Monitoring restoration regression

This records the first, data-focused correction. Its visual restoration claim
was rejected by the operator. See [the visual follow-up](pipeline-monitoring-visual-restoration.md)
for the clarified target, browser evidence and replacement presentation.

Compared archived serving commit `3ffaa68` with restored deployment `d37bbaa`.
The frontend page and pipeline route serializers were identical between these
commits. The regression spans the worker's emitted evidence, backend presentation
adapter, and frontend assumptions about the worker name and stage vocabulary.

| Capability | Restoration regression | Correction |
| --- | --- | --- |
| Original eight-stage run history | Enrichment selected only names shared with logical stages, hiding other legacy stages | Enrich only runs with an actual single-worker carrier; preserve all original legacy rows |
| Worker stdout/stderr | Frontend selected only `embeddinggemma2_generation`, hiding `predictive_daily` output | Show either worker; translate structured progress to readable logs and retain expandable raw output |
| Training progress | Worker discarded textual `phase` callbacks through the numeric metric allowlist | Forward bounded operational phase messages, including boosting rounds |
| Active stage completion and timing | Preparation stages stayed started until all preparation finished, did not tick during work, and emitted thousands of updates | Emit phase starts before work, finish on existing measured-duration callbacks, throttle progress while retaining latest counts |
| Quality and exclusion metrics | Available in final report but omitted from structured events | Emit existing evaluation, exclusion and SHAP aggregates; recover existing run-specific reports |
| SHAP timing | Restored worker recorded a zero although SHAP was measured within scoring | Explicit unknown separate duration; scoring explains the combined timing |
| Optional labeling | Restored stage initialized but never reported, even when explicitly skipped | Report the existing terminal outcome; recover historical skipped outcomes from the receipt |
| Source diagnostics | Collector stdout/stderr redirected to `/dev/null` | Inherit the existing retained worker streams |
| Historical enrichment | Removed retired private-journal queries without a replacement for retained evidence | Use public structured rows and bounded final JSON receipts from the exact run's existing worker log |

No database migration, history rewrite, retired journal query, `embedding_v2`
dependency, lifecycle reactivation, model/embedding change, training-policy change,
or scheduler change is needed. Preparation/model/scoring computations remain in
their original order; the preparation additions are progress callbacks only.
Original `stages` records are preserved; optional `stage_details` remains the API
presentation contract. `timing_known: false` prevents timestamp fallbacks from
fabricating separately measured durations. Numeric metrics remain allowlisted.

Read-only recovery reads at most 256 KiB from one exact per-run worker stdout
file, or uses a complete receipt already retained in the database tail. Missing,
rotated or ambiguous files produce no guessed report. It never substitutes the
latest evaluation, current model metrics, timestamps, or another run's data.
Raw file contents are not added to API responses; only allowlisted aggregates and
recorded status/reason/publication fields supplement existing stage records.

## Historical evidence and limits

Read-only inspection of all 11 retained executions confirmed:

- Runs 324 and 325 retain all eight original stages.
- Run 326's complete stdout receipt recovers ten logical stage summaries and
  their available measured/combined durations without its retired journal.
- Interrupted/failed runs 327, 328 and 331 retain recorded success/failure/skip
  outcomes. Runs 329, 330 and 332 retain their ten recorded logical stages.
- Restored runs 333 and 334 retain eleven stage records. Their own full worker
  logs recover quality metrics, exclusion counts, SHAP populations and the
  explicitly skipped optional-labeling outcome. Run 334 retains 9,294 training
  rows, 216,876 predictions, 17,937 SHAP contexts and 717,480 contributions.

Separate SHAP durations cannot be recovered from restored runs: that work was
measured inside scoring. Stage start/completion timestamps recorded late by old
workers cannot be reconstructed precisely. For early archived runs, separate
dataset/publication/verification times and metrics absent from the saved receipt
remain unknown. Per-title inference lists previously supplied by private item
checkpoints cannot be reconstructed from aggregate-only logs. Collection output
previously discarded with `/dev/null` is unavailable. Existing complete local
worker files remain retained; the UI continues to expose bounded log tails.

## Validation

- Focused backend routes, observer, history, architecture, labeling, scheduler and
  restart-guard checks: 109 passed, 11 optional database checks skipped.
- Disposable Unix-socket PostgreSQL predictor fixtures: 14 passed. Fictional
  sources/encoder only; coverage includes repeated-result equality, publication
  failures, existing safety checks and the restored monitoring event boundaries.
- Frontend: seven formatter/progress tests and three actual React component
  rendering tests passed; TypeScript and Vite production build passed.
- Existing production history projected read-only; original monitoring-record
  digests, model/configuration checksums, production populations and scheduling
  captured for comparison around the guarded backend restart.

There was no active production run during validation. Active monitoring was
exercised with synthetic subprocess output and rendered API-shaped fixtures;
no additional predictive run was initiated. The broad application test attempt
stalled early and was stopped; the focused and isolated results above are the
completed acceptance checks, not a claim of a full-suite pass.

Deployment evidence and rollback copies are local and private under
`.secrets/monitoring-restoration/`.

## Deployed verification

The backend was restarted through `scripts/restart_backend_safely.py --restart`,
holding the existing execution lock. Authenticated live list/detail responses
passed for runs 325, 326, 327, 331, 332, 333 and 334; unauthenticated access was
rejected. The deployed SPA and its JS/CSS matched the tested production build.
React rendering was tested directly; no interactive browser inspection is claimed.

Before/after checks matched exactly for the active configuration checksum,
classifier file checksum, all measured production populations, original run/stage
record digests and scheduling. Scheduling remains enabled as it was before this
deployment; all 11 existing run records are unchanged. No predictive job was
started. The backend is active with zero automatic restarts, and the disposable
test database has been stopped. No deployed-code receipt or retired infrastructure
was updated.
