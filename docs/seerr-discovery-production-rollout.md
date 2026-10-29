# Phase 3 — production preflight and controlled rollout

**Bounded Gate B2 completed — October 28, 2026, 22:07 CDT: PASS.** The operator authorized one movie-only 2026-10-28/page-1 execution with 25 attempts maximum. It persisted **20 movies / 20 observations / one terminal partial run**, enriched all 20 using **21 GET attempts / zero retries**, and exited 2 for the expected page limit. Persistent discovery remains disabled. See [B2 audit](seerr-discovery-gate-b2-validation.md). The seven-day B2 proposal below was not executed; any further run requires separate authorization.

**Targeted B1 follow-up — October 28, 2026, 21:23 CDT:** all four failed movie details returned HTTP 200 on one bounded follow-up each. Original 936 identities/window retained; 22 unknown movie dates, 235 remaining unknown runtimes and TV 120/5/0 retained. **GO for separately authorizing B2; discovery remains disabled and no writer ran.** See [targeted verification](seerr-discovery-gate-b1-targeted-verification.md).

**Original Gate B1 result — October 28, 2026:** read-only preview completed with **811 movies / 125 TV**, full pagination, and partial enrichment (four movie transport failures). TV: **120 eligible / 5 provisional / 0 ineligible**. **Initial Gate B2 recommendation: NO-GO pending review of failed calls; no persistence was run.** See [B1 validation](seerr-discovery-gate-b1-validation.md).

**Current production status — October 28, 2026, 20:51 CDT:** Gate A completed: migration **002 committed**, strict V2 verification **PASS**, inventory empty, discovery **disabled**. See [Gate A verification](seerr-discovery-gate-a-verification.md). Earlier V1/preflight statements below are historical; do not rerun 001/002 or proceed to Gate B without separate authorization.

## 1. Historical preflight assessment and approval boundaries

**CONDITIONAL GO for separately authorizing Gate A.** The implementation reflects the completed readiness remediation; no unrelated code changes are required. Production currently has **verified V1**, so the remaining production migration is **002 only**. Do not rerun 001 or execute discovery against the current V1 database.

This assignment performed read-only production inspection and two non-discovery Seerr GETs. It did **not** apply migrations, write production records, run discovery/preview, change configuration/privileges, restart services, run models/acquisition, schedule jobs, commit or deploy. **Stop here pending explicit Gate A authorization.** Each later gate requires its own approval; Gate A cannot authorize Gate B.

Evidence: `/home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-28-rollout-preflight/` (owner-only). The prepared helpers in that directory are runbook artifacts, not application code, startup hooks or installed jobs. Their mutation mode has **not** been used with a live production connection; an offline commit-loss simulation used mocked database calls only. All commands below run under Bash on **birch**, from the repository root, using `plexenv`; Docker is not involved.

| Gate | Readiness | What approval would authorize |
| --- | --- | --- |
| A | **PASS / completed at 20:51 CDT** | 002 committed and verified; stop, do not rerun |
| B1 | **Completed / partial enrichment; full pagination** | Read-only result recorded; do not rerun automatically |
| B2 | **PASS: one bounded movie-only validation completed** | One day/page1,20movies,21attempts; stop. Seven-day proposal and any further run remain unauthorized. |
| C | Needs B review and separate approval | One idempotency execution; separately bounded wider coverage |
| D | Deferred; not authorized | Future schedule design/registration only after operational review |

## 2. Verified production environment

Observed **October 28, 2026 at approximately 20:29 CDT**; recheck transient facts before execution.

| Item | Evidence |
| --- | --- |
| Host/runtime | `birch`; `/home/jmnovak/projects/plexintel`; Python **3.13.5**, `/home/jmnovak/projects/plexintel/plexenv/bin/python` |
| Active backend | `plexintel-backend.service`, active, PID **1633**, started October 27 23:45:34 CDT; unit `/etc/systemd/system/plexintel-backend.service`; working directory and interpreter match this checkout/environment |
| Dependencies | requests **2.34.2**, python-dotenv **1.2.2**, psycopg2-binary **2.9.12**; `pip check`: no broken requirements (pip cache unavailable, so disabled) |
| PostgreSQL | Authenticated **192.168.1.9:5432 / plexintel / jmnovak**, PostgreSQL **18.6**, online, not in recovery; inspection transaction read-only |
| Connection selection | Existing `api.db.connection`: `DATABASE_URL` takes precedence, otherwise `DB_*`; CLI loads repository `.env` without replacing exported values. Effective URL matched the running backend without printing it. |
| Installed discovery | V1 movie table present, V2 title table absent; **0 runs / 0 movies / 0 observations**; identity sequence last_value **1**, is_called **false**; no source bindings to adopt |
| Catalog compatibility | Live V1 catalog exactly matched canonical 001 built in a disposable PostgreSQL 18 fixture: **64 columns, 19 core constraints, 11 indexes**, ownership/ACLs and sequence dependency |
| Activity/isolation | No discovery CLI, discovery advisory lock, active discovery database session or enabled DDL event trigger observed. User/root cron and user/system timer checks found no Seerr discovery schedule. |
| Writer authority | `jmnovak` is a **superuser**, with role/database administration, replication and RLS-bypass privileges; required database/schema/advisory-lock access is effective. This is the **accepted temporary security exception**, not least privilege. No role, credential or grant changes are planned. |

The current CLI writer **and summary** reject V1. This is expected version safety, not a missing migration to run automatically. Ordinary backend behavior does not import/run this discovery CLI; no backend restart is required for these manual host commands.

Production schema, active process and application metadata are captured in `production-audit.json`, `production-v1-catalog.json`, `production-extra.json` and `host-runtime-configuration.json`. No write probe or sequence increment was used.

### Recovery readiness

The existing private archive remains available and checksum-matched:

```text
/home/jmnovak/.local/state/plexintel/preflight-backups/plexintel-20261028T231846Z-08d8dc.dump
174148995 bytes
SHA-256 8754923a28ed13c140cb269e59b2389786e4d653e6cfbfcf14bb46fb06d52f1a
```

Its consistent snapshot is **October 28 at 18:18:46 CDT**, before V1 and V2. Prior isolated PostgreSQL 18 restore evidence is PASS, with **40 table counts matched**; this preflight rechecked the archive checksum and that evidence, without another backup or restore. The recovery point is approximately two hours older than this preflight and continues to age. Before Gate A, accept that recovery-point age/data-loss window explicitly or separately authorize a fresh consistent backup and update this runbook; do not overwrite the validated archive.

Recovery requires PostgreSQL/extension binaries (including vector/vchord), referenced roles and application/filesystem configuration outside the single-database archive. Full application/host recovery and PITR were not established. WAL archiving remains off. Root cron still runs image backup at **03:02 Friday** (`2 3 * * 5`), with `/media/rpibk/backup.img` last modified October 23 03:13:34 CDT. The image script uses live rsync without a PostgreSQL backup protocol; existence/mtime does not establish database-consistent recoverability. No backup architecture or schedule was changed.

## 3. Migration order, prerequisites and rollback semantics

Actual files, in order:

1. `/home/jmnovak/projects/plexintel/api/db/migrations/optional/seerr_discovery/001_initial.sql` — original movie-only baseline, **already installed and verified**.
2. `/home/jmnovak/projects/plexintel/api/db/migrations/optional/seerr_discovery/002_unified_titles.sql` — V1-to-V2 forward upgrade, **not installed**.

A fresh, separately approved installation needs 001 then 002. **This production database needs only 002.** The prepared production command intentionally refuses an absent, drifted, populated-since-review, mixed or already-upgraded state rather than guessing a migration sequence. Populated migration correctness is covered by tests, but newly appeared production records require an updated review before this empty-inventory deployment plan is used.

| File | Reviewed SHA-256 |
| --- | --- |
| `001_initial.sql` | `fb54db94d34f7f00193f76164425adbea8f531c4cf5468e8c56baa9f342cb69c` |
| `002_unified_titles.sql` | `838902e5ef6b9d2dcccf257dbdcc2543f0673c90ebdc0eb3cbb979980d07a1c2` |
| `rollback.sql` | `34251738d74ca36b498de67b10ab452d96181e724bc33b83fa2d8883ee1e9d5b` |

001 relies on the caller's single transaction. 002 is one atomic `DO` statement; use an explicit outer transaction as prepared below. Both use advisory lock **(184725,30)** and a **five-second lock timeout**. 002 takes exclusive locks on the three discovery tables, rejects unexpected schema/dependencies and preserves run history, provenance, values, timestamps, fingerprints, ownership/ACLs and identity sequence state.

002 renames `seerr_discovered_movies` to `seerr_discovered_titles`; renames `release_date`/`discovery_release_date` to `premiere_date`/`discovery_premiere_date`; adds typed movie/TV identity and targeted TV/eligibility JSONB; rebuilds the composite PK/FK/observation uniqueness and affected indexes. Expected V2 is **three tables, 68 columns, 24 core constraints, 11 indexes**, plus the existing internally owned observation identity sequence. Canonical key: `(media_type, tmdb_id)`; titles' `first_discovery_run_id` and observations' `run_id` reference runs, while observations' typed title FK references that canonical key. Observation uniqueness: `(run_id, media_type, tmdb_id, scope_key)`. Existing rows become `movie`; future writes require explicit media type.

The normal migration runner only globs top-level `api/db/migrations/*.sql`. These nested optional migrations are outside that glob; startup and the CLI cannot install them. Never run the broad application schema bootstrap for this rollout. No grants, new users, extension installation, model/pipeline changes or deployment prerequisite were identified.

The existing `rollback.sql` is **V1-only and destructive**. It is incompatible with V2 and must not be run after 002. See section 9 and [the separate rollback strategy](seerr-unified-discovery-rollback.md).

Validation: the prior focused suite passed **271 tests** including populated migration/rollback/identity drift scenarios; current reviewed source hashes match that evidence. This preflight additionally built canonical 001 in a new TCP-disabled fixture, compared it exactly to live V1, applied 002 **only there**, and confirmed the strict runtime guard accepts the result. The fixture was stopped and removed. No full suite was repeated without source changes.

## 4. Configuration readiness

Keep the existing owner-only configuration unchanged:

```text
/home/jmnovak/.config/plexintel/seerr-discovery.env
owner 1000:1000; mode 0600
SEERR_DISCOVERY_ENABLED=false
SEERR_DISCOVERY_SOURCE_ID=plexintel-seerr-primary
```

It contains the existing normalized Seerr endpoint and available API credential; neither is reproduced in logs or this runbook. The endpoint SHA-256 remains `4547479bd1da2cd5fab4ff1af5e07bb9617e2dd37900447eb261491ec5330139`. Legacy `.seer_creds` was not modified. Never put a key/password in arguments, source it through shell tracing, rotate credentials or change the backend connection for this rollout. Environment values override private configuration; the prepared guards reject a different endpoint/identity, enabled configuration or database URL that differs from the active backend.

Current effective defaults: **movie only**, language **all**, UTC lookback **14 days**, lookahead **90 days**, **14-day windows**, primary-release-date ascending; page cap **500 per scope**, request budget **10000 per invocation including retries**, retries **2**, timeout **25 s**, interval **0.3 s**, retry-after ceiling **60 s**; metadata cache **on**, TTL **24 h**, failed cooldown **1 h**, refresh batch **1000**. `REFRESH_BATCH_SIZE` limits `--enrich-due`, **not ordinary discovery enrichment**. The controlled commands below override broad defaults explicitly without editing the private file.

Connectivity/authentication: exactly **GET `/api/v1/status`** and **GET `/api/v1/auth/me`** returned HTTP 200 without redirects; the auth body was not retained. Reported Seerr version **3.5.1**, commit `564bfb08b54caa374bddaf820abfd226e5e69151`. The [discovery route](https://github.com/seerr-team/seerr/blob/564bfb08b54caa374bddaf820abfd226e5e69151/server/routes/discover.ts), [TV mapping](https://github.com/seerr-team/seerr/blob/564bfb08b54caa374bddaf820abfd226e5e69151/server/models/Tv.ts), search mapping, TV route and TMDB adapter at that reported commit are byte-identical to the inspected development contract. This checks version-referenced source compatibility, not attestation of every running binary or live discovery/detail response. **No discovery/enrichment GETs or CLI dry-run were issued.**

Movie dates mean primary release; TV means original series premiere, supported by a matching dated Season 1. Neither proves digital availability. Missing/conflicting TV evidence stays provisional and auditable; unknown catalog/request status remains independent. Eligibility is not engagement prediction, a score or acquisition permission.

## 5. Gate A — completed; commands retained for audit

### Historical pre-install V1 checks (now superseded by V2 verification)

```bash
cd /home/jmnovak/projects/plexintel
umask 077
set -euo pipefail
set -o noclobber
sha256sum -c artifacts/seerr-exploration/2026-10-28-rollout-preflight/runbook-inputs.sha256
plexenv/bin/python artifacts/seerr-exploration/2026-10-28-rollout-preflight/guarded_gate_a.py --check-v1
systemctl show plexintel-backend.service --property=MainPID --property=ActiveState --property=NRestarts
```

The checksum list covers the prepared helpers/catalogs and the reviewed runtime/migration manifest. `--check-v1` verifies the effective backend target, authenticated server/version, disabled private configuration, reviewed source/migration hashes, archive integrity/PASS record, exact V1 columns/constraints/indexes/owner/ACL/sequence catalog, fresh counts and no discovery activity/locks or enabled DDL event triggers. It is read-only and never issues HTTP. No role/password/ACL changes are required.

### Authorized Gate A command — executed once; DO NOT RERUN

The operator subsequently authorized Gate A only. The following guarded command was executed once successfully; its receipt and separate verification are linked above. This block is retained as an audit record:

```bash
cd /home/jmnovak/projects/plexintel
umask 077
set -euo pipefail
set -o noclobber
plexenv/bin/python artifacts/seerr-exploration/2026-10-28-rollout-preflight/guarded_gate_a.py \
  --apply-reviewed-v2 \
  > artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-a-install.json
```

The prepared helper starts read-only with the existing connector convention, then changes only its own connection to a write transaction after all guards. It takes the advisory lock without waiting, locks the discovery tables with a five-second limit, immediately repeats target/config/catalog/count checks, executes the checksum-verified 002 bytes, validates exact V2 catalogs **and the actual runtime guard before commit**, preserves sequence state and compares unrelated application schema/ownership/ACL/role metadata against its immediate pre-DDL snapshot. A **120-second statement limit** bounds this small empty-schema upgrade. Any precommit failure rolls back; it does not repair drift or retry.

After commit, it repeats V2/non-discovery metadata checks read-only. Output distinguishes `commit_attempted`, `commit_confirmed`, verification PASS/STOP and counts. If connection loss makes commit uncertain, **inspect; do not rerun or roll back blindly**. The helper's read-only `--check-v1` mode passed against production. An offline mocked commit/rollback/close failure preserved structured STOP/uncertain-commit output. The live mutation path was not executed against production.

### Read-only post-install verification — requires installed V2

```bash
plexenv/bin/python artifacts/seerr-exploration/2026-10-28-rollout-preflight/guarded_gate_a.py --verify-v2 \
  > artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-a-verification.json
plexenv/bin/python scripts/sync_seerr_discovery.py --summary --media-type movie --media-type tv --json \
  > artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-a-summary.json
systemctl show plexintel-backend.service --property=MainPID --property=ActiveState --property=NRestarts
```

Require exact V2 catalog/runtime acceptance, expected owner-only ACLs with no PUBLIC grants, preserved sequence state and **0 runs / 0 titles / 0 observations** for this reviewed installation. Confirm unrelated metadata unchanged and backend remains active without a rollout-triggered restart. Discovery must still load disabled. Preserve logs. **STOP. No sync, preview or enabling follows Gate A.**

## 6. Gate B — seven-day preview, then separately approved persistence

Only after Gate A PASS. Selected inclusive window: **2026-10-26 through 2026-11-01**, exactly seven days. One all-language movie scope and one all-language TV scope share one client and budget. TV uses original `firstAirDate`, not later-season/episode dates.

Set these Bash arrays after reviewing/approving their values; they contain no secrets and do not change persistent configuration:

```bash
cd /home/jmnovak/projects/plexintel
umask 077
set -euo pipefail
set -o noclobber
seerr_rollout_args=(
  --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env
  --media-type movie --media-type tv --language all
  --start 2026-10-26 --end 2026-11-01
  --sort-by primary_release_date.asc --max-pages 500 --json
)
seerr_rollout_env=(
  SEERR_DISCOVERY_WINDOW_DAYS=7
  SEERR_DISCOVERY_MAX_REQUESTS=2500 SEERR_DISCOVERY_RETRIES=0
  SEERR_DISCOVERY_TIMEOUT=10 SEERR_DISCOVERY_INTERVAL=1
  SEERR_DISCOVERY_MAX_RETRY_AFTER=5
  SEERR_DISCOVERY_CACHE_ENABLED=true SEERR_DISCOVERY_METADATA_TTL_HOURS=24
  SEERR_DISCOVERY_FAILED_RETRY_HOURS=1
)
```

**Historical approved B1 command — executed once; result linked above:**

```bash
env "${seerr_rollout_env[@]}" SEERR_DISCOVERY_ENABLED=false \
  plexenv/bin/python scripts/sync_seerr_discovery.py --dry-run "${seerr_rollout_args[@]}" \
  > artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-b-preview.json \
  2> artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-b-preview.log
```

This preview performs discovery **and detail GETs**, using no PostgreSQL connection/cache. It can consume up to **2500 total attempts**, not 2500 per media type. Review JSON before requesting persistence approval: two scopes, exact dates/language/source, all reported pages accounted for, no invalid/duplicate/failed/missing/capped pages, `discovery_complete=true`, enrichment outcomes/TV assessments and errors/warnings understood. New/existing/updated database counts are deliberately unknown in preview.

Page limit 500 is the supported per-query ceiling, **not a one-page smoke test**. The client walks all reported pages up to that ceiling. With two scopes and zero retries, collection can use up to 1000 calls; remaining budget bounds enrichment. Full pagination is required for this gate, but cannot be promised in advance: upstream caps/drift/errors are explicit failures to establish completeness. Do not silently truncate, expand budgets, split into independently multiplied runs, or claim partial retrieval is full coverage. Stop and seek an amended bounded plan if preview does not establish complete retrieval/enrichment. No candidate-count target is imposed.

**STOP after preview review. Separate B2 approval is required.** Preview and persistence are each bounded at 2500 attempts: together their approved maximum is **5000**, not one shared 2500 across processes.

**Approval B2 — corresponding persistence (NOT EXECUTED):**

```bash
env "${seerr_rollout_env[@]}" SEERR_DISCOVERY_ENABLED=true \
  plexenv/bin/python scripts/sync_seerr_discovery.py --execute "${seerr_rollout_args[@]}" \
  > artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-b-execution.json \
  2> artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-b-execution.log
```

Enablement is scoped to this process; the private file remains false. Source/endpoint/schema guards run before recovery/run writes/HTTP. The operation persists the retrieved union with typed identities and per-scope observations, then enriches with one shared budget. Preview and execution are not an atomic upstream snapshot; changed populations are auditable, not forced to match. A valid empty population is successful but cannot demonstrate nonempty persistence for that media type; do not expand the window automatically to force a result.

### Read-only validation after B2

```bash
plexenv/bin/python artifacts/seerr-exploration/2026-10-28-rollout-preflight/guarded_gate_a.py --verify-v2
plexenv/bin/python artifacts/seerr-exploration/2026-10-28-rollout-preflight/inspect_inventory.py \
  > artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-b-inventory.json
plexenv/bin/python scripts/sync_seerr_discovery.py --summary --media-type movie --media-type tv --json
```

`inspect_inventory.py` uses an enforced read-only transaction and the actual schema guard. It reports authenticated target, new canonical movies/TV/dates, canonical fingerprint/timestamp state, observation counts, latest runs/parameters/pagination/errors/warnings, enrichment outcomes, provisional TV reasons/season-date evidence, duplicates/orphans and source-provenance mismatches. Require zero duplicates, zero orphans and zero provenance mismatches. Reconcile unique-title counts versus per-scope observation counts; TV inventory includes provisional/excluded audit evidence, and neither successful retrieval nor `eligible` authorizes acquisition.

Exit **0** means completed retrieval/accounting; **2** means partial/failed collected work; **1** configuration/database failure; **75** concurrent writer. Authentication/rate-limit/budget/page errors stop progression. A partial writer can have safely committed page memberships and detail results; preserve them. Do not delete rows or automatically rerun to make status green. `pagination.unresolved` records summary uncertainty even if detail later resolves it. `eligibility_complete=false` can coexist with complete retrieval/success when TV evidence remains provisional.

## 7. Gate C — idempotency, then wider population

Separate approval; keep identical arrays/window and run within the 24-hour metadata TTL if testing cache reuse. No `--refresh` or `--enrich-due` for this check.

```bash
env "${seerr_rollout_env[@]}" SEERR_DISCOVERY_ENABLED=true \
  plexenv/bin/python scripts/sync_seerr_discovery.py --execute "${seerr_rollout_args[@]}" \
  > artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-c-repeat.json \
  2> artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-c-repeat.log
plexenv/bin/python artifacts/seerr-exploration/2026-10-28-rollout-preflight/inspect_inventory.py \
  > artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-c-inventory.json
```

Compare B/C canonical state: no duplicated `(media_type,tmdb_id)`; existing stable titles keep first-discovery, fingerprint/change timestamp and cached enrichment age; last discovery observation can advance; new run/scope observations append. For unchanged source membership, expect zero new canonical titles and cache reuse of fresh successful metadata. New upstream titles or changed metadata must be explained rather than treated as duplicates or forced to zero. Failed-cooldown deferrals remain explicit. Abandoned `running` executions are recovered only after schema/source validation and exclusive lock; a new run is created rather than silently resuming old membership.

Stop after reviewing this check. For broader initial population, first approve the horizon and total request cost. A reproducible default-horizon proposal anchored October 28 is **2026-10-14 through 2027-01-26** (14 days back/90 forward), in separately reviewed cohorts of at most seven days (**15 cohorts if partitioned from October 14**; agree on boundary alignment before execution). Do not automatically loop over all cohorts. Retain per-cohort complete pagination and budget, plus an explicitly approved cumulative budget; preview+write+repeat budgets are additive.

Example next cohort, **only after separate coverage approval**, reusing the same limits and private credentials:

```bash
seerr_extension_args=(
  --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env
  --media-type movie --media-type tv --language all
  --start 2026-11-02 --end 2026-11-08
  --sort-by primary_release_date.asc --max-pages 500 --json
)
env "${seerr_rollout_env[@]}" SEERR_DISCOVERY_ENABLED=false \
  plexenv/bin/python scripts/sync_seerr_discovery.py --dry-run "${seerr_extension_args[@]}" \
  > artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-c-extension-preview.json
```

**STOP. Review the extension preview and obtain separate persistence approval.** Only then run:

```bash
env "${seerr_rollout_env[@]}" SEERR_DISCOVERY_ENABLED=true \
  plexenv/bin/python scripts/sync_seerr_discovery.py --execute "${seerr_extension_args[@]}" \
  > artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-c-extension-execution.json
```

No broader cohort was queried or populated here. Broader windows select discovery coverage, not engagement/acquisition eligibility. Historical dates cannot be treated as metadata known at historical discovery time.

## 8. Gate D — future scheduling considerations

No schedule is registered or enabled. Scheduling needs separate operational approval after A–C: selected media/language/window/horizon, UTC calendar anchor, total request/page limits, source identity, TTL/cooldown/refresh policy, history growth/retention, alerts and log protection, recovery ownership and a stop procedure. Use the direct host Python CLI under the existing owner, not Docker or a new authentication system. Do not duplicate cron/systemd jobs or overlap the normal model pipeline; the discovery advisory lock prevents two discovery writers, not all competing application activity.

A future timer should honor the disabled private configuration rather than permanently overriding it true. Acquisition, Sonarr/Radarr actions, model training/scoring/recommendations and recurring `--enrich-due` are not implied by discovery scheduling. No unit, timer, cron entry, backend startup hook or pipeline stage is created by this runbook.

## 9. Stop, rollback and recovery procedures

- **Before A:** any target/config/hash/catalog/count/activity/recovery mismatch is STOP. Do not relabel provenance, create missing objects, change roles, relax constraints/locks or rerun 001 to bypass the guard.
- **A before commit:** transaction failure rolls back the upgrade. Preserve output and inspect V1 read-only; do not retry a lock timeout without a new quiet-window decision.
- **A after commit/uncertain commit:** leave discovery disabled. Inspect catalog state using the read-only commands; retain V2 if installed. Do not use the V1-only `rollback.sql` or blindly rerun 002.
- **B/C:** stop launching writers. The persistent file is already disabled; process-scoped enablement does not survive command exit. Interrupt an unhealthy manual command if needed, wait for its connection to close, then inspect committed rows/run state read-only. An interrupt can leave `running`; preserve it for the next separately authorized recovery. No write-based cleanup or automatic retry.
- **D:** if a future schedule is approved, disabling/stopping that specific job requires its own operational procedure/authorization. No scheduling stop command is needed now because no discovery schedule exists.

Nondestructive rollback is retaining V2/inventory with discovery inactive. V1 discovery code is incompatible with V2. A structural downgrade after TV records exist would require separately reviewed exports and history/provenance handling; it must not discard TV or rewrite run history automatically. A whole-database restore from the validated archive would also lose unrelated application writes after its recovery point and remove the later V1/V2 installation. Restore needs separate authorization and isolated validation; no production restore/drop command is part of these gates.

## 10. Operator decisions, risks and next action

Before Gate A, approve **002 only**, the quiet window and current backup recovery point (or a separately refreshed backup). Maintain the accepted `jmnovak` superuser exception; least-privilege separation remains deferred hardening. No unrelated role/config/service change is required.

Before B1/B2, approve the exact seven-day movie/TV/all-language scopes, full pagination, 2500-attempt per-process budgets, zero retries and the conservative TV contract: matching original/Season 1 dates for eligibility; incomplete/conflicting evidence retained provisionally; explicit specials/season-0-only heuristic retained. Decide how an empty media-type population or partial result will be reviewed. Preview approval is not writer approval.

Remaining limitations: live discovery/detail response behavior is still untested; source dates/special classifications can be incomplete; exact date agreement can increase provisional coverage; aggregate eligibility across scopes is not acquisition authorization; pagination is not an atomic upstream snapshot; stored observations grow with repeated runs; existing logical recovery does not cover full host/PITR recovery. No forced candidate count, content score or acquisition action is introduced.

The code/test evidence remains **271 passing tests**, captured **778 movies → 778 cached**, and synthetic **six titles → six cached**, with zero HTTP in those replays. This preflight added only status/auth GET validation and canonical fixture verification. Existing implementation/configuration and protected model/data inputs remain unchanged.

**Gate A, B1 and the separately authorized one-day/page-1 B2 validation are complete. Stop here. No further execution is authorized.**
