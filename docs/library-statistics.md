# Library statistics

`GET /api/agent/library/stats` and MCP `get_library_stats` return exact PostgreSQL
aggregates over the synced library. They retrieve no media objects and are
independent of search limits. Use them for “how many movies were added this year?”,
“new episodes this month”, and inventory breakdowns. Continue using `search_library`
for lists, actor/genre/title searches, or poster selection. The conversational agent
formats tables or prose; the API returns JSON.

## API and MCP contract

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `since` | Optional ISO 8601 datetime | null | Inclusive library addition bound |
| `until` | Optional ISO 8601 datetime | Current UTC time | Exclusive library addition bound |
| `media_type` | Optional enum | null | `movie`, `show`, `season`, `episode` |

Explicit offsets normalize to UTC; offset-free timestamps mean UTC, following the
existing watch-history API policy. Library storage
has a different representation: ingestion casts `TO_TIMESTAMP(epoch)` into a
timestamp without time zone using its PostgreSQL session timezone. The statistics
query converts each UTC boundary into the current database session timezone before
comparing the unmodified `added_at` column. `added_at_timezone` reports that zone;
the inspected database uses `America/Chicago`. This preserves potential date-index
use and accounts for seasonal UTC offsets. It assumes ingestion and API connections
use the same database timezone, as the current shared connection helper does.
Historical timezone changes require separate reconciliation. A naive timestamp
cannot distinguish the two occurrences of the repeated hour when daylight saving
time ends; exact instant-level queries with a boundary inside that hour are not
reliably supported by the stored data and return HTTP 400 instead of uncertain counts.
Calendar-year/month boundaries are unaffected. PostgreSQL timezone names must be
available through the system IANA timezone database; unrecognized names return 503.
No release dates, last-watched dates, or metadata-update dates are substituted.

With `since`, the predicate is `added_at >= since AND added_at < until`.
Without `since`, inventory spans all addition dates before `until`, **including
records with null addition timestamps**. A date-bounded query with `since` excludes
undated records because their addition period cannot be verified. Future-dated
records beyond `until` are excluded. The resolved boundaries appear in `period`.
`since >= until` returns HTTP 400, including when `until` defaults to now. Invalid
datetimes/categories return 422. Valid empty periods return zero counts.

REST requires the existing agent authentication: a mapped OAuth bearer token with
`plexintel.read`, an existing read-enabled REST service credential, or a verified
secure browser session. Library statistics use the same catalog permission as
`/api/agent/search`; they contain no user history and do not require read-all.
An MCP static token alone is not a REST credential. Do not create new credentials
or change scopes for this feature. REST errors use the existing sanitized incident
response; validation diagnostics remain available.

Year-to-date example (set `PLEXINTEL_AGENT_TOKEN` to an existing authorized REST
credential in your shell):

```bash
curl --fail-with-body -G \
  'http://localhost:8489/api/agent/library/stats' \
  -H "Authorization: Bearer ${PLEXINTEL_AGENT_TOKEN}" \
  --data-urlencode 'since=2026-01-01T00:00:00Z'
```

For all inventory, omit `since`. To verify a completed year, supply
`since=2025-01-01T00:00:00Z&until=2026-01-01T00:00:00Z`. Add `media_type=movie`
to select movies only. Filtered responses contain only that category in `counts`;
`total` always sums the returned counts. `unsupported_categories` distinguishes
unavailable types from a supported type with zero records. All four requested
types are supported by the current ingestion/schema, so this list is currently
empty. A future unsupported type must be listed there and omitted from `counts`,
never represented by a fabricated zero.

Illustrative fixture response, not production data:

```json
{
  "period": {"since": "2026-01-01T00:00:00Z", "until": "2027-01-01T00:00:00Z"},
  "media_type": null,
  "counts": {"movies": 125, "shows": 20, "seasons": 35, "episodes": 300},
  "total": 480,
  "unsupported_categories": [],
  "added_at_timezone": "UTC",
  "scope": "synced_library_inventory"
}
```

MCP schema: three optional inputs, `since` and `until` as date-time strings,
`media_type` as the four-value enum above; no required inputs. The tool is
registered with structured output and read-only annotations. For year-to-date,
the agent calls `get_library_stats(since="2026-01-01T00:00:00Z")` once. It must
report limitations instead of interpreting unsupported types as zeros.

The existing MCP server runs inside FastAPI and other tools call shared services
directly; there is no existing MCP REST client. This tool uses existing `httpx`
with an in-process ASGI transport to invoke the **same authenticated agent route**.
A private client application maps the already validated MCP context to the route's
principal dependency; the public application's authentication stays intact. It
neither exchanges credentials nor opens its own database connection. Invalid MCP
contexts are rejected before queries. API failures become MCP errors preserving
HTTP status and sanitized detail/incident information.

## Architecture discovery and counting semantics

- `public.library`: `rating_key` is the canonical ingestion/upsert identity;
  `media_type`, `added_at`, `parent_rating_key`, `show_rating_key`,
  `season_number`, and `episode_number` describe the entities and hierarchy.
  `added_at` is `timestamp without time zone`. `plex_guid` is ingested as metadata,
  but is not the existing identity used for library upserts.
- `fetch_tautulli_data.py` ingests each movie, show, season, and episode separately
  and backfills missing show/season headers through upstream metadata. Each row
  uses its own metadata's `added_at`, not its parent's timestamp. The model accepts
  both `show` and `series`; statistics include both in `shows`.
- `COUNT(DISTINCT rating_key)` for each category avoids duplicates under repeated
  identity records and avoids assuming constraints in every deployed schema.
  Counts are per Plex item, not per title/GUID. Distinct keys for copies in separate
  library sections remain separate entities under existing rules. There is no
  server/instance namespace in this table; combining independent Plex instances
  with colliding keys is unsupported. No new deduplication policy is introduced.
- Existing `library_catalog_v` and `media_enriched_v` enrich items with genres and
  people; recommendation show/season rollups aggregate scores, not addition events.
  Statistics query the base table directly without joins, object hydration, or limits.
- The actual `search_library` MCP/service default is **20**, not 50; REST search
  defaults to 20 and caps at 100. Recent-additions MCP/REST/service defaults to
  **50**, with REST capped at 200. Neither response's `count` is a library total.
- Read-only database inspection on October 25, 2026 found 1,850 movies, 291 shows,
  579 seasons, and 5,638 episodes, all with non-null addition timestamps; there were
  no duplicate rating keys. Existing indexes are `library_pkey` (unique),
  `library_show_rating_key_idx`, and `idx_library_plex_guid`.
- Read-only `EXPLAIN (ANALYZE, BUFFERS)` for year-to-date scanned 8,358 rows,
  matched 1,680, and completed in about 9.5 ms. A sequential scan is adequate at
  this size; no new index is justified. No schema, migration, role, dependency, or
  infrastructure changes are needed.

These counts describe **records in the synced application library**, not an
authoritative history of all addition events. The incremental ingestion code adds
and updates records; it does not reconcile Plex deletions. Removed content may
therefore remain in the database. Counts must not be presented as confirmed live
Plex inventory until deletion reconciliation exists. Missing parent records or
null timestamps are source completeness limitations, not inferred entities/dates.
The minimal follow-up for authoritative current inventory is upstream deletion
reconciliation (or an authoritative active marker); for incomplete headers/dates,
repair metadata ingestion. Neither change is included here. No historical event
counts can be reconstructed reliably from this snapshot table.

## Validation

```bash
.venv/bin/python -m pytest -q tests/test_library_stats.py
```

The six SQL integration tests are opt-in and require an **empty disposable local
PostgreSQL cluster** whose Unix socket directory starts with
`/tmp/plexintel-stats-pg`. They create and drop `public.library` there; never point
them at an application database. Example using installed PostgreSQL 16 binaries:

```bash
stats_test_root=$(mktemp -d /tmp/plexintel-stats-pg.XXXXXX)
/usr/lib/postgresql/16/bin/initdb -D "$stats_test_root/data" --auth=trust --no-locale
/usr/lib/postgresql/16/bin/pg_ctl -D "$stats_test_root/data" \
  -l "$stats_test_root/server.log" -o "-h '' -k $stats_test_root -p 55439" start
PLEXINTEL_STATS_TEST_DSN="dbname=postgres host=$stats_test_root port=55439" \
  .venv/bin/python -m pytest -q tests/test_library_stats.py
/usr/lib/postgresql/16/bin/pg_ctl -D "$stats_test_root/data" -m fast stop
```

Fixtures include 125 movies, 20 shows, 35 seasons, and 300 episodes in the interval,
older parents, both show spellings, duplicate identities, boundary timestamps, and
undated rows. Tests also cover parameter validation, authorization, read-only SQL,
connection cleanup, MCP discovery, REST invocation, identity mapping, output, and
sanitized failures. Existing MCP transport/auth suites cover bearer validation at
the outer MCP boundary.

## Manual deployment

API and MCP live in the same backend process. `Dockerfile` copies `api`, including
both changes; no separate MCP image/deployment is needed. The Compose backend also
bind-mounts the repository. After review, the operator can run from the repository:

```bash
docker compose build backend
docker compose up -d --no-deps backend
```

These commands rebuild/recreate the backend and are documented for manual use;
they have not been run as part of this implementation. No migration is required.
The existing bootstrap may initialize schema if its normal schema check fails;
verify the existing deployment/database configuration before restarting as usual.
Refresh MCP tool discovery/reconnect ChatGPT or OpenWebUI after deployment. Verify
the authenticated curl example and MCP `tools/list`, then ask a year-to-date count
question. Deployment and live agent selection remain unverified.

Read-only verification against the configured application database at
`2026-10-25T14:08:37.405991Z` returned this year-to-date response (a synced database
snapshot, subject to the inventory limitations above):

```json
{
  "period": {"since": "2026-01-01T00:00:00Z", "until": "2026-10-25T14:08:37.405991Z"},
  "media_type": null,
  "counts": {"movies": 146, "shows": 54, "seasons": 130, "episodes": 1350},
  "total": 1680,
  "unsupported_categories": [],
  "added_at_timezone": "America/Chicago",
  "scope": "synced_library_inventory"
}
```

Final focused validation used the existing `plexenv` environment (`.venv` lacked
the existing `itsdangerous` authentication dependency). Authentication settings
were isolated from local deployment configuration for the test process:

```bash
PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='' \
PLEXINTEL_AGENT_SERVICE_SCOPES='plexintel.read' \
PLEXINTEL_STATS_TEST_DSN='dbname=postgres host=/tmp/plexintel-stats-pg port=55439' \
  plexenv/bin/python -m pytest -q \
  tests/test_library_stats.py tests/test_agent_tools_routes.py \
  tests/test_agent_tool_service.py tests/test_agent_rest_auth.py \
  tests/test_mcp_server.py tests/test_mcp_auth.py \
  tests/test_mcp_oauth_metadata.py tests/test_watch_history_compact.py
```

Result: **129 passed, 47 subtests passed**. `git diff --check` and compilation of
the changed Python files also passed. Ruff was unavailable in the installed
Python environments. The entire repository suite and deployed ChatGPT/OpenWebUI
behavior were not tested. The temporary PostgreSQL instance was stopped after
validation; no application services were rebuilt, restarted, or deployed.
