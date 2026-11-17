# Classic log formatting, verified with actual run 341

Run 341 contains the item-level records missing from earlier restored runs, but
the previous formatter still displayed ISO timestamps, quoted key/value fields,
protocol flags and thousands of individual cache hits. Its JSON-like line format
was visibly different from the original pre-cutover console output. Comparing
the actual deployed run with run 324 established the remaining presentation gap.

This correction changes only log reading/rendering and the existing stage API.
The worker, model, feature names, embeddings, policies and scheduler are untouched.
No predictive run is initiated. Existing run 341 supplies the validation data.

The default operator view now uses the original style of named-user headings,
plain console messages, `Rank N: key — feature (+0.00)` lines, title/probability
continuations, aligned three-decimal classification tables and confusion matrices.
It does not repeatedly prepend timestamps, stage keys or timing/provenance flags.
Actual feature identifiers are preserved; new features are never relabelled as
old embedding dimensions.

Repeated progress and cache-hit lists remain available in each stage's collapsed
Recorded details area, alongside the full completion receipt diagnostics. The
main log retains substantive item activity and compact recorded outcomes. Run 341
reused all 8,442 media vectors; its summary correctly says that no new media
embedding requests were needed. It does not claim those items were regenerated.
All 18,538 selected ranked SHAP records remain present in scoring, with the actual
31 users, titles, keys and probabilities. stderr stays separate.

Show recorded events switches just that stage to the complete redacted structured
records. The existing administrator-only endpoint accepts `view=operator` or
`view=recorded`, with the same bounded pagination, run ownership and no-cache
contract. This preserves timestamps, protocol extensions and full numeric
precision without putting them into the default operator text. JSON escapes are
normalized before secret scrubbing so the additional view cannot bypass existing
credential redaction. Original retained files and database rows are not rewritten.

Classification reports at the run's recorded 0.50 threshold are reconstructed
from the retained confusion counts. Precision, recall, F1, accuracy and macro/
weighted averages are deterministic presentation arithmetic, not new inference
or model evaluation. The reports explicitly identify the reconstruction and the
chronological/show-heldout cohorts. Missing matrices and other threshold results
are not invented. The old seven-threshold sweep remains unavailable for newer
runs that did not retain it.

Validation includes 140 focused backend checks, 18 frontend checks, the
TypeScript/Vite build, and browser comparison of real runs 341 and 324. A labelled
read-only replay appends the next actual retained scoring records into the same
stage; it never executes a model or pipeline. Private before/after screenshots,
asset hashes and state receipts are in `.secrets/stage-format-restoration/`.

## Deployed verification

The actual public page was opened in Firefox and inspected using completed runs
341 and 324, without injected fixture responses. Run 341 displays all 18,538
classic rank lines, aligned reports for its two retained cohorts, and a compact
media-reuse outcome. Its complete 8,442 cache-hit list, progress records and
full-precision structured events remain accessible within the owning stage.
Changing the view, expanding details, scrolling and mobile wrapping were checked.

Authenticated public API reads drained both views through all pages, verified
all ranked/reuse records and rejected invalid views/offsets and unauthenticated
requests. Original run 324 scoring/training tails remained byte-identical. Served
HTML/JS/CSS matched the tested build. Existing SPA tabs require one page reload to
load the new renderer.

Before/after model, configuration and predictor-source checksums, scheduling,
production populations, all 18 run/stage records and run 341 stdout/stderr file
hashes matched. The backend is healthy. No predictive execution was initiated.
Screenshots include `after-341-scoring.png`, `after-341-library.png` and
`after-341-classification-report.png` under the private evidence directory.
