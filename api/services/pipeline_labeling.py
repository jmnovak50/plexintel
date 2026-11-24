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
from api.services.labeling_costs import cumulative_usage
from api.predictive.progress import Reporter

SCOPE='daily-semantic-labeling/1'
POLICY_KEYS=('pipeline.labeling_enabled','pipeline.labeling_cloud_authorized',
             'pipeline.labeling_budget_usd')


def _observe(output,value):
    try:
        if output:output(value)
    except Exception:pass


def limits(conn=None, *, observe=None):
    """Resolve one strict policy snapshot, locked through reservation if supplied."""
    try:
        resolved=resolve_settings(keys=POLICY_KEYS,require_database=True,conn=conn,lock=conn is not None)
    except (SettingsUnavailableError,SettingsValidationError):
        raise BudgetExceeded('Authoritative automatic labeling policy unavailable') from None
    policy={key:resolved[key].value for key in POLICY_KEYS}
    _observe(observe,dict(event='labeling_policy',policy=policy))
    if policy['pipeline.labeling_enabled'] is not True:raise BudgetExceeded('Automatic labeling disabled')
    if policy['pipeline.labeling_cloud_authorized'] is not True:raise BudgetExceeded('Standing cloud authorization absent')
    cost=float(policy['pipeline.labeling_budget_usd'])
    if not math.isfinite(cost) or cost<=0:raise BudgetExceeded('Positive cumulative budget required')
    return dict(budget_usd=cost)


def check_allowance(conn,caps):
    """Cheap preflight; exact prompt reservations still gate every request."""
    from decimal import Decimal
    usage=cumulative_usage(conn,SCOPE)
    if Decimal(str(usage['estimated_cost_usd']))>=Decimal(str(caps['budget_usd'])):
        raise BudgetExceeded('Cumulative labeling financial allowance exhausted')
    return usage


def _eligible_attempts(conn,eligible,context,max_attempts):
    used=_attempt_counts(conn,context)
    return [r for r in eligible if used.get((r['dimension'],batch.prompt_hash(r['prompt'])),0)<max_attempts]


def _attempt_counts(conn,context):
    with conn.cursor() as cur:
        cur.execute('''SELECT r.dimension,b.forecast->'automation_prompts'->>r.dimension::text,COUNT(*)
            FROM embedding_label_requests r JOIN embedding_label_batches b USING(batch_id)
            WHERE b.forecast->>'automation_scope'=%s AND b.feature_space_id=%s
            GROUP BY r.dimension,b.forecast->'automation_prompts'->>r.dimension::text''',(SCOPE,context['feature_space_id']))
        return {(dimension,prompt):count for dimension,prompt,count in cur.fetchall()}


def _run(conn,result,caps,*,output=None):
    import gpt_utils as gpt
    observed={}
    def notify(value):
        # The outer adapter owns the one timed terminal summary. execute() still
        # returns/persists it and owns its terminal output for standalone CLI use.
        if 'final_status' in value:return
        if output:
            value=dict(value,limits=caps)
            try:
                with conn.cursor() as cur:
                    cur.execute('SAVEPOINT labeling_log_usage')
                    try:
                        usage=cumulative_usage(conn,SCOPE)
                    except Exception:
                        cur.execute('ROLLBACK TO SAVEPOINT labeling_log_usage')
                        raise
                    finally:cur.execute('RELEASE SAVEPOINT labeling_log_usage')
                value['cumulative_usage']=usage
                observed['cumulative_usage']=value['cumulative_usage']
            except Exception:pass  # Observation cannot authorize or stop a request.
            _observe(output,value)
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
        outcome=dict(previous[2],batch_id=previous[0],status=previous[1],reused=True,
                     reason='Existing terminal batch recovered without another provider request')
        return dict(outcome,limits=caps,**observed)
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
    if args.dim_type == 'user':
        raise LabelingError('USER_LABELING_RETIRED','configuration','User/watch dimensions are historical only; select media or all eligible media')
    from api.services.dimension_config import feature_groups
    args.labeling_inventory={side:sum(g['width'] for g in feature_groups(context) if g['name'] in names)
        for side,names in [('media',('media','media_text')),('user',('user',))]}
    args.selection_mode=get_setting_value('pipeline.label_selection_mode',default='eligible')
    if args.limit<1 or args.dim_type not in ('media','user','all') or args.selection_mode not in ('eligible','importance'):
        raise LabelingError('AUTOMATIC_SELECTION_UNSUPPORTED','configuration','Use a positive batch limit, media/all eligible media scope and eligible/importance selection')
    args.regenerate=bool(get_setting_value('pipeline.refresh_existing_labels',default=False))
    args.max_output_tokens=gpt.label_output_limit(None);args.label=True;args.save_label=True
    args.budget_usd=caps['budget_usd']
    try:pricing=pricing_for_model(args.label_model)
    except ValueError:
        raise LabelingError('AUTOMATIC_PRICING_UNKNOWN','configuration','Configured model has no supported default pricing; automatic requests are blocked') from None
    observed['cumulative_usage']=check_allowance(conn,caps)
    attempts=_attempt_counts(conn,context)
    finished=set()
    if args.regenerate:
        with conn.cursor() as cur:
            cur.execute('''SELECT DISTINCT a.dimension FROM embedding_dimension_assessments a
                JOIN embedding_label_batches b ON b.batch_id=a.result->>'batch_id'
                WHERE b.forecast->>'automation_scope'=%s AND b.forecast->>'automation_run_id'=%s
                AND b.forecast->>'automation_publication_id'=%s AND (a.saved OR a.outcome='abstained')''',
                (SCOPE,result['run_id'],result['promotion_id']))
            finished={r[0] for r in cur.fetchall()}
    evidence=Evidence(conn,args.top_n)
    if evidence.context!=context:raise ValueError('Label evidence provenance changed')
    eligible,ineligible=batch.candidates(conn,evidence,output=notify,args=args,
        attempt_counts=attempts,exclude_dimensions=finished)
    selected=batch.choose(eligible,args)
    notify(dict(event='labeling_selection',selected=len(selected),
                evidence_scope='selected_batch',preparation=ineligible))
    if not selected:return dict(status='empty',reason='No eligible unfinished dimensions within attempt limits',selected=0,
        assessed=0,usage=dict(requests=0,estimated_cost_usd=0.),limits=caps,**observed)
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
    outcome=batch.execute(conn,evidence,eligible,selected,pricing,args,prediction,output=notify)
    return dict(outcome,limits=caps,**observed)


def run_after_publication(result,*,output=None):
    """Optional work stays outside the predictive failure/retry boundary.

    Caller retains the ordinary predictive writer lock so publication cannot
    change while a provider request is admitted and its interpretation saved.
    """
    if result.get('verification_only') or not result.get('verified'):
        return dict(status='skipped',reason='No fresh verified predictive workload')
    started=time.perf_counter()
    try:
        try:caps=limits(observe=output)
        except BudgetExceeded as exc:outcome=dict(status='skipped',reason=str(exc),assessed=0,
            usage=dict(requests=0,estimated_cost_usd=0.))
        else:
            with closing(connect_db()) as conn:
                conn.set_session(readonly=False,isolation_level='READ COMMITTED')
                try:outcome=_run(conn,result,caps,output=output)
                except BudgetExceeded as exc:
                    outcome=dict(status='skipped',reason=str(exc),assessed=0,usage=dict(requests=0,estimated_cost_usd=0.))
                except BaseException as exc:
                    diagnostic=failure_diagnostic(exc)
                    outcome=dict(getattr(exc,'labeling_summary',{}) or {},
                        status='interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',
                        reason=diagnostic['message'],error_code=diagnostic['code'])
                try:outcome['cumulative_usage']=cumulative_usage(conn,SCOPE)
                except Exception:pass
    except BudgetExceeded as exc:
        outcome=dict(status='skipped',reason=str(exc),assessed=0,usage=dict(requests=0,estimated_cost_usd=0.))
    except BaseException as exc:
        diagnostic=failure_diagnostic(exc)
        outcome=dict(status='interrupted' if isinstance(exc,(KeyboardInterrupt,SystemExit)) else 'failed',
            reason=diagnostic['message'],error_code=diagnostic['code'])
    outcome['seconds']=time.perf_counter()-started
    if 'caps' in locals():outcome['limits']=caps
    if output:
        try:
            output(outcome)
            outcome['summary_emitted']=True  # Receipt retains data, not another log summary.
        except Exception:pass
    return outcome
