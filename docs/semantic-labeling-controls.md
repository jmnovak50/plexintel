# Labeling controls and output — November 20, 2026

Semantic labeling uses the existing enabled switch, standing cloud authorization,
configured dimension batch size, finite cumulative financial ceiling and retry
limits. The cumulative request count is accounting only. Its former setting and
environment alias are no longer registered, read, validated or enforced. Existing
stored settings and historical request-limit fields are left intact as evidence;
they are not current configuration or authorization inputs.

The effective budget was $10 and the batch size 25 before this correction. Neither
was changed. Standing authorization was already enabled by the operator and is
preserved. No labels or accounting records are removed or reclassified.

## Actual failure and duplicate sources

Run 349 completed predictive publication successfully but made zero labeling
requests. Two preceding manual batches had consumed 100 attempts in the shared
accounting scope, so the request cap stopped the daily stage despite remaining
financial allowance. Its retained stdout contains 11 rendered stage announcements,
two terminal assessment summaries and another copy in the final workload receipt.

The announcement came from repeatedly rendering state snapshots as stage-start
messages. The engine and daily adapter each emitted the terminal summary. The
receipt projection synthesized it again. Current producers distinguish subsequent
machine state snapshots from operator log output; those snapshots still update
status, elapsed time and progress. The daily adapter emits the one terminal summary
and marks its receipt as already emitted. The standalone CLI engine owns its one
terminal summary. Historical records are unchanged and remain readable, including
their original request-limit information and duplicate messages.

## Execution and evidence

Both daily execution and actual CLI labeling check standing policy and exhausted
financial allowance before constructing evidence. Every individual provider
attempt still acquires the existing cumulative accounting lock, rereads/locks
current policy, checks exact prompt reservations and per-prompt retry allowance,
and durably reserves cost before provider I/O. Revocations, exhausted funds,
pending reservations, retries and interruptions retain their existing safeguards.
Counts, measured/unknown tokens and estimated/reserved costs remain accounted for.
No cumulative request count can reject an otherwise admissible attempt.

Normal batches no longer prepare every contrastive prompt merely to choose a
batch. The same retained SHAP priority, compatibility/governance filters, exact
HIGH/LOW examples, prompt hashing, abstention reuse and attempt checks are applied
until the batch fills or the eligible candidates are exhausted. New dimensions
still precede due reviews in eligible mode. Already completed labels need no new
prompt unless the existing selection explicitly calls for a review. Vector
provenance checks and full populations needed for HIGH/LOW ranking are retained.

Explicit dry-run forecasts still prepare full coverage. A normal execution marks
its forecast as `selected_batch`; an uncomputed whole-inventory cost-to-finish is
unknown, rather than presented as a smaller exact total. There is no persistent
evidence cache or new eligibility policy. Later daily executions select remaining
work from the same labels, assessments and ledger.

No predictive pipeline or cloud batch was started for this correction. Private
preservation snapshots, existing-run log counts, read-only selection comparisons,
SQL fixture results and browser evidence are retained under the ignored
`.secrets/label-controls-20261120/` directory.

## Verification and deployment

The old and corrected selectors were compared read-only against the same actual
production evidence. Both chose the same 25 dimensions with identical prompt
hashes. The old path prepared 1,148 prompts in 69.34 seconds; the bounded path
prepared 37 in 16.44 seconds, including full vector/evidence initialization.
These are observations from one comparison, not guaranteed future timings.

The shared allowance scope retained 100 requests and $0.12115564 charged estimates
against the unchanged $10 ceiling. All-time history retained 1,034 requests and
$0.51940544. The retired count no longer prevents selection/admission. Financial
reservations and per-prompt retry caps still apply.

Validation passed 1,276 offline tests and 89 subtests (330 optional skips). The
focused PostgreSQL-enabled run passed 25 checks, including 11 tests using only
connection-private temporary tables. It verifies admission beyond 100 requests,
true retry numbering across batches, pending cost retention, real policy reads
with an invalid obsolete request-limit row, and financial/authorization revocation.
Providers were mocked throughout.

The tested source was deployed under the existing writer lock and the backend
restarted. A real authenticated browser verified that Settings/API no longer
exposes the request cap, while budget $10, batch size 25 and standing authorization
remain unchanged. The existing eight-stage run 349 and its original events remain
intact. GET-only browser fixtures verified incoming output beyond 100 requests,
cumulative known token/cost counters, one announcement and one terminal summary.
No real pipeline or cloud-labeling batch was started.

Full record-set hashes match for all 519 existing labels, 2,546 assessments,
1,034 requests, 20 batches, predictor configuration and all persisted settings.
No database schema or scheduler changes were made.
