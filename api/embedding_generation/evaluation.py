"""Measured predictive/ranking diagnostics; no claim of image benefit by width."""
from collections import defaultdict
import time
import numpy as np


def probability_metrics(rows,probability):
    from sklearn.metrics import (average_precision_score,balanced_accuracy_score,brier_score_loss,
        precision_score,recall_score,roc_auc_score,f1_score,precision_recall_curve,auc)
    y=np.asarray([r['label'] for r in rows],dtype=int);p=np.asarray(probability,dtype=float)
    result=dict(rows=len(rows),positive=int(y.sum()),negative=int(len(y)-y.sum()))
    if not len(rows):return dict(**result,status='no_examples')
    both=len(set(y))==2;pred=p>=.5
    curve_p,curve_r,_=precision_recall_curve(y,p) if y.sum() else (None,None,None)
    result.update(balanced_accuracy=float(balanced_accuracy_score(y,pred)) if both else None,
        precision=float(precision_score(y,pred,zero_division=0)),recall=float(recall_score(y,pred,zero_division=0)),
        average_precision=float(average_precision_score(y,p)) if y.sum() else None,
        pr_auc=float(auc(curve_r,curve_p)) if y.sum() else None,
        roc_auc=float(roc_auc_score(y,p)) if both else None,
        macro_f1=float(f1_score(y,pred,average='macro',zero_division=0)),brier_score=float(brier_score_loss(y,p)))
    bins=[];ece=0.
    for index in range(10):
        selected=(p>=index/10)&((p<(index+1)/10) if index<9 else (p<=1))
        count=int(selected.sum());confidence=float(p[selected].mean()) if count else None
        frequency=float(y[selected].mean()) if count else None
        if count:ece+=count/len(y)*abs(confidence-frequency)
        bins.append(dict(lower=index/10,upper=(index+1)/10,count=count,confidence=confidence,positive_rate=frequency))
    result['calibration']=dict(ece_10_bins=ece,bins=bins,status='uncalibrated_classifier_diagnostics')
    by_owner=defaultdict(list)
    for row,score in zip(rows,p):by_owner[row['owner']].append((float(score),row['media_key'],row['label']))
    ndcg=[];recall=[];sizes=[]
    for values in by_owner.values():
        values.sort(key=lambda v:(-v[0],int(v[1])));positives=sum(v[2] for v in values)
        if not positives:continue
        dcg=sum(v[2]/np.log2(i+2) for i,v in enumerate(values[:10]))
        ideal=sum(1/np.log2(i+2) for i in range(min(10,positives)))
        ndcg.append(float(dcg/ideal));recall.append(sum(v[2] for v in values[:25])/positives);sizes.append(len(values))
    result['ranking']=dict(ndcg_at_10=float(np.mean(ndcg)) if ndcg else None,
        recall_at_25=float(np.mean(recall)) if recall else None,users_with_positive_labels=len(sizes),
        min_candidates=min(sizes) if sizes else 0,max_candidates=max(sizes) if sizes else 0,
        users_with_at_most_25_candidates=sum(size<=25 for size in sizes),
        limitation='Ranks labeled heldout candidates per user, not the full catalog. Recall@25 saturates for small cohorts.')
    return result


def evaluate(classifier,vocabulary,rows,*,training_keys=()):
    start=time.perf_counter();p=classifier.predict_proba(vocabulary.transform(rows))[:,1]
    result=probability_metrics(rows,p);result['prediction_seconds']=time.perf_counter()-start
    keys=set(training_keys)
    segments={'movie':lambda r:r.get('media_type')=='movie','tv':lambda r:r.get('media_type')=='episode',
        'missing_art':lambda r:r.get('poster_missing',False),'with_art':lambda r:not r.get('poster_missing',False),
        'sparse_history_1_to_5_titles':lambda r:0<r.get('history_titles',0)<=5,
        'cold_start_title_not_in_training':lambda r:r['media_key'] not in keys}
    result['segments']={}
    for name,predicate in segments.items():
        indices=[i for i,r in enumerate(rows) if predicate(r)]
        result['segments'][name]=probability_metrics([rows[i] for i in indices],p[indices])
    result['zero_history_users']='Not scored: no semantic profile. Excluded counts appear in dataset/scoring coverage.'
    import xgboost as xgb
    values=classifier.get_booster().predict(xgb.DMatrix(vocabulary.transform(rows),feature_names=vocabulary.names),pred_contribs=True)[:,:-1]
    gain=classifier.get_booster().get_score(importance_type='gain');groups=defaultdict(list)
    for i,name in enumerate(vocabulary.names):
        group=next((prefix for prefix in ('media_text','media_poster','user','genre','director','decade') if name.startswith(prefix+'_')),name)
        groups[group].append(i)
    result['feature_group_importance']={group:dict(dimensions=len(indices),
        mean_sum_abs_shap=float(np.abs(values[:,indices]).sum(axis=1).mean()),
        sum_gain=float(sum(gain.get(vocabulary.names[i],0.) for i in indices))) for group,indices in groups.items()}
    result['importance_caution']='Associational model diagnostics, not independent causal contributions; no embedding pruning.'
    return result
