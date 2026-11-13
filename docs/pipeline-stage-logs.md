# Monitoring correction: output belongs to its stage

The subsequent [run 324 diagnostic comparison](pipeline-stage-diagnostics.md)
also restores recorded completion reports to their stages and the tail-first
view. The line counts below describe the earlier event-stream correction.

The consolidated log panel was the wrong presentation and has been removed,
along with its run-wide log endpoint. Recent runs is again the main page section.

## Cause

Logical `pipeline_run_stages.stdout_tail` records retain only the last structured
progress event, not the stage's complete output. Detailed stdout/stderr survive
in the existing worker files. The previous UI displayed those last-event records
inside cards but sent the detailed stream to a separate global panel. Its
frontend grouping also concatenated child tails instead of reading all of their
actual events in emission order.

## Corrected behavior

- Each existing operator stage contains its own expandable Stage output section,
  a dedicated `stdout:` pane and a separate `stderr:` pane when stderr exists.
  Long panes scroll. Opening a run loads all currently available stage output,
  using bounded pages internally rather than cutting output to a tail or summary.
- The existing chronological operator grouping is preserved. SHAP events remain
  in scoring; verification and optional-label events remain in publication.
  Their output preserves the worker file's emission order, including interleaved
  events. Original legacy subprocess stages retain their own stream ownership.
- Structured progress records remain separate readable log entries; plain script
  messages retain their lines; other JSON diagnostics retain all fields in a
  readable multiline representation. Progress-record extensions are retained too.
  No message is synthesized to pad a short historical record.
- While a run is active, open stage panes refresh every five seconds. New lines
  appear in the same stage. Closing a stage stops its log requests. Paging and
  per-stream identities prevent mixing output after a file replacement.
- Meaningful stage names, status, exit codes where recorded, timing and compact
  progress counts remain in the header. There is no metric grid or global log.

## Association rules and historical limits

`api/services/pipeline_logs.py` is a read-only adapter. It splits the exact
run's retained worker stdout by explicit stage keys and active-span markers.
Unkeyed stdout is associated only within an explicitly active span. A paused or
finished span cannot claim subsequent unkeyed messages. No timestamp matching or
other run's evaluation/model data is used.

Stderr is a separate stream. Explicit stderr stage keys are respected; untagged
stderr cannot be assigned from stdout's timing. Such output remains in the
actual recorded worker stage, labelled as unattributed output. That card contains
only unassigned output, not a duplicated consolidated copy. It is omitted when
there is no such output. Final unkeyed CLI receipts remain there too.

When individual files are missing, only exact `[run:ID] [stage:KEY]` sections in
the existing combined log are eligible for recovery. Otherwise only the genuine
saved stage tail is displayed, with an availability note. Projected historical
stages with no retained stdout show an explicit absence message outside the log,
not invented output. Credentials are redacted before presentation.

There are no database writes, schema changes, model/embedding changes,
training-policy changes, scheduler changes, additional predictive runs or new
serving infrastructure. The adapter uses the existing files and application
process; its bounded in-memory index is discarded with the process.

## Validation

Real completed run 336 now exposes these stage-owned stdout lengths:

| Stage | Available displayed lines |
| --- | ---: |
| Synchronization | 2,689 |
| Media-text refresh | 95 |
| Watch refresh | 39 |
| User profiles | 2 |
| Training data | 469 |
| Model fitting | 36 |
| Scoring including SHAP | 36 |
| Publication including verification/optional-label outcome | 7 |

The two user-profile records are genuinely all that worker retained for that
phase. Run 325 retains its older multiline subprocess tails; run 326 has no
recoverable stdout for some projected phases. Run 337's unkeyed error is preserved
as separate stderr in its actual worker stage, not guessed into a logical phase.

- Focused backend checks, including pipeline hardening: 122 passed, two optional
  database tests skipped.
- Frontend formatter/grouping/component checks: 15 passed; TypeScript/Vite build
  passed.
- Actual Firefox inspection covered the deployed public Pipeline runs page,
  completed run 336's multiline stage output, independent collapse/scroll,
  run 337's separate stderr, legacy run 325, dark mode and a 390px viewport.
- No production run was active during this correction. Available active evidence
  was replayed from run 336's real retained records in a temporary fixture. Six
  additional original records appeared in the same `train_model` pane on refresh
  (9 to 15 lines). The fixture was visibly labelled as replay and never executed
  the predictor. Temporary browsers/fixture servers were stopped after checks.
- The authenticated public API was drained through all pages and matched the
  complete per-stage output counts. Unauthorized requests and invalid offsets
  were rejected. The obsolete global endpoint returns 404. Served frontend
  assets matched the tested build.

Deployment used the existing execution-lock restart guard. Before/after model
and active-configuration checksums, production populations, scheduler setting and
all 14 original run/stage records matched. Private visual evidence and receipts
are under `.secrets/stage-log-restoration/`, including
`public-stage-source.png`, `public-stage-training.png`,
`public-separate-stderr.png`, and `replay-stage-after.png`.
