---
name: immich-photos
description: Find, inspect, and display photos or small highlight selections with an already connected Immich MCP server in ChatGPT. Use for Immich photo requests, including exact filenames and album highlights.
---

Use the available Immich MCP connection; discover its actual tool namespace. This skill adds workflow guidance, not a file-transfer API. If the connector is unavailable, explain that it must be enabled.

Check `get_immich_connection_status` when status is unknown. On `connected=false`, stop private calls and show the returned `accountUrl`. Recheck after connection/reconnection. If the stored credential is invalid, direct the user to reconnect and stop private calls. Identity comes from verified authentication; never supply a username to select credentials or ask for keys in chat.

Reuse album and asset IDs. Resolve exact filenames with `find_asset_by_filename`, optionally scoped by album. Matching requires the full filename, case-insensitively; report ambiguity before choosing an asset. Semantic search is for visual concepts.

For one photo, fetch one `get_asset_thumbnail` result. For unspecified highlights, default to three displayed photos from at most six candidate thumbnails. Follow the server's configured counts and batch limit if different. Explicitly pass `size="thumbnail"` for browsing, using `preview` only for necessary detail. Await batches of at most two image calls before continuing; honor explicitly larger selections through additional bounded batches. Reuse successful results for display. State how many candidates were inspected; a sample is not an exhaustive review. Use `get_asset_image` only for requested native originals (possibly HEIC), never as a display workaround.

On partial failures retain successful images, report the unavailable portion, and do not automatically retry failed calls or refetch the entire selection. The server already retries transient failures. A user-requested retry should target only the failed image after current work finishes.

For visible output, check the capabilities actually exposed in this conversation:

1. Reuse any image attachment or file reference supplied with the successful tool result, using the host's documented display helper or attachment syntax. Do not invent file IDs, URLs, or paths.
2. If the tool execution runtime exposes the result object and a native image-emission helper, pass the image content object directly to that helper. Read that runtime's tool schema; helper names differ across hosts.
3. If visible output requires a sandbox file, proceed only when a programmatic bridge can transfer the existing result's bytes into the rendering runtime. Read the result object programmatically, decode its native image content once, and write bytes once with the matching extension. Return only the resulting file reference to the model. Use the receiving runtime's attachment syntax and confirm the file exists there. Separate runtimes do not share a filesystem merely because paths look alike.
4. If none of these capabilities exists, stop display work and clearly state that the image was retrieved for vision but this client has not exposed a supported way to attach it. Do not claim it is visibly displayed.

Never print, chunk, copy, or reconstruct image base64 through model-generated commands, prose, or tool arguments. Do not re-download an image to move it between runtimes. Do not publish private photo URLs or create public shares as a display workaround. Widget-only `window.openai` APIs are not shell or tool-runtime APIs and cannot be assumed available. A skill cannot create a missing attachment bridge.
