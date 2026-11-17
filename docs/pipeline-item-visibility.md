# Item visibility under library synchronization and recommendation scoring

The pre-cutover collector (`a731740`) listed titles and rating keys queued for
embedding when `embeddings.log_titles` was enabled. Its scoring script printed
named-user candidate/scoring messages and ranked raw SHAP feature contributions.
Those were actual script diagnostics, not frontend metric widgets. The restored
worker's progress callbacks omitted that item-level content; reformatting its
aggregate completion receipt could not reproduce it.

## Restored content

- Media-text processing now emits the actual item's title, rating key, media type
  and available show/season/episode identity. An `Embedding media text` message
  precedes the existing encoder request; `Embedded media text` follows successful
  vector validation. Cache hits are explicitly `Reused cached media embedding`,
  never misrepresented as new inference. Encoder failures record their type
  without copying a private request URL or serialized embedding input.
- Named-user scoring messages record candidate, prediction and SHAP-target counts.
  Selected explanation rows include the actual recommendation rank, title/key,
  probability and top three raw feature contributions from the explanation that
  was already computed. This is selected SHAP output, not a claim that every
  prediction received an explanation. Feature identifiers remain literal model
  identifiers, not invented semantic labels or causal interpretations.
- Media refresh belongs inside the first **Library synchronization and media
  embeddings** card. The backend preserves emitted order while combining only
  those two consecutive phases; original database records and legacy subprocess
  stages remain intact. The independent media endpoint still returns only media
  output. The header retains combined timing and actual embedding progress.
- When item lines exist, they remain in the main stdout pane. The large recorded
  completion report remains available in a collapsed log section within the same
  stage's stdout; it does not displace the actual item lines at the log tail.
  stderr stays separate. There is no global log panel or metric grid.

The new `plexintel.pipeline-log/1` messages use the existing retained stdout files.
They are separate from `plexintel.pipeline-stage/1`, unthrottled and ignored by
its database stage observer. They cannot replace a stage status or create stage
rows. No schema, journal, logging database or additional serving process is added.
The existing title-logging setting is read and respected without changing it.

## Historical and deployment limits

Past runs that recorded only progress totals still cannot reveal which individual
titles were embedded/reused or reconstruct missing per-user/ranked SHAP lines.
Their cards now say that explicitly. No current embedding or recommendation table
is passed off as historical execution output. Retained legacy messages remain
verbatim. The new item logging applies to subsequent ordinary executions; no
predictive run is initiated to populate the interface.

Run 340 was independently active during development. Candidate changes and tests
were isolated in a temporary checkout so its source fingerprint remained stable.
Deployment waits for the shared execution lock and holds it while applying the
logging-only source, installing the tested frontend and restarting the backend.
Predictive source bytes change for instrumentation; encoder inputs, cache rules,
model computations, prediction/rank/SHAP storage, policies and scheduling do not.
Existing model files and configuration are compared around deployment.

## Validation

- 246 focused backend checks passed; two optional database checks skipped.
- 17 frontend formatter/grouping/component checks passed; TypeScript/Vite build
  passed. Tests cover library grouping, timing/progress/failure, separate stdout
  and stderr, and diagnostic disclosure without losing or duplicating messages.
- Fake encoder checks verify start-before-request, successful inference versus
  cache reuse, unchanged vectors and request count, and unchanged exceptions.
  Fake classifier checks verify exact prediction/rank/stored-SHAP equality with
  logging enabled/disabled and no extra model calls.
- Browser fixtures use the actual new callbacks with a fake encoder/classifier,
  visibly labelled fictional. They show titles/keys/actions under library sync,
  named ranked SHAP, live append in that same card, mobile wrapping, and preserved
  legacy history. Existing completed run 336 supplies genuine historical data.
- A fictional 26,979-record/7.36 MB retained file was indexed in about 2.4 seconds
  after moving credential-pattern setup outside the per-line parse loop. The
  same redaction rules and all available messages remain intact.

Private screenshots and audit receipts are under
`.secrets/stage-item-restoration/`; fictional fixture records are never inserted
into production history.

## Deployed verification

Run 340 completed independently before the guarded deployment. The public page
was opened in Firefox and inspected with genuine runs 324 and 336: legacy stages
remain unchanged, newer library/media output is combined, and missing item-level
history is explicit. Cache-bypassing HTML/JS/CSS bytes matched the tested build.

A second browser pass used that same deployed frontend with clearly labelled,
browser-only GET fixtures generated from the actual new callbacks. It showed
embedding start/success/reuse titles and keys, named ranked SHAP, active appends
in the same card, consistent terminal headers, retained diagnostic disclosure
and mobile wrapping. These were fake encoder/classifier fixtures, not a new
production run; no fixture was written to production history.

Before/after deployment, the current model checksum, configuration checksum,
existing title-logging/scheduler settings, production populations and all 17
run/stage records matched. Predictor source bytes changed exactly as expected
for the tested logging instrumentation. No model artifact was regenerated.
