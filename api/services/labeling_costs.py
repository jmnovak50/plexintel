"""Token estimates and durable per-attempt usage for manual dimension labeling.

Published Gemma 4 rates checked 2026-11-08. No tokenizer/network dependency.
Dollar amounts are estimated usage-credit consumption, not provider invoices.
"""
from dataclasses import asdict, dataclass
from decimal import Decimal
import math

from psycopg2.extras import Json, RealDictCursor

PRICE_SOURCE = 'https://ollama.com/library/gemma4:31b-cloud'


@dataclass(frozen=True)
class Pricing:
    input_per_million: float = .14
    cached_input_per_million: float = .05
    output_per_million: float = .40
    checked_at: str = '2026-11-08'
    source: str = PRICE_SOURCE

    def __post_init__(self):
        for value in (self.input_per_million,self.cached_input_per_million,self.output_per_million):
            if not math.isfinite(value) or value<0:
                raise ValueError('Token prices must be finite and nonnegative')

    def cost(self, input_tokens, output_tokens, cached_tokens=0):
        cached_tokens = min(input_tokens,max(0,cached_tokens))
        value = (Decimal(str(input_tokens-cached_tokens))*Decimal(str(self.input_per_million))
                 + Decimal(str(cached_tokens))*Decimal(str(self.cached_input_per_million))
                 + Decimal(str(output_tokens))*Decimal(str(self.output_per_million)))/Decimal(1000000)
        return float(value)


def pricing_for_model(model, input_price=None, cached_input_price=None, output_price=None):
    """Use prices for the configured model; never apply Gemma rates to another model."""
    normalized = model[:-6] if model.endswith('-cloud') else model
    known = {
        'gemma4:31b':(.14,.05,.40,PRICE_SOURCE),
        'gemma4':(.14,.05,.40,PRICE_SOURCE),
        'gpt-oss:120b':(.15,.014,.60,'https://ollama.com/pricing'),
        'gpt-oss:20b':(.07,.035,.30,'https://ollama.com/pricing'),
    }
    supplied = (input_price,cached_input_price,output_price)
    published = known.get(normalized)
    if published is None and any(value is None for value in supplied):
        raise ValueError('No verified default pricing for the configured label model. Supply --input-price, --cached-input-price and --output-price from current provider billing/pricing.')
    prices = [value if value is not None else published[i] for i,value in enumerate(supplied)]
    overridden = any(value is not None for value in supplied)
    return Pricing(*prices,checked_at='operator supplied' if overridden else '2026-11-08',
                   source='operator CLI pricing override' if overridden else published[3])


def estimate_input(system, prompt):
    """English/metadata approximation: UTF-8 bytes / 3 plus 32 template tokens.

    Conservative envelope uses bytes / 2 plus 64. Neither is measured usage or a
    guaranteed tokenizer bound. Exact original system and assembled user prompt
    are counted, including all selected HIGH/LOW examples.
    """
    size = len((system+'\n'+prompt).encode('utf-8'))
    return dict(expected=math.ceil(size/3)+32,high=math.ceil(size/2)+64,
                method='utf8-bytes/3+32 expected; utf8-bytes/2+64 high; estimated, not exact tokenization')


def forecast(prompts, pricing, *, system, output_limit=420, attempts=3, observations=None):
    observations = observations or {}
    sides = {}
    for side in ('media','user'):
        selected = [p for p in prompts if p['side']==side]
        learned = observations.get(side,{})
        output_mean = min(output_limit,learned.get('output_mean',min(256,output_limit)))
        input_ratio = learned.get('input_ratio',1.0)
        retry_factor = min(attempts,max(1.0,learned.get('retry_factor',1.1)))
        estimates = [estimate_input(system,p['prompt']['prompt_text']) for p in selected]
        expected_input = sum(math.ceil(e['expected']*input_ratio) for e in estimates)
        high_input = sum(max(e['high'],math.ceil(e['expected']*input_ratio*1.25)) for e in estimates)
        count = len(selected)
        request_count = math.ceil(count*retry_factor)
        extra = max(0,request_count-count)
        expected_input += math.ceil(expected_input/count*extra) if count else 0
        expected_output = math.ceil(output_mean*request_count)
        high_input *= attempts
        high_output = count*attempts*output_limit
        sides[side] = dict(dimensions=count,
            expected=dict(cloud_requests=request_count,input_tokens=expected_input,output_tokens=expected_output,
                          total_tokens=expected_input+expected_output,cost_usd=pricing.cost(expected_input,expected_output)),
            high=dict(cloud_requests=count*attempts,input_tokens=high_input,output_tokens=high_output,
                      total_tokens=high_input+high_output,cost_usd=pricing.cost(high_input,high_output)),
            calibration=learned or dict(source='unmeasured approximation',successful_requests=0))
    combined = {name:{key:sum(sides[s][name][key] for s in sides) for key in sides['media'][name]} for name in ('expected','high')}
    return dict(media=sides['media'],user=sides['user'],combined=combined,pricing=asdict(pricing),
        output_token_limit=output_limit,max_attempts_per_dimension=attempts,
        token_estimation=estimate_input('','')['method'],cached_input_assumed=0,
        uncertainty='Expected includes retry allowance; high assumes every retry at the output cap. Estimates cannot guarantee the provider billing ceiling. Subscription fees and taxes excluded.')


def token_usage(data):
    def count(key):
        value = data.get(key)
        return value if type(value) is int and value>=0 else None
    result = dict(input_tokens=count('prompt_eval_count'),cached_input_tokens=count('prompt_eval_cached_count'),output_tokens=count('eval_count'))
    if result['input_tokens'] is not None and result['cached_input_tokens'] is not None and result['cached_input_tokens']>result['input_tokens']:
        result['cached_input_tokens'] = None
    return result


class BudgetExceeded(RuntimeError):
    pass


class UsageLedger:
    def __init__(self, conn, batch_id, pricing, budget=None):
        self.conn,self.batch_id,self.pricing,self.budget = conn,batch_id,pricing,budget

    def total_cost(self):
        with self.conn.cursor() as cur:
            cur.execute('SELECT COALESCE(SUM(estimated_cost_usd),0) FROM embedding_label_requests WHERE batch_id=%s',(self.batch_id,))
            return float(cur.fetchone()[0])

    def start(self, dimension, side, attempt, prompt, system, output_limit, input_ratio=1.0):
        estimate = estimate_input(system,prompt)
        reserve_input = max(estimate['high'],math.ceil(estimate['expected']*max(1,input_ratio)*1.25))
        reserved = self.pricing.cost(reserve_input,output_limit)
        consumed = self.total_cost()
        if self.budget is not None and Decimal(str(consumed))+Decimal(str(reserved))>Decimal(str(self.budget)):
            raise BudgetExceeded('Budget would be exceeded by the next request reservation')
        with self.conn.cursor() as cur:
            cur.execute('''INSERT INTO embedding_label_requests
                (batch_id,dimension,side,attempt,estimated_input_tokens,reserved_input_tokens,reserved_output_tokens,estimated_cost_usd)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING request_id''',
                (self.batch_id,dimension,side,attempt,estimate['expected'],reserve_input,output_limit,reserved))
            request_id = cur.fetchone()[0]
        self.conn.commit()  # Persist the reservation before a possibly billable request.
        return request_id

    def finish(self, request_id, data, error):
        usage = token_usage(data)
        with self.conn.cursor() as cur:
            cur.execute('SELECT reserved_input_tokens,reserved_output_tokens FROM embedding_label_requests WHERE request_id=%s',(request_id,))
            reserved_input,reserved_output = cur.fetchone()
            # Missing provider counts are kept NULL; cost reserves estimates. A
            # missing cache count receives no unverified cache discount.
            cost = self.pricing.cost(usage['input_tokens'] if usage['input_tokens'] is not None else reserved_input,
                                    usage['output_tokens'] if usage['output_tokens'] is not None else reserved_output,
                                    usage['cached_input_tokens'] or 0)
            cur.execute('''UPDATE embedding_label_requests SET status=%s,input_tokens=%s,cached_input_tokens=%s,
                output_tokens=%s,estimated_cost_usd=%s,error_code=%s,completed_at=now() WHERE request_id=%s''',
                ('failed' if error else 'succeeded',usage['input_tokens'],usage['cached_input_tokens'],usage['output_tokens'],cost,
                 (f'HTTP_{error.status_code}' if hasattr(error,'status_code') else type(error).__name__) if error else None,request_id))
        self.conn.commit()
        return usage

    def observations(self, config_id, model):
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''SELECT r.* FROM embedding_label_requests r JOIN embedding_label_batches b USING(batch_id)
                WHERE b.config_id=%s AND b.model=%s AND r.status!='pending' ORDER BY r.request_id''',(config_id,model))
            rows = cur.fetchall()
        successful = [r for r in rows if r['status']=='succeeded' and r['input_tokens'] is not None and r['output_tokens'] is not None]
        if len(successful)<10:
            return {}
        result = {}
        for side in ('media','user'):
            own = [r for r in successful if r['side']==side]
            chosen = own if len(own)>=10 else successful
            attempts = [r for r in rows if r['side']==side] if len(own)>=10 else rows
            ratios = [r['input_tokens']/max(1,r['estimated_input_tokens']) for r in chosen]
            result[side] = dict(source='own side' if len(own)>=10 else 'pooled until 10 measurements on this side',
                successful_requests=len(own),pooled_successful_requests=len(successful),
                input_ratio=sum(ratios)/len(ratios),output_mean=sum(r['output_tokens'] for r in chosen)/len(chosen),
                retry_factor=len(attempts)/len(chosen))
        return result


def usage_report(conn, batch_id=None):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT r.* FROM embedding_label_requests r'''+(' WHERE r.batch_id=%s' if batch_id else '')+' ORDER BY request_id',
                    (batch_id,) if batch_id else ())
        rows = cur.fetchall()
        cur.execute('''SELECT b.* FROM embedding_label_batches b'''+(' WHERE batch_id=%s' if batch_id else '')+' ORDER BY created_at',
                    (batch_id,) if batch_id else ())
        batches = cur.fetchall()
    result = dict(batches=len(batches),requests=len(rows),provider_invoice_available=False,
                  billing_limitation='USD is a configurable-price estimate, not an invoice. Missing counts stay unknown; pending/unknown requests retain conservative cost reservations.')
    def totals(group):
        measured = [r for r in group if r['input_tokens'] is not None and r['output_tokens'] is not None]
        return dict(requests=len(group),pending=sum(r['status']=='pending' for r in group),
            retries=sum(r['attempt']>1 for r in group),failed=sum(r['status']=='failed' for r in group),
            input_tokens=sum(r['input_tokens'] or 0 for r in group),output_tokens=sum(r['output_tokens'] or 0 for r in group),
            cached_input_tokens=sum(r['cached_input_tokens'] or 0 for r in group),
            total_tokens=sum((r['input_tokens'] or 0)+(r['output_tokens'] or 0) for r in group),
            retry_input_tokens=sum(r['input_tokens'] or 0 for r in group if r['attempt']>1),
            retry_output_tokens=sum(r['output_tokens'] or 0 for r in group if r['attempt']>1),
            retry_estimated_cost_usd=float(sum(r['estimated_cost_usd'] for r in group if r['attempt']>1)),
            missing_input_counts=sum(r['input_tokens'] is None for r in group),
            missing_output_counts=sum(r['output_tokens'] is None for r in group),
            missing_cached_input_counts=sum(r['cached_input_tokens'] is None for r in group),
            requests_with_measured_input_and_output=len(measured),
            estimated_cost_usd=float(sum(r['estimated_cost_usd'] for r in group)),
            token_totals_are_complete=len(measured)==len(group))
    result.update(media=totals([r for r in rows if r['side']=='media']),user=totals([r for r in rows if r['side']=='user']),combined=totals(rows))
    result['batch_details'] = [dict(batch_id=b['batch_id'],status=b['status'],model=b['model'],summary=b['summary'],pricing=b['pricing'],
        forecast=b['forecast'],created_at=b['created_at'].isoformat()) for b in batches]
    if batch_id:
        result['request_details'] = [dict(request_id=r['request_id'],dimension=r['dimension'],side=r['side'],attempt=r['attempt'],
            status=r['status'],input_tokens=r['input_tokens'],cached_input_tokens=r['cached_input_tokens'],output_tokens=r['output_tokens'],
            estimated_cost_usd=float(r['estimated_cost_usd']),error_code=r['error_code']) for r in rows]
    return result
