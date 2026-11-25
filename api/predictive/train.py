"""Chronological and show-held-out validation, then a distinct all-data fit."""
from collections import Counter
from .contracts import ContractError,fingerprint,engagement_thresholds
from .features import Vocabulary,chronological_split,feature_row,show_heldout_plan,SUPERVISION_POLICY,compact_row
from .recovery import CanonicalTitles,IDENTITY_POLICY
from .model import fit,fit_compare
from .supervision import POLICY as WEIGHTING_POLICY, support, unit_key
from .reference import reference_fit


def train(inputs,media,watches,rows,summary,*,incumbent_ap=None,reference=None,progress=lambda **metrics:None):
    corrected=inputs.get('supervision_weighting')==WEIGHTING_POLICY
    if corrected and incumbent_ap is not None and reference is None:
        raise ContractError('Historical raw AP is not a comparable decision-normalized baseline')
    if (any(r.get('supervision_weighting')==WEIGHTING_POLICY for r in rows)!=corrected
        or (corrected and any(r.get('supervision_weighting')!=WEIGHTING_POLICY for r in rows))):
        raise ContractError('Mixed supervision weighting contracts')
    thresholds=engagement_thresholds(**inputs.get('label_thresholds',{}))
    if any(engagement_thresholds(**r.get('label_thresholds',{}))!=thresholds for r in rows):
        raise ContractError('Training rows and configured engagement thresholds differ')
    fit_rows,validation,boundary=chronological_split(rows)
    chronological=fit_compare(fit_rows,validation,include_poster=False,progress=lambda metrics:progress(**metrics))
    identity=CanonicalTitles(media)
    a,b,excluded,skips=show_heldout_plan(inputs,media,rows,identity=identity,boundary=boundary)
    grouped=[]
    for population in (a,b):
        rebuilt=[]
        for row in population:
            value=feature_row(inputs,media,watches,inputs['snapshot']['events'],row['owner'],row['media_key'],
                row['prediction_at'],excluded_keys=excluded,identity=identity)
            if value is None:raise ContractError('Grouped profile support changed')
            value.update({key:value for key,value in row.items() if key not in ('embedding','dependencies','dependency_hash','history_titles','watch_sim')})
            rebuilt.append(compact_row(value,media,watches,identity))
        grouped.append(rebuilt)
    if not all(grouped):raise ContractError('Show-held-out evaluation lacks support')
    show=fit_compare(*grouped,include_poster=False,progress=lambda metrics:progress(**metrics))
    for metrics,population,heldout in ((chronological,fit_rows,validation),(show,grouped[0],grouped[1])):
        if corrected:
            metrics['fit_support']=support(population)
            metrics['validation_support']=support(heldout)
            if {unit_key(r) for r in population}&{unit_key(r) for r in heldout}:
                raise ContractError('Original feedback decision crosses validation boundary')
        metrics['fit_classes']=dict(Counter(str(r['label']) for r in population))
        metrics['fit_identity_hash']=fingerprint([(r['owner'],r['canonical_identity'],r['prediction_at']) for r in population])
        metrics['validation_identity_hash']=fingerprint([(r['owner'],r['canonical_identity'],r['prediction_at']) for r in heldout])
    comparable={}
    if corrected and reference is not None:
        for name,heldout,omitted in (('chronological',validation,set()),('show_heldout',grouped[1],excluded)):
            ref_rows,legacy,manifest=reference_fit(reference,inputs,media,watches,rows,boundary,omitted,identity,heldout)
            measured=fit_compare(ref_rows,heldout,include_poster=False,legacy_weights=legacy,
                progress=lambda metrics:progress(**metrics))
            if measured['average_precision'] is None:raise ContractError('Comparable reference AP unavailable')
            comparable[name]=dict(manifest=manifest,metrics=measured)
    baseline=comparable['chronological']['metrics']['average_precision'] if comparable else incumbent_ap
    gates=dict(chronological_balanced_accuracy=chronological['balanced_accuracy'] is not None and chronological['balanced_accuracy']>=.5,
        show_balanced_accuracy=show['balanced_accuracy'] is not None and show['balanced_accuracy']>=.5,
        average_precision=baseline is None or chronological['average_precision']>=baseline-.05)
    evaluation=dict(label_thresholds=thresholds,chronological=chronological,show_heldout=show,boundary=boundary.isoformat(),show_support_skips=skips,
        gates=gates,incumbent_average_precision=baseline,comparable_reference=comparable,
        historical_incumbent_average_precision_diagnostic=incumbent_ap,
        supervision_weighting=WEIGHTING_POLICY if corrected else 'legacy-physical-row-support',
        threshold=.5,final_model_evaluation='No independent held-out score: final classifier is fitted on all eligible rows.',
        limitation='Repeated release validation, selected labeled candidates, current descriptive metadata; not an untouched prospective test.')
    if not all(gates.values()):
        error=ContractError('Existing model quality gate failed; nothing published');error.evaluation=evaluation;raise error
    vocabulary=Vocabulary.fit(rows,include_poster=False)
    classifier=fit(rows,vocabulary,progress=lambda metrics:progress(**metrics))
    bundle=dict(label_thresholds=thresholds,feature_space_id=inputs['feature_space_id'],contract_hash=inputs['contract_hash'],
        identity_policy=IDENTITY_POLICY,supervision_policy=SUPERVISION_POLICY,
        feature_names=vocabulary.names,vocabulary=vocabulary.specification(),model=classifier,dataset_hash=summary['dataset_hash'])
    if corrected:bundle['supervision_weighting']=WEIGHTING_POLICY
    return bundle,vocabulary,evaluation
