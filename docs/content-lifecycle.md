# Content lifecycle and Global Eligibility

Implemented October 31, 2026. Repository implementation only: no production migration, deployment, eligibility write, discovery run, scheduling or acquisition was performed.

## Boundaries and navigation

| Stage | Workspace | Responsibility | Implemented now |
|---|---|---|---|
| Discovery | `/admin/discovery` | Canonical source inventory, metadata and observations | Existing implementation preserved; supports typed record deep links |
| Global Eligibility | `/admin/eligibility` | Deterministic instance exclusions with policy and evidence history | Complete administration API, engine, preview, persistence and UI |
| Community Engagement | `/admin/engagement` | Per-user predictions, rankings, offer qualification | Authenticated administrator foundation only |
| Request Management | `/admin/requests` | Assignment, notification and external-request investigation | Authenticated administrator foundation only |
| My Request Queue | `/requests` | Recipient offers, explicit release/decline and supersession history | Authenticated user foundation only |

Future foundations have no operational metrics, buttons, outbound requests or new data tables. The queue is available from Recommendations and the shared page shell. Administrative navigation contains all four administrative lifecycle workspaces. Existing recommendations and ML pipeline remain independent.

## Eligibility rules and precedence

The installation defaults are preferences, not a product definition of worthwhile content:

| Rule ID | Default enabled/action | Definitive evidence |
|---|---|---|
| `short_movie` | yes / exclude | Canonical positive integer movie runtime strictly below 60 minutes; 60 is retained. Never TV episode runtime. |
| `recorded_sport` | yes / exclude | Administrator-confirmed exact typed identity and supporting evidence reference |
| `documentary` | yes / retain | TMDB genre 99, or administrator confirmation |
| `tv_movie` | yes / retain | TMDB movie genre 10770, or administrator confirmation; not applicable to TV series |
| `foreign_language` | yes / retain | Known canonical original language outside installation local languages (initially `en`) |
| `standup` | yes / retain | Administrator confirmation |
| `concert` | yes / retain | Administrator confirmation |

Each rule can be disabled or set to retain/exclude independently. Runtime threshold and local languages are configurable. Policies must specify exactly the supported rules, reject extra fields and invalid values, and validate confirmation identities, uniqueness and evidence. The administrator edits confirmation arrays under each category using `{ "media_type": "movie", "tmdb_id": 123, "evidence": "Source reference and confirmation" }`. Apply evidence entries to the draft before preview/save. Confirmations are policy evidence, not source-supplied classifications, and are included in policy history.

**Any enabled matching exclusion wins.** Retain rules are not exemptions. A 30-minute documentary is excluded by `short_movie` even though documentaries are retained. Multiple matching exclusion reasons are preserved. `*_excluded` codes identify the exact rule; threshold or confirmation evidence is stored with the decision.

An exclusion rule with unknown evidence adds `*_evidence_unknown`; it cannot exclude. An independent definitive exclusion can coexist with uncertainty. Disabling a rule produces a `disabled` trace, not a category exemption. Runtime/language rules cannot use administrator confirmations as overrides.

Seerr has no reliable recorded-event, stand-up or concert discriminator. Neither title text, synopsis, keywords nor broad Sports/Music/Comedy genres establish these categories. Missing a genre does not definitively prove category absence. These rules need explicit confirmation to match. Consequently the default sporting-event exclusion produces uncertainty for all unconfirmed titles; this is deliberate, not a claim that all titles are sports. Disabling that rule removes that unresolved exclusion check. Unsupported, absent, malformed, undetermined or non-linguistic language codes remain unknown (`und`, `xx`, `zxx` included).

No popularity, votes, ratings, predicted engagement, request status or availability rules exist. Missing/failed enrichment and unknown media/request status do not mean unavailable, absent or ineligible. A previously known canonical field can still support a decision after a later failed enrichment; the snapshot records its provenance and enrichment state. Release dates do not imply digital availability.

TV premiere classification remains a separate discovery concern. Every canonical TV identity, including provisional classifications, enters global evaluation. Global `retained` is not discovery `eligible`, model qualification or acquisition approval.

## Evaluation and history

`api/services/global_eligibility.py` is a pure deterministic engine (`eligibility-v1`). Equivalent evidence and policy produce identical outcomes and ordered reason traces. `api/services/eligibility_workspace.py` uses existing `connect_db`, typed discovery identities and strict existing V2 discovery schema validation. It has no Seerr client, model import or acquisition path. The optional eligibility schema is also catalog-validated: relation kinds, column types/nullability/identity/defaults, primary and foreign keys, check constraints, constraint/index validity and unexpected triggers. Partial or incompatible installations fail closed; stored policy hashes and shapes are verified before use.

Read operations use read-only repeatable-read transactions, bounded statement/lock timeouts and SQL pagination/search/sort. A write is a synchronous, explicit administrator operation serialized with a dedicated advisory try-lock. It captures the complete canonical inventory using one ordered SELECT, then atomically inserts an immutable run and its results. Writers use READ COMMITTED so a newly acquired lock sees the latest committed policy; the one SELECT provides a consistent input snapshot. There is no result cap and no automatic retry. Failure rolls the entire transaction back; there is no partially published retained subset or background job to recover.

Policy saves append versions, require the administrator's expected current version and return a conflict on stale edits. Saving an identical current policy is a no-op. The first evaluation materializes installation defaults if no policy was saved. Repeated evaluations create new audit runs, retaining identical decisions for identical inputs. No startup policy seeding or application-settings writes occur.

A run preserves policy version, engine version, actor/time, inventory hash, counts by media/reason, preceding run and changes: added/missing identities, retained→excluded, excluded→retained and explanation changes. Each result preserves typed identity, title, decision, all reasons, uncertainty, per-rule trace and exact relevant input snapshot. Input includes metadata fingerprint, runtime/language/genres, field states, enrichment timestamp/state, first discovery timestamp/run, metadata source key and first-discovery source ID/key. It intentionally does not copy credential-bearing raw configuration or unrelated user data.

The overview distinguishes live discovery counts from the latest evaluated snapshot. New inventory and changed metadata/source fingerprints are flagged; policy changes require reevaluation. The UI never labels newly added or changed records as currently evaluated by implication. Results can select any historical run; history shows the full policy and changes. Reason counts may overlap.

The future retained-subset contract is **an explicitly chosen successful atomic eligibility run**, queried from `eligibility_results WHERE run_id=:run_id AND outcome='retained'`, joined to that run's policy and evidence. Consumers must verify inventory/policy freshness and retain the run reference. Do not use an unversioned live boolean or silently consume stale results.

## HTTP and security

All endpoints below are under `/api/admin/eligibility` and require existing session administrator authorization. Non-administrators receive 403 and anonymous callers 401. Errors never serialize database connection details.

| Method/path | Behavior |
|---|---|
| GET `/overview` | Live discovery totals, evaluated snapshot and staleness |
| GET `/policy` | Saved policy or unsaved defaults, migration/write capability |
| POST `/preview` | Complete-inventory, read-only draft impact; counts and representative exclusions; no policy/run writes |
| PUT `/policy` | Append a policy version with optimistic version check |
| POST `/evaluations` | Atomically evaluate/persist complete inventory against saved version |
| GET `/evaluations` | Paginated run history, policies, totals and changes |
| GET `/results` | Paginated/searchable/sortable results, optional historical run, media/outcome/uncertainty filters |

All POST/PUT actions also require matching origin scheme/authority, `X-Eligibility-Action: 1`, and reject cross-site fetch metadata. `GLOBAL_ELIGIBILITY_WRITES_ENABLED` defaults false and is checked before any write connection. This gate is distinct from, and does not enable, any discovery feature gate. GET/page loads never create eligibility policies or runs. Preview requires no optional eligibility tables. Existing authentication behavior is reused, not redesigned.

## Optional persistence and rollout boundary

`api/db/migrations/optional/global_eligibility/001_initial.sql` creates only:

- `eligibility_policies`: identity version PK, actor/time, hash and JSON policy.
- `eligibility_runs`: UUID PK, policy FK, previous-run FK, engine/input fingerprint, summary and delta.
- `eligibility_results`: `(run_id,media_type,tmdb_id)` PK, run FK and canonical typed-title FK, decision, evidence and snapshot.
- One policy identity sequence and three supporting indexes for history, filtered results and title order; PUBLIC grants revoked.

No discovery or existing application table is altered. No new role, credential or scheduler is introduced. History foreign keys restrict deletion rather than cascading away evidence. The application exposes no history edit/delete operation. Database owners can still change rows directly; this is application-level immutability, not tamper-proof storage.

The migration is outside the startup `migrations/*.sql` glob. It is one-time, transactional and deliberately fails if these objects already exist, rather than accepting unverified schema drift. **Production application requires separate schema review/authorization. It was applied only to disposable tests.**

After separate review, with a separately verified `DATABASE_URL` already in the operator's environment, the proposed command is:

```bash
psql -X --dbname="$DATABASE_URL" -v ON_ERROR_STOP=1 --single-transaction \
  -f api/db/migrations/optional/global_eligibility/001_initial.sql
```

Do not print the URL, source credential files into shell logs, run this on deployment implicitly, or assume Docker. Verify target, schema/ACLs, source inventory, recovery readiness and installation conventions before authorization. The current production `jmnovak` superuser exception remains accepted temporary risk; this work does not claim least privilege or change privileges. Eligibility writes additionally require separate configuration/deployment approval for the new gate. No scheduler integration is planned here.

If a transaction fails, preserve existing data and report; retry is an explicit administrator decision. UI rollback needs no data rollback. After successful use, dropping eligibility tables would destroy policy/decision history and requires separate approval; no automatic down migration or destructive cleanup is supplied.

## Preliminary future contracts — documentation only

These are refinement starting points, not new tables or authorization to execute them. All title references retain `(media_type,tmdb_id)` and discovery source provenance; user references use a stable internal user identity with separately captured external mappings. UUID event/snapshot identities and UTC occurrence/recording timestamps are proposed. Histories should be append-only, with explicit idempotency keys for delivery and user actions.

| Entity / owner | Preliminary identity and fields | Evidence relationships |
|---|---|---|
| Eligibility evaluation / eligibility | Implemented run UUID + typed title, policy version, outcome/reasons/input | Canonical discovery and source; stable retained-subset input |
| Prediction snapshot / engagement | snapshot UUID; scoring-run identity, model artifact/version, feature-contract version, typed title, user ID, probability/score definition, applicable-user cohort, rank/tie handling, explanation/provenance, scored time; title-level offer qualification evidence belongs to the scoring cohort | Eligibility run/result; preserve each user's scores across runs, not just winner; missing scores are not zero |
| Assignment decision / request management | decision UUID; typed title, selected user (nullable for no offer), community qualification decision reference and selection rationale, prediction/cohort reference, prior decision UUID being superseded, actor/reason | Separate from predictions; explicit winner/rank evidence and complete supersession chain, no implicit expiry |
| Notification event / notification delivery | event UUID; assignment decision, intended recipient/channel, intent/delivery/failure event, attempt/idempotency identity, timestamps | Intent precedes delivery; ignored is neutral, not decline or negative engagement |
| User request action / recipient workflow | action UUID; assignment/offer, authenticated recipient, `release_intent` or `decline`, idempotency key, actor/time, optional explicit rationale | A release is intent, not a successful Seerr request. Decline is explicit feedback; neither is observed playback |
| External request observation / Seerr reconciliation | observation UUID; stable source ID/key + provider request ID, typed title, provider status, observed/source timestamps, requesting source user when known, optional verified internal user mapping | Link assignment/action only with reliable evidence; preserve direct Seerr/Plexgen requests even without an offer; unknown requester stays unknown |
| Engagement outcome / playback integration | outcome/event UUID; actual source playback identity, user mapping, canonical↔library identity resolution, playback timestamps/duration/outcome, evidence reference | Reuse existing `watch_history`/`watch_sessions` evidence and privacy rules; deduplicate actual playback independently of request/notification events |

Community Engagement owns the future title-level binary offer qualification and its evidence; assignments consume that decision without changing predictions. Prediction scores, binary offer decisions, proposed/current assignments, notification delivery, request intent, external request status and actual engagement are separate signals. A recipient action on a superseded offer must eventually be checked against assignment history; do not silently apply it to a new recipient. An ignored notification creates no action event or negative training label. Assignment history has no inherent waiting period, expiration, cooldown or minimum holding duration.

For A→B→A requester changes, join decisions through `supersedes` to the exact scoring cohorts and each user's prediction snapshots, model/feature versions, tie/rank explanations, notification events, external observations and actions. Preserve evidence before deciding whether stabilization is needed. No stabilization logic is implemented now.

Current scoring (`score_model.py::score_and_store`) operates on existing library/user embedding inputs and replaces recommendation outputs; `shap_prediction_context` offers existing model explanation provenance. It is not an immutable discovery-title prediction history. Future discovery scoring needs an explicit feature/identity compatibility design; do not pass unseen TMDB identities into library scoring or repurpose the current recommendation table as assignment history. No scorer, embeddings, labels, recommendations, pipeline stages or training behavior changed here.

## Operations, performance and limits

Evaluation is O(inventory × rules), with bounded seven-rule traces and batched result inserts. Confirmations are indexed once per policy/evaluation. SQL handles results pagination and indexed run/outcome/type lookups; literal search uses ILIKE with escaped wildcards. Arbitrary substring search can scan a run; no extra search infrastructure is introduced. Snapshots intentionally repeat relevant evidence for auditability; storage grows per title per evaluation. There is no recurring schedule, retention deletion or implicit reevaluation. Review growth and evidence retention before frequent operation.

There are no external network retries, worker registrations or pipeline jobs. Synchronous full-inventory evaluation is appropriate to the current small inventory; statement/lock timeouts fail atomically. Larger inventories may require an explicitly designed job path later; do not silently truncate. Existing pipeline history is not reused for eligibility because eligibility is a local atomic transaction, not a Seerr/ML execution job.

Read-only inventory assessment and isolated validation results are recorded in [the implementation report](global-eligibility-implementation.md).
