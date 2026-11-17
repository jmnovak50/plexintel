"""Classic console rendering from retained records; no pipeline/model execution."""
import json
from copy import deepcopy
from api.predictive.progress import Reporter,ITEM_EVENT
from api.services.pipeline_logs import get_stage_logs
from api.services.pipeline_log_format import classification_report
from tests.test_pipeline_log_view import fixture,event


def test_operator_scoring_matches_old_rank_lines_and_retains_full_recorded_events(tmp_path,monkeypatch):
    records=[];reporter=Reporter(records.append)
    reporter.log('score_model','scoring_user',user='fixture-viewer',candidates=1234)
    reporter.log('score_model','scored_user',user='fixture-viewer',predictions=1234,shap_targets=1,strategy='per_media_type')
    reporter.log('score_model','ranked_shap',user='fixture-viewer',rank=80,rating_key='7',title='Fixture title',probability=.76543,
                 contributions=[dict(feature='genre_Family',value=.234567),dict(feature='media_text_23',value=-.25678)])
    raw=''.join(json.dumps(r)+'\n' for r in records);run=fixture(tmp_path,monkeypatch,raw)
    rendered=get_stage_logs(run,'score_model')['stdout']['text']
    assert '📊 Fetching unwatched media for fixture-viewer...' in rendered
    assert '🔍 1,234 eligible media items after filtering.' in rendered
    assert '🔍 SHAP Feature Impact (Top Rows):' in rendered
    assert 'Rank 80: 7 — genre_Family (+0.23), media_text_23 (-0.26)' in rendered
    assert '🎬 Fixture title (rating_key=7) — Probability: 0.765' in rendered
    for protocol in ('stage_key','user=','probability=','timing_active','"event"',' | '):assert protocol not in rendered
    recorded=get_stage_logs(run,'score_model',view='recorded')['stdout']['text']
    assert recorded==raw.rstrip('\n')
    assert json.loads(recorded.splitlines()[-1])['contributions'][0]['value']==.234567


def test_cache_hits_and_progress_are_available_without_burying_actual_embedding_output(tmp_path,monkeypatch):
    values=[];r=Reporter(values.append)
    r.log('media_text','reused',rating_key='7',title='Cached film')
    r.log('media_text','embedding',rating_key='8',title='New film')
    r.log('media_text','embedded',rating_key='8',title='New film')
    r.log('media_text','reused',rating_key='9',title='Another cached film')
    raw=event('media_text')+''.join(json.dumps(v)+'\n' for v in values)
    run=fixture(tmp_path,monkeypatch,raw)
    result=get_stage_logs(run,'source_sync')['stdout'];text=result['text']
    main,details=text.split('\nRecorded cache reuse details',1)
    assert 'Embedding New film' in main and 'Embedded New film' in main
    assert 'Cached film' not in main and 'Another cached film' not in main
    assert 'Cached film' in details and 'Another cached film' in details and '2 items' in details
    assert result['has_supplement']
    recorded=get_stage_logs(run,'source_sync',view='recorded')['stdout']['text']
    assert recorded.count('"operation": "reused"')==2


def test_classic_no_embedding_message_requires_recorded_reuse_coverage(tmp_path,monkeypatch):
    value=json.loads(event('media_text','success'))
    value['metrics']=dict(completed=8442,expected=8442,reused=8442)
    run=fixture(tmp_path,monkeypatch,json.dumps(value)+'\n')
    assert '8,442 cached vectors reused. No new embedding requests were needed.' in get_stage_logs(run,'source_sync')['stdout']['text']
    value['metrics']['reused']=8441
    run=fixture(tmp_path,monkeypatch,json.dumps(value)+'\n')
    assert 'No new embedding requests' not in get_stage_logs(run,'source_sync')['stdout']['text']


def test_classic_classification_report_uses_only_recorded_counts_and_threshold():
    metrics=dict(confusion_matrix=[[7,23],[4,429]],balanced_accuracy=.612,average_precision=.98,feature_count=1602)
    original=deepcopy(metrics)
    text='\n'.join(classification_report('Show-heldout validation',metrics,.5))
    assert 'recorded threshold 0.50' in text and 'Reconstructed from this run’s recorded confusion counts.' in text
    assert 'precision    recall  f1-score   support' in text
    assert '0.636     0.233     0.341        30' in text
    assert '0.949     0.991     0.969       433' in text
    assert 'macro avg' in text and 'weighted avg' in text
    assert '[[    7    23]' in text and '[    4   429]]' in text
    assert metrics==original
    assert classification_report('Unknown',dict(confusion_matrix=None),.5)==[]


def test_recorded_view_redacts_json_escaped_secrets_without_discarding_other_fields(tmp_path,monkeypatch):
    monkeypatch.setenv('FIXTURE_LOG_SECRET','private-Ω-secret')
    record=dict(event=ITEM_EVENT,stage_key='score_model',operation='ranked_shap',rank=1,rating_key='7',
                contributions=[],extra_detail=dict(message='private-Ω-secret',preserved='real detail'))
    run=fixture(tmp_path,monkeypatch,json.dumps(record)+'\n')
    text=get_stage_logs(run,'score_model',view='recorded')['stdout']['text']
    assert 'private-Ω-secret' not in text and 'private-\\u03a9-secret' not in text
    assert '[REDACTED]' in text and json.loads(text)['extra_detail']['preserved']=='real detail'


def test_new_collector_metric_line_is_human_readable_but_original_legacy_text_is_preserved(tmp_path,monkeypatch):
    raw='Watch history sync metrics: '+json.dumps(dict(rows=337,inserted=3,unchanged=334,fetch_seconds=.123,status='committed'))
    run=fixture(tmp_path,monkeypatch,event('source_sync')+raw+'\n')
    text=get_stage_logs(run,'source_sync')['stdout']['text']
    assert '📊 Watch history sync — Rows: 337, Inserted: 3, Unchanged: 334, Status: committed' in text
    assert '{' not in text and 'fetch_seconds' not in text
    assert raw in get_stage_logs(run,'source_sync',view='recorded')['stdout']['text']
    legacy=dict(run_id=998,stages=[dict(stage_key='tautulli_incremental',stdout_tail=raw)])
    assert get_stage_logs(legacy,'tautulli_incremental')['stdout']['text']==raw
