"""One training/serving feature builder, with target and temporal isolation."""
from collections import defaultdict
from datetime import timedelta
import hashlib
import numpy as np
from .profiles import qualifying_profiles, runtime_seconds
from .contracts import ContractError, FEATURE_VERSION, LABEL_VERSION, cosine, fingerprint, utc, vector, modality_contract
from .recovery import CanonicalTitles, IdentityError, IDENTITY_POLICY
SUPERVISION_POLICY = 'canonical-retrospective-feedback/1.0'
FOUR_STATE_SOURCE_AT = '2026-03-07T18:13:11+00:00'

def feedback_provenance(feedback):
    if feedback is None:
        return 'none'
    return 'predates_four_state_source' if utc(feedback['created_at']) < utc(FOUR_STATE_SOURCE_AT) else 'four_state_era_unverified'

def available(event):
    value = event.get('available_at') or event.get('observed_at')
    return utc(value) if value else None

def history_before(events, owner, target, cutoff, *, excluded_keys=()):
    cutoff = utc(cutoff)
    excluded = {str(target), *map(str, excluded_keys)}
    return [e for e in events if e['username'] == owner and str(e['rating_key']) not in excluded and (available(e) is not None) and (available(e) < cutoff) and (utc(e['watched_at']) < cutoff)]

def cached_vector(row):
    if row.get('_cached_input_hash') != row['input_hash']:
        row['_cached_vector'] = np.asarray(vector(row['embedding']), dtype=np.float64)
        row['_cached_input_hash'] = row['input_hash']
    return row['_cached_vector']

def compatible(row, inputs, kind, *, allow_missing=False):
    hashes = inputs.setdefault('_modality_hash_cache', {})
    if kind not in hashes:
        hashes[kind] = fingerprint(modality_contract(inputs['contract'], kind))
    if row is None or row.get('feature_space_id') != inputs['feature_space_id'] or row.get('kind') != kind or (row.get('status') not in (('succeeded', 'missing') if allow_missing else ('succeeded',))) or (row.get('modality_contract_hash') != hashes[kind]):
        raise ContractError('Mixed/incomplete ' + kind + ' modality inputs')

def profile_inputs(inputs, media, events, owner, cutoff, excluded_keys=(), identity=None):
    """Eligibility-only profile plan: no vectors, IO, or feature recomputation."""
    past = history_before(events, owner, '__no_target__', cutoff, excluded_keys=excluded_keys)
    canonical_past = [dict(e, rating_key=identity.representative(e['rating_key'])) for e in past] if identity else past
    keys = qualifying_profiles(canonical_past, media, inputs['contract']['profile_threshold']).get(owner, [])
    return (past, keys)

class ProfileContext:
    """Reusable per-user/cutoff sums; target subtraction is identical in both paths."""

    def __init__(self, inputs, media, watches, events, owner, cutoff, excluded_keys=(), identity=None):
        self.feature_space_id = inputs['feature_space_id']
        self.owner = owner
        self.cutoff = utc(cutoff)
        self.contract_hash = inputs['contract_hash']
        self.identity = identity or CanonicalTitles(media)
        self.excluded_keys = frozenset(self.identity.expand(excluded_keys) if self.identity else map(str, excluded_keys))
        self.past, self.keys = profile_inputs(inputs, media, events, owner, cutoff, self.excluded_keys, self.identity)
        self.media_sum = np.zeros(768, dtype=np.float64)
        for key in self.keys:
            row = media[key]
            compatible(row, inputs, 'media_text')
            self.media_sum += cached_vector(row)
        self.watch_sum = np.zeros(768, dtype=np.float64)
        self.watch_count = 0
        self.watch_by_title = {}
        self.watch_events = []
        for event in self.past:
            key = str(event['rating_key'])
            runtime = runtime_seconds(media[key]) if key in media else None
            if not runtime or event.get('played_seconds') is None or event['played_seconds'] / runtime < inputs['contract']['watch_threshold']:
                continue
            row = watches.get(str(event['watch_id']))
            compatible(row, inputs, 'watch')
            values = cached_vector(row)
            self.watch_sum += values
            self.watch_count += 1
            if key not in self.watch_by_title:
                self.watch_by_title[key] = [np.zeros(768, dtype=np.float64), 0]
            self.watch_by_title[key][0] += values
            self.watch_by_title[key][1] += 1
            self.watch_events.append((key, [str(event['watch_id']), row['input_hash'], available(event).isoformat()]))

def feature_row(inputs, media, watches, events, owner, target, cutoff, *, excluded_keys=(), context=None, identity=None, dependencies=True):
    """Use only events completed/observed before cutoff, excluding target key.

    For a prospective never-watched candidate, the user half equals its complete
    eligible pre-cutoff mean. Limited history is explicitly skipped, never filled
    with the target vector or an unrelated user's profile.
    """
    target = str(target)
    space = inputs['feature_space_id']
    parent = media[target]
    identity = identity or (context.identity if context else None) or CanonicalTitles(media)
    target_aliases = identity.aliases(target) if identity else {target}
    expected_excluded = frozenset(identity.expand(excluded_keys) if identity else map(str, excluded_keys))
    context = context or ProfileContext(inputs, media, watches, events, owner, cutoff, excluded_keys, identity=identity)
    if context.feature_space_id != space or context.contract_hash != inputs['contract_hash'] or context.owner != owner or (context.cutoff != utc(cutoff)) or (context.excluded_keys != expected_excluded) or (identity and (context.identity is None or context.identity.signature != identity.signature)):
        raise ContractError('Reused profile context does not match inputs/user/cutoff')
    keys = [key for key in context.keys if key not in target_aliases]
    if not keys:
        return None
    compatible(parent, inputs, 'media_text')
    removed_media = sum((cached_vector(media[key]) for key in context.keys if key in target_aliases), np.zeros(768))
    mean = (context.media_sum - removed_media) / len(keys)
    removed = [context.watch_by_title[key] for key in target_aliases if key in context.watch_by_title]
    count = context.watch_count - sum((value[1] for value in removed))
    watch_sum = context.watch_sum - sum((value[0] for value in removed), np.zeros(768))
    watch_sim = cosine(watch_sum / count, parent['embedding']) if count else 0.0
    description = parent['source']['metadata']
    fused = np.concatenate([vector(parent['embedding']), mean]).astype(np.float32)
    if fused.shape != (1536,) or not np.isfinite(fused).all():
        raise ContractError('Invalid text/user feature layout')
    details=None
    if dependencies:
        details = dict(feature_space_id=space, contract_hash=inputs['contract_hash'], cutoff=utc(cutoff).isoformat(), target_excluded=target, profile_keys=keys, media_text_hash=parent['input_hash'], profile_hashes=[[k, media[k]['input_hash']] for k in keys], watch_events=[value for key,value in context.watch_events if key not in target_aliases], feature_version=inputs['contract']['features'])
        if identity:
            details.update(identity_policy=IDENTITY_POLICY, canonical_target=identity.identity(target), target_aliases=sorted(target_aliases), identity_index_hash=identity.signature)
    return dict(owner=owner, media_key=target, embedding=fused, genres=description['genres'] or (description.get('show_context') or {}).get('genres', []), directors=description['directors'], year=description['year'], watch_sim=watch_sim, history_titles=len(keys), media_type=description['media_type'], dependencies=details, show_key=identity.group(target) if identity else str(parent['source'].get('show_rating_key') or target), **dict(canonical_identity=identity.identity(target), identity_policy=IDENTITY_POLICY) if identity else {})

def label_for(events, feedback, runtime, kind, as_of, *, movie_days=21, tv_days=14):
    """Port of active legacy label rules, intentionally retaining 0.60, not 0.70."""
    explicit = {'interested': (1, 0.75, 'explicit_interest'), 'never_watch': (0, 5.0, 'explicit_reject'), 'watched_like': (1, 3.0, 'explicit_watched_like'), 'watched_dislike': (0, 5.0, 'explicit_watched_dislike')}
    if events and (not runtime or runtime <= 0):
        return None
    if feedback and feedback['feedback'] in explicit:
        return explicit[feedback['feedback']]
    if not events:
        return None
    played = [e['played_seconds'] for e in events if e.get('played_seconds') is not None]
    if not played:
        return None
    ratio = sum(played) / runtime
    maximum = max(played)
    weight = min(1.0 + 0.5 * len(played), 5.0)
    if ratio >= 0.6:
        return (1, weight, 'watch_history')
    meaningful = maximum >= 120 and ratio <= 0.35 and (maximum >= 600 or maximum / runtime >= 0.05)
    if meaningful:
        last = max((utc(e['watched_at']) for e in events))
        days = tv_days if kind == 'episode' else movie_days
        if (utc(as_of) - last).days >= days:
            return (0, weight, 'watch_history')
    return None

def unseen_training_candidates(snapshot, media, identity=None):
    """One canonical outcome: recorded watch, intent, or retrospective declaration.

    A declaration without recorded viewing uses submission time, never an
    invented first-viewing date. Recorded viewing takes precedence over watched
    feedback; eligible pre-viewing intent retains its existing label policy.
    """
    identity = identity or CanonicalTitles(media)
    pairs, feedback = (defaultdict(list), defaultdict(list))
    skips = defaultdict(int)
    unresolved = set()
    for field, destination in (('events', pairs), ('feedback', feedback)):
        for row in snapshot[field]:
            try:
                canonical = identity.identity(row['rating_key'])
                identity.group(row['rating_key'])
            except IdentityError:
                unresolved.add((row['username'], str(row['rating_key'])))
                continue
            destination[row['username'], canonical].append(row)
    skips['unresolved_identity'] = len(unresolved)
    candidates = []
    for owner, canonical in sorted(pairs.keys() | feedback.keys()):
        events = pairs[owner, canonical]
        key = identity.preferred[canonical]
        try:
            starts = [utc(e.get('verified_started_at') or e['watched_at']) for e in events]
        except (ContractError, KeyError, ValueError, TypeError):
            skips['unknown_prediction_time'] += 1
            continue
        first = min(starts) if starts else None
        eligible = []
        uncertain_feedback = False
        for row in feedback[owner, canonical]:
            try:
                created = utc(row['created_at'])
                changed = utc(row.get('modified_at') or row['created_at'])
                if changed < created or max(created, changed) > utc(snapshot['as_of']):
                    raise ContractError('Invalid/unavailable feedback timestamp')
            except (ContractError, KeyError, ValueError, TypeError):
                uncertain_feedback = True
                continue
            if first is None and row['feedback'] in ('interested', 'never_watch', 'watched_like', 'watched_dislike'):
                eligible.append(row)
            elif row['feedback'] in ('interested', 'never_watch') and max(created, changed) < first:
                eligible.append(row)
            elif first is not None:
                skips['recorded_watch_feedback_auxiliary'] += 1
        if uncertain_feedback:
            skips['invalid_feedback_time'] += 1
            continue
        f = None
        if eligible:
            latest = max((max(utc(row['created_at']), utc(row.get('modified_at') or row['created_at'])) for row in eligible))
            tied = [row for row in eligible if max(utc(row['created_at']), utc(row.get('modified_at') or row['created_at'])) == latest]
            if len({row['feedback'] for row in tied}) > 1:
                skips['conflicting_latest_feedback'] += 1
                continue
            f = max(tied, key=lambda row: (utc(row['created_at']), str(row['rating_key'])))
        if not events and f is None:
            skips['no_unseen_outcome'] += 1
            continue
        cutoff = first
        if f:
            cutoff = min(cutoff, utc(f['created_at'])) if cutoff else utc(f['created_at'])
        candidates.append((owner, key, events, f, cutoff))
    return (candidates, dict(skips))

def unseen_candidate_keys(media, events, feedback, owner, identity=None, *, quarantined_groups=None):
    """Preserve the existing watched threshold/suppression rules across aliases."""
    identity = identity or CanonicalTitles(media)
    from .eligibility_quarantine import suppression_scope
    scopes = set()
    watched, suppressed = (set(), set())
    for event in events:
        if event['username'] != owner:
            continue
        canonical = identity.identity(event['rating_key'])
        parent = media[str(event['rating_key'])]
        runtime = runtime_seconds(parent)
        percent = event.get('percent_complete')
        ratio = (percent / 100 if percent >= 1 else percent) if percent is not None else 0
        if ratio >= 0.5 or (runtime and event.get('played_seconds') is not None and (event['played_seconds'] / runtime >= 0.5)):
            watched.add(canonical)
    for f in feedback:
        if f['username'] == owner and f.get('suppress') and (f.get('feedback') != 'interested'):
            try:
                suppressed.add(identity.identity(f['rating_key']))
            except IdentityError:
                scopes.add(suppression_scope(identity, f['rating_key']))
    result = []
    for key, row in media.items():
        if row['source']['metadata']['media_type'] not in ('movie', 'episode'):
            continue
        try:
            canonical = identity.identity(key)
            identity.group(key)
        except IdentityError:
            continue
        if key == identity.preferred[canonical] and canonical not in watched | suppressed and (identity.group(key) not in scopes):
            result.append(key)
    if quarantined_groups is not None:
        quarantined_groups.update(scopes)
    return result

def training_plan(inputs, media, identity=None, *, progress=lambda value: None):
    """Shared text-only eligibility/label plan; metadata only, no vectors or IO.

    The actual feature builder and read-only reconciliation consume this same
    plan. Observation/provenance fields are diagnostics, not predictor inputs.
    """
    identity = identity or CanonicalTitles(media)
    snapshot = inputs['snapshot']
    candidates, initial = unseen_training_candidates(snapshot, media, identity)
    skips = defaultdict(int, initial)
    by_owner, feedback = (defaultdict(list), defaultdict(list))
    for event in snapshot['events']:
        by_owner[event['username']].append(event)
    for row in snapshot['feedback']:
        try:
            feedback[row['username'], identity.identity(row['rating_key'])].append(row)
        except IdentityError:
            continue
    rows = []
    for index, (owner, key, events, f, cutoff) in enumerate(candidates):
        if index % 32 == 0:
            progress(dict(stage='historical-features', expected=len(candidates), completed=index, failed=0, phase='canonical eligibility, labels and historical support'))
        parent = media[key]
        kind = parent['source']['metadata']['media_type']
        label = label_for(events, f, runtime_seconds(parent), kind, snapshot['as_of'], movie_days=inputs['contract'].get('movie_revisit_days', 21), tv_days=inputs['contract'].get('tv_revisit_days', 14))
        if label is None:
            skips['label_policy'] += 1
            continue
        if cutoff > utc(snapshot['as_of']):
            skips['future_prediction'] += 1
            continue
        try:
            _, keys = profile_inputs(inputs, media, by_owner[owner], owner, cutoff, identity=identity)
        except IdentityError:
            skips['unresolved_history_identity'] += 1
            continue
        if not set(keys).difference(identity.aliases(key)):
            skips['limited_history'] += 1
            continue
        ends = [available(e) for e in events]
        if any((value is None for value in ends)):
            skips['unknown_label_time'] += 1
            continue
        if f:
            ends.append(max(utc(f['created_at']), utc(f.get('modified_at') or f['created_at'])))
        label_available = max(ends) if ends else cutoff
        if label[0] == 0 and label[2] == 'watch_history' and events:
            days = inputs['contract'].get('tv_revisit_days', 14) if kind == 'episode' else inputs['contract'].get('movie_revisit_days', 21)
            label_available = max(label_available, max((utc(e['watched_at']) for e in events)) + timedelta(days=days))
        if label_available > utc(snapshot['as_of']):
            skips['future_label'] += 1
            continue
        auxiliary = [row for row in feedback[owner, identity.identity(key)] if row is not f]
        watch_label = label_for(events, None, runtime_seconds(parent), kind, snapshot['as_of'], movie_days=inputs['contract'].get('movie_revisit_days', 21), tv_days=inputs['contract'].get('tv_revisit_days', 14))
        conflicts = sum((row['feedback'] in ('watched_like', 'watched_dislike') and watch_label is not None and (watch_label[0] != int(row['feedback'] == 'watched_like')) for row in auxiliary))
        observation = 'retrospective_explicit_feedback' if f and f['feedback'] in ('watched_like', 'watched_dislike') else 'pre_viewing_intent' if f else 'first_recorded_watch'
        rows.append(dict(owner=owner, media_key=key, canonical_identity=identity.identity(key), identity_policy=IDENTITY_POLICY, supervision_policy=SUPERVISION_POLICY, show_key=identity.group(key), label=label[0], sample_weight=label[1], label_source=label[2], prediction_at=cutoff.isoformat(), label_available_at=label_available.isoformat(), label_version=LABEL_VERSION, feedback_value=f['feedback'] if f else None, observation_kind=observation, feedback_provenance=feedback_provenance(f), auxiliary_feedback_count=len(auxiliary), auxiliary_feedback_conflicts=conflicts, played_duration=int(sum((e['played_seconds'] or 0 for e in events))), media_duration=int(runtime_seconds(parent) or 0), engagement_ratio=sum((e['played_seconds'] or 0 for e in events)) / (runtime_seconds(parent) or 1) if events else 0.1 if label[0] else 0.0, season_number=parent['source']['metadata']['season_number'], episode_number=parent['source']['metadata']['episode_number']))
    return (rows, dict(skips))

def planned_text_rows(inputs, media, watches, plan, identity, *, progress=lambda value: None):
    """The shared text row assembly, also usable without retaining dependency graphs."""
    events_by_owner = defaultdict(list)
    for event in inputs['snapshot']['events']:
        events_by_owner[event['username']].append(event)
    for index, fields in enumerate(plan):
        if index % 32 == 0:
            progress(dict(stage='historical-features', expected=len(plan), completed=index, failed=0))
        row = feature_row(inputs, media, watches, events_by_owner[fields['owner']], fields['owner'], fields['media_key'], fields['prediction_at'], identity=identity)
        if row is None:
            raise ContractError('Historical feature support differs from training plan')
        row.update(fields)
        row['dependencies']['supervision_policy'] = SUPERVISION_POLICY
        yield row
    progress(dict(stage='historical-features', expected=len(plan), completed=len(plan), failed=0))

def compact_row(row, media, watches, identity):
    """Check the full dependency graph, keep its exact digest, then release it."""
    dependencies=row.pop('dependencies')
    aliases=identity.aliases(row['media_key'])
    if set(dependencies['profile_keys']) & aliases:
        raise ContractError('Canonical target leaked into profile')
    if any(str(watches[w[0]]['source']['rating_key']) in aliases for w in dependencies['watch_events']):
        raise ContractError('Canonical target leaked into watch similarity')
    row['dependency_hash']=fingerprint(dependencies)
    return row


def training_rows(inputs,media,watches,*,compact=False,progress=lambda value:None):
    identity=CanonicalTitles(media)
    plan,skips=training_plan(inputs,media,identity,progress=progress)
    return [compact_row(row,media,watches,identity) if compact else row for row in planned_text_rows(inputs,media,watches,plan,identity,progress=progress)],skips


class Vocabulary:
    """Fit only on training fold. No direct actor flags, preserving production choice."""

    def __init__(self, genres=(), directors=(), decades=(), include_poster=False):
        self.genres = list(genres)
        self.directors = list(directors)
        self.decades = list(decades)
        if include_poster:raise ContractError('Poster features are unsupported')
        self.include_poster = False

    @classmethod
    def fit(cls, rows, *, include_poster=False):
        counts = defaultdict(int)
        for r in rows:
            for director in set(r['directors']):
                counts[director] += 1
        directors = sorted(counts, key=lambda d: (-counts[d], d))[:20]
        return cls(sorted({g for r in rows for g in r['genres']}), sorted(directors), sorted({int(r['year']) // 10 * 10 for r in rows if r['year'] is not None}), include_poster)

    def specification(self):
        return dict(genres=self.genres, directors=self.directors, decades=self.decades, include_poster=self.include_poster)

    @property
    def names(self):
        return ([f'{group}_{i}' for group in ('media_text','user') for i in range(768)]
            +['genre_'+g for g in self.genres]+['director_'+d for d in self.directors]
            +[f'decade_{d}' for d in self.decades]+['watch_sim'])

    def transform(self,rows):
        values=np.empty((len(rows),len(self.names)),dtype=np.float32)
        for index,row in enumerate(rows):
            data=np.asarray(row['embedding'],dtype=np.float32)
            if data.shape!=(1536,) or not np.isfinite(data).all():
                raise ContractError('Expected exactly 768 text and 768 user coordinates')
            decade=int(row['year'])//10*10 if row['year'] is not None else None
            values[index,:1536]=data
            values[index,1536:]=([int(g in row['genres']) for g in self.genres]
                +[int(d in row['directors']) for d in self.directors]
                +[int(decade==d) for d in self.decades]+[row['watch_sim']])
        return values


def chronological_split(rows):
    identities = [(r.get('owner'), r['canonical_identity']) for r in rows if 'canonical_identity' in r]
    if len(identities) != len(set(identities)):
        raise ContractError('Duplicate canonical user/title outcomes cannot cross evaluation folds')
    if len(rows) < 10:
        raise ContractError('At least 10 historical examples required for evaluation')
    times = sorted((utc(r['prediction_at']) for r in rows))
    boundary = times[min(len(times) - 1, int(len(times) * 0.8))]
    train = [r for r in rows if utc(r['prediction_at']) < boundary and utc(r['label_available_at']) < boundary]
    test = [r for r in rows if utc(r['prediction_at']) >= boundary]
    if not train or not test or {r['label'] for r in train} != {0, 1} or ({r['label'] for r in test} != {0, 1}):
        raise ContractError('Chronological split lacks class/history support; do not substitute random validation')
    return (train, test, boundary)

def show_heldout_plan(inputs, media, rows, *, identity=None, boundary=None):
    """Shared metadata-only fold/support plan for text training and reconciliation."""
    identity = identity or CanonicalTitles(media)
    if boundary is None:
        _, _, boundary = chronological_split(rows)
    groups = sorted({r['show_key'] for r in rows}, key=lambda k: hashlib.sha256(k.encode()).hexdigest())
    heldout = set(groups[:max(1, len(groups) // 5)])
    excluded = set()
    for key in media:
        try:
            if identity.group(key) in heldout:
                excluded.add(key)
        except IdentityError:
            continue
    excluded = identity.expand(excluded)
    by_owner = defaultdict(list)
    for event in inputs['snapshot']['events']:
        by_owner[event['username']].append(event)
    train, test, skips = ([], [], defaultdict(int))
    for row in rows:
        is_test = row['show_key'] in heldout and utc(row['prediction_at']) >= boundary
        is_train = row['show_key'] not in heldout and utc(row['prediction_at']) < boundary and (utc(row['label_available_at']) < boundary)
        if not (is_test or is_train):
            continue
        try:
            _, keys = profile_inputs(inputs, media, by_owner[row['owner']], row['owner'], row['prediction_at'], excluded_keys=excluded, identity=identity)
        except IdentityError:
            skips['unresolved_history_identity'] += 1
            continue
        if not set(keys).difference(identity.aliases(row['media_key'])):
            skips['limited_history'] += 1
            continue
        (test if is_test else train).append(row)
    return (train, test, excluded, dict(skips))
