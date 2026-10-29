# Phase 3 — Production discovery provisioning and readiness

**Current production status — October 28, 2026, 20:51 CDT:** Gate A completed: migration **002 committed**, strict V2 verification **PASS**, inventory empty, discovery **disabled**. See [Gate A verification](seerr-discovery-gate-a-verification.md). Earlier V1/preflight statements below are historical; do not rerun 001/002 or proceed to Gate B without separate authorization.

## Unified enhancement status — subsequent code-only work

**The historical PASS/installed findings below apply to movie-only V1 (`001_initial.sql`). Unified V2 (`002_unified_titles.sql`) is NOT production-installed or production-verified.** The later unified enhancement used synthetic/captured responses and a disposable local PostgreSQL cluster only; it did not connect to production, rerun a migration, populate production discovery tables, validate live TV behavior, alter private configuration or touch the validated recovery archive.

The current checkout's discovery writer **and summary** require V2 and fail closed against V1. Consequently the historical first-sync commands/recommendation below must not be used with this checkout before separately reviewing and authorizing the forward upgrade and verifying it. Preserve disabled discovery. No authorization for either migration or synchronization follows from code-review readiness. Transient production counts, backend status and recovery age below are historical observations, not a new live audit. The accepted temporary `jmnovak` superuser exception is unchanged; this work neither modifies privileges nor claims least privilege.

See [unified implementation and evidence](seerr-unified-discovery.md) and [rollback implications](seerr-unified-discovery-rollback.md). Keep the prior installation, verification-failure recovery and backup evidence intact.

## A. Executive summary

**Migration: SUCCESS / COMMITTED. Post-migration verification recovery: PASS. GO for separately authorizing the first bounded manual sync.** The original migration committed October 28 at **18:42:13 CDT**; its initial verification stop is preserved in the audit history. A separately authorized read-only verifier corrected the identity parser and completed all schema, privilege, empty-inventory and isolation checks at **18:52–18:54 CDT**. No schema/data repair, migration rerun or rollback was needed. Discovery remains **disabled**, and no first-sync authorization is implied or exercised.

This update supersedes the earlier preflight requirement to provision a separate writer. **Continue using the existing production `DATABASE_URL`, database `plexintel`, and PostgreSQL user `jmnovak`.** No role, credential, privilege, backend database configuration, authentication abstraction or production application code was changed. Least-privilege separation is deferred to a future security-hardening phase.

Earlier provisioning checks began October 28 at approximately 18:00 CDT; the preceding preflight was at 17:46–17:50 CDT. The current separately authorized recovery operation ran that evening, with the backup at **18:18–18:19 CDT** and isolated restore at **18:19 CDT**. Production verification/count connections were read-only; `pg_dump` used an exported read-only snapshot. Those recovery/provisioning stages did not install schema. The subsequently authorized schema transaction is recorded below; no production application-data write, Seerr HTTP, discovery/dry-run, model job, restart, redeployment or schedule change was performed.

The recovery task created the authorized private archive/evidence and a temporary restore environment, now removed. The schema task added private installation evidence; the current verification-recovery task added private read-only verification evidence. The only repository change is this report. The previously approved private configuration remains unchanged. Source ID `plexintel-seerr-primary` was approved before configuration creation. The operator subsequently explicitly authorized schema installation, which is now committed. First discovery synchronization remains separately unauthorized.

Evidence labels: **P** = direct production/configuration observation; **C** = inspected implementation; **H** = historical isolated tests; **U** = unverified.

## B. Updated readiness matrix

| Gate | Status | Evidence | Required action |
| --- | --- | --- | --- |
| Seerr source identity | **PASS** | P: approved permanent `plexintel-seerr-primary`; normalized endpoint/source-key binding remains unchanged. | Preserve identity; no API authentication claim is made. |
| Private configuration | **PASS / DISABLED** | P: owner 1000:1000, mode `0600`, real loader valid, legacy endpoint/key reused and `enabled=false`; no Seerr HTTP. | Keep disabled by default; synchronization needs separate approval. |
| Production database target | **PASS** | P: effective URL matches the running backend; `192.168.1.9:5432`, `plexintel`, `jmnovak`, PostgreSQL 18.6. | Retain the same URL/role; immediately reconfirm both configured and authenticated target before any approved migration. |
| Optional discovery schema | **PASS / INSTALLED AND VERIFIED** | P: all 64 columns, 19 core constraints, 36 NOT NULL records, 11 indexes, identity sequence/dependency and owner/ACL metadata match canonical SQL. Initial verifier failure remains preserved; corrected read-only verification passed. | Do not rerun migration or rollback. No schema changes are needed. |
| Writer identity/security | **ACCEPTED TEMPORARY RISK** | P: `jmnovak` is a superuser with role/database administration, replication and RLS-bypass privileges; database/schema/lock-function access is effective. Operator explicitly accepts its use for Phase 3. | Existing role/grant snapshots match; new-object ACLs are owner-only with no PUBLIC access. Defer least-privilege separation to future hardening; do not describe this connection as restricted. |
| Inventory provenance / empty counts | **PASS / EMPTY** | P: runs **0**, movies **0**, observations **0**; no running/incomplete runs, source bindings or enrichment provenance. Sequence remains unused. | Preserve emptiness until separately authorized first sync; no adoption needed. |
| Bounded synchronization limits | **PREPARED / NOT AUTHORIZED** | C: existing one-day/one-page/all-language command below supports 25 total attempts, zero retries, 10-second request timeout and one-second spacing. | Separately approve the first sync and its possible partial/empty outcome. Do not inherit the broad defaults or run now. |
| PostgreSQL recovery readiness | **PASS — LOGICAL RESTORE VALIDATED** | P: new 174,148,995-byte custom archive; checksum verified; catalog/full-read/restore exit 0; all 40 table counts match the shared snapshot; catalog/dependency review completed; isolated cluster removed. | Preserve private archive/evidence and its recovery dependencies. The older image and PITR remain outside this PASS. |
| Resource capacity | **PASS FOR CAPACITY; OPERATIONAL LIMITS REMAIN** | P: database approximately 1.01 GiB; prior filesystem sample approximately 789.5 GiB free; autovacuum on. H: fixture growth is a reference, not production forecasting. | Pre-DDL available space was 847,515,631,616 bytes. Recheck capacity/activity before any future live sync; logical recovery remains PASS. |
| Production isolation | **PASS / DISCOVERY DISABLED** | P/C: current loader confirms disabled/private configuration; backend active with unchanged PID/start/restarts and loopback health HTTP 200; 11 existing-metadata groups match; normal pipeline settings unchanged; no discovery timers/cron/process/hooks observed. | Keep disabled until a separately approved bounded invocation; no acquisition/model/scheduling authorization. |

The accepted superuser exception is **not** a blocker to be removed by creating a role. Recovery readiness is resolved for the validated logical archive. The authorized schema transaction is committed and corrected read-only verification is now complete. First sync is ready for separate authorization, but must not advance automatically. Database work stopped under the original failure policy and resumed only under the later verification-only authorization.

## C. Verified configuration and approved security exception

### Private source configuration — completed

Created:

`/home/jmnovak/.config/plexintel/seerr-discovery.env`

The new regular nonsymlink file has owner `jmnovak` (UID/GID **1000:1000**) and permissions **0600**. Its nonsecret settings include:

```dotenv
SEERR_DISCOVERY_ENABLED=false
SEERR_DISCOVERY_SOURCE_ID=plexintel-seerr-primary
SEERR_DISCOVERY_LANGUAGES=all
```

The existing normalized URL and API key were copied into supported `SEERR_URL` / `SEERR_API_KEY` settings; neither value is reproduced here. Sanitized endpoint: **`https://<private-host>`**. The original `.seer_creds` remains unchanged at mode **0664**; it was not chmodded, weakened, replaced or used directly as a discovery private file.

Both credential equality and endpoint equality were checked internally. The actual `load_seerr_config()` contract was used with HTTP explicitly forbidden during validation; it returned the approved ID and `enabled=false`. The file was created without overwriting an existing configuration. No client, request, discovery run or enrichment was initiated. File-backed identity is persistent, but no database binding exists until the first separately approved run.

Expected endpoint source key:

```text
4547479bd1da2cd5fab4ff1af5e07bb9617e2dd37900447eb261491ec5330139
```

The existing source contract is unchanged: the normalized endpoint hash plus `runs.parameters.source_id` bind the inventory. URL suffix/trailing-slash normalization preserves the endpoint; credentials do not form the binding. Writer validation runs under the existing advisory lock before interrupted-run recovery or durable mutations. Mismatch/ambiguous legacy provenance still fails closed. Do not reuse this ID for a replacement installation behind the same URL, and do not edit history to bypass validation.

### Database target and accepted temporary exception

The active deployment remains `plexintel-backend.service`, running directly on the host as `jmnovak`, from `/home/jmnovak/projects/plexintel`, using `plexenv/bin/uvicorn api.main:app` and the existing `.env`. Main PID 1633 and service start time 2026-10-27 23:45:34 CDT matched the earlier preflight. No Docker orchestration or backend restart was involved.

Read-only reconfirmation established:

- Configured effective `DATABASE_URL` matches the running backend's URL; credentials were compared internally, never printed.
- Configured/authenticated target: **192.168.1.9:5432 / plexintel / jmnovak**; PostgreSQL **18.6**, not in recovery.
- Existing `.env` remains owner-only **0600**. `DATABASE_URL` takes precedence over `DB_*`; the fallback `DB_HOST=127.0.0.1` does not override it.
- `jmnovak`: `rolsuper=true`, `rolcreaterole=true`, `rolcreatedb=true`, `rolreplication=true`, `rolbypassrls=true`. CONNECT, public-schema USAGE and the advisory lock/unlock functions are available.

**Accepted risk record:** The operator explicitly authorizes retaining this same superuser identity and unchanged `DATABASE_URL` for Phase 3 discovery. It can access unrelated production objects and bypass normal object/RLS restrictions. This connection is **not least-privileged**. No discovery-specific role, password, grant, revoke on existing application objects, connection abstraction or backend configuration change is proposed. Least-privilege separation is **deferred hardening**, to be considered separately after Phase 3; this exception is temporary and scoped to the stated discovery rollout, not a general expansion of operating authority.

The Seerr private-file loader does not configure the database connection. Do not place a replacement database URL there or redirect the writer to a new role. A future operator launch environment can override `.env`, so verify the unchanged effective URL each time.

### Current inventory and isolation

Immediately before installation there were no discovery relations or legacy inventory to adopt. The canonical DDL is committed, and the later read-only verification observed **0 runs, 0 movies and 0 observations**, with no source bindings, running/incomplete records or canonical enrichment. The identity sequence remains unused. No insert, enrichment or synchronization was issued.

No discovery application hooks, background worker, acquisition path or model pipeline stage was added. Host timer/cron checks found no Seerr/PlexIntel discovery activation. The unrelated `wsdd.service` description includes “Discovery”; it is not a PlexIntel discovery worker. The existing pipeline remains enabled for **07:03 America/Chicago**, daily by the existing defaults; latest recorded run **318** succeeded on October 28, 07:03–07:40 CDT, with no active pipeline at inspection. Choose a quiet window later; discovery does not acquire the model pipeline's file lock.

Historical implementation evidence remains **145 tests passed, zero skips**, plus a captured-data replay with zero HTTP. This provisioning did not rerun tests or treat fixture success as live production validation.

## D. Optional schema installation — committed; verified in a separate read-only operation

### Reviewed migration and expected effects

Only this existing file is proposed:

`api/db/migrations/optional/seerr_discovery/001_initial.sql`

Reviewed SHA-256:

```text
fb54db94d34f7f00193f76164425adbea8f531c4cf5468e8c56baa9f342cb69c
```

Expected objects:

| Object | Canonical definition |
| --- | --- |
| `public.seerr_discovery_runs` | 13 columns; UUID PK; source key/JSONB parameters; timestamptz execution times; status/operation/completion checks |
| `public.seerr_discovered_movies` | 33 columns; positive bigint TMDB PK; structured metadata/provenance; nullable JSONB release events; first-run FK; runtime/status/date/array checks |
| `public.seerr_discovery_observations` | 18 columns; bigint identity PK; run/movie FKs; unique `(run_id,tmdb_id,scope_key)`; kind/outcome checks |
| `public.seerr_discovery_observations_observation_id_seq` | Identity sequence owned by the observation ID column |
| Indexes | Seven explicit secondary indexes plus three PK indexes and the observation uniqueness index: eleven table indexes total |
| Constraints | Five on runs, eight on movies and six on observations: nineteen PK/FK/unique/check constraints total, excluding column NOT NULL metadata |
| Ownership/ACL | New objects owned by executing `jmnovak`; canonical SQL revokes PUBLIC access on these new tables/sequence. No applicable creator default ACL overrides were found. Superuser authority remains unchanged. |

The migration sets a transaction-local five-second lock timeout and controlled search path, and takes advisory transaction lock `(184725,30)`. It does not itself issue BEGIN/COMMIT: the caller must wrap it in one transaction. The startup runner only searches top-level `migrations/*.sql`, so this nested migration is not applied on startup; the CLI never creates schema. No migration/version ledger exists for this optional component; catalog state is authoritative. `IF NOT EXISTS` does not repair unexpected schema drift.

### Historical guarded installation pattern — DO NOT RERUN

**Explicit installation approval was received and the canonical migration was executed once. The installation must not be rerun.** The preserved operation used the following guarded pattern and additional read-only pre/post checks. It uses the existing `.env`, `DATABASE_URL` and `connect_db()` utility, without putting secrets in process arguments or introducing a connection abstraction. It refuses a changed file hash, target, enabled discovery configuration, or pre-existing discovery relations.

Historical command pattern from `/home/jmnovak/projects/plexintel` (retained for audit, not a next-step command):

```bash
plexenv/bin/python -B - <<'PY'
from pathlib import Path
import hashlib
from dotenv import load_dotenv
from psycopg2.extensions import parse_dsn
from api.db.connection import connect_db, get_database_url
from api.services.seerr_client import load_seerr_config

root = Path.cwd()
load_dotenv(root / '.env', override=False)
cfg = load_seerr_config()
if cfg.enabled or cfg.source_id != 'plexintel-seerr-primary' or cfg.source_key != '4547479bd1da2cd5fab4ff1af5e07bb9617e2dd37900447eb261491ec5330139':
    raise SystemExit('Refusing unexpected or enabled discovery configuration')
params = parse_dsn(get_database_url())
if (params.get('host'), params.get('port', '5432'), params.get('dbname'), params.get('user')) != ('192.168.1.9', '5432', 'plexintel', 'jmnovak'):
    raise SystemExit('Refusing unexpected configured database target')
migration = (root / 'api/db/migrations/optional/seerr_discovery/001_initial.sql').read_bytes()
if hashlib.sha256(migration).hexdigest() != 'fb54db94d34f7f00193f76164425adbea8f531c4cf5468e8c56baa9f342cb69c':
    raise SystemExit('Refusing an unreviewed migration')
conn = connect_db()
try:
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port(),pg_is_in_recovery()")
            if cur.fetchone() != ('plexintel', 'jmnovak', '192.168.1.9', 5432, False):
                raise SystemExit('Refusing unexpected authenticated database target')
            cur.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relname LIKE 'seerr_%'")
            if cur.fetchone()[0] != 0:
                raise SystemExit('Discovery objects already exist; inspect rather than adopt or repair')
            cur.execute(migration.decode('utf-8'))
    print('Optional discovery schema transaction committed; perform read-only catalog verification next.')
finally:
    conn.close()
PY
```

The actual one-time operation ran as `plexenv/bin/python -B /tmp/plexintel_install_discovery_schema.py`; the temporary file has been removed after its exact source was preserved privately. It used `load_dotenv`, `get_database_url`, `connect_db`, and `with conn` to execute only the unchanged migration in one transaction. It did not synchronize or issue INSERT statements. Existing objects now cause the installation guard to refuse a rerun; do not bypass it.

### Initial installation and verification stop — preserved audit history

Mandatory guards passed immediately before DDL: configured and authenticated **192.168.1.9:5432 / plexintel / jmnovak / PostgreSQL 18.6**, online/not in recovery; reviewed migration hash matched; recovery archive checksum and final PASS assessment matched; no existing discovery relations; approved private source identity and `0600`/disabled configuration; active backend with matching unchanged URL; ample space; no active pipeline, conflicting database activity, pending/advisory lock conflict, enabled DDL event trigger or unexpected creator default ACL.

| Execution evidence | Observed value |
| --- | --- |
| Migration SHA-256 | `fb54db94d34f7f00193f76164425adbea8f531c4cf5468e8c56baa9f342cb69c` |
| DDL started | 2026-10-28 **18:42:13.111388 CDT** |
| Commit completed | 2026-10-28 **18:42:13.139342 CDT** |
| Transaction ID | `40865992` |
| Transaction-local lock timeout | `5s`, preserved |
| Transaction-local search path | `pg_catalog, public, pg_temp`, preserved |
| Migration result | **SUCCESS — COMMITTED**, not rolled back |
| Initial post-install result | **INCOMPLETE — stopped at observations-column comparison; subsequently resolved by separately authorized read-only verification below** |
| Recovery archive SHA-256 | `8754923a28ed13c140cb269e59b2389786e4d653e6cfbfcf14bb46fb06d52f1a`, revalidated before DDL |

Completed read-only checks before the stop:

- Existing application-schema, role, membership, extension and pipeline-setting snapshots matched across **11 snapshot groups**, before versus after commit.
- All **13** `seerr_discovery_runs` columns and all **33** `seerr_discovered_movies` columns matched canonical names, types, defaults, nullability and identity metadata.
- The observations table lookup succeeded, but its column comparison failed before the remaining checks.

**Verifier defect identified offline:** the temporary parser treated the `DEFAULT` word in `GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY` as a column-default clause. It generated the invalid expected value `AS IDENTITY PRIMARY KEY` for `observation_id.default`. The `BY DEFAULT` phrase belongs to identity generation and must be validated separately from the ordinary column-default expression. This was my verification-helper bug. It does **not** establish a production schema mismatch, and it does not justify marking the uncompleted checks PASS.

At the original post-commit failure, further database work stopped as required. Under that installation authorization, no corrected verifier, repair, rerun, rollback or discovery call followed. At that checkpoint the **18 observation columns**, **19 core constraints**, **11 indexes**, sequence/ACL metadata and **0/0/0 counts** were still unverified. The table below preserves that initial state; **the later verification-only task has now completed these checks successfully**, as recorded in the next subsection. PostgreSQL 18 NOT NULL records are counted separately.

| Initial-stop inventory table | Count known at original stop | Required count |
| --- | --- | ---: |
| `seerr_discovery_runs` | **UNVERIFIED — count stage not reached** | 0 |
| `seerr_discovered_movies` | **UNVERIFIED — count stage not reached** | 0 |
| `seerr_discovery_observations` | **UNVERIFIED — count stage not reached** | 0 |

Preserved private evidence under `/home/jmnovak/.local/state/plexintel/preflight-backups/` uses basename `schema-install-20261028T184212-0500-dd13e1`:

- `.json`: guards, target, transaction settings, commit timestamp and stopped status.
- `.failure.json`, `.review.json`: original failure and offline diagnosis/scope of incomplete checks.
- `.existing-schema-before.json`, `.existing-schema-after.json`: matching existing-object snapshots.
- `.operation.py`: exact one-time helper, retained privately for review, **not for rerunning**.

That follow-up was explicitly authorized as verification-only and has now passed. Only the temporary comparison logic was corrected; production objects and canonical SQL were not changed. The original failure evidence remains unchanged.

### Verification recovery — completed without database writes

On **October 28, 2026, 18:52:20–18:52:21 CDT**, the operator-authorized corrected verifier completed all outstanding checks. **Result: PASS.** This was a new read-only verification operation; the migration and rollback were not executed. The original stop/failure records remain unchanged.

The authenticated connection was **192.168.1.9:5432 / plexintel / jmnovak / PostgreSQL 18.6**, online and not in recovery. The verifier enforced a REPEATABLE READ, **read-only** transaction, **15-second statement timeout** and **2-second lock timeout**, then rolled back/closed the reporting transaction. The unchanged canonical SQL hash remained `fb54db94d34f7f00193f76164425adbea8f531c4cf5468e8c56baa9f342cb69c`.

#### Corrected identity methodology

The temporary parser now recognizes identity generation before searching for an ordinary DEFAULT clause. It treats `GENERATED BY DEFAULT AS IDENTITY` as identity metadata, not as `DEFAULT AS IDENTITY PRIMARY KEY`. Verification independently compares:

- `information_schema.columns.is_identity='YES'` and `identity_generation='BY DEFAULT'` for `observation_id`, with ordinary `column_default` **SQL NULL**.
- PostgreSQL `pg_attribute.attidentity='d'`, bigint type, NOT NULL, and the absence of a computed generation expression.
- `pg_get_serial_sequence()` resolving the expected identity sequence, sequence ownership by `jmnovak`, and an **internal dependency** (`deptype='i'`) on `seerr_discovery_observations.observation_id`.
- Sequence definition: bigint, start/minimum **1**, increment **1**, maximum **9223372036854775807**, cache **1**, no cycle.
- Read-only initial sequence state: **`last_value=1`, `is_called=false`**. No `nextval`, INSERT or generation write probe was used.

All other columns report `is_identity='NO'`; all 64 report no computed generation expression. A null ordinary default was never used as evidence that identity generation or its sequence was missing.

#### Complete schema and privilege results

| Verification | Observed result |
| --- | --- |
| Public tables | All three present; column counts **13 / 33 / 18**, total **64** |
| Column definitions | Names/order, PostgreSQL formatted types, defaults, nullability and identity attributes match canonical SQL |
| Core constraints | **19**: three PKs, three FKs, one composite unique constraint and twelve CHECKs; definitions and applicable validation/deferral/FK-action metadata match |
| PostgreSQL 18 NOT NULL records | **36**, separately accounted for alongside matching column nullability; not counted as additional PK/FK/unique/CHECK definitions |
| Indexes | **11**, full SQL definitions plus method, key order, uniqueness/PK flags, validity/readiness and sort/null ordering match; no partial/expression/INCLUDE additions |
| Identity sequence | Present, correctly linked/owned, BY DEFAULT generation, initial unused state verified |
| Relation ownership | All **15** discovery `pg_class` objects—three tables, one sequence and eleven indexes—owned by `jmnovak`, in `public` |
| Implicit row types | Exactly the expected three composite row types and their three array types, with expected ownership |
| Required access | SELECT/INSERT/UPDATE verified individually for each table; USAGE/SELECT verified individually on the sequence |
| New-object ACLs | Owner access only; **zero PUBLIC privileges**, no unexpected grantees |
| Unexpected discovery objects | None; expected names/classes only, no unexpected discovery routines or user-defined triggers |
| Existing application metadata | **All 11 pre-install snapshot groups match** current observations, including existing tables, constraints/indexes, functions/views, schemas, role attributes/memberships, relation grants, extensions and pipeline settings |

CHECK expressions were compared through PostgreSQL's parsed/deparsed projection representation using **EXPLAIN without ANALYZE**; it did not execute the projection or scan rows. PK/FK/unique metadata and full index SQL were compared to expectations derived from the unchanged canonical migration. No object was changed to make comparisons pass.

`jmnovak` remains the operator-accepted superuser exception; effective privileges do not imply a least-privileged connection. Existing roles and grants remain unchanged. No role, credential or grant statements were executed.

#### Empty inventory and provenance

| Table | Observed rows |
| --- | ---: |
| `public.seerr_discovery_runs` | **0** |
| `public.seerr_discovered_movies` | **0** |
| `public.seerr_discovery_observations` | **0** |

There are **zero running/incomplete run records, zero recorded source bindings and zero canonical enrichment records**. No legacy adoption or source-binding bypass is required. The approved identity exists only in the private configuration until the first separately authorized synchronization records a binding.

#### Live isolation and recovery-point checks

The backend remained **active**, PID **1633**, with unchanged start time and restart count **2**; its database URL still matches the unchanged production configuration. The inspected constant-response endpoint `GET http://127.0.0.1:8489/api/library/health` returned **HTTP 200**, `ok=true`, at **18:53:57 CDT**. That route calls no database/job helper; this was a PlexIntel loopback health request, **not a Seerr request**.

The latest model/pipeline run remains **318 / success**. No active pipeline or discovery/training/scoring process was observed. Existing schedule settings still enable the normal daily **07:03 America/Chicago** pipeline. System/user timer and user/root cron checks show no Seerr discovery scheduling, and application-source inspection found no discovery startup/background hook. No job, acquisition, recommendation action, restart or redeployment was initiated by this verification.

The real discovery loader still validates **`plexintel-seerr-primary`**, unchanged endpoint/source key, file owner 1000:1000/mode **0600**, and **`enabled=false`**. Seerr networking/authentication remains deliberately untested. The validated recovery archive is still readable and matches SHA-256 `8754923a28ed13c140cb269e59b2389786e4d653e6cfbfcf14bb46fb06d52f1a`; its prior isolated-restore PASS evidence remains available. No backup or restore was repeated.

#### Preserved evidence

New private evidence under `/home/jmnovak/.local/state/plexintel/preflight-backups/` uses basename **`schema-verification-20261028T185220-0500-d54568`**:

- `.json`: final PASS, target/timeouts, schema/count/privilege results, schedules, pipeline/backend observations and recovery-archive recheck.
- `.installed-catalog.json`: complete installed column, constraint, index, sequence/dependency, object-owner and ACL definitions.
- `.identity-and-column-info.json`, `.extra-catalog-evidence.json`: identity-generation attributes, sequence state, types and empty provenance.
- `.existing-application-schema.json`: comparison against the original pre-installation snapshot.
- `.backend-health.json`: inspected loopback health response.
- `.operation.py`: corrected verification-only helper; its temporary `/tmp` copy was removed.

The original `schema-install-20261028T184212-0500-dd13e1.*` failure/stop evidence is **unchanged**. Its post-commit failure flag remains part of the audit history; this separately authorized verification resolves readiness without rewriting that first attempt as successful. No installation, rollback, production record change or write probe occurred during recovery verification.

**Decision: GO for separately authorizing the first bounded manual sync.** All previously incomplete schema/provenance/isolation gates now pass. This is a readiness recommendation, **not synchronization authorization**. Discovery remains disabled, and the reviewed one-day/one-page/25-attempt plan still needs explicit approval. Existing limitations remain: accepted superuser authority, no live Seerr authentication test yet, non-atomic discovery pagination, and database-logical recovery rather than complete host/application or PITR recovery.

### Read-only catalog query reference — checks completed by the corrected verifier

The corrected verifier implemented the equivalent catalog/count checks below, plus independent identity-generation metadata, full definition comparisons and live isolation checks. This is a read-only reference, not a request to rerun installation or start synchronization:

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SELECT current_database(),current_user,inet_server_addr(),inet_server_port();

SELECT table_name,column_name,data_type,udt_name,is_nullable,column_default,is_identity
FROM information_schema.columns WHERE table_schema='public' AND table_name IN
 ('seerr_discovery_runs','seerr_discovered_movies','seerr_discovery_observations')
ORDER BY table_name,ordinal_position;

SELECT c.relname,k.conname,k.contype,pg_get_constraintdef(k.oid) AS definition
FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN
 ('seerr_discovery_runs','seerr_discovered_movies','seerr_discovery_observations')
ORDER BY c.relname,k.conname;
SELECT tablename,indexname,indexdef FROM pg_indexes
WHERE schemaname='public' AND tablename IN
 ('seerr_discovery_runs','seerr_discovered_movies','seerr_discovery_observations')
ORDER BY tablename,indexname;

SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner) AS owner,c.relacl
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname LIKE 'seerr_%' ORDER BY c.relname;
SELECT pg_get_serial_sequence('public.seerr_discovery_observations','observation_id') AS identity_sequence;
SELECT pg_get_userbyid(owner) AS sequence_owner,*
FROM (SELECT c.relowner AS owner,s.* FROM pg_sequence s
      JOIN pg_class c ON c.oid=s.seqrelid
      WHERE s.seqrelid='public.seerr_discovery_observations_observation_id_seq'::regclass) q;

SELECT table_name,privilege_type,grantee FROM information_schema.table_privileges
WHERE table_schema='public' AND table_name IN
 ('seerr_discovery_runs','seerr_discovered_movies','seerr_discovery_observations')
ORDER BY table_name,grantee,privilege_type;
-- Check each required privilege separately (a comma-list check can mean ANY).
SELECT t.name,p.privilege,has_table_privilege(current_user,'public.'||t.name,p.privilege)
FROM (VALUES ('seerr_discovery_runs'),('seerr_discovered_movies'),
             ('seerr_discovery_observations')) t(name)
CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE')) p(privilege);
SELECT p.privilege,has_sequence_privilege(current_user,
 'public.seerr_discovery_observations_observation_id_seq',p.privilege)
FROM (VALUES ('USAGE'),('SELECT')) p(privilege);

-- Canonical identity sequence has an internal dependency on observation_id.
SELECT seq.relname AS sequence,tbl.relname AS owning_table,a.attname,d.deptype
FROM pg_depend d JOIN pg_class seq ON seq.oid=d.objid AND seq.relkind='S'
JOIN pg_class tbl ON tbl.oid=d.refobjid
JOIN pg_attribute a ON a.attrelid=tbl.oid AND a.attnum=d.refobjsubid
WHERE seq.oid='public.seerr_discovery_observations_observation_id_seq'::regclass;
-- PUBLIC (grantee OID 0) must have no privileges on these tables/sequence.
SELECT c.relname,acl.privilege_type
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault(
 CASE WHEN c.relkind='S' THEN 's'::"char" ELSE 'r'::"char" END,c.relowner))) acl
WHERE n.nspname='public' AND c.relname IN
 ('seerr_discovery_runs','seerr_discovered_movies','seerr_discovery_observations',
  'seerr_discovery_observations_observation_id_seq') AND acl.grantee=0;

SELECT (SELECT count(*) FROM public.seerr_discovery_runs) AS runs,
       (SELECT count(*) FROM public.seerr_discovered_movies) AS movies,
       (SELECT count(*) FROM public.seerr_discovery_observations) AS observations;
ROLLBACK;
```

Compare every column/type/nullability/default/identity attribute and all index/constraint definitions to the reviewed SQL, not just the counts. Inspect sequence dependency/ownership and PUBLIC ACL absence; superuser `has_*_privilege` results alone do not prove restricted grants. All three row counts must be zero after installation, before any sync. Do not add grants or alter existing role privileges; the accepted owner/superuser already has effective access. No write probes are needed.

### Rollback implications

Any failure before the installation transaction commits rolls back its DDL as a unit. After commit, nondestructive operational rollback is to leave discovery disabled and retain the empty tables. The existing `rollback.sql`, which requires separate authorization, takes the same lock and drops observations, movies and runs in dependency order, without CASCADE; the identity sequence is removed with its owning column. It destroys any discovery history that may later exist and must never be run casually after population. No rollback was executed or automatically scheduled. Before/after snapshots of existing application schema, roles and pipeline settings matched after commit. That operator review and corrected read-only verification are now complete. Keep discovery disabled pending a separate first-sync decision; another installation or automatic destructive rollback is not appropriate.

## E. Database recovery readiness — PASS for logical recovery

### Current consistent backup and isolated restore — completed

The operator explicitly authorized one fresh production database backup and isolated recovery validation. **PASS:** the custom-format logical archive was created, fully read, restored successfully into a new isolated PostgreSQL 18 cluster, and validated against the same source snapshot. This establishes single-database logical recovery at the tested level; it does not establish complete application, host or point-in-time recovery.

The production URL and authenticated target were independently rechecked as **192.168.1.9:5432 / plexintel / jmnovak / PostgreSQL 18.6**, online and not in recovery. The URL still matched the running backend. The accepted temporary superuser exception remained in effect; no production roles, passwords, privileges, settings or application rows were changed.

A read-only REPEATABLE READ transaction exported a snapshot. Both `pg_dump --snapshot=...` and the reference catalog/row-count queries used that snapshot, avoiding comparison against a changing live database. The exporter was rolled back and closed when the dump completed. Credentials were supplied to the dump process privately from the existing URL, never placed in command arguments or output. No table/schema exclusions, `--no-owner`, or `--no-acl` shortcuts were used.

| Backup property | Verified result |
| --- | --- |
| Archive | `/home/jmnovak/.local/state/plexintel/preflight-backups/plexintel-20261028T231846Z-08d8dc.dump` |
| Directory / archive protection | Owner UID/GID 1000:1000; directory `0700`; archive and retained evidence `0600` |
| Format and scope | PostgreSQL custom archive, entire existing `plexintel` database |
| Backup start | **2026-10-28 18:18:46.987 CDT** (23:18:46.987 UTC) |
| Backup end | **2026-10-28 18:19:21.380 CDT** (23:19:21.380 UTC) |
| Size | **174,148,995 bytes**, approximately **166.08 MiB** |
| `pg_dump` exit / warnings | **0 / none** |
| Archive catalog | `pg_restore --list`: **exit 0**, expected application tables represented |
| Complete readability | `pg_restore --file=/dev/null`: **exit 0**, no warnings |
| Restore start / end | **18:19:24.996–18:19:45.259 CDT**, October 28 |
| Restore | `pg_restore --exit-on-error --single-transaction`: **exit 0**, no warnings/errors |
| Server / clients | Production PostgreSQL, isolated PostgreSQL, `pg_dump` and `pg_restore`: **18.6** |

Archive SHA-256, computed after creation and rechecked after validation:

```text
8754923a28ed13c140cb269e59b2389786e4d653e6cfbfcf14bb46fb06d52f1a
```

Checksum sidecar: `plexintel-20261028T231846Z-08d8dc.sha256` in the same private directory. A metadata-helper formatting error occurred before any dump began, was corrected, and its diagnostic evidence was retained. **Only one `pg_dump` backup was executed.**

### Restored data, schema and representative reads

The new disposable database was named `plexintel_recovery_validation`, in a freshly initialized cluster under the private backup directory. The cluster accepted **only a private Unix socket** on port identifier 55484, with `listen_addresses=''`; its data directory and absence of TCP addressing were checked before test-only role/database creation and before validation. No PlexIntel service was started against it. Locale/encoding matched production: libc `en_US.utf8`, UTF8.

All **40 application table counts** match the shared source snapshot. Core examples:

| Table | Snapshot and restored count |
| --- | ---: |
| `public.library` | 8,376 |
| `public.watch_history` | 9,816 |
| `public.watch_sessions` | 4,438 |
| `public.app_settings` | 96 |
| `public.training_data` | 9,284 |
| `public.recommendations` | 223,330 |
| `public.pipeline_runs` | 6 |
| `public.pipeline_run_stages` | 48 |

Catalog comparison matched **74 relations** (40 tables, 20 sequences, 14 views), **482 column metadata rows**, **200 constraints**, **85 indexes**, **20 sequence definitions**, **14 view definitions**, **387 table-grant entries**, and **three extension/version records**. There were no row-security policies on either side. Successful restoration also completed index builds and constraint restoration; no unexplained restore errors were tolerated.

Read-only validation queries for library media-type counts/identifiers, dated and linked viewing history, positive-duration sessions, history-to-library joins, configured application-setting counts and the playback-history view all succeeded and matched the snapshot results. No playback identities, IPs, session IDs, titles or secret configuration values were printed. Model/pipeline tables were restored and inspected as data; no training, scoring, recommendation or acquisition code was run.

**Reviewed extension metadata difference:** The initial strict textual function comparison flagged **32 of 163 functions** because source VectorChord definitions referenced `$libdir/vchord`, while extension recreation referenced `vchord`. All other text in those definitions and all remaining function definitions matched. Production `dynamic_library_path` and its compiled default are `$libdir`; both references resolve to the same installed `/usr/lib/postgresql/18/lib/vchord.so`, whose binary identity was recorded privately. This is a library-path spelling difference, not missing functions or a failed restore. PostgreSQL documents the `$libdir` substitution and search-path resolution rules. [PostgreSQL C-function dynamic loading](https://www.postgresql.org/docs/18/xfunc-c.html#XFUNC-C-DYNLOAD).

The original orchestration evidence retains its comparison-failure flag for auditability. It records **restore exit 0**, with only that function-text comparison differing; it does not record a failed `pg_restore`. The separate final `recovery-review.json` resolves the narrowly verified alias difference and records **PASS**. No source/restored database metadata was edited to force agreement, and no second backup was taken.

### Dependencies, scope and limitations

- Extensions restored at matching versions: **plpgsql 1.0, vector 0.8.1, vchord 0.5.3**. The isolated cluster preloaded VectorChord using already installed binaries; those binaries must be available in a real recovery environment. Other production preload modules/settings were not reproduced or modified.
- Referenced database role names were `jmnovak`, `plex_ro`, `plexintel_history_reader` and `plexintel_session_writer`. The isolated cluster's bootstrap owner was `jmnovak`; the other three names were created **only in the disposable cluster**, as login-disabled, nonadministrative placeholders, so ownership and ACL restoration could be checked without dropping grants. No production roles were created or altered.
- A single-database `pg_dump` does not include cluster-global role passwords, attributes, memberships or tablespace definitions. Those were not copied; a full environment recovery must provision its required globals securely. No custom application tablespaces were found, so no production paths were reused or remapped.
- Sequence definitions matched, and the archive restored sequence values. No claim is made that a sequence value observed later in the live database equals its archived value; sequence advancement is not an MVCC row-count comparison.
- This validates logical restore, core relational consistency, referenced grants and representative reads. It does **not** test full PlexIntel startup/authentication, external model artifacts, every application query, complete host restoration or point-in-time recovery. Application filesystem/configuration and extension binaries are separate recovery dependencies.
- The archive contains sensitive production data and must remain private. No new recurring backup job, retention policy or WAL archive was established. Its recovery point ages as normal production activity continues.

### Cleanup and retained evidence

The disposable cluster at:

`/home/jmnovak/.local/state/plexintel/preflight-backups/restore-p_mh6erg`

was stopped successfully and its entire temporary directory/database/socket was removed. The temporary operation helper in `/tmp` was also removed after preserving a private audit copy. No unrelated PostgreSQL data, existing image/logical backups or production objects were deleted.

Retained private evidence uses basename `plexintel-20261028T231846Z-08d8dc` under the archive directory:

- `.dump`, `.sha256`: validated archive and checksum.
- `.recovery-review.json`: final PASS assessment, alias resolution, counts, versions and cleanup evidence.
- `.evidence.json`: original stage results/times, including the strict comparison flag.
- `.source-snapshot.json`, `.restored-validation.json`: private catalog and aggregate count comparison inputs.
- `.archive-list.txt`, operation/validation logs and `.operation.py`: archive inventory, diagnostics and operation record; all owner-only.

The initial pre-dump metadata diagnostic files were also retained privately. Raw function definitions/configuration metadata were kept out of normal output and this report.

### Existing image backup — unchanged and still not a verified PostgreSQL recovery point

Root cron remains:

```text
2 3 * * 5 /usr/local/bin/image-backup /media/rpibk/backup.img
```

The latest observed image mtime remains **October 23, 03:13:34 CDT**, size 192,243,281,920 bytes. Its script uses a live root-filesystem `rsync` after `sync`, without a PostgreSQL shutdown, consistent snapshot or database-aware backup protocol. Neither an image mtime nor this successful new logical backup establishes consistency of that older image. PostgreSQL explains the requirements for filesystem-level recovery separately. [PostgreSQL filesystem-backup guidance](https://www.postgresql.org/docs/18/backup-file.html).

The May 12 logical archive remains an older, separately unvalidated file. **WAL archiving remains disabled**, with no new PITR chain or replication/backup architecture introduced. The current recovery PASS applies to the newly validated custom-format archive only.

## F. First-sync plan and approval checklist

### Bounded command — still NOT AUTHORIZED

Recovery readiness is now established. After separately approved schema installation/catalog verification, retain the existing production `DATABASE_URL` and user `jmnovak`, and separately approve this exact manual command from the repository root:

```bash
SEERR_DISCOVERY_ENABLED=true \
SEERR_DISCOVERY_MAX_REQUESTS=25 \
SEERR_DISCOVERY_RETRIES=0 \
SEERR_DISCOVERY_TIMEOUT=10 \
SEERR_DISCOVERY_INTERVAL=1 \
SEERR_DISCOVERY_MAX_RETRY_AFTER=5 \
plexenv/bin/python -B scripts/sync_seerr_discovery.py \
  --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env \
  --execute --start 2026-10-28 --end 2026-10-28 \
  --language all --sort-by primary_release_date.asc --max-pages 1 --json
```

The inline enablement applies only to a future approved command; the persistent file remains disabled. Do not run it now. The explicit date is a reproducible review scope; a different date requires approval. One ordinary Seerr page is expected to contain up to 20 titles, but **the client does not enforce a hard title-count cap**. All valid returned IDs on that page would persist; HTTP attempts, including discovery/details, are hard-capped at 25. With zero retries an ordinary 20-title page needs at most 21 requests, and one successful discovery call leaves at most 24 detail attempts. Calls are sequential, spaced by at least one second; the 10-second requests timeout covers connect/read behavior, not a total job deadline.

No `--enrich-due` or forced refresh is included. Default refresh batch 1,000 does not limit normal discovery; TTL/cooldown remain 24/1 hours. First persistence would create one run, canonical titles, per-title scope memberships, detail outcomes and terminal accounting, confined to the existing discovery design. An unexpected abandoned run would be recovered only after source validation under the advisory lock; inspect before granting first-sync approval.

The captured historical all-language dataset had 96 titles for this date, not a verified current population. With more than one live page, page cap 1 deliberately produces `partial`, `page_limit_exceeded` and exit 2; this is bounded persistence validation, not full coverage. An empty result does not validate title persistence. Do not automatically repeat/expand to force success. No curation eligibility filter, digital-availability assumption, acquisition or model scoring is introduced. `--dry-run` also issues real Seerr GETs and remains unauthorized.

### Post-sync validation — read-only

Capture the command's exit status and sanitized result/run ID for review. After an approved run, a supported summary is:

```bash
plexenv/bin/python -B scripts/sync_seerr_discovery.py \
  --credentials-file /home/jmnovak/.config/plexintel/seerr-discovery.env \
  --summary --json
```

Use an explicitly selected read-only reporting connection to the verified database for the following SQL. **These statements were not run against the absent discovery schema during this preflight.**

```sql
BEGIN READ ONLY;
SET LOCAL statement_timeout = '15s';
SET LOCAL lock_timeout = '2s';

-- Confirm target and reporting protection before interpreting results.
SELECT current_database(), current_user, inet_server_addr(), inet_server_port(),
       current_setting('transaction_read_only');

SELECT run_id, started_at, completed_at, status, operation,
       discovery_complete, enrichment_complete,
       source_key, parameters->>'source_id' AS source_id,
       parameters->'scopes' AS scopes, counts, pagination, errors, warnings
FROM public.seerr_discovery_runs
ORDER BY started_at DESC, run_id DESC LIMIT 5;

SELECT count(*) AS canonical_titles,
       count(*) FILTER (WHERE last_enriched_at IS NOT NULL) AS ever_enriched,
       count(*) FILTER (WHERE last_enriched_at IS NOT NULL
                        AND metadata_source_key IS NULL) AS ambiguous_enriched_source
FROM public.seerr_discovered_movies;

SELECT status, count(*) FROM public.seerr_discovery_runs GROUP BY status;
SELECT source_key, parameters->>'source_id' AS source_id, count(*)
FROM public.seerr_discovery_runs GROUP BY 1,2;
SELECT metadata_source_key, enrichment_status, count(*)
FROM public.seerr_discovered_movies GROUP BY 1,2;

WITH latest AS (
    SELECT run_id FROM public.seerr_discovery_runs
    ORDER BY started_at DESC, run_id DESC LIMIT 1
)
SELECT o.run_id, count(*) AS memberships, count(DISTINCT o.tmdb_id) AS titles,
       count(DISTINCT o.scope_key) AS scopes,
       count(*) FILTER (WHERE o.enrichment_outcome='success') AS enriched,
       count(*) FILTER (WHERE o.enrichment_outcome='cached') AS cached,
       count(*) FILTER (WHERE o.enrichment_outcome='failed') AS failed,
       count(*) FILTER (WHERE o.enrichment_outcome='deferred') AS deferred,
       count(*) FILTER (WHERE o.enrichment_outcome='pending') AS pending
FROM public.seerr_discovery_observations o JOIN latest USING (run_id)
GROUP BY o.run_id;

SELECT count(*) AS observations FROM public.seerr_discovery_observations;
SELECT field_states->>'release_events' AS incoming_release_state,
       count(*) AS titles,
       count(*) FILTER (WHERE release_events IS NULL) AS unknown_events,
       count(*) FILTER (WHERE release_events='[]'::jsonb) AS known_empty_events,
       count(*) FILTER (WHERE release_events IS NOT NULL
                        AND jsonb_typeof(release_events)<>'array') AS invalid_shape
FROM public.seerr_discovered_movies GROUP BY 1;

SELECT tmdb_id, field_states->>'release_events' AS incoming_release_state,
       release_events IS NULL AS unknown,
       CASE WHEN jsonb_typeof(release_events)='array'
            THEN jsonb_array_length(release_events) END AS retained_event_count
FROM public.seerr_discovered_movies ORDER BY tmdb_id LIMIT 25;

SELECT relname, pg_table_size(relid) AS table_toast_bytes,
       pg_indexes_size(relid) AS index_bytes,
       pg_total_relation_size(relid) AS allocated_bytes,
       n_live_tup, n_dead_tup, last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables
WHERE schemaname='public' AND relname IN
 ('seerr_discovery_runs','seerr_discovered_movies','seerr_discovery_observations');

SELECT run_id, status, started_at, completed_at, current_stage_key
FROM public.pipeline_runs ORDER BY started_at DESC LIMIT 3;
SELECT key, raw_value FROM public.app_settings
WHERE key IN ('pipeline.enabled','pipeline.frequency','pipeline.run_time','pipeline.timezone')
ORDER BY key;

ROLLBACK;
```

Check that the approved run is terminal and its counts reconcile with memberships; a page-capped run must not claim `discovery_complete=true`. No pending observations should be hidden under a claimed successful enrichment. Verify the recorded ID and endpoint hash against the approved configuration, and ensure there is exactly one source binding and no ambiguous enriched provenance. SQL NULL is unknown, `[]` is known-empty; an incoming unknown state can legitimately retain older populated or empty events. Primary dates do not prove digital availability. Populated event snapshots and nested source-presence states can be examined privately if needed; never expose requester details or credentials.

Compare post-install/pre-run and post-run physical sizes, disk space, sessions/lock waits, backend health and cumulative WAL counters over the same interval. WAL counters are cluster-wide, so concurrent services prevent attributing every byte to discovery. No write-based health probe, load test or EXPLAIN ANALYZE is required. Compare hashes of the protected model/scoring/pipeline inputs and inspect the existing pipeline status/settings and service/timer/cron inventories. Concurrent activity from the already enabled daily pipeline must be distinguished from a discovery-triggered change. Discovery code contains no acquisition/model invocation; it must remain that way.


### Final authorization checklist

- [x] Operator approved permanent source ID `plexintel-seerr-primary`; owner-only file created and validated locally without HTTP.
- [x] `SEERR_DISCOVERY_ENABLED=false`; existing normalized endpoint/key reused; legacy `.seer_creds` unchanged.
- [x] Existing production `DATABASE_URL`, server/database and user `jmnovak` retained; superuser access explicitly accepted temporarily. No new role or privilege changes required.
- [x] Fresh consistent custom archive created, fully read and restored in isolation; all 40 table counts matched; dependency/library-alias review passed; archive/evidence retained privately and disposable environment removed. **Logical recovery gate PASS.**
- [x] Operator explicitly approved the reviewed optional migration; target/hash/absence guards passed; the one-time transaction **committed successfully**.
- [x] Temporary identity parser corrected; all 64 columns, 19 core constraints, 11 indexes, identity attributes/dependency/unused state, owner/ACLs and **0/0/0** inventory verified read-only. Original failure history preserved; no DDL rerun or rollback.
- [x] Source/provenance and backend/pipeline/schedule checks completed; no inventory or bindings appeared. Recovery archive remains available with matching checksum. Recheck transient activity/capacity at the future approved execution time.
- [ ] Separately authorize the exact bounded first sync, its 25-attempt budget and possible partial/empty outcome. This task does not grant that authorization.
- [ ] Assign read-only post-sync review; retain discovery disabled by default and preserve acquisition/model/scheduling boundaries.

**Deferred hardening:** replacement of superuser operation with least-privilege separation is future security work, not a prerequisite silently reintroduced into this approved Phase 3 exception. Storage optimization, larger refresh query plans and extended discovery coverage also remain follow-up work; no code, schema redesign or recurring job was introduced.

**Latest verification evidence, October 28 at 18:52–18:54 CDT:** the corrected read-only verifier passed all 64 columns, 19 core constraints, 36 NOT NULL records, 11 indexes, identity sequence/ownership/dependency/initial state, ACLs and exact **0/0/0** inventory. All 11 existing-application metadata groups match their pre-installation snapshot. The backend remained active with the same PID/start/restart count and returned health HTTP 200; pipeline run 318 remains successful, normal pipeline configuration is unchanged, and no discovery schedule/process/hook was observed. The private source configuration still validates as disabled with approved identity and `0600` permissions; the recovery archive remains readable and checksum-matched. The original 18:42 installation failure history remains intact in the audit section and private evidence.

Comparison of 702 existing repository files found only this report changed, and all 1,131 original protected inputs remain unchanged. Documentation whitespace and historical-command syntax checks passed. The temporary corrected verifier was preserved privately and removed from `/tmp`. This task performed no migration, rollback, data write, sequence increment/write probe, Seerr call, sync, acquisition, model job, restart, schedule change, commit, push or deployment.

**Final recommendation: GO for separately authorizing the reviewed first bounded manual sync.** Schema/identity/privilege/empty-inventory/isolation verification is now **PASS**, the validated logical recovery point remains available, and the `jmnovak` superuser exception remains accepted. No unresolved schema discrepancy remains. **First synchronization is still NOT AUTHORIZED by this task and was not executed.** Keep the persistent configuration disabled and obtain explicit approval for that next operation; do not rerun the migration.
