"""Read-only presentation of current events and immutable historical run evidence."""
import json
from uuid import UUID

from api.embedding_generation.progress import STAGES, STAGE_NAMES, event_details


def receipt(stage):
    for line in reversed((stage.get('stdout_tail') or '').splitlines()):
        try:
            value = json.loads(line)
            key = value.get('generation_run_id') or value.get('run_id')
            UUID(str(key))
            return str(key)
        except (ValueError, TypeError, AttributeError):pass
    return None


def historical_details(journal):
    """Never invent separate SHAP/dataset durations or post-commit verification."""
    times = journal['stages'] or {}
    complete = journal['status'] == 'succeeded' and bool(journal['promotion_id'])
    counts = journal.get('counts') or {}
    delta = journal.get('reconciliation') or {}
    scoring = journal.get('scoring') or {}
    dataset = journal.get('dataset') or {}
    inference = journal.get('inference') or {}
    output = []
    durations = dict(source_sync=times.get('source_sync'),
        media_text=sum(times.get(k, 0) for k in ('context', 'metadata', 'media_text')) if 'media_text' in times else None,
        watch=times.get('watch'), users=times.get('users'), train_model=times.get('training'),
        score_model=times.get('scoring'))
    stage_checkpoint = dict(training_data='training', train_model='training', score_model='scoring',
                            shap='scoring', verification='no-post-commit-verification')
    for key, label in STAGES:
        status = 'success' if stage_checkpoint.get(key, key) in times else 'not_recorded'
        message = None
        metrics = {}
        if key == 'source_sync':
            coverage = dataset.get('watch_coverage') or {}
            metrics = dict(new_media=delta.get('new_media_identities'), new_watch_events=delta.get('new_watch_history_events'), quarantined=coverage.get('quarantined_watch_events'))
        if key in ('media_text', 'watch'):
            population = counts.get(key) or {}
            fresh=delta.get('new_media_embeddings' if key=='media_text' else 'new_watch_embeddings')
            regenerated=delta.get('existing_media_regenerated' if key=='media_text' else 'existing_watch_regenerated')
            inferred=fresh+regenerated if fresh is not None and regenerated is not None else (inference.get(key) or {}).get('succeeded')
            metrics = dict(population, inferred=inferred, requests=(inference.get(key) or {}).get('requests'),
                reused=delta.get('media_embeddings_reused' if key=='media_text' else 'watch_embeddings_reused'),
                new=delta.get('new_media_embeddings' if key=='media_text' else 'new_watch_embeddings'),
                regenerated=delta.get('existing_media_regenerated' if key=='media_text' else 'existing_watch_regenerated'))
        if key == 'users':
            rebuilt = journal.get('users_rebuilt')
            total = (counts.get('user') or {}).get('succeeded')
            metrics = dict(succeeded=total, rebuilt=rebuilt, reused=total-rebuilt if total is not None and rebuilt is not None else None)
        if key == 'training_data':
            metrics = dict(rows=dataset.get('rows'), label_policy_skips=(dataset.get('skips') or {}).get('label_policy'), limited_history_skips=(dataset.get('skips') or {}).get('limited_history'))
            message = 'Included in model training; separate duration was not recorded.'
        if key == 'train_model':
            message = 'Recorded duration includes training data preparation and evaluation.'
            if 'scoring' in times or complete:metrics['quality_passed'] = True
            elif 'training' in times:
                status = 'not_recorded'
                message += ' Training completed, but a passing quality outcome is not evidenced; inspect the original worker error.'
        if key == 'score_model':
            metrics = {k:scoring.get(k) for k in ('predictions', 'users', 'limited_history_skips')}
            message = 'Recorded duration includes SHAP generation.'
        if key == 'shap':
            metrics = dict(contexts=scoring.get('shap_contexts'), contributions=scoring.get('shap_contributions'))
            message = 'Executed within scoring; separate duration was not recorded.'
        if key == 'publication':
            status = 'success' if complete else 'not_recorded'
            message = ('Committed publication '+journal['promotion_id'] if complete else 'No committed publication receipt.')+' Separate duration was not recorded.'
        if key == 'verification':message = 'No separate post-publication verification was recorded. Vector validation occurred before commit.'
        output.append(dict(stage_id='historical-'+key, stage_key=key, label=label, status=status,
            duration_seconds=durations.get(key), metrics={k:v for k,v in metrics.items() if v is not None},
            message=message, detail_source='historical_journal', started_at=None, completed_at=None))
    return output


def enrich_runs(cur, runs):
    """No writes, timestamp guessing, raw watch histories or full source snapshots."""
    wanted = {}
    for run in runs:
        carriers = [s for s in run['stages'] if s['stage_key']=='embeddinggemma2_generation']
        if not carriers:continue
        run['semantic_labeling'] = dict(status='disabled', reason='No automatic post-publication labeling receipt was recorded for this historical run. Manual current-generation labeling remains available.')
        children = [event_details(s) for s in run['stages'] if s['stage_key'] in STAGE_NAMES]
        if children:
            run['stage_details'] = sorted(children, key=lambda s:list(STAGE_NAMES).index(s['stage_key']))
        key = next((receipt(s) for s in reversed(run['stages'])
                    if s['stage_key'] in STAGE_NAMES or s['stage_key']=='embeddinggemma2_generation'
                    if receipt(s)), None)
        if key:
            wanted.setdefault(key, []).append(run)
            run['production_run_id'] = key
        elif not children:
            run['stage_detail_note'] = 'This historical worker did not retain a correlatable stage receipt; its original log is preserved below.'
    if not wanted:return
    cur.execute("""SELECT to_regclass('embedding_v2.production_runs') AS installed,
        to_regclass('embedding_v2.production_run_requests') AS requests,
        to_regclass('embedding_v2.production_run_items') AS items""")
    row = cur.fetchone()
    if not row or not (row.get('installed') if hasattr(row,'get') else row[0]):
        for related in wanted.values():
            for run in related:run['stage_detail_note'] = 'The historical stage journal is unavailable; original execution records are preserved.'
        return
    cur.execute("""SELECT run_id,status,stages,promotion_id,summary->'counts' AS counts,
        summary->'reconciliation' AS reconciliation,summary->'scoring' AS scoring,
        summary->'training_dataset' AS dataset,summary->'inference' AS inference,
        summary->'users_rebuilt' AS users_rebuilt,summary->'semantic_labeling' AS semantic_labeling FROM embedding_v2.production_runs
        WHERE run_id IN %s""", (tuple(wanted),))
    for journal in cur.fetchall():
        for run in wanted[journal['run_id']]:
            if 'stage_details' not in run:run['stage_details'] = historical_details(journal)
            run['publication_id'] = journal['promotion_id']
            if journal.get('semantic_labeling'):run['semantic_labeling']=journal['semantic_labeling']
    if hasattr(row, 'get') and row.get('requests') and row.get('items'):
        # Catalog titles only. Never expose watch-event IDs, owners, prompts or vectors.
        cur.execute('''WITH media AS (
            SELECT DISTINCT ON (r.run_id,r.item_key) r.run_id,r.item_key AS rating_key,
                COALESCE(i.record->'source'->'metadata'->>'episode_title',
                         i.record->'source'->'metadata'->>'title',i.record->'source'->>'title') AS title,
                i.record->'source'->'metadata'->'show_context'->>'title' AS show_title,
                i.record->'source'->>'media_type' AS media_type,r.recorded_at
            FROM embedding_v2.production_run_requests r
            LEFT JOIN embedding_v2.production_run_items i USING(run_id,kind,item_key)
            WHERE r.run_id IN %s AND r.kind='media_text' AND r.status='succeeded'
            ORDER BY r.run_id,r.item_key,r.recorded_at DESC
        ), ranked AS (
            SELECT *,COUNT(*) OVER(PARTITION BY run_id) AS total,
                ROW_NUMBER() OVER(PARTITION BY run_id ORDER BY recorded_at DESC,rating_key) AS position FROM media
        ) SELECT run_id,rating_key,title,show_title,media_type,total FROM ranked WHERE position<=200
          ORDER BY run_id,position''', (tuple(wanted),))
        media = {}
        for item in cur.fetchall():
            media.setdefault(item['run_id'], []).append(dict(item))
        for key, related in wanted.items():
            titles = media.get(key, [])
            for run in related:
                run['embedded_media'] = [{k:v for k,v in title.items() if k not in {'run_id','total'}} for title in titles]
                run['embedded_media_total'] = titles[0]['total'] if titles else 0
                run['embedded_media_note'] = ('Completed media-text inference requests recovered from durable checkpoints. '
                    'Reused vectors are excluded. These checkpoints can precede publication; at most 200 titles are shown.')
    for related in wanted.values():
        for run in related:
            if 'stage_details' not in run:
                run['stage_detail_note'] = 'No matching historical stage journal remains; original execution records are preserved.'
