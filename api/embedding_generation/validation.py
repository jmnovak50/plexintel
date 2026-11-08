"""Full independent-modality verification before any publication."""
import json
import numpy as np
from psycopg2 import sql
from psycopg2.extras import Json

from .contracts import (ContractError,KINDS,REPRESENTATION,canonical,fingerprint,
                        vector,watch_text,modality_contract,embedding_input_hash,text_only)
from .history_scope import partition_history


def validate_generation(store,gid,*,quality_go=False,missing_art_limit=0,progress=lambda value:None):
    from .backfill import qualifying_profiles
    from .model import load_bundle
    generation=store.mutable(gid);spec=generation['contract'];snapshot=generation['snapshot']
    if spec.get('representation')!=REPRESENTATION:raise ContractError('Joint/legacy generation cannot be promoted')
    if fingerprint(partition_history(snapshot))!=fingerprint(snapshot):raise ContractError('Quarantine/coverage mismatch')
    if generation['scope']=='full' and not snapshot['watch_coverage']['existing_vector_coverage_verified']:
        raise ContractError('Existing watch-vector coverage is not verified')
    rows={kind:{r['item_key']:r for r in store.items(gid,kind)} for kind in KINDS}
    media=rows['media_text'];posters=rows['media_poster'];text_mode=text_only(spec)
    expected_media={str(r['rating_key']) for r in snapshot['media']}
    expected_watch={str(e['watch_id']) for e in snapshot['events']}
    events={str(e['watch_id']):e for e in snapshot['events']}
    if set(media)!=expected_media or set(posters)!=(set() if text_mode else expected_media) or set(rows['watch'])!=expected_watch:
        raise ContractError('Eligible media/watch identities are not completely rebuilt')
    if not {str(k) for k in snapshot.get('legacy_watch_ids',[])}.issubset(rows['watch']):
        raise ContractError('Existing watch-vector identity omitted')
    profiles=qualifying_profiles(snapshot['events'],media,spec['profile_threshold'])
    if set(profiles)!=set(rows['user']):raise ContractError('Qualifying-user population mismatch')
    counts=store.counts(gid)
    for kind,count in counts.items():
        accepted=count['succeeded']+(count['missing'] if kind=='media_poster' else 0)
        if count['expected']!=len(rows[kind]) or count['expected']!=accepted or count['pending'] or count['failed']:
            raise ContractError('Incomplete populations: '+canonical(counts))
    completed=0;total=sum(len(r) for r in rows.values());origins={gid:generation}
    all_dependencies=store.query(sql.SQL('SELECT * FROM {} WHERE generation_id=%s').format(store.table('dependencies')),(gid,),many=True)
    dependency_map={}
    for dep in all_dependencies:dependency_map.setdefault((dep['child_kind'],dep['child_key']),[]).append(dep)
    progress(dict(expected=total,completed=0,failed=0,phase='vector/provenance/dependency verification'))
    for kind,population in rows.items():
        contract=modality_contract(spec,kind);contract_hash=fingerprint(contract)
        for key,row in population.items():
            missing=kind=='media_poster' and row['status']=='missing'
            if not missing:vector(row['embedding'],unit=kind!='user')
            elif row['embedding'] is not None:raise ContractError('Missing poster must not have an image vector')
            if not row['input_hash'] or row['generated_at'] is None or row['modality_contract_hash']!=contract_hash:
                raise ContractError('Missing/incompatible modality provenance')
            expected_provenance=dict(**contract,output_dimensions=None if missing else 768,
                normalization_state='missing' if missing else contract['normalization'])
            if row['provenance']!=expected_provenance:raise ContractError('Modality identity/normalization provenance mismatch')
            if row['origin_generation'] not in origins:origins[row['origin_generation']]=store.generation(row['origin_generation'],include_snapshot=False)
            origin=origins[row['origin_generation']]
            if modality_contract(origin['contract'],kind)!=contract or generation['parent_id'] is None and row['origin_generation']!=gid:
                raise ContractError('Legacy/incompatible or non-rebuilt initial vector')
            if kind!='user' and not missing and not (row.get('timing') or {}).get('inherited'):
                if (row.get('timing') or {}).get('model')!='sha256:'+spec['encoder']['digest']:
                    raise ContractError('Missing immutable inference identity')
            expected_deps={}
            if kind=='media_text':
                prep=store.preparation(gid,key,'metadata')
                if not prep or prep['status']!='succeeded' or prep['content_hash']!=row['semantic_hash'] or row['semantic_hash']!=fingerprint(row['source']['metadata']):
                    raise ContractError('Metadata preparation provenance mismatch')
                if row['source'].get('_metadata_recovery'):
                    from .recovery import validate_origin
                    validate_origin(row['source'],key)
                expected_hash=embedding_input_hash(spec,kind,metadata=row['source']['metadata'])
            elif kind=='media_poster':
                prep=store.preparation(gid,key,'poster')
                poster=row['poster'] or {}
                prepared_hash=fingerprint({k:poster.get(k) for k in ('state','content_sha256','preprocessing')})
                if not prep or prep['status']!='succeeded' or prep['content_hash']!=prepared_hash:
                    raise ContractError('Poster preparation provenance mismatch')
                if poster.get('preprocessing')!=spec['image']:raise ContractError('Image preprocessing contract mismatch')
                if (poster.get('state')=='available')==missing or (poster.get('content_sha256') is None)!=missing:
                    raise ContractError('Image/missing-art provenance mismatch')
                expected_hash=embedding_input_hash(spec,kind,poster_hash=prepared_hash)
            elif kind=='watch':
                if (row['source']!=events[key] or row['owner']!=events[key]['username']
                    or row['media_key']!=str(events[key]['rating_key'])):
                    raise ContractError('Watch source/owner differs from the generation snapshot')
                parent=media[row['media_key']]
                expected_hash=embedding_input_hash(spec,kind,text=watch_text(row['source'],parent['source']['metadata']),
                    event_hash=row['semantic_hash'],media_hash=parent['semantic_hash'])
                expected_deps={row['media_key']:parent['semantic_hash']}
            else:
                keys=profiles[key]
                expected_history=fingerprint([e for e in snapshot['events'] if e['username']==key])
                if row['owner']!=key or row['source']['history_hash']!=expected_history:
                    raise ContractError('Semantic profile history/owner provenance mismatch')
                mean=np.mean(np.asarray([vector(media[k]['embedding']) for k in keys],dtype=np.float64),axis=0)
                if row['source']['qualifying_keys']!=keys or not np.allclose(vector(row['embedding']),mean,rtol=1e-6,atol=1e-7):
                    raise ContractError('Semantic user-profile arithmetic mismatch')
                deps=[('media_text',k,media[k]['input_hash']) for k in keys]
                expected_hash=embedding_input_hash(spec,kind,source=row['source'],dependencies=deps)
                expected_deps={k:media[k]['input_hash'] for k in keys}
            if row['input_hash']!=expected_hash:raise ContractError('Modality input hash mismatch')
            deps=dependency_map.get((kind,key),[])
            if any(d['parent_kind']!='media_text' for d in deps) or {d['parent_key']:d['parent_input_hash'] for d in deps}!=expected_deps:
                raise ContractError('Missing/stale modality dependencies')
            completed+=1
            if completed%32==0 or completed==total:progress(dict(expected=total,completed=completed,failed=0,phase='vector/provenance/dependency verification'))
    missing=counts['media_poster']['missing']
    if missing>missing_art_limit:raise ContractError('Explicit missing-art allowance required')
    bundle,_=load_bundle(store,gid)
    dimensions=json.loads(bytes(store.artifact(gid,'dimensions.json')['data']))
    if dimensions['embedding_features']!=bundle['feature_names'][:sum(bundle['dimensions'])] or dimensions['model_sha256']!=store.artifact(gid,'model.pkl')['sha256']:
        raise ContractError('Dimension metadata belongs to a different model/layout')
    quality=store.artifact(gid,'evaluation.json');evaluation=json.loads(bytes(quality['data']))
    if not {'chronological','show_grouped','ablations'}.issubset(evaluation):raise ContractError('Corrected and modality-ablation evaluation required')
    if not text_mode:
        for split in ('chronological','show_grouped'):
            try:
                a=evaluation['ablations']['B_text_only'][split];b=evaluation['ablations']['C_text_poster'][split]
                if a['cohort_hash']!=b['cohort_hash'] or a['rows']!=b['rows']:raise ContractError('Text/image ablations use different evaluation cohorts')
            except KeyError:raise ContractError('Complete text-only and text-plus-poster ablations are required') from None
        if generation['base_generation'] is None and 'paired_controls' not in evaluation:
            raise ContractError('Initial migration requires separate legacy/correction controls')
    else:
        if evaluation.get('model_sha256')!=store.artifact(gid,'model.pkl')['sha256']:
            raise ContractError('Text quality approval/model hash mismatch')
        if bundle.get('adopted_from') and not evaluation.get('selection',{}).get('exact_feature_label_parity'):
            raise ContractError('Adopted B classifier requires exact training feature parity evidence')
    scoring=store.artifact(gid,'scoring.json')
    actual=store.query(sql.SQL('SELECT count(*) AS n FROM {} WHERE generation_id=%s').format(store.table('predictions')),(gid,))['n']
    if json.loads(bytes(scoring['data']))['predictions']!=actual:raise ContractError('Prediction coverage mismatch')
    if not quality_go:raise ContractError('Quality GO decision is required; vector validity alone is insufficient')
    result=dict(counts=counts,watch_coverage=snapshot['watch_coverage'],missing_art=missing,quality_go=True,
        contract_hash=generation['contract_hash'],model_sha256=store.artifact(gid,'model.pkl')['sha256'],
        evaluation_sha256=quality['sha256'],scope=generation['scope'],feature_version=bundle['feature_version'])
    store.query(sql.SQL("UPDATE {} SET validation=%s,status='validated' WHERE generation_id=%s").format(store.table('generations')),(Json(result),gid))
    store.conn.commit();return result
