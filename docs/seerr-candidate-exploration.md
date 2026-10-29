# Read-only Seerr candidate exploration

`scripts/explore_seerr_candidates.py` is an independent experiment. It imports the existing database connector only when history is requested; it does not import application startup, app-settings bootstrap, schema utilities, training, scoring, ingestion, or acquisition code. It uses existing `requests`, `python-dotenv`, and `psycopg2` dependencies. No Docker execution is required.

The HTTP client allows only GET `/api/v1/discover/movies`, GET `/api/v1/movie/{positiveTmdbId}`, and GET `/api/v1/search` (the optional historical identity lookup). Redirects are refused. No Radarr endpoints are used. Database work runs in a PostgreSQL read-only repeatable-read transaction with statement and lock timeouts, followed by rollback.

## Reproduce the weekly snapshot

Run from the repository root with the existing virtual environment:

```bash
.venv/bin/python scripts/explore_seerr_candidates.py \
  --start 2026-10-26 --end 2026-11-01 \
  --sort-by primary_release_date.asc \
  --credentials-file .seer_creds \
  --output artifacts/seerr-exploration/2026-10-28-week \
  --history --history-sample 60
```

The dotenv credential file accepts `SEERR_URL` and `SEERR_API_KEY`, with the existing file's `SEER_URL` and `SEER_API_KEY` spellings also supported. Exported `SEERR_URL`/`SEERR_API_KEY` take precedence. Credentials never appear in output or command arguments. The root `.env` supplies the existing database configuration without overriding exported variables. The script reads the credential file without changing it. The repository's private-file helper has a stricter permission contract than the supplied file; this tool uses the existing dotenv dependency directly for that authorized file.

Dates are inclusive primary release dates. The script explicitly sends `primaryReleaseDateGte`, `primaryReleaseDateLte`, and `sortBy` (default `popularity.desc`). By default it preserves Seerr's configured language scope. `--language all` requests all original languages; Seerr's configured discovery region and user settings can still affect the candidate universe. A count different from the supplied 329 is reported, never trimmed or padded.

The completed baseline contains 333 titles. A prior popularity-sorted pass returned inconsistent page totals (329 on page 1, 333 on subsequent pages); its incomplete audit is preserved in `artifacts/seerr-exploration/2026-10-28-week-mixed-pages/`. Using the previously unused primary-date sort returned consistent 333-title/17-page coverage. This suggests upstream cache differences; their precise cause was not independently verified.

The separate all-language snapshot is in `artifacts/seerr-exploration/2026-10-28-all-languages/`. It used `--language all --sort-by popularity.desc`. To reproduce that collection, use those flags and that output directory. The two snapshots differ in collection times and sort, and have one differing English title despite equal English-language counts; they are not guaranteed nested/atomic populations. Both discovery and detail release-date observations are exported, including disagreements and missing detail dates.

Default request spacing is 0.3 seconds, with at most three retries after the initial attempt, a 25-second request timeout, and a maximum 60-second Retry-After wait. Authentication failures, redirects and exhausted rate limits stop further enrichment. Failed requests are not cached. Each missing detail remains visible and the multi-path approach defers it. Discovery page failures/count drift make coverage incomplete. A complete discovery/enrichment run exits 0; partial collection exits 2 with available datasets and an incomplete report; configuration/filesystem errors exit 1.

## Outputs

The dated output directory contains:

| File | Content |
| --- | --- |
| `analysis.md` | Generated field distributions, rule definitions, survivor counts, included/excluded examples, historical comparison and limitations |
| `candidates.json`, `candidates.csv` | One enriched row per unique discovery TMDB ID; credits and country/type/date release events are retained |
| `decisions.json`, `decisions.csv` | One row per title per approach, including all hard/soft exclusion reasons and qualifying paths |
| `distributions.json` | Numeric quantiles, missingness, genre/language/status counts and field coverage |
| `history_library.json` | Current movie library and aggregate engagement from retained history; no user identifiers |
| `history_matches.json` | Every selected historical title's lookup result, including failures/ambiguity |
| `history_candidates.json` | Current Seerr metadata for matched historical sample titles |
| `history_decisions.json`, `history_decisions.csv` | Per-historical-title decisions plus aggregate engagement |
| `history_comparison.json` | Rule retention and captured title-viewer engagement within the matched sample |
| `history_candidate_overlap.json` | Exact title/year overlaps between the discovery week and current library, including ambiguous matches |
| `manifest.json` | Dates, rules, coverage, sanitized request/cache provenance, history coverage, script/output SHA-256 hashes |

Generated data and cache live under ignored `artifacts/seerr-exploration/`; directories are owner-only and files are atomically replaced with mode 0600. Do not commit local engagement datasets or credentials. CSV protects spreadsheet formula prefixes; JSON preserves original text. Cache and exports omit Seerr user objects, requester identities/IDs, internal server URLs and paths.

## Cache and repeatable simulations

Successful sanitized responses are cached under `artifacts/seerr-exploration/cache/`, scoped by a hash of origin, credential, path and query. Online reads use entries at most 24 hours old by default. Use `--cache-ttl-hours 0` to collect fresh responses. That refresh can observe a changed upstream candidate population. Cache provenance distinguishes collection timestamps from analysis timestamps. Never treat old cached media/request state as fresh operational state.

To replay the same captured responses without network or database access:

```bash
.venv/bin/python scripts/explore_seerr_candidates.py \
  --start 2026-10-26 --end 2026-11-01 \
  --sort-by primary_release_date.asc \
  --credentials-file .seer_creds \
  --output artifacts/seerr-exploration/2026-10-28-week \
  --history --history-sample 60 --offline
```

Offline mode explicitly allows stale cache entries and marks them. It reuses `history_library.json` in the output directory. Keep a copy of a completed snapshot before replaying into that same output directory, since reports and manifests are regenerated. The cache still requires the same origin/credential scope; missing entries remain failures. Run without `--history` for Seerr-only exploration, or use `--history-sample 0` to collect library aggregates and weekly overlaps without historical Seerr searches.

The delivered reports were replayed offline after collection to validate reproducibility and include the final date-provenance fields. `collection_manifest.json` preserves the preceding live collection manifest; `manifest.json` describes the final cached replay with original per-response fetch timestamps. The first all-language collection's historical searches included HTTP 400 errors; the completed baseline corrected search URL encoding and populated the cache used by the final replay. Final historical comparisons have no HTTP failures: 57 unique matches, two unmatched titles, and one ambiguous match.

Optional rule configuration is a standalone JSON file, never a production setting. For example:

```json
{
  "popularity_min": 5,
  "votes_min": 20,
  "rating_min": 6,
  "runtime_min": 40,
  "completeness_min": 5,
  "niche_genres": ["Documentary", "Animation"],
  "niche_tmdb_ids": [],
  "person_ids": []
}
```

Pass `--rules /path/to/rules.json`. These are illustrative thresholds. The niche/person allowlists are deliberate global exceptions; they do not run personalized models. The completeness threshold is out of seven fields. Runtime, votes, language, genres and popularity are never common hard exclusions. Explicit adult/blocklist and existing standard-media/request workflow checks are proposed hard exclusions shared by all simulations. They are not activated anywhere. The 4K status is preserved separately and does not imply standard-media availability.

## Historical interpretation

There is no TMDB ID column in the live library model inspected on 2026-10-28. Matching uses one unique normalized exact title/year in Seerr's first search page and verifies it again against movie details. It is a heuristic; no fuzzy matching or Plex identity claims are made. Duplicate library editions mapping to one TMDB ID are excluded. Selection is bounded and deterministic: roughly one third strongest-engagement titles, up to one third zero-viewer library titles, and seeded remaining titles. The audit includes unmatched titles.

Engagement means distinct viewers per title and an exploratory engaged-viewer proxy of at least 50% maximum session completion or cumulative playback of at least half the current library runtime. Playback duration is seconds; library runtime is milliseconds. Repeat plays can inflate cumulative engagement. This does not reuse or modify training labels. Current ownership/request state is neutralized for historical *signal* comparison because otherwise owned historical films would all be workflow exclusions.

This analysis cannot estimate real acquisition recall or prospective performance: current metadata leaks future information relative to historical discovery, the library is already selected, rejected/non-acquired titles have no observable engagement, removed titles are missing, availability and follow-up periods differ, and no point-in-time discovery snapshots exist. Even high retrospective retention cannot validate the proposed thresholds.

Focused validation:

```bash
.venv/bin/python -m pytest -q tests/test_seerr_exploration.py
git diff --check
```
