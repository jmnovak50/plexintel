# Dimension Explorer run data — November 20, 2026

Labeling results were persisted correctly, but the Explorer read model still
looked for the obsolete `batch_label` pipeline stage. That query returned only
two stage records, most recently November 3. Current daily labeling uses
`semantic_labels`, while manual/CLI executions record batches and assessments
without creating pipeline runs. Consequently the recent execution list omitted
all four recent CLI batches and current daily-stage results.

The register joined current compatible saved labels, but its frontend called an
unlabeled dimension "Not assessed" even when a retained abstention or failure
existed. Review-attempt counters and dates also did not describe first-time batch
assessments. Automatic refresh watched only review jobs/locks among the visible
dimension rows, so batches working on other dimensions never triggered refresh.

## Correction and rationale

- Read current feature-space batch history from the existing batch, assessment
  and request tables. Display selected/assessed/saved counts, recorded accepted
  outcomes, reviews, abstentions, failures, requests, known tokens and charged
  cost estimates. In-flight batches use committed assessments and request records.
- Associate a daily batch with a pipeline stage only through its exact retained
  workload identifier. Include stage-only disabled/skipped and legacy history
  without inventing batch counts or inferring associations from timestamps.
- Expose the latest assessment record, date, source, outcome and typed error on
  each dimension, independently of whether it produced a compatible saved label.
  Show assessment-record counts separately from review attempts. Reconciliation
  records are identified as provenance reconciliation, not new cloud inference.
- Add current assessment coverage/abstention/failure counts. "Unlabeled" continues
  to mean no current-compatible saved label; it does not mean unprocessed.
- Poll the existing ledger through a small authenticated read endpoint: every
  ten seconds while labeling is active and every thirty seconds while idle,
  only while visible. Recompute the expensive scoped SHAP register only when
  batch data changes or the user explicitly refreshes/returns to the page.
  Keep the displayed page present while refreshed evidence loads.

SHAP scope and label history remain distinct. The selected user, ranks and model
scope contribution statistics; batch history describes current feature-space
labeling across users and predictor publications. Saved labels retain the same
strict compatibility and explanation eligibility checks. No label, assessment,
accounting, predictor or scheduling records are modified by this correction.

## Verification

Read-only production queries returned 551 compatible labels and 382 dimensions
with assessment records, including 217 latest abstentions and 10 latest failures.
The latest actual batch reconciled to 100 assessed, 39 saved/accepted, 48
abstentions, 8 failures and 5 skipped, with 100 request records. All four recent
CLI batches and daily run 349 were returned. A retained abstention on dimension
1322 was independently checked against its detailed assessment history.

The frontend production build passes. The offline suite passes 1,278 tests and
89 subtests (331 optional skips). Three focused contract checks also pass with
PostgreSQL enabled, including a connection-private temporary-table test for
batch/request/assessment reconciliation, exact workload links, unsaved outcomes,
and exclusion of incompatible feature-space/configuration batches. Private
read-only snapshots and browser evidence are kept under the ignored
`.secrets/dimension-data-20261120/` directory.

The corrected backend and matching hashed frontend bundle were deployed under
the existing writer lock. An authenticated browser verified the actual four CLI
batches and daily run 349, the exact latest-batch counts, dimension 1322's
abstention, and dark/mobile layouts. The served asset matches the tested build.
GET-only fixtures verified active progress/completion outside the visible rows
and confirmed that unchanged batch polling avoids full SHAP register queries.
Full preservation snapshots match for all 633 physical labels, 2,871 assessments,
1,359 requests, 24 batches, predictor configuration, settings and run history.
No predictive pipeline or cloud-labeling batch was started.
