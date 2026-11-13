# Revealing stage logs: comparison with run 324

The reference is run **324**, started **November 2, 2026 at 07:03:21 CST**.
Its eight original subprocess stages retain substantially more diagnostic content
than the restored worker's periodic progress events. The current per-stage layout
now preserves the available equivalent details from newer runs too.

| Original retained output | Newer retained evidence and presentation |
| --- | --- |
| Per-user profile title counts and vector norms | New worker logs retain aggregate user counts; individual historical profile lines were not emitted. They cannot be recovered from these logs. |
| Training positives/negatives, label sources and skipped-row explanations | This run's final stdout receipt contains the dataset summary. It is now rendered inside training-data stdout, including class counts, source/provenance distributions, coverage and each retained skip reason. |
| Classification reports and confusion matrices | The final stdout receipt contains chronological and show-held-out evaluation, per-class precision/recall/support and confusion matrices, calibration, segments, feature-group diagnostics and quality gates. These are now readable plain-text reports inside model-training stdout. Cohorts are explicitly named. |
| Seven-threshold comparison and diagnostic best thresholds | Newer evaluation records only the fixed 0.5 threshold. No seven-threshold results, per-class F1 values or threshold winners are invented or recomputed. |
| Individual ranked recommendation SHAP contributions | New logs retain SHAP populations and per-viewer ranking comparisons rather than those old per-card lines. The recorded ranking comparison and SHAP counts now appear inside scoring stdout. No current database population is substituted for a historical run. |
| Semantic labeling output | The retained optional-label outcome is displayed in publication stdout; genuinely skipped labeling remains skipped. |

## Why the preceding correction was incomplete

It restored the stage-owned event stream but left the large, unkeyed final JSON
receipt in the worker's unattributed-output card. Consequently most diagnostic
content remained disconnected from its stage. The stdout reader now recognizes
only the existing completed predictive receipt shape and routes its recorded
fields to their corresponding stages. Each field is displayed once; unknown
fields or fields without a recorded destination stay in the worker card.

Completion diagnostics are labelled as extracted from this execution's retained
stdout receipt. They are not presented as messages emitted during the stage.
The adapter reads only the exact run's retained stdout, never the latest model,
latest evaluation artifact or another run's database output. Original raw files
and database history remain unchanged. Missing, incomplete or unavailable
historical reports remain unavailable.

Logs open at their latest available output, with full earlier content still
scrollable. Follow-at-bottom behavior preserves a manual upward scroll when
incoming lines arrive. Scrolling is applied after React commits the log content;
a pre-commit animation callback was insufficient for a long report.

The correction touches only the log reader, existing frontend scroll behavior,
focused tests and documentation. No predictive behavior, training policy,
threshold, scheduler setting, model artifact, embedding lifecycle or schema is
changed. No predictive run was initiated to test it.

## Validation evidence

- 126 focused backend tests passed; two optional database tests skipped. Fifteen
  frontend component/grouping checks and the TypeScript/Vite build passed.
- Completed retained run 336 in a browser fixture displayed 510 training-data
  lines and 2,728 fitting lines, including the actual class reports and matrices.
  Scoring exposed the saved ranking comparison in its own stdout pane.
- The labelled active-evidence fixture appended original records in the same
  training pane, preserving a manual scroll position. No predictor was executed.
- Independently executing run 339 was observed on the public page before
  deployment. After the initial full load, publication output grew from 204 to
  828 characters in that same stage pane. The shared execution-lock guard
  prevented deployment restarts while that run was active.
- After run 339 finished, the tested version was deployed using that guard.
  Actual public-page inspection covered original run 324 and restored run 336,
  visible class reports and matrices, dataset and ranking breakdowns, tail-first
  scrolling, independent collapse and mobile width. The public API was drained
  across pages; model hashes in each report matched its own execution receipt.
  Served frontend assets exactly matched the tested build.
- Predictor-source, model and active-configuration checksums, scheduler setting,
  production populations and all 16 existing run/stage records matched before
  and after deployment. Natural changes from independently executing run 339
  were recorded separately before that deployment baseline was taken.
- Private screenshots and receipts are under
  `.secrets/stage-diagnostics-restoration/`, including
  `original-324-training.png`, `restored-336-training.png`,
  `restored-336-preparation.png`, and the active-run observation.
