# Durable media/watch inference

Media and watch encoder results are committed independently of predictive
publication. The public vector tables, active configuration, training rows,
recommendations and SHAP records remain one atomic published bundle. User profiles
are still reconstructed normally and are never cached here.

## Schema and installation

`api/db/migrations/optional/simple_predictor/002_pending_inference.sql` creates
exactly one table, `public.pending_embedding_inference`, with seven columns:

| Column | Type / purpose |
| --- | --- |
| modality | text; `media_text` or `watch` |
| source_key | integer; existing source identity key |
| input_hash | SHA-256 of the existing serialized input and modality contract |
| modality_contract_hash | SHA-256 of the existing modality contract |
| encoder_digest | Exact installed encoder digest |
| embedding | `public.vector(768)` |
| vector_sha256 | SHA-256 of the existing little-endian float32 representation |

The only index is the primary key `(modality, source_key)`. Each key has at most
one latest candidate. There are no execution IDs, generation IDs, statuses,
timestamps, raw metadata, profiles, training features or prediction snapshots.
Hashes have lowercase SHA-256 checks; modality and vector width are constrained.
Runtime validation also requires finite unit vectors and matching checksums.

This is an explicit optional migration, not a startup migration. Apply it in a
transaction to the reviewed database **before** starting the new worker. The SQL
deliberately fails if the relation already exists rather than silently accepting
an unknown shape. Fresh-install DDL is also included in `create.sql`.

Example installation command for an already explicitly configured destination:

```sh
psql --no-psqlrc --set=ON_ERROR_STOP=1 --single-transaction \
  --file=api/db/migrations/optional/simple_predictor/002_pending_inference.sql
```

Use the existing guarded deployment procedure. No production pipeline run,
backfill, source mutation or encoder request is required to apply the migration.
The worker checks its presence before collection/inference and never creates it.
Deploying this source without the migration stops a new daily worker before work;
existing recommendation readers continue using the prior publication. An older
worker ignores the new table if code is rolled back; preserve the table/results.
Workers load source when launched: in a shared serving/source checkout, lack of
a backend restart does not isolate a future worker from edited source. Coordinate
the migration before the next worker launch from that checkout.

## Reuse and durability

Current source resolution, canonical identity, history partitioning, metadata
recovery and serialization happen first. Prefer compatible validated public
vectors, then pending vectors, then inference. Pending existence never admits a
title/event, supplies metadata, establishes availability or changes eligibility.
The full model feature-space ID is not the cache identity: existing modality
compatibility still allows media reuse across unrelated profile/model changes.

Only a validated new encoder result is upserted. Lookup transactions finish
before encoder requests; successful writes commit immediately under the existing
session writer exclusion. There is no transaction held over inference and no
new retry policy. A persistence failure stops the execution without claiming
durability. An ambiguous commit is not replayed here: the next ordinary explicit
execution reads and validates whatever actually committed. A crash between the
encoder response and successful persistence can still lose that last response;
durability is claimed only after the commit returns.

Public vectors and active release remain untouched during preparation. All
existing temporary vector materialization, source drift detection, backup,
publication, verification and last-known-good restoration remain in place. The
pending table is outside `PUBLISHED`, source-vector membership and restoration.

## Deterministic retention

No cleanup occurs during preparation or because an execution failed. A failed,
cancelled or incomplete source reconciliation cannot authorize broad cleanup.

After the existing prepared-set verification, publication locks, source signature
and incumbent checks, the publisher creates/verifies its ordinary last-good
backup. Inside the **same transaction as publication**, it may remove:

1. **Backup-covered identical records:** same key, input hash, modality contract,
   encoder, vector checksum and actual vector as a public row in that verified
   last-good population. This requires a verified public-text incumbent backup.
2. **Obsolete candidates:** no matching key/input/modality/encoder in the complete
   prepared population about to be published. This includes reconciled absent or
   ineligible keys and replaced inputs/contracts. It never removes public data.
3. **Invalid candidates:** remaining cache vectors fail shape, unit-norm or
   checksum validation, including corrupt duplicates hidden by published reuse.

Cleanup rolls back with any failed publication. New pending results normally
remain after their first promotion, because the backup still contains the prior
release. A later verified backup covering them permits removal. Restoring that
backup cannot erase other pending results; restoration excludes this table.
An initial publication with no verified incumbent never claims backup coverage.

Replacing a candidate for the same source keeps only its newest actual input;
old inputs cannot hit compatibility checks. This is bounded by encountered source
keys, not by run count. A successful full reconciliation prunes unreferenced
keys. Repeated failed partial attempts can leave such entries until that safe
boundary; no age policy, timer or historical-vector archive is introduced.

## Visibility and validation

Existing stage stdout distinguishes published reuse, pending reuse, rejected
invalid/incompatible candidates, encoder completion awaiting persistence, durable
completion and persistence failure. Watch work is title-attributed; unchanged
published watch reuse remains aggregate. Stage diagnostics retain both total
reuse and its components, completed inference, durable writes, lookup/persistence
seconds and retained population. Committed publication reports backup-covered
and obsolete removals, retained population and cleanup seconds. Failed or
uncertain commits do not emit a successful cleanup result.

Tests use only disposable PostgreSQL, synthetic sources/encoder vectors and
temporary artifact directories. They cover interrupted preparation, actual
process kill/database-connection termination after commit, downstream failures,
publication rollback, source/contract changes, invalid candidates, identity and
history isolation, deterministic feature/prediction/SHAP equivalence and
last-good restoration/cleanup. They never fail or run the live pipeline.

Metadata policy, serialization, full-vector temporary staging, profile rebuilding,
predictor settings/features, feedback, engagement rules, non-blocking statistical
warnings, semantic labeling authorization, scheduling and PostgreSQL resource
limits are unchanged. No legacy generation/checkpoint machinery is activated.

## Measured fixture overhead

A disposable PostgreSQL 18 cluster with `fsync=on`, `synchronous_commit=on` and a
private Unix socket stored 225 media plus 327 watch candidates using distinct
dense synthetic unit vectors. No encoder requests were made. Measurements:

| Measurement | Result |
| --- | --- |
| Vector payload | 1,697,952 bytes |
| Total table/TOAST/index allocation | 2,572,288 bytes (2.45 MiB) |
| Primary-key index | 32,768 bytes |
| 552 individually committed writes, including validation | 0.754 seconds |
| Mean / p95 write | 1.365 / 1.819 milliseconds |
| 552 pending lookups and validation | 0.348 seconds |
| WAL during writes | 2,154,040 bytes |
| Additional WAL during lookups | 0 bytes |

These characterize the isolated fixture and local storage, not production
network latency or full-pipeline performance. The existing full-vector temporary
materialization cost remains unchanged and is not included in these timings.
