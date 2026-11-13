"""Read-only presentation of current events and immutable historical run evidence."""
import json
from uuid import UUID

from api.predictive.progress import STAGES, STAGE_NAMES, clean_metrics, event_details

WORKERS = {'embeddinggemma2_generation', 'predictive_daily'}


def retained_report(run, worker):
    """Read bounded evidence tied to this exact execution, never a latest artifact.

    The final JSON receipt often exceeds the database's 5000-character tail.
    Missing/rotated/ambiguous files are ordinary unavailable history.
    """
    texts = [worker.get('stdout_tail') or '']
    rid = run.get('run_id')
    if isinstance(rid, int):
        from api.services.pipeline_service import get_pipeline_log_path
        paths = list(get_pipeline_log_path().parent.glob(
            f'pipeline-run-{rid}-{worker["stage_key"]}-*.stdout.log'))
        if len(paths) == 1:
            try:
                with paths[0].open('rb') as handle:
                    handle.seek(0, 2)
                    handle.seek(max(0, handle.tell()-256*1024))
                    texts.append(handle.read(256*1024).decode('utf-8', errors='replace'))
            except OSError:pass
    for text in reversed(texts):
        for line in reversed(text.splitlines()):
            try:value = json.loads(line)
            except ValueError:continue
            if not isinstance(value, dict):continue
            if (value.get('run_id') and isinstance(value.get('counts'), dict)
                    and (value.get('verified') is True or isinstance(value.get('stages'), dict))):
                return value
    return None


def supplement(details, report):
    """Allowlisted aggregates only; never project current production onto history."""
    counts = report.get('counts') or {}
    summary = report.get('summary') or {}
    evaluation = report.get('evaluation') or {}
    metrics = dict(
        source_sync=dict(quarantined=(summary.get('watch_coverage') or {}).get('quarantined_watch_events')),
        training_data=dict(rows=summary.get('rows'),
            label_policy_skips=(summary.get('skips') or {}).get('label_policy'),
            limited_history_skips=(summary.get('skips') or {}).get('limited_history')),
        train_model=dict(chronological_balanced_accuracy=(evaluation.get('chronological') or {}).get('balanced_accuracy'),
            chronological_average_precision=(evaluation.get('chronological') or {}).get('average_precision'),
            show_balanced_accuracy=(evaluation.get('show_heldout') or {}).get('balanced_accuracy')),
        shap=dict(contexts=counts.get('shap_prediction_context'),contributions=counts.get('shap_impact')))
    if evaluation.get('gates'):metrics['train_model']['quality_passed'] = all(evaluation['gates'].values())
    for row in details:
        row['metrics'] = dict(clean_metrics(metrics.get(row['stage_key'], {})), **row.get('metrics', {}))
        if row['stage_key'] == 'score_model' and report.get('verified'):
            row['message'] = 'Duration includes SHAP generation and staged prediction persistence.'
        if row['stage_key'] == 'semantic_labels' and row['status'] == 'not_recorded':
            labeling = report.get('semantic_labeling') or {}
            if labeling.get('status') in ('skipped','failed','success','completed','empty'):
                row.update(status='success' if labeling['status'] in ('completed','empty') else labeling['status'],
                    message=labeling.get('reason'),duration_seconds=labeling.get('seconds'),
                    timing_known='seconds' in labeling,detail_source='retained_worker_receipt')
                row['metrics'].update(clean_metrics(labeling))


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
    for key, label in STAGES[:10]:  # Archived workers had no optional-label stage.
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
            message=message, detail_source='retained_worker_receipt', started_at=None, completed_at=None))
    return output


def enrich_runs(cur,runs):
    """Project public events and retained receipts; no journal queries or writes."""
    for run in runs:
        workers = [s for s in run['stages'] if s['stage_key'] in WORKERS]
        # Legacy multi-process runs must retain every original stage, even keys
        # shared with the logical-stage vocabulary.
        if not workers:continue
        details=[event_details(stage) for stage in run['stages'] if stage['stage_key'] in STAGE_NAMES]
        report = retained_report(run, workers[-1])
        if not details and report and workers[-1]['stage_key'] == 'embeddinggemma2_generation':
            details = historical_details(dict(report,status='succeeded' if run.get('status') == 'success' else run.get('status'),
                stages=report['stages'],dataset=report.get('training_dataset')))
        if report and details:
            supplement(details, report)
            run['publication_id'] = report.get('promotion_id')
            labeling = report.get('semantic_labeling')
            if isinstance(labeling, dict):
                run['semantic_labeling'] = {k:labeling[k] for k in ('status','reason') if k in labeling}
        if details:
            run['stage_details']=sorted(details,key=lambda row:list(STAGE_NAMES).index(row['stage_key']))
        else:
            run['stage_detail_note']='Historical execution log retained; migration journals are not queried. Separate stage details are unavailable in retained logs.'
