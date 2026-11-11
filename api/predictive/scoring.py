"""Saved recommendation/SHAP records from one frozen text feature space."""
from datetime import timedelta
from collections import defaultdict
import math
import numpy as np
from .contracts import cosine,utc
from .features import ProfileContext,feature_row,unseen_candidate_keys
from .recovery import CanonicalTitles,IdentityError
from .eligibility_quarantine import profile_exclusions


def shap_targets(predictions,media,policy):
    """Existing movie/show/overall allocations; changes explanations, never ranks.

    TV cards use the mean of their top 20% visible episodes. Store the leading
    episode's explanation, as in the existing score_model selector.
    """
    if policy['scoring.shap_targeting_strategy']=='global':
        return {key for key,_,_ in predictions[:policy['scoring.shap_max_items']]}
    selected=set();shows=defaultdict(list)
    movies=[]
    for item in predictions:
        key,probability,_=item;source=media[key]['source']
        if source['metadata']['media_type']=='movie':movies.append(item)
        elif source['metadata']['media_type']=='episode' and source.get('show_rating_key') is not None:
            shows[str(source['show_rating_key'])].append(item)
    selected.update(key for key,_,_ in movies[:policy['scoring.shap_max_items_movie']])
    ranked=[]
    for items in shows.values():
        top=items[:max(1,math.ceil(len(items)*.2))]
        ranked.append((sum(p for _,p,_ in top)/len(top),items[0]))
    ranked.sort(key=lambda item:(-item[0],-item[1][1],int(item[1][0])))
    selected.update(item[1][0] for item in ranked[:policy['scoring.shap_max_items_tv']])
    remaining=(key for key,_,_ in predictions if key not in selected)
    from itertools import islice
    selected.update(islice(remaining,policy['scoring.shap_max_items_overall']))
    return selected


def raw_shap(values,policy):
    maximum=policy['scoring.shap_raw_max_dims']
    minimum=min(maximum,policy['scoring.shap_raw_min_dims'])
    order=np.argsort(-np.abs(values),kind='stable')
    target=sum(abs(float(values[i])) for i in order)*policy['scoring.shap_raw_cumabs_target']
    cumulative=0.;selected=[]
    for index in order[:maximum]:
        selected.append((int(index),float(values[index])));cumulative+=abs(float(values[index]))
        if len(selected)>=minimum and cumulative>=target:break
    return selected


def score(inputs,media,watches,users,bundle,vocabulary,*,progress=lambda **metrics:None,policy=None):
    import xgboost as xgb
    if policy is None:
        from api.services.app_settings import resolve_settings
        keys=['scoring.shap_'+name for name in ('targeting_strategy','max_items','max_items_overall','max_items_movie','max_items_tv','raw_min_dims','raw_max_dims','raw_cumabs_target')]
        policy={k:v.value for k,v in resolve_settings(keys=keys,require_database=True).items()}
    identity=CanonicalTitles(media);snapshot=inputs['snapshot']
    for number,owner in enumerate(sorted(users),1):
        events=[e for e in snapshot['events'] if e['username']==owner]
        scopes=set()
        try:
            candidates=unseen_candidate_keys(media,events,snapshot['feedback'],owner,identity,quarantined_groups=scopes)
            excluded=profile_exclusions(identity,scopes) if scopes else set()
            cutoff=utc(snapshot['as_of'])+timedelta(microseconds=1)
            context=ProfileContext(inputs,media,watches,events,owner,cutoff,excluded_keys=excluded,identity=identity)
        except IdentityError:
            raise  # Preparation already approved this user; never silently drift.
        predictions=[]
        for start in range(0,len(candidates),128):
            rows=[feature_row(inputs,media,watches,events,owner,key,cutoff,excluded_keys=excluded,
                context=context,identity=identity,dependencies=False) for key in candidates[start:start+128]]
            rows=[r for r in rows if r is not None]
            if rows:
                probability=bundle['model'].predict_proba(vocabulary.transform(rows))[:,1]
                predictions.extend((row['media_key'],float(value),cosine(row['embedding'][:768],row['embedding'][768:]))
                    for row,value in zip(rows,probability))
        predictions.sort(key=lambda pair:(-pair[1],int(pair[0])))
        targets=shap_targets(predictions,media,policy)
        for start in range(0,len(predictions),128):
            part=predictions[start:start+128]
            explain=[item for item in part if item[0] in targets]
            explain_rows=[feature_row(inputs,media,watches,events,owner,key,cutoff,excluded_keys=excluded,
                context=context,identity=identity,dependencies=False) for key,p,c in explain]
            contributions=(bundle['model'].get_booster().predict(xgb.DMatrix(vocabulary.transform(explain_rows),
                feature_names=vocabulary.names,nthread=2),pred_contribs=True) if explain else [])
            by_key={item[0]:contributions[index][:1536] for index,item in enumerate(explain)}
            for offset,(key,probability,similarity) in enumerate(part):
                values=by_key.get(key)
                yield dict(owner=owner,key=int(key),probability=probability,rank=start+offset+1,
                    cosine=similarity,
                    shap=raw_shap(values,policy) if values is not None else [])
        progress(users=number,expected=len(users),predictions=len(predictions))
