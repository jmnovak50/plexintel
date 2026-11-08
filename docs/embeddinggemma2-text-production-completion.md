# EmbeddingGemma 2 text-only production completion — 2026-11-05

## Execution status

Phase 2 physical publication, Phase 3 retirement and the separately authorized
single catch-up run have completed and passed physical-production and live API
verification. Recurring scheduling remains paused. This is an execution record; implementation
and manual commands are documented in
[the cutover runbook](embeddinggemma2-text-production-cutover.md).

## Published architecture

The production encoder is `embeddinggemma-2:latest`, immutable digest
`f4981a15b99858ad1f2e0729416e526be7b4f428291b40082b9e4f7b27b5f62f`,
variant `embeddinggemma-2:740m-q8_0`, Q8_0. Each native media-text and watch
vector retains all 768 dimensions and L2 normalization. Each user profile retains
the existing unnormalized mean of qualifying, rating-key-deduplicated media-text
vectors. The rich `plexintel-media/2.1` and behavioral `plexintel-watch/2.0`
serializers, qualification rules and 0.60 engagement policy remain in force.

`physical-text-production/1.0` / `semantic-text-user-prospective/1.0` consumes
`media_text_0..767`, then `user_0..767`, followed by training-fitted engineered
features and `watch_sim`. Poster vectors, `poster_missing` and old dimension
interpretations are excluded. Poster preparation/inference is disabled; ordinary
UI artwork retrieval remains available.

Physical vectors live in the existing `public.media_embeddings`,
`public.watch_embeddings` and `public.user_embeddings` tables. Canonical
`embedding_v2.production_state` stores the verified active model and feature
contract; `production_inputs` stores independent source hashes, native-vector
hashes and original lineage. Runtime loading does not redirect to shadow vectors.
The encoder generation remains fixed while `publication_id` identifies each
atomic model/data revision.

## Phase 2 — executed

The initial inspection found C already published, rather than legacy production.
All physical Gemma 2 vectors exactly matched the validated source generation.
Adopting the evaluated B booster therefore required **zero embedding inference
and zero model fits**. Every one of the original 9,279 historical training rows
passed exact B feature/label/weight/cutoff parity checks.

| Physical population | Expected | Verified exact | Dimensions |
|---|---:|---:|---:|
| Media text | 8,393 | 8,393 | 768 |
| Watch text | 9,586 | 9,586 | 768 |
| User semantic profile | 31 | 31 | 768 |

Publication materialized all three populations and new B predictions, SHAP,
diagnostic training rows, active dimension configuration and classifier/context
in a single transaction. Source, feature, model, population, code-receipt and
rollback checks preceded commit. Physical verification covered every vector and
the exact identity sets, not only representative samples.

- Text encoder generation: `782a70b2-6be2-4948-88ce-53495153df49`.
- Initial B publication: `e62a356e-ac95-402d-b89e-d62d9c383556`.
- Adopted B wrapper SHA256:
  `b3332f55bf1ba60d1dc59aaddb8021e74433cbf587d47c336683146ecf2abb68`.
- Feature contract hash:
  `cc4590f68547214ceab18f913b44f8d02a51f6051765279e3644d342d9d584d7`.
- Initial classifier: 1,605 features, including all 1,536 native text/user axes.
- Initial scoring: 223,767 predictions for 31 users, no limited-history skips;
  797.33 seconds inside scoring (823.80 seconds including wrapper overhead).
- Full vector/dependency/provenance validation: 20.38 seconds.
- Atomic publication: 161.30 seconds.
- Initial explanations: 930,000 SHAP contribution rows and 23,250 prediction
  contexts; embedding dimension indices restricted to 0–1535.

The existing systemd backend was deployed and restarted once, then passed real
authenticated HTTPS checks. The deployed runtime code SHA256 is
`447c183fc3875964d0de0d05ffc829a40a2220527d875d9afc66efc0feeac2c6`.
Ollama and Plex were not restarted. Frontend assets were built and deployed after
preserving the previous served build.

## Phase 3 — executed after verified publication

Verified full database backups and production HTTP/vector checks preceded
retirement. Removed redundant B staging only: 18,010 item rows, 16,048 dependency
rows, 8,393 metadata preparations and 9,279 staging training rows. Removed 447,534
redundant staged prediction rows across C/B, exported and cleared 2,724 inactive
ML poster-cache entries, and marked two abandoned historical stage runs
interrupted. Ordinary vacuum reclaimed **1,004,101,632 database bytes**.

Retained both generations' evaluation/model/provenance evidence and all original
rollback archives. C's 8,374 poster vectors, 19 missing-art records, historical
multimodal training matrix and exact prepared images remain necessary for
reproducibility and rollback. The 2,567 prepared-image files (5,439,943,203 bytes,
including 2,565 verified SHA-named PNGs) were moved into the inactive backup
archive, not deleted. The active ML poster cache is empty.

An identical duplicate source archive was replaced with a verified relative
symlink, reclaiming 29,020,187 bytes. Removed 55,325,350 bytes of disposable
temporary source/build output after preserving durable copies. No Plex source
media, ordinary artwork, watch history or user data was deleted. No operational
shadow worker or poster job remains scheduled. The existing PlexIntel cron entry
was already commented; the application scheduler remains disabled.

## One catch-up run

Run `8f29455a-797a-4898-983e-be4999c008d4` was invoked once through the existing
`run_daily_pipeline.sh` shared-lock entrypoint. Source synchronization uses the
normal incremental Plex/Tautulli importer with embedding side effects disabled;
the canonical text pipeline then handles changed inputs. Durable run/delta
checkpoints and connection-private work tables avoid a new permanent generation.
Publication preserves the last good B revision until all quality and integrity
checks pass. No automatic acquisition or recurring scheduler activation occurs.

Source synchronization and physical vector/model publication completed with the
following changes. All original library identities and watch events remain present.

| Library population | Before | After | Net new |
|---|---:|---:|---:|
| Movies | 1,854 | 1,857 | 3 |
| Shows | 292 | 292 | 0 |
| Seasons | 581 | 583 | 2 |
| Episodes | 5,666 | 5,678 | 12 |
| Total | 8,393 | 8,410 | 17 |

Watch history increased from 9,860 to 9,884 events; eligible events increased
from 9,586 to 9,610. The same 274 unlinked events for 153 absent titles remain
preserved and quarantined, with unchanged coverage hash
`c121d3c3e076c45f67bd7900ad6845efa14a4b95d825d411a31a611337d75a45`.

Completed inference: **18 media-text requests** (17 new, one existing episode's
changed runtime) and **24 watch-text requests**, all successful. Their measured
client inference totals were 12.262 and 10.687 seconds respectively. Ten user
profiles were rebuilt. No poster request occurred. Unchanged vectors were reused;
the permanent generation count remains two.

| Vector population | New inference | Existing regenerated/rebuilt | Reused | Validated total |
|---|---:|---:|---:|---:|
| Media text | 17 | 1 | 8,392 | 8,410 |
| Watch text | 24 | 0 | 9,586 | 9,610 |
| User semantic profile | N/A | 10 | 21 | 31 |
| Poster | 0 | 0 | N/A | Not part of production |

The rebuilt historical dataset contains 9,291 rows. The normal authorized daily
refit completed three fits and passed the chronological and show-heldout gates;
its model SHA256 is
`619b72f1209ef26a196ec89ddb52e8650226cf44e4e99cbf05f78ea5fda3ac46`.
This is a new text-only B refit, not the identical originally adopted weights.
It was published only after scoring, validation and all quality gates passed.

| Catch-up evaluation | Chronological | Show-heldout |
|---|---:|---:|
| Test rows | 1,859 | 449 |
| Balanced accuracy | 0.5786 | 0.6132 |
| Precision | 0.9387 | 0.9584 |
| Recall | 0.9855 | 0.9765 |
| Average precision | 0.9681 | 0.9806 |
| Trapezoidal PR-AUC | 0.9681 | 0.9805 |
| ROC-AUC | 0.7446 | 0.7608 |
| Brier score | 0.0625 | 0.0537 |
| Calibration ECE, 10 bins | 0.0350 | 0.0556 |
| NDCG@10 | 0.9504 | 0.9611 |
| Recall@25 | 0.5162 | 0.8104 |

The refreshed cohorts differ from the original B evaluation; metric changes are
not a controlled representation comparison. Ranking evaluates labeled heldout
candidates per user rather than the full catalog; Recall@25 saturates for small
cohorts. Calibration values describe the uncalibrated classifier. Historical
metadata is reconstructed from current sources, not point-in-time metadata
snapshots; temporal event safeguards do not eliminate that limitation.

Training exclusions were 532 candidate rows under the preserved label policy and
42 under limited-history safeguards. These are not failed vector requests and
are separate from the 274 quarantined historical source events.

Scoring completed **224,217 predictions for all 31 users**, with zero
limited-history scoring skips and no scoring failures. All **18,051 vectors**
passed full provenance/dependency validation. After commit, every physical vector
matched its canonical native-float32 hash and modality/model provenance, with
exact identity sets and zero pending/failed rows. Predictions, 930,000 SHAP rows,
23,250 explanation contexts and 9,291 diagnostic training rows use the newly
published text-only B model and its 1,605-feature configuration.

Latest publication: **`2a7cb696-478c-4d6b-9c79-5d34fa238d75`**. The encoder
generation remains `782a70b2-6be2-4948-88ce-53495153df49`; the permanent
generation count is still two. Current source hash is
`a9dad0b0e25d7be364fb00f6ab6496dd6ec6aa7796de552942ea6e24e08a9015`.
Exactly one production-run journal exists and its status is `succeeded`.

The post-run acceptance verified complete embedding coverage for every new media
identity and eligible watch event, preservation of old source identities, unchanged
quarantine hash, no mixed encoder generations, exact active feature/model identity,
zero poster requests, an empty active ML image cache, no legacy writer process,
no transition marker and a free shared pipeline lock. The backend remains active
at PID 503490 with zero automatic restarts. Real HTTP checks also passed against
the new publication, including recommendations, SHAP, dimension group boundaries
and normal UI artwork. Scheduling remains false and the existing cron line remains
commented. No new recurring job or acquisition action was enabled.

| Catch-up stage | Elapsed seconds |
|---|---:|
| Incremental source synchronization | 142.38 |
| Snapshot and temporary working context | 116.41 |
| Metadata preparation/change checks | 221.96 |
| Media-text stage | 12.79 |
| Watch-text stage | 14.95 |
| User-profile stage | 7.59 |
| Historical training features, evaluation and three text-only fits | 498.10 |
| Scoring and SHAP stage | 873.94 |
| Full vector/provenance validation | 20.52 |

Measured pipeline work before publication was 1,940.64 seconds. Stage times
include checkpoint/database overhead; the separately reported 12.262/10.687
seconds measure actual Ollama client requests. Poster preparation, preprocessing
and inference took zero time in this pipeline. The wrapper measured **2,166.32
seconds (36 minutes 6 seconds)** end to end, from 10:25:48 to 11:01:54 CST
(16:25:48–17:01:54 UTC). Publication plus launcher/closing overhead accounts for
the remaining 225.69 seconds. The CLI's `elapsed_seconds` field is explicitly the
pre-publication interval; it must not be mistaken for the total wall time.

## Quality and verification

The original matched evaluation is retained: B chronological balanced accuracy
0.5796, PR-AUC 0.9696, ROC-AUC 0.7592; show-heldout balanced accuracy 0.6006,
PR-AUC 0.9837, ROC-AUC 0.7983. Selecting B is an approved cost/quality tradeoff;
C had higher balanced accuracy in that evaluation. These are original model
results, not claims about a later daily refit.

Target-title exclusion, historical activity/observation cutoffs, chronological
validation, show-heldout evaluation and fold-only vocabulary fitting remain
enabled. Daily refits must pass chronological balanced accuracy >=0.50,
chronological average precision (AP) no more than 0.05 below the current model, and show-heldout
balanced accuracy >=0.50. There is no silent publication of an unchecked refit.

Full regression: **791 passed, 224 skipped, 89 subtests passed**, 119.27 seconds;
one pre-existing FastAPI ORJSON deprecation warning. The retirement-specific
focused suite subsequently passed **11 tests**, including real PostgreSQL
publication/rollback, same-generation journal resume, latest-revision rollback
ordering, cleared-staging independence, unchanged-vector reuse and no-poster
source/embedding paths. TypeScript passed; Vite built 1,760 modules. Diff whitespace
checks passed.

Real authenticated HTTP acceptance passed before and after retirement: canonical
text-only identity, unauthorized admin rejection, recommendations for three users
across movies/episodes, Dimension Explorer text/user groups and boundary axes
0/767/768/1535, prediction SHAP, root/admin SPA routes, served JS/CSS hashes and
ordinary poster image decoding. No interactive browser engine was available;
this verifies live HTTP behavior and built assets, not visual browser automation.

## Recovery and retained evidence

Private execution directory:
`artifacts/embeddinggemma2/deployment-backups/text-cutover-20261105T151401Z/`.
It contains model/source/frontend/configuration backups, deployment receipts,
validation and HTTP evidence, retirement inventory and the single-run log.
Configuration backups contain secrets: retain private access and do not commit
this directory. `active-text-B-model.pkl` is an exact checksum-verified copy of
the final classifier (`619b72f…`); the canonical active bytes also reside in the
verified post-catch-up database backup. Immutable generation artifact exports
retain the initial release's artifacts; use the current publication receipt and
canonical production state to identify a later daily refit.

| Database backup | Bytes | SHA256 | Verification |
|---|---:|---|---|
| `database.dump` (before cutover) | 1,096,923,498 | `f8e328afadb111ce1de0ee0b5d23830303bc956ee13b9b73d69c640d469a5de4` | Archive list and complete restore stream read |
| `postcutover.database.dump` (B before retirement) | 1,961,152,738 | `003129aed860133e39f79afaa5c326b3b4668efa3e212bf69f83a04117a18be3` | Archive list and complete restore stream read |
| `postcatchup.database.dump` (final caught-up B) | 1,585,215,910 | `8103c49426a87d3ed3efad22e181f1c333459e8a9b3342995830c0d80a0f6d04` | Archive list and complete restore stream read |

Database archives were fully read using `pg_restore --file=/dev/null`; they were
not restored over the live database. Rollback behavior was separately exercised
against private PostgreSQL test tables, including injected publication failures
and corrupt-archive rejection. Initial B publication archives C; the original C
publication `2a06966a-d84d-44f5-90a8-9ef11dcece66` independently archives legacy
vectors/model/configuration and explanations. Its full twelve-table hashes and
typed 8,393/9,586/31 vector populations were reverified.

Rollback must proceed newest publication first, even when the encoder generation
has not changed. Keep writes and scheduling paused, identify the active
`publication_id` from authenticated admin status, then use the existing guarded
command:

```bash
cd /home/jmnovak/projects/plexintel
LATEST_PUBLICATION=2a7cb696-478c-4d6b-9c79-5d34fa238d75
plexenv/bin/python scripts/embeddinggemma2_migration.py rollback \
  --promotion-id "$LATEST_PUBLICATION" --approved-production-change
plexenv/bin/python scripts/embeddinggemma2_migration.py verify \
  --generation 782a70b2-6be2-4948-88ce-53495153df49
```

The command above is a recovery operation, not a remaining deployment step.
For full reversal, restore the catch-up revision to initial B first, then initial
B publication `e62a356e-ac95-402d-b89e-d62d9c383556` to C. Extended C operation
requires the preserved compatible application source/build and a reviewed
restart; keep the pipeline paused. Only after returning to C may its older
legacy rollback be applied. Do not bypass revision guards or manually delete
transition markers. Original source commit `b4f12ba`, model files, exact C inputs
and all three database snapshots remain available.

## Remaining limitations

- Recurring scheduling stays paused until separately approved. Readiness does
  not mean a timer or cron entry was enabled.
- Historical descriptive metadata has no point-in-time snapshots. The evaluation
  is leakage-corrected for event/profile construction, with the stated metadata
  limitation; it is not proof of fully prospective recommendation accuracy.
- Original C/poster inputs remain intentionally retained for recovery and
  reproducibility. Their bytes were not claimed as reclaimed storage.
- Publication rollback archives and durable run journals accumulate with daily
  operation. A reviewed retention policy is still needed; this execution does not
  automatically delete recovery evidence.
- No interactive browser engine was available. Real HTTPS routes, API behavior,
  UI asset integrity and frontend compilation passed; visual acceptance remains
  an operator check.

## Acceptance decision

**GO for normal text-only daily operation when the operator separately resumes
scheduling.** Physical production, model/feature compatibility, new-input coverage,
quality gates, live API behavior, rollback retention and the shared execution lock
passed. The single authorized catch-up completed; no second run, new shadow
generation or full embedding rebuild is needed to finish this migration.

## Commit synopsis

Adopt validated Gemma 2 text-only embeddings and B classifier into physical
production tables; add resumable, changed-input daily processing with no poster
inference; preserve rich metadata, leakage safeguards, atomic model/prediction
publication, provenance, native text/user dimension reporting and verified rollback.

No commit or push was performed. Operational databases, image caches, model
binaries, credentials, backup archives and private evidence are not commit content.
