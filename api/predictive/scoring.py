"""Saved recommendation/SHAP records from one frozen text feature space."""
from datetime import timedelta
import numpy as np
from .contracts import cosine,utc
from .features import ProfileContext,feature_row,unseen_candidate_keys
from .recovery import CanonicalTitles,IdentityError
from .eligibility_quarantine import profile_exclusions


def score(inputs,media,watches,users,bundle,vocabulary,*,progress=lambda **metrics:None):
    import xgboost as xgb
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
                context=context,identity=identity) for key in candidates[start:start+128]]
            rows=[r for r in rows if r is not None]
            if rows:
                probability=bundle['model'].predict_proba(vocabulary.transform(rows))[:,1]
                predictions.extend((row,float(value)) for row,value in zip(rows,probability))
        predictions.sort(key=lambda pair:(-pair[1],int(pair[0]['media_key'])))
        for start in range(0,len(predictions),128):
            part=predictions[start:start+128]
            explain=part[:max(0,750-start)]
            contributions=(bundle['model'].get_booster().predict(xgb.DMatrix(vocabulary.transform([r for r,p in explain]),
                feature_names=vocabulary.names,nthread=2),pred_contribs=True) if explain else [])
            for offset,(row,probability) in enumerate(part):
                values=contributions[offset][:1536] if offset<len(contributions) else []
                indices=np.argsort(-np.abs(values),kind='stable')[:40]
                yield dict(owner=owner,key=int(row['media_key']),probability=probability,rank=start+offset+1,
                    cosine=cosine(row['embedding'][:768],row['embedding'][768:]),
                    shap=[(int(i),float(values[i])) for i in indices])
        progress(users=number,expected=len(users),predictions=len(predictions))
