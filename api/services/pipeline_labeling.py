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
from api.predictive.progress import Reporter

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
            WHERE b.forecast->>'automation_scope'=%s AND b.feature_space_id=%s
            GROUP BY r.dimension,b.forecast->'automation_prompts'->>r.dimension::text''',(SCOPE,context['feature_space_id']))
        used={(dimension,prompt):count for dimension,prompt,count in cur.fetchall()}
    return [r for r in eligible if used.get((r['dimension'],batch.prompt_hash(r['prompt'])),0)<max_attempts]


def _run(conn,result,caps):
    import gpt_utils as gpt
    if result.get('verification_only') or not result.get('verified'):
        raise ValueError('Fresh verified predictive publication required')
    from api.predictive.artifacts import current_config
    config=current_config(conn)
    if not config or config.get('workload_id')!=result['promotion_id'] or config.get('model_sha256')!=result['model_sha256']:
        raise ValueError('Current model differs from completed workload')
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
    if (context['publication_id']!=result['promotion_id'] or context['model_sha256']!=result['model_sha256']):
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
    args.automation=dict(scope=SCOPE,feature_space_id=context['feature_space_id'],prompts=prompts,
                         max_attempts=args.max_attempts,limits=limits)
    observations=UsageLedger(conn,'forecast-only',pricing).observations(context['config_id'],args.label_model)
    prediction=batch.workload_forecast(eligible,selected,pricing,args,observations)
    prediction.update(automation_scope=SCOPE,automation_prompts=prompts,
                      automation_publication_id=context['publication_id'],automation_run_id=result['run_id'])
    conn.rollback();conn.set_session(readonly=False,isolation_level='READ COMMITTED')
    return batch.execute(conn,evidence,eligible,selected,pricing,args,prediction)


def run_after_publication(result,*,output=lambda value:None):
    """Optional work stays outside the predictive failure/retry boundary.

    Caller retains the ordinary predictive writer lock so publication cannot
    change while a provider request is admitted and its interpretation saved.
    """
    if result.get('verification_only') or not result.get('verified'):
        return dict(status='skipped',reason='No fresh verified predictive workload')
    started=time.perf_counter()
    try:
        try:caps=limits()
        except BudgetExceeded as exc:return dict(status='skipped',reason=str(exc))
        with closing(connect_db()) as conn:
            conn.set_session(readonly=False,isolation_level='READ COMMITTED')
            outcome=_run(conn,result,caps)
    except BaseException as exc:
        diagnostic=failure_diagnostic(exc)
        outcome=dict(status='interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',
            reason=diagnostic['message'],error_code=diagnostic['code'])
    outcome['seconds']=time.perf_counter()-started
    try:output(outcome)
    except Exception:pass
    return outcome
