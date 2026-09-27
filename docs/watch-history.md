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
for every username, and merge it before applying dates, titles, or aggregation.
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
| `GET /api/agent/watch-history` / `get_watch_history` | `limit` 1–200, default 200 | `offset` starts at 0 |

Both responses include `next_offset`: use that value for the next request with
the same filters until it is null. `count` is the number of records on the current
page. History sorts by descending timestamp and watch ID, with unknown times last.

For example, first call `list_users(limit=200, offset=0)` and follow its pages.
For each returned username, call
`get_watch_history(user="username", engaged_only=false, limit=200, offset=0)`
and follow its pages. Merge the results, then filter and summarize.

An omitted MCP `user` still resolves only to the authenticated user for backwards
compatibility. It never means everyone. The REST endpoint retains its existing
all-user behavior when `user` is omitted, but the pipeline always supplies a username.

Offset pagination is not a database snapshot: playback added during retrieval may
shift page boundaries. The pipeline deduplicates repeated watch IDs per user.
All history means all records available in PlexIntel's synced history, not activity
missing from the upstream sync.

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
  bounds are exclusive. Weeks start Monday. Results without a timestamp are
  excluded from date-filtered results and disclosed.
- `WATCH_HISTORY_TIMEZONE` (environment variable or pipeline valve) defaults to
  `America/Chicago` and controls calendar windows and naive history timestamps.
  Timestamps that already include an offset preserve it.
- Display limits apply after retrieval, filtering, and aggregation. Viewer lists
  include every matching username.

## Activating updates

Restart the PlexIntel API process to load the new MCP instructions and schemas,
then reconnect or refresh tool discovery in MCP clients. Update/reload the Open
WebUI pipeline file to version 0.1.8. Install the API changes with the pipeline so
large histories can be paginated.

The MCP rules guide the connected model's tool use; the deterministic pipeline
executes the per-user workflow directly.
