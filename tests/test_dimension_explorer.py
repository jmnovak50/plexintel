"""Fixtures only. Integration tests require a dedicated, explicitly named test database."""
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from psycopg2.extras import Json
import psycopg2

from api.services.dimension_config import build_metadata, identity
from api.services import dimension_explorer as explorer
from api.services import dimension_governance as governance
from api.routes import dimension_admin_routes, admin_routes


def metadata():
    return build_metadata([f'emb_{i}' for i in range(1536)] + ['genre_Action','watch_sim'],768,768,'fixture-embedding-model','fixture-model-version')


def test_inventory_contract():
    config = metadata()
    assert identity(config,0) == dict(dimension=0,feature_name='emb_0',side='media',local_index=0)
    assert identity(config,767)['local_index'] == 767
    assert identity(config,768)['side'] == 'user'
    assert identity(config,768)['local_index'] == 0
    assert identity(config,1535)['local_index'] == 767
    with pytest.raises(ValueError):
        identity(config,1536)
    with pytest.raises(ValueError):
        build_metadata(['emb_1','emb_0'],1,1,'fixture','sha')
    # Inventory is metadata-derived, not a fixed count.
    assert identity(build_metadata(['emb_0','emb_1','emb_2','emb_3'],2,2,'fixture','sha'),3)['local_index'] == 1


def test_admin_routes_guard_every_read_and_action():
    app = FastAPI()
    app.include_router(dimension_admin_routes.router)
    app.dependency_overrides[admin_routes.get_current_user] = lambda: {'username':'ordinary','is_admin':False}
    client = TestClient(app)
    for url in ['/admin/dimensions','/admin/dimensions/1','/admin/dimensions/prediction?username=a&rating_key=1&scored_at=x']:
        assert client.get(url).status_code == 403
    assert client.post('/admin/dimensions/1/actions',json=dict(config_id='x',version=0,action='pause',reason='fixture')).status_code == 403
    def anonymous():
        raise HTTPException(401,'Not signed in')
    app.dependency_overrides[admin_routes.get_current_user] = anonymous
    assert client.get('/admin/dimensions').status_code == 401


@pytest.fixture
def database(monkeypatch):
    dsn = os.getenv('EXPLORER_TEST_DATABASE_URL')
    if not dsn:
        pytest.skip('EXPLORER_TEST_DATABASE_URL not set; isolated PostgreSQL required')
    if psycopg2.extensions.parse_dsn(dsn).get('dbname') != 'plexintel_explorer_fixture':
        pytest.fail('Refusing any database except plexintel_explorer_fixture')
    def connect(**kwargs):
        return psycopg2.connect(dsn,**kwargs)
    monkeypatch.setattr(explorer,'connect_db',connect)
    monkeypatch.setattr(governance,'connect_db',connect)
    from api.db.schema import apply_dimension_schema
    with connect() as conn:
        apply_dimension_schema(conn)
        # Repeat to test idempotency with data intact.
        apply_dimension_schema(conn)
        with conn.cursor() as cur:
            cur.execute('''TRUNCATE embedding_dimension_assessments,embedding_dimension_actions,
                embedding_dimension_reviews,embedding_dimension_admin,embedding_feature_config,
                shap_prediction_context,shap_impact,embedding_label_history,embedding_labels,
                recommendations,library,users,watch_history,shap_dimension_stats_current CASCADE''')
            config = metadata()
            cur.execute('INSERT INTO embedding_feature_config(config_id,metadata,active) VALUES (%s,%s,true)', (config['config_id'],Json(config)))
            cur.execute("INSERT INTO library(rating_key,title,media_type) VALUES (101,'Fixture Movie','movie'),(102,'Fixture Episode','episode'),(103,'Fixture Show','show')")
            cur.execute("INSERT INTO watch_history(watch_id,username,friendly_name,rating_key) VALUES (1,'fixture-a','Fixture A',999),(2,'fixture-b','Fixture B',999)")
            cur.execute("INSERT INTO users(user_id,username) VALUES (1,'fixture-a'),(2,'fixture-b')")
            cur.execute("""INSERT INTO recommendations(id,username,rating_key,predicted_probability,rank,scored_at) VALUES
                (1,'fixture-a',101,0.9,1,'2026-09-01'),(2,'fixture-a',102,0.8,2,'2026-09-01'),
                (3,'fixture-b',101,0.7,1,'2026-09-01'),(4,'fixture-a',103,0.6,3,'2026-09-01')""")
            cur.execute("""INSERT INTO embedding_labels(dimension,label,display_label,label_type,explainable,needs_review) VALUES
                (0,'Shared wording','Shared wording','semantic',true,false),
                (1,'Shared wording','Shared wording','semantic',true,false),
                (2,'Second wording','Second wording','semantic',true,false),
                (3,'Third wording','Third wording','semantic',true,false),
                (4,'Fourth wording','Fourth wording','semantic',true,false),
                (768,'Preference for spacecraft','spacecraft','semantic',true,false),
                (769,'Review fixture','Review fixture','weak',false,true)""")
            cur.execute("UPDATE embedding_labels SET review_attempt_count=4,last_reviewed_at=now(),next_review_at=now()+interval '7 days' WHERE dimension=769")
            cur.execute("""INSERT INTO shap_impact(user_id,rating_key,dimension,shap_value) VALUES
                ('fixture-a',101,0,0.8),('fixture-a',101,1,0.7),('fixture-a',101,2,0.6),
                ('fixture-a',101,3,0.5),('fixture-a',101,4,0.4),('fixture-a',101,768,0.9),
                ('fixture-a',102,0,-0.2),('fixture-a',102,1,0),('fixture-b',101,0,0.4),
                ('fixture-a',103,0,0.2)""")
            cur.execute("INSERT INTO embedding_label_history(dimension,old_label,new_label,change_reason) VALUES (0,'Older wording','Shared wording','fixture'),(0,'Even older','Older wording','fixture')")
    return connect, config


def test_full_inventory_search_scope_and_no_join_multiplication(database):
    data = explorer.get_register(dict(top_n=0),limit=100)
    assert data['total'] == data['overview']['inventory_count'] == 1536
    assert data['overview']['unlabeled'] == 1529
    rows = explorer.get_register(dict(top_n=0),search='Shared wording')['rows']
    assert [row['dimension'] for row in rows] == [0,1]
    assert rows[0]['observed_count'] == 4  # user/title instances, not unique titles
    assert rows[0]['positive_count'] == 3 and rows[0]['negative_count'] == 1
    assert rows[0]['mean_abs_shap'] == pytest.approx(0.4)
    assert rows[0]['selected_count'] == 2  # show API rollup remains empty
    assert rows[1]['zero_count'] == 1
    assert rows[1]['selected_count'] == 1
    assert data['overview']['selected_wordings'] == 5  # shared wording is not counted twice
    missing = explorer.get_register(dict(top_n=0),dimension=1535)['rows'][0]
    assert missing['side']=='user' and missing['local_index']==767
    assert missing['observed_count']==0 and missing['mean_abs_shap'] is None
    scoped = explorer.get_register(dict(top_n=1,username='fixture-a',media_type='movie'),search='0')['rows'][0]
    assert scoped['observed_count']==1 and scoped['positive_count']==1
    assert explorer.get_register(dict(top_n=0),search='user:0')['rows'][0]['dimension']==768
    assert explorer.get_register(dict(top_n=0),offset=1500)['total']==1536


def test_production_selection_attribution_rollups_and_suppression(database):
    connect, config = database
    detail = explorer.get_prediction('fixture-a',101,'2026-09-01T00:00:00','legacy')
    title = [row for row in detail['selected'] if row['group_name']=='title_traits']
    assert [r['display_label'] for r in title]==['Shared wording','Second wording','Third wording']
    assert title[0]['dimensions']==[0,1]
    assert not [r for r in explorer.get_prediction('fixture-a',103,'2026-09-01T00:00:00','legacy')['selected'] if r['group_name']!='semantic_themes']
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT predicted_probability,rank FROM recommendations ORDER BY id')
        scores = cur.fetchall()
        cur.execute("SELECT semantic_themes FROM expanded_recs_w_label_v WHERE username='fixture-a' AND rating_key=101")
        assert cur.fetchone()[0]=='spacecraft, Shared wording, Second wording'
    governance.apply_action(config['config_id'],0,'fixture-admin','suppress','fixture reason',0)
    after = explorer.get_prediction('fixture-a',101,'2026-09-01T00:00:00','legacy')
    shared = [row for row in after['selected'] if row['group_name']=='title_traits' and row['display_label']=='Shared wording'][0]
    assert shared['dimensions']==[1]
    governance.apply_action(config['config_id'],1,'fixture-admin','suppress','fixture reason',0)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT semantic_themes FROM expanded_recs_w_label_v WHERE username='fixture-a' AND rating_key=101")
        assert 'Shared wording' not in cur.fetchone()[0]
        cur.execute("UPDATE embedding_labels SET label='Automatic replacement',display_label='Automatic replacement' WHERE dimension=0")
        cur.execute('SELECT predicted_probability,rank FROM recommendations ORDER BY id')
        assert cur.fetchall()==scores
    assert not explorer.get_register(dict(top_n=0),dimension=0)['rows'][0]['eligible']
    # Restoring does not force automatic eligibility.
    governance.apply_action(config['config_id'],769,'fixture-admin','suppress','fixture',0)
    governance.apply_action(config['config_id'],769,'fixture-admin','restore','fixture',1)
    assert not explorer.get_register(dict(top_n=0),dimension=769)['rows'][0]['eligible']
    with pytest.raises(HTTPException) as stale:
        explorer.get_prediction('fixture-a',101,'2020-01-01T00:00:00','legacy')
    assert stale.value.status_code==409


def test_review_queue_audit_stale_actions_and_pause_race(database):
    connect, config = database
    cid = config['config_id']
    first = governance.apply_action(cid,769,'fixture-admin','review','Assess this dimension',0)
    again = governance.apply_action(cid,769,'fixture-admin','review','Repeated click',0)
    assert first['review_id']==again['review_id'] and first['status']=='queued'
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM embedding_dimension_reviews'); assert cur.fetchone()[0]==1
        cur.execute('SELECT actor,reason,before_state,after_state FROM embedding_dimension_actions')
        action = cur.fetchone(); assert action[0]=='fixture-admin' and action[1]=='Assess this dimension'
        assert action[2]['version']==0 and action[3]['version']==1
    with pytest.raises(HTTPException) as stale:
        governance.apply_action(cid,769,'fixture-admin','pause','Stale state',0)
    assert stale.value.status_code==409
    with connect() as running, running.cursor() as cur:
        with governance.dimension_review_guard(cur,769) as allowed:
            assert allowed
            with connect() as second, second.cursor() as other:
                with governance.dimension_review_guard(other,769) as duplicate:
                    assert not duplicate
            governance.apply_action(cid,769,'fixture-admin','pause','Investigate evidence',1)
            cur.execute("UPDATE embedding_labels SET label='Valid replacement',needs_review=true,review_attempt_count=review_attempt_count+1 WHERE dimension=769")
            running.commit()
    detail = explorer.get_dimension(769,dict(top_n=0))
    row = detail['rows'][0]
    assert row['paused'] and row['needs_review'] and row['cooldown']
    with connect() as conn, conn.cursor() as cur:
        with governance.dimension_review_guard(cur,769) as allowed:
            assert not allowed
    governance.apply_action(cid,769,'fixture-admin','resume','Resume normal due date',2)
    row = explorer.get_dimension(769,dict(top_n=0))['rows'][0]
    assert not row['paused'] and row['cooldown']
    governance.apply_action(cid,769,'fixture-admin','investigate','Evidence concern',3)
    flagged = explorer.get_dimension(769,dict(top_n=0))['rows'][0]
    assert flagged['investigation_status']=='open' and flagged['cooldown'] and not flagged['suppressed']


def test_new_contexts_do_not_mix_models_legacy_or_stale_predictions(database):
    connect,config = database
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO shap_prediction_context(username,rating_key,config_id,model_version,scored_at) VALUES
            ('fixture-a',101,%s,'version-one','2026-09-01'),
            ('fixture-b',101,%s,'version-two','2026-09-01'),
            ('fixture-a',102,%s,'version-one','2020-01-01')""",[config['config_id']]*3)
    one = explorer.get_register(dict(top_n=0,model_version='version-one'),dimension=0)
    assert one['rows'][0]['observed_count']==1
    assert one['overview']['scoped_predictions']==1
    legacy = explorer.get_register(dict(top_n=0,model_version='legacy'),dimension=0)
    assert legacy['rows'][0]['observed_count']==1 # show only; stale context is excluded
    assert len(one['model_versions'])==2


def test_real_save_retains_valid_unresolved_evidence_and_overrides(database):
    import batch_label_embeddings as batch
    import pandas as pd
    connect, config = database
    cid = config['config_id']
    governance.apply_action(cid,0,'fixture-admin','suppress','Fixture override',0)
    governance.apply_action(cid,0,'fixture-admin','pause','Fixture pause during review',1)
    result = dict(label='prestige tv drama episodes',label_type='soft_structural',validation_status='valid',validation_notes=[])
    with connect() as conn, conn.cursor() as cur:
        before = batch.get_existing_label_row(cur,0)
        saved,outcome = batch.save_label_result(cur,0,result,review_mode=True)
        after = batch.get_existing_label_row(cur,0)
        governance.record_assessment(cur,0,source='fixture',provider='fixture',model='fixture',
            prompt=dict(prompt_text='ACTUAL FIXTURE PROMPT',positive_items=pd.DataFrame([dict(title='Fixture Movie',played_duration=1000,engagement_ratio=0.75,training_label=1)]),negative_items=pd.DataFrame(),valid_positive_count=1,valid_negative_count=0,flagged_item_count=0),
            result=result,saved=saved,outcome=outcome,before=before,after=after)
    assert saved and outcome=='updated_review_label_cooldown_scheduled'
    data = explorer.get_dimension(0,dict(top_n=0))
    row = data['rows'][0]
    assert row['paused'] and row['suppressed'] and row['needs_review'] and row['cooldown']
    assert row['validation_status']=='valid' and not row['eligible']
    assert data['assessments'][0]['prompt']['positive_items'][0]['played_duration']==1000
    assert data['assessments'][0]['before_state']['label']=='Shared wording'
    assert data['assessments'][0]['after_state']['needs_review'] is True


def test_all_automatic_candidate_modes_and_single_cli_respect_pause(database,monkeypatch):
    import batch_label_embeddings as batch
    import label_embeddings as single
    connect,config = database
    governance.apply_action(config['config_id'],769,'fixture-admin','pause','Fixture pause',0)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("UPDATE embedding_labels SET next_review_at=now()-interval '1 day' WHERE dimension=769")
        cur.execute("INSERT INTO shap_impact(user_id,rating_key,dimension,shap_value) VALUES ('fixture-a',102,769,2)")
        for mode in ['importance','coverage','hybrid','review','eligible']:
            selected,_ = batch.select_automatic_dimensions(cur,limit=10,selection_mode=mode,include_labeled=True)
            assert 769 not in [row['dimension'] for row in selected], mode
    monkeypatch.setattr(single,'connect_db',connect)
    with patch.object(single,'_label_single_dimension') as execute:
        single.label_single_dimension(769,generate_label=True,save_label=True)
        execute.assert_not_called()


def test_dispatcher_uses_exact_request_outcome_and_distinguishes_progress(database,monkeypatch,tmp_path):
    from types import SimpleNamespace
    from api.services import dimension_review_worker as worker
    connect, config = database
    monkeypatch.setattr(worker,'connect_db',connect)
    monkeypatch.setattr(worker,'_append_pipeline_log',lambda text: (tmp_path/'fixture-worker.log').write_text(text))
    class Lock:
        def __init__(self):
            self.handle = (tmp_path/'fixture.lock').open('w')
        def release(self):
            self.handle.close()
    monkeypatch.setattr(worker,'try_acquire_pipeline_lock',lambda **kw: Lock())
    job = governance.apply_action(config['config_id'],769,'fixture-admin','review','Fixture assessment',0)
    def process(args,**kwargs):
        assert '--dimension' in args and '769' in args and '--selection_mode' in args
        assert kwargs['pass_fds']
        with patch.dict(os.environ,kwargs['env']):
            with connect() as conn, conn.cursor() as cur:
                governance.record_assessment(cur,769,source='review',provider='fixture',model='fixture',
                    prompt=dict(prompt_text='fixture'),result=dict(validation_status='invalid'),
                    saved=False,outcome='repair_cooldown_scheduled',before=dict(needs_review=True),after=dict(needs_review=True))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(worker.subprocess,'run',process)
    worker.dispatch_review()
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT status,outcome FROM embedding_dimension_reviews WHERE review_id=%s',(job['review_id'],))
        assert cur.fetchone()==('completed','repair_cooldown_scheduled')
        cur.execute('SELECT review_id FROM embedding_dimension_assessments')
        assert cur.fetchone()[0]==job['review_id']
    # Completed execution with zero resolutions is not presented as review progress.
    row = explorer.get_dimension(769,dict(top_n=0))['rows'][0]
    assert row['job_status']=='completed' and row['needs_review']


def test_register_query_plan_uses_scoped_retained_observations(database):
    connect,config = database
    sql,params = explorer.register_cte(dict(top_n=100,username='fixture-a',model_version='legacy'),config)
    with connect() as conn, conn.cursor() as cur:
        cur.execute('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) ' + sql + ' SELECT * FROM register ORDER BY observed_count DESC LIMIT 50',params)
        plan = cur.fetchone()[0][0]
        assert plan['Plan']['Actual Rows']==50
        print('Fixture register plan execution ms:',plan['Execution Time'])
        assert plan['Execution Time'] < 5000  # generous fixture-only regression ceiling


def test_simultaneous_requests_enqueue_once_and_automatic_inflight_is_visible(database):
    from concurrent.futures import ThreadPoolExecutor
    connect,config = database
    def request(_):
        return governance.apply_action(config['config_id'],0,'fixture-admin','review','Concurrent fixture request',0)['review_id']
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(set(pool.map(request,range(2))))==1
    with connect() as conn, conn.cursor() as cur:
        with governance.dimension_review_guard(cur,0) as allowed:
            assert allowed
            assert explorer.get_register(dict(top_n=0),dimension=0)['rows'][0]['in_flight']
    assert not explorer.get_register(dict(top_n=0),dimension=0)['rows'][0]['in_flight']


def test_duplicate_label_rows_do_not_expand_the_dimension_inventory(database):
    connect,_ = database
    with connect() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO embedding_labels(dimension,label,display_label,explainable,needs_review) VALUES (0,'Shared wording','Shared wording',true,false)")
    data = explorer.get_register(dict(top_n=0),search='Shared wording')
    assert data['total']==2 and data['overview']['inventory_count']==1536
    assert data['rows'][0]['observed_count']==4 and data['rows'][0]['label_row_count']==2
    assert data['overview']['selected_wordings']==5


def test_prospective_context_writer_leaves_predictions_and_shap_unchanged(database,monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from api.services import dimension_scoring_context as context
    connect,config = database
    monkeypatch.setattr(context,'get_setting_value',lambda key: config['embedding_model'])
    model = SimpleNamespace(get_booster=lambda: SimpleNamespace(feature_names=config['feature_names']))
    with connect() as conn, conn.cursor() as cur:
        cur.execute('SELECT * FROM recommendations ORDER BY id'); predictions = cur.fetchall()
        cur.execute('SELECT * FROM shap_impact ORDER BY user_id,rating_key,dimension'); impacts = cur.fetchall()
        context.persist_scoring_context(cur,model,b'fixture-model-bytes',768,768,'fixture-a',[(101,datetime(2026,9,1))])
        cur.execute('SELECT * FROM recommendations ORDER BY id'); assert cur.fetchall()==predictions
        cur.execute('SELECT * FROM shap_impact ORDER BY user_id,rating_key,dimension'); assert cur.fetchall()==impacts
        cur.execute('SELECT COUNT(*) FROM shap_prediction_context'); assert cur.fetchone()[0]==1
    data = explorer.get_register(dict(top_n=0))
    assert data['scope']['model_version']==hashlib.sha256(b'fixture-model-bytes').hexdigest()
    assert data['overview']['scoped_predictions']==1
    assert explorer.get_register(dict(top_n=0,model_version='legacy'))['overview']['scoped_predictions']==3
