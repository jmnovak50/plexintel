"""One decision budget over existing leaf outcomes; no persistence or inference."""
from collections import Counter, defaultdict
from uuid import UUID

from .contracts import ContractError, fingerprint, utc

POLICY = 'explicit-decision-support/1.0'
PROVENANCE = 'plexintel.feedback-decision/1'
BASE_WEIGHTS = {'interested': .75, 'never_watch': 5., 'watched_like': 3., 'watched_dislike': 5.}
EXPLICIT = {'explicit_interest': 'interested', 'explicit_reject': 'never_watch',
            'explicit_watched_like': 'watched_like', 'explicit_watched_dislike': 'watched_dislike'}


class AttributionRequired(ContractError):
    def __init__(self, issues, reliable_rows):
        self.supervision_audit = dict(policy=POLICY, ambiguous_outcomes=len(issues),
            by_reason=dict(Counter(i['reason'] for i in issues)),
            reliable_outcomes=len(reliable_rows), publication_allowed=False)
        # Private qualification only; these are never serialized into worker logs.
        self.issues, self.reliable_rows = issues, reliable_rows
        super().__init__(f'{len(issues)} explicit feedback outcomes require reliable decision attribution; nothing published')


def decision_for(feedback, owner, key, media, identity):
    """Recover no hierarchy from timing or a generic source marker."""
    origin = feedback.get('decision_provenance')
    if origin is None:
        # A movie cannot be a descendant of the supported show/season expansion.
        if media[key]['source']['metadata']['media_type'] != 'movie' or feedback.get('id') is None:
            raise ContractError('historical_episode_origin_unavailable')
        return dict(id='legacy-movie:'+fingerprint([owner,feedback['id'],feedback['created_at'],feedback.get('modified_at'),feedback['feedback']]),
            kind='legacy-single-movie', target_identity=identity.identity(key), target_scope='movie',
            time_basis='retained_effective_row', time=feedback['created_at'])
    if not isinstance(origin, dict) or origin.get('version') != PROVENANCE:
        raise ContractError('invalid_decision_provenance')
    try: UUID(origin['id'])
    except (KeyError, ValueError, TypeError, AttributeError): raise ContractError('invalid_decision_identity') from None
    if origin.get('action') != feedback['feedback'] or origin.get('username') != owner:
        raise ContractError('decision_owner_or_action_mismatch')
    scope=origin.get('target_scope');target=origin.get('target_identity')
    if not target or scope not in ('movie','episode','season','show'):
        raise ContractError('unresolved_original_target')
    actual=identity.identity(key);src=media[key]['source']
    if scope in ('movie','episode'): expected=actual
    elif scope=='show': expected=identity.group(key)
    else: expected=identity.identity(str(src.get('parent_rating_key')))
    if target != expected or not target.startswith(scope+':'):
        raise ContractError('decision_target_mismatch')
    if origin.get('kind') == 'captured':
        stamp=utc(origin['occurred_at'])
        if stamp > max(utc(feedback['created_at']),utc(feedback.get('modified_at') or feedback['created_at'])):
            raise ContractError('decision_time_after_effective_feedback')
        basis='captured_action_time'
    elif origin.get('kind') == 'operator-confirmed':
        # Exact original time was never retained. Preserve that unknown instead
        # of inventing a date; existing row times remain causal bounds.
        if origin.get('occurred_at') is not None or not origin.get('evidence_sha256'):
            raise ContractError('recovered_decision_requires_explicit_evidence')
        interval=origin.get('derived_interval') or {}
        first,last=utc(interval['first']),utc(interval['last'])
        if not first <= utc(feedback['created_at']) <= last:
            raise ContractError('recovered_decision_time_outside_evidence')
        stamp=last;basis='latest_retained_derived_time_not_original_action_time'
    else: raise ContractError('unknown_decision_provenance_kind')
    return dict(id=origin['id'],kind=origin['kind'],target_identity=target,target_scope=scope,
                time_basis=basis,time=stamp.isoformat(),evidence_sha256=origin.get('evidence_sha256'))


def unit_key(row):
    if row.get('label_source') in EXPLICIT:
        if not row.get('feedback_decision'):
            raise ContractError('Explicit supervision lacks original decision identity')
        return ('decision',row['owner'],row['feedback_decision']['id'])
    return ('observation',row['owner'],row.get('canonical_identity') or row['media_key'])


def allocate(rows):
    """Normalize after effective precedence/eligibility, independently per fit."""
    identities=[(r['owner'],r.get('canonical_identity') or r['media_key']) for r in rows]
    if len(identities)!=len(set(identities)):
        raise ContractError('Duplicate canonical descendant supervision')
    groups=defaultdict(list)
    for r in rows: groups[unit_key(r)].append(r)
    result=[]
    for key,items in groups.items():
        explicit=key[0]=='decision'
        if explicit:
            if len({(r['label'],r['label_source']) for r in items})!=1:
                raise ContractError('One decision has contradictory supervision')
            if len({fingerprint(r['feedback_decision']) for r in items})!=1:
                raise ContractError('Decision provenance disagrees across descendants')
            if len({r.get('canonical_identity') or r['media_key'] for r in items})!=len(items):
                raise ContractError('Duplicate canonical descendant supervision')
            base=BASE_WEIGHTS[EXPLICIT[items[0]['label_source']]]
            for r in items:
                supplied=r.get('feedback_base_weight',base)
                if supplied != base: raise ContractError('Feedback base weight changed')
        else:
            if len(items)!=1: raise ContractError('Duplicate independent observation')
        for r in items:
            support=1./len(items) if explicit else 1.
            result.append(dict(r,supervision_weighting=POLICY,decision_support=support,
                sample_weight=base*support if explicit else r['sample_weight'],
                **(dict(feedback_base_weight=base) if explicit else {})))
    lookup={(r['owner'],r.get('canonical_identity') or r['media_key']):r for r in result}
    return [lookup[(r['owner'],r.get('canonical_identity') or r['media_key'])] for r in rows]


def support(rows):
    normalized=allocate(rows)
    return dict(physical_rows=len(rows),decision_equivalent=sum(r['decision_support'] for r in normalized),
        positive=sum(r['decision_support'] for r in normalized if r['label']==1),
        negative=sum(r['decision_support'] for r in normalized if r['label']==0))


def fit_weights(rows, *, legacy=False):
    import numpy as np
    y=np.asarray([r['label'] for r in rows])
    if legacy:
        base=np.asarray([r.get('feedback_base_weight',r['sample_weight']) for r in rows],dtype=float)
        ratio=float((y==1).sum()/(y==0).sum())
    else:
        rr=allocate(rows);base=np.asarray([r['sample_weight'] for r in rr],dtype=float)
        units=np.asarray([r['decision_support'] for r in rr],dtype=float)
        ratio=float(units[y==1].sum()/units[y==0].sum())
    return base*np.where(y==0,ratio,1.)


def atomic_split(rows):
    groups=defaultdict(list)
    for r in rows:groups[unit_key(r)].append(r)
    if len(groups)<10:raise ContractError('At least 10 decision-equivalent observations required')
    starts=sorted(min(utc(r['prediction_at']) for r in rr) for rr in groups.values())
    boundary=starts[min(len(starts)-1,int(len(starts)*.8))]
    train=[];test=[]
    for rr in groups.values():
        first=min(utc(r['prediction_at']) for r in rr);last=max(utc(r['prediction_at']) for r in rr)
        if first>=boundary:test.extend(rr)
        elif last<boundary:
            train.extend(r for r in rr if utc(r['label_available_at'])<boundary)
        # A group spanning the boundary is purged, never split or moved back.
    train_ids={id(r) for r in train};test_ids={id(r) for r in test}
    return [r for r in rows if id(r) in train_ids],[r for r in rows if id(r) in test_ids],boundary
