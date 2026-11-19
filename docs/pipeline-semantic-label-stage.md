# Dedicated semantic labeling stage

Semantic dimension labeling is the eighth operator stage, after production
publication and final verification. The first seven stage groups and their log
layout are unchanged. Publication groups only publication/verification; labeling
has its own status, clock, progress, stdout, stderr and recorded-event view.
Labeling errors do not change successful predictive publication or trigger a
predictive retry. No scheduler, provider authorization or financial limit is
changed by this correction.

The existing batch engine accepts an optional output callback. Daily labeling
uses it to tag preparation, selection, durable request reservations, completed
attempts and assessment outcomes with `semantic_labels`. The existing stage
observer continues to consume only bounded stage events. Item records retain
readable details in the same stdout files; no new logging store is introduced.
Assessed dimensions, accepted/saved labels, review assessments, abstentions and
failures come from the batch engine. Request/token/cost counts come from its
existing ledger. Cumulative scope totals are read within a short savepoint so a
failed observation cannot poison the labeling transaction. Those reads do not
grant authorization, release reservations or change admission decisions.

The measured labeling span starts before policy checks and ends on all normal
terminal outcomes, including disabled/unauthorized/skipped, empty, budget-stopped,
completed and failed outcomes. The actual policy snapshot is logged before its
checks. Failed/interrupted labeling remains a failure of this optional stage;
the predictive worker/publication can still succeed.

Historical runs use only their retained event/receipt data. Labeling completion
receipts and recognizable old batch output are routed to this stage, rather than
publication or unattributed worker output. A missing historical outcome remains
`not_recorded`; missing elapsed time, costs and counters stay unknown. Existing
multi-process history retains its original stages. Nothing is backfilled into
production history.

The recommendation/model feature contracts, embeddings, label selection and
governance, provider retry policy, and budget/request enforcement are unchanged.
The earlier labeling audit's selector-parity findings are separate work.

Validation uses existing completed runs and clearly labeled local browser
fixtures. Fixtures exercise incoming lines within the active labeling card,
separate stderr, completed/error/empty/disabled/unauthorized outcomes, progress,
costs and successful publication alongside labeling failure. No predictive run
or cloud-labeling batch is launched for interface verification.

## Deployed verification

November 19, 2026: the deployed page was opened in Firefox with genuine runs
348 (authorization absent) and 345 (labeling disabled). Labeling appears as the
eighth execution card after successful publication/verification, and its reason
is absent from publication stdout. Recorded-event toggling and mobile layout
were checked. Served HTML/JS/CSS match the tested build. All 25 retained runs,
including archived text-form labeling receipts, pass the read-only projection.

The final focused backend suite passed 276 tests with 55 opt-in database tests
skipped. All 19 frontend checks, TypeScript and the Vite build passed. Browser
fixtures demonstrate incoming lines, progress, assessment/request/cost counters,
separate stderr and independent labeling outcomes without real provider work.

Before/after model/configuration hashes, scheduler and labeling controls,
production table counts, run/stage digests and request/batch digests match.
Private screenshots and verification receipts remain under
`.secrets/semantic-stage-20261119/`. No predictive or labeling execution was
initiated, and no cloud authorization or financial limit was changed.
