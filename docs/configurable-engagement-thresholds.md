# Configurable passive engagement boundaries

The active daily path is `api.predictive.runner` → `prepare` →
`features.training_rows`/`training_plan` → `label_for`. The retired
`build_training_data.py` and archived `embedding_generation` implementation are
not used by this path. They are not changed by this correction.

## Settings and classification

| Key | Settings display name | Default |
| --- | --- | --- |
| `training.engagement_threshold` | Positive Engagement Minimum | 0.60 (60%) |
| `training.negative_engagement_threshold` | Negative Engagement Maximum | 0.35 (35%) |

The existing positive key and its stored values are preserved. Its former
Settings-definition default of 0.70 did not reflect the active fixed 0.60
implementation; the definition now matches the preserved effective default.
No stored threshold is rewritten. An absent negative setting resolves to 0.35
through the existing Settings infrastructure, without a database migration.

Both values must be finite proportions in [0, 1], with negative strictly below
positive. Settings saves validate the final effective pair before writing,
including partial edits, explicit resets and simultaneous updates. The existing
settings table is locked only for that short save transaction so concurrent
partial edits cannot produce an invalid pair. The active source policy also
validates both values after its authoritative database read. The former fixed
0.60 rejection is removed; unrelated contract guards remain in place.

A passive outcome is positive when summed played seconds/runtime is at least
the positive minimum. It can be negative when that ratio is at most the
negative maximum, provided the existing minimum viewing and revisit rules pass.
Between the two boundaries it remains unclassified. The same configured pair
is used for passive-label comparisons in auxiliary feedback diagnostics.

Explicit feedback handling and precedence, canonical identity, historical
availability and target exclusion, sample weights, meaningful viewing checks,
and existing 21-day movie/14-day episode defaults are unchanged. Watch/profile
qualification remains separate. The classifier validation cutoff and
recommendation display threshold are also unchanged.

## Provenance and incumbent compatibility

Engagement boundaries are supervised-fit parameters, not encoder or coordinate
space parameters. Each newly prepared input snapshot captures an explicit
`label_thresholds` object (`positive_minimum`, `negative_maximum`). It reaches
training rows and dependency hashes, the dataset summary, evaluation, the
checksum-addressed model bundle, published model metadata and the existing
training-data diagnostics JSON. Training rejects rows whose captured pair does
not match the fit inputs, before any fitting begins.

The existing `contract`, `feature_space_id`, modality hashes, supervision-policy
identifier and identity policy remain unchanged: the existing rule family is
preserved and only its two numeric parameters become configurable. In particular,
the legacy `labels` contract identifier is not used to infer a newly fitted
model's thresholds; explicit fit metadata supplies the parameter values. This
avoids invalidating vectors, compatible semantic labels or the incumbent merely
because configuration support was added.

Historical bundles and configurations without explicit threshold metadata were
created by the fixed 0.60/0.35 implementation. They retain that interpretation and
are not rewritten. A new artifact's threshold metadata must exist on both bundle
and configuration, be valid, and agree exactly. Existing checksum, source,
feature-map, identity and supervision safeguards still apply. Loading an
incumbent never compares its original thresholds against today's mutable Settings.

Changing a setting does not reclassify stored rows or reinterpret the current
model. The next separately initiated ordinary pipeline execution captures the
new pair, builds its own labels and uses the existing quality/publication gates.
Validation cohorts and class definitions may change with the pair, so old and
new aggregate scores should not be treated as equivalent-population comparisons.
No quality gate or publication safeguard is bypassed. No new persistence,
transition framework, label architecture or feature space is introduced.

## Validation and delivery boundaries

Focused tests cover frozen pre-change label parity, both configurable/equal
boundaries, cumulative playback, negative eligibility and revisit windows,
feedback precedence/weights, invalid/nonfinite pairs, transactional partial
edits/resets, actual preparation/training-plan propagation, persisted diagnostics,
model metadata, legacy artifact acceptance and provenance tampering rejection.
Model fitting is mocked in fit-path tests. Isolated configuration fixtures do not
write production settings.

This correction does not run training, scoring, embedding generation, semantic
cloud labeling or the production pipeline. It does not apply the proposed
85% negative / 90% positive pair. Deployment uses the existing pipeline lock and
backend restart convention; the metadata-driven Settings UI requires no frontend
code or bundle change. Production data/artifacts and effective settings are
checked with private read-only preservation snapshots before and after deployment.

## Verified deployment — November 21, 2026

The broader isolated suite passed 1,428 tests and 89 subtests, with 334 optional
skips. Three additional PostgreSQL checks passed using only a connection-private
temporary settings table. The authentication suite used its required secure-cookie
test environment; production authentication configuration was not changed.

The backend was deployed/restarted with the existing shared execution lock held.
An authenticated GET-only browser check verified both rendered field names,
0.60/0.35 current/default values, and proportion input bounds. The existing
frontend asset was unchanged, and no Settings save was submitted.

The exact incumbent loads with the corrected code. Full record-set hashes match
for all pre-existing published/model data, vectors, historical records, labels,
assessments, accounting and settings. All model/backup artifact file hashes match.
The existing Settings bootstrap added only the new definition's default-metadata
row, with a null raw value and no operator override; it did not rewrite any prior
setting. Effective positive/negative boundaries remain 0.60/0.35, recommendation
display remains 0.70, and scheduler settings/run history are unchanged. No model,
embedding, scoring, cloud-labeling or pipeline execution was initiated.
