# Watch-history scope and viewing metrics

PlexIntel supplies the watch-history rules in MCP initialization instructions and in
the `list_users`, `get_watch_history`, and `search_library` tool descriptions.
The Open WebUI deterministic pipeline implements the same workflow in code.

## User and server scope

For personal or named-user history, resolve one Plex username first. Named-user
resolution uses usernames and friendly names; first-person pipeline requests use
the Open WebUI identity or configured aliases. Unknown or ambiguous users require
clarification. Pass that resolved username explicitly.

For server-wide questions (everyone's history, title viewers, active users, most
watched, most viewers, or most plays), retrieve all users, fetch history separately
for every username using the same SQL time bounds, and merge it before title filtering
or aggregation. The pipeline verifies time bounds again after merging.
A single user's history cannot establish another user's inactivity.

MCP permissions still apply: mapped non-admin users cannot inspect another user's
history. An unavailable or denied query means incomplete coverage, not no activity.
The pipeline validates the username in both the response envelope and every row.
It marks failed, mismatched, or truncated responses as incomplete and avoids
definitive absence claims. Older API responses without pagination are accepted
only if they contain fewer rows than the requested limit.

## Existing API pagination

These are additive changes to existing endpoints, not a separate server-wide API.

| Endpoint / MCP tool | Page size | Pagination |
| --- | --- | --- |
| `GET /api/agent/users` / `list_users` | `limit` 1–1000, default 200 | `offset` starts at 0 |
| `GET /api/agent/watch-history` / `get_watch_history` | `limit` 1–200, default 50 | `offset` starts at 0 |

Both responses include `next_offset`: use that value for the next request with
the same filters until it is null. `count` is the number of records on the current
page. History sorts by descending timestamp and watch ID, with unknown times last.

For example, first call `list_users(limit=200, offset=0)` and follow its pages.
For each returned username, call
`get_watch_history(user="username", engaged_only=false, limit=50, offset=0)`
and follow its pages. Supply the same `since` and `until` on every page and for every
user when a time window is requested. Merge the results, then summarize.

An omitted MCP `user` still resolves only to the authenticated user for backwards
compatibility. It never means everyone. The REST endpoint retains its existing
all-user behavior when `user` is omitted, but the pipeline always supplies a username.

Offset pagination is not a database snapshot: playback added during retrieval may
shift page boundaries. The pipeline deduplicates repeated watch IDs per user.
All history means all records available in PlexIntel's synced history, not activity
missing from the upstream sync.

## Compact output and SQL time filtering

Watch history is compact by default for both personal and global REST queries and
for MCP calls. Rows contain playback ID, username/friendly name, rating key, UTC
watch time, played/media duration, completion/engagement, media type, title, show
title, and season/episode numbers. The default SQL projection does not select
summary, rating, year, genres, actors, or directors; these keys are absent from
compact JSON rather than emitted as empty placeholders.

Pass `include_metadata=true` only when those extra fields are needed. The page
limit remains 200 even with full enrichment; the default is 50. The pipeline requests
compact pages of 50 and applies display limits separately.

`since` (inclusive) and `until` (exclusive) accept ISO timestamps. They become
parameterized `watched_at >= since` and `watched_at < until` SQL predicates before
`ORDER BY`, `LIMIT`, and `OFFSET`, for both per-user and global queries. Reversed
or empty ranges are rejected. Explicit timezone offsets are converted to UTC;
offset-free API bounds mean UTC. Tautulli stores naive UTC timestamps in the
database, and responses label those timestamps as UTC.

Example: `/api/agent/watch-history?since=2026-09-01T00:00:00Z&until=2026-10-01T00:00:00Z&limit=50`
returns a compact page across users in that UTC interval. Add
`&user=alice` to scope the REST request and `&include_metadata=true` for enrichment.

## Partial plays, dates, and rankings

- Partial plays remain included unless engaged/completed viewing is explicitly requested.
- Engaged means at least 50% completion. The pipeline treats completed-only as
  100% and additionally checks `percent_complete`; engaged does not imply completed.
- Title viewer lookups match title, series title, or explicit `rating_key`, grouping
  repeat playback by username.
- Most watched / most plays rank playback records. Most viewers ranks distinct
  usernames. Show rankings combine episodes by `show_title`.
- Highest rated uses metadata via `search_library(sort_by="rating", sort_dir="desc")`
  or the REST search endpoint with those parameters. Missing ratings sort last.
  Ambiguous “popular” pipeline requests explain the two viewing measures.
- The pipeline supports today, yesterday, this/last week or month, last/past N
  hours/days/weeks, and ISO date windows: on, since, after, before, or between/from
  `YYYY-MM-DD` dates. Since/before/until/from ranges also accept ISO timestamps
  with optional timezone offsets. Date ranges include the final calendar day; internal end
  bounds are exclusive. Weeks start Monday. SQL excludes unknown timestamps
  from date-filtered results.
- `WATCH_HISTORY_TIMEZONE` (environment variable or pipeline valve) defaults to
  `America/Chicago` and controls calendar windows. Stored naive timestamps are
  interpreted as UTC, independently of that setting. Timestamps with offsets preserve them.
- Display limits apply after retrieval, filtering, and aggregation. Viewer lists
  include every matching username.

## Activating updates

Restart the PlexIntel API process to load the new MCP instructions and schemas,
then reconnect or refresh tool discovery in MCP clients. Update/reload the Open
WebUI pipeline file to version 0.1.9. Install the API changes with the pipeline so
large histories can be paginated.

The MCP rules guide the connected model's tool use; the deterministic pipeline
executes the per-user workflow directly.
