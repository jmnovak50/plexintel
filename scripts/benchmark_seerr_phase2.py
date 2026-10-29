#!/usr/bin/env python3
"""Offline Phase 2 capacity estimates. Inspects a model but never runs inference.

Optional --database reads aggregate counts/settings in a DB-enforced read-only transaction.
No embedding endpoint, production scoring import, model fit/predict, or model writes.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import time

import numpy as np

import explore_seerr_candidates as ex


def inspect_model(path):
    import io
    import joblib
    # One snapshot of the trusted local artifact; no production module import.
    raw = path.read_bytes()
    start = time.perf_counter()
    model = joblib.load(io.BytesIO(raw))
    booster = model.get_booster()
    names = list(booster.feature_names or [])
    trees = booster.get_dump(dump_format='json')
    def topology(node):
        if 'leaf' in node:
            return 1, 0
        children = [topology(c) for c in node['children']]
        return 1 + sum(c[0] for c in children), 1 + max(c[1] for c in children)
    shapes = [topology(json.loads(t)) for t in trees]
    def group(name):
        return next((prefix for prefix in ('emb', 'genre', 'actor', 'director') if name.startswith(prefix + '_')),
                    'decade' if name.startswith('is_') and name.endswith('s') else name)
    return dict(artifact_sha256=hashlib.sha256(raw).hexdigest(), feature_count=len(names),
        feature_groups=dict(Counter(group(n) for n in names)), feature_names=names,
        tree_count=len(trees), node_count=sum(t[0] for t in shapes), max_depth=max(t[1] for t in shapes),
        watch_sim_split_count=booster.get_score(importance_type='weight').get('watch_sim', 0),
        watch_sim_gain=booster.get_score(importance_type='gain').get('watch_sim', 0),
        model_load_and_inspection_seconds=time.perf_counter() - start, inference_executed=False)


def read_aggregates():
    from dotenv import load_dotenv
    from api.db.connection import connect_db
    load_dotenv(ex.ROOT / '.env', override=False)
    conn = connect_db()
    try:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ', autocommit=False)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SELECT COUNT(*),MIN(vector_dims(embedding)),MAX(vector_dims(embedding)) FROM user_embeddings WHERE embedding IS NOT NULL")
            count, minimum, maximum = cur.fetchone()
            cur.execute('SELECT COUNT(DISTINCT username) FROM watch_history')
            history_users = cur.fetchone()[0]
            cur.execute("""SELECT key,raw_value FROM app_settings WHERE key IN
                ('ollama.embedding_model','ollama.threads','ollama.timeout_s','embeddings.batch_size',
                 'user_embeddings.engagement_threshold','training.watch_embed_min_engagement') ORDER BY key""")
            settings = dict(cur.fetchall())
        return dict(observed_at=ex.utcnow(), user_profile_rows=count, user_profile_min_dimensions=minimum,
            user_profile_max_dimensions=maximum, historical_user_count=history_users, settings=settings,
            eligibility_definition='Non-null user profile rows indicate computational coverage, not final community eligibility or acquisition consent.')
    finally:
        conn.rollback()
        conn.close()


def benchmark(fn, repeats=9):
    fn()
    times = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return dict(repetitions=repeats, median_seconds=statistics.median(times), min_seconds=min(times), max_seconds=max(times))


def estimates(output, model, database):
    profiles = database['user_profile_rows']
    feature_count = model['feature_count']
    group = model['feature_groups']
    if group.get('emb') != 1536:
        raise ValueError('Inspected embedding contract changed; do not extrapolate 768-dimensional estimates')
    measurements, table, vocabulary = {}, [], {}
    live_path = output / 'live-validation/observations.json'
    live = json.loads(live_path.read_text()) if live_path.exists() else {}
    timings = [r['elapsed_seconds'] for r in live.get('requests', []) if r.get('source') == 'measured_operation']
    p50 = statistics.median(timings) if timings else None
    p90 = sorted(timings)[min(len(timings) - 1, int(.9 * len(timings)))] if timings else None
    assumptions = dict(profile_rows=profiles, embedding_dimension=768, feature_count=feature_count,
        embedding_texts_per_second=[1, 20], xgboost_pairs_per_second=[1000, 100000],
        embedding_and_xgboost_throughput_measured=False, live_http_operations=len(timings),
        measured_http_operation_median_seconds=p50, measured_http_operation_p90_seconds=p90,
        http_timing_includes_client_pacing=True, costs_are_seconds_unless_labeled=True,
        database_profile_coverage_is_not_verified_community_eligibility=True,
        numeric_precision='synthetic microbenchmarks float32; production pandas may materialize float64',
        cold_start_network_contention_and_shap_unmeasured=True)
    data = {}
    for name in ('2026-10-28-week', '2026-10-28-all-languages'):
        rows = json.loads((output.parent / name / 'candidates.json').read_text())
        count = len(rows)
        rng = np.random.default_rng(20261028)
        media = rng.normal(size=(count, 768)).astype(np.float32)
        users = rng.normal(size=(profiles, 768)).astype(np.float32)
        media /= np.maximum(np.linalg.norm(media, axis=1, keepdims=True), 1e-12)
        users /= np.maximum(np.linalg.norm(users, axis=1, keepdims=True), 1e-12)
        def text_mapping():
            for _ in range(50):
                texts = [f"{r['title'] or ''} — {r['overview'] or ''}".strip() for r in rows]
            return texts
        def feature_assembly():
            # Per-user chunks: do not retain a community-sized feature matrix.
            for user in users:
                matrix = np.zeros((count, feature_count), dtype=np.float32)
                matrix[:, :768] = media
                matrix[:, 768:1536] = user
            return matrix
        measurements[str(count)] = dict(text_mapping_50_iterations=benchmark(text_mapping),
            per_user_chunk_feature_assembly_all_profiles=benchmark(feature_assembly),
            all_profile_cosine_matrix=benchmark(lambda: media @ users.T))
        vocab = {}
        for field, prefix in [('genres', 'genre_'), ('directors', 'director_')]:
            allowed = {n[len(prefix):] for n in model['feature_names'] if n.startswith(prefix)}
            unknown = Counter(value for r in rows for value in r.get(field, []) if value not in allowed)
            vocab[field] = dict(vocabulary_size=len(allowed),
                titles_with_any_source_values=sum(bool(r.get(field)) for r in rows),
                titles_with_any_trained_flag=sum(bool(set(r.get(field, [])) & allowed) for r in rows),
                unknown_values=dict(unknown.most_common()))
        vocabulary[str(count)] = vocab
        pairs = count * profiles
        data[str(count)] = dict(pair_count=pairs, media_embedding_mib=count * 768 * 4 / 2**20,
            one_user_feature_mib_float32=count * feature_count * 4 / 2**20,
            community_features_mib_float32=pairs * feature_count * 4 / 2**20,
            community_features_mib_float64=pairs * feature_count * 8 / 2**20,
            max_tree_branch_comparisons=pairs * model['tree_count'] * model['max_depth'],
            embedding_seconds_assumed=[count / 20, count],
            one_user_xgboost_seconds_assumed=[count / 100000, count / 1000],
            community_xgboost_seconds_assumed=[pairs / 100000, pairs / 1000],
            metadata_request_count=math_ceil_pages(count) + count,
            metadata_seconds_warm_extrapolation=[(math_ceil_pages(count) + count) * x for x in (p50, p90)] if timings else None)
    def seconds(values):
        return 'not measured' if values is None else f'{min(values):.3f}–{max(values):.3f} s'
    a, b = data['333'], data['777']
    table += [
        ['Discovery + details, warm HTTP extrapolation', seconds(a['metadata_seconds_warm_extrapolation']), seconds(b['metadata_seconds_warm_extrapolation']), f'{len(timings)} measured validation operations incl. client pacing; not a cold crawl'],
        ['Additional external enrichment', '0 required for title/synopsis text', '0 required for title/synopsis text', 'Field repair optional and unmeasured; upstream may fetch appended metadata'],
        ['Local metadata text mapping', f"{measurements['333']['text_mapping_50_iterations']['median_seconds']/50:.6f} s", f"{measurements['777']['text_mapping_50_iterations']['median_seconds']/50:.6f} s", 'Measured local formatting; not network or embeddings'],
        ['Media embedding generation, once/title', seconds(a['embedding_seconds_assumed']), seconds(b['embedding_seconds_assumed']), 'Assumed 1–20 short texts/s; no Ollama request'],
        [f'Feature matrix assembly, {profiles} profiles', f"{measurements['333']['per_user_chunk_feature_assembly_all_profiles']['median_seconds']:.6f} s", f"{measurements['777']['per_user_chunk_feature_assembly_all_profiles']['median_seconds']:.6f} s", 'Measured synthetic NumPy chunk allocation/copy only'],
        ['Per-user XGBoost inference', seconds(a['one_user_xgboost_seconds_assumed']), seconds(b['one_user_xgboost_seconds_assumed']), 'Assumed 1k–100k pairs/s; actual inference forbidden/unmeasured'],
        [f'Entire profile-covered community, {profiles} users', seconds(a['community_xgboost_seconds_assumed']), seconds(b['community_xgboost_seconds_assumed']), f"{a['pair_count']:,}/{b['pair_count']:,} pairs; inference assumption only"],
        ['Full community feature matrix, float32 / float64', f"{a['community_features_mib_float32']:.1f} / {a['community_features_mib_float64']:.1f} MiB", f"{b['community_features_mib_float32']:.1f} / {b['community_features_mib_float64']:.1f} MiB", 'Calculated; prefer per-user chunks'],
    ]
    return dict(recorded_at=ex.utcnow(), assumptions=assumptions, measurements=measurements,
                calculated=data, vocabulary_coverage=vocabulary, table=table)


def math_ceil_pages(count):
    return (count + 19) // 20


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--database', action='store_true', help='Refresh aggregate-only DB evidence')
    args = parser.parse_args()
    allowed_base = ex.ROOT / 'artifacts/seerr-exploration'
    output = args.output.resolve()
    protected = [allowed_base / p for p in ('2026-10-28-week', '2026-10-28-all-languages', '2026-10-28-week-mixed-pages', 'cache')]
    if allowed_base.resolve() not in output.parents or any(p.resolve() == output or p.resolve() in output.parents for p in protected):
        parser.error('Use a new Phase 2 directory; Phase 1 inputs are immutable')
    ex.private_dir(output)
    model = inspect_model(ex.ROOT / 'xgb_model.pkl')
    ex.write_json(output / 'model-inspection.json', model)
    db_file = output / 'database-observations.json'
    database = read_aggregates() if args.database else json.loads(db_file.read_text())
    ex.write_json(db_file, database)
    costs = estimates(output, model, database)
    ex.write_json(output / 'cost-estimates.json', costs)
    print(json.dumps(dict(features=model['feature_count'], trees=model['tree_count'], profiles=database['user_profile_rows'],
                         model_inference_executed=False, embedding_calls=0, output=str(output))))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError):
        print('Phase 2 capacity analysis failed; verify inputs and analysis dependencies.', file=ex.sys.stderr)
        raise SystemExit(1)
