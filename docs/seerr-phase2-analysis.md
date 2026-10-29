# Seerr global curation: Phase 2

The results are in `artifacts/seerr-exploration/2026-10-28-phase2/`. Start with `phase2-findings.md` and the 50-title `candidate-review.md`, especially its excluded section. The directory is private and ignored by Git. Phase 1 results and their cache remain immutable inputs.

This analysis does not run production embedding/scoring/training modules. It inspects a trusted local model artifact for its feature names/tree topology, reads aggregate profile counts and nonsecret embedding settings in a PostgreSQL read-only transaction, and benchmarks synthetic NumPy allocations/cosine matrices. It does not call model fit/predict or Ollama. The active backend is a direct Python deployment; Docker is not involved.

## Replay the delivered analysis without network or database calls

```bash
.venv/bin/python scripts/analyze_seerr_phase2.py \
  --output artifacts/seerr-exploration/2026-10-28-phase2
```

The replay reuses the existing Phase 1 datasets/cache and captured Phase 2 evidence. It regenerates Phase 2 reports, deterministic sampling, CSV/JSON exclusions, inactive policy proposal and output hashes. It verifies Phase 1/protected source fingerprints before and after analysis. It does not rewrite Phase 1 outputs. `input-integrity.json` contains fingerprints for the three Phase 1 result directories, their cache and the inspected production source/model files.

## Capture another validation observation

Use a new output directory so live evidence is never silently replaced:

```bash
.venv/bin/python scripts/analyze_seerr_phase2.py \
  --output artifacts/seerr-exploration/phase2-another-observation \
  --credentials-file .seer_creds --live

plexenv/bin/python scripts/benchmark_seerr_phase2.py \
  --output artifacts/seerr-exploration/phase2-another-observation --database

.venv/bin/python scripts/analyze_seerr_phase2.py \
  --output artifacts/seerr-exploration/phase2-another-observation
```

The first command captures GET validation. The second supplies model metadata, aggregate database evidence and local microbenchmarks. The third renders the final analysis with those costs. The first report pass may describe capacity evidence as pending until the second/third commands complete. This is a replay of the fixed Phase 1 exclusion experiment with new validation evidence, not a discovery job or a refreshed candidate model evaluation. Interpret fixed-date narrative against its captured evidence; this is a Phase 2 investigation of the 2026-10-28 snapshots, not a general production reporting pipeline.

`--live` calls only Seerr GET `/status`, `/settings/main`, `/auth/me`, `/movie/{id}` and `/discover/movies`. The settings/account responses are projected immediately to version and a small allowlist of discovery settings; API keys, account identities and raw responses are never written. Movie payloads use the existing sanitizer, preserving only status values and service/library-identifier **presence**, never internal IDs, URLs, paths or requester identities. Requests use existing pacing/retries; redirects and authentication failures stop the relevant collection. The separate Phase 2 cache never changes the Phase 1 cache.

Both discovery scopes use `primary_release_date.asc` with the same inclusive dates, with first/last-page rechecks. This can detect observed inconsistencies, but it cannot create an atomic upstream snapshot. The two scopes were 333 and 779 titles during Phase 2 validation, and the all-language scope still omitted one configured-scope ID. The analysis of exclusions remains fixed to the original 333/777 snapshots.

The benchmark command uses `plexenv` because the lean `.venv` lacks joblib/XGBoost. With `--database` omitted, it reuses `database-observations.json`; all its other work is local. Local synthetic timings are measured; embedding and XGBoost throughputs remain explicitly assumed. No production inference benchmark is implied.

## Extraction refinement

The Phase 1 extractor already preserved media/request codes when present. Its additive refinement distinguishes missing, null, invalid, returned-record and failed-extraction cases; standard and 4K request scopes are separate observations. Existing legacy fields and Phase 1 rule behavior remain compatible. The Phase 2 tier simulation holds only known **standard** requests/workflows; a 4K-only request does not establish a standard-media duplicate. Missing/null mediaInfo does not prove a title has never been requested. An external Radarr association does not prove monitored=true, and a Seerr availability report is not an independent fresh Plex check.

The inactive `experimental-curation.json` separates hard policy/identity conditions, existing-workflow holds, soft ordering, revisit timing and admin exceptions. No timer, filter, record, request or model behavior is activated. Its readiness criterion describes adequate text for a **future compatible scoring experiment**, not permission to use the current production scoring loader on prospective titles.

## Outputs

Required deliverables are `phase2-findings.md`, `excluded-candidate-analysis.csv`, `candidate-review.md`, `curation-strategy-comparison.md`, `prospective-scoring-feasibility.md`, and `experimental-curation.json`.

Additional evidence includes full exclusion JSON and overlapping/exclusive distributions, deterministic review sampling provenance, sanitized live details and request audit, status normalization observations, same-sort language comparison, model feature inspection, source function line locations/hashes, database aggregate observations, cost assumptions/measurements, and input/output integrity manifests. All generated output files are mode 0600 in owner-only directories.

Validation:

```bash
plexenv/bin/python -m pytest -q tests/test_seerr_exploration.py tests/test_seerr_phase2.py
git diff --check
```
