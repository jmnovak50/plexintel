# Gate B1 — read-only discovery validation

**Gate B2 recommendation: NO-GO.** Preview status: **partial**. Discovery pagination: **complete**; metadata enrichment: **incomplete**.

Window: **October 26–November 1, 2026 inclusive**, one all-language movie scope and one all-language TV scope. Observed 2026-10-28T20:58:23.125424-05:00 through 2026-10-28T21:14:48.273155-05:00 (America/Chicago). The preview UUID `b02b82ab-ccda-476a-81ae-96b633d3ca75` is a local execution identifier, not a persisted database run.

## Counts and pagination

| Type | Reported / unique source titles | Pages fetched / reported | Passed summary coverage | Detail successes / failures | Duplicates / invalid rows |
| --- | --- | --- | --- | --- | --- |
| movie | 811 / 811 | 41 / 41 | 811 | 807 / 4 | 0 / 0 |
| tv | 125 / 125 | 7 / 7 | 125 | 125 / 0 | 0 / 0 |

All reported pages were retrieved; no candidate-count truncation was imposed. The supported 500-page ceiling and shared 2500-attempt budget were not reached. Actual GET attempts: **984**, comprising 48 discovery calls and 936 detail attempts; **zero retries** and one-second minimum spacing. Neither page drift, missing pages nor identity duplicates were hidden as successful coverage.

## TV classification

| Classification | Titles |
| --- | --- |
| eligible | 120 |
| provisional | 5 |
| ineligible (implementation: excluded) | 0 |

| Classification | Reason | Titles |
| --- | --- | --- |
| eligible | `original_series_premiere_in_window` | 120 |
| provisional | `original_premiere_unknown` | 2 |
| provisional | `season_premiere_conflict` | 3 |

These classifications are scope/premiere-evidence judgments, not engagement scores or acquisition decisions. Original premiere plus corroborating dated Season 1 is required for eligibility; incomplete/conflicting evidence remains provisional. Ineligible summary rows, if any, are included in source/classification totals and audited separately from accepted/enriched candidates. Returning-season and episode dates never substitute for original series premiere. Unknown library/request status remains independent.

### Provisional TV evidence

| Title / TMDB ID | Discovery premiere | Detail premiere | Season 1 premiere | Reason |
| --- | --- | --- | --- | --- |
| Dead-End Job / 289517 | 2026-10-30 | 2026-10-30 | 2026-10-29 | `season_premiere_conflict` |
| Pulso Fílmico / 338525 | 2026-10-31 | 2026-10-31 | 2026-10-28 | `season_premiere_conflict` |
| Fracture américaine / 339670 | 2026-10-27 | 2026-10-27 | 2026-10-26 | `season_premiere_conflict` |
| 谈话到此结束 / 340297 | 2026-10-29 | unknown | unknown | `original_premiere_unknown` |
| 邻里风波，当善意不再廉价 / 340302 | 2026-10-26 | unknown | unknown | `original_premiere_unknown` |

## API failures and integrity warnings

| Title | Type / TMDB ID | Failure |
| --- | --- | --- |
| Damned | movie / 1798181 | ConnectionError; `network_retries_exhausted` |
| Giring | movie / 1792901 | ConnectionError; `network_retries_exhausted` |
| Codename: Xivarus | movie / 1791311 | ConnectionError; `network_retries_exhausted` |
| Bad Day at the Office | movie / 1217928 | ConnectionError; `network_retries_exhausted` |

Failed titles retain sanitized discovery metadata; no missing detail is treated as evidence of ineligibility. No retry, writer execution or budget expansion was attempted. Full endpoint/time/error evidence is retained in `http-audit.jsonl` and `preview.json`.

HTTP/transport observations: `{"200": 980, "ConnectionError": 4}`. CLI returned **2**. Source sanitization/collection and enrichment error categories are retained in the datasets. Pagination warning counts are zero where shown in the table; this does not make live pagination an atomic snapshot.

Expected warnings: `live_pagination_is_not_an_atomic_snapshot` and `upstream_region_and_account_settings_can_change_scope`. Completeness describes this configured Seerr scope, not all conceivable regional/account discovery populations. Movie primary release and original TV premiere do not establish digital availability.

## Metadata availability

Availability is measured across all unique captured typed IDs, using successful detail or explicitly labeled summary-only fallback. Unknown/blank and known-empty collections remain distinct; zero votes are observed counts, not missing values or a rejection criterion. Full presence-state distributions are in `sanitized-summary.json`.

| Type | Field | Unknown / blank | Known-empty |
| --- | --- | --- | --- |
| movie | synopsis | 140 | 0 |
| movie | premiere_date | 22 | 0 |
| movie | genres | 0 | 132 |
| movie | cast_members | 4 | 234 |
| movie | crew_members | 4 | 68 |
| movie | production_countries | 4 | 314 |
| movie | production_companies | 4 | 388 |
| movie | runtime | 238 | 0 |
| movie | release_events | 4 | 19 |
| tv | synopsis | 45 | 0 |
| tv | premiere_date | 2 | 0 |
| tv | genres | 0 | 34 |
| tv | cast_members | 0 | 34 |
| tv | crew_members | 0 | 79 |
| tv | production_countries | 0 | 66 |
| tv | production_companies | 0 | 65 |
| tv | episode_run_times | 0 | 117 |
| tv | season_premieres | 0 | 2 |

**Media status codes were unavailable for all 936 titles**; observed request states were also unknown/omitted. Association presence states remain explicit in the datasets; no title is inferred absent or unrequested. **22 successfully fetched movie details lacked a usable premiere date**, despite having discovery dates; no known movie detail date fell outside the selected window. These gaps are retained without a new movie-exclusion rule. Media/request codes and omitted/null states remain available in CSV/JSON. Missing association or Seerr UNKNOWN is not proof of library absence or of never having been requested. Country release events are movie metadata; TV episode runtimes and season evidence are reported separately.

## Representative examples

| Type / classification | Title | TMDB ID | Premiere | Reason / context |
| --- | --- | --- | --- | --- |
| movie | The Awakening | 1657630 | 2026-10-29 | movie discovery; no engagement filter |
| movie | The Mongoose | 1294189 | 2026-10-29 | movie discovery; no engagement filter |
| movie | Wild Horse Nine | 891621 | 2026-10-30 | movie discovery; no engagement filter |
| tv_eligible | Minimum Wage | 321221 | 2026-10-26 | original_series_premiere_in_window |
| tv_eligible | Nocturne | 292741 | 2026-10-29 | original_series_premiere_in_window |
| tv_eligible | The One About Matthew Perry | 333533 | 2026-10-27 | original_series_premiere_in_window |
| tv_provisional | Dead-End Job | 289517 | 2026-10-30 | season_premiere_conflict |
| tv_provisional | Pulso Fílmico | 338525 | 2026-10-31 | season_premiere_conflict |
| tv_provisional | Fracture américaine | 339670 | 2026-10-27 | season_premiere_conflict |

These examples aid review only; no top-N filter was applied. `representative-examples.json` additionally includes sparse/niche/no-vote examples. Every retrieved valid typed title, its source snapshots, outcome and TV reason is retained in the full datasets.

## Read-only proof and outputs

**Production discovery state was identical before/after: zero runs, zero canonical titles and zero observations.** The real CLI ran only `--dry-run`; capture instrumentation blocked database connections at both application and psycopg layers, with **zero connection attempts**. Its HTTP session allowed only GET discovery/detail endpoints. Separate inventory checks used enforced read-only PostgreSQL transactions and the strict V2 guard. The preview created no database records or Seerr requests.

The persistent configuration remained disabled and unchanged. No migration, writer, scheduling, model job, acquisition, recommendation change, service restart, commit or deployment occurred. The application implementation was not modified.

Private ignored output directory:

`/home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-28-gate-b1/`

- `preview.json`, `preview.log`: actual CLI result and structured progress/error log.
- `sanitized-summary.json`: reconciled counts, integrity checks, metadata distributions and recommendation.
- `candidates.json`: all sanitized discovery/detail snapshots, with detail errors.
- `candidate-summary.json`, `candidate-summary.csv`: auditable per-title projections and TV decisions.
- `representative-examples.json`: review examples.
- `http-audit.jsonl`, `execution-audit.json`: method/path/status and zero-database-connection proof.
- `database-before.json`, `database-after.json`: identical read-only inventory evidence.
- `final-boundary-check.json`: source/configuration hash and secret-scan results.

**The B2 blocker is the four failed movie-detail calls.** Provisional TV evidence and ordinary source metadata gaps remain retained under the existing discovery contract.

**Stop at B1.** Resolve or separately validate the failed/incomplete enrichment before authorizing B2 under the current runbook. A separately authorized targeted GET diagnostic may distinguish transient transport failure from a reproducible source issue; it must not silently become a writer, expanded discovery run or automatic retry. No such follow-up was executed.
