"""Chronological and show-held-out validation, then a distinct all-data fit."""
from collections import Counter
from .contracts import ContractError,fingerprint,engagement_thresholds
from .features import Vocabulary,chronological_split,feature_row,show_heldout_plan,SUPERVISION_POLICY,compact_row
from .recovery import CanonicalTitles,IDENTITY_POLICY
from .model import fit,fit_compare


def train(inputs,media,watches,rows,summary,*,incumbent_ap=None,progress=lambda **metrics:None,warning=lambda value:None):
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
        metrics['fit_classes']=dict(Counter(str(r['label']) for r in population))
        metrics['fit_identity_hash']=fingerprint([(r['owner'],r['canonical_identity'],r['prediction_at']) for r in population])
        metrics['validation_identity_hash']=fingerprint([(r['owner'],r['canonical_identity'],r['prediction_at']) for r in heldout])
    gates=dict(chronological_balanced_accuracy=chronological['balanced_accuracy'] is not None and chronological['balanced_accuracy']>=.5,
        show_balanced_accuracy=show['balanced_accuracy'] is not None and show['balanced_accuracy']>=.5,
        average_precision=incumbent_ap is None or (chronological['average_precision'] is not None and chronological['average_precision']>=incumbent_ap-.05))
    warnings=[]
    for check,metric,value,minimum in (
        ('chronological_balanced_accuracy','chronological.balanced_accuracy',chronological['balanced_accuracy'],.5),
        ('show_balanced_accuracy','show_heldout.balanced_accuracy',show['balanced_accuracy'],.5),
        ('average_precision','chronological.average_precision',chronological['average_precision'],incumbent_ap-.05 if incumbent_ap is not None else None)):
        if gates[check]:continue
        measured=f'{value:.6f}' if value is not None else 'unavailable'
        message=f'Non-blocking statistical warning: {metric}={measured}; diagnostic minimum={minimum:.6f}.'
        if check=='average_precision':message+=f' Historical incumbent AP={incumbent_ap:.6f}; allowed decline=0.050000.'
        warnings.append(dict(check=check,metric=metric,value=value,minimum=minimum,comparison='>=',blocking=False,message=message))
    evaluation=dict(label_thresholds=thresholds,chronological=chronological,show_heldout=show,boundary=boundary.isoformat(),show_support_skips=skips,
        gates=gates,incumbent_average_precision=incumbent_ap,
        statistical_checks_blocking=False,statistical_warnings=warnings,
        threshold=.5,final_model_evaluation='No independent held-out score: final classifier is fitted on all eligible rows.',
        limitation='Repeated release validation, selected labeled candidates, current descriptive metadata; not an untouched prospective test.')
    for value in warnings:warning(value)
    vocabulary=Vocabulary.fit(rows,include_poster=False)
    classifier=fit(rows,vocabulary,progress=lambda metrics:progress(**metrics))
    bundle=dict(label_thresholds=thresholds,feature_space_id=inputs['feature_space_id'],contract_hash=inputs['contract_hash'],
        identity_policy=IDENTITY_POLICY,supervision_policy=SUPERVISION_POLICY,
        feature_names=vocabulary.names,vocabulary=vocabulary.specification(),model=classifier,dataset_hash=summary['dataset_hash'])
    return bundle,vocabulary,evaluation
