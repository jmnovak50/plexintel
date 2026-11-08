"""Resumable production runs: durable deltas plus connection-private working tables.

No new permanent generation, inference server, or shadow pipeline is created.
"""
import hashlib
import json
import re
import time
from pathlib import Path
from uuid import uuid4
from pgvector import Vector
from psycopg2 import sql
from psycopg2.extras import Json

from .store import Store
from .contracts import ContractError,fingerprint,vector
from .source import serializable

WORK={'generations','items','dependencies','artifacts','training_rows','text_training_rows',
      'modality_training_rows','predictions','preparations','preparation_attempts','inference_requests','operator_reviews'}


class ProductionRun(Store):
    """Existing workers operate on temporary views of the SAME encoder generation."""
    def __init__(self,durable,run_id,*,live_schema="public"):
        super().__init__(durable.conn,durable.schema)
        self.durable=durable;self.run_id=run_id;self.live_schema=live_schema

    def table(self,name):
        return sql.Identifier('pg_temp','production_work_'+name) if name in WORK else self.durable.table(name)

    def install_work(self):
        root=Path(__file__).resolve().parents[1]/'db/migrations/optional/embedding_generation'
        def mapped(statement):
            return re.sub(r'embedding_v2\.(\w+)',lambda m:self.table(m[1]).as_string(self.conn),statement)
        for path in sorted(root.glob('*.sql')):
            text=path.read_text()
            for match in re.finditer(r'CREATE TABLE IF NOT EXISTS embedding_v2\.(\w+) \([\s\S]*?\n\);',text):
                if match[1] in WORK:self.query(mapped(match[0]))
            if path.name=='002_independent_modalities.sql':
                for table,column in [('items','kind'),('items','status'),('preparations','kind')]:
                    self.query(sql.SQL('ALTER TABLE {} DROP CONSTRAINT IF EXISTS {}').format(self.table(table),sql.Identifier('production_work_'+table+'_'+column+'_check')))
                for match in re.finditer(r'ALTER TABLE embedding_v2\.(items|preparations) [\s\S]*?;',text):self.query(mapped(match[0]))
        self.conn.commit()

    def checkpoint(self,gid,kind,key):
        row=self.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s AND kind=%s AND item_key=%s').format(self.table('items')),(gid,kind,key))
        preparation=self.preparation(gid,key,'metadata') if kind=='media_text' else None
        record=serializable({k:v for k,v in row.items() if k!='embedding'})
        record['dependencies']=self.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s AND child_kind=%s AND child_key=%s').format(self.table('dependencies')),(gid,kind,key),many=True)
        reused=row['status']=='succeeded' and bool((row.get('timing') or {}).get('inherited'))
        if reused:record['_reuse_production_vector']=True
        self.query(sql.SQL('''INSERT INTO {} VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id,kind,item_key)
            DO UPDATE SET record=EXCLUDED.record,embedding=EXCLUDED.embedding,preparation=EXCLUDED.preparation''').format(self.durable.table('production_run_items')),
            (self.run_id,kind,key,Json(record),None if reused else row['embedding'],Json(serializable(preparation))))

    def complete(self,gid,kind,key,*args,**kwargs):
        result=super().complete(gid,kind,key,*args,**kwargs);self.checkpoint(gid,kind,key);return result

    def fail(self,gid,kind,key,*args,**kwargs):
        result=super().fail(gid,kind,key,*args,**kwargs);self.checkpoint(gid,kind,key);return result

    def preparation(self,gid,key,stage,**kwargs):
        result=super().preparation(gid,key,stage,**kwargs)
        if kwargs.get('status') is not None:self.checkpoint(gid,'media_text',key)
        return result

    def log_inference(self,gid,kind,key,input_hash,status,stats):
        super().log_inference(gid,kind,key,input_hash,status,stats)
        self.query(sql.SQL('INSERT INTO {}(request_id,run_id,kind,item_key,status,stats) VALUES(%s,%s,%s,%s,%s,%s)')
            .format(self.durable.table('production_run_requests')),(str(uuid4()),self.run_id,kind,key,status,Json(stats)))

    def artifact(self,gid,name,data=None,metadata=None):
        result=super().artifact(gid,name,data,metadata)
        if data is not None:
            self.query(sql.SQL('''INSERT INTO {} VALUES(%s,%s,%s,%s,%s) ON CONFLICT(run_id,name)
                DO UPDATE SET sha256=EXCLUDED.sha256,metadata=EXCLUDED.metadata,data=EXCLUDED.data''').format(self.durable.table('production_run_artifacts')),
                (self.run_id,name,result,Json(metadata or {}),data))
            if name=='scoring.json':
                self.query(sql.SQL('DELETE FROM {} WHERE run_id=%s').format(self.durable.table('production_run_predictions')),(self.run_id,))
                self.query(sql.SQL('INSERT INTO {} SELECT %s,owner,media_key,probability,cosine,rank,shap FROM {} WHERE generation_id=%s')
                    .format(self.durable.table('production_run_predictions'),self.table('predictions')),(self.run_id,gid))
        return result

    def hydrate(self,state,snapshot):
        """Read all vectors from physical production, overlay only durable run deltas."""
        gid=state['generation_id']
        # Ancestor contracts are audit lineage, not runtime vector/model sources.
        parent=gid;ancestors=[]
        while parent:
            old=self.durable.generation(parent)
            ancestors.append(parent);parent=old['parent_id']
        for ancestor in reversed(ancestors):
            self.query(sql.SQL('INSERT INTO {} SELECT * FROM {} WHERE generation_id=%s ON CONFLICT DO NOTHING')
                .format(self.table('generations'),self.durable.table('generations')),(ancestor,))
        expected=dict(media_text=len(snapshot['media']),media_poster=0,watch=len(snapshot['events']),
                      user=len(self.profile_sources(snapshot,state['contract']['profile_threshold'])))
        self.query(sql.SQL("UPDATE {} SET status='building',contract=%s,contract_hash=%s,snapshot=%s,source_hash=%s,expected=%s,base_generation=%s WHERE generation_id=%s")
            .format(self.table('generations')),(Json(state['contract']),state['contract_hash'],Json(snapshot),snapshot['_db_hash'],Json(expected),gid,gid))
        for row in snapshot['media']:self.upsert_source(gid,'media_text',str(row['rating_key']),row)
        for event in snapshot['events']:
            self.upsert_source(gid,'watch',str(event['watch_id']),event,owner=event['username'],media_key=str(event['rating_key']),semantic_hash=fingerprint({k:v for k,v in event.items() if k!='observed_at'}))
        for owner,source in self.profile_sources(snapshot,state['contract']['profile_threshold']).items():self.upsert_source(gid,'user',owner,source,owner=owner)
        canonical=self.query(sql.SQL('SELECT * FROM {}').format(self.durable.table('production_inputs')),many=True)
        for entry in canonical:
            kind,key,old=entry['kind'],entry['item_key'],entry['record']
            current=self.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s AND kind=%s AND item_key=%s').format(self.table('items')),(gid,kind,key))
            if current is None or kind=='watch' and current['semantic_hash']!=old['semantic_hash']:continue
            table,column={'media_text':('media_embeddings','rating_key'),'watch':('watch_embeddings','watch_id'),'user':('user_embeddings','username')}[kind]
            physical=self.query(sql.SQL('SELECT embedding FROM {} WHERE {}::text=%s').format(sql.Identifier(self.live_schema,table),sql.Identifier(column)),(key,))
            if not physical:raise ContractError('Canonical production vector is missing')
            record=dict(old,source={**old['source'],**current['source']} if kind=='media_text' else old['source'],timing=dict(inherited=True))
            self.restore_item(record,physical['embedding'])
        checkpoints=self.query(sql.SQL('SELECT * FROM {} WHERE run_id=%s').format(self.durable.table('production_run_items')),(self.run_id,),many=True)
        for checkpoint in checkpoints:
            record=checkpoint['record'];embedding=checkpoint['embedding']
            if record.get('_reuse_production_vector'):
                table,column={'media_text':('media_embeddings','rating_key'),'watch':('watch_embeddings','watch_id'),'user':('user_embeddings','username')}[record['kind']]
                embedding=self.query(sql.SQL('SELECT embedding FROM {} WHERE {}::text=%s').format(sql.Identifier(self.live_schema,table),sql.Identifier(column)),(record['item_key'],))['embedding']
            self.restore_item(record,embedding)
            prep=checkpoint['preparation']
            if prep:super().preparation(gid,record['item_key'],'metadata',status=prep['status'],content_hash=prep['content_hash'],provenance=prep['provenance'],timing=prep['timing'])
        for artifact in self.query(sql.SQL('SELECT * FROM {} WHERE run_id=%s').format(self.durable.table('production_run_artifacts')),(self.run_id,),many=True):
            Store.artifact(self,gid,artifact['name'],bytes(artifact['data']),artifact['metadata'])
        self.query(sql.SQL('INSERT INTO {} SELECT %s,owner,media_key,probability,cosine,rank,shap FROM {} WHERE run_id=%s')
            .format(self.table('predictions'),self.durable.table('production_run_predictions')),(gid,self.run_id))
        self.conn.commit();return gid

    def restore_item(self,record,embedding):
        row={k:v for k,v in record.items() if k not in ('dependencies','vector_sha256','_reuse_production_vector')};row['embedding']=None
        self.query(sql.SQL('''UPDATE {} t SET (owner,media_key,source,semantic_hash,input_hash,status,attempts,error,timing,generated_at,origin_generation,modality_contract_hash,provenance,embedding)=
            (r.owner,r.media_key,r.source,r.semantic_hash,r.input_hash,r.status,r.attempts,r.error,r.timing,r.generated_at,r.origin_generation,r.modality_contract_hash,r.provenance,%s)
            FROM jsonb_populate_record(NULL::{},%s) r WHERE t.generation_id=r.generation_id AND t.kind=r.kind AND t.item_key=r.item_key''')
            .format(self.table('items'),self.table('items')),(embedding,Json(row)))
        self.query(sql.SQL('DELETE FROM {} WHERE generation_id=%s AND child_kind=%s AND child_key=%s').format(self.table('dependencies')),(row['generation_id'],row['kind'],row['item_key']))
        for dep in record.get('dependencies',[]):
            self.query(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,%s,%s,%s)').format(self.table('dependencies')),
                (row['generation_id'],row['kind'],row['item_key'],dep['parent_kind'],dep['parent_key'],dep['parent_input_hash']))
        if row['kind']=='media_text' and 'metadata' in row['source']:
            Store.preparation(self,row['generation_id'],row['item_key'],'metadata',status='succeeded',content_hash=row['semantic_hash'])


def baseline(store):
    counts=store.query('SELECT media_type,count(*) AS n FROM public.library GROUP BY media_type',many=True)
    return dict(library_counts={r['media_type']:r['n'] for r in counts},
        media_keys=[r['key'] for r in store.query('SELECT rating_key::text AS key FROM public.library',many=True)],
        watch_ids=[r['key'] for r in store.query('SELECT watch_id::text AS key FROM public.watch_history',many=True)],
        media_embedding_keys=[r['key'] for r in store.query('SELECT rating_key::text AS key FROM public.media_embeddings',many=True)],
        watch_embedding_keys=[r['key'] for r in store.query('SELECT watch_id::text AS key FROM public.watch_embeddings',many=True)])


def execute(durable,config,*,collect,plex_factory,cache,publication_lock,pipeline_lock_held=False,progress=lambda value:None):
    import os,subprocess,sys
    from .runtime import ROOT
    from .text_production import load_production,train_text,verify_current_production
    from .io import Ollama
    from .contracts import Encoder
    from .backfill import prepare_metadata,run_media_text,run_watches,run_users,safe_error
    from .operator import approve_review,require_preparation
    from .model import score
    from .promotion import promote
    from .progress import Reporter
    monitor=Reporter(progress);progress=monitor
    overall_started=time.perf_counter()
    production=load_production(durable)
    if production is None:raise ContractError('Canonical text-only production must be active')
    state,_,_=production;gid=state['generation_id']
    with publication_lock(pipeline_lock_held):
        verify_current_production(durable)
        pending=durable.query(sql.SQL("SELECT * FROM {} WHERE generation_id=%s AND status IN ('running','failed') ORDER BY created_at LIMIT 1").format(durable.table('production_runs')),(gid,))
        if pending:
            run=pending;run_id=run['run_id']
            if run['base_model_sha256']!=state['model_sha256']:raise ContractError('Pending run belongs to a different production model')
        else:
            run_id=str(uuid4())
            durable.query(sql.SQL("INSERT INTO {}(run_id,generation_id,base_model_sha256,status,summary) VALUES(%s,%s,%s,'running',%s)").format(durable.table('production_runs')),
                          (run_id,gid,state['model_sha256'],Json(dict(before=baseline(durable)))))
            durable.conn.commit();run=durable.query(sql.SQL('SELECT * FROM {} WHERE run_id=%s').format(durable.table('production_runs')),(run_id,))
        monitor.bind(run_id)
        progress(dict(stage='production-run',run_id=run_id,generation_id=gid,resumed=bool(pending)))
        stages=dict(run['stages']);summary=dict(run['summary'] or {});started=time.perf_counter()
        def phase(name,operation):
            from contextlib import nullcontext
            logical={'source_sync':'source_sync','watch':'watch','users':'users'}.get(name)
            if name in stages:
                if logical:monitor.skip(logical,previous_seconds=stages[name])
                return
            t=time.perf_counter()
            with monitor.span(logical) if logical else nullcontext():operation()
            if logical:monitor.done(logical)
            stages[name]=time.perf_counter()-t
            durable.query(sql.SQL("UPDATE {} SET stages=%s,status='running',error=NULL WHERE run_id=%s").format(durable.table('production_runs')),(Json(stages),run_id));durable.conn.commit()
            progress(dict(stage=name,run_id=run_id,seconds=stages[name]))
        try:
            def sync():
                p=subprocess.run([sys.executable,str(ROOT/'fetch_tautulli_data.py'),'--mode','incremental','--no-embeddings'],cwd=ROOT,capture_output=True,text=True)
                # Never put credential-bearing provider URLs into pipeline logs.
                text=p.stdout+p.stderr
                for key,value in {**os.environ,**{k:str(v) for k,v in config.items()}}.items():
                    if value and any(word in key.lower() for word in ('secret','password','api_key','apikey','token')):text=text.replace(value,'[REDACTED]')
                text=re.sub(r'(?i)(apikey|api_key|x-plex-token|password|token)=([^&\s]+)',r'\1=[REDACTED]',text)
                log=ROOT/'logs'/('production-sync-'+run_id+'.log');log.write_text(text);log.chmod(0o600)
                if p.returncode:raise ContractError('Source synchronization failed; private sanitized stage log retained')
            phase('source_sync',sync)
            with monitor.span('media_text'):
                context_started=time.perf_counter()
                if run['snapshot'] is None:
                    snapshot=collect(config,progress=progress)
                    old={r['item_key']:r['record'] for r in durable.query(sql.SQL("SELECT * FROM {} WHERE kind='watch'").format(durable.table('production_inputs')),many=True)}
                    for event in snapshot['events']:
                        row=old.get(str(event['watch_id']))
                        if row and fingerprint({k:v for k,v in event.items() if k!='observed_at'})==row['semantic_hash']:event['observed_at']=row['source'].get('observed_at',event['observed_at'])
                    durable.query(sql.SQL('UPDATE {} SET snapshot=%s WHERE run_id=%s').format(durable.table('production_runs')),(Json(snapshot),run_id));durable.conn.commit()
                else:snapshot=run['snapshot']
                work=ProductionRun(durable,run_id);work.install_work();work.hydrate(state,snapshot)
                stages['context']=stages.get('context',0)+time.perf_counter()-context_started
                client=Ollama(config['ollama.host'],Encoder(**state['contract']['encoder']),timeout=config['ollama.timeout_s']);client.verify_pinned()
                plex=plex_factory(config,cache)
                def metadata_stage():
                    prepare_metadata(work,gid,plex,refresh=True,progress=progress)
                    require_preparation(work,gid,'metadata')
                def vectors_stage(kind,operation):
                    operation();count=work.counts(gid)[kind]
                    if count['succeeded']!=count['expected'] or count['failed'] or count['pending']:
                        raise ContractError('Production '+kind+' stage is incomplete; resume this run')
                phase('metadata',metadata_stage)
                require_preparation(work,gid,'metadata')
                phase('media_text',lambda:vectors_stage('media_text',lambda:run_media_text(work,gid,client,progress=progress)))
            phase('watch',lambda:vectors_stage('watch',lambda:run_watches(work,gid,client,progress=progress)))
            phase('users',lambda:vectors_stage('user',lambda:run_users(work,gid,progress=progress)))
            requests_now=durable.query(sql.SQL('SELECT kind,item_key,status,stats FROM {} WHERE run_id=%s').format(durable.table('production_run_requests')),(run_id,),many=True)
            for kind,key in [('media_text','media_text'),('watch','watch'),('user','users')]:
                counts=work.counts(gid)[kind]
                inferred=len({r['item_key'] for r in requests_now if r['kind']==kind and r['status']=='succeeded'})
                metrics=dict(expected=counts['expected'],completed=counts['succeeded'],succeeded=counts['succeeded'],failed=counts['failed'],pending=counts['pending'])
                if kind=='user':
                    rebuilt=sum((r.get('timing') or {}).get('rebuilt',False) for r in work.items(gid,'user'))
                    metrics.update(rebuilt=rebuilt,reused=counts['succeeded']-rebuilt)
                else:metrics.update(inferred=inferred,requests=sum(r['kind']==kind for r in requests_now),reused=counts['succeeded']-inferred,inference_seconds=sum(r['stats'].get('client_seconds',0) for r in requests_now if r['kind']==kind))
                if kind in ('media_text','watch'):
                    old_keys=set(summary['before']['media_embedding_keys' if kind=='media_text' else 'watch_embedding_keys'])
                    success_keys={r['item_key'] for r in requests_now if r['kind']==kind and r['status']=='succeeded'}
                    metrics.update(new=len(success_keys-old_keys),regenerated=len(success_keys&old_keys))
                if kind=='media_text':metrics.update(metadata_seconds=stages.get('metadata',0),context_seconds=stages['context'])
                monitor.done(key,**metrics)
            before=summary['before']
            monitor.done('source_sync',new_media=len({str(r['rating_key']) for r in snapshot['media']}-set(before['media_keys'])),new_watch_events=snapshot['watch_coverage'].get('source_watch_events',len(before['watch_ids']))-len(before['watch_ids']),quarantined=snapshot['watch_coverage'].get('quarantined_watch_events',0))
            for gate in ('text','profiles'):approve_review(work,gid,gate,'Approved canonical text-only production run; no poster dependency')
            if 'training' in stages:
                monitor.skip('training_data')
                monitor.skip('train_model',previous_seconds=stages['training'])
            phase('training',lambda:train_text(work,gid,progress=progress,monitor=monitor))
            with monitor.span('train_model'):
                evaluation=json.loads(bytes(work.artifact(gid,'evaluation.json')['data']))
                monitor.emit('train_model','started',chronological_balanced_accuracy=evaluation['chronological']['balanced_accuracy'],chronological_average_precision=evaluation['chronological']['average_precision'],show_balanced_accuracy=evaluation['show_grouped']['metrics']['balanced_accuracy'])
                if (evaluation['chronological']['balanced_accuracy']<.5
                    or evaluation['chronological']['average_precision']<state['evaluation']['chronological']['average_precision']-.05
                    or evaluation['show_grouped']['metrics']['balanced_accuracy']<.5):raise ContractError('Production text refit failed the existing quality gates')
                approve_review(work,gid,'quality','Normal daily text refit passed chronological/show-heldout gates; prior B remains archived',quality_go=True)
            monitor.done('train_model',quality_passed=True,chronological_balanced_accuracy=evaluation['chronological']['balanced_accuracy'],chronological_average_precision=evaluation['chronological']['average_precision'],show_balanced_accuracy=evaluation['show_grouped']['metrics']['balanced_accuracy'])
            if 'scoring' in stages:
                monitor.skip('score_model',previous_seconds=stages['scoring'])
                monitor.skip('shap')
            phase('scoring',lambda:score(work,gid,progress=progress,monitor=monitor))
            stages.pop('validation',None)  # Revalidate reconstructed temporary context on resume.
            with monitor.span('publication'):
                phase('validation',lambda:work.validate(gid,quality_go=True,progress=progress))
            after=baseline(durable)
            requests=durable.query(sql.SQL('SELECT kind,item_key,status,stats FROM {} WHERE run_id=%s').format(durable.table('production_run_requests')),(run_id,),many=True)
            media_success={r['item_key'] for r in requests if r['kind']=='media_text' and r['status']=='succeeded'}
            watch_success={r['item_key'] for r in requests if r['kind']=='watch' and r['status']=='succeeded'}
            before=summary['before']
            reconciliation=dict(new_media_identities=len(set(after['media_keys'])-set(before['media_keys'])),
                new_watch_history_events=len(set(after['watch_ids'])-set(before['watch_ids'])),
                new_media_embeddings=len(media_success-set(before.get('media_embedding_keys',before['media_keys']))),
                existing_media_regenerated=len(media_success&set(before.get('media_embedding_keys',before['media_keys']))),
                media_embeddings_reused=work.counts(gid)['media_text']['succeeded']-len(media_success),
                new_watch_embeddings=len(watch_success-set(before.get('watch_embedding_keys',before['watch_ids']))),
                existing_watch_regenerated=len(watch_success&set(before.get('watch_embedding_keys',before['watch_ids']))),
                watch_embeddings_reused=work.counts(gid)['watch']['succeeded']-len(watch_success))
            summary.update(after=after,reconciliation=reconciliation,stages=stages,source_hash=snapshot['_db_hash'],counts=work.counts(gid),watch_coverage=snapshot['watch_coverage'],
                inference={kind:dict(requests=sum(r['kind']==kind for r in requests),succeeded=sum(r['kind']==kind and r['status']=='succeeded' for r in requests),
                    seconds=sum(r['stats'].get('client_seconds',0) for r in requests if r['kind']==kind)) for kind in ('media_text','watch')},
                poster_inference_requests=0,model_before=state['model_sha256'],model_after=work.artifact(gid,'model.pkl')['sha256'],
                users_rebuilt=sum((r.get('timing') or {}).get('rebuilt',False) for r in work.items(gid,'user')),
                scoring=json.loads(bytes(work.artifact(gid,'scoring.json')['data'])),evaluation=evaluation,
                training_dataset=json.loads(bytes(work.artifact(gid,'dataset.json')['data'])),
                elapsed_seconds=time.perf_counter()-overall_started,no_new_shadow_generation=True)
            durable.query(sql.SQL('UPDATE {} SET summary=%s WHERE run_id=%s').format(durable.table('production_runs')),(Json(summary),run_id));durable.conn.commit()
            deployed=durable.query(sql.SQL('SELECT deployed_code_sha256 FROM {} WHERE singleton').format(durable.table('control')))['deployed_code_sha256']
            with monitor.span('publication'):
                result=promote(work,gid,approved=True,deployed_code=deployed)
            monitor.done('publication',message='Committed publication '+result['promotion_id'])
            with monitor.span('verification'):
                verified=verify_current_production(durable)
                if (verified['publication_id']!=result['promotion_id'] or verified['generation_id']!=gid
                    or verified['model_sha256']!=summary['model_after']):
                    raise ContractError('Published generation/model changed before final verification')
            monitor.done('verification',verified_vectors=sum(v['succeeded'] for v in verified['counts'].values()),poster_requests=0)
            summary['stage_details']=monitor.details
            summary['elapsed_seconds_total']=time.perf_counter()-overall_started
            durable.query(sql.SQL('UPDATE {} SET summary=%s,finished_at=clock_timestamp() WHERE run_id=%s').format(durable.table('production_runs')),(Json(summary),run_id));durable.conn.commit()
            return dict(run_id=run_id,**result,summary=summary)
        except BaseException as exc:
            durable.conn.rollback();durable.query(sql.SQL("UPDATE {} SET status='failed',error=%s WHERE run_id=%s").format(durable.table('production_runs')),(safe_error(exc),run_id));durable.conn.commit();raise
