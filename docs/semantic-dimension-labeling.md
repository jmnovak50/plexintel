# Manual semantic dimension labeling

The original HIGH-versus-LOW labeling workflow is restored for the active
EmbeddingGemma 2 text generation. It reads **Ollama Label Model in Setup**
(`labeling.ollama_model`), currently `gemma4:31b-cloud`, through the existing
Ollama integration. Both batch labeling and Dimension Explorer review use this
setting. An explicit CLI `--label-model` overrides it for that invocation only.
The resolved model and configuration source are shown in the forecast and stored
with results. No labeling stage is added to the daily pipeline. Operators
initiate batches or individual Dimension Explorer reviews manually.

Labels are approximate semantic interpretations of coordinates. They are not
proven causal explanations of XGBoost predictions. Prediction probabilities,
ranking, training data, embedding arithmetic and SHAP computations are unchanged.

## Operator commands on birch

Run from the production checkout with its existing model-host environment:

```bash
cd /home/jmnovak/projects/plexintel
```

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
