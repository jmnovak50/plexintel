"""Text-only adoption and physical production state; no encoder calls on adoption."""
from copy import deepcopy
import hashlib
import io
import json
import joblib
import numpy as np
from psycopg2 import sql
from psycopg2.extras import Json

from .contracts import (ContractError, text_contract, text_only, fingerprint, canonical,
                        TEXT_FEATURE_VERSION, LABEL_VERSION, modality_contract, vector)
from .model import dataset, verify_bundle
from .recovery import IDENTITY_POLICY
from .features import SUPERVISION_POLICY


def dimensions(bundle, sha):
    from api.services.dimension_config import build_text_metadata
    return build_text_metadata(bundle['feature_names'],sha,generation_id=bundle['generation_id'],
        contract_hash=bundle['contract_hash'],encoder_digest=bundle['encoder']['digest'],
        serializer=bundle['media_serializer'])


def adopt(store,source_id,*,reason,progress=lambda value:None):
    """Derive a separately reviewable release. Copy vectors; never infer or refit B."""
    if not reason or not reason.strip():raise ContractError('Text adoption requires an explicit selection reason')
    g=store.generation(source_id)
    if g['scope']!='full' or g['status'] not in ('validated','active') or not g['validation']:
        raise ContractError('A fully validated source generation is required')
    if text_only(g['contract']):raise ContractError('Already text-only; use the normal incremental path')
    original=store.artifact(source_id,'text_model.pkl')
    old=joblib.load(io.BytesIO(bytes(original['data'])))
    if (old['generation_id']!=source_id or old['contract_hash']!=g['contract_hash']
        or old['encoder']!=g['contract']['encoder'] or old['label_version']!=LABEL_VERSION
        or old['variant']!='text_only' or old['ordering']!='media_text,user' or old['dimensions']!=[768,768]
        or old['feature_version']!=g['contract']['features']):
        raise ContractError('Source B model identity/layout mismatch')
    spec=text_contract(g['contract'])
    gid=store.create(spec,g['snapshot'],scope='full',parent=source_id,progress=progress)
    for kind in ('media_text','watch','user'):
        # Values and their original inference lineage are preserved byte-for-byte.
        store.query(sql.SQL('''UPDATE {} n SET source=o.source,semantic_hash=o.semantic_hash,
            input_hash=o.input_hash,status=o.status,embedding=o.embedding,attempts=o.attempts,
            error=o.error,timing=o.timing,generated_at=o.generated_at,origin_generation=o.origin_generation,
            modality_contract_hash=o.modality_contract_hash,provenance=o.provenance
            FROM {} o WHERE n.generation_id=%s AND o.generation_id=%s AND n.kind=%s
            AND o.kind=n.kind AND o.item_key=n.item_key''').format(store.table('items'),store.table('items')),(gid,source_id,kind))
    store.query(sql.SQL('''INSERT INTO {} SELECT %s,kind,item_key,stage,status,content_hash,provenance,timing,prepared_at
        FROM {} WHERE generation_id=%s AND stage='metadata' ''').format(store.table('preparations'),store.table('preparations')),(gid,source_id))
    store.query(sql.SQL('''INSERT INTO {} SELECT %s,child_kind,child_key,parent_kind,parent_key,parent_input_hash
        FROM {} WHERE generation_id=%s AND child_kind IN ('watch','user')''').format(store.table('dependencies'),store.table('dependencies')),(gid,source_id))
    store.conn.commit()
    rows,summary=dataset(store,gid,progress=progress)
    # Prove that the evaluated B classifier sees exactly the same inputs/labels.
    from .features import Vocabulary
    vocab=Vocabulary(**old['vocabulary'])
    reference=store.query(sql.SQL('SELECT owner,media_key,features,media_text::text AS text,user_embedding::text AS profile FROM {} WHERE generation_id=%s').format(store.table('modality_training_rows')),(source_id,),many=True)
    reference={(r['owner'],r['media_key']):r for r in reference}
    if len(rows)!=len(reference):raise ContractError('Text adoption changed the evaluated training cohort')
    for row in rows:
        prior=reference.get((row['owner'],row['media_key']))
        if prior is None:raise ContractError('Text adoption changed training identities')
        previous=dict(prior['features'],embedding=json.loads(prior['text'])+json.loads(prior['profile']))
        if (not np.array_equal(vocab.transform([row]),vocab.transform([previous]))
            or row['label']!=previous['label'] or row['sample_weight']!=previous['sample_weight']
            or row['prediction_at']!=previous['prediction_at'] or row['label_available_at']!=previous['label_available_at']):
            raise ContractError('Text feature/label parity with evaluated B failed')
    bundle=dict(old,generation_id=gid,contract_hash=fingerprint(spec),feature_version=TEXT_FEATURE_VERSION,
                identity_policy=IDENTITY_POLICY,supervision_policy=SUPERVISION_POLICY,
                dataset_hash=summary['dataset_hash'],media_serializer=spec['media_serializer'],
                adopted_from=dict(generation_id=source_id,artifact='text_model.pkl',sha256=original['sha256'],
                                  contract_hash=g['contract_hash'],reason=reason))
    verify_bundle(bundle,spec,fingerprint(spec),gid=gid)
    out=io.BytesIO();joblib.dump(bundle,out)
    sha=store.artifact(gid,'model.pkl',out.getvalue(),{k:v for k,v in bundle.items() if k!='model'})
    # Preserve original A/B/C evidence. Text approval is separate from C approval.
    evidence=store.artifact(source_id,'evaluation.json');evaluation=json.loads(bytes(evidence['data']))
    evaluation=deepcopy(evaluation)
    evaluation.update(chronological=evaluation['ablations']['B_text_only']['chronological'],
        identity_policy=IDENTITY_POLICY,supervision_policy=SUPERVISION_POLICY,
        show_grouped=dict(metrics=evaluation['ablations']['B_text_only']['show_grouped']),
        selection=dict(variant='B_text_only',reason=reason,source_generation=source_id,
                       evaluation_sha256=evidence['sha256'],model_sha256=original['sha256'],
                       exact_feature_label_parity=True,no_refit=True,no_inference=True),model_sha256=sha)
    store.artifact(gid,'evaluation.json',canonical(evaluation).encode(),dict(contract_hash=fingerprint(spec)))
    store.artifact(gid,'dimensions.json',canonical(dimensions(bundle,sha)).encode(),dict(contract_hash=fingerprint(spec)))
    store.conn.commit()
    return dict(generation_id=gid,source_generation=source_id,adopted_model_sha256=original['sha256'],
                model_sha256=sha,embedding_inference_requests=0,model_refits=0)


def load_production(store):
    """The active classifier comes from canonical production state, not shadow artifacts."""
    installed=store.query('SELECT to_regclass(%s) IS NOT NULL AS ready',(store.schema+'.production_state',))
    if not installed['ready']:return None
    row=store.query(sql.SQL('SELECT * FROM {} WHERE singleton').format(store.table('production_state')))
    if not row:return None
    data=bytes(row['model_bundle'])
    if hashlib.sha256(data).hexdigest()!=row['model_sha256'] or fingerprint(row['contract'])!=row['contract_hash']:
        raise ContractError('Canonical production model/contract checksum mismatch')
    if not text_only(row['contract']):raise ContractError('Unsupported production representation')
    bundle,vocab=verify_bundle(joblib.load(io.BytesIO(data)),row['contract'],row['contract_hash'],gid=row['generation_id'])
    return row,bundle,vocab


def physical_verification(store,gid,live_schema='public'):
    """Compare exact key sets and ALL persisted vectors, not merely joined rows."""
    result={}
    generation=store.generation(gid,include_snapshot=False)
    for kind,table,key in [('media_text','media_embeddings','rating_key'),('watch','watch_embeddings','watch_id'),('user','user_embeddings','username')]:
        row=store.query(sql.SQL('''WITH expected AS (SELECT item_key,embedding FROM {} WHERE generation_id=%s AND kind=%s AND status='succeeded')
            SELECT count(*) AS n,count(*) FILTER(WHERE p.{} IS NULL OR i.item_key IS NULL OR p.embedding IS DISTINCT FROM i.embedding) AS mismatch
            FROM {} p FULL JOIN expected i ON p.{}::text=i.item_key''').format(store.table('items'),sql.Identifier(key),sql.Identifier(live_schema,table),sql.Identifier(key)),(gid,kind))
        if row['mismatch'] or row['n']!=generation['expected'][kind]:raise ContractError('Physical production vector identity/value mismatch: '+kind)
        examples=store.query(sql.SQL('SELECT {}::text AS key,embedding::text AS value FROM {} ORDER BY {}::text LIMIT 3')
            .format(sql.Identifier(key),sql.Identifier(live_schema,table),sql.Identifier(key)),many=True)
        result[kind]=dict(count=row['n'],dimensions=768,all_vectors_exact=True,
            representative_sha256=[dict(key=r['key'],sha256=hashlib.sha256(r['value'].encode()).hexdigest()) for r in examples])
    return result


def train_text(store,gid,*,progress=lambda value:None,monitor=None):
    """Future text-only refits; no posterior/artwork dependencies or legacy controls."""
    from .model import populations,fit,fit_compare
    from .features import Vocabulary,chronological_split,feature_row,show_heldout_plan
    from .recovery import CanonicalTitles, IDENTITY_POLICY
    from contextlib import nullcontext
    with monitor.span('training_data') if monitor else nullcontext():
        g,media,watches,_=populations(store,gid)
        rows,summary=dataset(store,gid,progress=progress)
    if monitor:monitor.done('training_data',rows=summary['rows'],label_policy_skips=summary['skips'].get('label_policy',0),limited_history_skips=summary['skips'].get('limited_history',0))
    with monitor.span('train_model') if monitor else nullcontext():
        train,test,boundary=chronological_split(rows)
        chronological=fit_compare(train,test,include_poster=False,progress=progress)
        identity=CanonicalTitles(media)
        group_train,group_test,excluded,group_skips=show_heldout_plan(g,media,rows,identity=identity,boundary=boundary)
        a=[];b=[]
        for row,is_test in [(r,False) for r in group_train]+[(r,True) for r in group_test]:
            value=feature_row(g,media,watches,g['snapshot']['events'],row['owner'],row['media_key'],row['prediction_at'],excluded_keys=excluded,identity=identity)
            if value is None:raise ContractError('Grouped feature support differs from training plan')
            value.update({k:row[k] for k in ('label','sample_weight','prediction_at','label_available_at',
                'label_source','observation_kind','feedback_provenance','auxiliary_feedback_count','auxiliary_feedback_conflicts')})
            (b if is_test else a).append(value)
        grouped=fit_compare(a,b,include_poster=False,progress=progress)
        vocab=Vocabulary.fit(rows,include_poster=False);model=fit(rows,vocab,progress=progress)
        bundle=dict(generation_id=gid,contract_hash=g['contract_hash'],encoder=g['contract']['encoder'],variant='text_only',
            feature_version=g['contract']['features'],label_version=LABEL_VERSION,dimensions=[768,768],ordering='media_text,user',
            identity_policy=IDENTITY_POLICY,supervision_policy=SUPERVISION_POLICY,
            vocabulary=vocab.specification(),feature_names=vocab.names,model=model,dataset_hash=summary['dataset_hash'],
            media_serializer=g['contract']['media_serializer'])
        out=io.BytesIO();joblib.dump(bundle,out)
        sha=store.artifact(gid,'model.pkl',out.getvalue(),{k:v for k,v in bundle.items() if k!='model'})
        evaluation=dict(chronological=chronological,show_grouped=dict(metrics=grouped),
            show_grouped_support_skips=group_skips,
            ablations=dict(B_text_only=dict(chronological=chronological,show_grouped=grouped)),
            feature_policy=g['contract']['features'],label_policy=LABEL_VERSION,model_sha256=sha,
            identity_policy=IDENTITY_POLICY,supervision_policy=SUPERVISION_POLICY,
            comparison='Text-only chronological and show-heldout validation, including retrospective explicit supervision. Submission cutoff does not establish first viewing. No new image ablation.')
        store.artifact(gid,'evaluation.json',canonical(evaluation).encode(),dict(contract_hash=g['contract_hash']))
        store.artifact(gid,'dimensions.json',canonical(dimensions(bundle,sha)).encode(),dict(contract_hash=g['contract_hash']))
        store.conn.commit();return evaluation


def archive_runtime(store,publication,control):
    from .source import serializable
    row=store.query(sql.SQL('SELECT * FROM {} WHERE singleton').format(store.table('production_state')))
    if row:
        model=bytes(row.pop('model_bundle'))
    elif control['active_generation']:
        model=bytes(store.artifact(control['active_generation'],'model.pkl')['data'])
    else:model=b''
    inputs=store.query(sql.SQL('SELECT * FROM {} ORDER BY kind,item_key').format(store.table('production_inputs')),many=True)
    manifest=dict(control=serializable(dict(control)),state=serializable(row),inputs=inputs,
                  model_sha256=hashlib.sha256(model).hexdigest())
    store.query(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,%s,%s,%s)').format(store.table('production_rollback')),
        (publication,Json(manifest['control']),Json(manifest['state']),Json(inputs),model,fingerprint(manifest)))
    return manifest


def publish_runtime(store,gid,*,publication_id=None):
    from .source import serializable
    g=store.generation(gid);artifact=store.artifact(gid,'model.pkl')
    store.query(sql.SQL('DELETE FROM {}').format(store.table('production_inputs')))
    deps=store.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s').format(store.table('dependencies')),(gid,),many=True)
    for kind in ('media_text','watch','user'):
        for row in store.items(gid,kind):
            record={k:v for k,v in row.items() if k not in ('embedding','poster')}
            record['vector_sha256']=hashlib.sha256(__import__('numpy').asarray(vector(row['embedding']),dtype='<f4').tobytes()).hexdigest()
            record['dependencies']=[d for d in deps if d['child_kind']==kind and d['child_key']==row['item_key']]
            store.query(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s)').format(store.table('production_inputs')),
                        (kind,row['item_key'],Json(serializable(record))))
    store.query(sql.SQL('DELETE FROM {}').format(store.table('production_state')))
    store.query(sql.SQL('''INSERT INTO {}(singleton,generation_id,contract,contract_hash,snapshot,source_hash,expected,model_sha256,model_bundle,evaluation,publication_id)
        VALUES(true,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''').format(store.table('production_state')),
        (gid,Json(g['contract']),g['contract_hash'],Json(g['snapshot']),g['source_hash'],Json(g['expected']),artifact['sha256'],bytes(artifact['data']),Json(json.loads(bytes(store.artifact(gid,'evaluation.json')['data']))),publication_id))
    load_production(store)


def restore_runtime(store,publication):
    saved=store.query(sql.SQL('SELECT * FROM {} WHERE promotion_id=%s').format(store.table('production_rollback')),(publication,))
    if not saved:return  # Historical multimodal publication.
    model=bytes(saved['model_bundle'])
    manifest=dict(control=saved['control'],state=saved['state'],inputs=saved['inputs'],model_sha256=hashlib.sha256(model).hexdigest())
    if fingerprint(manifest)!=saved['manifest_sha256']:raise ContractError('Production runtime rollback archive checksum mismatch')
    store.query(sql.SQL('DELETE FROM {}').format(store.table('production_inputs')))
    for row in saved['inputs']:
        store.query(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s)').format(store.table('production_inputs')),(row['kind'],row['item_key'],Json(row['record'])))
    store.query(sql.SQL('DELETE FROM {}').format(store.table('production_state')))
    state=saved['state']
    if state:
        store.query(sql.SQL('''INSERT INTO {}(singleton,generation_id,contract,contract_hash,snapshot,source_hash,expected,model_sha256,model_bundle,published_at,evaluation,publication_id)
            VALUES(true,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''').format(store.table('production_state')),
            (state['generation_id'],Json(state['contract']),state['contract_hash'],Json(state['snapshot']),state['source_hash'],
             Json(state['expected']),state['model_sha256'],model,state['published_at'],Json(state['evaluation']),state.get('publication_id')))
        load_production(store)
    elif saved['control']['active_generation']:
        previous=store.artifact(saved['control']['active_generation'],'model.pkl')
        if bytes(previous['data'])!=model:raise ContractError('Previous production classifier differs from rollback archive')
    control=saved['control']
    store.query(sql.SQL('''UPDATE {} SET active_generation=%s,previous_generation=%s,legacy_model_sha256=%s,
        deployed_code_sha256=%s,updated_at=%s WHERE singleton''').format(store.table('control')),
        tuple(control[k] for k in ('active_generation','previous_generation','legacy_model_sha256','deployed_code_sha256','updated_at')))


def seed_from_production(store,snapshot,*,progress=lambda value:None,live_schema='public'):
    """Incremental staging reads vectors from physical production tables, not shadow items."""
    state,_,_=load_production(store)
    records=store.query(sql.SQL('SELECT * FROM {}').format(store.table('production_inputs')),many=True)
    records={(r['kind'],r['item_key']):r['record'] for r in records}
    # Preserve availability provenance for unchanged history.
    for event in snapshot['events']:
        old=records.get(('watch',str(event['watch_id'])))
        if old and fingerprint({k:v for k,v in event.items() if k!='observed_at'})==old['semantic_hash']:
            event['observed_at']=old['source'].get('observed_at',event.get('observed_at'))
    gid=store.create(state['contract'],snapshot,scope='full',parent=state['generation_id'],progress=progress)
    for kind,table,key in [('media_text','media_embeddings','rating_key'),('watch','watch_embeddings','watch_id'),('user','user_embeddings','username')]:
        physical=store.query(sql.SQL('SELECT {}::text AS key,embedding FROM {}').format(sql.Identifier(key),sql.Identifier(live_schema,table)),many=True)
        vectors={r['key']:r['embedding'] for r in physical}
        for row in store.items(gid,kind):
            old=records.get((kind,row['item_key']))
            if not old or row['item_key'] not in vectors:continue
            if old['modality_contract_hash']!=fingerprint(modality_contract(state['contract'],kind)):
                raise ContractError('Physical production vector provenance is incompatible')
            if kind=='watch' and row['semantic_hash']!=old['semantic_hash']:continue
            source={**old['source'],**row['source']} if kind=='media_text' else old['source']
            from pgvector import Vector
            store.query(sql.SQL('''UPDATE {} SET source=%s,semantic_hash=%s,input_hash=%s,status='succeeded',embedding=%s,
                generated_at=%s,origin_generation=%s,modality_contract_hash=%s,provenance=%s,timing=%s WHERE generation_id=%s AND kind=%s AND item_key=%s''').format(store.table('items')),
                (Json(source),old['semantic_hash'],old['input_hash'],Vector(vector(vectors[row['item_key']])),old['generated_at'],
                 old['origin_generation'],old['modality_contract_hash'],Json(old['provenance']),Json(dict(inherited=True)),gid,kind,row['item_key']))
            for dep in old.get('dependencies',[]):
                store.query(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,%s,%s,%s)').format(store.table('dependencies')),
                    (gid,kind,row['item_key'],dep['parent_kind'],dep['parent_key'],dep['parent_input_hash']))
            if kind=='media_text':store.preparation(gid,row['item_key'],'metadata',status='succeeded',content_hash=old['semantic_hash'])
    store.conn.commit();return gid


def daily(store,config,*,collect,plex_factory,cache,publication_lock,pipeline_lock_held=False,progress=lambda value:None):
    from .production_run import execute
    return execute(store,config,collect=collect,plex_factory=plex_factory,cache=cache,
        publication_lock=publication_lock,pipeline_lock_held=pipeline_lock_held,progress=progress)


def verify_current_production(store,*,live_schema='public'):
    """Verify canonical physical state independently of frozen migration ledgers."""
    from .contracts import modality_contract
    from api.services.dimension_config import feature_groups
    state,bundle,vocab=load_production(store)
    rows=store.query(sql.SQL('SELECT * FROM {}').format(store.table('production_inputs')),many=True)
    indexed={(r['kind'],r['item_key']):r['record'] for r in rows};counts={}
    for kind,table,key in [('media_text','media_embeddings','rating_key'),('watch','watch_embeddings','watch_id'),('user','user_embeddings','username')]:
        physical=store.query(sql.SQL('SELECT {}::text AS key,embedding FROM {}').format(sql.Identifier(key),sql.Identifier(live_schema,table)),many=True)
        expected={key:record for (modality,key),record in indexed.items() if modality==kind}
        if set(expected)!={r['key'] for r in physical} or len(physical)!=state['expected'][kind]:raise ContractError('Canonical physical production population mismatch')
        contract=modality_contract(state['contract'],kind)
        for row in physical:
            record=expected[row['key']];values=vector(row['embedding'],unit=kind!='user')
            digest=hashlib.sha256(np.asarray(values,dtype='<f4').tobytes()).hexdigest()
            if record.get('vector_sha256')!=digest or record['generation_id']!=state['generation_id']:
                raise ContractError('Canonical production vector hash/encoder generation mismatch')
            if record['modality_contract_hash']!=fingerprint(contract) or record['provenance']!=dict(**contract,output_dimensions=768,normalization_state=contract['normalization']):
                raise ContractError('Canonical production provenance mismatch')
        counts[kind]=dict(expected=len(physical),succeeded=len(physical),failed=0,pending=0,dimensions=768,all_vectors_exact=True)
    config=store.query(sql.SQL('SELECT metadata FROM {} WHERE active').format(sql.Identifier(live_schema,'embedding_feature_config')))['metadata']
    if config['model_sha256']!=state['model_sha256'] or config['feature_names']!=vocab.names or feature_groups(config)!=[dict(name='media_text',start=0,width=768),dict(name='user',start=768,width=768)]:
        raise ContractError('Canonical dimension/model contract mismatch')
    invalid=store.query(sql.SQL("SELECT count(*) AS n FROM {} WHERE dimension<0 OR dimension>=1536 OR shap_value::text IN ('NaN','Infinity','-Infinity')").format(sql.Identifier(live_schema,'shap_impact')))['n']
    if invalid:raise ContractError('Incompatible production SHAP dimensions')
    stale=store.query(sql.SQL('SELECT count(*) AS n FROM {} WHERE model_version<>%s OR config_id<>%s').format(sql.Identifier(live_schema,'shap_prediction_context')),(state['model_sha256'],config['config_id']))['n']
    if stale:raise ContractError('Production SHAP context belongs to a different classifier')
    return dict(generation_id=state['generation_id'],publication_id=state.get('publication_id'),verified=True,
        feature_order='media_text,user',embedding_dimensions=1536,classifier_features=len(vocab.names),
        model_sha256=state['model_sha256'],encoder=state['contract']['encoder'],counts=counts,
        source_hash=state['source_hash'],poster_inference='disabled/1.0',watch_coverage=state['snapshot']['watch_coverage'])
