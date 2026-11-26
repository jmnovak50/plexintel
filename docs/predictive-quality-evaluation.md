# Non-blocking predictive quality evaluation

Chronological and show-held-out validation remain part of each daily execution.
Their metrics, cohort hashes, feature diagnostics and timings are retained.
Statistical comparisons are monitoring diagnostics, not publication conditions:

- Chronological balanced accuracy: at least 0.50.
- Show-held-out balanced accuracy: at least 0.50.
- Chronological average precision: no more than 0.05 below the incumbent's
  recorded historical AP. Historical cohorts may differ; this comparison is
  diagnostic and does not introduce a reference-model refit.

An unsatisfied comparison records its metric, observed value, diagnostic minimum,
comparison operator and readable warning. Warnings are emitted into the model
training stage before the final all-data fit. They do not prevent the final fit,
scoring or atomic publication. Training still performs only the two existing
validation fits and one final all-data fit.

The full evaluation is recorded in its training-stage stdout event immediately
after validation, so final-fit or staging errors cannot discard the measurements.
The completion receipt retains the same data without repeating the operator
classification summary.

For compatibility, `evaluation.gates` retains the original comparison booleans.
New evaluations explicitly record `statistical_checks_blocking: false` and a
`statistical_warnings` list. These are recorded outcomes, not configuration
switches. The monitoring stage reports successful execution independently of
`quality_passed` and records `quality_warning_count`. Operator labels identify
these as statistical diagnostics and non-blocking warnings.

Older run records keep their original statuses and recorded gate meaning. Missing
historical warning counts are not invented, and previously failed executions are
not retrospectively reclassified as successes.

Training data, model/feature contracts, chronological and show-held-out leakage
checks, inference validity, artifact checksums, scoring completeness, publication
transactions, final verification and last-good recovery remain blocking technical
safeguards. An evaluation execution error is also a real execution failure.

This correction does not incorporate the separate hierarchical-feedback branch,
change feedback weights, training eligibility, engagement thresholds, embeddings,
XGBoost features or hyperparameters, SHAP, semantic labeling, database schemas or
scheduling. Automatic semantic labeling remains disabled for the authorized
production validation run.

Temporary vector/training materialization is part of the scoring span, so a
staging error is visible as an execution failure before any scoring/publication
claim. PostgreSQL shared lock-table exhaustion is reported explicitly without
exposing SQL or source payloads. Exit 75 is a retryable classification, not proof
that a capacity problem will clear by itself. Manual executions have no automatic
retry queued; scheduled executions retain their existing limits and backoff.
No retry rules or database limits are changed by this reporting correction.

Public embeddings remain unchanged until atomic publication. Newly inferred
media/watch vectors are committed to the compact pending inference store, so a
later execution can reuse them after a pre-publication failure. See
`durable-embedding-inference.md` for compatibility, retention and backup coverage.
This is vector reuse, not stage checkpoint recovery.
