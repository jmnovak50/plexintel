# Semantic dimension labeling

The original HIGH-versus-LOW labeling workflow is restored for the active
EmbeddingGemma 2 text generation. It reads **Ollama Label Model in Setup**
(`labeling.ollama_model`), currently `gemma4:31b-cloud`, through the existing
Ollama integration. Both batch labeling and Dimension Explorer review use this
setting. An explicit CLI `--label-model` overrides it for that invocation only.
The resolved model and configuration source are shown in the forecast and stored
with results. Manual batches and Dimension Explorer reviews remain available.
The local integration adds an optional post-publication daily stage using this
same implementation; it is not deployed or enabled by this document.

Labels are approximate semantic interpretations of coordinates. They are not
proven causal explanations of XGBoost predictions. Prediction probabilities,
ranking, training data, embedding arithmetic and SHAP computations are unchanged.

## Optional automatic daily stage

The daily CLI calls `pipeline_labeling.run_after_publication()` only after the
existing worker has published and completed final verification. The adapter
reuses `Evidence`, `candidates`, `choose`, forecasting, `execute`, `UsageLedger`
and existing persistence/governance. There is no second labeler, embedding
inference or classifier fit. It shares the existing execution lock and verifies
the exact successful run/publication/model before evidence or provider work.

The stage runs synchronously after the predictive workload, but its failures do
not block or invalidate publication. Its outcome is independently visible as
`semantic_labels`, in the production journal's `semantic_labeling` summary and
the existing admin pipeline views. Batch summaries retain selected/saved,
abstained, failed and unprocessed counts, usage and conservative costs. Interrupts
retain committed batch summaries when available; unavailable metering remains
explicit. The parent/model run stays successful after an optional-stage error.
Verification-only recovery (exit 76) starts no labeling and changes no unrelated
run's labeling record. Core and complete worker durations are reported separately.

| Setting / existing control | Automatic behavior |
| --- | --- |
| `pipeline.labeling_enabled` | Existing enablement switch; **insufficient by itself**, including its historical `true` value |
| `pipeline.labeling_cloud_authorized` | New standing authorization, default **false**. Explicitly permits transmission of the existing prompt evidence to the configured cloud interpreter; viewer names are aliased, but titles and engagement evidence remain potentially sensitive |
| `pipeline.labeling_budget_usd` | New cumulative automatic reserved/estimated USD ceiling, default **0** |
| `pipeline.labeling_request_limit` | New cumulative automatic provider-attempt limit, default **0**; includes retries, pending and interrupted requests |
| `labeling.provider`, `labeling.ollama_model` | Existing Setup provider/model. Current-generation batches require `ollama`; normal Gemma 4 choice is `gemma4:31b-cloud`. Unknown model pricing blocks requests |
| `labeling.ollama_host`, `ollama.host`, `ollama.api_key` / key file | Existing label endpoint, fallback host and credentials; never the embedding model setting |
| `pipeline.label_batch_limit`, `pipeline.label_dim_type` | Existing per-publication selection limit (default 25) and media/user/all scope |
| `pipeline.label_selection_mode` | Existing current-generation `eligible` or `importance` selection. Legacy `coverage`/`hybrid` are rejected with an optional-stage failure, not silently reinterpreted; `label_coverage_share` is therefore not used here |
| `pipeline.refresh_existing_labels` | Existing explicit refresh control, default false. Compatible saved labels and identical-prompt abstentions are reused by default. Refresh is bounded to selected dimensions and skips outcomes already saved/abstained for that publication |
| `labeling.max_output_tokens`, advanced labeling settings | Existing output cap, evidence counts, HIGH coverage, LOW overlap, and governance rules |
| Existing batch parser/provider retry controls | Three attempts and fail-fast threshold three by default; transient retries use the existing backoff, permanent errors stop retrying. Automatic attempts for the same generation/dimension/prompt are counted across batches, so restarting cannot reset the three-attempt allowance |

The three new settings appear through the existing generic Pipeline settings UI;
no new screen or configuration subsystem is required. Their environment aliases
are `PIPELINE_LABELING_CLOUD_AUTHORIZED`, `PIPELINE_LABELING_BUDGET_USD` and
`PIPELINE_LABELING_REQUEST_LIMIT`. Enablement, authorization and positive limits
must all hold before requests. The four controls resolve in one strict database
read; environment defaults apply only after a successful read establishes that
no stored override exists. An unavailable database or malformed policy blocks
requests rather than falling back to stale environment authorization or limits.

Automatic accounting uses the existing batch/request tables. Batch forecast JSON
records scope `daily-semantic-labeling/1`, run/publication and prompt hashes.
One advisory-locked reservation transaction sums all automatic requests across
every batch UUID, model/publication change and restart before inserting a new
reservation. Old pending attempts stay charged. Automatic successes retain at
least their original conservative reservation; larger metered estimates are
charged. Budgets are **not daily allowances**: an operator must explicitly raise
the cumulative ceilings to authorize more work. Manual CLI budgets remain their
existing separate per-batch scope. Do not delete usage history to reset a limit.
The existing read-only `--usage` report adds an `automatic` total, separate from
manual batches, so cumulative pending/retry consumption can be reconciled.

Each reservation rereads the complete policy **after** acquiring the cumulative
accounting lock, using the same READ COMMITTED transaction as the durable request
insert. A short SHARE lock on the settings table prevents policy updates and
inserts for missing keys until that reservation commits. Settings-lock contention
fails closed immediately (`NOWAIT`); an old REPEATABLE READ snapshot is rejected.
Thus a committed revocation/reduction before reservation cannot be bypassed by
earlier startup settings. No settings lock spans cloud I/O. Reservation commit is
the authorization boundary: later policy changes govern subsequent reservations
and cannot cancel a request already admitted. Unrelated generic settings retain
their existing fallback behavior; no settings schema or admin screen changed.

These controls enforce request counts and a conservative estimated ledger ceiling,
not an exact provider invoice: token estimation, prices and provider billing can
differ, and one response can report consumption above its reservation. No further
request starts once the cap is exhausted. Use provider-side spending/credit controls
when an invoice-level ceiling is required. All rates remain model-specific; no new
price lookup or provider request occurs merely to configure this integration.

Terminal same-publication outcomes are reused from the run journal or batch ledger,
including a crash between batch completion and journal annotation. Partial refresh
reuses saved/abstained assessments; exhausted prompts are skipped so other dimensions
can progress. New assessments are tagged `daily-pipeline`; manual assessments keep
their existing source. Label, generation, contract, encoder, model/publication and
SHAP provenance checks remain in the existing implementation.

Before unattended enablement: review/commit/deploy the final source under separate
approval, explicitly register its matching deployment receipt, verify the existing
`005_semantic_dimension_labeling.sql` ledger/provenance schema, confirm endpoint/model
and pricing, grant standing evidence-transmission authorization and set finite
cumulative limits. Choose supported selection settings. Scheduling remains disabled;
real cloud requests and scheduler activation still need separate approval. No new
schema migration, production receipt or live batch was created by this local work.

Local integration validation, November 11, 2026: **342 focused tests passed**
(28 opt-in skips), **1,082 full offline tests passed** (303 skips, 89 subtests;
one existing FastAPI/ORJSON warning), and **29 automatic-label adapter checks
passed** with PostgreSQL enabled (20 mocked adapter checks and nine real
temporary-table ledger/engine checks). Cloud responses were mocked throughout.
The PostgreSQL cases cover new UUIDs, pending reservations, true retry numbering,
exhausted prompts, authorization revocation, labels, abstentions, errors and
interruptions. Cached batch reuse reports zero new requests. Numeric hardening
and canonical-identity regression tests remain passing.

Relevant reproduction from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 PLEXINTEL_TEST_TEMP_DB=0 \
PLEXINTEL_LABELING_TEST_DATABASE_URL='' PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' \
PLEXINTEL_AGENT_SERVICE_SCOPES=plexintel.read \
  plexenv/bin/python -m pytest -q -p no:cacheprovider tests

PYTHONDONTWRITEBYTECODE=1 PLEXINTEL_TEST_TEMP_DB=1 \
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' \
  plexenv/bin/python -m pytest -q -p no:cacheprovider tests/test_pipeline_labeling.py
```

The second command creates only synthetic, connection-private PostgreSQL tables;
it does not opt into the separate permanent-schema manual-label tests. No real
provider, embedding regeneration, production fitting, deployment or scheduling
action is part of these tests.

Authorization-correction validation, November 11, 2026: **157 targeted tests
passed**, including the settings, labeling and PostgreSQL policy tests; **1,092
full offline tests passed**, with 316 opt-in skips, 89 subtests and the existing
ORJSON deprecation warning. All SQL tests in that targeted run used a disposable
local PostgreSQL cluster, including isolated schemas and connection-private
tables; they did not connect to production. New cases assert zero provider calls
on settings outages with authorized environment values, conflicting stored
revocation, invalid policy, committed budget/request reductions, revocation while
waiting for reservation admission, settings-write contention, stale transaction
snapshots, connection loss and reservation commit failure. Authorized operation
and cumulative pending charges across restarted ledgers remain covered. Reproduce
the new SQL cases only with `PLEXINTEL_LABELING_TEST_DATABASE_URL` pointing to an
explicitly disposable test database; that existing opt-in fixture creates and
drops isolated test schemas. Run `tests/test_labeling_policy.py` alongside the
labeling/settings suites. No real cloud request, production write, commit,
deployment, receipt registration or scheduling change was performed.

## Operator commands on birch

Run from the production checkout with its existing model-host environment:

```bash
cd /home/jmnovak/projects/plexintel
```

Export the accumulated current-generation results without inference or database
writes (both `--export-csv` and the original `--export_csv` spelling work):

```bash
mkdir -p -m 700 .secrets/label-exports
plexenv/bin/python batch_label_embeddings.py --export-csv .secrets/label-exports/current-generation.csv
```

Export one batch, including failures, abstentions and unprocessed dimensions:

```bash
plexenv/bin/python batch_label_embeddings.py --export-csv .secrets/label-exports/batch.csv --batch-id 02ffcd06-acb4-4e84-9be8-a2d9450a4065
```

The snapshot includes one latest applicable assessment/request outcome per
dimension, plus current saved labels with no assessment. `label` describes that
attempt; `final_saved_label` and `final_*` describe the current saved state, which
can remain valid after a subsequent failed attempt. Batch exports use the saved
state recorded at assessment time, explicitly marked by `final_state_scope`.
Generated-label eligibility is computed under the current governance rules;
historical saved-state columns preserve what the batch recorded. No history is
rewritten. SHAP relevance columns describe the current matching model/prediction
context, not a reconstructed historical snapshot.

Existing assessments are linked to batches only when model, dimension, request
records and timestamps identify a unique batch (`legacy_time_window`); uncertain
links remain unassigned. New assessments store the batch UUID directly. Batch
rows aggregate all request attempts for a dimension, including failed retries;
`failed_attempt_count` and `request_error_codes` retain their failure information.
Snapshot costs cover only the exported latest outcomes, not lifetime usage.
Missing token counts stay blank; partial known sums are flagged by
`token_totals_are_complete=False`. Estimated USD uses the existing ledger and
can include reservations for pending/unmetered requests, shown by `cost_basis`.

Exports retain applicable original CSV column names and add batch, usage,
outcome and provenance fields. Files use UTF-8 with a BOM, quoted fields and
Excel-compatible newlines; formula-like text receives a protective apostrophe.
Files are created/replaced atomically with mode 0600. Evidence remains private
local data; raw prompts, prompt examples and arbitrary exception messages are
excluded. CSV files and `.secrets/` are ignored by Git. `--dim-type` and explicit
dimension filters apply; the labeling batch `--limit` does not truncate exports.
Do not combine export with labeling, saving, regeneration or usage-report flags.

Forecast the first 25 eligible dimensions in existing SHAP priority order,
without inference or label writes:

```bash
plexenv/bin/python batch_label_embeddings.py --dry-run --dim-type all --limit 25
```

Label and save that batch, with an optional $1 batch budget:

```bash
plexenv/bin/python batch_label_embeddings.py --label --save-label --dim-type all --limit 25 --budget-usd 1.00
```

Continue with another batch, or resume after interruption, using the same command:

```bash
plexenv/bin/python batch_label_embeddings.py --label --save-label --dim-type all --limit 25 --budget-usd 1.00
```

Each invocation skips successfully saved current-generation labels by default.
Completed abstentions are also skipped while their exact prompt remains unchanged.
Failures and interrupted dimensions without committed results remain retryable.
Every request has a durable usage reservation before inference; a killed process
can leave unknown-metering reservations, which remain visible in usage reporting.
An interruption after a response but before its label transaction commits can
require a new request; the original request’s consumption is still retained.

Forecast all remaining eligible dimensions:

```bash
plexenv/bin/python batch_label_embeddings.py --dry-run --all --dim-type all
```

View accumulated labeling usage and estimated cost:

```bash
plexenv/bin/python batch_label_embeddings.py --usage
```

Use `--usage --batch-id UUID` for one batch’s per-request and retry details. The
batch UUID is printed with progress and final statistics. `--dim-type media` or
`--dim-type user` restricts a batch; `all` includes both. Use `--limit 50`,
`--limit 100`, or `--all` for larger manually initiated batches.

Explicit regeneration of selected dimensions:

```bash
plexenv/bin/python batch_label_embeddings.py --label --save-label --regenerate --dimensions 17 802 --budget-usd 0.25
```

Replace those example indices with eligible dimensions you actually intend to
regenerate. Regeneration requires explicit indices; it is never a silent full
backfill. The existing single-dimension entry point also supports the restored
workflow, for example `label_embeddings.py --dimension 17 --dry-run`.
Existing underscore spellings such as `--dry_run`, `--dim_type`, and
`--save_label` remain supported. Coverage/hybrid expansion remains available in
the legacy implementation; the restored Gemma 2 CLI uses current-context SHAP
importance, eligible selection, or explicit review selection.

## Forecasts, pricing and spending limits

Every dry run and normal batch assembles the actual HIGH/LOW prompts and reports:

- Eligible, already labeled, completed abstention and remaining counts for media
  and user dimensions separately.
- Selected-batch expected and high-use requests, input/output/total tokens and USD.
- All remaining media, user and combined workloads with the same estimates.

The first forecast uses UTF-8 byte length / 3 plus 32 tokens for the complete
system and user prompts, and byte length / 2 plus 64 for the high envelope. This
is an approximation, not Gemma’s exact tokenizer. Expected output starts at
256 tokens; the default output cap is **1,024**, configured by **Label response
token limit** in Setup (`labeling.max_output_tokens`) or overridden with
`--max-output-tokens`. Expected requests allow approximately
10% retries, rounded separately per side; the high envelope assumes all three
attempts at the output cap. Forecasts assume no cache discount.

Published [Gemma 4 Cloud pricing](https://ollama.com/library/gemma4:31b-cloud),
checked November 8, 2026, is **$0.14 input, $0.05 cached input and $0.40 output
per million tokens**. Prices are configurable using `--input-price`,
`--cached-input-price` and `--output-price`; all are USD per million tokens.
Published defaults follow the configured model; the verified `gpt-oss:120b-cloud`
rates are $0.15/$0.014/$0.60, and `gpt-oss:20b-cloud` rates are
$0.07/$0.035/$0.30 (input/cached-input/output per million tokens). A different
Setup model without verified defaults requires all three explicit pricing
options; Gemma pricing is never silently applied to another model.
Recheck [Ollama pricing](https://ollama.com/pricing) before a later large batch.
These amounts estimate usage-credit consumption; account credits, subscription
fees, taxes and the provider’s invoice are separate.

Ollama’s `prompt_eval_count`, `prompt_eval_cached_count` and `eval_count` are
retained for each attempt when provided. Missing values stay unknown. Missing
cache counts receive no presumed discount. Known token totals, missing-count
counts, retry consumption, cumulative estimated cost, averages per completed
dimension, forecast variance and updated remaining-work forecasts are reported.

After ten successfully metered requests, subsequent forecasts use observed
input-estimate ratios, output lengths and retry rates. Media and user estimates
use their own measurements after ten on that side; until then, pooled measured
values are clearly identified. Partial batches compare their consumption to the
full selected forecast with an explicit partial-completion caveat.

`--budget-usd` reserves a conservative input estimate and the output cap before
**each attempt**, including retries. It stops launching requests when the next
reservation would exceed the batch budget. Measured usage replaces reservations
when available; unknown or interrupted requests retain conservative estimated
costs. No estimator can guarantee an exact billing ceiling if the provider’s
metering or tokenizer differs. Output caps and thinking-disabled requests bound
normal response generation; they do not assert provider billing guarantees.

## Compatibility, governance and evidence

Media dimensions 0–767 use the corresponding coordinate in current physical
media-text vectors. User dimensions 768–1535 use user coordinates 0–767, with the
original positive-training/engagement-qualified supporting media examples. User
profiles retain their unnormalized mean; no vectors are renormalized or inferred.
Cloud prompts replace account names with batch-local viewer aliases while
retaining the original per-user sampling and preference framing.

All source vectors are checked against canonical generation records, encoder
digest, width, finiteness and vector hashes. Constant coordinates, unsupported
layouts, insufficient valid HIGH/LOW evidence, paused dimensions and dimensions
without relevant current-model SHAP observations are ineligible. HIGH and LOW
user tails remain disjoint, including tied coordinate values. Full-population
quality counts are retained when caching user preprocessing; cached and original
prompt/evidence selection must match exactly.

The existing JSON label contract, confidence/coverage checks, abstention,
governance classification, review cooldowns, suppression and evidence/history
storage remain in use. Valid eligible labels can appear without a mandatory human
approval step. Labels needing review remain ineligible through the existing
policy. Failed or unclear attempts do not overwrite good saved labels.

Governance recognizes complete format descriptions such as “episodic drama
series” and “standalone movies and series” as structural. Runtime and release
metadata are also ineligible. A format or genre word alone does not exclude a
narrative interpretation such as “series about police corruption.” Structural
interpretations remain visible in Dimension Explorer.

Explanation eligibility uses the complete validated result, including confidence,
validation status, HIGH coverage and LOW overlap against the applicable prompt
thresholds (normally at least 70% HIGH and at most 40% LOW). A downgraded
interpretation can remain stored with its original confidence and evidence, but
cannot enter semantic explanations. This adds no human approval requirement and
does not change the validator's abstention or replacement rules.

New labels record feature configuration, generation, contract hash, encoder
digest and interpretation model. Assessment history retains confidence,
explanation, evidence, original prompt examples and validation metadata.
Dimension Explorer displays labels and assessments through its existing views;
its manual review action is enabled for the current text/user layout. A review
uses one dimension; use the CLI for a batch forecast and budget.

The eligible explanation path additionally requires compatible label provenance
and a current matching SHAP/model/prediction context. Historical labels from the
previous encoder remain retired. A same-numbered coordinate or stale SHAP context
is insufficient. Other embedding migration/writer safeguards remain enabled.

## Ollama and deployment

The default endpoint is the existing `ollama.host`; its daemon uses the existing
signed-in cloud configuration. No embedding endpoint/model setting is changed.
Optional `labeling.ollama_host` / `OLLAMA_LABEL_HOST` selects a label-only endpoint.
Direct `https://ollama.com` uses the optional secret `ollama.api_key` /
`OLLAMA_API_KEY`, or `OLLAMA_API_KEY_FILE`. The `-cloud` model suffix is mapped to
the direct API’s registered model name. Credentials are neither logged nor
committed. Requests do not follow redirects.

Connect timeout is 10 seconds; response timeout uses the existing
`ollama.timeout_s` setting. Transient connection/server/rate-limit failures have
bounded retries; permanent HTTP errors and invalid structured responses do not
repeatedly consume inference. Failed dimensions do not stop subsequent work.

The additive `005_semantic_dimension_labeling.sql` migration adds label
provenance and the batch/request usage ledger. Deployment uses the existing
direct-host `plexintel-backend.service` and rebuilt frontend assets. The Docker
distribution image remains separate; no container is deployed on birch.

The Concept Discovery worktree, private experiment data, packets and local
branch were explicitly retired. No remote research branch existed and no
experiment files had reached `main`; main history was not rewritten.

## Verification and recovery

Automated tests use fictional evidence and mocked cloud responses. Optional
PostgreSQL integration checks create/drop isolated `test_labeling_*` schemas and
exercise real persistence, retrieval, provenance rejection, metering and budgets;
they never write production labels. Set `PLEXINTEL_LABELING_TEST_DATABASE_URL`
explicitly to enable them.

```bash
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' PLEXINTEL_AGENT_SERVICE_SCOPES='plexintel.read' \
  plexenv/bin/python -m pytest -q tests
```

Use an isolated test DB configuration for unit tests; deployment-specific auth
settings must not supply test entitlements. The operator’s production API token
file and scopes are not changed by the command above.

Private rollback sources, previous served assets, protected-table checksums and
deployment verification receipts are retained under
`.secrets/semantic-labeling-restore-20261109T035218Z/`. No catalog evidence,
account identities, operational credentials, model binaries or private receipts
belong in Git. Roll back source/assets and restart the same backend service if
necessary; the additive schema and usage history can remain. Keep the deployed
code receipt synchronized through the normal deployment registration; do not
disable its mismatch checks. Do not restore a different classifier or embedding
generation as part of a labeling rollback.

## Completed deployment verification — November 8, 2026 (Central time)

The direct-host backend and public frontend passed live HTTP verification.
The configured Setup model is `gemma4:31b-cloud`. Authenticated
Dimension Explorer, coordinate boundaries 767/768/1535, catalog health and
recommendations returned 200; anonymous admin access returned 401. Served local
and public frontend asset hashes matched. The backend is active with no automatic
restarts. Previous frontend assets were retained for cached pages.

Deployed runtime code SHA256:
`f4089006c8ccb6aabe2412406e593eec360b676eda170f45b0a920594aca0188`.

All eleven protected production table row checksums matched the pre-deployment
snapshot, including physical media/watch/user vectors, training rows, predictions,
SHAP, feature configuration and retired/empty label tables. The active encoder
generation, classifier and publication identity are unchanged. The in-app pipeline
scheduler remains false and the pre-existing cron line remains commented.

Validation: **793 passed, 264 skipped, 89 subtests passed** in the full regression
suite; **eight additional opt-in PostgreSQL integration checks passed** (31 tests
in the labeling-focused run, including 23 unit checks). TypeScript and the Vite
production build passed. Existing ORJSON and outdated Browserslist warnings were
observed. Optional skipped tests are not claimed as executed.

The real-data forecast used all actual assembled prompts and current canonical
vectors, with **zero label requests or label writes**. It found 603 eligible
media dimensions and 345 eligible user dimensions; none are already labeled.
The first 25 in SHAP priority order contain 20 media and 5 user dimensions.

This historical table used the original 420-token cap. Current 1,024-token
forecasts and the first-batch parser correction are recorded in
[the incident report](semantic-labeling-first-batch-fix.md).
Each cell below is **expected / high-use**, including the original retry assumptions:

| Workload | Dimensions | Requests | Input tokens | Output tokens | Estimated USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| Selected media | 20 | 22 / 60 | 74,294 / 304,881 | 5,632 / 25,200 | $0.012654 / $0.052763 |
| Selected users | 5 | 6 / 15 | 24,758 / 93,081 | 1,536 / 6,300 | $0.004081 / $0.015551 |
| Selected combined | 25 | 28 / 75 | 99,052 / 397,962 | 7,168 / 31,500 | $0.016734 / $0.068315 |
| Remaining media | 603 | 664 / 1809 | 2,239,333 / 9,179,715 | 169,984 / 759,780 | $0.381500 / $1.589072 |
| Remaining users | 345 | 380 / 1035 | 1,556,621 / 6,375,894 | 97,280 / 434,700 | $0.256839 / $1.066505 |
| Remaining combined | 948 | 1044 / 2844 | 3,795,954 / 15,555,609 | 267,264 / 1,194,480 | $0.638339 / $2.655577 |

These are approximate token/cost forecasts, not measured labeling consumption.
User-evidence preprocessing was checked against the original implementation:
prompts, quality counts and forecast totals match exactly.

One separately forecast public connection probe verified the existing authenticated
Ollama Cloud path: HTTP 200, 32 input tokens, 0 cached input tokens and 6 output
tokens, estimated $0.00000688. It contained no catalog/user evidence and wrote no
labels. It is retained as a private connection-test receipt, not counted as a
labeling batch. **No real labeling batch or backfill ran during deployment.**
