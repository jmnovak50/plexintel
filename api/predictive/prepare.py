"""Incremental text vectors and corrected observations, prepared off publication."""
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,time
from uuid import uuid4
import numpy as np
from psycopg2 import sql
from .contracts import ContractError,fingerprint,specification,modality_contract,media_text,watch_text,vector,configured_engagement_thresholds
from .recovery import CanonicalTitles,IdentityError,Resolver,POLICY
from .features import ProfileContext,training_rows,SUPERVISION_POLICY,unseen_candidate_keys
from .eligibility_quarantine import profile_exclusions
from .progress import media_log_fields
from .pending import PendingVectors,checked

TABLES={'media_text':('media_embeddings','rating_key'),'watch':('watch_embeddings','watch_id'),
        'user':('user_embeddings','username')}


def cache(conn,kind):
    table,key=TABLES[kind]
    with conn.cursor(name='predictor_vectors_'+uuid4().hex) as cur:
        cur.execute(sql.SQL('SELECT {}::text,embedding::text,provenance FROM public.{}').format(
            sql.Identifier(key),sql.Identifier(table)))
        rows={}
        while batch:=cur.fetchmany(128):
            for key,values,provenance in batch:
                if key in rows:raise ContractError('Duplicate current-vector source keys')
                rows[key]=dict(provenance=provenance or {},embedding=json.loads(values) if values and provenance else None)
    conn.commit()  # Never hold a read transaction across local encoder requests.
    return rows


def record(spec,kind,key,source,values,input_hash):
    values=vector(values,unit=kind!='user')
    return dict(feature_space_id=fingerprint(spec),kind=kind,status='succeeded',input_hash=input_hash,
        modality_contract_hash=fingerprint(modality_contract(spec,kind)),source=source,embedding=values,
        encoder_digest=spec['encoder']['digest'],vector_sha256=hashlib.sha256(np.asarray(values,dtype='<f4').tobytes()).hexdigest())


def refresh_vector(spec,kind,key,source,text,old,encoder,stats,*,log=None,pending=None,observe=lambda:None):
    digest=fingerprint(dict(contract=modality_contract(spec,kind),text=text))
    contract_hash=fingerprint(modality_contract(spec,kind));encoder_digest=spec['encoder']['digest']
    saved=old.pop(str(key),None)
    values,reason=checked(saved['embedding'] if saved else None,saved['provenance'] if saved else None,
                          digest,contract_hash,encoder_digest)
    if reason is None:
        stats['reused']+=1;stats['published_reused']+=1
        if log:log('reused',cache_source='published')
        return record(spec,kind,key,source,values,digest)
    if reason!='missing':
        stats['published_'+reason]+=1
        if log:log('reuse_rejected',cache_source='published',reason=reason)
    if pending is None:raise ContractError('Durable pending store required before encoder inference')
    started=time.perf_counter()
    values,reason=pending.get(kind,key,digest,contract_hash,encoder_digest)
    stats['pending_lookup_seconds']+=time.perf_counter()-started
    if reason is None:
        stats['reused']+=1;stats['pending_reused']+=1
        if log:log('pending_reused')
        return record(spec,kind,key,source,values,digest)
    if reason!='missing':
        stats['pending_'+reason]+=1
        if log:log('reuse_rejected',cache_source='pending',reason=reason)
    if log:log('embedding',reason='No compatible valid published or pending vector')
    try:
        values=vector(encoder.embed(text),unit=True);stats['inferred']+=1
    except Exception as exc:
        if log:log('embedding_failed',error_type=type(exc).__name__)
        raise
    if log:log('inference_completed',inferred=stats['inferred'],durably_persisted=stats['durably_persisted'])
    observe()
    result=record(spec,kind,key,source,values,digest)
    started=time.perf_counter()
    try:
        pending.save(kind,key,result)
    except Exception as exc:
        if log:log('persistence_failed',error_type=type(exc).__name__)
        raise
    finally:stats['persistence_seconds']+=time.perf_counter()-started
    stats['durably_persisted']+=1
    if log:log('embedded',durably_persisted=True)
    return result


def prepare(conn,snapshot,plex,encoder,associations,*,allow_stored_history=False,policy=None,progress=lambda stage,**metrics:None,log=None,pending=None):
    if pending is None:
        pending=PendingVectors(conn);pending.require_schema()
    spec=specification(encoder.identity,policy=policy)
    spec.update(identity_policy='verified-canonical-unseen-title/1.0',supervision_policy=SUPERVISION_POLICY)
    inputs=dict(contract=spec,contract_hash=fingerprint(spec),feature_space_id=fingerprint(spec),snapshot=snapshot,
        label_thresholds=configured_engagement_thresholds(policy))
    sources={str(row['rating_key']):row for row in snapshot['media']}
    resolver=Resolver(plex,sources,associations)
    resolver.catalog=[];revisions={}
    for row in plex.catalog():
        resolver.catalog.append({k:row.get(k) for k in ('ratingKey','type','guid','parentRatingKey','index')})
        if row.get('updatedAt') is not None:
            revisions[str(row['ratingKey'])]=fingerprint({k:row.get(k) for k in
                ('updatedAt','guid','type','parentRatingKey','grandparentRatingKey')})
    started=time.monotonic()
    progress('media_text',completed=0,expected=len(sources))
    old=cache(conn,'media_text');media={};stats=Counter(published_reused=0,pending_reused=0,inferred=0,durably_persisted=0)
    for key,source in sources.items():
        previous=(old.get(key) or {}).get('provenance',{}).get('source',{})
        revision_keys=previous.get('_revision_keys',[])
        known=revision_keys and all(k in revisions for k in revision_keys)
        signature=fingerprint(dict(source=source,revisions=[(k,revisions[k]) for k in revision_keys])) if known else None
        if signature and previous.get('_revision')==signature:
            source=previous
        else:
            value,_,origin=resolver.payload(source)
            if not allow_stored_history and any(c['source']=='stored-library' for c in origin['components'].values()):
                raise ContractError('Stored-only descriptive recovery needs explicit --allow-stored-history approval')
            revision_keys=sorted({str(c['resolved_key']) for c in origin['components'].values() if c.get('resolved_key')})
            base_source=source
            source=dict(source)
            source.update(metadata=value,metadata_origin=origin,
                _metadata_recovery=dict(policy=POLICY,reason='Verified live identity recovery; stored history only when explicitly allowed',
                    approved_at=snapshot['as_of']),_revision_keys=revision_keys)
            source['_revision']=(fingerprint(dict(source=base_source,revisions=[(k,revisions[k]) for k in revision_keys]))
                                 if revision_keys and all(k in revisions for k in revision_keys) else None)
        item_log=(lambda operation,**fields:log('media_text',operation,**media_log_fields(key,source),**fields)) if log else None
        media[key]=refresh_vector(spec,'media_text',key,source,media_text(source['metadata']),old,encoder,stats,log=item_log,pending=pending,
            observe=lambda:progress('media_text',completed=len(media),expected=len(sources),**stats))
        progress('media_text',completed=len(media),expected=len(sources),**stats)
    progress('media_text',seconds=time.monotonic()-started,pending_retained=pending.population('media_text'))
    identity=CanonicalTitles(media)
    started=time.monotonic()
    progress('watch',completed=0,expected=len(snapshot['events']))
    old=cache(conn,'watch');watches={};stats=Counter(published_reused=0,pending_reused=0,inferred=0,durably_persisted=0)
    for event in snapshot['events']:
        key=str(event['rating_key']);watch=str(event['watch_id'])
        if key not in media:raise ContractError('Unscoped watch event: quarantine before preparation')
        # Existing watch reuse stays aggregate; report new/pending/rejected work with its actual title.
        item_log=(lambda operation,**fields:log('watch',operation,**media_log_fields(key,media[key]['source']),**fields)
                  if operation!='reused' else None) if log else None
        watches[watch]=refresh_vector(spec,'watch',watch,event,watch_text(event,media[key]['source']['metadata']),old,encoder,stats,
            log=item_log,pending=pending,observe=lambda:progress('watch',completed=len(watches),expected=len(snapshot['events']),**stats))
        progress('watch',completed=len(watches),expected=len(snapshot['events']),**stats)
    progress('watch',seconds=time.monotonic()-started,pending_retained=pending.population('watch'))
    started=time.monotonic()
    progress('users',users=0)
    users={};blocked=0
    for owner in sorted({e['username'] for e in snapshot['events']}):
        events=[e for e in snapshot['events'] if e['username']==owner]
        try:
            scopes=set();unseen_candidate_keys(media,events,snapshot['feedback'],owner,identity,quarantined_groups=scopes)
            excluded=profile_exclusions(identity,scopes) if scopes else set()
            context=ProfileContext(inputs,media,watches,events,owner,snapshot['as_of'],excluded_keys=excluded,identity=identity)
        except IdentityError:
            blocked+=1;continue
        if not context.keys:continue
        mean=context.media_sum/len(context.keys)
        source=dict(profile_keys=context.keys,hashes=[[k,media[k]['input_hash']] for k in context.keys],identity_policy=spec['identity_policy'])
        digest=fingerprint(dict(contract=modality_contract(spec,'user'),source=source))
        users[owner]=record(spec,'user',owner,source,mean,digest)
    progress('users',users=len(users),quarantined=blocked,seconds=time.monotonic()-started)
    started=time.monotonic()
    progress('training_data',completed=0)
    rows,skips=training_rows(inputs,media,watches,compact=True,progress=lambda item:progress('training_data',**{k:v for k,v in item.items() if k!='stage'}))
    if not rows:raise ContractError('No leakage-safe training observations')
    identities=[(r['owner'],r['canonical_identity']) for r in rows]
    if len(identities)!=len(set(identities)):raise ContractError('Duplicate canonical training outcome')
    summary=dict(label_thresholds=inputs['label_thresholds'],rows=len(rows),positive=sum(r['label'] for r in rows),negative=sum(1-r['label'] for r in rows),skips=skips,
        sources=dict(Counter(r['label_source'] for r in rows)),observations=dict(Counter(r['observation_kind'] for r in rows)),
        provenance=dict(Counter(r['feedback_provenance'] for r in rows)),blocked_users=blocked,
        historical_metadata='Current descriptive snapshot, not a point-in-time metadata replay',
        watch_coverage=snapshot.get('watch_coverage'))
    # Hash complete numeric vectors + relevant diagnostics; no private row manifest in normal logs.
    summary['dataset_hash']=fingerprint([dict(identity=fingerprint([r['owner'],r['canonical_identity']]),
        vector=hashlib.sha256(np.asarray(r['embedding'],dtype='<f4').tobytes()).hexdigest(),
        fields={k:r[k] for k in ('label','sample_weight','prediction_at','label_available_at','watch_sim','label_source',
                                  'observation_kind','feedback_provenance','genres','directors','year')}) for r in rows])
    progress('training_data',rows=len(rows),completed=len(rows),expected=len(rows),seconds=time.monotonic()-started)
    return inputs,media,watches,users,rows,summary
