# Normalized metadata acceptance

Existing library metadata is a stable internal snapshot. Ordinary collection
discovers absent titles and accepts them once; changed upstream metadata is not
an update instruction. This contract does not change predictive metadata
revision handling, canonical recovery, stored-source fallback, embeddings,
training, scoring, publication, or Seerr discovery.

## Acceptance and evidence

`api/services/metadata_ingestion.py` validates the requested/returned key, media
kind, existing canonical identity rules, parent/series relationships, and usable
movie/episode runtime. Zero season/episode indexes are retained. Optional
descriptive fields can be empty or unavailable; malformed collections and
operationally incomplete required identity/runtime cannot be accepted. Tautulli
optional descriptive fields omitted/null are recorded as unavailable, **not** as
an observed empty set. Cast/genre fallback retains its series scope. No director
is required for a show/season, and no provider person ID is required.

The title, dictionaries/relationships and successful receipt commit together.
Relationship helpers never commit or swallow errors. Writers use the short
transaction advisory mutex `(184727, 73)`, fetch remotely before acquiring it,
and use insert-on-conflict-skip for new titles. A competing insert never appends
relationships to the winner. Failed attempts leave no partial accepted title.
Receipt insertion failure also rolls back acceptance. A connection lost during
commit is checked against receipts through a fresh read-only connection; the
job reports the resolved/unknown outcome and stops rather than guessing or
retrying writes. Reapply a correction plan to resolve its operation ID safely.

`metadata_collection.py` collects and checks discovery pages before accepting
new titles, preserving the existing library scope. Users/history retain separate
transactions and visible outcomes. A partial metadata/discovery failure produces
a nonzero collection exit even if other work committed, preserving the
predictor's existing source-failure behavior and last published results.

Only validated candidates are cached, with a bounded 128-title cache. No vectors
or full provenance histories are loaded by this path. Receipt growth follows
new acceptances, failed attempts and real corrections; ordinary skips create no
events. Measure actual storage/concurrency before changing these limits.

## The one additive relation

`metadata_ingestion_events` is the application's append-only acceptance and
correction ledger. It stores a contract version, operation ID, outcome, source
presence/scope, observation time and hashes; corrections retain scoped
before/after values. `recorded_at` is receipt creation time, not an inferred
PostgreSQL commit timestamp. Failures can precede successful retry; applied
operation/key pairs are unique. There is no FK to missing titles or prunable
pipeline runs. No legacy records are seeded.

* Row absent: new/rediscoverable title; a failed receipt explains a previous
  incomplete attempt when available.
* Row with successful initial-acceptance receipt: accepted under that version.
* Later successful completion/correction: retains acceptance and records change.
* Row without an initial-acceptance receipt: historical completeness unknown,
  even if a narrow legacy repair has succeeded.

The migration is deliberately outside startup's `migrations/*.sql` glob:
`api/db/migrations/optional/metadata_ingestion/001_contract.sql`. It must be
applied explicitly and transactionally before deploying the new ingestion
writer. Fresh-install DDL is included in `create.sql`. Missing migration fails
new ingestion before writes; optional feedback GUID completion defers while
feedback remains available. Normal read APIs do not require the ledger.

Production migration/deployment, any data repair, and scheduler changes are
separate from isolated implementation approval. No production backfill is
needed or authorized by installing the ledger.

## Operator interfaces

No importer arguments means usage and no writes. Explicit `--mode full` scans
the full configured scope but only accepts absent titles; it never overwrites
existing records. `--mode incremental --no-embeddings` remains the daily runner's
invocation. Recover mode also restores missing parents before children.
Retired numeric modes remain guarded; this change does not reactivate the old
Recently Added launcher or change timers.

`--dry-run` for normalized modes uses a read-only database connection and skips
schema bootstrap, source cache clear, users/history writes and inference.
Preview means no attempted INSERT followed by rollback: sequences stay unchanged.

Explicit correction preparation (examples describe the interface, not authority
to mutate production):

```sh
python scripts/correct_metadata.py status --rating-key 123
python scripts/correct_metadata.py preview --rating-key 123 \
  --changes changes.json --operator operator --reason "Scoped correction" \
  --output private-plan.json
python scripts/correct_metadata.py apply --plan private-plan.json --dry-run
python scripts/correct_metadata.py apply --plan private-plan.json
```

Preview files show existing scoped values alongside the proposed fields/operations
and are exclusively created with mode 0600. A changes file names only
authorized fields and relationships, for example:

```json
{"fields":{"summary":"Corrected synopsis"},
 "relationships":{"actors":{"action":"remove","values":[456]}}}
```

Supported relationship actions are `add`, `remove`, `replace`, and actor `orders`.
`remove` uses existing integer dictionary IDs; `replace: []` is an explicit
authorized clear. Missing/unknown source data never implies deletion. Dictionary
names are not globally renamed. The before-state fingerprint and identity are
rechecked under lock. A stale plan requires a fresh preview; repeated application
of the same operation is a no-op/replay. Changing the content of an already
applied operation ID is rejected.

`preview --completion` fills identified missing scalar fields; it cannot replace
known values or refresh membership. Explicit membership changes use correction
mode. `orders --rating-key ... --operator ... --reason ... --output ...` prepares
NULL-order completion for current members only. `--reorder` explicitly permits
known-order changes while preserving membership. Ambiguous order collisions defer
to reviewed reorder. The importer `backfill_cast_order` alias requires explicit
keys/operator/reason, previews by default, and applies only with `--apply --plan`
using those exact reviewed values; apply never refetches or rebuilds a new plan.

Missing-GUID repair is shared by incremental collection and feedback. It checks
returned identity/parents/title/year and any retained canonical GUID anchor,
then uses a conditional missing-field completion. Existing GUID conflicts defer;
no unrelated metadata changes. Feedback owns its transaction; savepoint rollback
of an optional repair does not roll back the feedback action.

Explicit operator application takes the existing predictor writer lock
nonblockingly and defers if the predictor is active. Normal collection never
tries to acquire that parent-owned lock again.

## Existing data, corrections and recovery

Do not infer defects from NULL optional fields, non-null GUIDs, or differences
from a newer predictive snapshot. Existing rows remain untouched/unassessed.
Confirmed defects require scoped evidence and a reviewed preview before any
production mutation. `inverse --event-id ... --operator ... --reason ... --output ...`
prepares a separate reversal preview and refuses intervening changes. It cannot
delete an initially accepted title. Reversal is an explicit inverse plan with a fresh expected
state; preserve the original receipt. Keep the old `.bk` importer unchanged as
historical evidence and outside supported launchers/deployment. Application
contracts cannot make privileged ad hoc SQL or historical scripts safe.

Future viewing-history connections should use normalized series/movie credits
and honest series wording. No second metadata catalog, age TTL, polling service
or periodic metadata validation is introduced. Successful existing-title change
events provide a future invalidation hook; failed attempts and skipped titles
are not changes. A committed event-count token handles out-of-order commits;
bare global MAX(sequence) is not a safe commit watermark. Selected connection
persistence remains a separate feature.

For rollout, apply the optional migration only when authorized, deploy the
coherent writer change, and observe an already scheduled collection. For rollback,
retain accepted metadata and receipts. Prefer a verified safe writer build; do
not restore broad-upsert behavior as an automatic rollback. If no safe writer is
available, stop normalized writes/keep preview available and preserve published
recommendations. No destructive schema rollback or blanket reimport is needed.

## Validation

`tests/test_metadata_ingestion.py` requires `PLEXINTEL_METADATA_TEST_DSN` pointing
to a deliberately private `/tmp/plexintel-metadata-pg-*` Unix-socket cluster. Each
test creates/drops its own disposable database. It covers actual transactions,
relationship/receipt failure injection, two-connection races, source mismatch,
initial/legacy status, scoped corrections, uncertain commit acknowledgements,
real CLI subprocesses, unchanged history processing, and old/new normalized
replay using the unmodified predictive source signature. Existing predictive
replay/publication and consumer suites remain part of acceptance.
