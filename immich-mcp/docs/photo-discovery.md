# People, combined search and photo discovery — 2026-09-13

The subsequent [phase-3 event exploration](event-exploration.md) builds on committed `487ece8`.
Use its separate rollback checklist for event-only rollback, preserving phases 1 and 2. The
evidence and test counts below describe the completed phase-2 task.

## Starting state and live limitations

This follow-on starts from clean `main` / `origin/main` **2c1e06b**, containing the completed
[location/API investigation](location-search.md), its adapter, diagnostics, tests and operational
checklist. There were no uncommitted dependency changes. No applicable AGENTS.md was found.
The earlier `07512b2` snapshot is historical and is not the rollback target for this work.
Changes are restricted to `immich-mcp/`; no dependencies or OpenWebUI files were changed.

Read-only runtime refresh: `immich-mcp.service` PID **997241**, active since **09:34:31 CDT**
September 13. This differs from the preceding investigation's PID; no restart was performed
by this task. Working directory remains `/home/jmnovak/projects/plexintel/immich-mcp`, executing
`.venv/bin/uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8490 --no-access-log
--proxy-headers`, one worker, without reload. A fresh import resolves the checkout client.
Python **3.13.5**, MCP **2.1.1**, httpx **0.28.1**, Pydantic **2.13.5**, FastAPI **0.141.1**,
Uvicorn **0.52.4** are unchanged. The separate older `site-packages/app` copy is not evidence
of the loaded process revision; no runtime build fingerprint exists. Immich **3.2.0** and
legacy API mode were observed in the same-session preceding investigation; no production
configuration was modified here. Existing Authentik namespace, resource/scope, confidential
clients, linking, encrypted credentials and public/private separation are preserved.

The available authenticated connector still advertises the earlier tool catalog, with no
people tools or location-page tools. Its cached metadata does not identify the loaded source.
The new people endpoints have therefore not been exercised through a deployed authenticated
tool in this task. Stored private keys were not extracted for probes. There was no new retry
of the failing smart-search call, no production fault traffic and no production image download.

The prior live `query="Hawaii"` smart-search failure remains **unresolved**. The available
evidence did not identify exact upstream status or root cause. Metadata discovery and optional
visual preferences operate independently of smart search. Required semantic and reference-image
similarity depend on its health. The prior raw SDK/HTTP tests place `INVALID_ARGUMENT` beyond
the repository's tested MCP boundary; this change does not claim to repair that external adapter.

## Capability inventory

| Intent | Existing capability / extension | Upstream and permissions | Limit |
| --- | --- | --- | --- |
| Find by name | New `find_people`, paginated `list_people`, `get_person_thumbnail` | GET search/person, people, people/{id}, people/{id}/thumbnail; person.read | Account-scoped name candidates, not identity inference; hidden opt-in |
| Both/either/exclude people | New `search_library`, reusing location adapter and traversal store | search/metadata; asset.read, plus person.read for explicit record authorization | Legacy supports all or a single any; structured v3.2 supports all/any/none |
| Place and event dates | Existing location suggestions/pages, now composed with people | Same authenticated asset metadata and capture-date predicates | Missing metadata excludes real matches; date-only means midnight UTC |
| Sign/text clue | New required `ocr` in composed filters | Flat OCR or structured matches predicate | Full-text evidence, not GPS or visual semantics |
| Visual clue / Lucy in snow | Existing semantic tool; composed required query or optional visual_preference | search/smart for required query | Ranked sample; unhealthy ML/search blocks required semantics; pet identity unverified |
| More like an explicit photo | New reference_mode=similar | Authorized asset read then smart queryAssetId | Requires embedding and healthy smart search; not exhaustive |
| Other shots that moment/afternoon | New near_time / afternoon reference modes | Asset read plus bounded metadata capture interval | Needs usable capture timestamp; local afternoon needs IANA zone |
| Same place | New same_place reference mode | Exact stored city/state/country, no invented geographic operator | Administrative area, not distance/radius/venue |
| Varied five-photo selection | New sample_photo_candidates; existing thumbnail/preview tools | At most six metadata bins; asset.view only when assistant fetches images | Bounded, biased time sample; visual judgment delegated to assistant |
| Filename, albums, favorites/recent, public shares | Existing tools unchanged | Existing permissions/contracts | No write operations added; original list shapes/defaults retained |

The [v3.2 person DTO](https://github.com/immich-app/immich/blob/v3.2.0/server/src/dtos/person.dto.ts),
[person controller](https://github.com/immich-app/immich/blob/v3.2.0/server/src/controllers/person.controller.ts),
[person service](https://github.com/immich-app/immich/blob/v3.2.0/server/src/services/person.service.ts)
and [person repository](https://github.com/immich-app/immich/blob/v3.2.0/server/src/repositories/person.repository.ts)
establish record access, account scoping, name-search cap and pagination. v3.2 returns a person-group
ID as the person record ID; consume that returned ID unchanged, never substitute an account ID.
The [v3.1 person DTO](https://github.com/immich-app/immich/blob/v3.1.0/server/src/dtos/person.dto.ts)
was checked for legacy compatibility. Permissions were inspected, not granted.

Composed requests follow the pinned
[v3.2 search DTO](https://github.com/immich-app/immich/blob/v3.2.0/server/src/dtos/search.dto.ts),
[controller](https://github.com/immich-app/immich/blob/v3.2.0/server/src/controllers/search.controller.ts),
[service](https://github.com/immich-app/immich/blob/v3.2.0/server/src/services/search.service.ts),
[v3.2 predicates](https://github.com/immich-app/immich/blob/v3.2.0/server/src/utils/database.ts)
and [v3.1 predicates](https://github.com/immich-app/immich/blob/v3.1.0/server/src/utils/database.ts).
No upstream-main assumptions or statistics permission were introduced.

## Contracts and interpretation

`find_people(name, match="fuzzy", include_hidden=false, limit=50, offset=0)` returns minimal
records: ID, name, hidden flag, thumbnail availability. It never returns thumbnail filesystem
paths or unnecessary birth dates. Upstream name matching is fuzzy/unaccented, not a guaranteed
substring search. `match="exact"` applies local Unicode casefold equality, preserving accents.
Multiple similar/duplicate names return `resolution="ambiguous"`; a sole record is a `candidate`,
not an automatic mapping for “me”, “wife”, “girls” or Lucy. A cap hit at 100 returns `incomplete`
even if local exact filtering leaves one record. `nextOffset` only pages the first bounded name
result set; no name cache is shared between users, and repeated calls are not snapshots.

`list_people(page=1, limit=50, include_hidden=false, unnamed_only=false)` uses upstream numeric
pages and `hasNextPage`. `unnamed_only` filters each page locally: empty filtered pages can still
continue. Keep the same arguments when following `nextPage`; deduplicate observed IDs if the
library changes. A terminal page is `enumerationEnd=true`, not proof earlier pages were fetched.
The configured page cap produces an explicit stop. Hidden people need explicit opt-in both for
name discovery and person thumbnails; default compact discovery metadata also omits hidden labels.
Missing person.read, denied/deleted IDs and disconnected/revoked keys fail with sanitized guidance;
unrelated permitted location/album calls still work.

`search_library(filters, visual_preference, limit, continuation)` accepts one typed object with
no arbitrary filter branches, owner/account/key or URL. All supplied predicates are required:

- `people_all`: all resolved IDs together; `people_any`: at least one; `people_none`: none of
  those labels. Operators combine with AND. IDs are deduplicated, at most 12 distinct records,
  and each record is authorized before search and again on continuation. Contradictory all/none
  or wholly excluded any lists fail. Empty lists and non-UUIDv4 IDs fail explicitly.
- `city`, `state`, `country`, `start_date`, `end_date`, `media_type`: same location/capture-date
  semantics as the preceding tool. Use authenticated suggestions when spelling/geography is unclear.
  Capture timestamps have explicit offsets; date-only bounds remain inclusive midnight UTC.
- `ocr`: required full-text match; `query`: required semantic concept. A readable Louisiana sign
  is text evidence, not proof of location. `visual_preference` is optional assistant judgment and
  is never silently promoted into a smart-search request or used to weaken mandatory predicates.

Legacy requests keep flat personIds (ALL), location, dates, OCR and numeric metadata pages.
Multi-any, none, or all+any fail clearly in legacy mode. The shared **explicit** setting
`IMMICH_SEARCH_API_MODE=structured` enables the validated v3.2 combinations. It applies to the
new location/discovery adapter; older semantic, filename and recent tools retain their successful
legacy contracts. There is no error-driven downgrade, repeated version probe or mixed old/new
request shape. Using the extra combinations on the observed installation needs a later reviewed
configuration choice; this task leaves its default unchanged.

Structured requests contain one filter with personIds all/any/none, location/type eq, OCR matches,
takenAt gte/lte; metadata adds orderBy and opaque cursor. No OR branch or owner override exists.
Immich retains its authorized partner/shared-asset rules. Person discovery itself is scoped to
the current account. Excluding a label means not matched by available metadata; unnamed,
unrecognized, hidden or undetected people can still be visible. Neither “both” nor “none” proves
“only us”. Use bounded visual inspection for visible context, without inventing biometric IDs.

Metadata pages share the earlier random, single-use, expiring handle store, account/key binding,
deduplication and safety limits. Handles are also tool-kind bound: location handles cannot become
discovery handles or vice versa. Send only continuation; mandatory criteria and preferences stay
fixed. People/reference authorization is rechecked, not cached. A later page failure is an MCP
error carrying the preceding unique count and incomplete-enumeration warning. Terminal completion
only covers matching accessible metadata, never a transactional snapshot or all real trip photos.

Required smart searches return one bounded ranking with `complete=false`, `partial=true`,
`stopReason="ranked_sample"`. Legacy smart numeric continuation is intentionally not followed;
v3.2 structured smart has no continuation. Metadata cursor logic is not applied to that ranking.
Reference and duplicate IDs are removed from similarity results. POST is attempted once; GET
retains existing bounded retries. Required semantic failures are errors, never successful empty
results or unrestricted substitutes. Lucy requires explicit user confirmation/reference context;
visual similarity does not verify her identity.

## Explicit reference and selection workflows

An ordinal such as “second one” is resolved by the assistant from its prior displayed ID list.
Pass that `reference_asset_id` and exactly one `reference_mode`; there is no global last-result
or cross-user conversation memory. The current credential reads the reference once initially,
then again on continuation. Known reference metadata survives compacting in `searchContext`.

- `similar`: smart queryAssetId, with all other predicates retained. Combining this with a text
  query is rejected so neither embedding input is silently ignored.
- `near_time`: ±60 capture minutes by default, adjustable 1–1440 via window_minutes. Explicit
  date bounds intersect that interval; an empty intersection fails instead of broadening it.
- `afternoon`: 12:00 through 17:59:59.999 on the reference capture day in supplied IANA time_zone
  or a valid reference EXIF timeZone. No account-zone or upload-date inference. Missing/invalid
  zones require clarification. DST conversion and effective bounds are visible in the result.
- `same_place`: reuse all nonblank stored city/state/country fields. Conflicting explicit values
  or missing administrative metadata fail. A state-only reference remains state-level precision.

These time choices use fileCreatedAt, not createdAt (upload time) or timezone-agnostic localDateTime;
see the [pinned asset response schema](https://github.com/immich-app/immich/blob/v3.2.0/server/src/dtos/asset-response.dto.ts).
No radius search, pet face recognition, training pipeline or second photo database was added.

`sample_photo_candidates` needs a capture interval and IMAGE (or omitted media type). Defaults:
12 metadata candidates, five suggested selections, four time bins, UTC day grouping, five-minute
minimum spacing. At most 48 candidates (also capped by private page limits), six bins and 1440
minutes spacing are accepted. Every bin retains required people/place/OCR predicates. Split the
UTC interval equally, request newest metadata within each bin, and deduplicate IDs where inclusive
boundaries overlap. Unused continuations are discarded; no hidden traversal downloads the library.

This intentionally favors newest items within each bin and may underrepresent busy days. Results
show each interval's bounds, returned count and whether that individual page ended. Overall
`complete=false` / `partial=true` always identifies a sample; `samplingFinished` only says whether
the planned bins finished. A page error stops remaining bins and preserves earlier candidates
with a sanitized error and partial state. An initial error remains an MCP failure.

Suggested IDs favor distinct days in the chosen zone, then additional moments separated by the
requested minimum gap. Temporal distance is computed in UTC across DST folds. Missing capture
timestamps cannot support this shortlist. Return fewer when no suitable candidates remain;
no unmatched filler or numerical “best” score. Equal/near timestamps do not prove identical files,
duplicate content or scene clusters. Metadata selection is distinct from visible quality review.

The assistant inspects a **small** subset with get_asset_thumbnail(size="thumbnail"), compares
expressions, relevance, meaning and assessable focus/exposure, and uses preview only where more
detail matters. Explain judgments and material uncertainty. Existing per-account/global image
concurrency, bytes, deadlines and stop-on-error guidance apply to person thumbnails too. Keep
successful images if another fails. No new search or sampler downloads images automatically.

## Usage examples

Find a remembered photo (illustrative pseudocode; resolve actual IDs/values first):

```text
get_immich_connection_status()
find_people(name="Brigid")
find_people(name="Jason", match="exact")
# Confirm which records and whether Jason is the user's intended "me".
get_location_suggestions(field="state")
search_library(filters={people_all:[BRIGID_ID,JASON_ID], state:STORED_STATE,
                        start_date:"2026-01-01T00:00:00-10:00",
                        end_date:"2026-02-01T00:00:00-10:00", ocr:"welcome"},
               visual_preference="sunset", limit=12)
# Dates above are examples, not guessed family events. Follow returned metadata handles if needed.
```

Curate a varied five-photo sample with verified people/place and user-provided trip dates:

```text
sample_photo_candidates(
  filters={people_all:[BRIGID_ID,JASON_ID], state:STORED_STATE,
           start_date:TRIP_START_WITH_OFFSET, end_date:TRIP_END_WITH_OFFSET},
  visual_preference="sunsets; meaningful expressions and different scenes",
  candidate_limit=12, selection_count=5, time_bins=4,
  time_zone="Pacific/Honolulu", min_gap_minutes=5)
# Use the actual returned candidate IDs; inspect a few thumbnails in bounded batches.
# Suggested selection is temporal, not visually ranked. Return fewer than five when necessary.
search_library(filters={reference_asset_id:SECOND_DISPLAYED_ID, reference_mode:"afternoon",
                        time_zone:"Pacific/Honolulu", people_all:[BRIGID_ID,JASON_ID]})
```

For either verified girl in structured mode use people_any; to exclude a named label use
people_none, with the detection caveat. “Without anyone else” requires honest visual/detection
limitations. For “same place, favor Lucy” keep a same_place reference and optional preference,
request user confirmation of pet identity. A required “dog in snow” query is semantic candidate
search, not Lucy recognition; stop and report an unhealthy smart endpoint.

## Validation and SDK/client boundary

Tests use synthetic names, UUIDs, assets, credentials, OAuth subjects and images; temporary SQLite
and mocked HTTP only. The checkout-origin test and service-directory pytest configuration prevent
stale installed imports. Existing isolated environments are reused; the running service environment
and requirements were not changed. Final results: **247 passed** in the complete Immich MCP suite
(83 additional discovery cases beyond the preceding 164), including the local OpenWebUI content
cross-check; **28 passed** in the four focused OpenWebUI files, with two existing Typer/Click
deprecation warnings. Ruff checks/formatting on changed Python files and git diff --check passed.
Initial new-test runs caught a helper argument-name collision, a mistaken SDK list-serialization
assertion, and the SDK validation-value disclosure described below; all were corrected before
the passing full run. Live people/search/rendering checks remain unexecuted.

Coverage includes unique/duplicate/partial/case/Unicode/empty names, cap disclosure, unnamed and
hidden records, denied/stale IDs, exact all/any/none mappings, legacy rejection, required filters
with preferences and semantic failure, OCR, reference access, DST/capture-vs-upload dates, missing
reference metadata, malformed/repeated/opaque cursors, deduplication, incomplete traversal,
bounded sampling, missing dates, fewer selections, and retention on partial failure. Raw MCP HTTP
tests exercise names, reference reads, continuation, person images and distinct credentials for
two users, including disconnected/revoked/denied cases. Existing location/asset image and OAuth
regressions remain applicable. POST counts stay bounded; new GET errors verify retry counts for
400/422/401/403/429/500/503, timeout and invalid JSON with body/name/key canaries.

MCP 2.1.1 deliberately returns upstream errors as isError with sanitized text, without the external
INVALID_ARGUMENT label. Its default Pydantic argument validator echoed rejected input values.
Only the five new tools' argument models are configured with hide_input_in_errors and extra=forbid;
schema/value errors retain field/type guidance without echoing names or rejected scope values.
This uses the SDK's internal tool metadata at registration (not a global monkeypatch); raw tools/list,
tools/call and schema tests guard the dependency. Review this boundary on future SDK changes.
No upstream bodies, names, search terms, asset IDs, filenames, coordinates or credentials enter
routine diagnostics. Operation labels for people reads/thumbnails contain no private IDs.

OpenWebUI checkout remains clean at **4ff4ca0** with its existing attachment-promotion code.
Its MCPClient passes input schemas and descriptions through, including nested filter schemas;
the live deployed artifact/overlays have not been verified. Native image content stays singular,
without duplicate base64 text/structured content. Deterministic retrieval, vision conversion and
attachment-persistence tests are distinct from unexecuted live browser/visual-quality checks.

Reproduce from **immich-mcp/**:

```bash
OPENWEBUI_CHECKOUT=/home/jmnovak/projects/open-webui /tmp/immich-location-check/bin/pytest -q
```

From the separate **open-webui/** checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend /tmp/immich-location-openwebui/bin/python -m pytest -q -p no:cacheprovider \
  backend/tests/test_mcp_content.py backend/tests/test_mcp_client.py \
  backend/tests/test_responses_tool_images.py backend/tests/test_responses_assistant_attachments.py
```

## Manual post-approval deployment, rollback and refresh — NOT EXECUTED

1. Review the follow-on diff and tests against **2c1e06b**, including new source/test/doc files.
   Preserve a complete patch including untracked files (`/tmp/immich-photo-discovery.patch`) in
   durable storage and record the deployment artifact. Preserve the preceding location/API fix.
2. Recheck systemctl WorkingDirectory/ExecStart/MainPID and the fresh import location from the
   service directory. Confirm one worker and no reload; if the launch changed, identify its real
   artifact. The verified checkout launch needs no wheel reinstall or application upgrade.
3. Retain existing config and credentials. Legacy supports name resolution, all-people combinations
   and metadata selection. Enabling structured v3.2 any/none is a **separate reviewed configuration
   choice**, after verifying the server remains compatible. Person discovery needs person.read;
   if absent, report the limitation and seek a separate permission decision. Do not rotate/relink
   credentials or grant broad permissions merely to make a demo pass. No migrations are needed.
4. Only after deployment approval, load the reviewed source and restart the MCP unit. Check
   localhost:8490 health/readiness, unauthenticated MCP denial and protected resource metadata.
   Preserve confidential OAuth clients, resource/audience, immich.read, account linking and secrets.
5. Refresh the existing ChatGPT developer connection's metadata and start a fresh chat, following
   the [official refresh procedure](https://developers.openai.com/plugins/deploy/connect-chatgpt).
   Confirm all five new tool descriptions and nested schemas; published connections have a separate
   update flow. In OpenWebUI reselect/refresh the existing connection and inspect its fetched tools,
   preserving OAuth Static configuration/access controls. No OpenWebUI patch, upgrade or restart
   is prescribed by this change. Do not infer metadata refresh from an old chat's tool catalog.
6. Run the acceptance checks below and record retrieval, model vision and visible attachments as
   separate outcomes. Forced permission/revocation/error tests belong in fixtures, not production.

Rollback after separate approval: at repository root run
`git apply --reverse --check /path/to/immich-photo-discovery.patch`, then reverse only that reviewed
follow-on patch if it applies cleanly. Review overlapping edits manually; never reset to 07512b2
or reverse the preceding location patch. Restore only optional config changed by a later approved
rollout. Then, with authorization, restart MCP and refresh both connectors. Retest the original
location tools and account boundaries. No credential/database rollback is needed; restart loses
active continuation handles, so existing traversals must be reported incomplete.

## Fresh-chat manual acceptance — NOT EXECUTED

- [ ] In both ChatGPT and OpenWebUI, verify connection status, resolve actual Jason/Brigid/Ava/Falyn
  records without assumed family aliases, disambiguate duplicates, and inspect a person thumbnail
  only when useful. Record separately any person.read limitation.
- [ ] Repeat the original Hawaii request: location suggestions and metadata pages, all media
  enumeration where requested, two matching photos with capture-date/state evidence. Record
  returned count/completion and actual visible attachments; call the photos a sample.
- [ ] Ask for both verified people in the stored Hawaii region, favoring sunsets and five different
  days. Required predicates must survive every bin/page. Show the actual bounded pool size and
  fewer than five if needed; explain judgment after limited thumbnail inspection, not scores.
- [ ] Where structured mode is separately approved, check either-person and named exclusions.
  “Only us” must retain the unnamed/undetected-person caveat. Check OCR signage separately from
  location. Do not force an unhealthy semantic call repeatedly; preserve its independent failure.
- [ ] Resolve “second one” to the displayed ID; verify same-place precision, the effective local
  afternoon and near-time ranges, and explicit reference access. Similarity remains unverified
  until a healthy live query succeeds. Lucy is not identified solely by a semantic result.
- [ ] Confirm thumbnail retrieval, model vision and **visible user attachments** separately. On
  OpenWebUI, verify persistence/reload and reuse of a single stored file as tool/assistant attachment.
  On ChatGPT use a supported returned attachment/file reference when available. Never duplicate
  base64 in text or copy the whole result into another library to solve rendering.
- [ ] Repeat authorized name/search/image reads as a second user. Own same-name records should
  differ; another user's private person/reference/continuation must not grant access. Keep Immich's
  intentional partner/shared access intact. Recheck filenames, recent assets, albums, public shares
  and prior location paths. Disconnection/revocation/forced faults remain deterministic fixture tests.
