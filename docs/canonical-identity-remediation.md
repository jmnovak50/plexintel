# Canonical identity and retrospective supervision policy

The corrective implementation and its regression tests are retained while the predictive-model investigation is suspended. Cleanup does not deploy this code, retrain or publish a model, rebuild embeddings, restart services, or resume scheduling. Existing production model artifacts are not upgraded by a source change alone. Any future training, deployment or publication needs separate authorization and review.

## Shared identity resolution

`api/embedding_generation/recovery.py` owns both historical recovery and the read-only `CanonicalTitles` index. The index consumes verified `plex-guid-replacement` / `exact-stable-guid` evidence from the existing `Resolver`; it does not perform a competing lookup, fuzzy title match or live metadata request.

Canonical identity combines media kind and exact stable GUID. Movie, episode, season and show identities remain distinct. Episodes require consistent series identity and season/episode coordinates. Different episodes can share an evaluation group without becoming one prediction target.

Recovery provenance, source/destination GUIDs and types must agree. Replacement chains require one terminal destination and no cycles. Missing destinations, conflicting members, invalid provenance and unsupported identities fail closed. Cross-provider equivalence is not inferred without verified evidence.

## Training and feedback

`features.unseen_training_candidates()` and `training_plan()` consolidate aliases into at most one observation per user/canonical title:

| Evidence | Policy |
| --- | --- |
| Recorded canonical viewing | Use the earliest recorded engagement cutoff and one supported watch-derived outcome, aggregating relevant watch events. Existing verified-start/source-time and maturity rules apply. |
| Watched-like/dislike with recorded viewing | Keep the declaration as auxiliary evidence; do not create a later first-exposure observation or overwrite the watch-derived outcome. Count opinion conflicts separately. |
| Interest/rejection fully available before first recorded viewing | Preserve the explicit pre-viewing label and its earlier cutoff. Later intent/rejection does not become first-exposure supervision. |
| Interest/rejection without recorded viewing | Retain a supported intent/rejection observation at creation time. |
| Watched-like/dislike without recorded viewing | Retain a retrospective explicit observation at `created_at`; label availability is `max(created_at, modified_at)`. Submission is not a verified first-viewing date. |
| Multiple alias feedback records | Select the latest valid available state. Conflicting states tied at latest availability quarantine the outcome. |
| Invalid timestamps, uncertain target identity or uncertain available history | Exclude and count; never substitute unrestricted history or invent exposure times. |

The existing engagement thresholds, meaningful-partial criteria, waiting periods and sample weights remain unchanged. Explicit mappings remain interest = positive/0.75, rejection = negative/5, watched-like = positive/3 and watched-dislike = negative/5.

Rows retain `observation_kind`, qualified legacy-feedback provenance and auxiliary/conflict counts for diagnostics. Those fields are excluded from numeric predictor inputs. `predates_four_state_source` identifies a source-history boundary, not proof of the original action or deployment date. Retrospective declarations may reflect unrecorded viewing, and classifier output is not a calibrated probability of enjoyment or completion.

## Feature isolation, candidates and evaluation

`ProfileContext` and `feature_row()` exclude every verified target alias from qualifying-media means and watch-vector sums before calculating `watch_sim`. Each qualifying canonical title contributes one representative media vector; multiple qualifying watch events retain their existing event weighting. Strict watch/availability cutoffs, empty-history exclusion and cached-context identity checks remain in force.

`unseen_candidate_keys()` applies the existing watched threshold and suppression rules across aliases. Watching a retired key suppresses its replacement as an unseen candidate. Different episodes remain independently eligible. Uncertain candidates are omitted; uncertain available watch history cannot silently disappear from a profile.

Chronological validation retains label-maturity purging. `show_heldout_plan()` groups episodes by canonical show and movies by canonical title, expanding held-out profile exclusions across aliases. Duplicate user/canonical outcomes are rejected. Vocabulary fitting remains fold-only. Model architecture, numeric feature definitions, decision threshold and quality gates are unchanged.

## Narrow Friends suppression containment

`eligibility_quarantine.py` implements the separately reviewed `audited-series-suppression/1.0` exception. Only keys `14808`, `14833`, `14858`, `14859`, `14884`, `14909`, `14934` and `14953` qualify, with their exact local GUIDs, episode coordinates, valid provenance and verified Friends series identity.

For unresolved suppressed feedback on those records, the verified series is excluded from candidates and resolved profile contributions. This never assigns an uncertain episode identity, merges sibling episodes, permits unknown watch history or admits unresolved training outcomes. Unrelated local keys or changed evidence still fail closed.

## Compatibility and operational boundary

Identity policy: `verified-canonical-unseen-title/1.0`. Supervision policy: `canonical-retrospective-feedback/1.0`.

Policy markers are retained in rows, dependencies, dataset/model metadata and evaluation/scoring summaries. `model.load_bundle()` rejects stale text-model or dataset policy markers. Text adoption still requires exact reconstructed cohort/feature/label/weight/time parity; changing markers alone is insufficient.

The 768 media-text + 768 user layout and existing embedding contracts are preserved. Stored complete user profiles retain their existing publication/interpretation role; historical/scoring features use the canonical builder. Legacy/multimodal paths are not silently upgraded by this policy. The production `daily` entrypoint includes scoring and promotion and must not be used as a training-only trial.

The removed investigation runners, generated model copies, reports and owner-review artifacts are recoverable from the private cleanup snapshot, outside normal application paths. Production deployment manifests, provenance, rollback archives and backups remain in place.

## Regression coverage

`tests/test_canonical_identity.py` retains anonymized retired/replacement episode fixtures, repeated-event and feedback-update cases, timestamp maturity, canonical user/watch exclusion and `watch_sim` mutation invariance, distinct sibling episodes, ambiguous evidence, candidate suppression, policy compatibility and the narrowly bounded quarantine. Existing feature/database fixtures retain explicit valid GUIDs.

These tests use fixtures and fake scoring/model objects. Opt-in database integration tests remain separate. A safe focused check is:

```bash
PYTHONDONTWRITEBYTECODE=1 PLEXINTEL_TEST_TEMP_DB=0 \
  plexenv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_canonical_identity.py \
  tests/test_embedding_generation_features.py \
  tests/test_embedding_generation_recovery.py \
  tests/test_training_leave_one_out.py
```

Historical metadata/revision availability, selection bias, class imbalance and the absence of a locked prospective test remain evaluation limitations. Retaining these correctness fixes does not certify a production model or authorize further investigation.
