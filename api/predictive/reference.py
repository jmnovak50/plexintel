"""Refit the pinned published population without exposing the current holdout.

This is a release comparison on shared evaluation observations, not a claim that
an all-data serving model had an independent held-out score.
"""
from psycopg2.extras import RealDictCursor
from .contracts import ContractError, fingerprint, utc
from .features import feature_row, compact_row
from .supervision import EXPLICIT, POLICY, BASE_WEIGHTS, unit_key, allocate


def published_reference(conn, config):
    if not config:return None
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT username,rating_key,label,sample_weight,label_source,feedback_value,diagnostics FROM public.training_data ORDER BY id')
        rows=[dict(row) for row in cur]
    expected=config.get('dataset_summary',{}).get('rows')
    if expected is None or len(rows)!=expected:
        raise ContractError('Published incumbent training population is incomplete')
    return dict(config=config, rows=rows)


def reference_fit(reference, inputs, media, watches, current_rows, boundary, excluded, identity, heldout):
    config=reference['config']
    if config.get('feature_space_id')!=inputs['feature_space_id'] or config.get('contract_hash')!=inputs['contract_hash']:
        raise ContractError('Comparable reference requires the same feature/encoder contract')
    recipe=dict(seed=42,threshold=.5,n_estimators=100,max_depth=6,learning_rate=.1,subsample=.8,n_jobs=2)
    if config.get('fit_settings')!=recipe:
        raise ContractError('Incumbent fit settings cannot be reproduced by the current recipe')
    old_policy=config.get('supervision_weighting')
    if old_policy not in (None,POLICY):raise ContractError('Unknown incumbent weighting recipe')
    lookup={(r['owner'],r['canonical_identity']):r for r in current_rows}
    forbidden={unit_key(r) for r in heldout}
    forbidden_pairs={(r['owner'],r['canonical_identity']) for r in heldout}
    fitted=[];excluded_count=0;limited_history=0
    for original in reference['rows']:
        d=original['diagnostics'] or {};key=str(original['rating_key']);owner=original['username']
        # Exclusion of all aliases precedes profile reconstruction.
        if key in excluded:excluded_count+=1;continue
        if utc(d['prediction_at'])>=boundary or utc(d['label_available_at'])>=boundary:continue
        if key not in media:raise ContractError('Incumbent fit target unavailable in comparable feature snapshot')
        canonical=identity.identity(key)
        if d.get('canonical_identity')!=canonical:
            raise ContractError('Incumbent target canonical identity changed')
        if (owner,canonical) in forbidden_pairs:continue
        row=dict(owner=owner,media_key=key,canonical_identity=canonical,label=original['label'],
            sample_weight=original['sample_weight'],label_source=original['label_source'],
            feedback_value=original['feedback_value'],prediction_at=d['prediction_at'],label_available_at=d['label_available_at'],
            supervision_weighting=POLICY,show_key=identity.group(key))
        if row['label_source'] in EXPLICIT:
            # Never infer an original action from a timestamp cluster. Match only
            # an already-attributed, unchanged effective observation.
            decision=d.get('feedback_decision');base=d.get('feedback_base_weight')
            if (not decision and old_policy is None
                and media[key].get('source',{}).get('metadata',{}).get('media_type')=='movie'):
                # A retained movie outcome cannot be a hierarchy descendant.
                # Bind its effective historical observation to the pinned model;
                # do not invent an original action UUID or require current feedback
                # that may legitimately have been replaced or undone.
                decision=dict(id='legacy-published-movie:'+fingerprint([config['model_sha256'],owner,canonical,
                    row['prediction_at'],row['label_available_at'],row['label_source']]),
                    kind='legacy-published-single-movie',target_scope='movie',target_identity=canonical,
                    time_basis='retained_effective_training_observation',time=row['prediction_at'])
                base=BASE_WEIGHTS[EXPLICIT[row['label_source']]]
            if not decision:
                current=lookup.get((owner,canonical))
                if (not current or any(current.get(k)!=row[k] for k in ('label','label_source','prediction_at','label_available_at','feedback_value'))):
                    raise ContractError('Incumbent explicit supervision requires reliable decision attribution')
                decision=current.get('feedback_decision');base=current.get('feedback_base_weight')
            if not decision:raise ContractError('Incumbent explicit supervision lacks decision attribution')
            row.update(feedback_decision=decision,feedback_base_weight=base)
        if unit_key(row) in forbidden:continue
        value=feature_row(inputs,media,watches,inputs['snapshot']['events'],owner,key,row['prediction_at'],excluded_keys=excluded,identity=identity)
        if value is None:
            limited_history+=1
            continue
        value.update(row)
        fitted.append(compact_row(value,media,watches,identity))
    if not fitted or {r['label'] for r in fitted}!={0,1}:raise ContractError('Comparable incumbent fit lacks both classes')
    fitted=allocate(fitted)
    if ({unit_key(r) for r in fitted}&forbidden
        or {(r['owner'],r['canonical_identity']) for r in fitted}&forbidden_pairs):
        raise ContractError('Comparable reference contains held-out supervision')
    manifest=dict(protocol='pinned-population-causal-refit/1',model_sha256=config['model_sha256'],
        original_population_rows=len(reference['rows']),population_hash=fingerprint(reference['rows']),
        fit_settings=recipe,fit_rows=len(fitted),excluded_show_rows=excluded_count,limited_history_skips=limited_history,
        original_weighting=old_policy or 'legacy-physical-row-support',
        fit_hash=fingerprint([(r['owner'],r['canonical_identity'],r['prediction_at'],r['label'],r['sample_weight']) for r in fitted]),
        validation_hash=fingerprint([(r['owner'],r['canonical_identity'],r['prediction_at'],r['label']) for r in heldout]),
        source_hash=config.get('source_hash'),dataset_hash=config.get('dataset_hash'),
        causal_boundary=boundary.isoformat(),decision_overlap=0,canonical_outcome_overlap=0,
        limitation='Incumbent recipe refitted on its causally eligible published population using the common feature snapshot; not predictions of the saved all-data model.')
    return fitted,old_policy is None,manifest
