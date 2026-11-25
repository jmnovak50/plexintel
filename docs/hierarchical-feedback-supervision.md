# Hierarchical feedback supervision correction

This implementation is prepared in `fix/hierarchical-feedback-supervision`.
Production remains on its existing model and recommendations. A full production
transition is not qualified while effective historical episode feedback lacks
reliable original-decision attribution. No production pipeline, embedding
inference, cloud request, or historical feedback rewrite was performed.

## Behavior

The existing leaf observations, canonical identity resolution, feedback
precedence, recommendation suppression and undo behavior remain in place.
Interested retains base weight 0.75, Never Watch 5, Watched Like 3 and Watched
Dislike 5. No additional hierarchy actions are introduced.

After precedence and eligibility, the surviving canonical descendants of each
explicit decision share its original base training weight. Independent viewing
outcomes keep their existing weights. Superseded feedback contributes no extra
observation; remaining eligible descendants share their originating decision's
budget. Undo removes the effective leaf as before; it does not invent or
resurrect an overwritten ancestor decision.

Negative-class balancing uses positive / negative **decision-equivalent support**
in the actual fit population. An independent viewing observation contributes
one unit; the eligible descendants of an explicit decision together contribute
one unit. Feedback significance remains separate from class-support accounting.

Chronological splitting uses independent decision/observation start times.
Decisions spanning the boundary are purged rather than divided across folds.
Fit labels must still be available before the boundary. Show exclusion and
canonical aliases remain excluded from held-out profiles. An explicit overlap
check rejects any decision shared between fit and validation.

Classification, probability and calibration metrics use decision-equivalent
evaluation weights, not feedback-type training weights. Both physical counts
and effective support are reported. Existing unweighted episode diagnostics
remain in `raw_episode_metrics`; ranking metrics remain explicitly identified
as raw episode diagnostics. Model features and SHAP retain their existing layout.

## Minimal persistence and supervision contract

One nullable JSONB column is added to the existing `user_feedback` table:
`decision_provenance`. Apply the operator SQL in
`api/db/migrations/optional/feedback_decisions/001_decision_provenance.sql`
before installing the updated feedback writer. The predictive job never applies
this migration. The migration is additive and does not backfill historical data.

The existing writer records a UUID, original target rating key and canonical
identity, hierarchy scope, action, owner and accepted-action timestamp. Descendants
share this provenance. A new effective action replaces the leaf provenance along
with the existing effective feedback fields; bulk skips and protected watched
feedback keep their original provenance.

Model/config and existing training diagnostics carry
`supervision_weighting=explicit-decision-support/1.0`, decision attribution,
base weight and evaluation support. This is an internal supervision contract,
not a new configurable policy or feature-space identifier. Embedding contracts,
semantic labels and the existing model-serving architecture are unchanged.
Legacy model artifacts remain readable; mismatched new weighting metadata fails
closed.

## Comparable quality safeguard

New normalized AP must never be compared with the incumbent's historical raw AP.
The incumbent model checksum and published training population are pinned under
the existing writer lock. For each current fold, the incumbent recipe is refitted
only on its published observations that precede the current causal boundary.
Current held-out decisions, shows and aliases are excluded. Features are rebuilt
using the common snapshot and the same target/profile exclusion rules.

Candidate and reference are evaluated on identical current held-out observations
with identical decision-normalized evaluation weights. Legacy reference fits
retain their original raw-row class balancing and base feedback weights. New
reference fits use their recorded decision-aware recipe. Manifests record model,
source, population and cohort hashes, causal boundary and decision overlap.
Unsupported contracts, unavailable reference support or uncertain original
explicit supervision stop publication. The saved all-data incumbent is never
misrepresented as an independent held-out model.

The existing AP tolerance of 0.05 and both balanced-accuracy floors of 0.50 remain
unchanged. Both chronological and show-held-out reference metrics are reported.
The final all-data fit still occurs only after the quality gates pass.

## Historical evidence from run 360

The confirmed whole-show Never Watch action has 113 retained leaf records. Its
original aggregate base weight was 565; the corrected total is 5, approximately
0.0442478 per eligible leaf. The user confirmed the original show action. A private,
row-specific recovery manifest binds the exact retained records, canonical target,
action and evidence digest. No recovery is inferred from timing proximity alone.

The original action timestamp was not retained. Proposed recovered provenance
keeps it null and explicitly records the observed descendant timestamp interval;
its latest retained time is only a conservative causal bound, not an invented
original click time. No production historical rows have been changed.

There are 1,425 other physical episode-feedback records with uncertain original
decision scope. Of these, 1,237 currently supply eligible explicit supervision:
1,172 Watched Like and 65 Never Watch outcomes. Some remaining feedback is
auxiliary to recorded viewing or otherwise ineligible. Historical movies can be
attributed as single-movie effective decisions because supported hierarchy
expansion cannot produce movie descendants. Generic `ui` / `bulk` markers and
nearby timestamps do not establish episode-level original decisions. In particular,
the original March 1 bulk route (`8a89b5e`) called `replace_feedback_rows` with its
default `source="ui"`; later schema migrations converted legacy `up` / `down`
values without retaining the original target. Therefore `ui` is demonstrably not
a reliable individual-episode marker. The number of original decisions behind
these uncertain rows cannot be recovered from the retained markers alone.

The corrected production planner fails closed on this uncertainty; it does not
silently count each episode as an independent decision or silently discard those
outcomes. Feedback records and recommendation suppression remain intact.

For the reliable 8,381-row cohort, the raw negative-class multiplier would be
6694 / 1687 = 3.967991. Corrected decision support gives 6694 / 1575 = 4.250159,
regardless of whether the confirmed decision has one eligible descendant or 113.
After class balancing, that decision has the same aggregate influence as a
single movie rejection in the same fit population. These are restricted-cohort
calculations, not an assumption that the ambiguous historical rows are independent.

## Qualification and transition

Focused regressions cover aggregate base weights, all four existing explicit
states, partial eligibility, canonical aliases, independent viewing, hierarchy
overlap, replacement, undo, class balancing, decision-atomic splitting, weighted
and raw reporting, SQL provenance and isolated atomic publication.

An isolated comparison uses 8,381 reliably attributable run-360 outcomes (8,269
effective units), excluding the 1,237 uncertain supervision outcomes explicitly
and only for this experiment. It uses retained pre-run media/watch vectors and
frozen descriptive metadata. The failed candidate's numerical feature vectors
and per-observation predictions were discarded, so this is a controlled frozen
projection, not an exact numerical reconstruction of run 360. No replacement
vectors are generated. The reference population is restricted by the same
reliability requirement; its coverage is reported rather than presented as a full
incumbent reproduction.

The restricted raw-row chronological split has 5,696 fit and 1,677 validation
observations. The decision-aware split has 5,590 fit and 1,766 validation
observations (1,654 validation units). The show-held-out split changes from
4,662 / 502 to 4,600 / 543 physical fit/validation observations, with 431 corrected
validation units. These changes reflect the new split unit and the explicitly
restricted cohort, not a claim of improved discrimination. The confirmed action
is held out in both validation folds; its 113 outcomes do not enter either
candidate validation fit.

Reference observations without an independent profile after current held-out-show
exclusions follow the existing limited-history eligibility rule. Their exclusions
are counted in the reference manifest; a missing complete class remains a hard
failure. Canonical user/title outcomes are also excluded from reference fits even
when their historical decision ID differs after feedback replacement.

The restricted real-data comparison passed the unchanged quality gates and
completed its isolated final fit. No model file was saved or published.

| Fold | Candidate normalized AP | Comparable reference AP | Candidate normalized balanced accuracy | Candidate raw episode AP |
| --- | ---: | ---: | ---: | ---: |
| Chronological | 0.944700 | 0.947949 | 0.642322 | 0.859759 |
| Show held out | 0.950621 | 0.955601 | 0.633179 | 0.611331 |

The raw and normalized candidate metrics use the same predictions with different
evaluation weights; their difference is not improved model discrimination. The
reference and candidate comparisons use identical held-out observations and
normalized weights. The full original run and incumbent historical scores use
different cohorts and metric semantics and are not treated as equivalent tests.
Passing this restricted comparison does not qualify the excluded historical
supervision or authorize a production predictive run.

Recommended transition:

1. Install the additive column and forward provenance capture independently of
   predictive promotion; retain all current source and label records.
2. Recover the confirmed 113-row decision using its exact private manifest,
   preserving existing feedback values/times and the unknown original time.
3. Establish reliable attribution for other eligible historical feedback from
   explicit evidence or operator confirmation. If that is impossible, a deliberate
   historical-supervision policy is required. Excluding only ambiguous explicit
   supervision would preserve suppression and independently observed viewing,
   but would remove 1,237 current training outcomes and requires a fresh comparable
   isolated qualification. It must not happen silently.
4. Run a full comparable isolated qualification with the established historical
   treatment. Only then promote code/model through the existing guarded procedure.
   Do not start a production predictive run merely to resolve historical ambiguity.

Validation on November 25, 2026: the complete offline project suite passed
1,570 tests (473 skipped; 89 subtests passed), with unmocked network access blocked
and database access restricted to a disposable Unix-socket cluster. The final
focused publication run passed 43 tests; the final contract run passed 280 tests
(4 skipped). A separate SQL test verifies the exact shared action timestamp using
the production feedback column type. `git diff --check` passed. The disposable
cluster is removed from operation after testing.

Read-only production checks confirmed the same active model/checksum, 9,497
published training rows, feedback values/times, audited settings and latest run
360 in failed state. The existing model remains readable with the new loader.
Private evidence, frozen-vector replay, metrics, guard checks and the proposed
113-row provenance manifest are retained under
`.secrets/feedback-supervision-20261125/` and are excluded from Git.
