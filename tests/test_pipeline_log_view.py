"""Stage-owned complete output, using fictional retained files and no predictive run."""
import json
from fastapi import FastAPI
import pytest
from api.routes import pipeline_admin_routes as routes
from api.services import pipeline_logs as logs


def event(key,status='started',**extra):
    return json.dumps(dict(event=logs.EVENT,stage_key=key,status=status,timing_active=status=='started',
                           metrics={},**extra))+'\n'


def fixture(tmp_path,monkeypatch,stdout='',stderr='',keys=('source_sync','media_text','train_model','score_model','shap','publication','verification','semantic_labels')):
    monkeypatch.setenv('PIPELINE_LOG_PATH',str(tmp_path/'pipeline.log'))
    for stream,text in [('stdout',stdout),('stderr',stderr)]:
        (tmp_path/f'pipeline-run-999-predictive_daily-fixture.{stream}.log').write_text(text)
    return dict(run_id=999,stages=[dict(stage_key='predictive_daily',stdout_tail='saved worker tail',stderr_tail=None),
                                  *[dict(stage_key=k,stdout_tail=event(k,'success'),stderr_tail=None) for k in keys]])


def test_full_stage_output_is_not_replaced_by_latest_summary(monkeypatch,tmp_path):
    source=''.join(f'collector detail {i}\n' for i in range(3000))
    raw=event('source_sync')+source+event('source_sync','success')+event('train_model')+'fit detail\n'+event('train_model','success')
    run=fixture(tmp_path,monkeypatch,raw)
    before=(tmp_path/'pipeline-run-999-predictive_daily-fixture.stdout.log').read_bytes()
    out=logs.get_stage_logs(run,'source_sync')['stdout']
    assert out['source']=='retained stage file'
    assert 'collector detail 0\n' in out['text'] and 'collector detail 2999\n' in out['text']
    assert len(out['text'].splitlines())==3002 and 'fit detail' not in out['text']
    assert (tmp_path/'pipeline-run-999-predictive_daily-fixture.stdout.log').read_bytes()==before


def test_unkeyed_lines_follow_explicit_active_boundary_and_stderr_is_not_guessed(monkeypatch,tmp_path):
    raw='worker setup without a phase\n'+event('train_model')+'fit first\nfit second\n'+event('train_model','success')+'outside any phase\n'
    run=fixture(tmp_path,monkeypatch,raw,'unkeyed failure\n'+json.dumps(dict(stage_key='train_model',error='keyed failure'))+'\n')
    fit=logs.get_stage_logs(run,'train_model')
    worker=logs.get_stage_logs(run,'predictive_daily')
    assert 'fit first\nfit second' in fit['stdout']['text']
    assert 'outside any phase' not in fit['stdout']['text']
    assert 'unkeyed failure' not in fit['stderr']['text'] and 'keyed failure' in fit['stderr']['text']
    assert 'unkeyed failure' in worker['stderr']['text']
    assert 'fit first' not in worker['stdout']['text']
    assert 'outside any phase' in worker['stdout']['text']


def test_grouped_interleaved_events_keep_their_actual_order(monkeypatch,tmp_path):
    raw=(event('score_model')+'score before\n'+event('shap')+'explanation detail\n'+event('shap','success')+
         event('score_model')+'score after\n'+event('score_model','success'))
    run=fixture(tmp_path,monkeypatch,raw)
    out=logs.get_stage_logs(run,'score_model')['stdout']['text']
    assert out.index('score before') < out.index('explanation detail') < out.index('score after')
    assert out.count('explanation detail')==1
    assert 'explanation detail' not in logs.get_stage_logs(run,'predictive_daily')['stdout']['text']
    assert 'score before' not in logs.get_stage_logs(run,'shap')['stdout']['text']


def test_live_append_and_utf8_pagination_preserve_every_line_once(monkeypatch,tmp_path):
    run=fixture(tmp_path,monkeypatch,event('train_model')+'early 東京 🎬\n')
    path=tmp_path/'pipeline-run-999-predictive_daily-fixture.stdout.log'
    assert 'late output' not in logs.get_stage_logs(run,'train_model')['stdout']['text']
    with path.open('a') as f:f.write('late output\n')
    expected=logs.get_stage_logs(run,'train_model')['stdout']['text']
    offset=0;parts=[]
    while True:
        page=logs.get_stage_logs(run,'train_model',stdout_offset=offset,limit=19)['stdout']
        parts.append(page['text'])
        if page['next_offset'] is None:break
        offset=page['next_offset']
    assert ''.join(parts)==expected and expected.count('late output')==1
    assert '東京 🎬' in expected


def test_pretty_json_retains_detailed_fields_and_redacts_credentials(monkeypatch,tmp_path):
    monkeypatch.setenv('FICTIONAL_API_KEY','private-value')
    value=dict(phase='fit diagnostics',matrix=[[1,2],[3,4]],details=dict(kept='actual detail'),token='other-secret')
    run=fixture(tmp_path,monkeypatch,event('train_model')+'token=private-value\n'+json.dumps(value)+'\n')
    out=logs.get_stage_logs(run,'train_model')['stdout']['text']
    assert 'private-value' not in out and 'other-secret' not in out
    assert 'actual detail' in out and '"matrix": [' in out and len(out.splitlines())>8


def test_progress_record_extensions_are_not_lost_to_metric_allowlists(monkeypatch,tmp_path):
    value=json.loads(event('train_model'))
    value.update(metrics=dict(completed=1,additional_diagnostic='actual retained diagnostic'),
                 generation_run_id='recorded-receipt',additional_detail=dict(kept=True))
    run=fixture(tmp_path,monkeypatch,json.dumps(value)+'\n')
    out=logs.get_stage_logs(run,'train_model')['stdout']['text']
    assert 'actual retained diagnostic' in out and 'recorded-receipt' in out and '"kept": true' in out


def test_completion_receipt_details_belong_to_their_stages_not_the_worker(monkeypatch,tmp_path):
    receipt=dict(verified=True,run_id='exact-execution',counts=dict(media_embeddings=50,user_embeddings=3,
        training_data=18,recommendations=60,shap_impact=40),
        summary=dict(rows=18,positive=12,negative=6,skips=dict(limited_history=2),
                     sources=dict(explicit_reject=4)),
        evaluation=dict(chronological=dict(confusion_matrix=[[3,1],[2,9]],negative_precision=.6,
                                           negative_recall=.75,negative=4,precision=.9,recall=.8,positive=11,
                                           feature_group_importance=dict(genre=dict(sum_gain=7))),
                        show_heldout=dict(balanced_accuracy=.7),gates=dict(quality=True),threshold=.5),
        ranking_comparison=dict(users=[dict(user='viewer_1',top20_overlap=12)]),
        semantic_labeling=dict(status='skipped',reason='Recorded reason'),
        extra_diagnostic='preserve unknown fields')
    run=fixture(tmp_path,monkeypatch,event('train_model')+'original fitting detail\n'+
        event('train_model','success')+json.dumps(receipt)+'\n',
        keys=('media_text','users','training_data','train_model','score_model','shap','publication','semantic_labels'))
    outputs={key:logs.get_stage_logs(run,key)['stdout']['text'] for key in
             ('train_model','training_data','score_model','publication','users','media_text','predictive_daily')}
    fit=outputs['train_model']
    assert 'original fitting detail' in fit and 'Recorded completion diagnostics' in fit
    assert 'Confusion matrix (actual rows / predicted columns; labels 0, 1)' in fit
    assert 'actual 0:' in fit and 'actual 1:' in fit and 'Class report [evaluation / chronological]' in fit
    assert '0 | 0.6 | 0.75 | 4' in fit and '1 | 0.9 | 0.8 | 11' in fit
    assert 'show heldout:' in fit and 'sum gain: 7' in fit
    assert 'positive: 12' in outputs['training_data'] and 'limited history: 2' in outputs['training_data']
    assert 'viewer_1' in outputs['score_model'] and 'top20 overlap: 12' in outputs['score_model']
    assert 'verified: true' in outputs['publication'] and 'user embeddings: 3' in outputs['users']
    worker=outputs['predictive_daily']
    assert 'preserve unknown fields' in worker
    for detail in ('viewer_1','confusion_matrix','negative_precision','explicit_reject','Recorded reason'):
        assert detail not in worker
    assert 'positive: 12' not in fit


def test_incomplete_recorded_class_reports_keep_every_available_field():
    value=dict(confusion_matrix=None,negative_precision=.6,negative_recall=.75,negative=4,
               precision=.9,recall=.8,positive=11)
    text='\n'.join(logs._diagnostic_lines(value))
    assert 'negative precision: 0.6' in text and 'confusion matrix: null' in text
    assert 'positive: 11' in text and 'Class report' not in text


def test_receipt_without_destination_or_noncompletion_records_remain_accessible(monkeypatch,tmp_path):
    receipt=dict(verified=True,run_id='exact',counts=dict(training_data=3,unknown_population=7),
                 summary=dict(rows=3),evaluation=dict(confusion_matrix=[[1,0],[0,2]]))
    run=fixture(tmp_path,monkeypatch,json.dumps(receipt)+'\n',keys=())
    worker=logs.get_stage_logs(run,'predictive_daily')['stdout']['text']
    for key in receipt:assert f'"{key}"' in worker
    # An unrelated JSON diagnostic isn't silently interpreted as a final receipt.
    receipt['verified']=False
    run=fixture(tmp_path,monkeypatch,json.dumps(receipt)+'\n')
    assert '"evaluation"' in logs.get_stage_logs(run,'predictive_daily')['stdout']['text']


def test_completion_diagnostics_are_redacted_paginated_and_exact_run_only(monkeypatch,tmp_path):
    monkeypatch.setenv('TEST_DIAGNOSTIC_SECRET','sensitive-field')
    receipt=dict(verified=True,run_id='execution-999',counts={},summary={},
                 evaluation=dict(warning='sensitive-field',detail='genuine Ω field',confusion_matrix=[[1,0],[0,2]]))
    run=fixture(tmp_path,monkeypatch,json.dumps(receipt)+'\n')
    (tmp_path/'pipeline-run-998-predictive_daily-fixture.stdout.log').write_text(
        json.dumps(dict(receipt,evaluation=dict(warning='unrelated run')))+'\n')
    expected=logs.get_stage_logs(run,'train_model')['stdout']['text']
    assert 'sensitive-field' not in expected and '[REDACTED]' in expected and 'genuine Ω field' in expected
    assert 'unrelated run' not in expected
    pages=[];offset=0
    while True:
        page=logs.get_stage_logs(run,'train_model',stdout_offset=offset,limit=17)['stdout']
        pages.append(page['text'])
        if page['next_offset'] is None:break
        offset=page['next_offset']
    assert ''.join(pages)==expected


def test_legacy_files_and_genuine_record_only_history(monkeypatch,tmp_path):
    monkeypatch.setenv('PIPELINE_LOG_PATH',str(tmp_path/'pipeline.log'))
    run=dict(run_id=999,stages=[dict(stage_key='train_model',stdout_tail='saved last line',stderr_tail='saved error')])
    out=logs.get_stage_logs(run,'train_model')
    assert out['stdout']['text']=='saved last line' and 'saved stage' in out['stdout']['source']
    (tmp_path/'pipeline-run-999-train_model-fixture.stdout.log').write_text('full first\nfull second\n')
    out=logs.get_stage_logs(run,'train_model')
    assert out['stdout']['text']=='full first\nfull second' and 'saved last line' not in out['stdout']['text']
    assert out['stderr']['text']=='saved error'


def test_missing_worker_stderr_file_preserves_its_saved_diagnostic(monkeypatch,tmp_path):
    run=fixture(tmp_path,monkeypatch,event('train_model'))
    (tmp_path/'pipeline-run-999-predictive_daily-fixture.stderr.log').unlink()
    run['stages'][0]['stderr_tail']='genuine saved worker diagnostic'
    result=logs.get_stage_logs(run,'predictive_daily')
    assert result['stderr']['text']=='genuine saved worker diagnostic'
    assert result['stderr']['source']=='saved stage record only'


def test_combined_log_uses_exact_run_stage_sections_only(monkeypatch,tmp_path):
    monkeypatch.setenv('PIPELINE_LOG_PATH',str(tmp_path/'pipeline.log'))
    run=dict(run_id=999,stages=[dict(stage_key='predictive_daily',stdout_tail='saved mixed tail',stderr_tail=None),
                                 dict(stage_key='train_model',stdout_tail=None,stderr_tail=None)])
    (tmp_path/'pipeline.log').write_text('[x] [run:998] [stage:predictive_daily] stdout:\nother run detail\n'+
        '[x] [run:999] [stage:predictive_daily] stdout:\n'+event('train_model')+'actual first\nactual second\n'+
        event('train_model','success')+'worker remainder\n'+
        '[x] [run:999] [stage:predictive_daily] stderr:\nactual unkeyed error\n'+
        '[x] [run:999] [stage:predictive_daily] end\n')
    out=logs.get_stage_logs(run,'train_model')['stdout']
    assert 'actual first\nactual second' in out['text'] and 'other run detail' not in out['text']
    assert out['source']=='exact run/stage section in pipeline.log'
    worker=logs.get_stage_logs(run,'predictive_daily')
    assert 'saved mixed tail' not in worker['stdout']['text'] and 'actual first' not in worker['stdout']['text']
    assert worker['stderr']['text']=='actual unkeyed error'


def test_no_known_child_records_keeps_worker_output_accessible(monkeypatch,tmp_path):
    run=fixture(tmp_path,monkeypatch,event('media_text')+'detail without saved child stage\n',keys=())
    out=logs.get_stage_logs(run,'predictive_daily')['stdout']['text']
    assert 'detail without saved child stage' in out
    with pytest.raises(KeyError):logs.get_stage_logs(run,'not-a-stage')


def test_paused_span_does_not_claim_following_unkeyed_output(monkeypatch,tmp_path):
    paused=json.loads(event('train_model'));paused['timing_active']=False
    run=fixture(tmp_path,monkeypatch,event('train_model')+'inside\n'+json.dumps(paused)+'\nnot attributable\n')
    assert 'not attributable' not in logs.get_stage_logs(run,'train_model')['stdout']['text']
    assert 'not attributable' in logs.get_stage_logs(run,'predictive_daily')['stdout']['text']


def test_stage_route_is_admin_only_bounded_and_no_global_route(monkeypatch):
    monkeypatch.setattr(routes,'get_pipeline_run',lambda _:dict(run_id=999,stages=[dict(stage_key='train_model')]))
    monkeypatch.setattr(logs,'get_stage_logs',lambda *a,**kw:dict(stdout=dict(text='actual output')))
    response=routes.admin_pipeline_stage_logs(999,'train_model',stdout_offset=0,stderr_offset=0,limit=10,admin_user={})
    assert response.headers['cache-control']=='no-store'
    app=FastAPI();app.include_router(routes.router);paths=app.openapi()['paths']
    assert '/admin/pipeline/log' not in paths
    operation=paths['/admin/pipeline/runs/{run_id}/stages/{stage_key}/logs']['get']
    params={p['name']:p['schema'] for p in operation['parameters']}
    assert params['stdout_offset']['minimum']==0 and params['limit']['maximum']==131072
    route=next(r for r in routes.router.routes if r.path.endswith('/{stage_key}/logs'))
    assert routes.require_admin in [d.call for d in route.dependant.dependencies]
