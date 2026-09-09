# Dimension & Label Explorer

Open **Admin → Dimensions & Labels** (`/admin/dimensions`). Every API read and action uses the existing server-side `require_admin` dependency. The register includes unlabeled and unobserved positions. Search returns dimensions, not unique wording; shared wording can match multiple rows. Scope, search, sorting, pagination and drilldown identity live in the URL.

## Install / start

Run these commands **in `/home/jmnovak/projects/plexintel` on the model/pipeline host**, using its existing `.env` database configuration and existing ML environment. No code needs to be pasted into Python files.

```bash
cd /home/jmnovak/projects/plexintel
./plexenv/bin/python scripts/migrate_dimension_explorer.py
./plexenv/bin/python scripts/register_dimension_config.py --model xgb_model.pkl
cd frontend
PATH=/opt/homebridge/bin:$PATH npm run build
cd ..
```

The build command includes the Node/npm location verified on this host (`/opt/homebridge/bin`); an existing npm elsewhere on PATH still works.

The first command applies only the additive SQL in `api/db/migrations/`. Normal API/CLI startup also applies those migrations via `api/db/schema.py`. The second reads the trusted local model artifact and the database vector-column widths, verifies contiguous `emb_*` feature names, and records observed configuration metadata. It does **not** train, score, relabel, import CSV history, or associate old SHAP rows with a model. Use `--inspect-only` to inspect metadata without registering it. Registration refuses to reassign an incompatible active configuration; changing embedding models/layouts requires an explicit data migration outside this feature.

For the repository's Docker deployment, run from that same project root:

```bash
docker compose up -d --build backend
```

For the documented direct Python deployment, start the backend from that same project root:

```bash
./plexenv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8489
```

Use the deployment method already operating your installation. Targeted reviews require the full checkout and ML environment on the API/pipeline host, just like existing pipeline stages. The slim API image alone does not contain the labeling scripts/ML dependencies; the repository compose mount provides the checkout. The UI reports execution errors if that environment is unavailable. All launch environments must share the existing `PIPELINE_LOCK_PATH` (default `logs/daily-pipeline.lock`).

No production migration, labeling, training, scoring or bulk update was run during feature development.

## Verified feature contract

`build_training_data.py:process_row` calls `user_profile_embeddings.py:fuse_media_and_user_embedding`, which concatenates **media, then user**. `score_model.py:preprocess` uses the same ordering. `train_model.py:preprocess` generates contiguous `emb_0…emb_1535`, and saves those names on the booster.

The local `xgb_model.pkl` inspected during implementation is an `XGBClassifier` with `binary:logistic`, **1,605 total features**, including **1,536 embedding positions**. The repository vector columns and embedding implementation use 768 per side:

| Combined feature | Side | Local index |
| --- | --- | --- |
| 0–767 | media | combined index |
| 768–1535 | user | combined index − 768 |

Inventory comes from the registered, verified metadata, not label rows or a fixed `generate_series(0,1535)`. Non-embedding features are counted separately. Targeted labeling rejects unsupported side widths because the existing labeling implementation uses 768 per side. No embedding values, feature ordering, training labels, score/rank calculations, validation rules or SHAP computation/retention thresholds changed.

## Existing data versus new records

Existing: `embedding_labels` has wording, classification, display eligibility, unresolved state, last review, attempt count and next-review date. `embedding_label_history` retains selected old wording/governance revisions, but not every attempted review. CSV exports can contain evidence and validation; they are not assumed to be complete database history. The single-dimension CLI retains its existing acceptance/save behavior.

New: `embedding_feature_config` stores verified metadata; `embedding_dimension_admin` stores overrides separately from generated fields; `embedding_dimension_actions` records actor, time, configuration/dimension, reason and before/after override state. `embedding_dimension_reviews` is the durable targeted queue. `embedding_dimension_assessments` retains actual prompt items, HIGH/LOW samples, provider/model, validation, before/after label state and save outcome for future saved batch/single-CLI assessments after registration. Queue assessments have an explicit request ID. No historical records are synthesized.

New SHAP writes also populate `shap_prediction_context` with the exact prediction timestamp, feature configuration and model fingerprint. This adds provenance only. The model is read once so the fingerprint describes the loaded bytes. Only retained contexts are offered as model filters; stale timestamp associations and incompatible recorded configurations are excluded. New context metadata does not backfill old rows. Legacy observations remain in a separate, explicitly unverified scope. That legacy scope cannot establish whether its observations came from compatible historical models.

## Metric definitions and limits

- The scope selects current recommendations by user/all users, media type, stored **global rank per user**, and retained model snapshot or unversioned legacy data. Top 100 is the initial scope; zero means all ranks. Top-N filters the stored global rank, even when a media-type filter is applied.
- Observed count is distinct `(username, rating_key)` instances with a retained contribution for a dimension in that scope, not unique titles. Current tables replace earlier predictions. New verified contexts identify the paired `scored_at`; legacy SHAP lacks that association.
- Mean absolute SHAP uses finite retained contributions. Positive, negative, zero and unknown counts describe stored values. Missing observations are not zero contribution. The scorer already normalizes non-finite SHAP values to zero; this feature does not alter that behavior.
- SHAP targeting selects recommendations and truncates embedding contributions by existing count/cumulative-magnitude settings. The separate `shap_dimension_stats_current` snapshot has different retention and insufficient user/title detail, so the explorer does not mix it into scoped aggregates.
- **Selected by current explanation rules** reconstructs current eligibility, positive-only ranking, wording deduplication and group limits. It is not a historical display count or proof a user saw a card. API groups (`title_traits`, `taste_match`) select up to three wordings each; legacy `semantic_themes` selects up to three across sides. `selected_embedding_labels()` is shared by production and explorer SQL. A selected wording is counted once per prediction/group; its contributing eligible dimensions remain linked. Sum of dimension attribution counts can exceed the deduplicated wording total.
- API show/season rollups return empty explanation groups. The explorer does not invent leaf SHAP explanations for aggregate scores. Legacy semantic themes are separately identified. Card visibility (watch/feedback/threshold filtering) is separate from label selection; counts describe selection if rendered.
- The verified model's TreeExplainer output is raw margin/log-odds, not probability percentage points. Complete non-embedding contributions and compatible prediction base values are not retained. Bars compare individual retained signed contributions; there is no waterfall or additive reconstruction claim.
- Multiple saved rows for a dimension cannot multiply inventory/contribution totals: the register flags the conflict and shows the latest timestamped row. Production selection continues to reflect saved rows; no records are merged/deleted. Targeted review refuses conflicting rows.

Timestamp columns without timezone are displayed as database-local values; the UI does not invent UTC offsets.

The register calculates totals before pagination, using materialized scoped observations/selection and indexed dimension lookups. History joins cannot multiply contribution counts. Reads use a repeatable-read transaction and a 30-second statement timeout. The default top-N scope bounds ordinary work; all-rank queries can still be expensive. Query plans were checked on fixtures, not production volumes.

## Controls and execution

Every intervention requires a reason and an optimistic override version; stale updates return HTTP 409. Duplicate queued/running requests return the existing request. A partial unique index and transactional row lock prevent duplicate work, including simultaneous requests.

- **Request review/retry now:** queues one dimension, bypassing only its cooldown. It uses `batch_label_embeddings.py --dimension N --selection_mode review --label --save_label` in the existing pipeline execution environment. Validation and automated replacement acceptance still apply. It does not immediately change wording.
- **Pause/resume:** automatic selectors and both labeling CLIs respect the pause. Resume preserves the existing `next_review_at`: an elapsed date becomes eligible normally; a future cooldown remains. A paused dimension must be resumed before requesting a new assessment. Already queued work waits while paused. An in-flight assessment may finish; its save cannot erase the separate pause.
- **Suppress/restore:** the shared production selector honors suppression independently of classification. Scores/ranks do not change. Shared wording may still be selected through another eligible dimension. Restore removes only the override and cannot force automatic eligibility. Suppression does not pause reviews.
- **Flag/clear investigation:** stores a reason and open/clear state without changing scheduling or eligibility. Earlier reasons remain in action history.

A five-second dispatcher runs independently of the nightly schedule, checks for work, and acquires the existing pipeline file lock before spawning the targeted CLI. The child inherits that lock so a web-process restart cannot release it while labeling is still running. A shared per-dimension PostgreSQL advisory lock also serializes standalone CLI work. The UI detects these locks as in-flight state. Dispatcher interruptions are reported as `interrupted`, never guessed to be successful/failed reviews or automatically retried. Process output goes to the existing pipeline log. LLM processing errors and validation/review outcomes remain separate: a completed process can resolve nothing. The register includes recent retained `batch_label` stage results, explicitly global and outside the selected SHAP scope. Ordinary pipeline runs remain available under Admin → Pipeline runs; their execution success does not imply review progress.

Exception filters are transparent diagnostic views of the full register. `DIMENSION_EXPLORER_REPEATED_ATTEMPTS` defaults to 3: **currently unresolved with at least that many recorded attempts**, not proof of consecutive failures. `DIMENSION_EXPLORER_FREQUENT_SELECTIONS` defaults to 10 current API-group selections. These environment settings affect explorer filters only; they do not change automatic retry policy. Because unresolved labels are ordinarily ineligible, frequently-selected-under-review can correctly return no rows. Rejected candidate, overdue, cooldown, pause and processing-error states are separate.

## Walkthrough

1. Search wording in the register; shared text returns every matching dimension.
2. Select `emb_N` and check its side/local index, current wording, governance and active scope.
3. Inspect observed count, mean absolute SHAP and retained signed user/title rows.
4. Open a title to see its exact current prediction timestamp, selected wordings and attributed dimensions. If it was rescored, reload instead of treating the new prediction as the old one. Follow a dimension link or return with the scope preserved.
5. Expand actual assessment evidence and recorded wording/action history. Missing older evidence is explicitly identified.
6. Enter an intervention reason, apply one dimension-level action, and inspect queued/running/outcome state. A successful execution and a resolved review are different results.

## Validation

From the project root:

```bash
./plexenv/bin/python -m pytest -q tests --ignore=tests/test_dimension_explorer.py
cd frontend
npm run build
npm run lint
cd ..
```

The existing Python suite passed (360 tests plus 34 subtests). Frontend build passes; lint has two existing warnings in `Recommendations.tsx` and `ThemeContext.tsx`. The 13 new explorer tests passed against an isolated PostgreSQL fixture server; they are in `tests/test_dimension_explorer.py`. Its database tests **refuse every database name except `plexintel_explorer_fixture`** and reset fixture tables, so use a dedicated empty test server, never a production database renamed for testing. Initialize that database with the vector extension and `create.sql`, then run, from the project root:

```bash
EXPLORER_TEST_DATABASE_URL=postgresql://TEST_USER@localhost:55439/plexintel_explorer_fixture \
DATABASE_URL=postgresql://TEST_USER@localhost:55439/plexintel_explorer_fixture \
./plexenv/bin/python -m pytest -q tests/test_dimension_explorer.py
```

Replace `TEST_USER` with the local test-server owner. Without the fixture URL, database tests skip explicitly. Coverage includes inventory/mapping, search, scoped signs/counts, deduplication and rollups, unauthorized reads/actions, overrides/audit/stale updates, simultaneous enqueue requests, pause/locking, actual valid-but-unresolved saves, exact request outcomes, model/context isolation, and `EXPLAIN (ANALYZE, BUFFERS)`.

The built register, dimension detail and user/title explanation were visually checked in headless Firefox against a localhost preview explicitly marked as fixture data.

Live LLM execution, production query plans/load, legacy model/run associations and unavailable original historical evidence remain unverified. Fixture data is never served as production evidence.
