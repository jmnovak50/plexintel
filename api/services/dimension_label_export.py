"""Local CSV exports of saved labeling records; no prompts, inference or writes."""
import csv
from datetime import datetime, timezone
from pathlib import Path
import os
import tempfile

from psycopg2.extras import RealDictCursor

from api.services.dimension_labeling import current_context


def fieldnames():
    from batch_label_embeddings import CSV_FIELDNAMES
    omitted = {'selection_mode', 'label_repair_status', 'selection_reason', 'unlock_count_total',
        'marginal_unlock_count', 'marginal_weighted_unlock_score', 'cumulative_unlocked_recommendations',
        'positive_shap_sum_on_unlabeled', 'positive_shap_avg_on_unlabeled', 'mode', 'summary',
        'prompt_text', 'combined_score', 'review_cooldown_until', 'gpt_label'}
    return [name for name in CSV_FIELDNAMES if name not in omitted] + [
        'batch_id', 'batch_status', 'batch_link_source', 'assessment_id', 'assessment_source',
        'processing_date', 'processing_timezone', 'exported_at_utc', 'processing_outcome', 'saved',
        'explanation_eligible', 'final_explanation_eligible', 'final_state_scope', 'error_code', 'error_category',
        'attempt_count', 'failed_attempt_count', 'pending_attempt_count', 'request_error_codes',
        'input_tokens', 'cached_input_tokens', 'output_tokens', 'token_totals_are_complete',
        'estimated_cost_usd', 'cost_basis', 'minimum_label_coverage_percent', 'maximum_low_overlap_percent',
        'interpretation_model', 'config_id', 'generation_id', 'contract_hash', 'encoder_digest', 'encoder_model',
        'model_sha256', 'publication_id',
    ]


def excel_cell(value):
    """CSV quoting alone does not stop Excel from evaluating untrusted text."""
    if not isinstance(value, str):
        return value
    probe = value
    while probe and (probe[0].isspace() or probe[0] in '\ufeff\u200b'):
        probe = probe[1:]
    if probe.startswith(('=', '+', '-', '@', '＝', '＋', '－', '＠')) or value.startswith(('\t', '\r', '\n')):
        return "'" + value
    return value


def error_category(code):
    if not code:
        return None
    if code.startswith(('HTTP_', 'PROVIDER_')) or code == 'INCOMPLETE_RESPONSE':
        return 'provider'
    return {'OUTPUT_TRUNCATED':'truncation', 'INVALID_JSON_SYNTAX':'json_syntax',
        'INVALID_JSON_TYPES':'json_schema', 'INVALID_JSON_FIELDS':'json_schema',
        'MISSING_JSON_FIELDS':'json_schema', 'MULTIPLE_JSON_OBJECTS':'json_schema',
        'LABEL_COVERAGE_MISMATCH':'label_validation', 'MODEL_NOT_FOUND':'configuration',
        'LABELING_INTERNAL_ERROR':'internal'}.get(code, 'unknown')


def write_csv(filename, rows):
    """Atomic replacement with private permissions, UTF-8 BOM and Excel newlines."""
    target = Path(filename).expanduser()
    if target.is_symlink():
        raise ValueError('Refusing to replace a symlink with a private CSV export')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='',
                dir=target.parent, prefix='.' + target.name + '.', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)  # NamedTemporaryFile creates mode 0600.
            writer = csv.DictWriter(handle, fieldnames=fieldnames(), quoting=csv.QUOTE_ALL, lineterminator='\r\n')
            writer.writeheader()
            for row in rows:
                writer.writerow({key: excel_cell(value) for key, value in row.items()})
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_records(conn, context):
    """Select explicit export fields; never load raw prompt text or prompt examples."""
    identity = (context['config_id'], context['generation_id'], context['contract_hash'], context['encoder_digest'])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT * FROM embedding_labels WHERE config_id=%s AND generation_id=%s
            AND contract_hash=%s AND encoder_digest=%s ORDER BY dimension''', identity)
        labels = {r['dimension']: dict(r) for r in cur.fetchall()}
        cur.execute('''SELECT assessment_id,dimension,source,provider,model,result,saved,outcome,
            before_state,after_state,created_at,
            jsonb_build_object('minimum_label_coverage_percent',prompt->'minimum_label_coverage_percent',
                'maximum_low_overlap_percent',prompt->'maximum_low_overlap_percent',
                'valid_positive_count',prompt->'valid_positive_count',
                'valid_negative_count',prompt->'valid_negative_count',
                'flagged_item_count',prompt->'flagged_item_count',
                'skipped_reason',prompt->'skipped_reason') AS prompt_metadata
            FROM embedding_dimension_assessments
            WHERE config_id=%s
              AND COALESCE(result->'provenance',prompt->'provenance')->>'generation_id'=%s
              AND COALESCE(result->'provenance',prompt->'provenance')->>'contract_hash'=%s
              AND COALESCE(result->'provenance',prompt->'provenance')->>'encoder_digest'=%s
            ORDER BY assessment_id''', identity)
        assessments = [dict(r) for r in cur.fetchall()]
        cur.execute('''SELECT batch_id,config_id,generation_id,model,dimensions,status,created_at,completed_at
            FROM embedding_label_batches WHERE config_id=%s AND generation_id=%s ORDER BY created_at''', identity[:2])
        batches = {r['batch_id']: dict(r) for r in cur.fetchall()}
        cur.execute('''SELECT r.* FROM embedding_label_requests r JOIN embedding_label_batches b USING(batch_id)
            WHERE b.config_id=%s AND b.generation_id=%s ORDER BY r.request_id''', identity[:2])
        requests = [dict(r) for r in cur.fetchall()]
    return labels, assessments, batches, requests


def collect_events(labels, assessments, batches, requests, batch_id=None):
    """One result per dimension in a batch; snapshot chooses its latest event.

    Historical assessments lack batch IDs. Associate only a unique matching
    model/dimension/request/time window; uncertain links remain unassigned.
    Request-only rows preserve interrupted or unrecorded outcomes.
    """
    groups = {}
    for request in requests:
        groups.setdefault((request['batch_id'], request['dimension']), []).append(request)
    linked = {}
    events = []
    for assessment in assessments:
        event = dict(assessment, batch_id=None, batch_link_source='assessment_only')
        explicit = assessment['result'].get('batch_id')
        matches = []
        for (bid, dimension), attempts in groups.items():
            batch = batches[bid]
            if dimension != assessment['dimension'] or batch['model'] != assessment['model']:
                continue
            if explicit:
                if bid == explicit:
                    matches.append(bid)
            elif (assessment['source'] == 'manual-batch'
                  and batch['created_at'] <= assessment['created_at']
                  and min(r['created_at'] for r in attempts) <= assessment['created_at']
                  and (batch['completed_at'] is None or assessment['created_at'] <= batch['completed_at'])):
                matches.append(bid)
        if len(matches) == 1:
            event.update(batch_id=matches[0], batch_link_source='explicit' if explicit else 'legacy_time_window')
            linked[(matches[0], assessment['dimension'])] = event  # Assessments are ordered by ID.
        elif matches or explicit:
            event['batch_link_source'] = 'unresolved_batch_link'
        events.append(event)
    for key, attempts in groups.items():
        if key in linked:
            continue
        last = attempts[-1]
        outcome = {'failed': 'failed_without_assessment', 'pending': 'pending_without_assessment'}.get(
            last['status'], 'result_not_recorded')
        event = dict(dimension=key[1], batch_id=key[0], batch_link_source='request_ledger_only',
            created_at=last['completed_at'] or last['created_at'], outcome=outcome, result={}, saved=False)
        linked[key] = event
        events.append(event)
    if batch_id is not None:
        if batch_id not in batches:
            raise ValueError('Batch UUID was not found in the active embedding configuration/generation')
        batch = batches[batch_id]
        dimensions = set(batch['dimensions']) | {d for b, d in linked if b == batch_id}
        return [linked.get((batch_id, dimension), dict(dimension=dimension, batch_id=batch_id,
            batch_link_source='batch_inventory_only', created_at=None, outcome='not_processed', result={}, saved=False))
            for dimension in sorted(dimensions)], groups
    latest = {}
    for event in events:
        key = (event['created_at'], event.get('assessment_id', 0))
        previous = latest.get(event['dimension'])
        if previous is None or key > (previous['created_at'], previous.get('assessment_id', 0)):
            latest[event['dimension']] = event
    for dimension, label in labels.items():
        latest.setdefault(dimension, dict(dimension=dimension, created_at=label.get('created_at'),
            outcome='saved_label_only', result={}, batch_id=None, batch_link_source='saved_label_only'))
    return [latest[d] for d in sorted(latest)], groups


def shap_statistics(conn, context):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT s.dimension,COUNT(*) AS usage_count,SUM(ABS(s.shap_value)) AS sum_abs_shap,
            AVG(ABS(s.shap_value)) AS avg_abs_shap,COUNT(DISTINCT s.user_id) AS user_count
            FROM shap_impact s JOIN shap_prediction_context c ON c.username=s.user_id AND c.rating_key=s.rating_key
            JOIN recommendations r ON r.username=c.username AND r.rating_key=c.rating_key AND r.scored_at=c.scored_at
            WHERE c.config_id=%s AND c.model_version=%s AND s.dimension BETWEEN 0 AND 1535
              AND s.shap_value::text NOT IN ('NaN','Infinity','-Infinity') GROUP BY s.dimension''',
            (context['config_id'], context['model_sha256']))
        return {r['dimension']: dict(r) for r in cur.fetchall()}


def format_row(event, saved_label, batch, attempts, stats, context, historical=False):
    from batch_label_embeddings import (classify_validated_label_governance, is_saved_label_usable_for_explanation,
                                        MINIMUM_LABEL_COVERAGE_PERCENT, MAXIMUM_LOW_OVERLAP_PERCENT)
    result = event['result']
    metadata = event.get('prompt_metadata') or {}
    minimum = metadata.get('minimum_label_coverage_percent')
    maximum = metadata.get('maximum_low_overlap_percent')
    minimum = MINIMUM_LABEL_COVERAGE_PERCENT if minimum is None else minimum
    maximum = MAXIMUM_LOW_OVERLAP_PERCENT if maximum is None else maximum
    dimension = event['dimension']
    side = 'media' if dimension < 768 else 'user'
    final = (event.get('after_state') if historical else saved_label) or {}
    before = event.get('before_state') or {}
    generated = result.get('label', '')
    governance = classify_validated_label_governance(result, side,
        minimum_label_coverage_percent=minimum, maximum_low_overlap_percent=maximum)
    if not result:
        governance = {key: None for key in ('label_type','explainable','display_label','needs_review')}
    label_only = event['outcome'] == 'saved_label_only'
    if not historical and final and (label_only or generated == final.get('label')):
        governance = {key: final.get(key) for key in ('label_type','explainable','display_label','needs_review')}
    if label_only and final:
        generated = final.get('label', '')
    date = event.get('created_at')
    evidence = result.get('evidence') or []
    diagnostic = result.get('error_diagnostics') or {}
    error_codes = list(dict.fromkeys(r['error_code'] for r in attempts if r.get('error_code')))
    code = result.get('error_code') or (error_codes[-1] if error_codes else None)
    category = diagnostic.get('category') or error_category(code)
    if not category and result.get('processing_error'):
        category = 'unknown'  # Historical RuntimeError records cannot recover their original cause.
    measured = bool(attempts) and all(r['input_tokens'] is not None and r['output_tokens'] is not None for r in attempts)
    row = dict(dimension=dimension, dim_type=side, batch_id=event.get('batch_id'),
        batch_status=batch.get('status'), batch_link_source=event['batch_link_source'],
        assessment_id=event.get('assessment_id'), assessment_source=event.get('source'),
        processing_date=(date.astimezone(timezone.utc) if date.tzinfo else date).strftime('%Y-%m-%d %H:%M:%S') if date else None,
        processing_timezone='UTC' if not date or date.tzinfo else 'unspecified database local time',
        exported_at_utc=datetime.now(timezone.utc).isoformat(),
        label_provider=event.get('provider'), label_model=event.get('model') or batch.get('model') or final.get('interpretation_model'),
        proposed_label=generated, proposed_label_confidence=result.get('label_confidence'),
        proposed_label_type=result.get('proposed_label_type') or result.get('label_type'),
        label=generated, label_confidence=result.get('label_confidence'), **governance,
        explanation_eligible=is_saved_label_usable_for_explanation(governance),
        final_saved_label=final.get('label'), final_label_type=final.get('label_type'),
        final_explainable=final.get('explainable'), final_needs_review=final.get('needs_review'),
        final_display_label=final.get('display_label'), final_explanation_eligible=is_saved_label_usable_for_explanation(final),
        final_state_scope='assessment_time' if historical else 'current_saved_label',
        validation_status=result.get('validation_status'), validation_notes='\n'.join(result.get('validation_notes') or []),
        label_explanation=result.get('explanation'), processing_outcome=event['outcome'], saved=event.get('saved'),
        error_code=code, error_category=category,
        attempt_count=len(attempts), failed_attempt_count=sum(r['status']=='failed' for r in attempts),
        pending_attempt_count=sum(r['status']=='pending' for r in attempts), request_error_codes='; '.join(error_codes),
        token_totals_are_complete=measured if attempts else None,
        estimated_cost_usd=sum(r['estimated_cost_usd'] for r in attempts) if attempts else None,
        cost_basis=('metered token estimate' if measured and all(r['status']!='pending' for r in attempts)
                    else 'includes reserved estimates') if attempts else 'usage unavailable',
        minimum_label_coverage_percent=minimum, maximum_low_overlap_percent=maximum,
        stats_source='current matching model/prediction context' if stats else 'unavailable')
    row['interpretation_model'] = row['label_model']
    for name in ('coverage_high_count','coverage_high_total','coverage_high_percent',
                 'coverage_low_overlap_count','coverage_low_total','coverage_low_overlap_percent'):
        row[name] = result.get(name)
    for index in range(3):
        row[f'label_evidence_{index+1}'] = evidence[index] if index < len(evidence) else None
    for name in ('valid_positive_count','valid_negative_count','flagged_item_count','skipped_reason'):
        row[name] = metadata.get(name)
    for name in ('label','display_label','label_type','explainable','needs_review'):
        row['existing_' + name] = before.get(name)
    for name in ('last_reviewed_at','review_attempt_count','next_review_at'):
        value = final.get(name)
        row[name] = value.isoformat() if hasattr(value,'isoformat') else value
    for name in ('input_tokens','cached_input_tokens','output_tokens'):
        values = [r[name] for r in attempts if r[name] is not None]
        row[name] = sum(values) if values else None
    row.update({name:stats[name] for name in ('usage_count','sum_abs_shap','avg_abs_shap','user_count') if name in stats})
    row.update({name:context.get(name) for name in ('config_id','generation_id','contract_hash','encoder_digest',
                                                  'encoder_model','model_sha256','publication_id')})
    return row


def export_csv(conn, filename, *, batch_id=None, dim_type='all', dimensions=None):
    # Enforce a stable read-only snapshot even for callers other than the CLI.
    with conn.cursor() as cur:
        cur.execute('SHOW transaction_read_only')
        if cur.fetchone()[0] != 'on':
            raise ValueError('CSV export requires a read-only database transaction')
    context = current_context(conn)
    labels, assessments, batches, requests = load_records(conn, context)
    events, groups = collect_events(labels, assessments, batches, requests, batch_id)
    stats = shap_statistics(conn, context)
    rows = []
    for event in events:
        dimension = event['dimension']
        if dimensions is not None and dimension not in dimensions:
            continue
        if dim_type != 'all' and dim_type != ('media' if dimension < 768 else 'user'):
            continue
        rows.append(format_row(event, labels.get(dimension), batches.get(event.get('batch_id'), {}),
            groups.get((event.get('batch_id'), dimension), []), stats.get(dimension, {}), context, historical=bool(batch_id)))
    write_csv(filename, rows)
    return dict(export_csv=str(Path(filename).expanduser()), rows=len(rows), batch_id=batch_id,
                generation_id=context['generation_id'], cloud_requests_started=0,
                warning='Private local evidence. CSV is not an invoice; unknown token counts stay blank. Keep out of Git.')
