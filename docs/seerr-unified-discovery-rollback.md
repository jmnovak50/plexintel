# Unified discovery rollback strategy

## Preferred operational rollback

Keep discovery disabled and do not invoke its CLI writer. Stop any separately authorized manual writer before maintenance. The active PlexIntel backend/pipelines do not invoke discovery; retaining unified tables does not activate it. Keep V2 schema/history intact while resolving a code issue. This preserves TV inventory, source provenance, membership history, fingerprints and timestamps without a production database mutation.

The previous V1 discovery writer is incompatible with the unified table/keys. Do not run old code against V2, create a shadow movie table, rerun `001_initial.sql`, or relabel/remove TV records to make old code appear compatible. Deploying code, changing configuration or stopping a production process each remains subject to the operator's authorization; none was done here.

## Failed forward upgrade

`002_unified_titles.sql` is a single atomic statement, with a five-second lock timeout and the existing advisory transaction lock. Use an explicit `psql --single-transaction -v ON_ERROR_STOP=1` wrapper after approval. A failure rolls back its changes. Isolated tests inject a failure after the rename and confirm original data/schema remain intact, including in autocommit.

If connection loss leaves commit outcome uncertain, inspect catalogs and preserved records read-only. Do not rerun blindly: an already unified schema is deliberately rejected. A timeout is a stop condition, not permission to weaken locking or remove dependencies. Complete post-upgrade verification before any discovery writer.

## Structural downgrade or database restore

No reverse migration is supplied or authorized. The original `rollback.sql` is **V1-only** and intentionally destructive; do not run it on V2. It references the old canonical table and cannot correctly remove or downgrade the unified inventory.

A future reviewed reverse migration would need to preserve/export all runs, typed observations and TV records, handle movie/TV ID collisions, reestablish V1 keys/date names/constraints/indexes, and explicitly define the treatment of TV membership history. Keeping history only partially can break provenance or misrepresent run counts. Automatically dropping TV or rewriting run JSON is unacceptable.

Restoring a pre-upgrade **whole database** backup removes all subsequent writes, including unrelated application/playback/model metadata. The previously validated archive predates even the original V1 installation; it is recovery evidence, not a lossless downgrade artifact. Its age and current recovery dependencies must be reviewed before a future operation. Do not alter that archive or perform a restore under this task.

Before any separately authorized structural rollback/restore, take a fresh consistent recovery point, record current catalogs/source binding/counts/hash/timestamps/sequence/ACLs, export discovery history, agree on data-loss scope and validate the procedure against a new disposable restore. No destructive restore test or automatic production rollback is part of this enhancement.
