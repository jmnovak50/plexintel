"""One training/serving feature builder, with target and temporal isolation."""
from collections import defaultdict
from datetime import timedelta
import numpy as np

from .backfill import qualifying_profiles, runtime_seconds
from .contracts import (ContractError, FEATURE_VERSION, LABEL_VERSION, cosine,
                        fingerprint, utc, vector, modality_contract)


def available(event):
    value=event.get('available_at') or event.get('observed_at')
    return utc(value) if value else None


def history_before(events, owner, target, cutoff, *, excluded_keys=()):
    cutoff=utc(cutoff)
    excluded={str(target),*map(str,excluded_keys)}
    return [e for e in events if e['username']==owner and str(e['rating_key']) not in excluded
            and available(e) is not None and available(e)<cutoff
            and utc(e['watched_at'])<cutoff]


def cached_vector(row):
    if row.get('_cached_input_hash')!=row['input_hash']:
        row['_cached_vector']=np.asarray(vector(row['embedding']),dtype=np.float64)
        row['_cached_input_hash']=row['input_hash']
    return row['_cached_vector']


def compatible(row,generation,kind,*,allow_missing=False):
    hashes=generation.setdefault('_modality_hash_cache',{})
    if kind not in hashes:hashes[kind]=fingerprint(modality_contract(generation['contract'],kind))
    if (row is None or row.get('generation_id')!=generation['generation_id'] or row.get('kind')!=kind
        or row.get('status') not in (('succeeded','missing') if allow_missing else ('succeeded',))
        or row.get('modality_contract_hash')!=hashes[kind]):
        raise ContractError('Mixed/incomplete '+kind+' modality inputs')


class ProfileContext:
    """Reusable per-user/cutoff sums; target subtraction is identical in both paths."""
    def __init__(self,generation,media,watches,events,owner,cutoff,excluded_keys=()):
        self.generation_id=generation['generation_id'];self.owner=owner;self.cutoff=utc(cutoff)
        self.contract_hash=generation['contract_hash']
        self.excluded_keys=frozenset(map(str,excluded_keys))
        self.past=history_before(events,owner,'__no_target__',cutoff,excluded_keys=excluded_keys)
        self.keys=qualifying_profiles(self.past,media,generation['contract']['profile_threshold']).get(owner,[])
        self.media_sum=np.zeros(768,dtype=np.float64)
        for key in self.keys:
            row=media[key]
            compatible(row,generation,'media_text')
            self.media_sum+=cached_vector(row)
        self.watch_sum=np.zeros(768,dtype=np.float64);self.watch_count=0
        self.watch_by_title={};self.watch_events=[]
        for event in self.past:
            key=str(event['rating_key']);runtime=runtime_seconds(media[key]) if key in media else None
            if not runtime or event.get('played_seconds') is None or event['played_seconds']/runtime<generation['contract']['watch_threshold']:continue
            row=watches.get(str(event['watch_id']))
            compatible(row,generation,'watch')
            values=cached_vector(row);self.watch_sum+=values;self.watch_count+=1
            if key not in self.watch_by_title:self.watch_by_title[key]=[np.zeros(768,dtype=np.float64),0]
            self.watch_by_title[key][0]+=values;self.watch_by_title[key][1]+=1
            self.watch_events.append((key,[str(event['watch_id']),row['input_hash'],available(event).isoformat()]))


def feature_row(generation,media,watches,events,owner,target,cutoff,*,posters=None,excluded_keys=(),context=None):
    """Use only events completed/observed before cutoff, excluding target key.

    For a prospective never-watched candidate, the user half equals its complete
    eligible pre-cutoff mean. Limited history is explicitly skipped, never filled
    with the target vector or an unrelated user's profile.
    """
    target=str(target)
    gid=generation['generation_id']
    parent=media[target]
    context=context or ProfileContext(generation,media,watches,events,owner,cutoff,excluded_keys)
    if (context.generation_id!=gid or context.contract_hash!=generation['contract_hash'] or context.owner!=owner
        or context.cutoff!=utc(cutoff) or context.excluded_keys!=frozenset(map(str,excluded_keys))):
        raise ContractError('Reused profile context does not match generation/user/cutoff')
    keys=[key for key in context.keys if key!=target]
    if not keys:return None
    compatible(parent,generation,'media_text')
    mean=(context.media_sum-(cached_vector(parent) if target in context.keys else 0))/len(keys)
    removed=context.watch_by_title.get(target,[0,0])
    count=context.watch_count-removed[1]
    watch_sim=cosine((context.watch_sum-removed[0])/count,parent['embedding']) if count else 0.
    used_events=[value for key,value in context.watch_events if key!=target]
    description=parent['source']['metadata']
    poster=posters.get(target) if posters is not None else None
    if poster is None:raise ContractError('Explicit poster availability row is required')
    compatible(poster,generation,'media_poster',allow_missing=True)
    missing=poster['status']=='missing'
    if missing and poster['embedding'] is not None:raise ContractError('Missing poster must not contain an image vector')
    image=np.full(768,np.nan) if missing else np.asarray(vector(poster['embedding']))
    fused=np.concatenate([vector(parent['embedding']),image,mean]).astype(np.float32)
    if fused.shape!=(2304,) or not np.isfinite(fused[:768]).all() or not np.isfinite(fused[1536:]).all():
        raise ContractError('Invalid text/poster/semantic-user feature layout')
    dependencies=dict(generation_id=gid,contract_hash=generation['contract_hash'],cutoff=utc(cutoff).isoformat(),
        target_excluded=target,profile_keys=keys,
        media_text_hash=parent['input_hash'],media_poster_hash=poster['input_hash'],
        profile_hashes=[[k,media[k]['input_hash']] for k in keys],
        watch_events=used_events,feature_version=FEATURE_VERSION)
    return dict(owner=owner,media_key=target,embedding=fused,
        genres=description['genres'] or (description.get('show_context') or {}).get('genres',[]),
        directors=description['directors'],year=description['year'],
        watch_sim=watch_sim,poster_missing=missing,history_titles=len(keys),
        media_type=description['media_type'],dependencies=dependencies,
        show_key=str(parent['source'].get('show_rating_key') or target))


def label_for(events,feedback,runtime,kind,as_of,*,movie_days=21,tv_days=14):
    """Port of active legacy label rules, intentionally retaining 0.60, not 0.70."""
    explicit={'interested':(1,.75,'explicit_interest'),'never_watch':(0,5.,'explicit_reject'),
              'watched_like':(1,3.,'explicit_watched_like'),'watched_dislike':(0,5.,'explicit_watched_dislike')}
    if events and (not runtime or runtime<=0):return None
    if feedback and feedback['feedback'] in explicit:
        return explicit[feedback['feedback']]
    if not events:return None
    played=[e['played_seconds'] for e in events if e.get('played_seconds') is not None]
    if not played:return None
    ratio=sum(played)/runtime
    maximum=max(played)
    weight=min(1.+.5*len(played),5.)
    if ratio>=.60:return 1,weight,'watch_history'
    meaningful=maximum>=120 and ratio<=.35 and (maximum>=600 or maximum/runtime>=.05)
    if meaningful:
        last=max(utc(e['watched_at']) for e in events)
        days=tv_days if kind=='episode' else movie_days
        if (utc(as_of)-last).days>=days:return 0,weight,'watch_history'
    return None


def training_rows(generation,media,watches,posters,*,progress=lambda value:None):
    snapshot=generation['snapshot']
    events=snapshot['events']
    events_by_owner=defaultdict(list)
    for event in events:events_by_owner[event['username']].append(event)
    pairs=defaultdict(list)
    for event in events:
        if event.get('played_seconds') is not None:pairs[(event['username'],str(event['rating_key']))].append(event)
    feedback={(r['username'],str(r['rating_key'])):r for r in snapshot['feedback']}
    pairs.update({key:[] for key in feedback if key not in pairs})
    rows=[];skips=defaultdict(int)
    for index,((owner,key),target_events) in enumerate(sorted(pairs.items())):
        if index%32==0:progress(dict(stage='historical-features',expected=len(pairs),completed=index,failed=0,phase='candidate labels/profiles'))
        if key not in media:
            skips['missing_media']+=1;continue
        parent=media[key]
        f=feedback.get((owner,key))
        label=label_for(target_events,f,runtime_seconds(parent),parent['source']['metadata']['media_type'],snapshot['as_of'],
            movie_days=generation['contract'].get('movie_revisit_days',21),tv_days=generation['contract'].get('tv_revisit_days',14))
        if label is None:
            skips['label_policy']+=1;continue
        first=[utc(e.get('verified_started_at') or e['watched_at']) for e in target_events]
        if f and f.get('created_at'):first.append(utc(f['created_at']))
        if not first:
            skips['unknown_prediction_time']+=1;continue
        cutoff=min(first)
        result=feature_row(generation,media,watches,events_by_owner[owner],owner,key,cutoff,posters=posters)
        if result is None:
            skips['limited_history']+=1;continue
        ends=[available(e) for e in target_events]
        if any(v is None for v in ends):
            skips['unknown_label_time']+=1;continue
        if f and f.get('modified_at'):ends.append(utc(f['modified_at']))
        label_available=max(ends) if ends else cutoff
        if label[0]==0 and label[2]=='watch_history' and target_events:
            days=generation['contract'].get('tv_revisit_days',14) if parent['source']['metadata']['media_type']=='episode' else generation['contract'].get('movie_revisit_days',21)
            label_available=max(label_available,max(utc(e['watched_at']) for e in target_events)+timedelta(days=days))
        if label_available>utc(snapshot['as_of']):
            skips['future_label']+=1;continue
        result.update(label=label[0],sample_weight=label[1],label_source=label[2],
            prediction_at=cutoff.isoformat(),label_available_at=label_available.isoformat(),
            label_version=LABEL_VERSION,feedback_value=f['feedback'] if f else None,
            played_duration=int(sum(e['played_seconds'] or 0 for e in target_events)),
            media_duration=int(runtime_seconds(parent) or 0),
            engagement_ratio=(sum(e['played_seconds'] or 0 for e in target_events)/(runtime_seconds(parent) or 1)
                              if target_events else .1 if label[0] else 0.),
            season_number=parent['source']['metadata']['season_number'],
            episode_number=parent['source']['metadata']['episode_number'])
        rows.append(result)
    progress(dict(stage='historical-features',expected=len(pairs),completed=len(pairs),failed=0))
    return rows,dict(skips)


class Vocabulary:
    """Fit only on training fold. No direct actor flags, preserving production choice."""
    def __init__(self,genres=(),directors=(),decades=(),include_poster=True):
        self.genres=list(genres);self.directors=list(directors);self.decades=list(decades)
        self.include_poster=include_poster

    @classmethod
    def fit(cls,rows,*,include_poster=True):
        counts=defaultdict(int)
        for r in rows:
            for director in set(r['directors']):counts[director]+=1
        directors=sorted(counts,key=lambda d:(-counts[d],d))[:20]
        return cls(sorted({g for r in rows for g in r['genres']}),sorted(directors),
                   sorted({int(r['year'])//10*10 for r in rows if r['year'] is not None}),include_poster)

    def specification(self):
        return dict(genres=self.genres,directors=self.directors,decades=self.decades,include_poster=self.include_poster)

    @property
    def names(self):
        groups=['media_text']+(['media_poster'] if self.include_poster else [])+['user']
        return ([f'{group}_{i}' for group in groups for i in range(768)]+['genre_'+g for g in self.genres]
            +['director_'+d for d in self.directors]+[f'decade_{d}' for d in self.decades]+['watch_sim']
            +(['poster_missing'] if self.include_poster else []))

    def transform(self,rows):
        values=[]
        for r in rows:
            if len(r['embedding'])!=2304:raise ContractError('Feature width mismatch')
            data=np.asarray(r['embedding'],dtype=np.float32)
            if (not np.isfinite(data[:768]).all() or not np.isfinite(data[1536:]).all()
                or (not np.isnan(data[768:1536]).all() if r['poster_missing'] else not np.isfinite(data[768:1536]).all())):
                raise ContractError('Invalid missing-modality feature policy')
            embedding=list(data if self.include_poster else np.concatenate([data[:768],data[1536:]]))
            decade=int(r['year'])//10*10 if r['year'] is not None else None
            values.append(embedding+[int(g in r['genres']) for g in self.genres]
                +[int(d in r['directors']) for d in self.directors]+[int(decade==d) for d in self.decades]+[r['watch_sim']]
                +([int(r['poster_missing'])] if self.include_poster else []))
        return np.asarray(values,dtype=np.float32).reshape(len(rows),len(self.names))


def chronological_split(rows):
    if len(rows)<10:raise ContractError('At least 10 historical examples required for evaluation')
    times=sorted(utc(r['prediction_at']) for r in rows)
    boundary=times[min(len(times)-1,int(len(times)*.8))]
    train=[r for r in rows if utc(r['prediction_at'])<boundary and utc(r['label_available_at'])<boundary]
    test=[r for r in rows if utc(r['prediction_at'])>=boundary]
    if not train or not test or {r['label'] for r in train}!={0,1} or {r['label'] for r in test}!={0,1}:
        raise ContractError('Chronological split lacks class/history support; do not substitute random validation')
    return train,test,boundary
