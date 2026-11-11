# Restoration acceptance — November 11, 2026

Historical assessment at `63c116e`. See [defect closure](restoration-defect-closure.md) for the subsequent corrections and focused review; predictive acceptance still requires a real-data fit.

**Final implementation acceptance: NO-GO. Predictive acceptance of a new restoration model: HOLD.** The simpler architectural direction is reasonable, but two concrete blockers invalidate the earlier fixture-based GO: the source reader requires a nonexistent public column, and a reachable labeling entry point still uses the retired runtime. This is a separate adversarial source-review pass by the same assistant that implemented the restoration, not a second independent assessor.

Reviewed branch: `restoration/simple-predictive-pipeline`, HEAD `63c116ee23f37c8bcf71faadc89d36a76476d869`, including `f576410` and `6c0d579`. Reference architecture: `764b2ee3920026d49ba1ad5b3705a9b25255f122`, before `00a420c`. No application code, production records, settings, models or vectors changed during this acceptance exercise. No fitting, embedding requests, cloud requests, publication, deployment, merge, push or scheduler action occurred. Only this report and protected analysis artifacts were written; no commit was made.

## Material architectural findings

### A1 — High: required public observation column is missing

`api/predictive/source.py:86–89` selects `wh.observed_at`. The actual production `public.watch_history` has no such column. Calling that reader in a read-only transaction produced `UndefinedColumn: column wh.observed_at does not exist`. The prepared `001_public_provenance.sql` does not add it, and the grouped history writer does not populate it. The PostgreSQL fixture at `tests/test_predictive_publication.py:42–44` adds it separately, hiding this incompatibility.

Applying only the documented migration to a public-only production clone therefore does not produce an executable daily pipeline. Adding an empty column alone would also not establish historical observation provenance.

Minimum correction: define the actual supported observation/availability source, include any necessary public column and writer in the explicit migration/ingestion contract, and preserve unknown historical times. Test a clone of the actual public schema with only the documented migrations; do not supply extra fixture columns. Do not manufacture old observation timestamps or require a full upstream replay merely to evaluate retained, verified feature data.

### A2 — High: an admin-reachable labeling path still depends on the migration runtime

`api/routes/admin_routes.py:33–40` whitelists `label_embeddings.py`; `:393–404` launches that file as a subprocess. `label_embeddings.py:149`, `:181–185` and `:212–215` still import and branch on `api.embedding_generation.runtime`. With no installation marker, its guard calls `active_generation()`, which queries `embedding_v2.control` even before parsing `--help`.

A mock-only invocation captured `SELECT to_regclass('embedding_v2.control')`. Expanding the import-closure test to this entry point rejects it. The existing closure test follows Python imports but misses the admin subprocess edge. The current dimension-config error message also directs operators to `scripts/register_dimension_config.py`, which retains the old runtime guard.

When no marker/schema remains, the single-dimension CLI can enter its legacy path. That path calls the provider directly (`label_embeddings.py:117–124`), outside the new usage-reservation and provenance engine. No real request was made; the control-flow issue is demonstrated, not a claim of observed unauthorized spending.

Minimum correction: route supported labeling entry points unconditionally through the current labeling engine, or explicitly retire them. Include whitelisted subprocess targets and supported registration/repair commands in the dependency acceptance check. This needs a small integration correction, not a replacement platform.

### A3 — Medium: supported profile/maturity settings are silently ignored

`api/predictive/source.py:24–39` reads the profile threshold and movie/TV waiting periods. `runner.py:63–89` does not pass them into preparation; `contracts.py:110–114` hardcodes `.5`, 21 and 14 instead. The prior collection code explicitly forwarded those settings.

A pure probe with an intended 30-day movie wait showed that the restored 21-day specification labels a 22-day-old partial watch negative, while the configured policy leaves it pending. A nondefault profile threshold is likewise ignored. This is a conditional compatibility defect; the retained incumbent uses the default values, so it does not explain a demonstrated current-data mismatch.

Minimum correction: either carry the resolved supported values into the versioned specification or reject unsupported nondefaults before work begins. Add a regression for configured label maturity and profile qualification. Do not silently change the policy or quality gates.

### A4 — Meaningful resource concern: avoidable bulk associations and retained dependency graphs

The current source fingerprint and runner load the entire cast-association population (`publication.py:42–45`, `runner.py:67–68`, `recovery.py:152–165`). Production has about 1.006 million media/cast associations, averaging 119.4 per title, maximum 278. That helper exhausted a deliberately bounded 384 MiB address-space analysis process. This does **not** measure the pipeline's production RSS requirement.

Separately, the real 9,302-row plan entails 4,422,602 profile-hash links. Just their inner two-element Python lists require about **304 MiB**, excluding strings, outer lists, watch dependencies, vectors and fitting. `features.py:113` constructs them per observation and `:323–326` retains all rows. `scoring.py:23–31` also retains full feature/dependency rows for every candidate before sorting. Temporary staging is legitimate; retaining all these repeated Python structures is an avoidable resource cost, not evidence that a larger permanent test installation is needed.

Minimum correction if needed for resource acceptance: bound/stream association reads and dependency hashing, and retain only the data required for fitting/ranking. No new database subsystem is warranted. Full workload RSS, publication-lock duration and incremental latency remain unmeasured. The approximately 32m49s historical reference and 40-minute acceptance threshold remain unchanged.

## What is structurally acceptable

The predictor core has no migration-schema SQL, generation store, activation registry, permanent staging populations or per-run database archives. `api/predictive` has about 2,389 Python lines with identifiable duties: serialization/encoder access; identity, quarantine and profile rules; features/fitting/evaluation; scoring; file persistence/publication/recovery; and ordinary progress/history/diagnostics. A stable feature-space fingerprint is an input contract, not a new generation lifecycle.

There is one current public vector store per modality, one current canonical training population and one current recommendation/SHAP population. Connection-private staging supports atomic replacement; a single last-good ordinary backup and current/previous model files support recovery. These are proportionate responsibilities. Model-file checksum/fsync precedes pointer publication, and protected outputs/configuration are replaced transactionally. No long publication-table lock is held during fitting. Unknown commit outcomes require verification rather than automatic workload replay.

The intended daily path, canonical/retrospective arithmetic and new optional-label adapter preserve the requested design. Authentication and recommendation query interfaces show no new source-level regression in this pass; production API compatibility has not been qualified. The generation-status response intentionally changed. New automatic labeling retains coherent authorization, cumulative reservations, revocation checks and label compatibility; A2 prevents claiming those controls cover every reachable labeling path.

## Real-data evidence and reuse

Production access used only read-only repeatable-read SELECT transactions and session-local limits. Public source capture was at 08:55 America/Chicago; saved-output verification was at 09:04. The application reader failure was recorded rather than repaired in production. A bounded explicit reader collected the fields actually present.

The incumbent remains model SHA-256 `7255f9ea0907d0ee089a36b5be378056f0586680fc74feb5785c1b1c36e89030`, publication `49bcdcbc-befa-4887-85d7-2dc2388024a3`. All 8,420 media, 9,667 watch and 31 user vectors match the protected November 11 capture. Streaming order-independent hashes also match all 9,301 current training-feature/label projections and 223,877 current saved predictive-output projections. Interaction-tracking fields were excluded from the prediction comparison.

Original media/watch input hashes, encoder digest, modality contracts, completion status and physical float32 vector checksums were checked: **zero mismatches**. The local encoder digest is `f4981a15b99858ad1f2e0729416e526be7b4f428291b40082b9e4f7b27b5f62f`. No regeneration or full ingestion replay was needed for this analysis.

Public alone lacks the new vector provenance columns and historical start/availability/observation receipts. Retained approved provenance supplies those details. All 8,420 public library source records also match the retained public-valued fields. All 9,949 public event records exactly match the public-valued fields of those retained receipts; 9,667 are library-linked and 282 remain quarantined. No timestamps were invented. This is retrospective source-event reconstruction, not proof of what the application knew before later source corrections. Without these retained receipts, public summaries/cast associations alone would not prove identical embedding inputs or historical availability.

The restored old-cutoff plan reproduces **all 9,301 labels and sample weights**, with no missing outcome identities. A deterministic, class/source/history-stratified sample of 36 stored rows has **exactly zero** feature-vector and `watch_sim` differences. This is bounded arithmetic evidence, not population-wide feature reconstruction or a new performance estimate.

The two original retired-key cases were checked on real retained inputs. They now form first-recorded-watch outcomes under the live keys; later explicit feedback is auxiliary. Both alias sets contribute zero target media/watch history to their features:

| Canonical alias keys | Observation cutoff UTC | Primary source | Target media/watch contributions |
|---|---|---|---|
| 36296 / 36298 | 2026-04-04 01:13:57 | watch history | 0 / 0 |
| 38257 / 38259 | 2026-08-25 02:05:08 | watch history | 0 / 0 |

## Current eligible population — no new fit

One additional explicit positive feedback record explains the change from 9,301 to **9,302** observations: **8,475 positive / 827 negative**. Canonical user/title duplicates are zero. Nothing was restored to force a target count.

| Observation kind | Rows |
|---|---:|
| First-recorded watch | 7,008 |
| Retrospective explicit feedback | 2,136 |
| Pre-viewing rejection/intent | 158 |

Sources are 6,340 watch positives, 668 watch negatives, 2,135 explicit watched-like positives, 158 explicit rejections and one watched-dislike negative. All 2,136 retrospective rows belong to A. B is the largest negative contributor (311 negatives); A has 193 negatives overall, mostly from other sources. Contributor counts are not per-user performance measurements.

Exclusions: 553 label-policy cases, 42 limited-history cases and eight unresolved identities. There are also 211 auxiliary post-watch feedback records; these are **not** 211 additional removed training observations. The chronological partition has 5,263 fit / 1,861 validation rows, with 2,178 earlier observations purged for immature labels. Show-held-out support is 4,348 / 463, with six support skips. Chronological fit classes are 4,585 positive / 678 negative; grouped fit classes are 3,791 / 557.

## Historical validation models — distinct from the final all-data model

These are stored results of the incumbent's earlier chronological/show-held-out models. **No restored classifier was newly fitted here.** Reconstructed current cohorts have the same counts, but that does not turn recorded metrics into a new experiment.

| Metric at existing 0.5 threshold | Chronological | Show held out |
|---|---:|---:|
| Fit / validation | 5,263 / 1,861 | 4,348 / 463 |
| Validation positive / negative | 1,726 / 135 | 432 / 31 |
| Balanced accuracy | 0.53269 | 0.59446 |
| Positive precision / recall | 0.93192 / 0.99131 | 0.94505 / 0.99537 |
| Negative precision / recall | 0.40000 / **0.07407** | 0.75000 / **0.19355** |
| Average precision | 0.96788 | 0.97920 |
| ROC AUC | 0.74044 | 0.82781 |
| Macro F1 | 0.54285 | 0.63863 |
| Brier score | 0.06262 | 0.04838 |
| ECE, ten buckets | 0.02840 | 0.02850 |
| Confusion matrix, rows true negative/positive, columns predicted negative/positive | [[10,125],[15,1711]] | [[6,25],[2,430]] |
| Labeled-candidate NDCG@10 / recall@25 | 0.95017 / 0.51783 | 0.99061 / 0.86536 |

Chronological validation is 92.75% positive; grouped validation is 93.30% positive. High positive precision/AP therefore coexists with missing 125/135 and 25/31 negatives. Constant-prevalence Brier baselines are 0.06728 and 0.06247. The 0.9–1.0 score bucket has chronological mean prediction 0.9740 versus 0.9532 observed positives (1,497 rows); grouped values are 0.9773 versus 0.9636 (385 rows). Sparse lower buckets and few negative predictions make minority calibration uncertain.

The historical models used **only four retrospective rows in each fit**, while the current all-data plan includes 2,136. Their validation metrics do not validate the effect of the large retrospective block in the final model. Only 58 retrospective rows occur in chronological validation and ten in grouped validation. No new transfer/ablation claim is made.

Ranking metrics use selected labeled candidates, not the eligible catalog. Related users/shows, retrospective submission cutoffs, current descriptive metadata and repeatedly consulted validation limit independence. Grouped validation is not a user-disjoint or prospective test.

## Current final-model scores and recommendations

These are observations from the **existing final all-data incumbent**, whose saved outputs were verified against public. There is no independent performance score for this final model.

Among 223,877 saved scores, the median is **0.92853**; **60.88%** are >=0.9 and **4.21%** are >=0.99. The 10th/90th percentiles are 0.64914 / 0.98391. The saved population includes 54,738 movie and 169,139 episode predictions.

Four representative lists were filtered to the restored current eligible population and reranked by the incumbent's saved scores. This is an **eligibility-only control**, not a new restoration-model comparison. A has one newly suppressed saved candidate (3,905 saved, 3,904 still eligible); no new model inference was used.

| User | History events | Eligible movie / episode candidates | Top-20 movie / episode | Distinct series | Largest series share | Saved-score median |
|---|---:|---:|---:|---:|---:|---:|
| A, retrospective contributor | 1,622 | 615 / 3,289 | 0 / 20 | 15 | 2 / 20 | 0.98204 |
| B, largest negative contributor | 1,105 | 1,457 / 5,229 | 0 / 20 | 8 | 13 / 20 | 0.33575 |
| C, middle history | 133 | 1,861 / 5,589 | 0 / 20 | 6 | 13 / 20 | 0.94503 |
| D, limited history | 1 | 1,860 / 5,664 | 0 / 20 | 6 | 13 / 20 | 0.91781 |

B/C/D each contain 13 different episodes of **Curb Your Enthusiasm**. Movies were available, so movie absence is not explained by candidate unavailability. No exact canonical title repeats within a list; repeated series concentration is real. B/C, B/D and C/D share four, six and five exact top-20 titles respectively. No sequential daily restoration outputs were generated, so day-to-day repetition is unmeasured. This does not establish that the recommendations are personally irrelevant.

Readable 80-title lists and per-user distributions are in protected `.secrets/restoration-acceptance/top20-current-incumbent.private.md` and `offline-analysis.json`. No account names are included in the review lists. A genuinely common-population **new restoration model versus incumbent** comparison remains unexecuted because no new fit ran. No different-cohort metric comparison is presented as equivalent.

## What drives predictions, in plain English

The trees mainly use the title's text embedding and the user's prior-title mean embedding. In chronological validation their mean summed absolute SHAP contributions are about 6.01 and 5.42 raw-margin units, versus 0.22 for `watch_sim` and 0.01 for genre flags; director/decade contributions there are zero. Grouped evaluation shows the same broad pattern. These are correlated feature-group summaries, not additive causal percentages.

A high score means the title/profile coordinate combinations follow tree paths associated with positive engagement labels. A lower score means those paths supply less positive or more negative evidence. It does not establish that a particular coordinate means a specific taste, or that a user dislikes a title. Stored top-40 SHAP evidence is truncated and restricted to top predictions; low-ranked candidates generally lack saved explanations. The largest retained coordinate contribution is user_365 (global dimension 1133), an association without independently validated semantic meaning.

Strong differences in score medians across users show substantial personalization, but do not distinguish transferable engagement patterns from fitting particular user histories. The final model sees a large positive retrospective block from one user, while historical validation mostly does not. Related episodes share parent-series descriptive context and are ranked independently, allowing many siblings to win. Concentration is demonstrated; its causal attribution to Gemma geometry, retrospective feedback or a specific feature is not established by this study.

D has only one history event and no negative training outcomes, yet receives very high top scores. C has only seven negatives. Confidence and per-user rejection estimates for these users are not independently supported. Scores are outputs of a weighted classifier on selected engagement proxies, not validated probabilities of future catalog-wide viewing or subjective enjoyment.

## Resource decision and minimum next acceptance step

No full fit was started. Available memory ranged roughly 3.05–3.35 GiB of 15.84 GiB; the 20% reserve is about 3.17 GiB, leaving negative headroom or at most about 0.18 GiB. The dense feature matrix alone is approximately 57 MiB, and the runtime's profile-link lists alone about 304 MiB, before watch dependencies, associations, NumPy/XGBoost and fitting. A new full pipeline fit could not safely satisfy the established headroom condition. The bounded offline analysis peaked at 358,160 KiB RSS; streaming public-output verification peaked at 35,824 KiB. Those are not full-fit resource measurements.

This does **not** require a production-sized infrastructure project. The smallest next predictive experiment is an isolated, fixed-input fit on the already verified 9,301-row public materialization, with restored fold/group rules and reused vectors, on a host/resource window with enough headroom for one bounded analysis worker. Compare its saved scores with the incumbent on the exact same eligible titles. Test the additional feedback row separately. No upstream ingestion, embedding regeneration, cloud service, new permanent database or ranking/threshold tuning is necessary for that experiment. Its actual peak allocation must be measured rather than inferred from synthetic tests.

The existing identity/architecture unit suites passed **96 checks** in this acceptance pass, but the real-schema failure and expanded subprocess probe expose gaps in those fixtures. Application source remains unchanged. No production runtime measurement was made; retain approximately 33 minutes as the reference and <=40 minutes as the normal incremental qualification threshold.

Decision: **architectural direction acceptable in principle; current implementation NO-GO because of A1/A2; nondefault-policy acceptance blocked by A3; real predictive acceptance HOLD.** The earlier synthetic-based GO is superseded by these findings. Correct the demonstrated integration defects under separate implementation authorization, then complete the small frozen real-data fit, common-population score comparison and owner relevance review. Do not promote, retire the old schema, enable scheduling or authorize cloud work on this evidence.
