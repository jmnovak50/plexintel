# Trip and event exploration — phase 3, 2026-09-13

## Baseline and capability assessment

Started from clean `main`, **487ece8**, the committed phase-2 discovery change on top of
phase-1 **2c1e06b**. There were no uncommitted dependency changes or applicable repository/
ancestor AGENTS.md files. Read the actual [phase-1 report](location-search.md),
[phase-2 report](photo-discovery.md), source, schemas and tests; their completed contracts,
not the original prompts, are the dependency. Only `immich-mcp/` changes belong to this phase.

| Capability | Existing dependency | Phase-3 addition / assistant responsibility |
| --- | --- | --- |
| Resolve scope | list_albums/get_album, find_people, location suggestions | Assistant confirms album/title/name ambiguity and distinguishes album, filtered metadata and accessible timeline |
| Retrieve metadata | Shared legacy/structured adapter, account-bound pagination, diagnostics | Add album confinement to the same internal builder; reuse pages for bounded event reads |
| Group trips/events | Phase 2 offered searches and temporal references, not event groups | Deterministic gap/year/explicit-sequence grouping across all pages in a bounded read |
| Drill/refine | Explicit asset IDs and reference-photo time windows | Immutable event references, fresh scoped pages, explicit splits/adjacent combinations/narrowing |
| Select story photos | Phase-2 time-bin sampling and image budgets | Reuse sampling; shortlist temporal endpoints, different stored places, then spread within candidates |
| Narrate/display | Existing assistant reasoning and native/attachment image workflow | Assistant writes grounded captions and verifies visible attachments; no new LLM or UI service |

The MCP service was read-only inspected again: PID **997241**, active since September 13
09:34:31 CDT; working directory `/home/jmnovak/projects/plexintel/immich-mcp`, launching
`.venv/bin/uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8490 --no-access-log
--proxy-headers`, with no reload/workers argument. A fresh interpreter resolves checkout source.
MCP **2.1.1**, httpx **0.28.1**, Pydantic **2.13.5**, FastAPI **0.141.1**, Uvicorn **0.52.4**
remain installed. There is still no loaded-process build fingerprint; the older site-packages/app
copy and on-disk edits do not prove the process loaded this phase. No restart was performed.

Immich **3.2.0** / legacy mode were observed in the preceding same-session investigation;
the version was not newly probed here. Pinned contracts were refreshed. The live smart-search
failure and external connector INVALID_ARGUMENT label remain unresolved. No smart-search
fault probe, key extraction, permission change or production image retrieval was performed.
Event exploration rejects required semantic query/similarity, with an explicit limitation;
it never drops that requirement or makes metadata grouping depend on ML. Phase-2 smart tools
remain available for separate candidate discovery, subject to their unresolved live health.

## Version-matched APIs and access

Both supported contracts use POST search/metadata: legacy flat albumIds plus existing filters,
order and numeric page; structured v3.2 filter.albumIds.all plus predicates, orderBy and opaque
cursor. Shapes are never mixed. Album scope is explicitly authorized by Immich and may include
authorized shared-with-me contributions; a whole-timeline scope retains Immich's searchable
account/partner rules. No caller-selected owner or unrestricted URL exists.

This follows the pinned [v3.2 search service](https://github.com/immich-app/immich/blob/v3.2.0/server/src/services/search.service.ts),
[search DTO](https://github.com/immich-app/immich/blob/v3.2.0/server/src/dtos/search.dto.ts),
[v3.1 search service](https://github.com/immich-app/immich/blob/v3.1.0/server/src/services/search.service.ts),
[v3.2 album DTO](https://github.com/immich-app/immich/blob/v3.2.0/server/src/dtos/album.dto.ts)
and [v3.1 album DTO](https://github.com/immich-app/immich/blob/v3.1.0/server/src/dtos/album.dto.ts).
Album reads in these versions return metadata without an embedded full asset list; no guessed
withoutAssets flag or alternate bulk retrieval was added. Existing list_albums resolves titles;
ambiguous titles require clarification. Album order is not capture chronology.

Native memories were inspected using the pinned
[memory DTO](https://github.com/immich-app/immich/blob/v3.2.0/server/src/dtos/memory.dto.ts) and
[controller](https://github.com/immich-app/immich/blob/v3.2.0/server/src/controllers/memory.controller.ts).
Their anniversary-oriented records and separate memory.read permission are unnecessary here.
No memory API, memory writes, additional statistics permission or persistent indexing is used.

Current request identity resolves the credential on every tool call. Event references bind to
namespace, subject and a credential digest. They contain query plans, grouping choices, expiry
and observed bounds, not cached asset metadata, photos, credentials or authorization decisions.
Every drill-down/story/refinement re-reads the original mandatory scope. Album and explicit
person/reference access are checked through existing helpers. A key change, disconnect, expired
reference or different user cannot reuse the old plan. Authorization loss during an overview or
story is an error, without returning an earlier cached-looking prefix. Ordinary service failures
after successful pages can return current-operation partial evidence, clearly marked as such.

Public-share grouping is **not** added to these private event tools. Existing public tools retain
their separate share-bound functionality. A public share key/URL cannot select an account or
authorize private event reads. No fallback to share keys or administrator credentials occurs.
OAuth confidential clients, resource/audience/scope, linking, credential encryption/revocation,
GET retry policy and existing success shapes remain intact. Routine diagnostics contain no
personal titles, names, GPS, IDs, filenames, request/response bodies, images or secrets.

## Retrieval and overview continuation

`explore_events(scope, grouping, continuation)` returns a bounded overview page. Scope wraps
the existing DiscoveryFilters, optional album_id, user label, capture_months, capture_quality
(all/dated/undated) and up to 12 exact location exclusions. All supplied filters remain mandatory.
Month and exclusion conditions run locally **after authorized retrieval**, so counts distinguish
retrieved metadata from included assets. Unknown locations survive exclusions; missing dates do
not match a month. Returned scope objects can be reused without inventing reference arguments.

The default initial prefix is two pages, at most 100 metadata assets/page (also bounded by
PRIVATE_TOOL_MAX_ITEMS and existing traversal limits). Continuation re-reads four, then at most
six pages from the beginning. All those pages are grouped together; no page boundary is treated
as an event boundary. Earlier groups may extend or change. This is deliberately a replacement
overview, **not incremental appended counts**. `eventId` helps correlate an unchanged newest
anchor within the same scope; `eventRef` is the immutable drill-down plan from a specific response.

The re-read design costs up to 2 + 4 + 6 search POSTs for those three default revisions. Each
individual call has a strict page budget and no hidden image work. It avoids retaining photo
metadata between requests and rechecks current access/membership. It also avoids silently missing
a page boundary when a formerly provisional group extends. It is not a transactional snapshot:
library changes during pagination may still move/remove/add matches. The inherited page engine
deduplicates IDs and validates numeric/opaque continuations, including wrong-contract and repeated
values. It discards unused upstream handles when the bounded operation ends.

At most 24 groups are returned per overview page. If more groups were retrieved, continuation
re-reads the same prefix and displays the next group slice before increasing prefix size. Read
eventOffset and updateMode: replace the displayed overview page and never sum counts across
revisions. The query-plan store is bounded at 128 entries, expiring with the existing 900-second
TTL; eviction/restart invalidates references explicitly. Small configured reference limits reduce
the group-page size to avoid evicting references created in the same response. No background jobs.

Source defaults (no production settings changed): EVENT_INITIAL_PAGES=2, EVENT_MAX_PAGES=6
(hard validated maximum 10), EVENT_MAX_GROUPS=24 (maximum 50), EVENT_REFERENCE_LIMIT=128.
Existing page/item/TTL limits can stop work earlier. On hard caps, narrow capture dates with the
original mandatory filters; do not claim complete coverage or silently scan unrelated years.

`coverage.complete` means the bounded traversal actually reached the end of accessible matching
upstream metadata. Local-filter includedCount and fullScopeCount are distinguished; the latter
is null while incomplete. No deprecated upstream total is used. Every incomplete event is
provisional, with the oldest observed boundary marked separately. A later timeout/service/malformed
page yields partial results, a sanitized error, and no automatic retry continuation. After resolving
that failure, explicitly restart/refine the scoped overview. A first-page failure remains an MCP
error; 401/403/404 authority/access failures remain errors even after earlier pages succeeded.
Complete matching metadata never proves all real visits were found: missing geocoding and sparse
photography can omit both destination photos and intervening out-of-scope photos.

## Grouping and timestamp evidence

- **visits**: split on capture gaps greater than 72 hours by default. **moments**: default three
  hours. gap_hours can be explicitly set from 15 minutes to 90 days; it is not a universal trip
  definition. Larger visit groups include bounded smaller-moment summaries (three-hour default).
- **years**: group by calendar year in grouping.time_zone, explicitly defaulting to UTC. Optional
  capture_months supplies calendar clues, not holiday recognition. No current-user timezone guess.
- **sequence**: explicitly interpret the scoped set as one sequence, subject to explicit split_at
  points. A multi-event album is not automatically treated as one event. gap_hours with years or
  sequence is rejected rather than ignored. Split points retain ISO offset/date-only semantics.
- City/state/country changes summarize known places; they do not automatically break a visit.
  Simultaneous different places can reflect multiple photographers, not one person's route.
  Separate months-long visits, consecutive days and sparse long gaps remain candidate boundaries.

Timestamp hierarchy is intentionally strict: timezone-aware fileCreatedAt normalized to UTC,
otherwise **unknown**, with no upload-time fallback. Raw fileCreatedAt, localDateTime and createdAt
survive compact evidence. localDateTime is timezone-agnostic and is not silently interpreted using
the user's current zone. A disagreement over two days is flagged for clock/import review; neither
timestamp is “corrected”. Missing/invalid/naive capture times form an explicit undated group, ordered
deterministically by ID. Scans, screenshots and imports may have plausible but historically wrong
file times; no fixture can establish those dates as ground truth. UTC elapsed gaps handle midnight,
DST folds and changing offsets without fictitious travel-time jumps. See the pinned
[asset timestamp contract](https://github.com/immich-app/immich/blob/v3.2.0/server/src/dtos/asset-response.dto.ts).

Event labels are marked inferred; a user scope label and an album title retain separate provenance.
Each row has observed start/end, retrieved/full-scope count distinction, media counts, bounded
location and person-label summaries, representative photo IDs/evidence, grouping reason and caveats.
Location/person summary cardinalities and momentCount expose truncation of their bounded lists.
No confidence score, arrival/departure date, actual attendance or uninterrupted event duration is
inferred. People metadata cannot prove “only us”; a human label or dog-like photo cannot establish
Lucy. Videos count in metadata timelines; representative photo IDs are IMAGE-only. A video filename
or still preview does not establish the clip's actions or full content.

## Drill-down, refinement and stories

`get_event_assets(event_ref, limit)` retrieves fresh pages within the **observed** event window
and original album/people/place/OCR/month/exclusion constraints. Send only continuation thereafter.
An undated event stays undated. Local filtering can produce an empty page with a continuation;
counts before filtering are named accordingly. The window does not grow implicitly if the overview
was provisional: continue the source overview to investigate unseen earlier/later extensions.
Deleted/repermissioned assets are not returned from a summary cache; newly matching assets can
appear because the reference is a scoped query plan, not a frozen member list.

`refine_event` narrows one event (default moments), adds mandatory people_all or exact exclusions,
or combines two to four **adjacent dated events from the same overview response/revision**.
Combination explicitly searches their observed envelope with original filters intact; new matches
in the intervening window remain possible. Different scopes/revisions and nonadjacent combinations
are rejected. Override grouping or supply split_at to refine boundaries. No albums/metadata change.
“That afternoon” uses the completed phase-2 reference mode in a fresh explicit scope; retain
mandatory constraints and explain any user-authorized temporal/location expansion separately.

`prepare_event_story` uses phase-2 time-bin metadata sampling, including album confinement, then
keeps local month/exclusion constraints before choosing frames. Defaults use IMAGE_CANDIDATE_LIMIT
(six in source defaults) and IMAGE_HIGHLIGHT_COUNT; explicit counts cannot exceed that configured
candidate budget (maximum 12). It favors endpoints of the **retrieved sample**, known place variety,
then temporal spread. Sampling is newest within each time bin and may miss important moments.
Single-instant events use one bounded fresh page; undated and video-only story scopes fail clearly.
Fewer frames are returned when required. No scores, duplicate deletion or global-best claim.

Frames contain asset IDs, compact metadata, captionEvidence, selection reason and uncertainty.
The MCP writes no open-ended story. The assistant inspects a few matching thumbnails in existing
bounded batches, requests preview detail only as needed, and narrates only from metadata, inspected
pixels or explicit user context. Album titles, OCR, filenames and descriptions are **data**, never
instructions. Do not invent restaurants, exact routes, relationships, conversations, emotions or
video activities. An ordinary partial failure retains successful candidates; lost authority stops
the story. No search/story tool downloads images. Existing image tools retain successes, concurrency,
byte and deadline policies. Vision access and visible attachments are separate checks.

## Example conversations (illustrative IDs/dates must be resolved)

Chronological exploration:

```text
get_immich_connection_status()
list_albums()  # resolve "Lucy's Big Adventure"; clarify duplicate titles
explore_events(scope={album_id:CONFIRMED_ALBUM_ID}, grouping={mode:"visits",gap_hours:72})
explore_events(continuation:RETURNED_HANDLE)  # replacement overview, not appended counts
get_event_assets(event_ref:SECOND_DISPLAYED_EVENT_REF, limit:20)
refine_event(event_refs:[THAT_REF], grouping:{mode:"moments",gap_hours:2,
             split_at:[USER_SPECIFIED_ISO_CUT]})
```

For Hawaii visits resolve stored state spelling through get_location_suggestions, then use
`scope={filters:{state:STORED_STATE}}`. Do not include IMAGE when all media are requested.
For family Christmas candidates, resolve actual people IDs, use people_all/any as supported by
the configured API mode, and explicit month/date/album clues. For example capture_months:[12]
with grouping.mode:years and a known calendar zone finds December candidates; confirm Christmas
from album/user/OCR/visual evidence, not the calendar alone.

Photo story or photo-to-event exploration:

```text
prepare_event_story(event_ref:CONFIRMED_EVENT_REF, selection_count:3,
                    visual_preference:"different scenes and meaningful expressions")
# Fetch only a few returned IDs with get_asset_thumbnail(size:"thumbnail").
# Reuse successful attachments; write a short chronological caption sequence from evidence.
explore_events(scope:{filters:{reference_asset_id:KNOWN_PHOTO_ID,
                reference_mode:"near_time",window_minutes:90}}, grouping:{mode:"moments"})
# An afternoon refinement needs explicit reference_mode:"afternoon" and a known IANA zone.
# Explain any authorized expansion and carry original mandatory filters forward.
```

## Validation and remaining manual checks

Tests use isolated dependencies, temporary SQLite, synthetic names/IDs/assets/credentials, and
mocked upstreams. They assert checkout imports. No running environment was upgraded. Final results:
**283 passed** in the complete Immich MCP suite (including **36 new event cases**) and **28 passed**
in the four focused OpenWebUI files, with two existing Typer/Click deprecation warnings. Ruff checks,
format checks on changed Python files and git diff --check pass. Initial fixture mistakes (story
candidate configuration and a missing parametrized argument) were corrected before the passing run.
Event-specific acceptance includes version-shaped
requests, visits, road trips, cross-page grouping, sparse gaps, unknown dates/GPS, clock conflicts,
DST/travel offsets, holiday ambiguity, multi-event albums, scoped refinement, stories, caps,
partial failures, deletion/authority loss, two-user references, raw MCP errors/schemas and share
separation. Existing phase-1/2 authorization, search, image and public-share regressions still run.

Reproduce from immich-mcp/:

```bash
OPENWEBUI_CHECKOUT=/home/jmnovak/projects/open-webui /tmp/immich-location-check/bin/pytest -q
```

The separate clean OpenWebUI checkout remains **4ff4ca0**, with MCP 1.27.2 in its isolated test
environment. Its four existing MCP content/client, Responses tool-image and assistant-attachment
test files are run using `/tmp/immich-location-openwebui/bin/python`, PYTHONPATH=backend,
PYTHONDONTWRITEBYTECODE=1 and pytest -p no:cacheprovider. No OpenWebUI source/config changes.
Its deployed TrueNAS artifact/overlays and live rendering remain unverified; local checks prove
neither live discovery nor visible browser attachments. MCP input models reuse phase-2 value-hiding
validation; the outer connector's INVALID_ARGUMENT remains outside this tested boundary.

## Manual deployment/rollback and connector refresh — NOT EXECUTED

1. Review source/tests/docs against **487ece8**, preserving both prior phases. Save the complete
   `/tmp/immich-event-exploration.patch` including new files to durable storage. Record the actual
   predeployment artifact; do not reset or reverse phase-1/2 patches.
2. Recheck the unit's WorkingDirectory, ExecStart, PID and import origin. Confirm the observed
   one-worker checkout launch; it needs no package reinstall or application upgrade. If changed,
   identify the actual artifact before planning deployment. No loaded revision is assumed here.
3. Keep existing configuration/permissions/OAuth/secrets unchanged. Source defaults enable this
   bounded workflow. Structured any/none still requires the separately reviewed v3.2 API mode from
   phase 2; album.read/person.read apply only where used. No memory/statistics permission, migration,
   secret rotation or asset mutation is required. New event limits are optional reviewed settings.
4. **Only with later deployment approval**, load the reviewed source and restart immich-mcp.service.
   Check localhost:8490 health/readiness, unauthenticated MCP denial and protected resource metadata.
   Verify existing location/people/image tools before the event acceptance below.
5. Refresh the existing ChatGPT connection's tool metadata and start a fresh chat using the
   [official refresh procedure](https://developers.openai.com/plugins/deploy/connect-chatgpt).
   Confirm all four new tools, schemas and descriptions. Published connections have their own
   reviewed update flow. In OpenWebUI refresh/reselect the existing tool connection in a fresh chat,
   retaining OAuth Static settings, account linking and access controls. No OpenWebUI restart or patch.

Rollback requires separate approval: run `git apply --reverse --check /path/to/immich-event-exploration.patch`
at repository root, then reverse only this reviewed phase-3 patch if clean. Overlapping edits require
hunk review, never reset to earlier commits. Restore only optional event settings changed during
approved rollout. Restart MCP only with authorization, refresh both connectors and verify phase-1/2
tools. No credential/database rollback is needed. Restarts invalidate temporary references/handles.

In **each fresh ChatGPT and OpenWebUI chat**, mark these separately (all currently unexecuted):

- [ ] Resolve an accessible album or confirmed location and request an event overview. Verify source
  scope, candidate labels, observed spans, media counts and partial/full metadata coverage.
- [ ] Continue across pages: the same visit must extend without an artificial boundary; replace
  overview counts and retain the exact displayed eventRef for “expand the second trip”.
- [ ] Drill and refine a known group; confirm all album/person/location constraints survive. Check
  a user-authorized surrounding-photo time window with known IANA zone and no invented place.
- [ ] Prepare a short story, inspect only a few thumbnails, and verify captions against actual
  metadata/pixels/user context. Treat calendar/album/label clues as distinct evidence.
- [ ] Record image retrieval, model vision and **visible user attachments** separately. Verify
  OpenWebUI persistence/reload and single-file reuse; use supported ChatGPT attachment references.
  Never duplicate base64 text as a display workaround or claim video understanding from a still.
- [ ] Repeat as a second user with different accessible assets; private event/continuation/reference
  tokens must not grant access. Verify existing public-share workflows independently. Revocation,
  forced faults and cache expiry belong in fixtures, not production fault traffic.
- [ ] Recheck original Hawaii location retrieval, people searches, filenames, recent assets, albums
  and existing images. Keep unresolved smart-search health and external adapter issues separate.
