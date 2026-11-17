"""Classic operator text from retained records; no model calls or history writes."""
import json
from api.predictive.progress import EVENT,ITEM_EVENT,STAGE_NAMES


def scalar(value):
    if isinstance(value,bool):return 'yes' if value else 'no'
    if isinstance(value,int):return f'{value:,}'
    if isinstance(value,float):return f'{value:.3f}'
    return str(value)


def plain_line(line):
    prefix='Watch history sync metrics: '
    if line.startswith(prefix):
        try:metrics=json.loads(line[len(prefix):])
        except ValueError:return line
        if isinstance(metrics,dict):
            labels={'rows':'Rows','inserted':'Inserted','updated':'Updated','unchanged':'Unchanged','skipped':'Skipped','failed':'Failed','status':'Status'}
            return '📊 Watch history sync — '+', '.join(label+': '+scalar(metrics[key]) for key,label in labels.items() if key in metrics)
    return line


def title(value):
    name=value.get('title') or 'Media item'
    if value.get('show_title'):
        context=value['show_title']
        if value.get('season') is not None:context+=f' — S{int(value["season"]):02d}'
        if value.get('episode') is not None:context+=f'E{int(value["episode"]):02d}'
        name=context+' — '+name
    return name+(f' (rating_key={value["rating_key"]})' if value.get('rating_key') is not None else '')


def item_line(value):
    op=value.get('operation');user=value.get('user','Unknown user')
    if op=='embedding':return '   🎬 Embedding '+title(value)
    if op=='embedded':return '✅ Embedded '+title(value)
    if op=='reused':return '   🎬 '+title(value)+' — cached embedding reused'
    if op=='embedding_failed':return '❌ Embedding failed: '+title(value)+' — '+str(value.get('error_type','Error'))
    if op=='scoring_user':
        return f'\n📊 Fetching unwatched media for {user}...\n🔍 {scalar(value.get("candidates","Unknown"))} eligible media items after filtering.\n🔮 Scoring predictions...'
    if op=='scored_user':
        targets=value.get('shap_targets')
        return (f'✅ Scored {scalar(value.get("predictions","Unknown"))} recommendations for {user}.\n'
                f'📊 Selected {scalar(targets)} recommendation cards for raw SHAP ({value.get("strategy","recorded strategy")}).\n'+
                ('\n🔍 SHAP Feature Impact (Top Rows):' if targets else '⏩ No rows selected for SHAP.'))
    if op=='ranked_shap':
        contributions=value.get('contributions',[])
        if not all(isinstance(v,dict) and isinstance(v.get('value'),(int,float)) and 'feature' in v for v in contributions):
            return json.dumps(value,ensure_ascii=False,indent=2)
        result=f'Rank {value.get("rank","?")}: {value.get("rating_key","?")} — '+', '.join(
            f'{v["feature"]} ({v["value"]:+.2f})' for v in contributions)
        if value.get('title'):
            result+='\n   🎬 '+title(value)
            if isinstance(value.get('probability'),(int,float)):result+=f' — Probability: {value["probability"]:.3f}'
        return result
    if op=='scoring_complete':return f'✅ Finished scoring {user}: {scalar(value.get("predictions","Unknown"))} scored items; {scalar(value.get("shap_targets","Unknown"))} raw SHAP explanations.\n'
    return json.dumps(value,ensure_ascii=False,indent=2)


def stage_line(value):
    key=value.get('stage_key','');status=value.get('status','');message=value.get('message')
    metrics=value.get('metrics') or {};name=STAGE_NAMES.get(key,key)
    if status=='started' and value.get('timing_active') is False and not message:return None
    if message:
        return ('❌ ' if status=='failed' else '🧠 ')+message
    if status=='failed':return '❌ '+name+' failed.'
    if status in ('skipped','not_recorded','cancelled'):return '⏩ '+name+': '+status.replace('_',' ')+'.'
    if key=='media_text' and status=='success' and 'reused' in metrics and metrics.get('inferred',0)==0 and metrics.get('completed')==metrics['reused']:
        return f'✅ Media embeddings unchanged: {scalar(metrics["reused"])} cached vectors reused. No new embedding requests were needed.'
    if status=='started' and not any(metrics.get(k) for k in ('completed','users','predictions')):
        return {'source_sync':'🔄 Synchronizing the library...', 'media_text':'🧠 Checking media embeddings...',
                'watch':'🧠 Checking watch embeddings...', 'users':'🔍 Building user-profile embeddings...',
                'training_data':'📦 Preparing training data...', 'train_model':'📥 Training and validating the model...',
                'score_model':'🔮 Scoring recommendations...', 'publication':'📦 Publishing completed output...',
                'verification':'🔍 Verifying publication...'}.get(key,'🔄 '+name+'...')
    labels={'completed':'Processed','expected':'Total','reused':'Reused','inferred':'Embedded','users':'Users',
            'predictions':'Predictions','rows':'Training rows','contexts':'SHAP contexts','contributions':'SHAP contributions',
            'quality_passed':'Quality gates passed','chronological_balanced_accuracy':'Chronological balanced accuracy',
            'chronological_average_precision':'Chronological average precision','show_balanced_accuracy':'Show-heldout balanced accuracy'}
    details=' · '.join(labels.get(k,k.replace('_',' ').capitalize())+': '+scalar(v) for k,v in metrics.items() if k!='seconds')
    return ('✅ ' if status=='success' else '📊 ')+name+(' complete' if status=='success' else '')+(' — '+details if details else '.')


def classification_report(name,metrics,threshold):
    matrix=metrics.get('confusion_matrix')
    if not (isinstance(matrix,list) and len(matrix)==2 and all(isinstance(row,list) and len(row)==2 for row in matrix)
            and all(isinstance(v,int) and not isinstance(v,bool) and v>=0 for row in matrix for v in row)):
        return []
    tn,fp=matrix[0];fn,tp=matrix[1];supports=[tn+fp,fn+tp];total=sum(supports)
    if not total:return []
    divide=lambda a,b:a/b if b else 0.
    precision=[divide(tn,tn+fn),divide(tp,tp+fp)]
    recall=[divide(tn,supports[0]),divide(tp,supports[1])]
    f1=[divide(2*tn,2*tn+fp+fn),divide(2*tp,2*tp+fp+fn)]
    lines=[f'\n📋 {name} classification report at recorded threshold {threshold:.2f}',
           '   Reconstructed from this run’s recorded confusion counts.',
           '              precision    recall  f1-score   support','']
    for i in (0,1):lines.append(f'{i:>12}  {precision[i]:>9.3f} {recall[i]:>9.3f} {f1[i]:>9.3f} {supports[i]:>9}')
    lines.extend(['',f'{"accuracy":>12}                      {(tn+tp)/total:>9.3f} {total:>9}'])
    for label,weights in [('macro avg',[.5,.5]),('weighted avg',[s/total for s in supports])]:
        values=[sum(a*w for a,w in zip(series,weights)) for series in (precision,recall,f1)]
        lines.append(f'{label:>12}  {values[0]:>9.3f} {values[1]:>9.3f} {values[2]:>9.3f} {total:>9}')
    lines.extend(['',f'🧮 Confusion matrix (labels: [0, 1])',f'[[{tn:5d} {fp:5d}]',f' [{fn:5d} {tp:5d}]]'])
    for key,label in [('balanced_accuracy','Balanced accuracy'),('average_precision','Average precision'),('feature_count','Feature count')]:
        if metrics.get(key) is not None:lines.append(label+': '+scalar(metrics[key]))
    if metrics.get('negative_sample_warning'):lines.append('⚠️ '+metrics['negative_sample_warning'])
    return lines


def completion_summary(stage,fields):
    lines=[]
    if stage=='training_data' and isinstance(fields.get('summary'),dict):
        summary=fields['summary']
        for key,label in [('rows','🧠 Training rows created'),('positive','➕ Positive training rows'),('negative','➖ Negative training rows')]:
            if key in summary:lines.append(label+': '+scalar(summary[key]))
        if 'negative' in summary and 'positive' in summary:lines.append(f'📈 Label distribution: {{0: {summary["negative"]}, 1: {summary["positive"]}}}')
        for key,label in [('sources','🧾 Label sources'),('observations','🧾 Observation types'),('provenance','🧾 Feedback provenance')]:
            if isinstance(summary.get(key),dict):lines.append(label+': '+', '.join(k+': '+scalar(v) for k,v in summary[key].items()))
        if isinstance(summary.get('skips'),dict):
            lines.extend('🛡️ Skipped '+k.replace('_',' ')+': '+scalar(v) for k,v in summary['skips'].items())
    if stage=='train_model' and isinstance(fields.get('evaluation'),dict):
        evaluation=fields['evaluation'];threshold=evaluation.get('threshold')
        if isinstance(threshold,(int,float)):
            for key,label in [('chronological','Chronological validation'),('show_heldout','Show-heldout validation')]:
                if isinstance(evaluation.get(key),dict):lines.extend(classification_report(label,evaluation[key],threshold))
        if isinstance(evaluation.get('gates'),dict):
            lines.append('\n🛡️ Recorded quality gates: '+', '.join(k.replace('_',' ')+': '+('passed' if v else 'failed') for k,v in evaluation['gates'].items()))
        if evaluation.get('final_model_evaluation'):lines.append('📝 '+evaluation['final_model_evaluation'])
    counts=fields.get('published counts') or {}
    if counts:lines.append('📊 Published totals: '+', '.join(k.replace('_',' ')+': '+scalar(v) for k,v in counts.items()))
    return '\n'.join(lines)
