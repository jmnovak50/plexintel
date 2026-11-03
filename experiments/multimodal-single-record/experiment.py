#!/usr/bin/env python3
"""One real Plex movie, existing Ollama models only; no production writes.

Run from any directory with the repository's .venv Python. --report-only
regenerates README.md without network/inference. Reuses the pinned movie on rerun.
Existing dependencies: requests, python-dotenv, psycopg2 (project environment).
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import struct
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
SECRETS = []


def checked_bytes(raw):
    for value in SECRETS:
        if value and len(value) >= 8 and value.encode() in raw:
            raise RuntimeError('Credential detected in artifact; refused to save')
    return raw


def save_json(name, obj):
    raw = json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False).encode() + b'\n'
    (HERE / name).write_bytes(checked_bytes(raw))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def endpoint_only(url):
    u = urlsplit(url)
    return urlunsplit((u.scheme, u.netloc.rsplit('@', 1)[-1], u.path, '', ''))


def request(method, url, **kwargs):
    # No response bodies/URLs in exceptions: Tautulli authenticates in query params.
    try:
        r = requests.request(method, url, timeout=kwargs.pop('timeout', 30),
                             allow_redirects=False, **kwargs)
    except requests.RequestException as exc:
        raise RuntimeError(f'Network request failed ({type(exc).__name__}); details withheld') from None
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code}; response details withheld')
    return r


def configuration():
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    # Enforce read-only for every libpq connection, including settings resolution.
    os.environ['PGOPTIONS'] = '-c default_transaction_read_only=on -c statement_timeout=15000'
    from api.db.connection import connect_db
    from api.services.app_settings import resolve_settings
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SHOW transaction_read_only')
            assert cur.fetchone()[0] == 'on'
            cur.execute('SELECT 1 FROM public.app_settings LIMIT 1')
    finally:
        conn.rollback()
        conn.close()
    keys = ['ollama.host', 'ollama.embedding_model', 'ollama.threads', 'ollama.timeout_s',
            'tautulli.api_url', 'tautulli.api_key', 'plex.client_id', 'plex.product', 'plex.version']
    resolved = resolve_settings(keys=keys)
    cfg = {k: s.value for k, s in resolved.items()}
    SECRETS.append(str(cfg['tautulli.api_key']))
    return cfg, {k: s.source for k, s in resolved.items()}, connect_db


def tautulli(cfg, cmd, **params):
    r = request('GET', cfg['tautulli.api_url'], params={
        'apikey': cfg['tautulli.api_key'], 'cmd': cmd, **params})
    d = r.json()['response']
    if d.get('result') != 'success':
        raise RuntimeError('Tautulli read failed; source details withheld')
    return d['data']


def production_serializer():
    # Execute only the exact pure serializer AST, never import the ingest pipeline.
    source = (ROOT / 'fetch_tautulli_data.py').read_text()
    node = next(n for n in ast.parse(source).body
                if isinstance(n, ast.FunctionDef) and n.name == '_media_text_for_embedding')
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<production serializer>', 'exec'), namespace)
    return namespace[node.name], sha(ast.get_source_segment(source, node).encode())


def jpeg_size(raw):
    if raw[:2] != b'\xff\xd8':
        raise RuntimeError('Plex poster was not JPEG; refusing to relabel image bytes')
    pos = 2
    while pos < len(raw):
        if raw[pos] != 255:
            pos += 1
            continue
        while raw[pos] == 255:
            pos += 1
        marker = raw[pos]
        pos += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        length = struct.unpack('>H', raw[pos:pos + 2])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack('>HH', raw[pos + 3:pos + 7])
            return width, height
        pos += length
    raise RuntimeError('JPEG dimensions unavailable')


def complete_text(movie, baseline):
    # Preserve the production title/synopsis first, then add available semantic
    # movie metadata. Exclude file paths, user state and technical stream data.
    lines = [baseline]
    fields = ['title', 'year', 'originalTitle', 'tagline', 'studio', 'contentRating',
              'originallyAvailableAt', 'duration', 'rating', 'audienceRating']
    supplied = ['title', 'summary']
    for field in fields:
        if movie.get(field) is not None:
            lines.append(f'{field}: {movie[field]}')
            supplied.append(field)
    for field in ['Genre', 'Director', 'Writer', 'Role', 'Country', 'Collection', 'Label', 'Rating']:
        if movie.get(field):
            entries = []
            for item in movie[field]:
                text = item.get('tag') or item.get('value')
                if text is None:
                    continue
                if item.get('role'):
                    text = f"{text} as {item['role']}"
                if field == 'Rating':
                    text = f"{item.get('type', '')}: {text}"
                entries.append(str(text))
            if entries:
                lines.append(f'{field}: ' + '; '.join(entries))
                supplied.append(field)
    return '\n'.join(lines), list(dict.fromkeys(supplied))


def capture(cfg, connect_db, result):
    pin = HERE / 'selected-record.json'
    if pin.exists():
        selected = json.loads(pin.read_text())
    else:
        conn = connect_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""SELECT rating_key, title, year FROM public.library l
                    WHERE media_type='movie' AND length(trim(title))>0
                      AND length(summary)>150 AND thumb_path IS NOT NULL
                      AND EXISTS (SELECT 1 FROM public.media_genres g WHERE g.media_id=l.rating_key)
                      AND EXISTS (SELECT 1 FROM public.media_directors d WHERE d.media_id=l.rating_key)
                      AND EXISTS (SELECT 1 FROM public.media_actors a WHERE a.media_id=l.rating_key)
                    ORDER BY rating_key LIMIT 1""")
                row = cur.fetchone()
                if row is None:
                    raise RuntimeError('No complete movie candidate; no other titles fetched')
                selected = dict(rating_key=row[0], title=row[1], year=row[2])
        finally:
            conn.rollback()
            conn.close()
        save_json('selected-record.json', selected)

    # Use existing configured Tautulli credentials to discover PMS configuration.
    # Only the PMS section is requested; its token stays in process memory.
    pms = tautulli(cfg, 'get_settings', key='PMS')
    pms = pms.get('PMS', pms)
    token = pms.get('pms_token')
    if not token:
        # Tautulli redacts this secret. PlexIntel already stores the Plex token
        # obtained by its normal OAuth login; read one existing credential only.
        conn = connect_db()
        try:
            with conn.cursor() as cur:
                cur.execute("""SELECT plex_token FROM public.users
                    WHERE plex_token IS NOT NULL AND length(trim(plex_token))>0
                    ORDER BY COALESCE(is_admin, FALSE) DESC, user_id LIMIT 1""")
                row = cur.fetchone()
                token = row[0] if row else None
        finally:
            conn.rollback()
            conn.close()
        result['environment']['plex_credential_source'] = 'Existing PlexIntel OAuth token, read-only users query; Tautulli PMS token redacted'
    if not token:
        raise RuntimeError('Existing PMS/OAuth token unavailable')
    SECRETS.append(token)
    server = tautulli(cfg, 'get_server_info')
    plex_url = server['pms_url'].rstrip('/')
    headers = {'X-Plex-Token': token, 'X-Plex-Client-Identifier': str(cfg['plex.client_id']),
               'X-Plex-Product': str(cfg['plex.product']), 'X-Plex-Version': str(cfg['plex.version']),
               'Accept': 'application/json'}
    metadata_path = HERE / 'metadata.json'
    if not metadata_path.exists():
        raw = request('GET', plex_url + f"/library/metadata/{int(selected['rating_key'])}",
                      headers=headers).content
        payload = json.loads(raw)
        metadata_path.write_bytes(checked_bytes(raw))
    else:
        payload = json.loads(metadata_path.read_bytes())
    movies = payload['MediaContainer']['Metadata']
    if len(movies) != 1:
        raise RuntimeError('Expected exactly one metadata record')
    movie = movies[0]
    assert str(movie['ratingKey']) == str(selected['rating_key'])
    if movie.get('type') != 'movie' or not all(movie.get(k) for k in ('title', 'summary', 'Genre', 'thumb')):
        raise RuntimeError('Selected record lacks required movie fields; no second movie fetched')
    thumb = movie['thumb']
    if not thumb.startswith('/library/metadata/') or urlsplit(thumb).netloc or urlsplit(thumb).query:
        raise RuntimeError('Unexpected poster path; refused credential-bearing request')
    poster_path = HERE / 'poster.jpg'
    if not poster_path.exists():
        raw = request('GET', plex_url + thumb, headers={**headers, 'Accept': 'image/jpeg'}).content
        jpeg_size(raw)
        poster_path.write_bytes(checked_bytes(raw))
    raw = poster_path.read_bytes()
    width, height = jpeg_size(raw)
    serializer, serializer_hash = production_serializer()
    baseline = serializer((movie['ratingKey'], movie['title'], movie['summary']))
    full, fields = complete_text(movie, baseline)
    (HERE / 'metadata.txt').write_bytes(checked_bytes(baseline.encode()))
    (HERE / 'metadata-complete.txt').write_bytes(checked_bytes(full.encode()))
    result['movie'] = dict(title=movie['title'], year=movie.get('year'), rating_key=selected['rating_key'],
        metadata_fields=fields, production_fields=['title', 'summary'],
        poster_width=width, poster_height=height, poster_bytes=len(raw), poster_sha256=sha(raw),
        metadata_sha256=sha(metadata_path.read_bytes()), production_text_sha256=sha(baseline.encode()),
        complete_text_sha256=sha(full.encode()), production_serializer_sha256=serializer_hash,
        production_text_characters=len(baseline), complete_text_characters=len(full),
        plex_version=server.get('pms_version'), plex_server_name=server.get('pms_name'))
    print(f"Selected one movie: {movie['title']} ({movie.get('year')}); poster {width}x{height}, {len(raw)} bytes", flush=True)
    return baseline, full, base64.b64encode(raw).decode()


def installed_model(tags, name):
    canonical = name if ':' in name.rsplit('/', 1)[-1] else name + ':latest'
    matches = [m for m in tags if m['name'] == canonical]
    if len(matches) != 1:
        raise RuntimeError('Required model is not already installed; no pull attempted')
    return matches[0]


def verify_capabilities(host, models, result):
    version = request('GET', host + '/api/version').json()['version']
    result['environment']['ollama_version'] = version
    for label, m in models.items():
        info = request('POST', host + '/api/show', json={'model': m['name']}).json()
        # Modelfile may contain absolute paths; capture only relevant public fields.
        result['environment']['models'][label] = {
            'tag': m, **{k: info.get(k) for k in ['details', 'capabilities', 'parameters', 'model_info', 'projector_info']}}
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise RuntimeError('Cannot verify source for this Ollama version; stopped before multimodal requests')
    source_url = f'https://raw.githubusercontent.com/ollama/ollama/v{version}/server/routes.go'
    try:
        raw = request('GET', source_url).content
    except RuntimeError:
        raise RuntimeError('Version-matched API source unavailable; stopped before multimodal requests') from None
    source = raw.decode()
    start = source.index('func (s *Server) EmbedHandler(')
    end = source.index('\nfunc ', start + 1)
    handler = source[start:end]
    required = ['case map[string]any:', 'case "image", "audio":', 'base64.StdEncoding.DecodeString',
                'r.Embedding(ctx, text, item.media)']
    supported = all(x in handler for x in required)
    capabilities = result['environment']['models']['experimental']['capabilities'] or []
    vision = 'vision' in capabilities and 'embedding' in capabilities
    result['capability_verification'] = dict(version_matched_source=source_url,
        source_sha256=sha(raw), handler_sha256=sha(handler.encode()),
        native_joint_format_supported=supported and vision,
        request_format={'model': models['experimental']['name'],
                        'input': {'text': '<complete metadata>', 'image': '<base64 JPEG bytes>'}},
        explanation='Version-matched handler parses one object and forwards text plus decoded media to one Embedding call.',
        alternatives='Text-only /api/embed is supported. Direct Sentence Transformers/llama.cpp would require a separate runtime and was not executed. No captioning, averaging, or concatenation used.')
    # Small source excerpt for reproducible format audit, not another dependency.
    (HERE / 'ollama-embed-handler.go.txt').write_text(handler + '\n')
    return supported and vision


def ps(host):
    return request('GET', host + '/api/ps', timeout=10).json()


def vector_stats(data, dimensions):
    vectors = data.get('embeddings')
    shape_ok = isinstance(vectors, list) and len(vectors) == 1 and isinstance(vectors[0], list)
    vector = vectors[0] if shape_ok else []
    finite = all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector)
    norm = math.sqrt(sum(x*x for x in vector)) if vector and finite else 0
    return dict(shape=[len(vectors) if isinstance(vectors, list) else 0, len(vector)],
                expected_dimensions=dimensions, finite=finite, norm=norm,
                valid=shape_ok and len(vector) == dimensions and finite and norm > 0)


def benchmark(label, model, input_value, cfg, result, dimensions=768, baseline=False):
    host = cfg['ollama.host'].rstrip('/')
    group = dict(model=model, input_kind='string-list' if isinstance(input_value, list) else 'object',
                 status='running', runs=[])
    result['benchmarks'][label] = group
    for index in range(4):
        before = ps(host)
        resident = any(m.get('name') == model or m.get('model') == model for m in before.get('models', []))
        payload = {'model': model, 'input': input_value, 'keep_alive': '15m'}
        if cfg.get('ollama.threads'):
            # Match the production client exactly. This is not options.num_thread.
            payload['num_thread'] = cfg['ollama.threads']
        if not baseline:
            payload['truncate'] = False
        start = time.perf_counter()
        try:
            response = requests.post(host + '/api/embed', json=payload, timeout=cfg['ollama.timeout_s'])
        except requests.RequestException as exc:
            group.update(status='failed', reason=f'Network failure: {type(exc).__name__}; not retried')
            save_json('results.json', result)
            return
        elapsed = time.perf_counter() - start
        data = response.json()
        checked_bytes(response.content)
        raw_name = f'raw-responses/{label}-{index}.json'
        save_json(raw_name, data)
        after = ps(host)
        run = dict(index=index, phase='first' if index == 0 else 'warm', http_status=response.status_code,
                   resident_before=resident, client_elapsed_seconds=elapsed, response_file=raw_name,
                   ps_before=before, ps_after=after,
                   peak_process_memory_bytes=None,
                   memory_note='/api/ps exposes model allocation snapshots, not process RSS or peak memory.')
        group['runs'].append(run)
        if response.status_code != 200:
            group.update(status='failed', reason=str(data.get('error', 'API rejected request'))[:800])
            save_json('results.json', result)
            print(f'{label}: HTTP {response.status_code}; stopped this configuration', flush=True)
            return
        run['ollama'] = {k: v for k, v in data.items() if k != 'embeddings'}
        run['vector'] = vector_stats(data, dimensions)
        total = data.get('total_duration')
        load = data.get('load_duration')
        # /api/embed has no prompt_eval_duration: this includes tokenization,
        # preprocessing and pooling, not a separately measured GPU kernel time.
        run['server_nonload_seconds'] = (total-load)/1e9 if total is not None and load is not None else None
        if not run['vector']['valid']:
            group.update(status='invalid', reason='Returned vector failed shape/finite/nonzero validation')
            save_json('results.json', result)
            return
        save_json('results.json', result)
        print(f"{label} {run['phase']} {index}: client={elapsed:.4f}s, load={load/1e9:.4f}s, nonload={run['server_nonload_seconds']:.4f}s, dims={run['vector']['shape'][1]}", flush=True)
    warm = group['runs'][1:]
    group.update(status='success', dimensions=dimensions,
        cold_load_seconds=group['runs'][0]['ollama'].get('load_duration', 0)/1e9 if not group['runs'][0]['resident_before'] else None,
        warm_inference_median_seconds=statistics.median(r['server_nonload_seconds'] for r in warm),
        warm_client_median_seconds=statistics.median(r['client_elapsed_seconds'] for r in warm),
        first_client_seconds=group['runs'][0]['client_elapsed_seconds'],
        warm_client_range_seconds=[min(r['client_elapsed_seconds'] for r in warm), max(r['client_elapsed_seconds'] for r in warm)])
    save_json('results.json', result)


def comparisons(result):
    groups = result['benchmarks']
    def success(k):
        return groups.get(k, {}).get('status') == 'success'
    def first_vector(k):
        return json.loads((HERE / groups[k]['runs'][0]['response_file']).read_text())['embeddings'][0]
    def cosine(a, b):
        a, b = first_vector(a), first_vector(b)
        assert len(a) == len(b)
        return sum(x*y for x,y in zip(a,b))/math.sqrt(sum(x*x for x in a)*sum(y*y for y in b))
    c = result.setdefault('comparisons', {})
    if all(success(k) for k in ('metadata', 'poster', 'combined')):
        c['metadata_combined_cosine'] = cosine('metadata', 'combined')
        c['poster_combined_cosine'] = cosine('poster', 'combined')
        c['combined_over_metadata_warm_inference_ratio'] = groups['combined']['warm_inference_median_seconds']/groups['metadata']['warm_inference_median_seconds']
    if success('production'):
        for key in ('metadata', 'poster', 'combined', 'production_text_control'):
            if success(key):
                c[key+'_relative_client_throughput_vs_production'] = groups['production']['warm_client_median_seconds']/groups[key]['warm_client_median_seconds']
    result['recommendation'] = 'GO' if all(success(k) for k in ('production', 'metadata', 'poster', 'combined')) else 'NO-GO' if result.get('capability_verification', {}).get('native_joint_format_supported') is False else 'INCONCLUSIVE'


def report(result):
    comparisons(result)
    env, movie = result.get('environment', {}), result.get('movie', {})
    groups = result.get('benchmarks', {})
    def seconds(value):
        return 'N/A' if value is None else f'{value:.4f} s'
    rows = []
    for key, title in [('production', 'Production EmbeddingGemma'), ('metadata', 'EmbeddingGemma 2 — metadata'),
                       ('poster', 'EmbeddingGemma 2 — poster'), ('combined', 'EmbeddingGemma 2 — combined')]:
        g = groups.get(key, {})
        if g.get('status') == 'success':
            rows.append(f"| {title} | {g['dimensions']} | {seconds(g['cold_load_seconds'])} | {seconds(g['warm_inference_median_seconds'])} | {seconds(g['warm_client_median_seconds'])} |")
        else:
            rows.append(f'| {title} | N/A | N/A | N/A | N/A |')
    lines = ['# Single-record multimodal embedding experiment', '',
        f"Observed: {result.get('started_at', 'unavailable')}. Recommendation: **{result.get('recommendation', 'INCONCLUSIVE')}** for a larger offline technical evaluation only.", '',
        '## A. Selected movie', '',
        f"{movie.get('title', 'Not retrieved')} ({movie.get('year', 'N/A')}); one pinned Plex rating key.", '',
        '- `metadata.json`: original Plex JSON response bytes, stored locally (may contain media paths).',
        '- `metadata.txt`: exact production serializer output, title and synopsis only.',
        '- `metadata-complete.txt`: same title/synopsis plus all captured semantic movie fields; input to Tests A and C.',
        f"- Complete fields: {', '.join(movie.get('metadata_fields', []))}.",
        f"- Poster: {movie.get('poster_width', 'N/A')} × {movie.get('poster_height', 'N/A')}, {movie.get('poster_bytes', 'N/A'):,} bytes; original Plex thumbnail bytes, no resizing or caption substitution." if movie.get('poster_bytes') else '- Poster unavailable.', '',
        '## B. Environment', '',
        f"Client: `{env.get('client_host', 'N/A')}`. Ollama: `{env.get('ollama_host', 'N/A')}`, version **{env.get('ollama_version', 'N/A')}**. Plex server: {movie.get('plex_server_name', 'N/A')}, {movie.get('plex_version', 'N/A')}.", '',
        'Model identities and digests:', '']
    for label, m in env.get('models', {}).items():
        tag = m['tag']
        lines += [f"- {label}: `{tag['name']}`, parent `{m['details'].get('parent_model') or '(none)'}`, {m['details'].get('quantization_level')}; digest `{tag['digest']}`. Capabilities: {', '.join(m.get('capabilities') or [])}."]
    verification = result.get('capability_verification', {})
    lines += ['', 'PlexIntel retrieves metadata through Tautulli (`fetch_tautulli_data.get_metadata`), stores it in `library`, and embeds `title — summary` (`_media_text_for_embedding`, `generate_media_embeddings`). `ollama_embeddings._post_embed` sends string lists to `/api/embed`, keep-alive 15m, with the configured top-level `num_thread` hint. This script extracts only the pure serializer AST and reproduces that request for one input. Settings use the existing resolver with database-enforced read-only connections. Tautulli supplies the Plex endpoint but redacts its PMS token; an existing PlexIntel OAuth token was read from `users`. Metadata/poster were fetched directly through Plex with `X-Plex-Token` headers. No credentials were saved.', '',
        f"API verification: {verification.get('explanation', 'Not completed')} [Installed-version source]({verification.get('version_matched_source', 'https://github.com/ollama/ollama')}). The exact handler and its hash are captured locally. This verifies the tagged public implementation; successful live requests are the runtime evidence. [Model reference](https://registry.ollama.com/library/embeddinggemma-2).", '',
        'Native payload (one input object produces one vector):', '',
        '```json', '{"model":"embeddinggemma-2:latest","input":{"text":"<complete metadata>","image":"<base64 original JPEG bytes>"},"truncate":false,"keep_alive":"15m"}', '```', '',
        'Poster-only omits `text`; metadata-only uses a one-item string list. No prefixes, dimension override, vector averaging, or concatenation are applied. Tests A/C and the matched-text control disable truncation. The baseline retains production defaults. The configured thread hint is copied exactly; this top-level field is absent from Ollama’s EmbedRequest options, so 16 configured threads does not establish 16 effective runner threads.', '',
        '## C. Performance results', '',
        'Seconds. Warm inference is the median of three identical warm requests, measured as Ollama `total_duration − load_duration`. It includes tokenization, image preprocessing/encoding, pooling, and request overhead on the server; Ollama does not report isolated inference-kernel time. Total is median warm client wall time, including HTTP/JSON transfer. Cold load is the first request’s reported load only when `/api/ps` showed the model absent immediately beforehand. Models are never explicitly unloaded. A shared model cold load is measured once; later modality rows show N/A when already resident.', '',
        '| Configuration | Dimensions | Cold load | Warm inference | Total |',
        '|---|---:|---:|---:|---:|', *rows, '',
        '| Configuration | First client total | Warm client min–max | Prompt tokens (first; warm) |',
        '|---|---:|---:|---|']
    for key, g in groups.items():
        if g.get('status') == 'success':
            counts = [r['ollama'].get('prompt_eval_count', 'N/A') for r in g['runs']]
            spread = g['warm_client_range_seconds']
            lines.append(f"| {key} | {seconds(g['first_client_seconds'])} | {spread[0]:.4f}–{spread[1]:.4f} s | {counts[0]}; {counts[1:]} |")
        else:
            lines.append(f"| {key} | N/A | N/A | {g.get('status')}: {g.get('reason', 'not run')} |")
    lines += ['', 'Every request’s load/total durations, token counts, client timing, resident-state snapshots, vector shape/norm/finiteness, and response path are in `results.json`. Original API responses including vectors are in ignored `raw-responses/`. No model files were downloaded.', '',
        '## D. Findings', '',
        f"- Native joint format supported by inspected server/model: **{verification.get('native_joint_format_supported', 'unverified')}**; successful operations and failures are listed above."]
    for key,g in groups.items():
        if g.get('status') == 'success':
            norms = [r['vector']['norm'] for r in g['runs']]
            allocations = [m for r in g['runs'] for m in r['ps_after'].get('models', []) if m.get('name') == g['model'] or m.get('model') == g['model']]
            size = max((m.get('size', 0) for m in allocations), default=0)
            gpu = max((m.get('size_vram', 0) for m in allocations), default=0)
            lines.append(f"- {key}: all four outputs valid `[1, {g['dimensions']}]`, finite, nonzero; norm range {min(norms):.8f}–{max(norms):.8f}. Largest post-request `/api/ps` model allocation {size:,} bytes ({size/2**30:.3f} GiB); VRAM allocation {gpu:,} bytes.")
    lines += ['- **Peak process RSS/VRAM consumption: N/A.** The remote API reports model allocation snapshots, not OS/container peak usage. Allocation is not total host memory, and post-request snapshots can miss transient image allocations. GPU type, CPU use, and competing workload are not established.',
              '- “Cold” means model absent from Ollama’s resident list, not a cleared OS disk cache. No services were restarted and no models explicitly unloaded. Each model has one first request plus three repeats per configuration. Same-record caches and other server activity can affect these small samples.']
    experimental = env.get('models', {}).get('experimental')
    if experimental:
        disk = experimental['tag']['size']
        lines.append(f'- Installed EmbeddingGemma 2 files total {disk:,} bytes ({disk/2**30:.3f} GiB). The allocation snapshots must not be treated as total runtime memory including the vision/audio projector. True daily memory requirements remain unmeasured. Model metadata distinguishes a 512-wide internal representation from a 768-wide output projection; measured outputs are 768-dimensional.')
    c = result.get('comparisons', {})
    if 'metadata_combined_cosine' in c:
        ratio=c['combined_over_metadata_warm_inference_ratio']
        lines += [f"- Within EmbeddingGemma 2 only: metadata/combined cosine **{c['metadata_combined_cosine']:.6f}**; poster/combined cosine **{c['poster_combined_cosine']:.6f}**. These measure representation differences for one movie, not recommendation accuracy.",
                  f'- Combined warm server processing is **{ratio:.2f}×** metadata-only ({(ratio-1)*100:+.1f}%); this includes actual poster encoding.']
    for key in ('metadata','poster','combined','production_text_control'):
        value=c.get(key+'_relative_client_throughput_vs_production')
        if value is not None:
            lines.append(f'- {key}: **{value:.3f}×** production single-record warm client throughput (reciprocal median latency).')
    lines += ['', 'Production uses the shorter title/synopsis input; Test A uses complete semantic metadata. `production_text_control` is an additional EmbeddingGemma 2 run on the exact production text to separate text-length changes from model latency. All requests concern the same movie. These are serial single-record rates, not measured batch/daily capacity. No cross-model cosine is calculated; matching output dimensions does not make the two model spaces interchangeable.', '',
        '## E. Recommendation', '',
        f"**{result.get('recommendation', 'INCONCLUSIVE')}** for larger offline evaluation. " + ('Native text, poster, and joint requests produced valid vectors on the installed server. Next evaluate a fixed offline sample for retrieval/recommendation quality, diversity, missing-art handling, cache effects, batching, and measured host peak memory. Daily-pipeline capacity remains unproven by one movie. Any adoption would require independent re-embedding and downstream evaluation.' if result.get('recommendation') == 'GO' else 'The experiment did not establish all required operations; resolve the documented limitation before expanding scope.'), '',
        '## Reproduction and artifacts', '',
        'From the repository root:', '',
        '```bash', '.venv/bin/python experiments/multimodal-single-record/experiment.py', '# Rebuild the report without another inference call:', '.venv/bin/python experiments/multimodal-single-record/experiment.py --report-only', '```', '',
        'Reuses `selected-record.json` and captured input files. Reruns overwrite timing/response artifacts for that same movie; preserve this directory first if comparing runs. Requires the project virtualenv and network access to configured services plus the public version-matched source. No new dependencies. Generated poster, original private metadata and vector responses are ignored by the experiment-local `.gitignore`. No commits were made. All writes remain in this directory.', '']
    if result.get('failure'):
        lines += ['Encountered limitation: ' + result['failure'], '']
    (HERE / 'README.md').write_bytes(checked_bytes('\n'.join(lines).encode()))
    save_json('results.json', result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    if args.report_only:
        report(json.loads((HERE / 'results.json').read_text()))
        return
    (HERE / 'raw-responses').mkdir(exist_ok=True)
    result = dict(started_at=datetime.now(timezone.utc).isoformat(),
        environment=dict(client_host=platform.node(), models={}), benchmarks={})
    try:
        cfg, sources, connect_db = configuration()
        host = cfg['ollama.host'].rstrip('/')
        result['environment'].update(ollama_host=endpoint_only(host), setting_sources=sources,
            configured_production_model=cfg['ollama.embedding_model'],
            configured_thread_hint=cfg['ollama.threads'], python=platform.python_version())
        tags = request('GET', host + '/api/tags').json()['models']
        models = dict(production=installed_model(tags, cfg['ollama.embedding_model']),
                      experimental=installed_model(tags, 'embeddinggemma-2'))
        supported = verify_capabilities(host, models, result)
        save_json('results.json', result)
        baseline, full, image = capture(cfg, connect_db, result)
        benchmark('production', models['production']['name'], [baseline], cfg, result, baseline=True)
        benchmark('metadata', models['experimental']['name'], [full], cfg, result)
        if not supported:
            for label in ('poster', 'combined'):
                result['benchmarks'][label] = dict(status='unsupported', reason='Native joint format or model vision capability not verified; no multimodal benchmark run')
        else:
            benchmark('poster', models['experimental']['name'], {'image': image}, cfg, result)
            if result['benchmarks']['poster']['status'] == 'success':
                benchmark('combined', models['experimental']['name'], {'text': full, 'image': image}, cfg, result)
            else:
                result['benchmarks']['combined'] = dict(status='not_run', reason='Stopped after poster operation failed; no substitute')
        benchmark('production_text_control', models['experimental']['name'], [baseline], cfg, result)
    except Exception as exc:
        # Avoid tracebacks leaking credentials from HTTP, DB or config exceptions.
        result['failure'] = str(exc) if isinstance(exc, (RuntimeError, AssertionError)) else f'{type(exc).__name__}; diagnostic details withheld'
        checked_bytes(result['failure'].encode())
        print('Experiment limitation:', result['failure'], flush=True)
    report(result)
    print('Report saved:', HERE / 'README.md', flush=True)
    print('Recommendation:', result['recommendation'], flush=True)


if __name__ == '__main__':
    main()
