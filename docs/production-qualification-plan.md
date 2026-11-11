# Daily pipeline production qualification plan

Prepared November 10, revised November 11, 2026 (America/Chicago). Qualification results must be recorded separately; this plan does not assert that a gate passed.

Hardening base commit: `5e2697e4c86f4a92e61dbe88fc1d1d525a176004` — `Harden daily publication and recovery boundaries`. The reviewed candidate is the commit introducing this plan and the optional labeling integration; pin its exact Git SHA in the qualification evidence before execution.

The base commit's locally computed fingerprint was `c31034b28be7e989197da6904a4ced6f215cb1f302df5723b0e6945320d3bb37`; it does not cover the subsequent labeling integration. Pin the final reviewed source fingerprint before deployment. Neither value is automatically an approved receipt. The live baseline must be captured afresh; historical publication IDs and row counts are not qualification inputs.

The reviewed integration's candidate fingerprint at validation is
`7489c56006baf907a8eeaa4dfa48a197c9396576b7553877eca6050ec4cd2a9c`.
Recheck it against the exact reviewed source before any approved deployment;
this document neither registers nor approves it. Integration regression evidence
is recorded in `semantic-dimension-labeling.md`: after the authorization corrections,
1,092 full offline passes and 157 targeted settings/labeling/PostgreSQL passes.
The SQL checks used a disposable local cluster; no production qualification was run.

Implementation and test evidence: [pipeline-hardening.md](pipeline-hardening.md). Completed regression evidence is 343 focused tests, 1,062 full offline tests and 49 isolated compatibility checks. Those results do not establish production capacity.

## Authorization and sequence

The November 11 owner instruction authorizes committing/pushing the reviewed integration and progressing through Q0 and Q1 within their read-only/isolated boundaries. Q1 requires Q0 readiness and an approved consistent snapshot and isolated destination; unavailable prerequisites remain NOT RUN. Q2 deployment/receipt registration requires approval after Q1 passes. Q3 requires separate approval and starts with labeling disabled; real cloud labeling is a subsequent independently budgeted and authorized exercise. Scheduling requires separate acceptance and activation approval. No production fault injection or rollback is implied by Q0/Q1. Standing cloud controls are documented in [semantic-dimension-labeling.md](semantic-dimension-labeling.md).

| Gate | Work proposed | Production effects | Approval needed before execution |
| --- | --- | --- | --- |
| Q0 | Capture and pin a fresh baseline; confirm backups and monitoring | Read-only checks | Preparation within the reviewed qualification scope; no write approval implied |
| Q1 | Production-sized isolated rehearsal, fault matrix and rollback rehearsal | None; isolated destination only | Approve snapshot handling, storage and isolated execution |
| Q2 | Deploy the exact reviewed code against the incumbent model; verify existing serving behavior | Code deployment/restart and explicit receipt registration only | Separate deployment/receipt approval, including conditional recovery scope |
| Q3 | One supervised manual daily workload, followed by verification | Normal ingestion, possible embedding refresh, training, scoring and publication | Separate explicit approval for all those effects and conditional rollback scope |
| Q4 | Review evidence and decide production readiness | None | Owner acceptance; scheduling still requires its own later approval |

Stop after Q1/Q2 if production predictions, model and embeddings must remain byte-for-byte unchanged. `daily` has no production dry-run or non-publishing mode: it includes promotion. Do not relabel a daily run as a read-only check. Do not run it now.

Every gate is **PASS, FAIL or NOT RUN**. NOT RUN is not a pass. A failed gate blocks the next gate; do not alter receipts, saved baselines, thresholds, PostgreSQL settings or budgets to force a pass.

Before Q2/Q3, name the supervising operator and approve intervention/conditional rollback authority for that window, including the exact baseline deployment pair and publication. Without that recovery authority, do not start a production-changing gate. This avoids relying on a new approval being available during a failure; it does not authorize any recovery action now.

## Q0 — Baseline and readiness

Capture B0 in one bounded, read-only `REPEATABLE READ` transaction, with an eight-second per-statement timeout and rollback/close. Large population hashing must use bounded reads. Preserve:

- Live generation/publication IDs, model SHA, feature-contract SHA, source receipt, backend deployment/image identity, encoder identity, identity/supervision policies and active dimension configuration.
- Hashes and counts of physical media/watch/user vectors, stored recommendations/ranks, training data, explanation contributions/contexts and interpretation records. Retain canonical model bytes and exact current rollback provenance privately.
- Stored dataset/evaluation artifacts, class/source/observation-kind distributions, existing quality-gate reference AP, training/validation cohort identities and relevant operational settings.
- Installed/transition-marker state, active worker/journal inventory, scheduler setting plus any external timer/cron state, database lock settings, memory/container limits, disk availability and evidence retention location.

Use the same users, endpoints, filters, authentication roles and pacing for B0 and subsequent API latency samples: at least 180 requests over at least 15 minutes. Hash the publication's protected projections as the rollback code does; for example, its `app_settings` archive covers only embedding model and engagement threshold, not unrelated settings changed by another workflow.

Read production state through SELECTs and existing read-only verification routines. Do not call `validate_generation()`, schema/bootstrap helpers, dataset builders or scoring functions for this baseline. Admin pipeline list/detail GETs can reconcile run records; use direct SELECTs when a strictly read-only inventory is required.

**Q0 passes only if:**

1. Control, canonical publication/model, vectors and active feature configuration agree, with zero missing/corrupt receipts or vectors. The text model has 768 media + 768 user coordinates, no poster inputs, identity policy `verified-canonical-unseen-title/1.0` and supervision policy `canonical-retrospective-feedback/1.0`.
2. No production worker owns the execution lock and no ambiguous transition marker, unregistered child or unresolved pending run exists. An old unpublished run without an exact incumbent pin is an operator hold; do not manufacture a pin.
3. Scheduling is confirmed disabled in every launcher. This plan does not change its state.
4. A restorable B0 backup exists, with verified hashes and an identified prior code/model deployment pair. Do not assume the previous Git commit is the deployed baseline.
5. Monitoring and the operational budgets below are accepted before execution. Missing measurements or an unverified rollback backup mean FAIL/hold.

Private evidence should use an ignored, access-restricted location such as `.secrets/production-qualification/<id>/` (directory 0700, files 0600). Confirm ignore rules before creating it. Keep account names, watch/session IDs, credentials, model bytes and raw history out of Git, public reports and external providers.

## Proposed operational pass/fail budgets

These are proposed qualification budgets to approve and freeze before Q1. They are not measured production baselines, model-quality changes or PostgreSQL limits. If a budget is unsuitable, revise it explicitly before testing and retain the revision; do not waive it after a failed run.

| Measurement | Proposed pass criterion | Failure / stop rule |
| --- | --- | --- |
| Predictive daily workload, through final verification | Historical reference approximately 33 minutes; expected 30–35 minutes for comparable workloads; normal PASS <= 40 minutes; no concurrent second worker | > 40 minutes is a predictive-pipeline performance regression requiring stage/workload investigation; 60 minutes is the predictive-workload operational intervention ceiling |
| Optional cloud labeling | Record its own duration, request/retry/token counts and cumulative reserved/estimated spending against the separately approved cloud authorization and limits | Labeling errors, duration or spending stops never invalidate a successful predictive pipeline or count against its 40-minute acceptance budget; stop further labeling requests when its approved limits are exhausted |
| Cutover/source-write blocking | At most 60 seconds from first conflicting cutover lock until commit/rollback; individual lock acquisition remains subject to existing 5-second timeout | Longer blocking or any timeout fails this gate; resolve transaction outcome before intervention |
| Serving during the run | At least 180 paced read requests over at least 15 minutes, spanning pre-cutover, cutover and post-cutover; zero unexpected 5xx; p95 <= 2 seconds AND <= max(2 × B0 p95, 250 ms) | Any unexpected 5xx or exceeded latency budget fails availability acceptance |
| Worker memory | Peak worker RSS <= 70% of its effective memory budget; host memory available >= 20%; no OOM kill, cgroup OOM event or increase in swap-out | Available memory < 10% for 10 seconds triggers operator intervention; crossing acceptance thresholds fails qualification |
| Restoration locks | Peak own-backend lock count <= 128 during hydration/row restoration; at fixed input, a repeat has peak <= first run + 5; zero lock-exhaustion errors | Over-budget or input-sized lock growth fails; do not change server lock settings as a retry |
| Disk | Before start, free space >= 20% AND >= twice measured Q1 archive/temp/WAL growth on each affected filesystem; during run remain >= 10% free | Falling below 10% triggers intervention; no new attempt without capacity review |
| Final recovery of resources | Within 60 seconds of worker exit, its pinned backend/PID is gone and its locks/private context are released | Leaked worker/backend/locks or uncertain ownership fails acceptance |

Use the lower of container/cgroup allowance and an explicitly assigned host memory budget. An unknown effective limit is NOT RUN/hold. Lock counts are telemetry, not a calculation of PostgreSQL lock-table capacity; record global locks/waits separately. Peak RSS alone is insufficient to exclude host or database memory pressure.

Sample RSS, memory availability, swap, disk and database waits at least once per second. Also retain the implementation's 128-row checkpoint metrics. Identify backend processes using PID plus backend start time/application identity; never terminate a session based on a recycled PID or timestamps alone. Do not record raw SQL or credentials in public telemetry.

### Validated November 10 runtime reference

Bounded SELECT-only history inspection confirmed manual parent run **332**,
13:10:53.635724–13:43:42.323827 America/Chicago: **1,968.688 seconds = 32m 48.7s**.
Its correlated production run `aa8352c8-40ad-4818-91e7-a03560fa87fa` published
`49bcdcbc-befa-4887-85d7-2dc2388024a3`; the worker recorded 1,966.287 seconds total.
This is a historical comparison, not a new production qualification result.

| Recorded phase | Reference seconds |
| --- | ---: |
| Source synchronization | 119.592 |
| Context / metadata / media inference | 115.092 / 80.129 / 0.283 |
| Watch refresh / user profiles | 8.242 / 4.709 |
| Historical training data / model evaluation and fit | 343.934 / 234.651 |
| Prediction / SHAP | 377.429 / 423.342 |
| Validation plus publication span | 210.750 |
| Final verification | 12.444 |

The reference had 9,301 training rows, 31 user vectors, 223,877 predictions,
zero media-text inference requests and three watch requests. Compare volumes,
inference counts and class/cohort support before attributing a timing change to
hardening. Timers are not fully additive; phase and logical-span timing differ.
The publication span includes validation and is not a measurement of source-write
blocking; the existing 60-second blocking budget still requires qualification.
Flag a comparable phase increase exceeding both 20% and 30 seconds for diagnosis;
this is an operational diagnostic, not a changed model-quality gate. Record core
time and optional labeling time separately. Labeling had no automatic-stage time
in this historical reference, so report its overhead explicitly rather than
inventing a baseline.

## Q1 — Isolated production-sized rehearsal

Use a separate database/service endpoint with production network destinations blocked, schedulers disabled and cloud access disabled. Merely changing a schema/search path on a production writer connection is insufficient isolation. Restore an approved consistent snapshot, existing vectors and model into that destination. Capture the snapshot hash, versions, memory/lock settings and hardware differences from production.

Run the existing offline/temporary-table tests using the exact commands in `pipeline-hardening.md`. Then exercise full-size restoration and normal publication/rollback in the isolated destination. Reuse saved vectors. Derive any necessary new fixture inference solely within the approved isolated environment; no cloud requests or unapproved production encoder workload.

Normal full-pipeline rehearsal also requires reviewed local replay endpoints for frozen Tautulli/Plex responses and an isolated local encoder if justified inference is needed. Repoint only the isolated environment; a copied production URL/token is not permission to use that destination. Establish any candidate source receipt there as an explicitly approved, isolated-test fixture, never as production approval. If the full-size replay/fault harness or frozen source evidence is unavailable, mark the affected Q1 scenarios NOT RUN and stop; this document does not supply or execute a new harness.

| Scenario | Measurable PASS |
| --- | --- |
| Baseline acquired under lock | A competing revision becomes the baseline only after execution-lock ownership; the journal pins exact generation/publication/model identities |
| Same-generation revision race | Change publication ID or model SHA after staging in the isolated destination; publication rejects before source/archive hooks or protected-table changes; all protected hashes unchanged |
| Restoration past a committed batch | Inject interruption and mismatch at row 129 or later; prove at least 128 rows previously committed; saved model/dataset/evaluation/dimensions/scoring hashes unchanged; clean resume restores exact dataset count/hash/skips and materialization receipt; zero fit/inference calls during reconstruction |
| Genuine worker connection loss | Disconnect only the identified isolated worker backend after a completed batch; preserve original failure classification if journal annotation also fails; the next independent connection uses durable receipts, not lost temp tables |
| Ambiguous commit | Drop only the isolated client connection around COMMIT; independently inspect the publication receipt. If committed, resume performs verification only with zero ingestion/fit/scoring/promotion; if not committed, B0 protected hashes remain; uncertainty produces an operator hold |
| Actual hard kill | Kill only the disposable isolated barrier worker; retained transition marker blocks all automatic recovery work and is not removed, even when its PID is dead |
| Dispatch failure / orphan parent | Failed activation launches zero children; parent is terminal if writable. If terminal annotation fails, only an old, unchanged, unlocked row without dispatch evidence is reconciled; live/fresh/advanced/ambiguous rows remain protected |
| Retry durability | Transient exits are 75, permanent/unknown exits 78; restart the isolated controller between attempts; no more than 3 failures per slot and no retry earlier than 300 seconds with default settings; exhausted/permanent failures launch zero additional workers |
| Recovery across days | Prior-publication recovery persists `verification_only`, exits 76 and consumes neither a fresh slot nor retry budget; a later isolated poll may start one fresh workload; no second worker while the execution lock is owned |
| Rollback rehearsal | Restore the exact pre-publication model/publication, archived protected populations, explanation/config context and appropriate code receipt; verify hashes, not only counts; completion <= 15 minutes; scheduler remains disabled. The feature-config exception below is explicit |

Q1 must pass every correctness row and the resource budgets twice at identical full-size input for restoration. The second run checks repeatability, not an excuse to overwrite a failed first result. Rehearse fault scenarios on reset isolated snapshots; never inject these faults into production under this plan.

Existing rollback intentionally retains a newly introduced feature-config row as inactive. For that table, require exact restoration of baseline configuration rows and active metadata, exactly one correct active configuration, and a manifest of any additional inactive rows; do not require their deletion or claim whole-table hash equality. All other archived protected projections must match their saved hashes exactly. Restoring a prior source receipt while different code is still running must block writers until the approved code/receipt pair is restored.

## Q2 — Approved code-only deployment, incumbent unchanged

After Q1 passes and separate approval, deploy the exact reviewed candidate commit pinned in the qualification evidence and explicitly register its authenticated source receipt. Coordinate deployment with the execution lock/no active writer. Receipt changes are operator actions, not automatic acceptance.

PASS requires the backend deployment-status fingerprint, on-disk `runtime.code_hash()` and explicitly registered control receipt to equal the final reviewed candidate fingerprint. The existing model/publication, contract, policies, physical vector values, prediction/rank values and interpretation/explanation records must match B0 exactly. Verify before any writer starts.

Perform authenticated serving checks for at least five representative users: low, median and high history support, the retrospective-feedback contributor and the bounded quarantine case (anonymized in the report). Inspect 20 recommendations per selected user where available, movies/episodes/show rollups and explanation arrays. All returned records must obey the existing eligibility rules; missing semantic labels must remain empty/approximate explanations rather than invented labels. Stored numeric outputs remain unchanged. Input/feedback drift makes the API comparison inconclusive until re-pinned; never repair records just to make the comparison pass.

If the serving/receipt checks fail, stop before Q3. Any code rollback/restart or receipt restoration must follow the separately approved deployment recovery scope. Keep scheduling and cloud labeling disabled.

## Q3 — Separately approved single manual production workload

The owner must explicitly approve normal production ingestion, any justified local embedding refresh, fitting, scoring, SHAP, archival and atomic publication for this gate. Before starting, re-pin B1 and ensure Q0 conditions still hold. If B1 differs from B0 because legitimate source activity occurred, explain/reconcile it; do not reuse old counts or an old incumbent AP reference.

Use the existing authenticated manual pipeline trigger, which acquires the parent execution lock and writes parent/stage history: `POST /api/admin/pipeline/trigger`. Do not use the production `daily` CLI as a dry run or start an independent worker alongside the controller. Resolve the actual API mount/authentication from the approved deployment. No trigger request is made by preparing this document.

During the run, collect stage events, process/backend identities and the private evidence below. Perform paced read probes against the existing status/recommendation/explanation endpoints; zero expected failure responses are permitted in the normal Q3 run. A second trigger under the held lock must be rejected without a second child (prove this in Q1; do not create production fault traffic without approval).

| Acceptance area | PASS condition |
| --- | --- |
| Source/identity | Saved snapshot/source hash and exact incumbent pin recorded; no unknown target identity admitted; all quarantine/exclusion counts explained |
| Training materialization | Dataset rows > 0; row count, full original dataset hash and stored-row manifest agree; zero duplicate user/canonical-title outcomes; zero target-alias profile/watch contributions and zero future/unavailable history dependencies |
| Data reconciliation | Class, source, observation-kind and provenance counts sum exactly to the dataset total and match the pinned source policy; every delta from B1 is attributed. Do not force 9,291 or any historical row count, or restore duplicate/unresolved outcomes |
| Feature/model contract | 768 media + 768 user coordinates, no poster features/inference, unchanged label mappings/weights/thresholds/architecture. Bundle, vocabulary names and actual matrix layout agree; engineered/fold feature counts may vary legitimately with fold vocabulary and must be recorded |
| Existing quality gates | Chronological balanced accuracy >= 0.50; chronological AP >= pinned incumbent chronological AP − 0.05; show-held-out balanced accuracy >= 0.50. Metrics must be finite; threshold stays 0.50; no tuning or gate relaxation |
| Evaluation evidence | Retain both cohort hashes, fit/validation counts, class counts, mature-label purges and vocabulary/feature counts; distinguish validation-model metrics from the final all-row fit. Report negative recall/calibration limitations without adding a new model gate or claiming independent-test accuracy |
| Embeddings/inference | Every reused input/vector retains compatible hashes and lineage; inference ledger contains only justified changed/new inputs. Zero poster or cloud requests. Unexpected regeneration or unexplained vector differences fails acceptance |
| Prediction/SHAP coverage | Staged and published prediction counts/hashes agree; probabilities finite in [0,1], ranks contiguous and ties follow the existing ordering; one candidate per user/canonical title; zero watched/suppressed canonical candidates under the existing policy, including its interested-feedback exception. Counts must match scoring metadata, including explicit user/history exclusions |
| Explanation context | At most 750 contexts per scored user, exactly the expected top min(750, user prediction count) where supported; 40 retained embedding contributions per context, indices 0–1535 and finite values. Every context references the published model/config; no old-model semantic description is silently attached to a new configuration |
| Atomic cutover | One new publication for this run; journal, canonical state, model/config and physical populations agree. An independently pinned read-only snapshot taken at cutover sees the complete old or complete new state, never a mixture within that snapshot. No normal reader is claimed to have cross-request snapshot consistency |
| Completion | Fresh workload exits 0, parent `success`, journal has `daily_completed` and final verification. An exit-76 recovery is valid recovery evidence but does not pass this fresh-workload gate |
| Optional labeling | Disabled/unauthorized/unbudgeted: zero requests. Authorized mocked-provider rehearsal: starts only after exact final verification, respects durable cumulative cost/request/per-prompt limits, reuses compatible labels/abstentions and recorded completion. A labeling failure or interruption never invalidates publication, changes numeric inputs/SHAP or triggers fitting/scoring. Real cloud exercise requires separate approval |
| Operations/rollback | All resource/availability budgets pass; the exact B1 rollback archive verifies and has capacity to restore; no unexplained failed/pending populations, stale worker or missing stage receipt |

Inspect interpretation inventory changes separately: a new model/config may intentionally archive incompatible labels. Pass requires this to follow the existing publication policy with a verified archive and honest display; do not run cloud labeling to replenish it during qualification.

Stop and record FAIL for identity/hash/contract discrepancies, failed quality gates, source drift at cutover, lost rollback evidence, unexpected inference, duplicate publication, resource errors or unexplained exclusions. Source drift rejection is a protective outcome, not a successful normal Q3 qualification. No automatic baseline rewrite or repeated production fit is authorized by one failed attempt.

Before cutover, use the approved cancellation path if intervention is required. During an uncertain commit, first resolve state through an independent read-only connection; do not repeatedly start workers or delete the transition marker. An emergency process/database action or production rollback requires explicit recovery authorization. A committed publication followed by failed final verification is not assumed rolled back.

## Q4 — Evidence and decision

Retain a private SHA-256 manifest covering B0/B1 and candidate source receipts, deployment identity, run/publication/model/dataset/materialization/cohort hashes, class/source reconciliation, inference ledger, stage events, resource time series, API results and rollback verification. Keep fault transcripts and original errors, sanitized for sharing. Record UTC times plus America/Chicago presentation times and monotonic durations.

The owner report must list each gate/budget as PASS/FAIL/NOT RUN, actual values, exclusions, deviations and outstanding risk. No full-size measurement or failure result may be replaced by the small-fixture results.

**GO for production acceptance only when Q0–Q3 all pass with no unexplained discrepancies and the owner accepts Q4 evidence.** A production rollback restores the verified prior code/model/receipt pair; it must not automatically bless the currently checked-out source. Scheduling remains disabled after acceptance until separately approved. Cloud labeling remains manual and separately authorized.

Current authorization: commit/push and Q0/Q1 preparation/execution within their stated boundaries. **Q2, Q3, real cloud labeling and scheduling remain separately gated.** Record actual PASS/FAIL/NOT RUN results and fresh baseline measurements in the qualification evidence; historical tests and this document do not establish production readiness.
