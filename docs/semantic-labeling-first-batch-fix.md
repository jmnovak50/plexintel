# First semantic labeling batch failure — November 8, 2026

Batch `02ffcd06-acb4-4e84-9be8-a2d9450a4065` received 25 metered replies but
saved no labels. Its original request/assessment records are preserved unchanged:
64,603 input tokens, 10,752 cached input tokens, 5,921 output tokens, no retries,
and $0.01044514 estimated usage-credit consumption. The request ledger recorded
`ValueError`; the assessment wrapper reduced every error to `RuntimeError`.

Only one reply hit the 420-token cap. The other 24 used 205–268 output tokens.
The old implementation discarded their bodies and detailed causes, so a precise
per-dimension retrospective classification is unavailable. It would be inaccurate
to attribute every original failure to truncation or to missing fields.

## Reproduced cause and bounded verification

Exactly **one** additional real request was made, for dimension 24, using the
existing Setup model/cloud configuration. It had one attempt, an exclusive
one-request guard, a pre-execution forecast, a 1,024-token cap and no label save.
No second inference request, repair request or 25-dimension batch was launched.

The reply completed with `done_reason=stop`: 2,413 input tokens, zero cached input
tokens and 442 output tokens, estimated **$0.00051462**. It contained two
Markdown-fenced JSON objects separated by a visible self-correction. Both objects
had the required fields and correct types. Replaying that exact reply through
the original validator, with all I/O mocked, reproduced:

```
ValueError: Ollama returned invalid label JSON
  caused by JSONDecodeError: Expecting value: line 1 column 1
```

The parser attempted to decode the Markdown envelope as a single raw JSON value.
The full self-correction also needed more than the old 420-token limit. This
reproduces response-envelope incompatibility and demonstrates insufficient output
headroom; it does not reconstruct the discarded bodies of all 25 original replies.

Ollama documents that [Cloud does not currently support structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
The existing `format="json"` request is retained, but it is not trusted to enforce
the response contract. A full JSON schema is not sent as an assumed Cloud feature.

The initial diagnostic run correctly recorded the multi-object reply as an error.
After correcting the parser, the **same captured reply was replayed offline**:
the existing 75% LOW-overlap rule rejects its proposed label. It validates to a
conservative abstention, with no usable label recovered or published. There was
no second live run of the final prompt. The diagnostic request's original error
record is not rewritten to pretend it succeeded at execution time.

## Targeted changes

- Unwrap a unique JSON fence without changing the object. Retain the original
  parser's known aliases and lossless enum/integer normalization, while still
  rejecting missing fields, numeric strings, fractional counts, booleans in numeric
  fields, invalid enum values, invalid ranges and malformed evidence arrays.
- Multiple JSON objects never recover a usable label. The narrow recovery path
  requires every candidate to abstain under existing quality checks and exactly
  one coverage report to match the actual HIGH/LOW counts. Conflicting proposals
  or multiple matching reports remain explicit failures. No fields or judgments
  are invented, and positive-label coverage/overlap gates are unchanged.
- Instruct the model to finish its checks internally and emit one final JSON
  object without Markdown, preliminary candidates or visible corrections.
- Default the response cap to **1,024** through Setup's **Label response token
  limit** (`labeling.max_output_tokens`, range 64–4096). `--max-output-tokens`
  overrides one invocation. Forecasts, usage reservations and native
  `options.num_predict` use the same resolved limit.
- Preserve typed errors and safe diagnostics through wrapping, request accounting,
  assessments and progress. Codes distinguish `OUTPUT_TRUNCATED`,
  `INCOMPLETE_RESPONSE`, `INVALID_JSON_SYNTAX`, `MISSING_JSON_FIELDS`,
  `INVALID_JSON_TYPES`, `MULTIPLE_JSON_OBJECTS`, `LABEL_COVERAGE_MISMATCH`,
  provider HTTP failures, timeouts and internal errors. Diagnostics contain only
  exception types, known field names, completion reason, counts and locations;
  never credentials, raw responses or private viewing evidence.
- Stop after **three consecutive identical failures** by default; configure with
  `--fail-fast-threshold`. Persist usage and each failure, return a nonzero CLI
  exit status, and leave failed/unprocessed dimensions retryable. Valid success
  or abstention resets the streak. Sample-count failures after metering update
  the request classification without losing consumed tokens.

## Updated forecasts and operator use

The real-data dry run still selects all 25 original failed dimensions. No label
was published and no dimension was silently marked completed by the diagnostic
request or its offline replay. The configured model remains
`Setup: labeling.ollama_model` → `gemma4:31b-cloud`.

With the actual prompts, the final one-object instruction and 1,024-token cap:

| Workload | Expected requests | Expected input / output tokens | Expected USD | High-use USD |
| --- | ---: | ---: | ---: | ---: |
| First 25 | 28 | 100,576 / 7,168 | $0.01694784 | $0.08728938 |
| Remaining 948 | 1,044 | 3,852,661 / 267,264 | $0.64627814 | $3.37513728 |

The first-25 high envelope includes 75 attempts, 404,067 input tokens and
76,800 output tokens. Expected output remains the documented 256-token
approximation until enough successful measured requests support refinement.
Prices remain $0.14/$0.05/$0.40 per million input/cached-input/output tokens;
these are estimates, not an invoice or exact spending ceiling.

From `/home/jmnovak/projects/plexintel`:

```bash
# No cloud inference or label writes
plexenv/bin/python batch_label_embeddings.py --dry-run --limit 25

# When the operator chooses to retry; not executed as part of this fix
plexenv/bin/python batch_label_embeddings.py --label --save-label --limit 25 --budget-usd 1

# Inspect the original batch's unchanged metering
plexenv/bin/python batch_label_embeddings.py --usage --batch-id 02ffcd06-acb4-4e84-9be8-a2d9450a4065
```

Private snapshots, the one captured reply, old-parser replay and corrected offline
validation are retained under `.secrets/semantic-labeling-fix-02ffcd06/` with
private permissions and Git exclusion. Tests in Git use fictional responses only.
No embeddings, classifier, SHAP, scheduled jobs, recommendation rows or eligible
production labels are changed by this incident investigation.

## Validation

The full regression suite passed **816 tests and 89 subtests**; 267 optional tests
were skipped. The targeted run passed **122 tests**, including eleven opt-in
PostgreSQL integration checks in isolated schemas. These cover strict types,
missing fields, truncation, safe exception chains, cloud self-corrections,
ambiguous-positive rejection, budget accounting, fail-fast behavior and retryability.
The captured provider reply also passed the corrected parser and sample-count
checks offline as an abstention. No second cloud request was made.

## Deployment verification

The fix is deployed through `plexintel-backend.service` on birch. Authenticated
status, Setup, Dimension Explorer, recommendations and the public application
returned 200; anonymous admin access remained 401. Setup exposes the existing
`gemma4:31b-cloud` model and the 1,024-token response limit. All ten protected
production table checksums matched the pre-fix snapshot, including vectors,
training rows, recommendations, SHAP and the unchanged empty label table. The
encoder generation, classifier and publication identity are unchanged. Original
batch/request records are unchanged, scheduling remains disabled as before, and
exactly one real request was made during this fix. No label was published.

Deployed runtime SHA256: `1a72ffc8ede8f389546b667e9b0ea798fb0417c5b76f12eba6f01d9b65c708c6`.
