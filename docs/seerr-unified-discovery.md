# Unified movie and new-series discovery — implementation and review

**Current production status — October 28, 2026, 20:51 CDT:** Gate A completed: migration **002 committed**, strict V2 verification **PASS**, inventory empty, discovery **disabled**. See [Gate A verification](seerr-discovery-gate-a-verification.md). Earlier V1/preflight statements below are historical; do not rerun 001/002 or proceed to Gate B without separate authorization.

## Current readiness remediation

The original delivery/test evidence below is historical (**214 tests**, five-title synthetic replay). The later deployment-readiness review found three P2 issues, now remediated; see [current behavior, 271-test evidence and readiness assessment](seerr-discovery-readiness-remediation.md). Migration 002 remains unchanged and uninstalled in production. The original deployment-readiness review's production audit used read-only queries; implementation remediation used only the disposable fixture.

## Initial delivery outcome and boundary (historical)

**GO for independent code review.** A separate review agent reviewed the implementation and migration, reported two correctness issues, and verified both fixes. The focused suite passed **214 tests** against synthetic responses and an isolated PostgreSQL 18 fixture. Captured movie replay and synthetic combined replay passed with **zero HTTP calls**.

**No production migration, database connection, Seerr request, synchronization, service restart, deployment, scheduling, acquisition, scoring, training, recommendation change, credential/privilege change, commit or push occurred in this enhancement.** Discovery remains disabled in the existing operator configuration. The validated production backup was not opened for writing or changed. Production remains the historically verified movie-only V1 installation; its current contents/activity were not re-audited here.

The current CLI writer and read-only summary require unified V2 and fail closed on V1 before run recovery/insertion or HTTP. Do not run historical first-sync commands with this checkout until separately authorizing, applying and verifying 002. A dry-run issues Seerr GETs and is also outside this task's authorization.

## Architecture and identities

One inventory, repository, source binding, client, run lifecycle, observation model and refresh queue serve both media types. The shared hard HTTP-attempt budget includes discovery, enrichment and retries across both types. There is no parallel TV subsystem, episode persistence or Sonarr monitoring.

| Contract | Unified behavior |
| --- | --- |
| Canonical table | `public.seerr_discovered_titles`, renamed in place from `seerr_discovered_movies` |
| Canonical key | `(media_type, tmdb_id)`; exact `movie` or `tv`, positive bigint ID |
| Observation key | Existing identity ID plus unique `(run_id, media_type, tmdb_id, scope_key)`; typed canonical FK |
| Source binding | Existing permanent source ID + normalized endpoint hash; shared by both types, validated before writes/HTTP |
| Scope identity | Media type + name + query parameters; historical V1 scope keys/run JSON remain unchanged |
| Premiere dates | `premiere_date`: movie primary release or TV original first-air date; `discovery_premiere_date`: independently retained summary date |
| TV coverage audit | Nullable observation `eligibility` JSONB with `eligible/provisional/excluded` and reason; movies and historical observations use NULL |
| TV extension | One nullable `tv_metadata` JSONB object, TV-only; no new season/episode tables |
| Reporting | Generic title totals and `by_media_type`; legacy `movies/new_movies/existing_movies/updated_movies` remain strictly movie-only |

Every lookup/upsert, cache hit, refresh selection, detail routing, source fingerprint and membership uses media type. Valid legacy movie sanitization and the V1 fingerprint projection remain byte-for-byte compatible. TV fingerprints add an explicit TV domain. This avoids rehashing/relabeling historical movies while isolating the TMDB namespaces. Original dates, fingerprints, timestamps, run JSON and sanitized snapshots survive the migration unchanged.

## Upstream contract inspected

Public official source was inspected at pinned Seerr revision [`bfbb3e9452756e66193d55d92b8a4d4da8bd7351`](https://github.com/seerr-team/seerr/tree/bfbb3e9452756e66193d55d92b8a4d4da8bd7351). Relevant implemented contracts:

- [Discovery routes](https://github.com/seerr-team/seerr/blob/bfbb3e9452756e66193d55d92b8a4d4da8bd7351/server/routes/discover.ts): `/discover/movies` uses primary-release bounds; `/discover/tv` uses `firstAirDateGte/Lte` → TMDB `first_air_date.gte/lte`, rather than later-season/episode dates.
- [TV mapping](https://github.com/seerr-team/seerr/blob/bfbb3e9452756e66193d55d92b8a4d4da8bd7351/server/models/Tv.ts) and [search mapping](https://github.com/seerr-team/seerr/blob/bfbb3e9452756e66193d55d92b8a4d4da8bd7351/server/models/Search.ts): TV `name`, `originalName`, `firstAirDate`, `episodeRunTime[]`, `createdBy[]`, `numberOfSeasons`, aggregate credits and season summaries differ from movie detail. Implemented plural `numberOfSeasons` takes precedence over the stale singular spelling in the published API schema.
- [TV detail route](https://github.com/seerr-team/seerr/blob/bfbb3e9452756e66193d55d92b8a4d4da8bd7351/server/routes/tv.ts): `/tv/{tmdbId}` supplies series metadata; season/episode endpoints are outside the client's allowlist.

Cached source URLs and hashes are in `artifacts/seerr-exploration/2026-10-28-unified-discovery/upstream-contract/manifest.json`. This is an implemented upstream reference, **not proof that production runs that revision**. No production API was contacted; deployed-version compatibility remains a rollout gate.

## New-series coverage and uncertainty

TV discovery requires a valid original series premiere inside the explicitly configured inclusive window. Historical windows permit late discovery; there is no requirement to discover a title on its premiere day. Returning-season announcements, last-air dates, next episodes and individual episode/season results cannot create new-series candidates. Missing/malformed original summary dates are retained as provisional canonical records and audited in `pagination.unresolved`, then detail-enriched. Detail may resolve them; unsuccessful enrichment preserves the candidate and yields a partial run. Unknown eligibility alone does not imply incomplete retrieval; no date is inferred from episodes.

A valid summary initially has provisional classification pending detail. Detail inside the window is eligible only when Season 1 has a valid date matching the original premiere and no contradictory season/summary evidence exists. A nonempty type, incomplete seasons, or a recent Season 2 alone cannot establish eligibility; future announcements with incomplete Season 1 evidence remain provisional. Explicit types `Special`, `TV Special`, `TV Movie`, or nonempty confirmed season summaries containing only season 0, are excluded. These explicit exclusions take precedence over unknown dates and refresh-without-window. `Miniseries`, one episode, or season 0 alongside a positive season do not independently imply a special. No universal upstream special flag exists; unknown classification stays provisional.

Summary exclusions retain ID/type/reason in run pagination. A summary/detail contradiction discovered after insertion remains in the inventory and observation history with provisional eligibility and a diagnostic; confirmed ineligibility (such as explicit specials) remains excluded. Neither unresolved nor excluded evidence is automatically acquisition-approved. Inventory counts include these records. `success` indicates complete retrieval/accounting, not that every TV row is eligible. Unknown detail dates/classification may therefore produce successful retrieval with provisional eligibility. Per-run TV counts prefer any eligible membership, then provisional, then excluded when a title belongs to multiple scopes; individual observation reasons remain available.

Eligibility describes the latest sanitized detail snapshot attached to that observation (a cache hit retains its original fetch age), rather than retained canonical TV values. Earlier exclusions remain auditable but are not sticky; changed or incomplete source evidence can change assessment. Neither eligible classification nor successful retrieval authorizes acquisition.

Explicit metadata refresh updates already discovered titles without changing first/last discovery timestamps or generating discovery events. Refresh-only TV observations have provisional `refresh_not_new_series_discovery` unless an explicit special exclusion applies. They do not establish a fresh date-window eligibility claim.

Premiere dates never establish streaming, download or digital availability. No popularity/vote/runtime/genre/engagement acquisition filter is activated.

## Metadata and status semantics

Movie runtime and country release events retain their prior contract. TV `runtime` and `release_events` are NULL with `not_applicable` presence states; episode runtime arrays, creators, series type, season numbers/counts, native season premiere dates/presence, episode count, in-production flag and series status live in `tv_metadata`. Creator names do not become directors. No movie-style release event is fabricated from TV seasons/episodes.

TV native arrays distinguish omitted/null/invalid from authoritative `[]`: unknown arrays preserve the last known value; true empty arrays clear it. Initial unknown values remain unknown, never coerced to `[]`; presence states preserve the observation's uncertainty even when values are retained. TV genres/countries/companies/genre IDs reject malformed members instead of filtering them into authoritative emptiness. General shared scalar/null semantics remain as documented in the persistence guide; movie release-event nested unknown/empty semantics are unchanged. Repeated identical responses preserve fingerprints/change timestamps; new run observations append intentionally.

Status codes retain explicit unknown/null/omitted states separately from known request/library codes. Missing status or failed detail is not evidence that a title is absent or unrequested. Standard/4K states remain separate. Sanitized TV requests retain status/is4k and seasonNumber/status only, without requester identity, internal IDs, tokens or URLs. Season status is metadata, not a request/acquisition action or monitoring instruction.

## Forward migration and rollout gates

[`002_unified_titles.sql`](../api/db/migrations/optional/seerr_discovery/002_unified_titles.sql) is a single atomic `DO` statement. It sets a five-second lock timeout, takes the existing `(184725,30)` transaction advisory lock and locks only the three discovery tables exclusively. It checks expected V1 objects, columns/defaults, constraints, indexes/validity, owner consistency, sequence identity/dependency and unexpected external dependencies/user triggers. Drift, missing V1, both/new tables, or a repeated upgrade fails rather than adopting an ambiguous schema. PostgreSQL catalog rendering is version-sensitive; the verified baseline and fixture are PostgreSQL 18.

The migration renames the canonical table and two date columns, labels existing canonical/observation rows `movie`, adds targeted TV/eligibility JSONB, builds the composite PK/FK/uniqueness, and replaces/renames affected indexes. It preserves run history, data, source provenance, sequence values, table ownership and ACLs. Temporary movie defaults are removed so new writers must explicitly supply media type. Legacy names on unaffected constraints remain intentionally. No unrelated application object, role or grant changes.

Original `001_initial.sql` and `rollback.sql` remain unchanged. **Never rerun 001 on V2**; it is not a version manager. A fresh disposable installation needs 001 then 002. Existing production V1 needs only separately approved 002, after current-state/target/recovery checks. Reviewed illustrative operator command, **not executed**:

```bash
# Supply the approved existing target through the established connection conventions.
# Reconfirm authenticated server/database/user first; do not embed secrets here.
psql -X -v ON_ERROR_STOP=1 --single-transaction \
  -f api/db/migrations/optional/seerr_discovery/002_unified_titles.sql
```

No production target/backup freshness is inferred from fixture results. Reconfirm actual catalogs, dependencies/DDL event triggers, row counts, owner/grants, capacity and backup recovery point immediately before any separately approved upgrade; verify all resulting keys/indexes/columns, source provenance, preserved counts/hash/timestamps and sequence afterward. Do not proceed on a five-second lock timeout. First live sync, bounded media/window/request limits, private enablement and post-sync review require further explicit authorization. Existing `jmnovak` superuser use remains the accepted temporary exception; least privilege is deferred.

Operational rollback is disabling discovery and retaining V2 data. A reverse structural migration/restore is a separate operation with data-loss and application-wide recovery implications; see [rollback strategy](seerr-unified-discovery-rollback.md).

## Reproducible isolated validation

Use the disposable, Unix-socket-only fixture setup in [the persistence guide](seerr-discovery-persistence.md#validation-and-sample-evidence). Tests refuse other database names, socket roots, data directories or TCP-enabled servers **before DDL**. No production connection variable is used by these fixture commands.

```bash
# Only after starting the dedicated disposable cluster described in the guide:
export SEERR_DISCOVERY_TEST_DSN='host=/tmp/plexintel-seerr-fixture.XXX port=55483 dbname=plexintel_seerr_fixture'
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' plexenv/bin/python -m pytest -q \
  tests/test_seerr_discovery.py tests/test_seerr_unified_discovery.py \
  tests/test_seerr_exploration.py tests/test_seerr_phase2.py tests/test_schema_migrations.py
plexenv/bin/python -m tests.replay_seerr_discovery
plexenv/bin/python -m tests.replay_seerr_unified_discovery
```

The replay entry points reset only this verified disposable fixture. Captured replay additionally requires the existing private Phase 1 candidates/detail cache. Synthetic replay is self-contained. Stop the disposable cluster afterward; no service deployment is involved.

Illustrative future CLI selections, **not executed or authorized here**:

```bash
# Only after separately authorizing live GETs; not executed in this task.
plexenv/bin/python scripts/sync_seerr_discovery.py --dry-run --media-type movie --json
plexenv/bin/python scripts/sync_seerr_discovery.py --dry-run --media-type tv --json
plexenv/bin/python scripts/sync_seerr_discovery.py --dry-run \
  --media-type movie --media-type tv --start 2026-10-26 --end 2026-11-01 --max-pages 1 --json
```

Movie remains the default. `SEERR_DISCOVERY_MEDIA_TYPES=movie,tv` selects both, or repeat `--media-type`. One `SEERR_DISCOVERY_MAX_REQUESTS` caps the entire invocation including retries; page caps apply per scope. Existing interval/timeout/TTL/cooldown/refresh batch settings are shared. Failed attempts rotate behind older attempts across media types. Sustained arrivals exceeding capacity can still grow the queue; there is no schedule or retention change.

## Tests, replay evidence and independent review

Evidence directory: `artifacts/seerr-exploration/2026-10-28-unified-discovery/` (private, ignored; original artifacts preserved).

| Evidence | Actual result |
| --- | --- |
| `focused-suite.txt` | **214 passed**; 79 original discovery, 69 unified, 66 exploration/Phase 2/schema-runner cases; no skips |
| `captured-movie-replay.json` | Captured 333/777 populations union **778**; first run 778 new/enriched; repeat 778 existing/cached, zero updates; both success, zero HTTP |
| `synthetic-unified-replay.json` | **5** canonical titles: one movie and four TV, including same-ID coexistence; TV one eligible, one provisional, two excluded; repeat five cached, zero new/updated; both success, zero HTTP |
| `tests/fixtures/seerr_movie_v1_record.json` | Pre-upgrade movie payload and canonical fingerprint golden fixture; populated migration + identical refresh preserves hash and change timestamp |
| Migration regressions | Empty and populated V1; collision after upgrade; seven drift variants; injected late failure rolls back even in autocommit; repeat upgrade rejected; V1 writer fails before HTTP/writes |
| Operational regressions | Source ID/endpoint mismatch fail closed; cache isolation; combined retries consume global budget; page caps; interrupted mixed run recovery; cross-media refresh fairness; GET endpoint allowlist |
| Independent review | Two P2 findings fixed and independently reproduced as resolved: explicit-special exclusion precedence; malformed TV collections preserving known values. No remaining blocking core/migration finding; final documentation consistency review completed and both clarifications incorporated; GO for review readiness |

The independent reviewer used read-only source inspection/pure local reproductions, with no DB/network writes. Parent isolated test/replay results provide the integration evidence; neither establishes live-client or production deployment validity.

## Modified files in this enhancement

- `api/services/seerr_client.py` — media selection, native TV sanitization/GET routing and coverage classification.
- `api/services/seerr_discovery.py` — typed scopes/routing, shared lifecycle/budget and eligibility accounting.
- `api/db/seerr_discovery.py` — typed inventory/repository, provenance/cache/refresh/recovery/reporting and fail-closed V2 guard.
- `api/db/migrations/optional/seerr_discovery/002_unified_titles.sql` — new optional forward upgrade.
- `scripts/sync_seerr_discovery.py` — repeatable media selection, TV sort handling and typed summaries.
- `deploy/seerr-discovery.env.example` — movie-only default selection, still disabled.
- `tests/test_seerr_discovery.py` — original regressions on unified schema, separate guarded V1 fixture.
- `tests/test_seerr_unified_discovery.py` — TV/identity/migration/operational regression coverage.
- `tests/fixtures/seerr_movie_v1_record.json` — synthetic pre-upgrade golden record.
- `tests/replay_seerr_discovery.py` — shared guarded fixture initialization, captured movie replay on V2.
- `tests/replay_seerr_unified_discovery.py` — new synthetic combined replay and auditable outcomes.
- `sql/seerr_discovery_visibility.sql` — V2 typed read-only visibility/eligibility queries.
- `docs/seerr-discovery-persistence.md` — updated V2 contract/commands.
- `docs/seerr-discovery-production-preflight.md` — explicit historical V1 versus uninstalled V2 boundary; prior evidence preserved.
- `docs/seerr-unified-discovery.md` — this findings/review report.
- `docs/seerr-unified-discovery-rollback.md` — separate nondestructive rollback and restore/downgrade risks.

Pre-existing Dockerfile/ignore changes and other exploratory/Phase 3 files are outside this enhancement. All **1,138 protected files** were hash-checked unchanged, including original 001/rollback, prior artifacts and production/model inputs. The real private configuration passed its actual loader with discovery disabled and movie-only default; the validated archive checksum matched. The V2 visibility SQL passed against the disposable fixture. Protected input verification and file hashes are recorded separately in `final-boundary-check.json` and `implementation-manifest.json` in the evidence directory.

## Remaining decisions and risks

Operator review must approve the conservative special-only classification and retention of contradictory/excluded detail records as audit evidence before rollout. These are documented coverage decisions, not acquisition rules. Unknown classification is provisional and must never be treated as approval for acquisition.

Other rollout gates are deployed Seerr version/response compatibility, separately reviewed DDL and lock window, preserved populated inventory/provenance, current recovery readiness and explicit first-run media/request limits. No full-library model or live service behavior is validated here. TV synthetic data cannot quantify real-world coverage or upstream special-classification reliability. Observation/detail snapshot history grows with runs; composite identity does not add retention. No target candidate count, acquisition automation, database authentication abstraction, production scheduling or model feature change is introduced.
