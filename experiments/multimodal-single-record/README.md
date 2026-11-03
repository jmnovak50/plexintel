# Single-record multimodal embedding experiment

Observed: 2026-11-03T14:47:58.981131+00:00. Recommendation: **GO** for a larger offline technical evaluation only.

## A. Selected movie

101 Dalmatians 2: Patch's London Adventure (2002); one pinned Plex rating key.

- `metadata.json`: original Plex JSON response bytes, stored locally (may contain media paths).
- `metadata.txt`: exact production serializer output, title and synopsis only.
- `metadata-complete.txt`: same title/synopsis plus all captured semantic movie fields; input to Tests A and C.
- Complete fields: title, summary, year, originalTitle, tagline, studio, contentRating, originallyAvailableAt, duration, rating, audienceRating, Genre, Director, Writer, Role, Country, Rating.
- Poster: 960 × 1440, 468,172 bytes; original Plex thumbnail bytes, no resizing or caption substitution.

## B. Environment

Client: `birch`. Ollama: `http://192.168.1.123:31770`, version **0.40.13**. Plex server: habanero, 1.43.5.11079-b3b13e506.

Model identities and digests:

- production: `embeddinggemma:latest`, parent `(none)`, BF16; digest `82f094e4c0e19bc4208c692996d4f1ecf14e82a8dee579ee1d2ca1175260058e`. Capabilities: embedding.
- experimental: `embeddinggemma-2:latest`, parent `embeddinggemma-2:740m-q8_0`, Q8_0; digest `f4981a15b99858ad1f2e0729416e526be7b4f428291b40082b9e4f7b27b5f62f`. Capabilities: embedding, vision, audio.

PlexIntel retrieves metadata through Tautulli (`fetch_tautulli_data.get_metadata`), stores it in `library`, and embeds `title — summary` (`_media_text_for_embedding`, `generate_media_embeddings`). `ollama_embeddings._post_embed` sends string lists to `/api/embed`, keep-alive 15m, with the configured top-level `num_thread` hint. This script extracts only the pure serializer AST and reproduces that request for one input. Settings use the existing resolver with database-enforced read-only connections. Tautulli supplies the Plex endpoint but redacts its PMS token; an existing PlexIntel OAuth token was read from `users`. Metadata/poster were fetched directly through Plex with `X-Plex-Token` headers. No credentials were saved.

API verification: Version-matched handler parses one object and forwards text plus decoded media to one Embedding call. [Installed-version source](https://raw.githubusercontent.com/ollama/ollama/v0.40.13/server/routes.go). The exact handler and its hash are captured locally. This verifies the tagged public implementation; successful live requests are the runtime evidence. [Model reference](https://registry.ollama.com/library/embeddinggemma-2).

Native payload (one input object produces one vector):

```json
{"model":"embeddinggemma-2:latest","input":{"text":"<complete metadata>","image":"<base64 original JPEG bytes>"},"truncate":false,"keep_alive":"15m"}
```

Poster-only omits `text`; metadata-only uses a one-item string list. No prefixes, dimension override, vector averaging, or concatenation are applied. Tests A/C and the matched-text control disable truncation. The baseline retains production defaults. The configured thread hint is copied exactly; this top-level field is absent from Ollama’s EmbedRequest options, so 16 configured threads does not establish 16 effective runner threads.

## C. Performance results

Seconds. Warm inference is the median of three identical warm requests, measured as Ollama `total_duration − load_duration`. It includes tokenization, image preprocessing/encoding, pooling, and request overhead on the server; Ollama does not report isolated inference-kernel time. Total is median warm client wall time, including HTTP/JSON transfer. Cold load is the first request’s reported load only when `/api/ps` showed the model absent immediately beforehand. Models are never explicitly unloaded. A shared model cold load is measured once; later modality rows show N/A when already resident.

| Configuration | Dimensions | Cold load | Warm inference | Total |
|---|---:|---:|---:|---:|
| Production EmbeddingGemma | 768 | 0.7942 s | 0.0365 s | 0.0398 s |
| EmbeddingGemma 2 — metadata | 768 | 1.5829 s | 0.3935 s | 0.3967 s |
| EmbeddingGemma 2 — poster | 768 | N/A | 6.0672 s | 6.0815 s |
| EmbeddingGemma 2 — combined | 768 | N/A | 6.5332 s | 6.5464 s |

| Configuration | First client total | Warm client min–max | Prompt tokens (first; warm) |
|---|---:|---:|---|
| production | 0.8379 s | 0.0397–0.0401 s | 64; [64, 64, 64] |
| metadata | 2.0092 s | 0.3955–0.3987 s | 580; [580, 580, 580] |
| poster | 6.0970 s | 6.0521–6.1078 s | 604; [604, 604, 604] |
| combined | 6.5412 s | 6.5133–6.5965 s | 1182; [1182, 1182, 1182] |
| production_text_control | 0.0418 s | 0.0406–0.0411 s | 64; [64, 64, 64] |

Every request’s load/total durations, token counts, client timing, resident-state snapshots, vector shape/norm/finiteness, and response path are in `results.json`. Original API responses including vectors are in ignored `raw-responses/`. No model files were downloaded.

## D. Findings

- Native joint format supported by inspected server/model: **True**; successful operations and failures are listed above.
- production: all four outputs valid `[1, 768]`, finite, nonzero; norm range 0.99999999–0.99999999. Largest post-request `/api/ps` model allocation 692,993,392 bytes (0.645 GiB); VRAM allocation 0 bytes.
- metadata: all four outputs valid `[1, 768]`, finite, nonzero; norm range 0.99999986–0.99999986. Largest post-request `/api/ps` model allocation 634,461,879 bytes (0.591 GiB); VRAM allocation 0 bytes.
- poster: all four outputs valid `[1, 768]`, finite, nonzero; norm range 1.00000008–1.00000008. Largest post-request `/api/ps` model allocation 634,461,879 bytes (0.591 GiB); VRAM allocation 0 bytes.
- combined: all four outputs valid `[1, 768]`, finite, nonzero; norm range 0.99999992–0.99999992. Largest post-request `/api/ps` model allocation 634,461,879 bytes (0.591 GiB); VRAM allocation 0 bytes.
- production_text_control: all four outputs valid `[1, 768]`, finite, nonzero; norm range 1.00000004–1.00000004. Largest post-request `/api/ps` model allocation 634,461,879 bytes (0.591 GiB); VRAM allocation 0 bytes.
- **Peak process RSS/VRAM consumption: N/A.** The remote API reports model allocation snapshots, not OS/container peak usage. Allocation is not total host memory, and post-request snapshots can miss transient image allocations. GPU type, CPU use, and competing workload are not established.
- “Cold” means model absent from Ollama’s resident list, not a cleared OS disk cache. No services were restarted and no models explicitly unloaded. Each model has one first request plus three repeats per configuration. Same-record caches and other server activity can affect these small samples.
- Installed EmbeddingGemma 2 files total 1,284,852,670 bytes (1.197 GiB). The allocation snapshots must not be treated as total runtime memory including the vision/audio projector. True daily memory requirements remain unmeasured. Model metadata distinguishes a 512-wide internal representation from a 768-wide output projection; measured outputs are 768-dimensional.
- Within EmbeddingGemma 2 only: metadata/combined cosine **0.919071**; poster/combined cosine **0.952338**. These measure representation differences for one movie, not recommendation accuracy.
- Combined warm server processing is **16.60×** metadata-only (+1560.4%); this includes actual poster encoding.
- metadata: **0.100×** production single-record warm client throughput (reciprocal median latency).
- poster: **0.007×** production single-record warm client throughput (reciprocal median latency).
- combined: **0.006×** production single-record warm client throughput (reciprocal median latency).
- production_text_control: **0.970×** production single-record warm client throughput (reciprocal median latency).

Production uses the shorter title/synopsis input; Test A uses complete semantic metadata. `production_text_control` is an additional EmbeddingGemma 2 run on the exact production text to separate text-length changes from model latency. All requests concern the same movie. These are serial single-record rates, not measured batch/daily capacity. No cross-model cosine is calculated; matching output dimensions does not make the two model spaces interchangeable.

## E. Recommendation

**GO** for larger offline evaluation. Native text, poster, and joint requests produced valid vectors on the installed server. Next evaluate a fixed offline sample for retrieval/recommendation quality, diversity, missing-art handling, cache effects, batching, and measured host peak memory. Daily-pipeline capacity remains unproven by one movie. Any adoption would require independent re-embedding and downstream evaluation.

## Reproduction and artifacts

From the repository root:

```bash
.venv/bin/python experiments/multimodal-single-record/experiment.py
# Rebuild the report without another inference call:
.venv/bin/python experiments/multimodal-single-record/experiment.py --report-only
```

Reuses `selected-record.json` and captured input files. Reruns overwrite timing/response artifacts for that same movie; preserve this directory first if comparing runs. Requires the project virtualenv and network access to configured services plus the public version-matched source. No new dependencies. Generated poster, original private metadata and vector responses are ignored by the experiment-local `.gitignore`. No commits were made. All writes remain in this directory.
