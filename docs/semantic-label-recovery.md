# Semantic label recovery — November 19, 2026

The November 17 cleanup incorrectly treated a feature-configuration mismatch as
proof that 500 EmbeddingGemma-2 labels were obsolete. The full-column removal
backup retained all 500 rows. Recovery inserted those exact rows in one
transaction and independently compared every column with the backup before any
provenance reconciliation. No replacement inference was performed.

## Compatibility and preserved evidence

The 403 media labels describe native coordinates 0–767. The archived and current
media serializers have identical syntax trees, input construction and serializer
version. Both use the same 768-coordinate encoder digest, normalization, context
and batch options; requests compared offline differ only in execution thread
count. The coordinate ordering is identical. The changed user-profile contract
does not change those media coordinates.

Only these 403 rows' current-association fields (`config_id`, `feature_space_id`,
`contract_hash`) were reconciled. Original generation IDs, encoder digests,
timestamps, label contents and governance flags remain unchanged. Each row has
an appended assessment containing its complete original row, reconciled row,
original accepted assessment reference and equivalence-proof hash. The original
full-column backup remains untouched. Strict compatibility checks are unchanged.
Of the 403 compatible labels, 221 satisfy the existing explanation display gates;
the other 182 retain their original review/explainability restrictions.

All 97 user labels are recovered with their original provenance and excluded
from current explanations. Both profiles use the same encoder basis, but the
profile construction changed from `rating-key-text-mean/2.0` to
`canonical-text-mean/1.0`. Comparing retained old/current profiles finds only
3 of 31 complete vectors identical, no identical population columns among the
97 labeled coordinates, and different HIGH/LOW rankings for 91 of them. History
changes may contribute to these differences: this establishes unresolved
equivalence, not proof that every old semantic description is false.

The original 2,043 assessments, 934 request entries and 17 batches are preserved.
The 403 new audit assessments record reconciliation, not provider requests.
Recorded estimated consumption remains $0.39824980. No accounting was reset.

## Focused corrections

Daily eligible selection includes retained finite SHAP coordinates even when
their retained contributions are nonpositive. Valid compatible labels and
unchanged-prompt abstentions are reused. Due reviews remain eligible after their
existing cooldown, follow new dimensions, and use the existing review save path.
Forecast/progress pending counts include those reviews. Provenance, quality,
per-prompt attempt caps, cloud authorization and cumulative limits still apply.

Plex's authenticated identity and Tautulli's authenticated server information
agree on the actual server identifier. Only `plex.server_identifier` was
corrected. A real metadata item and its generated deep link were checked against
that server. The literal test fixture `real-machine-id` had reached persisted
settings because poster discovery tests mocked HTTP but not persistence. Those
tests now explicitly mock persistence, and an autouse test guard rejects any
unmocked use of that discovery persistence path. The intentional persistence
unit test uses a fake connection. Other callers of this settings path were
checked for equivalent leaks.

The dedicated eighth semantic-labeling stage remains after publication and
verification, with separate logs, timing, status and nonblocking failure behavior.
Existing completed history and active fixtures verify it without running a job.
Effective policy at recovery: labeling enabled; standing cloud authorization
false; cumulative budget $0; request limit 0. These settings were not changed.
Daily cloud labeling remains blocked until the operator independently changes
the existing authorization and limits.

Private backup checksums, exact-row recovery receipt, source/encoder comparison,
assessment reconciliation, identity checks and deployment verification are kept
under the ignored `.secrets/label-recovery-20261119/` directory. No model, vector,
prediction, scheduler, database schema or public response schema was changed.

## Validation and deployment

The focused suite passed 131 tests and 3 subtests (36 optional tests skipped).
The complete offline suite passed 1,261 tests and 89 subtests (330 optional tests
skipped), with an invalid database URL and test-persistence guards. Secure-cookie
configuration was set before application import for that suite. Backend source
was installed under the existing pipeline lock and the backend restarted; the
frontend assets and scheduler were unchanged.

Read-only production verification confirms the 500 physical rows, 403 compatible
media labels, 221 display-eligible labels, unchanged original assessments and
ledger, unchanged predictor configuration and unchanged pipeline policy. A real
retained prediction returns media descriptions through the existing strict SHAP
selection function; recovered user descriptions remain excluded.

An authenticated deployed browser check verified 200 rendered poster-link anchors
against the independently verified server identity, restored Title traits on
recommendations, media labels in Dimension Explorer and the separate eighth
labeling card on completed run 348. Temporary GET-only browser fixtures verified
incoming stage-local output, progress, accepted labels, reviews, abstentions,
request/cost counters and terminal states. No real active run or labeling batch
was started. The deployed backend is active. Final preservation checks were
repeated after browser validation.
