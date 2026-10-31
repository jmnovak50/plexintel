# Global Eligibility implementation report

October 31, 2026. **Implementation: GO for architectural review. Production activation: CONDITIONAL GO, pending separate optional-migration review and deployment authorization.** Nothing was migrated, deployed or enabled in production.

## Implemented

- Pure deterministic engine and strict policy models: `api/services/global_eligibility.py`.
- Transactional policy versions, evidence snapshots, complete-inventory evaluations, history/deltas, SQL pagination/search and overview: `api/services/eligibility_workspace.py`.
- Administrator API, authorization, origin checks, sanitized errors and default-disabled write gate: `api/routes/eligibility_admin_routes.py`, registered in `api/main.py`.
- Optional manual migration: `api/db/migrations/optional/global_eligibility/001_initial.sql`. Three eligibility-only tables, one identity sequence and supporting indexes; no discovery/application table alterations.
- Functional React workspace: `frontend/src/pages/AdminEligibility.tsx`; funnel and shared foundation layouts in `frontend/src/components/EligibilityViews.tsx`.
- Community Engagement, Request Management and My Request Queue foundations: `frontend/src/pages/ContentLifecycleFoundation.tsx`, copy in `frontend/src/lib/contentLifecycle.ts`. Routing/navigation updated using existing shell, admin navigation and Recommendations. Canonical discovery deep links open the matching typed title.
- Write-free assessment CLI: `scripts/preview_global_eligibility.py`; guarded isolated runner: `scripts/run_eligibility_tests.py`.
- Rule, API, schema-drift, persistence, history, scale and UI regressions: `tests/test_global_eligibility.py`, `tests/frontend_eligibility.test.cjs`.
- Architecture, precedence, future contracts, rollout and limitations: [content-lifecycle.md](content-lifecycle.md). Existing workspace documentation links to it.

Existing database connection, session administrator authentication, UI components, strict unified discovery schema validation and optional-migration conventions are reused. Immutable eligibility policies carry installation configuration and history in one place; duplicating those values into mutable `app_settings` overrides would obscure which version was evaluated. No new settings bootstrap, scheduler, worker or pipeline job was added. Complete local evaluations are synchronous and atomic.

## Rule behavior

Initial instance preferences exclude only positive known movie runtimes below 60 minutes and explicitly confirmed recorded sporting events. Documentaries, TV movies, foreign languages, stand-up and concerts retain by default. Every rule is independently enabled/disabled and configurable to retain/exclude. Runtime and local-language parameters are editable. Sports/stand-up/concert confirmations require exact movie/TV identity and supporting evidence, not title/keyword guesses.

Any matching exclusion wins; retain is not an exemption. Missing evidence retains and is traced. Multiple reasons are retained. TV runtime cannot trigger the short-movie rule. Discovery's TV premiere classification and global eligibility remain separate. No popularity, ratings, votes, availability, request-status or prediction filtering was introduced.

Policies use optimistic version checks. Repeating identical policy saves preserves the version; repeated evaluations add audit runs with unchanged outcomes for unchanged inputs. Policy/engine/input references and complete relevant per-title evidence are persisted. Failure rolls back all evaluation writes; canonical discovery/history is never updated or deleted. Catalog checks reject incompatible/partial eligibility schemas and altered stored policy hashes before publishing evaluations.

## Actual read-only inventory evaluation

Snapshot: **October 31, 2026, 09:19 CDT** (`2026-10-31T14:19:17Z`). PostgreSQL explicitly reported a read-only transaction. No HTTP requests or production evaluation writes.

| Scope | Discovered | Excluded | Retained |
|---|---:|---:|---:|
| Movies | 832 | 353 | 479 |
| TV series | 130 | 0 | 130 |
| Total | 962 | 353 | 609 |

All 353 exclusions are `short_movie_excluded` with positive runtime below 60. Examples: *The SAS* (`movie:741533`, 17 minutes), *Lost Tape* (`movie:1211637`, 5 minutes), *Nightblade* (`movie:1293266`, 10 minutes). This is a policy assessment, not a target-count reduction or engagement prediction.

242 movies lack usable runtime evidence and are not excluded on that basis. All 962 titles have unresolved sporting-event evidence, because no title confirmations were supplied and Seerr does not establish that category definitively. Thus all titles have at least one incomplete exclusion check; this includes the 353 independently excluded short movies. The UI explicitly explains this overlap. Missing media/request statuses were not interpreted as absence or availability, and were not mutated.

The complete 962-title evidence and decision trace is preserved privately at:

`artifacts/seerr-exploration/2026-10-31-global-eligibility/production-preview.json`

Inventory snapshot SHA-256: `faaa7e0d36b5e792fb162f1125d21befc87889da2201dcd00254bb91f093dd9c`.

## Validation

- **375 Python tests passed**, including **65 new eligibility regressions**. Existing Content Discovery, movie/TV canonical discovery, discovery remediation, pipeline service/routes/scheduler and app-settings tests are included.
- Regression coverage: runtime boundaries, TV runtime isolation, unknown/invalid language evidence, non-inferred content categories, every independent rule, multiple reasons/retain precedence, confirmation provenance and typed identities, deterministic results, policy validation/version conflicts, history/deltas, failed enrichment, atomic failure rollback, read-only preview without optional schema, inventory staleness, writer lock conflict, canonical/history preservation, pagination/literal search, schema/constraint/type drift and policy-hash tampering.
- A complete **2,002-title** synthetic inventory is evaluated and persisted without a cap; result paging and the run/outcome/type index are verified. This is a disposable database, not a production population experiment.
- **12 UI tests passed** (six new eligibility/foundation checks and six existing discovery checks).
- **15 headless Firefox acceptance checks passed** against the staged production build and an isolated fixture API/database: live counts, first evaluation/funnel, 25-item paging/next, typed TV filter, search/evidence link, draft preview, policy save/reevaluation, historical deltas/results, three foundation screens, ordinary-user queue access, and non-admin workspace rejection.
- Targeted ESLint and TypeScript validation passed with no errors. The existing Recommendations effect-dependency lint warning remains unchanged; new eligibility/foundation files are clean. Vite production build passed into `/tmp/plexintel-eligibility-build-20261031`; active `frontend/dist` was not overwritten. Existing Browserslist age notice only; no dependency update was performed.
- `git diff --check` passed.

The test runner installs exact disposable-DSN and no-HTTP guards **before application imports**. The cluster listens only on its dedicated `/tmp/plexintel-seerr-fixture.*` Unix socket and verifies its own data directory and disabled TCP. No production integration tests, settings writes or Tautulli/Seerr calls were used. One initial browser attempt overlapped fixture recreation by the database suite and was discarded; sequential final database and browser checks passed. This was test-fixture interference, with no production connection.

Private detailed evidence, logs and harnesses:

`artifacts/seerr-exploration/2026-10-31-global-eligibility/`

Key files: `pytest.xml`, `pytest.log`, `frontend-tests.log`, `frontend-build.log`, `browser-checks.json`, `benchmark.json`, `production-preview.json`, `production-isolation.json`. The artifact directory is ignored by Git. It includes local harnesses for reproducing the isolated browser run; no production credentials/cookies are included in the deliverable.

## Performance and storage

An isolated 2,002-title fixture measured approximately 0.53 seconds for a complete evaluation and 0.019 seconds for a 25-result page. Those are local illustrative measurements, not a production SLA; final measurements are recorded in `benchmark.json`. Result snapshots/indexes occupied approximately 4.74 MB for that evaluation; policy/run tables approximately 82 KB combined. Sizes depend on metadata, reasons and confirmation text. Historical growth is linear in title evaluations; no automatic retention deletion or recurring evaluation was introduced.

Wildcard substring search can scan one evaluation's results. Existing indexed run/outcome/type lookups and SQL paging are appropriate to the current inventory. The 30-second per-statement timeout and atomic rollback remain safeguards; much larger inventories need a separately reviewed job/retention approach rather than silent truncation.

## Production isolation

Final read-only verification confirmed:

- 962 titles (832 movie/130 TV), 1,049 observations, six discovery runs.
- No eligibility tables installed or production eligibility records created.
- Persistent discovery remains disabled; preview, persistence, scheduling and new eligibility-write gates are false/default-disabled.
- Backend healthy and active, original PID `169181`, original October 30 12:14:01 CDT start, zero restarts.
- Published frontend files still match the pre-existing committed deployment.

No production database mutation, acquisition/notification, model scoring/training, embeddings/label changes, migration, service restart, scheduler registration or persistent configuration change occurred. The production database writer's previously accepted temporary superuser exception is unchanged; least privilege was not claimed or altered.

## Reproduction and activation boundary

From the repository root, a safe read-only assessment (optional new output file, never overwrites an existing audit):

```bash
plexenv/bin/python -B scripts/preview_global_eligibility.py \
  --output /tmp/plexintel-eligibility-audit.json
```

For isolated regression tests, first provision the repository's established TCP-disabled fixture with database `plexintel_seerr_fixture`, data directory `<socket-directory>/data`, and socket directory `/tmp/plexintel-seerr-fixture.*`. Use its actual socket and port, never production:

```bash
SEERR_DISCOVERY_TEST_DSN='host=/tmp/plexintel-seerr-fixture.REPLACE port=55519 dbname=plexintel_seerr_fixture' \
  plexenv/bin/python -B scripts/run_eligibility_tests.py
/opt/homebridge/bin/node --test --test-isolation=none \
  tests/frontend_eligibility.test.cjs tests/frontend_discovery.test.cjs
cd frontend
/opt/homebridge/bin/node node_modules/typescript/bin/tsc -b
/opt/homebridge/bin/node node_modules/eslint/bin/eslint.js \
  src/pages/AdminEligibility.tsx src/pages/ContentLifecycleFoundation.tsx \
  src/components/EligibilityViews.tsx src/lib/contentLifecycle.ts \
  src/pages/AdminDiscovery.tsx src/components/AdminNav.tsx src/components/AppShell.tsx
/opt/homebridge/bin/node node_modules/vite/bin/vite.js build \
  --outDir /tmp/plexintel-eligibility-staged
```

Production activation requires a separate review of the optional migration, recovery/ACL/target checks, then separately authorized installation and code/UI deployment. Enabling `GLOBAL_ELIGIBILITY_WRITES_ENABLED=true` is a separate explicit configuration decision. It does not enable discovery. The first production eligibility policy/evaluation is an additional operator action, not an automatic deployment side effect. No migration or deployment command was executed here.

## Remaining next-stage decisions

- Confirm installation preferences and any trustworthy recorded-event evidence. Without confirmation the sports rule conservatively retains unknowns.
- Review metadata correctness, policy/evaluation cadence, retained-subset freshness requirements and history retention/storage growth.
- Design the feature/identity path for out-of-library discovery scoring, immutable per-user/cohort predictions, model-version provenance and title-level binary offer qualification.
- Refine requester/user mappings, assignment supersession, explicit release/decline intent, external Seerr reconciliation and delivery idempotency. Preserve score histories, actions and playback as separate signals; ignored notifications remain neutral.

**Recommend architectural acceptance of the implemented Global Eligibility stage and future workspace contracts. Production use remains conditional on the separately reviewed migration/deployment/enablement steps. No Community Engagement scoring, assignment, notifications or request automation was implemented.**
