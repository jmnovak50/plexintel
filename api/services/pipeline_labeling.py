"""Optional post-publication adapter for the existing semantic-label batch engine."""
from contextlib import closing
import math
import time

from psycopg2 import sql
from psycopg2.extras import Json

from api.db.connection import connect_db
from api.services.app_settings import get_setting_value,resolve_settings,SettingsUnavailableError,SettingsValidationError
from api.services import dimension_label_batch as batch
from api.services.dimension_labeling import Evidence,current_context
from api.services.labeling_costs import BudgetExceeded,UsageLedger,pricing_for_model,LabelingError,failure_diagnostic
from api.embedding_generation.progress import Reporter

SCOPE='daily-semantic-labeling/1'
POLICY_KEYS=('pipeline.labeling_enabled','pipeline.labeling_cloud_authorized',
             'pipeline.labeling_budget_usd','pipeline.labeling_request_limit')


def limits(conn=None):
    """Resolve one strict policy snapshot, locked through reservation if supplied."""
    try:
        resolved=resolve_settings(keys=POLICY_KEYS,require_database=True,conn=conn,lock=conn is not None)
    except (SettingsUnavailableError,SettingsValidationError):
        raise BudgetExceeded('Authoritative automatic labeling policy unavailable') from None
    policy={key:resolved[key].value for key in POLICY_KEYS}
    if policy['pipeline.labeling_enabled'] is not True:raise BudgetExceeded('Automatic labeling disabled')
    if policy['pipeline.labeling_cloud_authorized'] is not True:raise BudgetExceeded('Standing cloud authorization absent')
    cost=float(policy['pipeline.labeling_budget_usd'])
    count=int(policy['pipeline.labeling_request_limit'])
    if not math.isfinite(cost) or cost<=0 or count<=0:raise BudgetExceeded('Positive cumulative budget and request limit required')
    return dict(budget_usd=cost,request_limit=count)


def _eligible_attempts(conn,eligible,context,max_attempts):
    with conn.cursor() as cur:
        cur.execute('''SELECT r.dimension,b.forecast->'automation_prompts'->>r.dimension::text,COUNT(*)
            FROM embedding_label_requests r JOIN embedding_label_batches b USING(batch_id)
            WHERE b.forecast->>'automation_scope'=%s AND b.generation_id=%s
            GROUP BY r.dimension,b.forecast->'automation_prompts'->>r.dimension::text''',(SCOPE,context['generation_id']))
        used={(dimension,prompt):count for dimension,prompt,count in cur.fetchall()}
    return [r for r in eligible if used.get((r['dimension'],batch.prompt_hash(r['prompt'])),0)<max_attempts]


def _run(conn,result,caps):
    import gpt_utils as gpt
    # Bind to the completed daily run, not merely the latest publication.
    with conn.cursor() as cur:
        cur.execute('''SELECT status,promotion_id,summary FROM embedding_v2.production_runs WHERE run_id=%s''',(result['run_id'],))
        saved=cur.fetchone()
    if not saved or saved[0]!='succeeded' or saved[1]!=result['promotion_id']:
        raise ValueError('A successfully published daily run is required')
    summary=saved[2] or {};verified=summary.get('final_verification') or {}
    if (summary.get('outcome')!='daily_completed' or verified.get('publication_id')!=result['promotion_id']
        or verified.get('generation_id')!=result['generation_id'] or not verified.get('verified')
        or verified.get('model_sha256')!=summary.get('model_after')):
        raise ValueError('Final daily publication verification is missing or inconsistent')
    prior=summary.get('semantic_labeling') or {}
    if prior.get('status') in ('completed','completed_with_errors','budget_stopped','failed','systemic_failure_stopped','empty'):
        return dict(prior,reused=True,reason='A terminal labeling outcome is already recorded for this publication')
    with conn.cursor() as cur:
        cur.execute('''SELECT batch_id,status,summary FROM embedding_label_batches
            WHERE forecast->>'automation_scope'=%s AND forecast->>'automation_run_id'=%s
            AND forecast->>'automation_publication_id'=%s AND status NOT IN ('running','interrupted')
            ORDER BY created_at DESC LIMIT 1''',(SCOPE,result['run_id'],result['promotion_id']))
        previous=cur.fetchone()
    if previous:
        return dict(previous[2],batch_id=previous[0],status=previous[1],reused=True,
                    reason='Existing terminal batch recovered without another provider request')
    context=current_context(conn)
    if any(context[k]!=verified[k] for k in ('generation_id','publication_id','model_sha256')):
        raise ValueError('Current production differs from the verified daily publication')
    args=batch.parser().parse_args([])
    args.label_provider,args.label_model=gpt.resolve_label_backend()
    if args.label_provider!='ollama':
        raise LabelingError('AUTOMATIC_PROVIDER_UNSUPPORTED','configuration','Automatic current-generation labeling requires the Ollama provider in Setup')
    args.model_source='Setup: labeling.ollama_model'
    args.limit=int(get_setting_value('pipeline.label_batch_limit',default=25))
    args.dim_type=get_setting_value('pipeline.label_dim_type',default='all')
    args.selection_mode=get_setting_value('pipeline.label_selection_mode',default='eligible')
    if args.limit<1 or args.dim_type not in ('media','user','all') or args.selection_mode not in ('eligible','importance'):
        raise LabelingError('AUTOMATIC_SELECTION_UNSUPPORTED','configuration','Use a positive batch limit, media/user/all scope and eligible/importance selection')
    args.regenerate=bool(get_setting_value('pipeline.refresh_existing_labels',default=False))
    args.max_output_tokens=gpt.label_output_limit(None);args.label=True;args.save_label=True
    args.budget_usd=caps['budget_usd']
    try:pricing=pricing_for_model(args.label_model)
    except ValueError:
        raise LabelingError('AUTOMATIC_PRICING_UNKNOWN','configuration','Configured model has no supported default pricing; automatic requests are blocked') from None
    evidence=Evidence(conn,args.top_n)
    if evidence.context!=context:raise ValueError('Label evidence provenance changed')
    eligible,ineligible=batch.candidates(conn,evidence)
    eligible=_eligible_attempts(conn,eligible,context,args.max_attempts)
    if args.regenerate:
        with conn.cursor() as cur:
            cur.execute('''SELECT DISTINCT a.dimension FROM embedding_dimension_assessments a
                JOIN embedding_label_batches b ON b.batch_id=a.result->>'batch_id'
                WHERE b.forecast->>'automation_scope'=%s AND b.forecast->>'automation_run_id'=%s
                AND b.forecast->>'automation_publication_id'=%s AND (a.saved OR a.outcome='abstained')''',
                (SCOPE,result['run_id'],result['promotion_id']))
            finished={r[0] for r in cur.fetchall()}
        eligible=[r for r in eligible if r['dimension'] not in finished]
    selected=batch.choose(eligible,args)
    if not selected:return dict(status='empty',reason='No eligible unfinished dimensions within attempt limits',selected=0)
    # Existing refresh semantics remain explicit and bounded to this selection.
    if args.regenerate:args.dimensions=[row['dimension'] for row in selected]
    prompts={str(r['dimension']):batch.prompt_hash(r['prompt']) for r in selected}
    args.automation=dict(scope=SCOPE,generation_id=context['generation_id'],prompts=prompts,
                         max_attempts=args.max_attempts,limits=limits)
    observations=UsageLedger(conn,'forecast-only',pricing).observations(context['config_id'],args.label_model)
    prediction=batch.workload_forecast(eligible,selected,pricing,args,observations)
    prediction.update(automation_scope=SCOPE,automation_prompts=prompts,
                      automation_publication_id=context['publication_id'],automation_run_id=result['run_id'])
    conn.rollback();conn.set_session(readonly=False,isolation_level='READ COMMITTED')
    return batch.execute(conn,evidence,eligible,selected,pricing,args,prediction)


def run_after_publication(store,result,*,publication_lock,pipeline_lock_held=False,output=lambda value:None):
    """Never enters the predictive worker's failure/retry boundary."""
    def safe_output(value):
        try:output(value)
        except Exception:pass
    reporter=Reporter(safe_output);reporter.bind(result['run_id'])
    if result.get('verification_only'):
        reporter.skip('semantic_labels')
        return dict(status='skipped',reason='Verification-only recovery does not start labeling')
    started=time.perf_counter()
    try:
        try:caps=limits()
        except BudgetExceeded as exc:
            outcome=dict(status='skipped',reason=str(exc))
        else:
            reporter.emit('semantic_labels','started')
            with publication_lock(pipeline_lock_held):
                with closing(connect_db()) as conn:
                    conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
                    outcome=_run(conn,result,caps)
    except BaseException as exc:
        # Provider errors, interrupts and unavailable optional ledgers never
        # reclassify an already committed/verified model run as failed.
        outcome=dict(getattr(exc,'labeling_summary',{}) or {})
        diagnostic=failure_diagnostic(exc)
        outcome.update(status='interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',
                       reason=diagnostic['message'],error_code=diagnostic['code'])
        if 'usage' not in outcome:outcome['usage_unavailable']=True
    outcome['seconds']=time.perf_counter()-started
    usage=outcome.get('usage') or {}
    outcome.setdefault('reason',f"Selected {outcome.get('selected',0)}; saved {outcome.get('successes',0)}, "
        f"abstained {outcome.get('abstentions',0)}, failed {outcome.get('failures',0)}; "
        f"reserved/estimated USD {usage.get('estimated_cost_usd',0):.6f}")
    status='skipped' if outcome.get('reused') or outcome['status'] in ('skipped','empty') else 'success' if outcome['status']=='completed' else 'failed'
    metrics={k:usage[k] for k in ('requests','input_tokens','output_tokens','total_tokens','estimated_cost_usd') if k in usage}
    if outcome.get('reused'):metrics={'requests':0}  # Historical usage remains in the durable outcome.
    reporter.emit('semantic_labels',status,message=outcome.get('reason') or outcome['status'],expected=outcome.get('selected',0),
                  reused=bool(outcome.get('reused')),
                  **{k:outcome[k] for k in ('selected','successes','failures','abstentions','seconds') if k in outcome},
                  **metrics)
    try:
        store.query(sql.SQL("""UPDATE {} SET summary=jsonb_set(COALESCE(summary,'{{}}'::jsonb),
            '{{semantic_labeling}}',%s::jsonb) WHERE run_id=%s AND promotion_id=%s AND status='succeeded'""")
            .format(store.table('production_runs')),(Json(outcome),result['run_id'],result['promotion_id']))
        store.conn.commit()
    except Exception:
        try:store.conn.rollback()
        except Exception:pass
    result['summary']['semantic_labeling']=outcome
    return outcome
