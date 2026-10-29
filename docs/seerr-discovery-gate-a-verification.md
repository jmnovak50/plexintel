# Gate A — production migration 002 and verification

**PASS — migration 002 committed and strict post-install verification passed.** Executed under the operator's explicit Gate A-only authorization on **October 28, 2026, approximately 20:50–20:51 CDT**. No synchronization, configuration activation or Gate B operation occurred.

## Migration 001 provenance and prerequisites

Before execution, the original installation receipt confirmed migration 001's **successful commit at 18:42:13 CDT**, with SHA-256 `fb54db94d34f7f00193f76164425adbea8f531c4cf5468e8c56baa9f342cb69c`. That receipt preserves its initial post-commit verification-parser failure. The separately authorized read-only verifier at 18:52 subsequently recorded **PASS**, without schema repair or migration rerun.

The fresh `--check-v1` check matched production's complete V1 catalog to the canonical 001 fixture, including 64 columns, 19 core constraints, 11 indexes, owner/ACLs and identity-sequence dependency. Runs, movies and observations were **0/0/0**; sequence state was **1 / is_called=false**. The verified recovery archive checksum/PASS evidence, disabled configuration, unchanged source binding and absence of conflicting discovery activity also passed. **001 was not executed again.**

Provenance records:

- `/home/jmnovak/.local/state/plexintel/preflight-backups/schema-install-20261028T184212-0500-dd13e1.json`
- `/home/jmnovak/.local/state/plexintel/preflight-backups/schema-verification-20261028T185220-0500-d54568.json`
- `artifacts/seerr-exploration/2026-10-28-gate-a/migration001-provenance.json`

## Authorized execution and outcome

Authenticated target: **192.168.1.9:5432 / plexintel / jmnovak / PostgreSQL 18.6**, online and not in recovery. The effective connection matched the active direct-Python backend. Credentials were not printed or changed.

Only `api/db/migrations/optional/seerr_discovery/002_unified_titles.sql` was applied, once, using the documented `guarded_gate_a.py --apply-reviewed-v2` command. Reviewed SHA-256:

```text
838902e5ef6b9d2dcccf257dbdcc2543f0673c90ebdc0eb3cbb979980d07a1c2
```

The helper rechecked prerequisites, took advisory transaction lock `(184725,30)` and exclusive locks on the three discovery tables with a five-second lock timeout and 120-second statement timeout. Exact V2 catalog/runtime and unrelated-application metadata checks passed **inside the transaction before commit**, then again after commit. Receipt flags: `production_migration_executed=true`, `commit_attempted=true`, `commit_confirmed=true`, `status=PASS`. No rollback, retry, schema repair or second migration execution was needed.

## Strict verification results

| Check | Result |
| --- | --- |
| Canonical schema | V2 present; old movie table renamed to `seerr_discovered_titles`; no mixed V1/V2 state |
| Columns/types/defaults/identity | **68 columns**, exact canonical definitions; real runtime schema guard PASS |
| Constraints | **24 core constraints**, plus **38 NOT NULL constraints**; expected definitions and validation/deferral flags match |
| Primary keys | Titles `(media_type,tmdb_id)`; runs `run_id`; observations `observation_id` |
| Foreign keys | Titles' `first_discovery_run_id` → runs; observations' `run_id` → runs; observations' `(media_type,tmdb_id)` → typed titles |
| Observation uniqueness | `(run_id,media_type,tmdb_id,scope_key)` |
| Indexes | **11**, exact definitions and valid/ready flags; supporting composite indexes verified |
| Identity sequence | Existing observation sequence/internal dependency preserved; **last_value=1, is_called=false** |
| Ownership/ACLs | Canonical owner/ACL catalog matches; owner `jmnovak`, no PUBLIC grants |
| Effective application permissions | **11/11 allowed**: SELECT/INSERT/UPDATE on each discovery table, plus USAGE/SELECT on observation sequence |
| Production inventory | **0 runs / 0 titles / 0 observations**; summary reports movies 0, TV 0, refresh due 0, latest run null |
| Unrelated application schema/roles/ACLs | Immediate pre-DDL, in-transaction and post-commit comparisons unchanged |
| Existing application data check | Row counts for **40 existing application tables unchanged** before/after |
| Backend | Active; PID **1633**, start time and restart count unchanged; local health HTTP **200**, `ok=true` |
| Scheduling | User/root cron and system/user timer-definition hashes unchanged |
| Configuration | Actual loader confirms discovery **disabled**, permanent source identity unchanged |

The existing `jmnovak` **superuser** privileges remain the accepted temporary security exception. No grants, roles, passwords or database connection settings changed; this is not a least-privileged connection. Some unaffected constraint names retain their legacy movie prefix by design; their table references and key definitions are correct.

## Evidence and boundaries

Installation and separate post-install verification receipts:

- `artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-a-install.json`
- `artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-a-verification.json`
- `artifacts/seerr-exploration/2026-10-28-rollout-preflight/gate-a-summary.json`

Additional owner-only evidence is under `artifacts/seerr-exploration/2026-10-28-gate-a/`: `before.json`, `after.json`, provenance, boundary checks and the read-only observer source. These contain sanitized target/catalog/count/permission/service metadata, not credentials or raw playback data.

**Anomalies: none during migration 002 or its verification.** The historical 001 verifier-parser issue remains recorded and resolved; it was not repeated or hidden.

Application implementation, model/scoring/training inputs, migrations and validated backup remain unchanged on disk. The only production database mutation was the approved 002 schema transaction. No Seerr HTTP call, discovery/dry-run, acquisition, model job, configuration activation, schedule change, restart, redeployment, commit or push occurred. Local health GETs and post-install CLI `--summary` were read-only.

**Gate A is complete. Do not rerun 001, 002 or the V1-only rollback. Discovery remains disabled and Gate B has not begun.** Any later preview or synchronization requires separate operator authorization.
