"""Generation-specific independent-modality classifiers, ablations and scoring."""
from datetime import timedelta
from collections import defaultdict
import hashlib
import io
import json
import time
import joblib
import numpy as np
from pgvector import Vector
from psycopg2 import sql
from psycopg2.extras import Json
from .contracts import ContractError,FEATURE_VERSION,LABEL_VERSION,canonical,cosine,fingerprint,utc,text_only,TEXT_FEATURE_VERSION
from .features import Vocabulary,ProfileContext,chronological_split,feature_row,training_rows
from .backfill import runtime_seconds,generation_writer
from .evaluation import evaluate


def populations(store,gid):
    g=store.mutable(gid);counts=store.counts(gid)
    if g['contract']['features']!=(TEXT_FEATURE_VERSION if text_only(g['contract']) else FEATURE_VERSION) or g['contract']['labels']!=LABEL_VERSION:
        raise ContractError('Feature/label contract differs from this implementation')
    for kind,r in counts.items():
        if r['expected']!=r['succeeded']+(r['missing'] if kind=='media_poster' else 0) or r['failed'] or r['pending']:
            raise ContractError('Every required modality/population must complete before downstream construction')
    return (g,{r['item_key']:r for r in store.items(gid,'media_text')},
        {r['item_key']:r for r in store.items(gid,'watch')},{r['item_key']:r for r in store.items(gid,'media_poster')})


def dataset(store,gid,*,progress=lambda value:None):
    g,media,watches,posters=populations(store,gid)
    rows,skips=training_rows(g,media,watches,posters,progress=progress)
    if not rows:raise ContractError('No leakage-safe examples; no fallback to legacy training rows')
    text_mode=text_only(g['contract'])
    table='text_training_rows' if text_mode else 'modality_training_rows'
    store.query(sql.SQL('DELETE FROM {} WHERE generation_id=%s').format(store.table(table)),(gid,))
    for i,row in enumerate(rows,1):
        if row['dependencies']['generation_id']!=gid or row['dependencies']['contract_hash']!=g['contract_hash']:
            raise ContractError('Training dependency provenance mismatch')
        fields={k:v for k,v in row.items() if k not in ('embedding','dependencies')}
        values=row['embedding']
        if text_mode:
            store.query(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)').format(store.table(table)),
                (gid,row['owner'],row['media_key'],row['prediction_at'],row['label_available_at'],row['label'],
                 Vector(values),Json({k:v for k,v in fields.items() if k!='poster_missing'}),Json(row['dependencies'])))
        else:
            store.query(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)').format(store.table('modality_training_rows')),
                (gid,row['owner'],row['media_key'],row['prediction_at'],row['label_available_at'],row['label'],
                 Vector(values[:768]),None if row['poster_missing'] else Vector(values[768:1536]),Vector(values[1536:]),Json(fields),Json(row['dependencies'])))
        if i%32==0 or i==len(rows):progress(dict(stage='training-dataset',expected=len(rows),completed=i,failed=0))
    hasher=hashlib.sha256()
    for row in rows:
        serialized={**{k:v for k,v in row.items() if k!='embedding'},
            'embedding':[float(v) if np.isfinite(v) else None for v in row['embedding']]}
        hasher.update(canonical(serialized).encode());hasher.update(b'\n')
    summary=dict(rows=len(rows),skips=skips,feature_version=g['contract']['features'],label_version=LABEL_VERSION,
        dataset_hash=hasher.hexdigest(),hash_format='canonical-rows-jsonl/1.0',watch_coverage=g['snapshot']['watch_coverage'],
        retrospective_metadata_assumption='Captured descriptive metadata (current Plex or explicitly approved stored history); point-in-time metadata snapshots do not exist. Mutable ratings/popularity/outcomes are excluded.')
    store.artifact(gid,'dataset.json',canonical(summary).encode(),dict(contract_hash=g['contract_hash']));store.conn.commit()
    return rows,summary


def fit(rows,vocabulary,*,progress=lambda value:None):
    import xgboost as xgb
    y=np.array([r['label'] for r in rows],dtype=np.int32)
    if set(y)!={0,1}:raise ContractError('Training requires both classes')
    weights=np.array([r['sample_weight'] for r in rows],dtype=np.float32)*np.where(y==0,(y==1).sum()/(y==0).sum(),1.)
    class Observer(xgb.callback.TrainingCallback):
        def after_iteration(self,model,epoch,evals_log):
            if epoch%10==0 or epoch==99:progress(dict(phase=f'boosting round {epoch+1}/100; examples={len(rows)}'))
            return False
    classifier=xgb.XGBClassifier(objective='binary:logistic',eval_metric='aucpr',n_estimators=100,max_depth=6,
        learning_rate=.1,subsample=.8,random_state=42,scale_pos_weight=1.,n_jobs=2,callbacks=[Observer()])
    classifier.fit(vocabulary.transform(rows),y,sample_weight=weights)
    classifier.set_params(callbacks=None)  # Do not serialize a local progress callback.
    classifier.get_booster().feature_names=vocabulary.names
    classifier._plexintel_training_keys=sorted({r['media_key'] for r in rows})
    return classifier


def metrics(classifier,vocabulary,rows):
    return evaluate(classifier,vocabulary,rows,training_keys=getattr(classifier,'_plexintel_training_keys',()))


def fit_compare(train_rows,test_rows,*,include_poster,progress=lambda value:None):
    if not test_rows:raise ContractError('Evaluation cohort lacks heldout examples')
    vocabulary=Vocabulary.fit(train_rows,include_poster=include_poster)
    started=time.perf_counter();classifier=fit(train_rows,vocabulary,progress=progress);elapsed=time.perf_counter()-started
    result=evaluate(classifier,vocabulary,test_rows,training_keys={r['media_key'] for r in train_rows})
    result.update(training_seconds=elapsed,train_rows=len(train_rows),feature_count=len(vocabulary.names),
        cohort_hash=fingerprint([(r['owner'],r['media_key'],r['prediction_at'],r['label']) for r in test_rows]),
        train_only_vocabulary=vocabulary.specification())
    return result


@generation_writer
def train(store,gid,*,legacy_populations=None,progress=lambda value:None):
    if text_only(store.generation(gid,include_snapshot=False)['contract']):
        from .text_production import train_text
        return train_text(store,gid,progress=progress)
    started=time.perf_counter();g,media,watches,posters=populations(store,gid)
    store.query(sql.SQL("DELETE FROM {} WHERE generation_id=%s AND name IN ('model.pkl','text_model.pkl','evaluation.json','scoring.json','dimensions.json')").format(store.table('artifacts')),(gid,))
    store.query(sql.SQL('DELETE FROM {} WHERE generation_id=%s').format(store.table('predictions')),(gid,));store.conn.commit()
    rows,summary=dataset(store,gid,progress=progress)
    train_rows,test_rows,boundary=chronological_split(rows)
    evaluations={};jobs=0;expected_fits=11 if legacy_populations is not None else 6
    def compare(name,train_set,test_set,include):
        nonlocal jobs
        progress(dict(stage='model-evaluation',expected=expected_fits,completed=jobs,failed=0,phase=name))
        result=fit_compare(train_set,test_set,include_poster=include,progress=progress);jobs+=1
        progress(dict(stage='model-evaluation',expected=expected_fits,completed=jobs,failed=0,phase=name));return result
    evaluations['B_text_only']=dict(chronological=compare('B chronological',train_rows,test_rows,False))
    evaluations['C_text_poster']=dict(chronological=compare('C chronological',train_rows,test_rows,True))
    groups=sorted({r['show_key'] for r in rows},key=lambda k:hashlib.sha256(k.encode()).hexdigest())
    heldout=set(groups[:max(1,len(groups)//5)])
    excluded={k for k,m in media.items() if str(m['source'].get('show_rating_key') or k) in heldout}
    grouped_train=[];grouped_test=[]
    for row in rows:
        is_test=row['show_key'] in heldout and utc(row['prediction_at'])>=boundary
        is_train=row['show_key'] not in heldout and utc(row['prediction_at'])<boundary and utc(row['label_available_at'])<boundary
        if not(is_test or is_train):continue
        features=feature_row(g,media,watches,g['snapshot']['events'],row['owner'],row['media_key'],row['prediction_at'],posters=posters,excluded_keys=excluded)
        if features is None:continue
        features.update({k:row[k] for k in ('label','sample_weight','prediction_at','label_available_at')})
        (grouped_test if is_test else grouped_train).append(features)
    if {r['label'] for r in grouped_train}!={0,1} or {r['label'] for r in grouped_test}!={0,1}:
        raise ContractError('Show-heldout chronological test lacks class/history support; no random fallback')
    for name,include in [('B_text_only',False),('C_text_poster',True)]:
        evaluations[name]['show_grouped']=compare(name+' show-heldout',grouped_train,grouped_test,include)
    evaluation=dict(boundary=boundary.isoformat(),train_rows=len(train_rows),ablations=evaluations,
        chronological=evaluations['C_text_poster']['chronological'],
        show_grouped=dict(heldout_groups=len(heldout),metrics=evaluations['C_text_poster']['show_grouped']),
        label_policy=LABEL_VERSION,feature_policy=FEATURE_VERSION,metadata_limitation=summary['retrospective_metadata_assumption'],
        comparison='B and C have identical rows, chronological boundaries, vocabularies, text/user/watch inputs. C adds only poster features and missing-art indicator.')
    if legacy_populations is not None:
        progress(dict(stage='model-evaluation',expected=expected_fits,completed=jobs,failed=0,phase='legacy control fits'))
        evaluation['paired_controls']=paired_controls(g,media,watches,posters,legacy_populations,boundary,progress=progress)
        jobs+=4
        # Corrected A on the same show-heldout cohort, with all heldout-show events excluded.
        old_media,old_watches,shared_g=legacy_inputs(g,media,watches,legacy_populations)
        old_train=[];old_test=[]
        for source,dest in ((grouped_train,old_train),(grouped_test,old_test)):
            for row in source:
                if row['media_key'] not in old_media:continue
                feature=feature_row(shared_g,old_media,old_watches,shared_g['snapshot']['events'],row['owner'],row['media_key'],row['prediction_at'],posters=posters,excluded_keys=excluded)
                if feature is None:continue
                feature.update({k:row[k] for k in ('label','sample_weight','prediction_at','label_available_at')});dest.append(feature)
        evaluation['ablations']['A_corrected_legacy']=dict(
            chronological=evaluation['paired_controls']['legacy_vectors_corrected_features'],
            show_grouped=compare('A show-heldout',old_train,old_test,False),coverage=evaluation['paired_controls']['coverage'])
    evaluation['accuracy_attribution']='Poster incremental value is C versus B; encoder/serializer effects are B versus corrected A. Unsafe legacy controls isolate profile leakage, not image value.'
    for variant,include,name in [('text_only',False,'text_model.pkl'),('text_poster',True,'model.pkl')]:
        progress(dict(stage='model-evaluation',expected=expected_fits,completed=jobs,failed=0,phase='final '+variant))
        vocab=Vocabulary.fit(rows,include_poster=include);model=fit(rows,vocab,progress=progress)
        bundle=dict(generation_id=gid,contract_hash=g['contract_hash'],encoder=g['contract']['encoder'],variant=variant,
            feature_version=FEATURE_VERSION,label_version=LABEL_VERSION,dimensions=[768,768,768] if include else [768,768],
            ordering='media_text,media_poster,user' if include else 'media_text,user',vocabulary=vocab.specification(),
            feature_names=vocab.names,model=model,dataset_hash=summary['dataset_hash'])
        out=io.BytesIO();joblib.dump(bundle,out)
        digest=store.artifact(gid,name,out.getvalue(),{k:v for k,v in bundle.items() if k!='model'})
        if include:
            evaluation['model_sha256']=digest
            from api.services.dimension_config import build_independent_metadata
            dimensions=build_independent_metadata(vocab.names,digest,generation_id=gid,contract_hash=g['contract_hash'],
                encoder_digest=g['contract']['encoder']['digest'],serializer=g['contract']['media_serializer'])
            store.artifact(gid,'dimensions.json',canonical(dimensions).encode(),dict(contract_hash=g['contract_hash']))
        jobs+=1;progress(dict(stage='model-evaluation',expected=expected_fits,completed=jobs,failed=0))
    evaluation['total_training_evaluation_seconds']=time.perf_counter()-started
    store.artifact(gid,'evaluation.json',canonical(evaluation).encode(),dict(contract_hash=g['contract_hash']));store.conn.commit()
    return evaluation


def legacy_inputs(g,media,watches,legacy):
    import copy
    result=copy.deepcopy(g);common_media=set(media)&set(legacy['media']);common_watch=set(watches)&set(legacy['watch'])
    result['snapshot']['events']=[e for e in g['snapshot']['events'] if str(e['rating_key']) in common_media and str(e['watch_id']) in common_watch]
    result['snapshot']['feedback']=[f for f in g['snapshot']['feedback'] if str(f['rating_key']) in common_media]
    old_media=copy.deepcopy({k:v for k,v in media.items() if k in common_media})
    old_watches=copy.deepcopy({k:v for k,v in watches.items() if k in common_watch})
    for kind,values in [('media',old_media),('watch',old_watches)]:
        for key,row in values.items():
            row['embedding']=legacy[kind][key];row.pop('_cached_input_hash',None);row.pop('_cached_vector',None)
    return old_media,old_watches,result
def paired_controls(g,media,watches,posters,legacy,boundary,*,progress=lambda value:None):
    """Use legacy vectors ONLY in explicitly labeled, never-published controls.

    Same target/cohort and fold vocabulary permit separating outcome-isolation
    effects from representation/serializer changes. No cross-space cosines.
    """
    import copy
    boundary=utc(boundary)
    common_media=set(media)&set(legacy['media'])
    common_watch=set(watches)&set(legacy['watch'])
    g=copy.deepcopy(g)
    original_events=len(g['snapshot']['events'])
    g['snapshot']['events']=[e for e in g['snapshot']['events'] if str(e['rating_key']) in common_media and str(e['watch_id']) in common_watch]
    g['snapshot']['feedback']=[f for f in g['snapshot']['feedback'] if str(f['rating_key']) in common_media]
    new_media={k:v for k,v in media.items() if k in common_media}
    new_watches={k:v for k,v in watches.items() if k in common_watch}
    old_media=copy.deepcopy(new_media);old_watches=copy.deepcopy(new_watches)
    for key,row in old_media.items():
        if key not in legacy['media']:raise ContractError('Legacy control coverage incomplete')
        row['embedding']=legacy['media'][key]
        row.pop('_cached_input_hash',None);row.pop('_cached_vector',None)
    for key,row in old_watches.items():
        if key not in legacy['watch']:raise ContractError('Legacy behavioral control coverage incomplete')
        row['embedding']=legacy['watch'][key]
        row.pop('_cached_input_hash',None);row.pop('_cached_vector',None)
    corrected,_=training_rows(g,old_media,old_watches,posters)
    old_train=[r for r in corrected if utc(r['prediction_at'])<boundary and utc(r['label_available_at'])<boundary]
    old_test=[r for r in corrected if utc(r['prediction_at'])>=boundary]
    vocab=Vocabulary.fit(old_train,include_poster=False)
    corrected_model=fit(old_train,vocab,progress=progress)
    corrected_metrics=metrics(corrected_model,vocab,old_test)
    # Reintroduce the old all-history behavioral similarity ONLY for this ablation.
    # Media user half retains target exclusion to isolate the confirmed watch_sim gap.
    contaminated=[]
    for row in corrected:
        target=row['media_key'];behavior=[]
        for event in g['snapshot']['events']:
            key=str(event['rating_key']);runtime=runtime_seconds(old_media[key]) if key in old_media else None
            if event['username']==row['owner'] and runtime and event.get('played_seconds') is not None and event['played_seconds']/runtime>=.5:
                behavior.append(old_watches[str(event['watch_id'])]['embedding'])
        value={**row}
        value['watch_sim']=cosine(np.mean(np.asarray(behavior),axis=0),old_media[target]['embedding']) if behavior else 0.
        contaminated.append(value)
    unsafe_train=[r for r in contaminated if utc(r['prediction_at'])<boundary and utc(r['label_available_at'])<boundary]
    unsafe_test=[r for r in contaminated if utc(r['prediction_at'])>=boundary]
    unsafe_model=fit(unsafe_train,vocab,progress=progress)
    from .backfill import qualifying_profiles
    complete_profiles=qualifying_profiles(g['snapshot']['events'],old_media,g['contract']['profile_threshold'])
    full_history=[]
    for row in contaminated:
        keys=[k for k in complete_profiles.get(row['owner'],[]) if k!=row['media_key']]
        if not keys:raise ContractError('Legacy comparison cohort lost profile support')
        user_mean=np.mean(np.asarray([old_media[k]['embedding'] for k in keys],dtype=np.float64),axis=0)
        full_history.append({**row,'embedding':np.concatenate([row['embedding'][:1536],user_mean]).astype(np.float32)})
    full_train=[r for r in full_history if utc(r['prediction_at'])<boundary and utc(r['label_available_at'])<boundary]
    full_test=[r for r in full_history if utc(r['prediction_at'])>=boundary]
    full_model=fit(full_train,vocab,progress=progress)
    new_rows,_=training_rows(g,new_media,new_watches,posters)
    new_train=[r for r in new_rows if utc(r['prediction_at'])<boundary and utc(r['label_available_at'])<boundary]
    new_test=[r for r in new_rows if utc(r['prediction_at'])>=boundary]
    if {(r['owner'],r['media_key']) for r in new_test}!={(r['owner'],r['media_key']) for r in old_test}:
        raise ContractError('Paired comparison cohort differs')
    new_model=fit(new_train,vocab,progress=progress)
    return dict(coverage=dict(source_events=original_events,shared_events=len(g['snapshot']['events']),
                             missing_legacy_events=original_events-len(g['snapshot']['events']),shared_media=len(common_media)),
                new_vectors_corrected_same_cohort=metrics(new_model,vocab,new_test),
                legacy_vectors_corrected_features=corrected_metrics,
                legacy_vectors_full_history_watch_sim=metrics(unsafe_model,vocab,unsafe_test),
                legacy_vectors_full_history_user_and_watch_profiles=metrics(full_model,vocab,full_test),
                caution='Control models are discarded. Encoder, media serializer, image modality and watch serializer all change in the new representation; no single-factor accuracy attribution.')



def verify_bundle(bundle, specification, contract_hash, *, gid=None):
    text_mode=text_only(specification)
    expected_dimensions=[768,768] if text_mode else [768,768,768]
    ordering='media_text,user' if text_mode else 'media_text,media_poster,user'
    if (gid is not None and bundle['generation_id']!=gid or bundle['contract_hash']!=contract_hash
        or bundle['encoder']!=specification['encoder'] or bundle['feature_version']!=specification['features']
        or bundle['label_version']!=LABEL_VERSION or bundle['variant']!=('text_only' if text_mode else 'text_poster')
        or bundle['ordering']!=ordering or bundle['dimensions']!=expected_dimensions):
        raise ContractError('Model generation/feature/encoder/modality contract mismatch')
    vocabulary=Vocabulary(**bundle['vocabulary'])
    if vocabulary.include_poster==text_mode or bundle['feature_names']!=vocabulary.names or bundle['model'].get_booster().feature_names!=vocabulary.names:
        raise ContractError('Model feature names/order differ from serving preprocessing')
    if bundle['model'].get_booster().num_features()!=len(vocabulary.names):raise ContractError('Model feature width mismatch')
    expected=[f'{group}_{i}' for group in ordering.split(',') for i in range(768)]
    if vocabulary.names[:sum(expected_dimensions)]!=expected or text_mode and any(n.startswith('media_poster_') or n=='poster_missing' for n in vocabulary.names):
        raise ContractError('Invalid production embedding feature ordering')
    return bundle,vocabulary


def load_bundle(store,gid):
    g=store.generation(gid);artifact=store.artifact(gid,'model.pkl')
    bundle=joblib.load(io.BytesIO(bytes(artifact['data'])))
    result=verify_bundle(bundle,g['contract'],g['contract_hash'],gid=gid)
    data=json.loads(bytes(store.artifact(gid,'dataset.json')['data']))
    if data['dataset_hash']!=bundle['dataset_hash']:raise ContractError('Model dataset provenance mismatch')
    return result


@generation_writer
def score(store,gid,*,batch_size=128,shap_items_per_user=750,progress=lambda value:None):
    import xgboost as xgb
    started=time.perf_counter();g,media,watches,posters=populations(store,gid);bundle,vocab=load_bundle(store,gid)
    as_of=utc(g['snapshot']['as_of'])+timedelta(microseconds=1)
    feedback={(r['username'],str(r['rating_key'])):r for r in g['snapshot']['feedback']}
    owners=[r['item_key'] for r in store.items(gid,'user')]
    store.query(sql.SQL('DELETE FROM {} WHERE generation_id=%s').format(store.table('predictions')),(gid,))
    total=0;skipped=0
    for owner_index,owner in enumerate(owners):
        progress(dict(stage='shadow-scoring',expected=len(owners),completed=owner_index,failed=0))
        events=[e for e in g['snapshot']['events'] if e['username']==owner]
        context=ProfileContext(g,media,watches,events,owner,as_of);by_key=defaultdict(list)
        for event in events:by_key[str(event['rating_key'])].append(event)
        rows=[]
        for key,parent in media.items():
            if parent['source']['metadata']['media_type'] not in ('movie','episode'):continue
            f=feedback.get((owner,key))
            if f and f.get('suppress') and f.get('feedback')!='interested':continue
            runtime=runtime_seconds(parent);watched=False
            for event in by_key[key]:
                percent=event.get('percent_complete');ratio=(percent/100 if percent>=1 else percent) if percent is not None else 0
                if ratio>=.5 or runtime and event.get('played_seconds') is not None and event['played_seconds']/runtime>=.5:
                    watched=True;break
            if watched:continue
            row=feature_row(g,media,watches,events,owner,key,as_of,posters=posters,context=context)
            if row is None:skipped+=1;continue
            rows.append(row)
        predictions=[]
        for start in range(0,len(rows),batch_size):
            part=rows[start:start+batch_size];probability=bundle['model'].predict_proba(vocab.transform(part))[:,1]
            predictions.extend(zip(part,map(float,probability)))
            progress(dict(stage='shadow-scoring',expected=len(owners),completed=owner_index,failed=0,
                phase=f'candidate batch {start+len(part)}/{len(rows)}'))
        predictions.sort(key=lambda pair:(-pair[1],int(pair[0]['media_key'])))
        for index,(row,probability) in enumerate(predictions):
            shap=[]
            if index<shap_items_per_user:
                values=bundle['model'].get_booster().predict(xgb.DMatrix(vocab.transform([row]),feature_names=vocab.names,nthread=2),pred_contribs=True)[0][:-1]
                shap=[[i,float(values[i])] for i in sorted(range(sum(bundle['dimensions'])),key=lambda i:abs(values[i]),reverse=True)[:40]]
            store.query(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,%s,%s,%s,%s)').format(store.table('predictions')),
                (gid,owner,row['media_key'],probability,cosine(row['embedding'][:768],row['embedding'][-768:]),index+1,Json(shap)))
        total+=len(predictions)
    summary=dict(predictions=total,users=len(owners),limited_history_skips=skipped,generation_id=gid,
        contract_hash=g['contract_hash'],model_sha256=store.artifact(gid,'model.pkl')['sha256'],
        total_scoring_seconds=time.perf_counter()-started,
        shap_dimensions=('text 0:768, semantic user 768:1536; raw margin' if text_only(g['contract']) else 'text 0:768, poster 768:1536, semantic user 1536:2304; raw margin; no legacy labels reused'))
    store.artifact(gid,'scoring.json',canonical(summary).encode(),dict(contract_hash=g['contract_hash']));store.conn.commit()
    progress(dict(stage='shadow-scoring',expected=len(owners),completed=len(owners),failed=0));return summary
