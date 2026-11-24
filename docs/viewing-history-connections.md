# Connections to Your Viewing History

This capability adds factual context to an already selected recommendation. It
never explains why XGBoost scored a title, infers actor preferences, invokes a
model, or changes recommendation visibility, ranking, scores, filters or paging.
The existing Title Traits, Taste Match, semantic search, labels and diagnostics
remain intact. Production activation is separate from implementation approval.

## Source and evidence contract

Normalized `library`, `media_actors`, `media_directors`, `media_genres` and their
existing dictionaries supply the facts. There is no second media catalog,
source acquisition, metadata polling, age expiration or refresh requirement.
Predictive metadata revision handling is independent and unchanged.

Typed exact GUID validation reuses `api.predictive.recovery.stable_identity`.
Canonical aliases must agree about title/year, media kind, TV hierarchy/numbering
and applicable normalized facts. A conflict poisons that group and descendants;
no fuzzy title matching or vector lookup repairs it. Missing historical keys,
unsupported GUIDs and recycled-key title/type conflicts abstain. Scoped source
corrections can resolve those problems through the existing ingestion contract.

Current grouped history and latest feedback are retrieved once per cold page,
for the authorized viewer only. Observed watching uses the existing
`watch_history_enriched_v` convention: recorded playback at least half a known
positive runtime, in seconds versus normalized runtime in milliseconds. This
is evidence of watching, not liking. Intent (`interested`) alone does not qualify.
`watched_like` qualifies independently of recorded playback; the sentence says
"You marked ... as liked." Episode/season likes retain that scope in wording.

`never_watch` and `watched_dislike` override positive/watch evidence for the same
canonical title. A show rejection covers descendants; a season rejection covers
its episodes. An episode rejection excludes that episode's evidence, without
claiming the viewer dislikes its whole show. Feedback undo removes the current
feedback state; it does not reconstruct historical feedback. Actual grouped
viewing can still qualify independently after undo. Raw session IDs, playback
IPs and unverified reference-chain groupings are never needed.

TV evidence groups to its canonical show. Both sides use movie or show facts,
including when the recommendation is an episode or season. Wording names the
series and never asserts that a performer appeared in the watched episode, or
that the entire series was completed. No minimum episode count is imposed.
Separate qualified grouped events affect tie-breaking; no claim of a complete
rewatch is made from those counts. Recent activity and more complete playback
also affect ties, without creating another engagement classifier.

## Selection policy v2

Choose one connection per viewer/canonical display target, in this order:

1. The same actual series relationship.
2. A shared normalized director.
3. A shared normalized cast member.
4. Two or more actual shared genres. A single shared genre does not qualify;
   no connection is preferable to a broad single-tag fallback.

Within a tier, prefer explicit liking and greater observed playback fraction
(capped at one), then known target cast order and source cast order, followed by
qualified grouped-event count, recency, canonical source identity and entity ID.
Cast order therefore influences selection before a raw event count can let a
frequently watched series dominate a more prominent shared cast member. Unknown
orders sort after known orders but do not disqualify a connection. There is no
invented leading-cast cutoff or weighted quality formula. Genre wording includes
at most three actual shared tags. Higher-priority matches prevent unnecessary
lower-tier SQL work.

Persist every selected viewer/target connection independently of page arrival
order. At presentation, show each actor, director, displayed genre combination
or same-series fact only once within the requested page/batch, in its existing
order. Repetitions return null context for that page; their saved rows remain
ready and can be reused when viewed on another page or alone. This is distinct
from a persisted no-result: no supporting evidence is deleted or declared
absent. Different facts from one historical source can still be shown. There is
no arbitrary source quota, score/rank change, alternate filler selection,
cross-page fatigue profile or dependency graph. The independent UI refresh
preserves requested key order so its suppression winner matches the page.

Same-series wording is concise: "You've watched some of X" for observed
watching, or "You liked an episode/season of X" for scoped explicit feedback.
Episode/season likes use a separate sentence naming the series before describing
its credits, avoiding a relative clause that attaches a series credit to the
liked episode. No episode-credit or completion metadata is newly required.

Policy version `viewing-history-connections/2` invalidates version 1 saved
connections and no-results on first access, then reuses version 2 results.
Source revisions, persistence schema, authorization and feature activation are
unchanged. No migration or source-data correction is needed for this refinement.

Collections/franchise edges, writers and creators are not represented in the
normalized relationship schema and are not inferred from names, genres or plot.
Only actual TV hierarchy supports continuity initially. Actor/director IDs are
existing unique-name dictionary IDs, not provider person identifiers. The
implementation does not establish a new global person registry or resolve
unrepresented real-world homonyms. Known canonical/fact conflicts abstain.

## Persistence and invalidation

The optional migration is
`api/db/migrations/optional/viewing_connections/001_context.sql`, outside startup
migration discovery. It adds exactly two tables, one trigger function and
statement-level triggers on existing source owners, plus three reverse credit
indexes. No existing data is updated or seeded by the migration.

* `viewing_connection_context`: primary key `(username,target_identity)`; one
  current structured connection or explicit no-result, policy version, viewer
  and catalog revisions, and created/updated timestamps. It stores selected
  source identity, entity IDs/names and compact evidence category, playback
  fraction, grouped-event count and most recent evidence time. No copied history,
  scores, recommendation IDs, embeddings, model versions or rendered sentence.
  The structured value can evolve to multiple selections without changing its
  viewer/target ownership; v1 selects one.
* `viewing_connection_state`: one catalog revision and a row per affected viewer.
  Atomic counters express committed source changes. They are not sequence-ID
  watermarks, reconstructed historical states, or periodic freshness checks.

Statement transition tables coalesce bulk writes into one increment per affected
viewer. `watch_history` and `user_feedback` insert/update/delete/owner changes
invalidate both old/new owners; account changes invalidate relevant viewers and
remove contexts when an account is deleted/renamed. Normalized library,
relationship and dictionary changes invalidate the catalog revision, covering
canonical remapping and facts added after a no-result. Successful
`metadata_ingestion_events` receipts also invalidate catalog state; failed
receipt inserts do not. Source truncation invalidates the catalog. The trigger
updates share the source transaction: rollback never invalidates a valid cache.
Existing source writers need no hooks, imports or model/publication changes.

A normal prediction publication does not touch these source tables or own the
context. Its replacement recommendation IDs therefore cannot delete contexts.
The cache stores current context only, not a record of what was displayed before
source evidence changed. The invalidated old row is retained until its next
lookup replaces it; it is never rendered through the service as current.

Warm reads use a batched lookup and fresh revision validation. A cold request
uses one temporary scalar canonical index, one viewer evidence query, indexed
relational intersections and a batched upsert. It does not retrieve vectors or
whole provenance histories. A nonblocking per-viewer advisory lock avoids
concurrent cold derivations. Final short share locks recheck source revisions
before saving or returning cached selections; a racing source change causes
abstention. The unique viewer/target key prevents duplicate selections.

SQL statement limits are two seconds and final lock waits 100 ms. These are
operational fail-open limits for optional context, not eligibility thresholds or
an end-to-end request SLA. Timeouts, migration absence, lock contention and other
failures omit the connection while preserving recommendations; failed work is
not persisted as a confident no-result. Repeated successful no-results are
cached. There is no daemon, prewarmer, periodic history scan or scheduler change.

## API, UI and privacy

`PLEXINTEL_VIEWING_CONNECTIONS_ENABLED` defaults off and is the sole activation
switch. Disabled session/digest reads do not access connection persistence.
The structured field is `viewing_history_connection`; existing `explanation`,
`semantic_themes`, `title_traits` and `taste_match` retain their meanings.

The shared service enriches the existing authenticated session page after its
current pagination, authorized agent/MCP/OpenWebUI recommendation results after
their existing scope checks, and the recipient's digest. Public rendering
allowlists relationship type, source title/kind, target fact title/kind, shared
names, evidence category and factual text. Episode/season cards explicitly name
the target series for credits/genre connections, avoiding an episode-credit
assertion. It excludes source keys/GUIDs, raw history/session IDs,
provenance fingerprints and internal generations. Email output remains escaped.

The unauthenticated legacy `/api/recs` and global-key public recommendation
endpoints retain their existing contracts and do not gain private viewing
connections. A public recommendation key is not upgraded to a private history
credential. Existing tests exercise public/API-key behavior unchanged.

Desktop and mobile render **Connections to Your Viewing History** independently
of old explanation chips. No connection means no new section. Feedback changes
and undo clear current connection text immediately and reject older in-flight
context responses. The existing 15-second UI status poll also refreshes an
optional bounded batch of context without rerunning the recommendation query,
changing ordering, or invoking a predictive job.

`GET /api/recommendations/viewing-history-connections?rating_key=...` requires a
valid session, resolves its viewer server-side, accepts at most 250 positive keys
and restricts results to that viewer's current recommended leaves/TV display
groups. No request parameter selects another viewer. Failures clear optional
context. After a user loads more than 250 rows, that refresh covers the latest
250 and clears older context; recommendations themselves stay available. This
bounds ongoing work without fetching history separately per card. External
source changes become visible on the next request/poll; already delivered pages
and emails are snapshots, not a push subscription.

## Isolated validation and private review

`tests/test_viewing_connections.py` uses the private PostgreSQL fixture guard in
`test_metadata_ingestion.py`; each test owns a disposable database. It covers
factual relationships, scope/wording, identities, negative evidence/undo,
persistence across score replacement, no-results, concurrent readers and source
changes, rollback, truncation, account changes, timeout recovery and enabled
session/agent/digest integration. Existing authorization/consumer suites remain
part of regression acceptance.

For a new owner-only current preview (always a read-only transaction):

```sh
plexenv/bin/python scripts/preview_viewing_connections.py --user EXISTING_VIEWER \
  --view all --limit 20 --output /private/path/connections.html
```

The output is exclusively created with mode 0600. It never installs schema or
writes contexts, and does not require activating the feature.

The private review package under `.secrets/viewing-connections-20261122/` contains
read-only current-source exports, replay examples, screenshots, timings and test
results. Actual facts and compact evidence were copied into a disposable local
database to demonstrate persisted reuse; production context tables were absent at that review.
Preview storage status refers to that isolated persistence, not a production
cache hit. Read-only derivation agrees with saved results. No private artifacts
are committed or transmitted to external inference services.

## Production operation and rollback

Production deployment and activation on birch were authorized on November 24,
2026. The approved engine is integrated in `f64e1d8`, including `acd2b7f`,
`5d1aaca`, policy refinement `86e6956` and Tautulli ingestion fix `cc20e24`.
The rollout receipt records the exact deployed commit, including operator
instruction updates. The pre-deployment rollback baseline is **`cc20e24`**.

The non-containerized `plexintel-backend.service` runs this checkout and reads
its `.env` via systemd's existing `EnvironmentFile`. Set
`PLEXINTEL_VIEWING_CONNECTIONS_ENABLED=true` there to enable version 2. The
backend serves the committed frontend build. Title Traits and Taste Match remain
available alongside the new section; labeling containment and scheduling are
independent and must remain unchanged.

For deployment, acquire the existing `try_acquire_pipeline_lock()` exclusion,
check `active_workers()` and pending dimension reviews, and retain the lock
through the database migration, code installation, necessary backend restart
and readiness checks. Coordinate with the existing predictive advisory lock;
never start a pipeline as a deployment check. Preserve scheduler settings and
check the current slot before restarting an enabled scheduler.

Apply only `api/db/migrations/optional/viewing_connections/001_context.sql`
once in one transaction with production credentials (`psql -X
--single-transaction --set ON_ERROR_STOP=1`, or the existing psycopg2 transaction
procedure). Verify its reviewed bytes before executing it. The approved schema
adds two tables, one function, 44 statement triggers and three reverse credit
indexes. Do not run `create.sql`, certify historical metadata, backfill or
precompute connection contexts. Normal authorized recommendation, refresh and
digest-preview requests create the viewer-specific contexts naturally.

Verify local and public HTTPS health, the active feature flag in the backend
process, authenticated recommendation and context requests, desktop/mobile
cards, entitled agent/MCP consumers and recipient-specific digest preview
without sending mail. Compare recommendation ordering/scores/visibility and
existing source/model/settings fingerprints, retain actual examples privately,
and compare context timestamps and revisions across repeated requests to verify
warm reuse. Existing isolated tests cover destructive invalidation scenarios;
do not change production viewing or feedback to demonstrate them.

For rollback, set `PLEXINTEL_VIEWING_CONNECTIONS_ENABLED=false` and restart only
the backend while holding the existing execution lock and checking workers. If
code rollback is necessary, restore **`cc20e24`**, which preserves the latest
Tautulli ingestion fix; do not use `6058081`. Retain additive tables, indexes and
persisted records. Disabling the flag stops connection lookups/rendering but
does not stop transactional invalidation triggers.

If the triggers themselves cause a material problem, use a separately recorded,
narrow, reversible containment of only `viewing_connection_*` triggers on the
listed source tables. Before permitting any later connection reads, invalidate
all persisted contexts by transactionally incrementing the catalog revision,
then restore and verify every trigger. Never treat saved contexts as current
after an untracked source-change interval. Do not automatically drop tables or
revert the metadata-ingestion contract. Preserve all legacy metadata, labels,
SHAP, scores, embeddings, models, schedules and historical records.
