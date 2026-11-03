"""Durable manual review gates and terminal-friendly checkpoint progress."""
import json
import time
from uuid import uuid4
from psycopg2 import sql
from psycopg2.extras import Json
from .contracts import ContractError,fingerprint


def require_preparation(store,gid,stage):
    rows=store.query(sql.SQL('SELECT status,count(*) AS n FROM {} WHERE generation_id=%s AND stage=%s GROUP BY status')
        .format(store.table('preparations')),(gid,stage),many=True)
    counts={r['status']:r['n'] for r in rows}
    expected=store.generation(gid,include_snapshot=False)['expected']['media_text']
    if counts.get('succeeded',0)!=expected or counts.get('failed',0):
        raise ContractError(stage+' preparation is incomplete; finish/retry that stage before proceeding')


def review_state(store,gid,gate,*,missing_art_limit=0):
    g=store.generation(gid);kinds={'text':['media_text'],'poster':['media_poster'],
        'profiles':['media_text','media_poster','watch','user'],'quality':['media_text','media_poster','watch','user']}[gate]
    state={};counts=store.counts(gid)
    for kind in kinds:
        count=counts[kind]
        if count['succeeded']+(count['missing'] if kind=='media_poster' else 0)!=count['expected'] or count['failed'] or count['pending']:
            raise ContractError('Review requires complete '+kind+' population')
        if kind=='media_poster' and count['missing']>missing_art_limit:raise ContractError('Review requires explicit missing-art allowance')
        state[kind]=[(r['item_key'],r['input_hash'],r['modality_contract_hash'],r['status']) for r in store.items(gid,kind)]
    if gate in ('text','poster'):
        stage='metadata' if gate=='text' else 'poster'
        preps=store.query(sql.SQL('SELECT item_key,status,content_hash FROM {} WHERE generation_id=%s AND stage=%s ORDER BY item_key')
            .format(store.table('preparations')),(gid,stage),many=True)
        if len(preps)!=g['expected']['media_text'] or any(r['status']!='succeeded' for r in preps):raise ContractError('Preparation checkpoint incomplete')
        state['preparations']=[dict(r) for r in preps]
    if gate=='quality':
        state['artifacts']={name:store.artifact(gid,name)['sha256'] for name in ('dataset.json','evaluation.json','model.pkl','text_model.pkl','dimensions.json')}
    return fingerprint(dict(contract=g['contract_hash'],gate=gate,state=state))


def approve_review(store,gid,gate,reason,*,missing_art_limit=0,quality_go=False):
    store.assert_mutable(gid)
    if not reason or not reason.strip():raise ContractError('A review reason is required')
    if gate=='quality' and not quality_go:raise ContractError('Quality review requires an explicit --quality-go decision')
    state=review_state(store,gid,gate,missing_art_limit=missing_art_limit)
    store.query(sql.SQL('INSERT INTO {}(generation_id,gate,state_hash,missing_art_limit,reason) VALUES(%s,%s,%s,%s,%s)')
        .format(store.table('operator_reviews')),(gid,gate,state,missing_art_limit,reason.strip()))
    store.conn.commit();return dict(generation_id=gid,gate=gate,state_hash=state,approved=True)


def require_review(store,gid,gate):
    records=store.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s AND gate=%s ORDER BY review_id DESC')
        .format(store.table('operator_reviews')),(gid,gate),many=True)
    for row in records:
        try:state=review_state(store,gid,gate,missing_art_limit=row['missing_art_limit'])
        except ContractError:continue
        if state==row['state_hash']:return row
    raise ContractError('Manual '+gate+' review is missing or stale; use the separate review command')


class StageProgress:
    def __init__(self,store,gid,stage,*,kind=None,preparation=None,rescan=False,printer=print,clock=time.monotonic):
        self.store=store;self.gid=gid;self.stage=stage;self.kind=kind;self.preparation=preparation
        self.printer=printer;self.clock=clock;self.run_id=str(uuid4());self.last_error=None
        self.rescan=rescan
        self.current=None;self.attempted=0;self.custom=dict(expected=0,completed=0,failed=0);self.last_print=-100.
        self.reused=0

    def state(self):
        if self.kind:
            c=self.store.counts(self.gid)[self.kind]
            return dict(expected=c['expected'],completed=c['succeeded']+c['missing'],failed=c['failed'],missing=c['missing'])
        if self.preparation:
            rows=self.store.query(sql.SQL('SELECT status,count(*) AS n FROM {} WHERE generation_id=%s AND stage=%s GROUP BY status')
                .format(self.store.table('preparations')),(self.gid,self.preparation),many=True)
            values={r['status']:r['n'] for r in rows}
            return dict(expected=self.store.generation(self.gid,include_snapshot=False)['expected']['media_text'],
                completed=values.get('succeeded',0),failed=values.get('failed',0))
        return self.custom

    def __enter__(self):
        self.started=self.clock();self.skipped=0 if self.rescan else self.state()['completed'];self.emit(force=True);return self

    def __call__(self,event):
        if 'expected' in event:self.custom={k:event.get(k,0) for k in ('expected','completed','failed')}
        elif 'item_key' in event or 'error' in event:self.attempted+=1
        self.current=event.get('item_key') or event.get('phase') or self.current
        self.reused+=int(bool(event.get('reused')))
        self.last_error=event.get('error') or self.last_error
        self.emit(persist=event.get('persist',True))

    def emit(self,*,force=False,status='running',persist=True):
        now=self.clock()
        if not force and now-self.last_print<5:return
        state=self.state();elapsed=max(0.,now-self.started)
        measured=self.attempted or max(0,state['completed']-self.skipped)
        rate=measured/elapsed if elapsed>0 else 0.
        remaining=max(0,state['expected']-state['completed']-state['failed'])
        metrics=dict(**state,remaining=remaining,outstanding=max(0,state['expected']-state['completed']),
            records_per_minute=rate*60,elapsed_seconds=elapsed,
            estimated_remaining_seconds=remaining/rate if rate>0 else None,
            resumed_or_skipped=self.skipped+self.reused,current_record=self.current,last_error=self.last_error)
        if persist:self.store.query(sql.SQL('''INSERT INTO {}(run_id,generation_id,stage,status,metrics,finished_at)
            VALUES(%s,%s,%s,%s,%s,CASE WHEN %s='running' THEN NULL ELSE now() END)
            ON CONFLICT(run_id) DO UPDATE SET status=EXCLUDED.status,metrics=EXCLUDED.metrics,finished_at=EXCLUDED.finished_at''')
            .format(self.store.table('stage_runs')),(self.run_id,self.gid,self.stage,status,Json(metrics),status))
        if persist:self.store.conn.commit()
        eta='unknown' if metrics['estimated_remaining_seconds'] is None else f"{metrics['estimated_remaining_seconds']:.0f}s"
        self.printer(f"[{self.stage} {self.gid}] {status} completed={state['completed']}/{state['expected']} failed={state['failed']} missing={state.get('missing',0)} remaining={remaining} retryable={state['failed']} "
            f"rate={rate*60:.1f}/min elapsed={elapsed:.0f}s eta={eta} resumed/skipped={self.skipped+self.reused} record={self.current or '-'} last_error={self.last_error or '-'}",flush=True)
        self.last_print=now

    def __exit__(self,typ,error,tb):
        if typ:
            self.store.conn.rollback();self.last_error=typ.__name__
            self.emit(force=True,status='interrupted' if issubclass(typ,KeyboardInterrupt) else 'failed');return False
        state=self.state();incomplete=state['completed']!=state['expected'] or bool(state['failed'])
        self.emit(force=True,status='failed' if incomplete else 'succeeded')
        if incomplete:raise ContractError(self.stage+' is incomplete; inspect status and retry this stage')
