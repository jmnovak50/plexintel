# Gate B1 — targeted remediation and independent verification

**GO for separately authorizing Gate B2. Gate B2 was not executed.** All four missing movie details were recovered with exactly one new GET per identity. No persistent per-title failure was observed on this check; the original connection errors did not recur, which is consistent with transient transport failures. Their exact original cause remains unproven.

The **October 26–November 1, 2026** preview window and all **936 original typed candidate identities** are unchanged. The original partial preview, its four error events and all original artifacts remain intact. This report reconciles that snapshot with four later observations; it does not relabel the original CLI result as success or claim a new simultaneous population snapshot.

## Request outcomes and limits

Exactly these four requests ran on October 28 at **21:23:45–21:23:48 CDT**, using the existing approved Seerr source and credentials. No status/authentication, pagination, TV or successfully enriched movie endpoint was queried.

| Original title | Movie TMDB ID | New requests | Result | Identity | Premiere | Runtime | Elapsed |
| --- | ---: | ---: | --- | --- | --- | --- | ---: |
| Damned | 1798181 | 1 | HTTP 200 | Matches | 2026-10-29 | 19 min | 0.467 s |
| Giring | 1792901 | 1 | HTTP 200 | Matches | 2026-10-29 | Unknown: source zero | 0.153 s |
| Codename: Xivarus | 1791311 | 1 | HTTP 200 | Matches | 2026-10-29 | 16 min | 0.166 s |
| Bad Day at the Office | 1217928 | 1 | HTTP 200 | Matches | 2026-10-30 | 112 min | 0.142 s |

Each request used **timeout=10 seconds**, **zero automatic retries**, disabled redirects and a transport retry budget of zero. Request starts were at least one second apart (minimum observed **1.000067 seconds**). A fixed allowlist and already-attempted-ID guard prevented additional identities, duplicate attempts, pagination or non-GET calls. Database connections were blocked in the diagnostic process, with **zero attempts**. Sanitization reused the existing movie allowlist; credentials, private URLs and requester identities were not logged.

HTTP 200, valid JSON, matching positive integer TMDB identity and successful metadata sanitization establish successful retrieval in this observation. They do not prove permanent service stability, digital availability or library/request absence. The original error audit retained only a fixed `ConnectionError` category; retrospective network/server root-cause attribution is not possible from that evidence alone.

## Count and identity reconciliation

| Measure | Original B1 | Reconciled evidence |
| --- | ---: | ---: |
| Unique movies | 811 | **811** |
| Unique TV series | 125 | **125** |
| Unique typed identities | 936 | **936, exact same set** |
| Successful movie details | 807 | **811** |
| Successful TV details | 125 | **125** |
| Unresolved detail retrievals | 4 | **0** |
| Movie details with unusable premiere dates | 22 | **22** |
| Unknown movie runtimes | 238 | **235** |
| TV eligible / provisional / ineligible | 120 / 5 / 0 | **120 / 5 / 0** |
| Unknown library/request status | 936 | **936** |
| Actual GET attempts | 984 | **988 cumulative: only 4 new** |

The original **41 movie pages and 7 TV pages** were not fetched again. The original pagination integrity result remains historical evidence for that original population/window. Existing successful details were not refetched. The later overlay updates only the four failed movie identities; no media-type collision, additional candidate or hidden exclusion was introduced.

## Independent handling verification

Offline checks independently tallied the captured source values before comparing normalization/classification output. All checks passed, with network and database calls prohibited during verification. A separate reviewer independently confirmed the same data counts and semantics without database/network access or edits.

### 22 unusable movie premiere dates

All 22 successful original detail responses contain **`releaseDate=''`**, rather than a usable date. Each title retains a valid, in-window discovery-summary date. Normalization returns an unknown/nullable canonical premiere; it does not turn the blank into a digital-release date, discard the discovery-date evidence or exclude the candidate.

The presence annotation `value` records a present string of the expected source shape; it does **not** make an empty string a usable date. Parsed date and source snapshot must be inspected together. No new date was inferred or imputed. All four recovered details have valid dates matching their original discovery summaries, so the unusable-date count remains 22.

### 238 originally unknown movie runtimes

The original 238 reconcile exactly to **234 successful details with source runtime zero**, plus **four failed details without a runtime**. Zero normalizes to `None`/`zero_unknown`, not a zero-minute film, a default duration or exclusion. Failed enrichment leaves the field unknown and the candidate retained.

The follow-up supplies three positive runtimes; **Giring still reports zero**. The reconciled unknown total is therefore **234 + 1 = 235**. The original 238 is preserved in the original dataset; these three resolutions are later evidence, not values retroactively known at the initial preview time.

### Five provisional TV candidates

No TV detail call was repeated. Independent date comparisons and the implemented classifier agree:

| TV title / TMDB ID | Original premiere | Season 1 premiere | Result |
| --- | --- | --- | --- |
| Dead-End Job / 289517 | 2026-10-30 | 2026-10-29 | Provisional: `season_premiere_conflict` |
| Pulso Fílmico / 338525 | 2026-10-31 | 2026-10-28 | Provisional: `season_premiere_conflict` |
| Fracture américaine / 339670 | 2026-10-27 | 2026-10-26 | Provisional: `season_premiere_conflict` |
| 谈话到此结束 / 340297 | Unknown; discovery says 2026-10-29 | Unknown | Provisional: `original_premiere_unknown` |
| 邻里风波，当善意不再廉价 / 340302 | Unknown; discovery says 2026-10-26 | Unknown | Provisional: `original_premiere_unknown` |

The other 120 have a usable in-window original premiere corroborated by a matching dated Season 1 and no contradictory evidence under the implemented rules. The three date differences do not themselves prove returning-season activity or establish their exact cause. All five uncertain titles remain retained and auditable; none was silently promoted to eligible or excluded.

### Missing media/request status

All **936 original source projections omit `mediaInfo`**, and all four follow-up details also omit it. Standard/4K media status remains `None`; association and requests presence states remain `omitted`; request count remains **unknown (`None`), not zero**.

Offline positive/negative controls additionally verified distinct handling of omitted association, explicit-null association, null nested status/requests, an explicitly supplied UNKNOWN code, an explicitly empty request array and an explicitly observed status code. A previously known available code does not become current availability merely because a new response omits status. Known-empty request metadata describes that response collection, not lifetime request absence or permission to acquire.

## Meaning of the states

- **Discovery candidate:** a valid typed identity retained from the configured discovery scope. Movies are not assigned a new eligibility score at this layer; missing premiere/runtime detail does not silently remove them.
- **Eligible TV:** original-series premiere evidence satisfies the configured window and corroborating Season 1 rules. This is not an engagement prediction, acquisition score, library-absence assertion or availability claim.
- **Provisional TV:** supporting premiere/season evidence is incomplete or contradictory. Retain it with diagnostics for later resolution; do not equate it with ineligibility.
- **Unknown metadata/status:** source information is omitted, null, blank, invalid or a documented zero placeholder. Preserve its provenance and uncertainty; do not infer absent, unrequested, ineligible, released or available.
- **Ineligible/excluded TV:** positive scope/category evidence supports exclusion, such as a confirmed old original premiere outside the window or the existing special-category rule. An offline established-series control confirms exclusion follows the old original date, not missing runtime/status. No original TV title in this population was excluded.
- **Failed enrichment:** a retrieval outcome separate from discovery membership and metadata truth. Original summaries remain evidence; previously successful canonical metadata is not replaced by failure. No GET failure is a deletion/absence signal.

Neither a movie primary release date nor a TV original/season premiere proves digital availability. Unknown library/request status is acceptable to store as unknown in discovery persistence; any future acquisition decision would require its own separately authorized status/readiness checks. No acquisition action is part of B2 or this task.

## Audit evidence and operational boundaries

Private ignored output directory:

`/home/jmnovak/projects/plexintel/artifacts/seerr-exploration/2026-10-28-gate-b1-targeted/`

- `targeted-results.json`, `targeted-requests.jsonl`, `request-outcomes.log`: four sanitized responses and method/path/identity/status/timing/timeout/retry evidence.
- `targeted-details-overlay.json`: exactly four later observations, retaining original failure codes and fetch provenance.
- `reconciled-summary.json`: count reconciliation, measured spacing, identity-set checksum and recommendation.
- `reconciled-candidate-audit.json` / `.csv`: all 936 typed identities with original/later provenance, nullable metadata and TV states/reasons.
- `semantic-verification.json`: independent source tallies, normalization checks and presence-state controls; no network/database operations.
- `database-before.json`, `database-after.json`: identical read-only inventory checks, **zero runs / zero titles / zero observations**.
- `independent-review.md`, `final-boundary-check.json`, `artifacts-hashes.json`: review and complete file/configuration/original-evidence integrity records.

The immutable original evidence remains under `2026-10-28-gate-b1/`, including the original partial result and original 984-request audit. The overlay does not refresh the rest of that snapshot. Source identity and endpoint binding are unchanged. No application implementation, migration, model/scoring/training input or production configuration changed. No production database write, synchronization, scheduling, service restart, acquisition, commit or deployment occurred. Discovery remains **disabled**.

**Recommendation: GO for seeking separate Gate B2 authorization on the reconciled evidence.** The four retrieval blockers are resolved; the 22 unknown dates, 235 remaining unknown runtimes, five provisional TV cases and unknown statuses remain explicit under the existing discovery contract. A future B2 execution is a new live operation with its own approved request budget, complete-pagination checks and post-write validation; population/metadata may have changed since B1. No B2 command was executed. **Stop here.**
