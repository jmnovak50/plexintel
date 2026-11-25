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
