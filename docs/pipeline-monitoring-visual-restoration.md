# Pipeline monitor: restoring the earlier log view

This intermediate presentation was rejected: the operator requires output within
each stage, not a consolidated panel. See [the stage-log correction](pipeline-stage-logs.md)
for the deployed replacement and its visual evidence.

The first monitoring correction restored data but targeted the wrong presentation.
The operator clarified that the intended screen had plain log tails, fewer stages,
no embedded metric summaries, and a last-X-lines log view above execution history.

## What the source and browser comparison established

- `3ffaa68` and `d37bbaa` contain identical frontend source, CSS, markup, route
  layout and built HTML/JS/CSS. Neither restoration commit introduced a different
  visual design. Those snapshots already contain the newer monitoring UI.
- The earlier `a731740` frontend displays the original subprocess stage keys in
  monospace, status/exit/duration on one line, and stdout/stderr directly in dark,
  scrollable `<pre>` panels. Existing run 325 has its eight original stages and
  script output. This exact archived build was rendered in Firefox for comparison.
- Commit `b06469d`, before `3ffaa68`, introduced the ten logical-stage view,
  embedded metric lists, human-readable stage labels and collapsed stage logs.
  The predictive restoration later reduced available evidence while retaining that
  newer renderer. The first correction retained it too.
- The rejected deployment left the overview table, shared CSS and initial
  collapsed state essentially unchanged. Almost all additions were inside
  "Show stages" and closed log disclosures. This explains the lack of a visible
  difference on initial page load; it was not evidence of a successful visual
  restoration.
- Cache-bypassing requests to both the local backend and the actual public
  hostname returned the same rejected HTML, JS and CSS bytes. A fresh Firefox
  session with network caching bypassed reproduced the rejected appearance.
  There was no stale proxy bundle in those checks. An already open SPA tab still
  needs a page reload to load a newly deployed bundle.

The checked-in versions above confirm the earlier inline-log layout. They do not
contain the separate last-X-lines panel described by the operator. That portion
is restored from the operator's clarified description, using the existing local
log files; it is not claimed as an exact recovered historical component.

## What changes on screen

- A **Pipeline log** section appears above **Recent runs**. It shows the last
  100/200/500/1000 lines as scrollable monospace text, initially positioned at the
  newest output. It follows new output while at the bottom and preserves manual
  scrolling. Active runs refresh every five seconds; Refresh reloads completed
  output too.
- Expanded runs use the earlier compact header and directly visible log panes.
  There are no embedded metric grids or progress bars and no extra log-opening
  click. Recorded numeric diagnostics remain text within the logs.
- Restored single-worker runs display eight execution blocks: source sync,
  media embeddings, watch embeddings, profiles, training data, fitting, scoring,
  and publication. SHAP stays in the scoring log; verification and optional-label
  outcomes stay in the publication log. These are display groups over existing
  evidence, not new jobs. Original legacy runs retain all their actual stages.
- The existing public `stages` and `stage_details` API records remain intact.
  Missing/combined timing stays explicit. Failure and cancellation evidence stays
  visible when stages are grouped.
- The existing `pipeline.log` is read through a bounded, administrator-only GET.
  For active workers, existing retained stdout/stderr files supply live output
  before they have been copied to the combined log. Structured JSON progress and
  final receipts are presented as plain text; no writer, database schema or
  pipeline execution is added. Reads and secret redaction are bounded.
- SPA HTML now requires cache revalidation. New content-hashed assets are served
  together, and older assets are retained for tabs already using the prior build.

The shared shell, navigation, table, colors and theme system are preserved. There
are no predictive/model/embedding/training-policy/scheduler changes in this
follow-up.

## Remaining differences and data limits

Current phases and timing follow the restored worker; they are not separate
legacy subprocesses and do not have invented subprocess exit codes. Related
phases are grouped for display without changing execution or stored history.
Legacy script output is preserved verbatim where available. Newer workers wrote
aggregate structured events, so their logs cannot reproduce old per-item titles,
per-user script messages or discarded collection output that were never retained.
Separate SHAP time remains unknown where measured within scoring. The global tail
is bounded by 512 KiB of readable text and 1000 displayed lines; rotated or missing
files are reported as unavailable rather than reconstructed from another run.

## Rendered validation

Actual Firefox screenshots, inspected directly, compare the exact earlier build,
the rejected deployment and this revision. Checks cover the 1440px desktop view,
390px mobile view, light/dark themes, 200-to-100-line selection, eight inline-log
blocks, absence of metric widgets and five-second active-fixture polling.
Read-only fixtures reject all POST and DELETE requests. No predictive run was
started for validation. Real completed runs provide historical data. An initial
active fixture is explicitly synthetic. During the work another workflow started
run 336 independently; an additional read-only browser preview used that real
run's API records and retained worker output, including live tail refresh. The
existing restart guard prevented deployment from interrupting that worker.

Focused regression checks: 80 backend tests passed, two optional database checks
skipped; 13 frontend formatter/grouping/actual-component rendering tests passed;
TypeScript and Vite production build passed. The acceptance evidence is the
rendered screenshots and interactions in addition to those checks.

Private screenshots, source snapshots, asset hashes and before/after production
state evidence are in `.secrets/monitoring-visual/`.

## Public deployment verification

Run 336, started independently by another workflow, completed before deployment.
The existing execution-lock guard then restarted only the backend, and the
already tested content-hashed assets were published before replacing the HTML.
No predictive run was launched by this monitoring task.

The actual public page was subsequently rendered and inspected in Firefox:
the top log panel, eight expanded inline-log blocks, original run 325 logs,
persisted dark theme, light theme and 390px mobile layout all rendered correctly.
Normal warm navigation loaded the same new bundle; there was no service worker.
The public and local HTML/JS/CSS bytes matched the build used for visual checks:
`index-YlhbsBk2.js` and `index-CEmWVQtN.css`.

Authenticated requests for 100, 200, 500 and 1000 lines returned those exact line
counts; unauthorized access and invalid limits were rejected. Log responses use
`Cache-Control: no-store`; SPA HTML uses `Cache-Control: no-cache`.

The deployment comparison deliberately uses the state after the independent run
finished as its baseline. Model-file and active-configuration checksums,
production populations, scheduling and all 13 original run/stage records matched
immediately before and after this deployment. The backend is active with zero
automatic restarts. Temporary preview servers and validation browsers were
stopped after the checks.

Inspected public screenshots:

- `.secrets/monitoring-visual/deployed-public-overview-light.png`
- `.secrets/monitoring-visual/deployed-public-inline-light.png`
- `.secrets/monitoring-visual/deployed-public-overview-dark.png`
- `.secrets/monitoring-visual/deployed-public-legacy-dark.png`
- `.secrets/monitoring-visual/deployed-public-mobile-dark.png`
