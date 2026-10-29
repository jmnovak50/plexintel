# Canonical Seerr discovery persistence

**Current production status — October 28, 2026, 20:51 CDT:** Gate A completed: migration **002 committed**, strict V2 verification **PASS**, inventory empty, discovery **disabled**. See [Gate A verification](seerr-discovery-gate-a-verification.md). Earlier V1/preflight statements below are historical; do not rerun 001/002 or proceed to Gate B without separate authorization.

Phase 3 adds a discovery inventory alongside PlexIntel's existing library. It implements discovery and metadata persistence only. It contains no community-engagement filters, embeddings, model calls, acquisition requests, Radarr/Sonarr changes, UI, pipeline stages or scheduling. TV-only original-premiere coverage/classification is explicitly audited; it is not engagement scoring. The service defaults to disabled. The movie-only V1 installation is recorded historically in the production preflight. This unified V2 enhancement has not been installed or run in production. The current writer and summary require V2; they fail closed against V1. See [unified design/review evidence](seerr-unified-discovery.md) and the [V2 rollback strategy](seerr-unified-discovery-rollback.md).

## Components and boundaries

- `api/services/seerr_client.py`: instance configuration, bounded GET-only transport and source sanitization.
- `api/services/seerr_discovery.py`: query windows, pagination integrity, separate membership/enrichment phases and refresh orchestration.
- `api/db/seerr_discovery.py`: discovery-only PostgreSQL persistence and read-only inventory summary.
- `scripts/sync_seerr_discovery.py`: explicit preview/execution/summary CLI using the current Python interpreter.
- `api/db/migrations/optional/seerr_discovery/001_initial.sql`: immutable original movie-only baseline.
- `api/db/migrations/optional/seerr_discovery/002_unified_titles.sql`: separately approved, atomic V1-to-V2 forward upgrade; never applied automatically.
- `api/db/migrations/optional/seerr_discovery/rollback.sql`: destructive V1-only removal; incompatible with V2. Do not use after 002.
- `deploy/seerr-discovery.env.example`: inactive configuration template.
- `sql/seerr_discovery_visibility.sql`: read-only run, inventory, refresh and membership examples.

The implementation reuses `requests`, `python-dotenv`, `psycopg2`, `api.db.connection.connect_db`, the owner-only private-file reader and the existing advisory-lock namespace. Runtime dependencies already appear in `requirements.runtime.txt`. It does not import the exploration scripts, app-settings bootstrap, application startup or model modules. Exploration code/results remain separate inputs; production-capable discovery is not dependent on them.

The distribution Dockerfile already copies `api/`, including the optional migrations; it now also packages this explicit CLI and inactive configuration template. Startup behavior is unchanged. Private exploration outputs and legacy credentials are excluded from the build context. No image was built or run for this phase; implementation and validation use direct Python.

**The existing startup migration runner executes every top-level `api/db/migrations/*.sql`.** These opt-in migration files are nested outside that glob. Neither the shared runner nor application startup was changed; installing this code cannot automatically apply the new schema on restart. The CLI never creates schema.

## Relational model

| Table | Identity and purpose |
| --- | --- |
| `seerr_discovery_runs` | UUID per explicit execution, UTC start/completion, operation (`discover`/`enrich`), status (`running`/`success`/`partial`/`failed`), source hash, reproducible query parameters, page diagnostics, unique-title counts, errors and warnings |
| `seerr_discovered_titles` | Composite `(media_type, tmdb_id)` primary key, exact `movie`/`tv` namespace and positive bigint ID; structured metadata, first/last discovery timestamps, first discovery run, last enrichment/attempt, fingerprint/change timestamp, field-presence state and sanitized JSONB source observations |
| `seerr_discovery_observations` | One membership per `(run_id, media_type, tmdb_id, scope_key)` with typed canonical FK, query/scope/kind, nullable TV `eligibility` state/reason, observation time, discovery source fingerprint, detail snapshot and original fetch time, enrichment outcome, prior/current metadata fingerprints, changed fields and first-insertion flag |

Titles, original titles, synopses and language use text; primary/discovery dates use `date`; runtime uses nullable positive integer minutes; popularity/rating use floating point and vote count uses bigint. TV `tv_metadata` holds native series type, episode-runtime array, creators, season numbers/counts and `season_premieres` (native seasonNumber/airDate plus per-date presence state), episode count, production flag and series status, without episode persistence. `premiere_date` means primary movie release or original TV first-air date; `discovery_premiere_date` separately retains the summary date. Neither establishes digital availability. Genres, cast/crew, companies/countries and country-specific release events use structured JSONB arrays; director names use `text[]`. Status codes remain integers, including future unrecognized codes, with separate media/request field states in JSONB. All operational timestamps are `timestamptz`; the service supplies timezone-aware UTC values.

Indexes cover latest runs, first/last discovery, enrichment freshness, media/language/premiere date and typed title/scope observation lookups. Unique constraints and FKs protect canonical identity and per-run/scope membership. No library table is copied or altered, and there is no assumed TMDB ID = Plex rating_key relationship. The inventory retains every discovered title even after it stops appearing in search. Multiple scopes and overlapping windows retain independent memberships while sharing one canonical typed title. Movie and TV ID collisions coexist; every lookup, upsert, refresh, snapshot and observation uses both identity components.

## Single-instance source identity

Set `SEERR_DISCOVERY_SOURCE_ID` to a permanent nonsecret label or UUID for this Seerr installation before an approved first writer execution. Keep it stable across refreshes and API-key rotation. It is independent of credentials. Missing/invalid identity fails before connecting the writer CLI. Preview and read-only summary can operate without it.

The first run in an empty inventory persists the binding in existing `seerr_discovery_runs.parameters.source_id` plus the existing `source_key` (SHA-256 of the normalized configured endpoint). `/api/v1` and trailing slash variants resolve to the same endpoint. The exclusive discovery lock protects validation and run insertion. Every subsequent writer checks all persisted runs and canonical enrichment source keys before recovery or any writes/network requests. A different ID or endpoint fails with `discovery_source_identity_mismatch`; missing legacy identity or an enriched row without provenance fails with `discovery_source_identity_ambiguous`. Even an empty/interrupted first run establishes the binding. The source-binding guard itself adds no new identity storage, automatic adoption, rebind or multi-instance support.

Do not reuse an ID for a replacement Seerr installation, including one behind the same URL. This is an operator-assigned identity: Seerr movie/discovery responses do not attest server identity, and a transparent replacement using the same URL and configured ID cannot be detected. A legitimate endpoint move also fails closed; operator verification and a separately reviewed migration/rebind procedure are required. Existing pre-fix inventory must be investigated explicitly, never relabeled automatically. Use a separately provisioned discovery database for another source. Do not edit run history to bypass this guard.

## Discovery coverage

Default coverage is UTC today minus 14 days through UTC today plus 90 days, split into inclusive 14-day windows. Adjacent configured windows do not duplicate a boundary date. Repeated executions naturally overlap and are idempotent for canonical identity; each execution deliberately adds historical observations. Defaults are operational choices, not a claim to cover all new TMDB records. A film first cataloged today with an older or much later primary date can be missed by that window. Configure a broader horizon or perform explicit historical/forward sweeps as needed; no sweep schedule is installed.

`--start`/`--end` override the coverage dates; `--as-of` fixes the UTC calendar anchor for relative windows. `--language` is repeatable (`all`, `configured`, a language code, or an upstream-supported pipe-separated original-language selection). `configured` omits the API language parameter; `all` asks Seerr to remove its original-language restriction. Upstream account/region preferences can still affect results and are not snapshotted by this service. Parameters and a source-origin hash are stored; replay also requires the matching external instance/account configuration. No credentials or raw private base URL are stored in run parameters.

For installations wanting the union of both observations, configure `SEERR_DISCOVERY_LANGUAGES=all,configured`. No strict superset relationship is assumed. Scope keys identify media type, name and query parameters, including date window/sort; title counts are deduplicated across all scopes, while observations retain each query's membership. Movies retain the existing discovery membership behavior. TV queries use `firstAirDateGte/Lte` and local original-premiere validation. Returning-season/episode dates do not qualify. Explicit specials and specials-only season-0 listings are excluded; uncertain detail classification is provisional. Eligibility requires a valid original premiere inside the window and Season 1 with a valid matching airDate. Missing/null/malformed/empty seasons or Season-2-only evidence remain provisional even with a nonempty series type. Conflicting original/season dates or summary/detail dates remain provisional with an explicit reason. Summary exclusions are in run pagination; confirmed ineligible detail evidence remains in inventory as excluded, while contradictions remain provisional. Missing/malformed summary dates are persisted and enriched, never skipped solely for incompleteness; `pagination.unresolved` records the original diagnostic. Retrieval completeness and eligibility certainty are separate: a successfully fetched provisional title can belong to a successful run. Inventory size therefore includes audit evidence, not just eligible TV candidates. No runtime, language, genre, popularity, votes, metadata completeness, digital-availability or release-readiness engagement filter is applied. Search-window selection is discovery coverage, not acquisition readiness.

## Transactions, integrity and recovery

One dedicated connection per execution holds the session advisory lock `(184725,30)` across commits. A concurrent execution fails with exit 75. Before recovery, run insertion or HTTP, a catalog guard validates the exact V2 ordinary-table, 68-column type/default/nullability/identity and 24-integrity-constraint contract, key-index validity, sequence dependency/generation, active FK triggers and origin replication mode. It rejects RLS, user triggers, unexpected integrity constraints or standalone unique indexes that could undermine typed identity; harmless nonunique reporting indexes are allowed. V1, mixed and partial schemas fail closed without schema repair. The guard also runs for read-only summary and preserves the caller search path. A new `running` run record is committed before collection. Each successfully fetched page persists its valid TMDB memberships in one transaction, including summary-only titles. The service closes that transaction before further network IO. It deduplicates within a query and later enriches the union once per `(media_type, tmdb_id)`. Combined operations share one client, hard HTTP-attempt budget (including retries), refresh batch, source binding and run; separate media loops cannot multiply limits.

Each enrichment success/failure commits separately. A failed page transaction rolls back the whole page; previously committed pages remain visible under a non-successful run. A failed detail call cannot erase membership or prior successful metadata. A terminal run status is committed only after collection/enrichment accounting. `success` requires both discovery and enrichment completion; `partial` means candidates were persisted but one or both operations are incomplete; `failed` means execution could not complete and no candidates were recorded for that run. A valid empty result is successful and never deletes previous inventory.

Page metrics retain the first reported total/page count, per-page reports, observed raw and unique counts, duplicates, invalid identities, failed pages, limits and drift. A run is incomplete if totals change, pages are missing/capped, duplicates or invalid identities appear, or observed unique totals disagree. Transient errors are retried; later pages can still be collected after a nonfatal page failure. Authentication errors, redirects, exhausted rate limits and request-budget exhaustion stop the affected network operation. No missing title is treated as a deletion.

An interrupted process leaves a `running` record, which cannot masquerade as success. After the next explicit writer obtains the exclusive lock, it reconstructs durable counts for abandoned runs, marks them `partial`/`failed` with an interruption diagnostic, and preserves their observations before starting a new run. It does not silently resume an old run ID. If the database becomes unavailable during finalization, the run can remain `running` until that recovery. Inspect it with the summary/queries.

These checks establish observed accounting, not an atomic TMDB snapshot. Live per-query caches, updates and equal-count substitutions can still produce nonidentical populations without detectable count drift. Every run records that limitation. No arbitrary candidate-count target is imposed; page/request budgets produce explicit partial runs.

## Metadata and cache semantics

Discovery and detail membership are separate. New rows are seeded from discovery summaries and persist even with missing title/synopsis/runtime or a failed detail GET. General omitted detail fields retain previous structured values; explicit null clears them, except movie release collections and native TV arrays (`episodeRunTime`, `createdBy`, `seasons`): omitted/null/invalid collections preserve last-known values, while complete explicit empty arrays clear them. Movie nested release semantics are described below. TV presence states record unknown separately from retained canonical values. `tv_metadata.season_premieres` and sanitized discovery/detail observations retain season dates with their source field states; observation `detail_observed_at` and source-key provenance identify origin and fetch age. Omitted/null/invalid season collections preserve prior canonical dates; true `[]` clears them. Individual missing/null/invalid dates remain uncertain in the new snapshot and never establish eligibility. Season dates are supporting series-premiere evidence, without season persistence, episode calls or ongoing-series monitoring. `field_states` reports omission, null, value or invalid source shape; runtime zero is recorded as `zero_unknown`. A retained field marked omitted may predate `last_enriched_at`, which timestamps the latest successful *detail response*, not each individual field. Source/detail snapshots in observations permit historical inspection.

Release collections have separate semantics: omitted/null `releases`, omitted/null `results`, and omitted/null or malformed country `release_dates` are unknown and preserve the entire previous canonical event collection. Initial unknown events are SQL NULL; a known-empty collection is JSONB `[]`. A complete `results: []`, or a complete list of countries whose `release_dates` arrays are explicitly empty, may clear known events. This authority applies to Seerr detail's complete release collection, not to a partial/patch/paginated source. If any country collection is unknown, the mapper conservatively preserves all prior events, including when other countries are populated. Fully specified populated collections replace events without appending duplicates. Nested presence annotations survive sanitization; `field_states.release_events` reports `omitted`, `null`, `results_omitted`, `results_null`, `results_invalid`, `release_dates_omitted`, `release_dates_null`, `release_dates_invalid`, `empty` or `value`. Retained events can predate the latest response. A repeated identical refresh preserves the fingerprint/change timestamp; new run observations still append by design. Primary release date never establishes digital availability.

Discovery-only genre IDs populate the structured genre array with `ids_only` provenance, so known IDs remain queryable even if detail enrichment fails before names become available.

Canonical structured metadata uses the last successful detail response when one exists. Later discovery summaries remain in per-run observations and `source_metadata.discovery`; they do not overwrite richer cached details until enrichment refresh. `discovery_premiere_date` separately retains discovery's date, including disagreements with detail's primary date. Successful source metadata changes advance `metadata_updated_at`; retry/cache bookkeeping does not. `metadata_fingerprint` hashes canonical metadata, presence states and the sanitized detail representation. `changed_fields` names changed structured fields or `source_metadata` for additional source changes. Discovery-only source changes can be inspected through observation fingerprints without pretending a fresh detail call occurred.

Media status omission, explicit null, existing status `1` (Seerr UNKNOWN), other known codes and retrieval failure remain distinguishable. A missing/null association does not mean never requested. Request summaries preserve status/is4k and, for TV, seasonNumber/status only; source IDs, requester identities, account details, internal URLs, library identifiers and service IDs are excluded. Service/library association **presence** can be retained. Processing/approved is not available; an external association is not proof of actual Radarr monitoring. Standard and 4K codes/request scopes remain separate. No Radarr API is called.

The durable metadata cache is the canonical database record, not a file cache. Discovery pages are always fetched. Default metadata freshness is 24 hours; failed attempts retry after a one-hour cooldown. A cache hit attaches the prior sanitized detail snapshot and its original enrichment timestamp to the new run without advancing `last_enriched_at`. Failed refreshes preserve prior successful data and expose `enrichment_status=failed`. Cooldown deferrals keep a run partial rather than claiming new enrichment succeeded.

`--refresh` bypasses freshness/cooldown; `SEERR_DISCOVERY_CACHE_ENABLED=false` also forces detail fetches. A source ID or endpoint change rejects writer execution before any discovery recovery, run insertion or HTTP call; it cannot be used to refresh the existing inventory from another instance. API-credential/permission changes at the same origin require explicit `--refresh`, because authentication data is intentionally not retained as a database cache key. A cached request/media state is an observation with an age, not authorization for a future acquisition action.

Refresh bypasses PlexIntel's cache only; it does not clear Seerr/TMDB caches. `last_enriched_at` records when PlexIntel received a successful response, not when TMDB last changed every field.

`--execute --enrich-due` refreshes already discovered inventory even when its titles no longer appear in current discovery windows. It records `refresh` observations and leaves first/last **discovery** timestamps unchanged. A configurable batch size bounds work. Eligible records are ordered by `last_enrichment_attempt_at NULLS FIRST, media_type, tmdb_id`, so unattempted records precede retries and repeatedly failing records rotate behind older attempts. Failed-attempt cooldown and freshness eligibility remain in effect. This prevents a permanent low-ID failure backlog from monopolizing every batch; sustained arrivals above processing capacity can still create a backlog. No scheduled refresh job is enabled.

## Configuration

Copy `deploy/seerr-discovery.env.example` into an operator-managed owner-only file when preparing an approved rollout. Default location is `~/.config/plexintel/seerr-discovery.env`; override with `SEERR_DISCOVERY_CREDENTIALS_FILE` or `--credentials-file`. Environment values override file values. The CLI loads the repository `.env` without replacing exported environment values, preserving existing `DATABASE_URL`/`DB_*` connection conventions. The discovery credential file configures Seerr only; PostgreSQL credentials remain in those existing connection settings.

Use `SEERR_URL` and `SEERR_API_KEY`, or `SEERR_API_KEY_FILE` for an owner-only token file. Existing `SEER_URL`/`SEER_API_KEY` spellings are accepted. Owner-only credential files must be regular nonsymlink files with no group/other access. The earlier `.seer_creds` file may require an operator-managed private copy; this implementation never changes that existing file. Never pass a token as a CLI argument. `enabled=false` prevents writer connection/run creation; an explicit `--execute` flag is also required for writes.

| Setting (`SEERR_DISCOVERY_` prefix) | Default |
| --- | --- |
| `ENABLED` | false |
| `SOURCE_ID` | unset; required for writes; permanent nonsecret instance label or UUID |
| `MEDIA_TYPES` | movie; CSV `movie,tv` for an explicitly combined operation |
| `LANGUAGES` | all |
| `LOOKBACK_DAYS`, `LOOKAHEAD_DAYS`, `WINDOW_DAYS` | 14, 90, 14 |
| `SORT` | primary_release_date.asc |
| `MAX_PAGES` | 500 per query; incomplete if capped |
| `MAX_REQUESTS` | 10000 per CLI/client execution, including retries |
| `RETRIES` | 2 retries after initial request |
| `TIMEOUT` | 25 seconds per request |
| `INTERVAL` | 0.3 seconds minimum between attempt starts |
| `MAX_RETRY_AFTER` | 60 seconds; longer upstream waits terminate work rather than violating Retry-After |
| `METADATA_TTL_HOURS` | 24 |
| `FAILED_RETRY_HOURS` | 1 |
| `CACHE_ENABLED` | true |
| `REFRESH_BATCH_SIZE` | 1000 |

There are no community-engagement eligibility settings. `--media-type movie` / `--media-type tv` are repeatable and override the configuration selection. Primary-release date sorts translate to first-air-date sorts for TV and vice versa; popularity/vote sorts are shared. `--enrich-due` selects only configured media types and never queries season/episode endpoints. A refresh is not a new-series discovery event. Configuration validation rejects unsupported sorts, invalid ranges, nonfinite timing values, malformed URLs and header credentials. Structured logs contain UTC time, run/scope identifiers, counts and fixed error categories; no raw exceptions, URLs, credentials or requester objects are logged. No existing pipeline logs or schedules are rewritten.

## Execution and rollout gates

Use the deployment's existing Python interpreter with runtime dependencies installed. This checkout's `.venv` and `plexenv` were inspected; the CLI itself chooses neither and works through `sys.executable`. Commands run from the repository root and require no Docker.

**Illustrative only; this task does not authorize running a live preview.** A future approved bounded GET preview never connects to PostgreSQL, but does issue live Seerr GETs:

```bash
python scripts/sync_seerr_discovery.py --dry-run \
  --credentials-file /path/to/private/seerr-discovery.env \
  --media-type movie --media-type tv \
  --start 2026-10-26 --end 2026-11-01 --language all --max-pages 1 --json
```

The page cap intentionally yields a partial result/exit 2 when more pages exist. Remove the cap for complete preview. New/existing/updated counts are unknown in dry-run because it does not read the database. An inventory summary is a separate read-only operation.

**GO requires explicit approval before any production migration or writer execution.** First validate on an isolated database. Configure PostgreSQL/libpq connection settings for the approved target separately (for example `PGSERVICE` or `PGHOST`/`PGDATABASE`/`PGUSER` plus an owner-only `PGPASSFILE`), rather than embedding passwords in command arguments. For an existing verified V1 installation, after separate upgrade approval only (not executed by this enhancement):

```bash
psql -X -v ON_ERROR_STOP=1 --single-transaction \
  -f api/db/migrations/optional/seerr_discovery/002_unified_titles.sql

python scripts/sync_seerr_discovery.py --summary --json
# Set SEERR_DISCOVERY_ENABLED=true only in the approved instance configuration.
python scripts/sync_seerr_discovery.py --execute \
  --start 2026-10-26 --end 2026-11-01 --language all --language configured --json
python scripts/sync_seerr_discovery.py --summary --json
```

For a fresh isolated installation only, apply immutable 001 first, then 002. Do not rerun 001 on a V2 installation: its V1 `IF NOT EXISTS` statements are not a schema-version manager. The V2 upgrade rejects repeated invocation, drift and unexpected dependencies; review its exact definitions and PostgreSQL version before authorizing production DDL.

The migration owner must be the app writer or grant it DML on just these three tables and usage on the observation identity sequence. The CLI uses the existing connector; it does not create/rotate users or credentials. A read-only reporting role needs only SELECT on these tables. Application startup does not grant permissions or apply this optional schema.

For an existing separately owned app role, an approved operator can use psql identifier substitution:

```sql
\set app_role 'your_existing_plexintel_role'
GRANT SELECT,INSERT,UPDATE ON public.seerr_discovery_runs,
  public.seerr_discovered_titles,public.seerr_discovery_observations TO :"app_role";
GRANT USAGE,SELECT ON SEQUENCE public.seerr_discovery_observations_observation_id_seq TO :"app_role";
```

For an approved explicit metadata refresh later:

```bash
python scripts/sync_seerr_discovery.py --execute --enrich-due --json
python scripts/sync_seerr_discovery.py --execute --enrich-due --refresh --json
```

Exit codes: 0 successful preview/execution/summary; 2 incomplete/failed collected execution; 1 configuration/connection failure; 75 concurrent writer lock. A known-empty discovery result is successful. Missing schema, missing privileges or a lost connection must be reviewed rather than invoking the application's broad schema bootstrap. Repeated runs safely append observations and never delete inventory.

## Rollback

Use the [separate V2 rollback strategy](seerr-unified-discovery-rollback.md). Disable discovery and retain the unified schema/data for nondestructive operational rollback. The original `rollback.sql` is V1-only; it must not run against V2. No automatic downgrade, TV deletion or historical rewrite is provided. A full database restore loses unrelated later writes and requires separate authorization.

## Validation and sample evidence

`tests/test_seerr_discovery.py` uses fake Seerr responses plus a separately configured, TCP-disabled PostgreSQL fixture. Database tests refuse any name except `plexintel_seerr_fixture`, require a Unix socket under `/tmp/plexintel-seerr-fixture.*`, and verify the server's data directory and disabled TCP before any migration/rollback. Unit tests can run without a database; integration tests then report skips.

To prepare a disposable cluster as an unprivileged user with installed PostgreSQL server binaries (choose another installed server directory if `pg_config` points elsewhere):

```bash
seerr_pg_bin="$(pg_config --bindir)"
seerr_fixture_root="$(mktemp -d /tmp/plexintel-seerr-fixture.XXXXXX)"
"$seerr_pg_bin/initdb" -D "$seerr_fixture_root/data" -A trust --no-locale --encoding=UTF8
"$seerr_pg_bin/pg_ctl" -D "$seerr_fixture_root/data" -l "$seerr_fixture_root/postgres.log" \
  -o "-c listen_addresses='' -c unix_socket_directories='$seerr_fixture_root' -p 55483" -w start
"$seerr_pg_bin/createdb" --host="$seerr_fixture_root" --port=55483 plexintel_seerr_fixture
export SEERR_DISCOVERY_TEST_DSN="host=$seerr_fixture_root port=55483 dbname=plexintel_seerr_fixture"
python -m pytest -q tests/test_seerr_discovery.py tests/test_seerr_unified_discovery.py
python -m tests.replay_seerr_discovery
python -m tests.replay_seerr_unified_discovery
"$seerr_pg_bin/pg_ctl" -D "$seerr_fixture_root/data" -m fast -w stop
```

The private temporary directory confines trust authentication to this disposable Unix socket. These commands do not connect to the existing PostgreSQL service.

```bash
python -m pytest -q tests/test_seerr_discovery.py
# After explicitly preparing the disposable cluster described above:
SEERR_DISCOVERY_TEST_DSN='host=/tmp/plexintel-seerr-fixture.XXX port=55483 dbname=plexintel_seerr_fixture' \
  python -m pytest -q tests/test_seerr_discovery.py

# Optional captured-data replay; its guard permits only that same disposable cluster.
SEERR_DISCOVERY_TEST_DSN='host=/tmp/plexintel-seerr-fixture.XXX port=55483 dbname=plexintel_seerr_fixture' \
  python -m tests.replay_seerr_discovery
```

The isolated replay reads the original captured 333/777 populations and detail cache without altering them, unions memberships and executes twice with **zero HTTP calls**. `artifacts/seerr-exploration/2026-10-28-phase3/captured-replay-summary.json` contains its actual run summaries. Its data/time/source are fixture evidence, not production coverage or deployment validation. Normalized live reference validation, when available, is separately labeled. Preserve the original Phase 1/2 artifacts; no backfill, model job, production migration, writer execution or schedule activation is included in this phase.

Unified validation and replay evidence is recorded in [the V2 findings report](seerr-unified-discovery.md). The current replay prepares both migrations only in the guarded disposable database. Legacy captured movie JSON and legacy movie hash projection remain compatible; scope keys on future runs include media type, while old run JSON/scope keys are preserved verbatim. Generic `titles/new_titles/existing_titles/updated_titles` and `by_media_type` describe combined runs; legacy `movies/new_movies/existing_movies/updated_movies` remain movie-only. Historical run counts are never rewritten into the new format.

Current readiness corrections, regression results and operational conditions are recorded in [the remediation report](seerr-discovery-readiness-remediation.md).
