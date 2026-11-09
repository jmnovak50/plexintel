"""Manual, resumable Gemma 2 labeling using the original contrastive prompts."""
import argparse
from contextlib import closing, contextmanager
from dataclasses import asdict
import hashlib
import json
import math
import os
from uuid import uuid4

from psycopg2.extras import Json, RealDictCursor

from api.db.connection import connect_db
from api.services.dimension_governance import dimension_review_guard, record_assessment
from api.services.dimension_labeling import Evidence, current_context, compatible_label_sql
from api.services.labeling_costs import (Pricing, UsageLedger, BudgetExceeded, LabelingError, failure_diagnostic,
                                       failure_signature, forecast, usage_report, pricing_for_model)


def emit(value):
    print(json.dumps(value,default=str,sort_keys=True),flush=True)


def prompt_hash(prompt):
    import gpt_utils as gpt
    return hashlib.sha256((gpt.SYSTEM_PROMPT+'\n'+prompt['prompt_text']).encode()).hexdigest()


def validate_sample_counts(result, prompt):
    """A model's coverage denominator must describe the examples actually sent."""
    import gpt_utils as gpt
    notes=[]
    for prefix,items,count_field,percent_field in (
        ('high','positive_items','coverage_high_count','coverage_high_percent'),
        ('low','negative_items','coverage_low_overlap_count','coverage_low_overlap_percent')):
        if items not in prompt:
            continue
        size=len(prompt[items]);total=result.get('coverage_'+prefix+'_total');count=result.get(count_field);percent=result.get(percent_field)
        if (total!=size or type(count) is not int or not 0<=count<=size or not size
            or type(percent) is not int or abs(percent-round(100*count/size))>1):
            notes.append('Reported '+prefix.upper()+' coverage did not match the supplied examples/counts')
    if notes:
        return dict(result,label=gpt.UNCLEAR_LABEL,label_confidence='unclear',label_type='unclear',
                    validation_status='invalid',sample_count_mismatch=True,validation_notes=list(result.get('validation_notes',[]))+notes)
    return result


@contextmanager
def batch_lock():
    """Share the daily pipeline lock; never alter or invoke its schedule."""
    import fcntl
    from api.services.pipeline_service import get_pipeline_lock_path, try_acquire_pipeline_lock
    inherited = os.getenv('PLEXINTEL_LABELING_LOCK_FD')
    if inherited:
        fd = int(inherited)
        actual,expected = os.fstat(fd),get_pipeline_lock_path().stat()
        if (actual.st_dev,actual.st_ino)!=(expected.st_dev,expected.st_ino):
            raise ValueError('Invalid inherited labeling lock')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield  # The parent owns/relinquishes this shared open-file-description lock.
        return
    lock = try_acquire_pipeline_lock(source='manual-dimension-labeling')
    if lock is None:
        raise ValueError('A pipeline or labeling batch is already running; retry later')
    try:
        yield
    finally:
        lock.release()


def candidates(conn, evidence):
    ctx = evidence.context
    with conn.cursor() as cur:
        cur.execute('''SELECT s.dimension,SUM(ABS(s.shap_value)) AS priority
            FROM shap_impact s JOIN shap_prediction_context context
                ON context.username=s.user_id AND context.rating_key=s.rating_key
            JOIN recommendations r ON r.username=context.username AND r.rating_key=context.rating_key
                AND r.scored_at=context.scored_at
            WHERE context.config_id=%s AND context.model_version=%s
                AND s.dimension BETWEEN 0 AND 1535 AND s.shap_value::text NOT IN ('NaN','Infinity','-Infinity')
            GROUP BY s.dimension HAVING COUNT(*) FILTER(WHERE s.shap_value>0)>0
            ORDER BY priority DESC,s.dimension''',(ctx['config_id'],ctx['model_sha256']))
        ranked = [r[0] for r in cur.fetchall()]
        cur.execute('''SELECT dimension FROM embedding_dimension_admin WHERE config_id=%s AND paused''',(ctx['config_id'],))
        paused = {r[0] for r in cur.fetchall()}
        cur.execute('''SELECT saved.dimension FROM embedding_labels saved JOIN embedding_feature_config c ON c.active
            WHERE NULLIF(BTRIM(saved.label),'') IS NOT NULL AND '''+compatible_label_sql())
        completed = {r[0] for r in cur.fetchall()}
        cur.execute('''SELECT DISTINCT ON (dimension) dimension,result->>'prompt_sha256' FROM embedding_dimension_assessments
            WHERE config_id=%s AND outcome='abstained' AND result->'provenance'->>'generation_id'=%s
            ORDER BY dimension,assessment_id DESC''',(ctx['config_id'],ctx['generation_id']))
        abstained = dict(cur.fetchall())
    eligible,ineligible = [],dict(paused=len(paused),insufficient_contrast=0)
    for position,dimension in enumerate(ranked,1):
        if dimension in paused:
            continue
        prompt = evidence.prompt(dimension)
        if prompt['skipped_reason']:
            ineligible['insufficient_contrast'] += 1
            continue
        eligible.append(dict(dimension=dimension,side='media' if dimension<768 else 'user',prompt=prompt,
            completed=dimension in completed,abstained=abstained.get(dimension)==prompt_hash(prompt)))
        if position%128==0:
            emit(dict(preparing_prompts=position,ranked_dimensions=len(ranked)))
    return eligible,ineligible


def choose(eligible, args):
    dimensions = args.dimensions or ([args.dimension] if args.dimension is not None else [])
    def scope(row):
        return args.dim_type=='all' or row['side']==args.dim_type
    if dimensions:
        lookup = {r['dimension']:r for r in eligible}
        invalid = [d for d in dimensions if d not in lookup or not scope(lookup[d])]
        if invalid:
            raise ValueError('Selected dimensions have no eligible current-generation contrast, are paused, or fall outside scope: '+str(invalid))
        rows = [lookup[d] for d in dict.fromkeys(dimensions)]
    else:
        rows = [r for r in eligible if scope(r)]
    if not args.regenerate and args.selection_mode!='review':
        rows = [r for r in rows if not r['completed'] and not r['abstained']]
    if args.selection_mode=='review' and not dimensions:
        rows = [r for r in rows if r['completed']]
    return rows if args.all_remaining else rows[:args.limit]


def workload_forecast(eligible, selected, pricing, args, observations):
    import gpt_utils as gpt
    args.max_output_tokens=gpt.label_output_limit(args.max_output_tokens)
    remaining = [r for r in eligible if not r['completed'] and not r['abstained']]
    common = dict(system=gpt.SYSTEM_PROMPT,output_limit=args.max_output_tokens,attempts=args.max_attempts,observations=observations)
    counts = {}
    for side in ('media','user'):
        rows = [r for r in eligible if r['side']==side]
        counts[side] = dict(inventory=768,eligible=len(rows),already_labeled=sum(r['completed'] for r in rows),
            completed_abstentions=sum(r['abstained'] and not r['completed'] for r in rows),
            remaining=sum(not r['completed'] and not r['abstained'] for r in rows))
    return dict(interpretation_model=args.label_model,label_provider=args.label_provider,
                model_source=getattr(args,'model_source','explicit invocation'),
                counts=counts,selected_batch=forecast(selected,pricing,**common),
                all_remaining=forecast(remaining,pricing,**common))


def persist_result(conn, context, row, result, model, *, regenerate=False):
    import batch_label_embeddings as original
    dimension = row['dimension']
    with conn.cursor() as cur:
        if current_context(conn)!=context:
            raise ValueError('Production provenance changed during labeling; candidate not saved')
        before = original.get_existing_label_row(cur,dimension)
        cur.execute('SELECT config_id,generation_id,contract_hash,encoder_digest FROM embedding_labels WHERE dimension=%s',(dimension,))
        previous = cur.fetchone()
        incompatible = previous is not None and tuple(previous)!=(context['config_id'],context['generation_id'],context['contract_hash'],context['encoder_digest'])
        saved,outcome = original.save_label_result(cur,dimension,result,review_mode=regenerate or incompatible,dim_type=row['side'],
            minimum_label_coverage_percent=row['prompt'].get('minimum_label_coverage_percent',original.MINIMUM_LABEL_COVERAGE_PERCENT),
            maximum_low_overlap_percent=row['prompt'].get('maximum_low_overlap_percent',original.MAXIMUM_LOW_OVERLAP_PERCENT))
        if saved:
            cur.execute('''UPDATE embedding_labels SET config_id=%s,generation_id=%s,contract_hash=%s,
                encoder_digest=%s,interpretation_model=%s,needs_review=needs_review OR %s WHERE dimension=%s''',
                (context['config_id'],context['generation_id'],context['contract_hash'],context['encoder_digest'],model,
                 result.get('validation_status')=='needs_review',dimension))
        elif result.get('label')==original.UNCLEAR_LABEL:
            outcome = 'abstained'
        record_assessment(cur,dimension,source='manual-batch',provider='ollama',model=model,
            prompt=dict(row['prompt'],provenance=context),result=result,saved=saved,outcome=outcome,
            before=before,after=original.get_existing_label_row(cur,dimension))
    conn.commit()
    return saved,outcome


def execute(conn, evidence, eligible, selected, pricing, args, prediction):
    import gpt_utils as gpt
    ctx = evidence.context
    batch_id = str(uuid4())
    with conn.cursor() as cur:
        cur.execute('''INSERT INTO embedding_label_batches(batch_id,config_id,generation_id,model,dimensions,forecast,pricing,budget_usd)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)''',(batch_id,ctx['config_id'],ctx['generation_id'],args.label_model,
            Json([r['dimension'] for r in selected]),Json(prediction),Json(asdict(pricing)),args.budget_usd))
    conn.commit()
    ledger = UsageLedger(conn,batch_id,pricing,args.budget_usd)
    summary = dict(batch_id=batch_id,selected=len(selected),successes=0,failures=0,abstentions=0,skipped=0)
    side_completed = dict(media=0,user=0)
    status = 'completed'
    refined = False
    started = []
    previous_failure=None;consecutive_failures=0
    try:
        for position,row in enumerate(selected,1):
            dimension = row['dimension']
            request_count_before=len(started)
            with conn.cursor() as cur,dimension_review_guard(cur,dimension) as allowed:
                if not allowed:
                    summary['skipped'] += 1
                    continue
                observations = ledger.observations(ctx['config_id'],args.label_model)
                if observations and not refined:
                    emit(dict(forecast_refined_after_measurements=workload_forecast(eligible,selected[position-1:],pricing,args,observations)))
                    refined = True
                def before(attempt):
                    if current_context(conn)!=ctx:
                        raise ValueError('Production identity changed; no further cloud requests')
                    started.append(ledger.start(dimension,row['side'],attempt,row['prompt']['prompt_text'],gpt.SYSTEM_PROMPT,
                        args.max_output_tokens,observations.get(row['side'],{}).get('input_ratio',1.0)))
                def finish(attempt,usage,error):
                    ledger.finish(started[-1],usage,error)
                try:
                    result = gpt.call_llm_for_label_result(row['prompt']['prompt_text'],provider='ollama',model=args.label_model,
                        dimension_mode=row['side'],max_retries=args.max_attempts,max_output_tokens=args.max_output_tokens,
                        before_attempt=before,attempt_callback=finish)
                    result=validate_sample_counts(result,row['prompt'])
                    if result.get('sample_count_mismatch'):
                        raise LabelingError('LABEL_COVERAGE_MISMATCH','label_validation','Reported coverage does not match the examples sent.')
                except BudgetExceeded:
                    status = 'budget_stopped'
                    emit(dict(event='budget_stop',batch_id=batch_id,next_dimension=dimension,consumed_estimated_usd=ledger.total_cost()))
                    break
                except Exception as exc:
                    summary['failures'] += 1
                    diagnostic=failure_diagnostic(exc)
                    if len(started)>request_count_before:
                        # A post-parse sample-count check can fail after token
                        # metering was committed. Retain its usage and classify
                        # the latest attempt consistently with the assessment.
                        cur.execute("UPDATE embedding_label_requests SET status='failed',error_code=%s WHERE request_id=%s AND status='succeeded'",
                                    (diagnostic['code'],started[-1]))
                    signature=failure_signature(diagnostic)
                    consecutive_failures=consecutive_failures+1 if signature==previous_failure else 1
                    previous_failure=signature
                    result = dict(processing_error=True,validation_status='invalid',label=gpt.UNCLEAR_LABEL,
                        error_code=diagnostic['code'],error_diagnostics=diagnostic,provenance=ctx,prompt_sha256=prompt_hash(row['prompt']))
                    outcome='provider_error' if diagnostic['category']=='provider' else 'response_error'
                    record_assessment(cur,dimension,source='manual-batch',provider='ollama',model=args.label_model,
                        prompt=dict(row['prompt'],provenance=ctx),result=result,saved=False,outcome=outcome,before=None,after=None)
                    conn.commit()
                    emit(dict(progress=position,total=len(selected),dimension=dimension,outcome=outcome,error=diagnostic))
                    if consecutive_failures>=args.fail_fast_threshold:
                        status='systemic_failure_stopped'
                        summary.update(systemic_failure=diagnostic,consecutive_identical_failures=consecutive_failures,
                                       unprocessed_dimensions=[r['dimension'] for r in selected[position:]])
                        emit(dict(event='systemic_failure_stop',batch_id=batch_id,error=diagnostic,
                                  consecutive_identical_failures=consecutive_failures,unprocessed=len(selected)-position))
                        break
                    continue
                previous_failure=None;consecutive_failures=0
                result.update(provenance=ctx,prompt_sha256=prompt_hash(row['prompt']))
                if args.save_label:
                    saved,outcome = persist_result(conn,ctx,row,result,args.label_model,
                        regenerate=args.regenerate or args.selection_mode=='review')
                else:
                    saved,outcome = False,'candidate_not_saved'
                    record_assessment(cur,dimension,source='manual-batch',provider='ollama',model=args.label_model,
                        prompt=dict(row['prompt'],provenance=ctx),result=result,saved=False,outcome=outcome,before=None,after=None)
                    conn.commit()
                if result.get('label')==gpt.UNCLEAR_LABEL:
                    summary['abstentions'] += 1
                    side_completed[row['side']] += 1
                    if args.save_label:row['abstained']=True
                elif saved or not args.save_label:
                    summary['successes'] += 1
                    side_completed[row['side']] += 1
                    if saved:row['completed']=True
                else:
                    summary['skipped'] += 1
                usage = usage_report(conn,batch_id)
                emit(dict(progress=position,total=len(selected),dimension=dimension,outcome=outcome,
                          tokens=usage['combined'],successes=summary['successes'],failures=summary['failures'],abstentions=summary['abstentions']))
    except BaseException:
        status = 'interrupted'
        raise
    finally:
        conn.rollback()
        if status=='completed' and summary['failures']:
            status='completed_with_errors' if summary['successes'] or summary['abstentions'] else 'failed'
        summary['status']=status
        usage = usage_report(conn,batch_id)
        count = summary['successes']+summary['abstentions']
        summary.update(usage=usage['combined'],average_tokens_per_completed_dimension=(usage['combined']['input_tokens']+usage['combined']['output_tokens'])/count if count else None,
            average_estimated_cost_per_completed_dimension=usage['combined']['estimated_cost_usd']/count if count else None,
            forecast_cost_variance_usd=usage['combined']['estimated_cost_usd']-prediction['selected_batch']['combined']['expected']['cost_usd'],
            updated_cost_to_finish=workload_forecast(eligible,[],pricing,args,ledger.observations(ctx['config_id'],args.label_model))['all_remaining'])
        summary['averages_by_side'] = {side:dict(completed_dimensions=side_completed[side],
            estimated_cost_per_completed_dimension=usage[side]['estimated_cost_usd']/side_completed[side] if side_completed[side] else None,
            known_tokens_per_completed_dimension=usage[side]['total_tokens']/side_completed[side] if side_completed[side] else None,
            token_totals_are_complete=usage[side]['token_totals_are_complete']) for side in ('media','user')}
        summary['variance_scope'] = 'Entire selected-batch forecast; partial/interrupted batches are not a like-for-like completion comparison'
        with conn.cursor() as cur:
            cur.execute('UPDATE embedding_label_batches SET status=%s,summary=%s,completed_at=now() WHERE batch_id=%s',(status,Json(summary),batch_id))
        conn.commit()
        emit(dict(final_status=status,**summary))
    return summary


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dry-run','--dry_run',action='store_true')
    p.add_argument('--label','--gpt_label',action='store_true')
    p.add_argument('--save-label','--save_label',action='store_true')
    p.add_argument('--dim-type','--dim_type',choices=['media','user','all'],default='all')
    p.add_argument('--limit',type=int,default=25)
    p.add_argument('--top-n','--top_n',type=int,default=None,help='Candidate examples per HIGH/LOW tail; default uses existing labeling setting')
    p.add_argument('--all',dest='all_remaining',action='store_true',help='All remaining eligible dimensions in the requested scope')
    p.add_argument('--dimension',type=int)
    p.add_argument('--dimensions',nargs='+',type=int)
    p.add_argument('--regenerate','--refresh_existing','--includeLabeled',action='store_true')
    p.add_argument('--selection-mode','--selection_mode',choices=['importance','eligible','review'],default='importance')
    p.add_argument('--label-provider','--label_provider',default=None,choices=['ollama'],help='Default: Label Provider in Setup')
    p.add_argument('--label-model','--label_model',default=None,help='Default: Ollama Label Model in Setup')
    p.add_argument('--budget-usd',type=float)
    p.add_argument('--max-output-tokens',type=int,default=None,help='Default: Label response token limit in Setup (1024)')
    p.add_argument('--max-attempts',type=int,default=3)
    p.add_argument('--fail-fast-threshold',type=int,default=3,help='Stop after this many consecutive identical failures')
    p.add_argument('--input-price',type=float,default=None,help='USD per million input tokens; default follows the configured model')
    p.add_argument('--cached-input-price',type=float,default=None)
    p.add_argument('--output-price',type=float,default=None)
    p.add_argument('--usage',action='store_true',help='Read accumulated usage without inference')
    p.add_argument('--batch-id')
    return p


def main(argv=None):
    p = parser();args = p.parse_args(argv)
    if args.limit<1 or args.max_output_tokens is not None and not 64<=args.max_output_tokens<=4096 or not 1<=args.max_attempts<=5 or args.top_n is not None and not 1<=args.top_n<=100:
        p.error('Use a positive batch limit, 64..4096 output tokens and 1..5 attempts')
    if not 1<=args.fail_fast_threshold<=25:
        p.error('Fail-fast threshold must be between 1 and 25')
    if args.budget_usd is not None and (not math.isfinite(args.budget_usd) or args.budget_usd<0):
        p.error('Budget must be finite and nonnegative')
    if args.regenerate and not (args.dimension is not None or args.dimensions):
        p.error('Regeneration requires explicitly selected --dimension or --dimensions')
    with closing(connect_db()) as conn:
        if args.usage:
            conn.set_session(readonly=True)
            emit(usage_report(conn,args.batch_id));return
        import gpt_utils as gpt
        args.max_output_tokens=gpt.label_output_limit(args.max_output_tokens)
        args.model_source='CLI override' if args.label_model else 'Setup: labeling.ollama_model'
        args.label_provider,args.label_model=gpt.resolve_label_backend(args.label_provider,args.label_model)
        if args.label_provider!='ollama':
            p.error('The current-generation labeling workflow requires Ollama; select the Label Provider in Setup or pass --label-provider ollama')
        try:
            pricing=pricing_for_model(args.label_model,args.input_price,args.cached_input_price,args.output_price)
        except ValueError as exc:
            p.error(str(exc))
        with batch_lock():
            conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
            evidence = Evidence(conn,args.top_n)
            eligible,ineligible = candidates(conn,evidence)
            selected = choose(eligible,args)
            ledger = UsageLedger(conn,'forecast-only',pricing)
            observations = ledger.observations(evidence.context['config_id'],args.label_model)
            prediction = workload_forecast(eligible,selected,pricing,args,observations)
            emit(dict(forecast=prediction,ineligible=ineligible,provenance=evidence.context,
                      selected_dimensions=[r['dimension'] for r in selected],cloud_requests_started=0))
            conn.rollback()
            if args.dry_run or not args.label or not selected:
                return prediction
            conn.set_session(readonly=False,isolation_level='READ COMMITTED')
            result=execute(conn,evidence,eligible,selected,pricing,args,prediction)
            if result['status'] in ('failed','completed_with_errors','systemic_failure_stopped'):
                raise SystemExit(1)
            return result


if __name__=='__main__':
    main()
