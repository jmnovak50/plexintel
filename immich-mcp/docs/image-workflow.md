# Image workflow investigation and validation

The 2026-09-13 [location-search investigation](location-search.md) records a newer service
start, current server/library versions, error-boundary tests, and the manual checklist for
the capture-location changes. The observations below remain historical. Successful native
image retrieval still does not establish visible rendering in either live client.

## Evidence and boundaries (2026-09-11)

Both checkouts started clean. Plexintel: `main`, `845c007`; last Immich change
`e68577f`. No applicable AGENTS.md files were found in either checkout or ancestor
paths. OpenWebUI: detached `4ff4ca0`, above `17ef818`, `d5eb96e`, and supplied
v0.11.3 base `2a960a5`. No OpenWebUI files were changed.

The detected local `immich-mcp.service` has working directory
`/home/jmnovak/projects/plexintel/immich-mcp`, invokes that directory's
`.venv/bin/uvicorn app.main:create_app --factory` on port 8490, and started
2026-09-10 17:32:19 CDT. It has no auto-reload argument. Installed Uvicorn adds
its default app directory (the working directory) to the import path. Therefore
this unit should load checkout source on its next start. Its *currently loaded*
source cannot be proved from HEAD or these paths; it exposes no build fingerprint.
Nothing was restarted or deployed during this investigation.

The installed `app` package is a separate copy. Its retrieval code matches HEAD,
but its server/connection tool lack HEAD's expanded connection guidance. A direct
`.venv/bin/pytest` initially tested that installed package (73 passed), not the
edited source. `pythonpath = ["."]` now makes ordinary project pytest runs test
checkout source. Explicit `PYTHONPATH=.` also works. No installed packages in the
service virtualenv were modified.

Verified local environment: Python 3.13.5, MCP 2.1.1, httpx 0.28.1,
Pydantic 2.13.5, FastAPI 0.141.1, pytest 9.1.1, pytest-asyncio 1.4.0,
respx 0.23.1. OpenWebUI requirements pin MCP 1.27.2. Its 28 focused tests were
rerun in an isolated `/tmp/immich-openwebui-check` environment with that version,
not MCP 2.x. The TrueNAS container's installed versions and overlay files were
not inspected during this task.

The shared ChatGPT conversation could not be fetched. Album count 43, 18 parallel
calls, six successes/twelve failures, retry success, 2.5-second latency, and the
525,220-character transfer are user-supplied observations of assistant reports,
not independently measured traces. The small local log file contained no
recognized image errors or useful retrieval measurements. The conversation-length
error's cause remains unproven.

## Separate stages and findings

| Stage | Confirmed locally | What remains unknown |
| --- | --- | --- |
| Retrieval | Immich image GET streams enforce Content-Length and received-byte checks. Default limit 10,000,000 bytes. GETs can retry twice after transient HTTP/transport failures. httpx read timeout 15s, connect timeout 5s. There was no total deadline or image admission limit. | Actual deployed Immich image dimensions/bytes, upstream load, and status/latency of the reported failures. |
| Serialization | `get_asset_thumbnail` has `structured_output=False` and emits one native MCP image; no text duplicate or structured base64. Its existing default is preview. Originals retain their bytes/MIME, including HEIC. | Client-specific payload ceilings and context accounting. |
| Error translation | MCP 2.1.1 wraps ordinary exceptions as `UnexpectedToolError`, masking their messages. Most sanitized Immich errors previously escaped as ordinary exceptions. 401/403 were already deliberate tool errors. | Which upstream error, if any, produced the reported generic failures. |
| Client ingestion | OpenWebUI's MCP client preserves image content; its helper turns images into vision inputs and removes encoded bytes from text context. | ChatGPT's internal ingestion/attachment implementation for this account and conversation mode. |
| Rendering | OpenWebUI persists once, retains the resulting file URL in tool output, and promotes that same URL to final message files. The frontend omits input_image from textual tool output and consumes existing file mechanisms. | Live browser rendering after refresh and the TrueNAS overlay's actual state. ChatGPT vision success alone does not prove visible attachment output. |

Image dimensions are controlled by Immich's thumbnail/preview generation settings,
not this MCP. No verified live dimensions were available, so no pixel values are
claimed and no resizing/decoder dependency was added. The byte ceiling applies to
binary response bytes; base64 adds roughly one third to wire size (a 10 MB image
can produce about 13.33 MB of encoded data). That arithmetic does not prove a
conversation-length failure or that encoded bytes were counted as text tokens.
The observed manual text transfer is avoidable work, independent of its role in
any earlier error.

## Implemented changes

- Server instructions: one image for one photo; default three highlights from no
  more than six candidate thumbnails; two image calls per awaited batch; explicit
  larger selections through additional batches. Reuse IDs and successful results,
  identify samples honestly, and do not automatically reissue failed selections.
- Thumbnail descriptions explicitly request `size="thumbnail"` for browsing,
  previews for necessary detail, and reference reuse for display. The existing
  preview default and individual tools remain compatible. Size schemas now expose
  the actual supported enum. Native originals remain untouched.
- Image-only admission: two active downloads per credential and six per process.
  Credential waiters acquire their own slot before global capacity, so one user's
  queued work cannot reserve all global slots. Entries use digests and disappear
  after active/waiting calls finish; no image cache or cross-user result reuse.
  Different users sharing the same actual upstream credential share its quota.
- Admission waits at most two seconds and returns a sanitized `ImmichImageBusy`.
  Admitted work has a 45-second total deadline covering retries and streaming.
  Existing per-attempt timeout and retry count remain; no outer retry layer.
  Slots and response streams are released on failure, deadline, and cancellation.
- Expected private Immich errors become deliberate MCP `ToolError`s with category
  and no-automatic-retry guidance. Public individual image errors receive the same
  treatment. A 403 now acknowledges either key scope or asset/album permissions.
- Image redirects remain disabled, including for injected HTTP clients. Redirects
  receive a clear error rather than being interpreted as image bodies. No
  credential forwarding or fullsize redirect resolution was added.
- One sanitized `immich_image_retrieval` event per image request records logical
  image tool, requested size, last HTTP status, attempts, received bytes for the
  last attempt, duration (including admission), and error category. No URLs,
  identifiers, credentials, image bodies, exception strings, or tracebacks are
  included by this diagnostic. A failed admission has zero attempts and no status.
  Existing httpx/httpcore request logging remains suppressed by application setup.

Defaults in `.env.example`:

| Variable | Default | Scope |
| --- | ---: | --- |
| IMAGE_MAX_CONCURRENCY | 6 | Active images per process |
| IMAGE_PER_CREDENTIAL_CONCURRENCY | 2 | Active images per upstream credential |
| IMAGE_QUEUE_TIMEOUT_SECONDS | 2 | Maximum admission wait |
| IMAGE_TOTAL_TIMEOUT_SECONDS | 45 | Entire admitted retrieval |
| IMAGE_HIGHLIGHT_COUNT | 3 | Model workflow guidance |
| IMAGE_CANDIDATE_LIMIT | 6 | Model workflow guidance |

These are conservative starting limits, not a measured Immich capacity result.
Counts in instructions are guidance, not a server-wide conversation quota. The
server enforces simultaneous retrieval bounds; multiple workers multiply the
process-wide limit. Metadata operations bypass image admission. Requests already
serialized by a client continue normally. Oversized originals still fail the
existing byte ceiling and unusually slow originals can hit the new configurable
deadline; successful originals are never converted or truncated.

No new gallery tool was added: bounded individual calls preserve successful
results during partial failures and do not add multi-image payloads. A gallery
returning native image blocks would not itself fix ChatGPT attachment rendering.
The existing public-share gallery remains available; its enumeration/partial
failure behavior was not redesigned in this focused fix.

Authentication remains Authentik OAuth/OIDC (confidential client, `immich.read`)
followed by the authenticated user's encrypted server-side Immich key from
`/account`. No auth configuration, identities, credential records, secrets,
WEBUI_SECRET_KEY, filename search, flat album metadata search fields, or people
features were changed.

## ChatGPT display and optional workflow draft

The [draft plugin](../chatgpt/immich-photo-workflow) contains a capability-aware
[skill](../chatgpt/immich-photo-workflow/skills/immich-photos/SKILL.md) and a validated
compatibility manifest. It is skills-only and uses the user's existing MCP
connection, preserving its confidential-client OAuth setup. Nothing is installed
or published automatically.

The skill first reuses a host-provided image/file reference, then a documented
native image-emission helper if available. Only when a real bridge exposes bytes
programmatically may it decode once and write once in the receiving rendering
runtime. It never asks the model to transcribe base64 or assumes shared filesystems.
If no bridge exists, it reports the display limitation and stops that work.

Official documentation establishes optional widget APIs (`uploadFile`,
`selectFiles`, `getFileDownloadUrl`) and MCP UI resource templates. These are
widget-context capabilities; they do not establish an arbitrary tool-runtime to
ChatGPT sandbox transfer API, nor make a native ImageContent automatically into
a final assistant attachment. They are not present in this server, and this
session has no connected Immich tool or authenticated ChatGPT browser to test.
See the [OpenAI plugin UI reference](https://developers.openai.com/plugins/reference)
and [MCP server guide](https://developers.openai.com/plugins/build/mcp-server).
An optional widget would require a separate authenticated delivery/UI design;
private public-share links are not an acceptable shortcut. Repository instructions
and a skill cannot supply an absent platform attachment bridge.

To install the draft on a supported desktop/local plugin surface, copy the
`immich-photo-workflow` folder to `~/plugins/immich-photo-workflow`. Merge this
entry into the existing `plugins` array in `~/.agents/plugins/marketplace.json`,
preserving existing entries and marketplace identity (create a root object with
`"name":"personal"` and a `plugins` array only if the file does not exist):

```json
{
  "name": "immich-photo-workflow",
  "source": {"source": "local", "path": "./plugins/immich-photo-workflow"},
  "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
  "category": "Productivity"
}
```

Restart the desktop app, open its Plugins Directory, select the personal
marketplace and install this plugin. Enable the existing Immich connection in a
fresh chat. Verify the installed skill actually appears before relying on it.
This local workflow is not a claim that a web-only ChatGPT connector can import
local skills. If unavailable, use the server instructions and report that the
optional skill could not be installed. See [OpenAI plugin packaging](https://developers.openai.com/plugins/build/plugins)
and [skill guidance](https://developers.openai.com/plugins/build/skills).

## Local validation

Final source suite with cross-check: **88 passed**. This includes original account,
credential encryption/isolation, OIDC, shared-link, byte-limit, exact filename,
flat albumIds/order/page/size, and native image tests, plus 15 new cases.
New tests exercise protocol serialization and errors, ASGI authentication/context
isolation, missing scope/token denial, stream timeout cleanup, admission and
cancellation, retries, redirect refusal, and the actual OpenWebUI content helpers.

OpenWebUI's four original focused files: **28 passed**, with two Typer/Click
deprecation warnings. Persistence is exercised via test callbacks; the added
cross-check writes a synthetic PNG once and reuses its file URL. This verifies
helper behavior, not a running OpenWebUI database/storage backend or browser.
Source review confirms middleware invokes normal `get_file_url_from_base64`, then
`Chats.add_message_files_by_id_and_message_id` and `chat:message:files` without a
second binary write. Skill and plugin structural validators pass.

Reproduce from the MCP directory:

```bash
OPENWEBUI_CHECKOUT=/home/jmnovak/projects/open-webui .venv/bin/pytest -q
```

The cross-check skips when OPENWEBUI_CHECKOUT is unset. Some sandboxed Python
invocations stalled on async SQLite worker wakeup; the full run succeeded outside
the sandbox with mocked upstream requests and temporary databases.

Reproduce the existing OpenWebUI suite from its checkout using the isolated test
environment created for this task:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend \
  /tmp/immich-openwebui-check/bin/python -m pytest -q -p no:cacheprovider \
  backend/tests/test_mcp_content.py backend/tests/test_mcp_client.py \
  backend/tests/test_responses_tool_images.py \
  backend/tests/test_responses_assistant_attachments.py
```

## Manual deployment and connector refresh — not executed

For the detected local systemd installation, after reviewing/authorizing deployment:

1. Preserve the current diff for rollback before any further edits:
   `git diff --binary -- immich-mcp > /tmp/immich-image-workflow.patch` from repository root.
   Retain a copy somewhere durable. Review `git diff --check` and the tests above.
2. Confirm the unit still uses the recorded working directory and Uvicorn command:
   `systemctl show immich-mcp.service -p WorkingDirectory -p ExecStart --no-pager`.
   If it now points to a container or different installation, stop and adapt the
   deployment to that actual artifact; do not assume this source tree is used.
3. Existing defaults require no `.env` edit. Optional tuning changes only the six
   IMAGE_* variables above. Preserve all OAuth/client-secret, encryption, account,
   database, and OpenWebUI secret settings. This change requires no migrations or
   dependency upgrades. Do not follow the README's first-install key-generation
   instructions for this existing deployment.
4. In `/home/jmnovak/projects/plexintel/immich-mcp`, verify the intended import:
   `PYTHONPATH=. .venv/bin/python -c 'import app.mcp.server; print(app.mcp.server.__file__)'`.
   Uvicorn's default app directory should produce that same source origin. This
   unit uses source; rebuilding/reinstalling the stale wheel copy is unnecessary
   for this unit and was not performed.
5. Only after deployment authorization: `sudo systemctl restart immich-mcp.service`.
   Check `curl -fsS http://127.0.0.1:8490/health` and then `/ready` on that origin.
   Check public `/mcp` authentication and protected-resource discovery. Do not
   export raw private tool responses or credential-bearing request logs.
6. In ChatGPT Plugins, open the existing connection and select **Refresh**. Confirm
   updated image descriptions/size enum, then start a fresh conversation with the
   connection enabled. Preserve its confidential OAuth client configuration and
   `immich.read`. Published plugins instead require their metadata review/update
   flow; see [official refresh instructions](https://developers.openai.com/plugins/deploy/connect-chatgpt).
7. OpenWebUI needs no patch, upgrade, container restart, or TrueNAS overlay change.
   Start a fresh chat and reselect the existing Immich tool connection so its
   tool list is fetched again. Confirm the new description/enum in available tools.
   If metadata stays cached, reconnect that existing tool entry through the UI,
   preserving OAuth Static settings and existing access controls. Reauthorize
   through Authentik only if prompted; never replace OAuth with an Immich key.

The public route to this local unit and TrueNAS's deployed overlay were not
independently verified. Health readiness is not a substitute for the client checks.

## Fresh-chat acceptance checklist — run separately in both clients

- [ ] Unconnected user: status checked first; `connected=false` shows the returned
  accountUrl; no private retrieval follows. Connect at `/account` and confirm a
  status recheck. A revoked key directs reconnection and stops private work.
- [ ] Connected album: retrieve the intended album and confirm its actual current
  count/permissions. Reuse that ID in follow-up calls.
- [ ] One photo: exactly one image retrieval; the photo is visibly attached and
  usable for vision. Distinguish a correct description from actual rendering.
  In OpenWebUI inspect one stored file URL shared by tool and assistant outputs,
  without encoded bytes in frontend JSON or a second upload. Reload the chat.
- [ ] Highlights: default three displayed from at most six thumbnail candidates,
  at most two image calls in flight. State sample size. Avoid re-fetching successful
  images merely to display them. Explicit larger requests proceed in bounded batches.
- [ ] Exact filename: mixed-case complete filename uses find_asset_by_filename,
  optionally with the known album ID; duplicate matches remain explicitly ambiguous.
- [ ] Shared access: two separate authenticated users see only their allowed
  albums/assets; a denied private asset stays denied even with another user's ID.
  Exercise public shared-link access separately from user-shared private albums.
- [ ] Partial failure: in a development fixture, make one image fail (404, 429,
  503, timeout), retain successes, report the unavailable portion, and observe no
  automatic retry loop. Use sanitized diagnostics for attempts/status/duration;
  do not force faults or high-load fan-out on production.

## Rollback

Before deploying, verify the saved patch includes only this task's changes. From
repository root, `git apply --reverse --check /tmp/immich-image-workflow.patch`
then `git apply --reverse /tmp/immich-image-workflow.patch` restores the previous
tracked source. If the check fails because later edits overlap, restore only
reviewed hunks manually; do not use git reset or overwrite other work. New test,
documentation, and draft-plugin files can remain inert. Revert only IMAGE_* settings
added for this change. No database/credential rollback or secret rotation is needed.
After explicit authorization, restart the MCP unit and refresh the ChatGPT metadata
again, then repeat one-photo and connection checks. Disable/uninstall the optional
skills-only plugin if installed. OpenWebUI requires no rollback change.

## Discovery follow-on

The additive people/combined-search and bounded photo-selection workflow is documented in
[photo-discovery.md](photo-discovery.md). It uses the same authorized image tools and limits.
Metadata sampling downloads no images. Native retrieval, model vision and visible attachments
remain separate checks; no OpenWebUI deployment or rendering behavior is inferred from fixtures.
