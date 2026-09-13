# Capture-location search investigation — 2026-09-13

## Diagnosis and evidence

Started from clean `main` / `origin/main`, `07512b2a68ce3a126cd0f35ee172116986afd8e0`.
No applicable AGENTS.md files were found. Only `immich-mcp/` source, tests and documentation
were changed. Nothing was deployed, restarted, upgraded, merged, migrated or reconfigured.

Confirmed retrieval defects in that source: `search_assets(query="Hawaii", media_type="IMAGE",
limit=30)` sends a smart-search POST; state/province is absent from filters and compact
results; the list response discards pagination. These defects explain why the interface
cannot reliably answer capture-location enumeration. They do **not** explain the upstream failure.

The exact supplied text matches the inspected client's HTTP >=500 branch. A bounded journal
read (30 available records since September 12, maximum 300 requested) found one deliberate
SDK `search_assets` failure with `ImmichUnavailable`, at **2026-09-13 13:42:02.201664 UTC**.
It contains no exact upstream status or useful upstream diagnostic, and cannot be independently
linked to the supplied ChatGPT call without its timestamp/correlation. The current source and
journal are consistent with an upstream 5xx; the precise status and underlying cause remain
unconfirmed. There is no evidence establishing an upgrade incompatibility, disabled ML,
malformed request, vector/database failure, or transport timeout as the cause of that incident.

Read-only installation evidence:

| Item | Observation |
| --- | --- |
| Configured Immich endpoint | One unauthenticated `GET /api/server/version`, HTTP 200, **3.2.0**; no retry after successful probe |
| Service | `immich-mcp.service`, PID 1946, active since September 12 08:31:01 CDT |
| Unit | `/etc/systemd/system/immich-mcp.service` |
| Working directory | `/home/jmnovak/projects/plexintel/immich-mcp` (also confirmed via `/proc`) |
| Launch | `.venv/bin/uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8490 --no-access-log --proxy-headers`; no reload/workers argument |
| Imports | Explicit checkout import resolves `immich-mcp/app/immich/client.py`; `.venv/lib/python3.13/site-packages/app` is a separate older copy. Its client/server/connection files differ from the handoff; installed connection code lacks deliberate general ImmichError translation |
| Installed libraries | Python 3.13; MCP 2.1.1; httpx 0.28.1; Pydantic 2.13.5; FastAPI 0.141.1; Uvicorn 0.52.4 |
| Safe configuration inspection | Private access enabled; namespace `authentik`; scope `immich.read`; both confidential client secrets present (values withheld); TLS verification enabled; HTTP timeouts 15s/5s; GET retries 2; private page cap 100; image concurrency 6/process, 2/credential; image deadline 45s |
| Process overrides | No IMMICH/OIDC/ACCOUNT/CREDENTIAL/IMAGE environment overrides or PYTHONPATH found; local `.env` supplies configuration |
| OpenWebUI checkout | Clean detached `4ff4ca0`, existing attachment-promotion implementation; requirements pin MCP 1.27.2. No OpenWebUI source/configuration changes |

Uvicorn's working-directory import behavior points to checkout source, and the journal's
deliberate error is consistent with it. There is no runtime build fingerprint proving every
loaded module's revision. Do not equate installed-wheel files or current disk contents with
already-loaded code. Neither the running TrueNAS OpenWebUI artifact/overlays nor browser
rendering could be inspected here; local compatibility tests do not establish their deployment.

The deferred tool catalog exposes the user's authenticated Immich connector. After confirming
`connected=true`, two bounded live searches were executed through that connector:

| Probe | Observed connector result |
| --- | --- |
| Metadata only: `search_assets(country="United States", limit=2)` | Success, zero items. This is an endpoint/authorization check, not Hawaii coverage or validation of the stored country spelling |
| Original: `search_assets(query="Hawaii", media_type="IMAGE", limit=30)` | Reproduced the exact supplied `ImmichUnavailable` text and outer `structuredContent.error_code="INVALID_ARGUMENT"`; called once, no automatic retry |

The currently advertised tool schema has city/country but no state or location suggestions.
Consequently an authenticated **state-only** live probe cannot be made through the deployed
interface before deployment. No keys were decrypted or chosen from the credential store, no
images downloaded, and no upstream error bodies exposed. No upstream Immich/ML/database logs
were available. The public
version request initially failed inside the network sandbox, then succeeded with authorized
network access; that sandbox failure says nothing about the reported production incident.

## MCP error boundary

Installed MCP 2.1.1, `mcp/server/mcpserver/server.py` `_handle_call_tool`, converts deliberate
`ToolError` exceptions to `CallToolResult(content=[TextContent(...)], is_error=True)` without
structured content. Direct client wrapping and raw authenticated ASGI HTTP regressions
confirm the serialized result has `isError: true`, readable sanitized text, and **no
`structuredContent.error_code`**. Neither application source nor that installed SDK defines
`INVALID_ARGUMENT`. Thus the contradictory field is introduced beyond this tested repository/SDK
boundary, in the external connector/adapter path. The live reproduction confirms the external
label still occurs. The specific external component cannot be identified without a raw live
response and adapter trace; this patch does not claim to fix it.

Failures now preserve exact HTTP status, a fixed operation label, category, locally generated
correlation ID, attempts and elapsed milliseconds. Metadata diagnostics include configured
mode and actual emitted request mode (older tools still emit legacy requests). No URLs, IDs,
search terms, filenames, coordinates, upstream bodies, keys, tokens or cookies are logged by
these diagnostics. HTTP client URL logging remains suppressed. Upstream HTML is never reflected.
Image errors also carry correlation/status details; original image payload behavior is unchanged.

| Failure | Deliberate category / handling |
| --- | --- |
| 400 | `ImmichBadRequest`: request rejection or operation precondition; not proof of malformed arguments or disabled ML |
| 422 / local validation | `ImmichValidationError` |
| 401 / 403 | `InvalidImmichCredential` with reconnect guidance / `ImmichForbidden` with permission/access guidance |
| 429 | `ImmichRateLimited` |
| 500, 503, other >=500 | `ImmichUnavailable` with exact HTTP status |
| Timeout / network | `ImmichTimeout` / `ImmichNetworkError` |
| Invalid JSON or page shape | `MalformedImmichResponse`; never a successful empty page |

Search POSTs are attempted **once**. GETs retain their bounded retry budget for transport
errors and 429/500/502/503/504 only. No assistant retry loop or generic POST retries were added.
The correlation ID links the tool error to the local service event; it is not an upstream
server trace ID. Use timestamps/operation to correlate with authorized upstream logs.

## Interface and contracts

`get_location_suggestions(field="state")` reads authenticated asset suggestions. Optional
country scopes state/city suggestions; state scopes cities. Invalid scope combinations fail
instead of being silently ignored. Null/blank entries are omitted, duplicates removed, Unicode
preserved. `contains` only filters case-insensitive substrings locally; it never invents aliases.
Results are bounded with `nextOffset` (repeat the same arguments to retrieve more). Suggestions
are not cached across accounts. The upstream endpoint itself returns an unpaginated list.

`search_location_assets` combines city, state/province and country with AND. Optional media
type and inclusive capture-date bounds are supported; date-only bounds mean midnight UTC.
Omit media type for matching photos and videos. This tool always uses metadata search and
downloads no images. IDs, capture dates and state/city/country evidence survive compaction.
Existing `search_assets` retains its list shape/defaults and adds state; mixed semantic queries
keep all supplied location constraints. There are no user/owner/credential/URL parameters or
OR branches. Immich enforces its own searchable account/partner and authorized shared-album
rules. This tool does not expand library search to every arbitrary shared album.

The new pages use an explicit validated `IMMICH_SEARCH_API_MODE`:

| Mode | Request / continuation | Compatibility |
| --- | --- | --- |
| `legacy` (default) | Flat state/city/country/type/takenAfter/takenBefore, order, numeric page, size, withExif | Validated v3.1 and v3.2 contracts; no production configuration change needed |
| `structured` | filter predicates, takenAt gte/lte, orderBy fileCreatedAt descending, opaque cursor, size, withExif | Validated v3.2.0 contract; opt in only after reviewing the actual server contract |

No discovery or error-driven downgrade occurs. New/legacy fields are never mixed. This setting
only selects the new location-page contract; existing filename, album, recent and semantic
tools retain flat requests. Legacy consumers now reject wrong-contract cursors and backward
pages instead of parsing cursors as numbers. The structured path selects `nextCursor` even
when `nextPage` is null; numeric-looking cursors are forwarded unchanged. Smart search has
distinct ranking semantics; this implementation does not apply metadata cursors to it.

These decisions follow the pinned [v3.2 DTO](https://github.com/immich-app/immich/blob/v3.2.0/server/src/dtos/search.dto.ts),
[controller permissions](https://github.com/immich-app/immich/blob/v3.2.0/server/src/controllers/search.controller.ts),
[execution/scoping](https://github.com/immich-app/immich/blob/v3.2.0/server/src/services/search.service.ts),
[date predicates](https://github.com/immich-app/immich/blob/v3.2.0/server/src/utils/database.ts),
and [v3.1 DTO](https://github.com/immich-app/immich/blob/v3.1.0/server/src/dtos/search.dto.ts).
The [v3.2 release](https://github.com/immich-app/immich/releases/tag/v3.2.0) introduces the new
API; its existence alone does not diagnose the incident. No statistics call or additional
`asset.statistics` permission is needed. Deprecated totals are ignored.

## Enumeration, sample and limits

Example after confirming the intended region and discovering the actual stored state spelling:

```text
get_immich_connection_status()
get_location_suggestions(field="state")
search_location_assets(state="Hawaii", limit=100)         # photos and videos
search_location_assets(continuation=<returned handle>)    # repeat while a handle exists
```

Each continuation is a random handle bound to the authenticated namespace/subject and current
credential digest. The server retains the original filters, ordering, size, seen cursors and
seen IDs; it stores no image bytes or credential token in that traversal. Each call resolves
the credential again. A different account, reconnect with a different key, disconnect or
revocation cannot reuse the old authorized scope. Handles are single-use and consumed before
the upstream await, preventing concurrent replay. Do not send new filters/limit with a handle.

`returned` counts unique assets in this response; `returnedSoFar` is unique IDs observed since
the first page. `complete=true` only means that traversal reached a terminal page. There is
no snapshot guarantee while the library changes. Wrong/malformed/repeated continuations,
empty pages with continuation, oversized pages and invalid IDs fail explicitly. Later page
failure remains an MCP error with the preceding unique count and “Enumeration incomplete”.

Defaults: 100 pages, 10,000 unique IDs per traversal; page size capped at `PRIVATE_TOOL_MAX_ITEMS`
(100 here); 128 retained continuations/process; 900-second lifetime from the first page.
Page/item/deadline stops return `partial=true`, `complete=false`, no continuation and a
`stopReason`. Expired/evicted/consumed handles fail explicitly. Unused expired records are
pruned on the next page request; storage is also bounded by the session cap. Handles are process
local: worker changes or restarts invalidate them. The verified unit launches one worker.
Multiple-worker installations require affinity or a future shared continuation store.

For the requested photos, independently call
`search_location_assets(state="Hawaii", media_type="IMAGE", limit=2)` or select two photo IDs
from already-enumerated metadata. Fetch only a small candidate set with existing thumbnail
tools, at most two image calls at a time under current settings. Reuse successful results;
request previews only for needed detail. State that the two photos are a sample, even when
metadata enumeration is complete. Missing or incorrect GPS/reverse-geocoding can exclude real
Hawaii photos. Neither an empty search nor a place/album name proves whether a trip occurred.
Clarify Georgia or Hawaii island/state ambiguity; do not replace a state with Honolulu.

## Validation

Final regression results: **164 passed** in the complete Immich MCP suite, including its
OpenWebUI content cross-check; **28 passed** in the four focused OpenWebUI files (two
Typer/Click deprecation warnings). Ruff checks on the touched Python files and
`git diff --check` pass. The two live probes above were executed; the new state-only search,
live client rendering and deployed OpenWebUI artifact verification are unexecuted. No deliberate
faults or repeated smart-search calls were generated.

Tests import the edited checkout (an explicit regression checks the source path) and disable
`.env` loading in fixtures. Upstream services, API keys, OAuth identities and images are synthetic;
SQLite databases are temporary. Isolated environments are `/tmp/immich-location-check` (MCP 2.1.1,
httpx 0.28.1) and `/tmp/immich-location-openwebui` (MCP 1.27.2, httpx 0.28.1). No packages in
the service environment were installed or changed.

An early sandboxed SQLite test run stalled and was interrupted; the mocked suite completed
outside that sandbox. One invocation from repository root failed collection because it bypassed
the service's pytest import configuration and included unrelated PlexIntel tests. The results
above are from the corrected service-directory command below, with an explicit checkout-origin
assertion. No unrelated tests or running applications were repaired or upgraded.

Run from **immich-mcp/**, so its pytest configuration selects checkout imports:

```bash
OPENWEBUI_CHECKOUT=/home/jmnovak/projects/open-webui /tmp/immich-location-check/bin/pytest -q
```

From **open-webui/**:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend /tmp/immich-location-openwebui/bin/python -m pytest -q -p no:cacheprovider \
  backend/tests/test_mcp_content.py backend/tests/test_mcp_client.py \
  backend/tests/test_responses_tool_images.py backend/tests/test_responses_assistant_attachments.py
```

Coverage includes state-only all-media retrieval while smart search fails; a two-photo native
sample with date/state evidence and no bulk image downloads; both request contracts; opaque
and numeric-looking cursors; null/terminal/empty/malformed/repeated pages; duplicate IDs and
partial failures; safety/expiry/eviction/scope limits; Unicode/null suggestions; distinct users
through raw HTTP suggestions/pages/continuations/images; disconnected/revoked/denied access;
sanitized HTTP/transport/JSON errors and retry counts; existing public shares, filenames,
albums, recent assets, OAuth and image workflows. OpenWebUI tests exercise content handling,
vision conversion, single persistence and reuse as assistant attachments. They are **not** live
browser/display checks. No client-side code change is justified by the available evidence.

## Manual post-approval deployment and rollback — NOT EXECUTED

1. Review the complete diff (including new `app/immich/location.py`, tests and this document)
   and the final test results. Preserve a full patch including untracked files, e.g. the supplied
   `/tmp/immich-location-search.patch`, in durable storage. Do not use plain `git diff` alone
   to back up untracked files. Preserve the predeployment artifact/source revision for rollback.
2. Recheck `systemctl show immich-mcp.service -p WorkingDirectory -p ExecStart -p MainPID --no-pager`.
   Confirm the one-worker checkout launch still applies. If it changed, identify the actual
   artifact and adapt the procedure. Check the import with
   `PYTHONPATH=. .venv/bin/python -c 'import app.immich.client; print(app.immich.client.__file__)'`
   from the service directory. No wheel reinstall is needed for the verified checkout launch.
3. Default legacy mode needs no configuration change on the observed v3.2 server. Structured
   mode is optional, separately reviewed configuration. Preserve existing OAuth clients,
   resource URLs, `immich.read`, account boundaries, encryption keys, stored credentials and
   OpenWebUI secrets. No application upgrade, secret generation/rotation or migration is needed.
4. **Only after deployment authorization**, restart `immich-mcp.service`. Check local
   `http://127.0.0.1:8490/health`, `/ready`, unauthenticated `/mcp` denial and protected-resource
   metadata. Health alone does not establish correct retrieval or rendering.
5. For a developer-mode ChatGPT connection, open the existing connection in ChatGPT Plugins,
   select **Refresh**, confirm the new tools/state field/descriptions, and start a fresh chat.
   Published metadata has a separate reviewed-update flow. Preserve the existing confidential
   OAuth setup. See [official refresh guidance](https://developers.openai.com/plugins/deploy/connect-chatgpt).
6. In OpenWebUI, reselect the existing tool connection in a fresh chat and confirm the new
   tools were fetched. If cached, refresh/reconnect that existing entry through its current UI,
   retaining OAuth Static configuration, access controls and account linking. No OpenWebUI
   patch, upgrade, service restart or overlay replacement is part of this change.
7. Run the acceptance and remaining diagnostic checks below. Record retrieval, vision and
   visible attachments as separate outcomes.

Rollback after separate approval: first run
`git apply --reverse --check /path/to/immich-location-search.patch` at repository root, then
reverse the reviewed patch if it still applies cleanly. Overlapping later edits require manual
hunk review; do not reset the repository. A complete patch removes the new files too. Restore
only any optional location settings added during approved deployment. After authorization,
restart the MCP unit and refresh connector metadata, then repeat account and one-photo checks.
No credential/database rollback or OpenWebUI change is needed. Restart invalidates active handles.

## Fresh-chat acceptance and remaining live diagnosis

Run separately in ChatGPT and OpenWebUI after approved deployment:

- [ ] Ask the original Hawaii question in a **fresh chat**. Check connection status first;
  resolve the intended state and stored value using authenticated suggestions. It should use
  capture-location metadata, not `query="Hawaii"` or an album-name substitute.
- [ ] Enumerate all matching photos **and videos** through returned handles; distinguish
  returned unique count/completion from an authoritative total. Stop with a partial report if
  any page fails or a limit is reached. Compare location evidence in actual metadata.
- [ ] Select two representative **photos** from a small matching candidate set. Record which
  two IDs were retrieved; check vision accuracy separately from **two visibly attached images**.
  Reuse the client-provided attachment/file reference. In OpenWebUI verify persistence/reload
  and one stored file reused by tool and assistant output. Do not duplicate base64 as prose or
  copy the whole result/library elsewhere. If no display bridge exists, report that limitation.
- [ ] Repeat with a second connected user whose accessible library differs; verify suggestion,
  search and thumbnail scope, and denial of another user's private asset/continuation. Test
  public shares separately; never substitute public/admin credentials for failed private access.
  Use development fixtures for revocation, forced errors and expiry, not production fault traffic.
- [ ] Verify exact filename, album access, recent assets and a normal semantic query still work.
  For “beaches photographed in Hawaii”, preserve the resolved location filters. If semantic
  search fails, report that independently and keep metadata results labelled accurately.

To finish the unresolved diagnosis after deployment, use the affected user's authenticated
request context: make one metadata-only location request using the verified stored state and,
if the smart-path diagnosis is still needed, one original smart request
(`query="Hawaii", media_type="IMAGE", limit=30`) to obtain the new diagnostics. The original
was already reproduced once during this investigation; do not repeatedly replay it. Record
sanitized operation/status/category/timing/correlation and API mode, not request/response bodies.
Compare raw MCP HTTP result with the connector wrapper to locate the external error-label
translation. Correlate the timestamp with authorized Immich/reverse-proxy logs, and only then
inspect relevant ML/vector/database configuration/logs if those logs identify that path.
400/422, 401/403, 429, timeout/network and 5xx now remain distinguishable, but status alone
cannot identify a database or ML cause. A successful metadata search does not prove the
independent smart-search incident is fixed; mocked test success does not prove either live path.
