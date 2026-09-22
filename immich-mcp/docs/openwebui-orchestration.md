# OpenWebUI compound-search orchestration

## Confirmed cause and source state

The observed “Lucy in New Orleans” response lost two mandatory constraints in orchestration. The
model chose `search_location_assets`, whose public contract intentionally supports capture location,
date and media type only, then described location matches as Lucy photos without person evidence or
visual inspection. `list_album_assets` also returns compact asset metadata without detected-person
evidence, so its empty or unverified identity conclusions were not grounded.

The server already had most of the correct composed path. `search_library` preserved people,
location, capture dates, media type, OCR, semantic/reference criteria, authorization context and
continuations. Its internal request builder already supported `albumIds`, and continuation sessions
already froze the original body and reauthorized an `albumId`. The public `DiscoveryFilters` omitted
`album_id`, and `search_library` therefore never supplied that internal capability. This change adds
the missing field instead of adding another search tool.

The repository did not contain the handoff's proposed `openwebui/immich_display.py` or
`openwebui/test_immich_display.py`. The running OpenWebUI container was not available in the local
Docker context, so its Workspace Tool source could not be exported read-only. The validated image
helper was not recreated or changed. `openwebui/system-prompt.txt` is an additive, reviewable prompt
source for a later manual client update.

## Search and completeness contract

`DiscoveryFilters.album_id` accepts one resolved Immich UUIDv4. The server authorizes that album
with the current user's own Immich credential, combines album membership with every supplied filter,
and uses the selected configured API mode:

```json
{
  "filters": {
    "album_id": "<authorized album UUID>",
    "people_all": ["<resolved Lucy person UUID>"],
    "city": "New Orleans",
    "state": "Louisiana",
    "media_type": "IMAGE"
  },
  "limit": 50
}
```

Legacy mode emits flat `albumIds`, `personIds`, location, date and type fields. Structured mode emits
the same constraints under `filter` with `albumIds: {"all": [...]}` and matching operators. The
shapes are never mixed. A continuation call accepts only its opaque continuation handle; the frozen
body, account fingerprint and authorization context are reused. Only `complete=true` establishes
complete traversal of matching accessible metadata. Missing face or capture-location metadata can
still omit real photos, and the library is not a transactional snapshot.

## Image and full-resolution behavior

Metadata enumeration, visual inspection and visible attachment are separate operations. The current
controlled Workspace Tool uses native image continuation for inspection and a verified display helper
for at most three final attachments. Photo-book, quality and diversity judgments require sequential
inspection of a bounded shortlist; adjacent or similar metadata alone does not prove duplication.

The controlled helper's reviewed source is not in this checkout, so this change does not claim safe
native-original attachment support. The prompt directs explicit full-resolution requests to a clear
limitation response and forbids using `get_asset_image` as an improvised display path. Originals may
be HEIC or exceed practical client limits even though the MCP endpoint itself enforces ownership,
MIME/signature and byte limits. Preview display remains the supported behavior until the helper source
can be exported, reviewed and tested.

## Manual post-approval update and validation

No deployment or client update was performed. After approval:

1. Deploy the reviewed Immich MCP source using the existing service procedure, then restart only that
   service and verify its checkout/import origin. Refresh the external MCP tool metadata in OpenWebUI
   or reconnect it so the `search_library` schema includes `filters.album_id`.
2. Update the OpenWebUI model/system prompt from `openwebui/system-prompt.txt`. Do not replace the
   existing Workspace Tool image helper. Start a fresh chat so cached schemas and instructions do not
   influence the test.
3. Prompt: “From Lucy's Big Adventure, show me all photos of Lucy in New Orleans.” Expected sequence:
   `list_albums`/`get_album` as needed; `find_people` as needed; one `search_library` call containing
   album ID, resolved Lucy ID, New Orleans capture metadata and `IMAGE`; continuation-only calls until
   `complete=true`; inspect only bounded display candidates if identity/visual selection needs it; one
   `display_immich_photos` call with at most three verified IDs. Report the complete metadata match
   count and call the attachments a subset when more than three exist.
4. Prompt: “Show me three photos taken in New Orleans.” Expected sequence: location suggestions if the
   stored spelling is uncertain, `search_location_assets` with no invented person/album constraint,
   bounded inspection if needed, then one display call.
5. Prompt: “Find the best three pictures from Lucy's Big Adventure for a photo book.” Expected sequence:
   resolve album; build a bounded diverse metadata shortlist; perform at most six sequential
   `inspect_immich_photo` calls in the parent chat; reject near-duplicate winners; make one display call
   with up to three inspected IDs; disclose that this ranks the inspected shortlist.
6. Prompt: “Show me the full-resolution versions of those photos.” Expected behavior: explain that the
   controlled helper currently supports previews and cannot safely attach native originals. It must not
   call `get_asset_image`, fabricate a URL, or make a display claim.
7. Verify the final tool result contains `attached_selection`, all selected assets remain in the same
   user's authorized album/intersection, and the photos are visibly attached. Repeat in a second user's
   private chat and confirm no IDs, people, albums, continuations or saved displays cross accounts.
8. Run branch/reuse checks: branch after a prior display, ask for “the second photo again,” and confirm
   `get_last_immich_display` resolves the branch-relative saved selection. Confirm internal subagent
   attempts to inspect, display or reuse parent-chat images remain rejected.

Rollback is source-only: restore the prior reviewed files and service artifact, refresh MCP metadata,
and restore the prior OpenWebUI system prompt. Keep the existing Workspace Tool and OpenWebUI native
image-continuation patch unchanged. Database migrations, configuration changes and credential changes
are not involved.
