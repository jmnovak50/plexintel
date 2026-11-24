"""Factual connections on disposable PostgreSQL. Never acquire live viewing data."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Event
import json
import os

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from tests.test_metadata_ingestion import db as metadata_db
from api.services import viewing_connections as v

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def db(metadata_db):
    with metadata_db.cursor() as q:
        q.execute('''CREATE TABLE watch_history(watch_id int PRIMARY KEY,username text,rating_key int,
            media_type text,title text,show_rating_key int,played_duration int,watched_at timestamp);
            CREATE INDEX history_owner ON watch_history(username,rating_key);
            CREATE TABLE user_feedback(id serial PRIMARY KEY,username text,rating_key int,feedback text,
                created_at timestamp DEFAULT now(),modified_at timestamp DEFAULT now());
            CREATE INDEX feedback_owner ON user_feedback(username,rating_key);
            CREATE TABLE users(username text PRIMARY KEY);
            CREATE TABLE recommendations(id serial PRIMARY KEY,username text,rating_key int,score float);''')
        q.execute((ROOT/'api/db/migrations/optional/viewing_connections/001_context.sql').read_text())
    metadata_db.commit()
    return metadata_db


def execute(db,sql,params=()):
    with db.cursor() as q:q.execute(sql,params)
    db.commit()


def scalar(db,sql,params=()):
    with db.cursor() as q:q.execute(sql,params);return q.fetchone()[0]


def title(db,key,kind='movie',guid=None,**kwargs):
    data=dict(rating_key=key,title='Film '+str(key),media_type=kind,plex_guid=guid or f'plex://{kind}/{key}',duration=6000000,year=2020,**kwargs)
    with db.cursor() as q:
        q.execute('INSERT INTO library('+','.join(data)+') VALUES('+','.join(['%s']*len(data))+')',list(data.values()))
    db.commit()


def link(db,kind,key,name,order=0):
    table,fk={'cast':('actors','actor_id'),'director':('directors','director_id'),'genre':('genres','genre_id')}[kind]
    with db.cursor() as q:
        q.execute(f'INSERT INTO {table}(name) VALUES(%s) ON CONFLICT(name) DO UPDATE SET name=excluded.name RETURNING id',(name,));person=q.fetchone()[0]
        q.execute(f'INSERT INTO media_{table}(media_id,{fk}'+(',cast_order' if kind=='cast' else '')+') VALUES(%s,%s'+(',%s' if kind=='cast' else '')+')',(key,person,order) if kind=='cast' else (key,person))
    db.commit()


def watch(db,key,owner='alice',played=4000,event=None,**kw):
    with db.cursor() as q:
        q.execute('SELECT media_type,title,show_rating_key FROM library WHERE rating_key=%s',(key,));kind,name,show=q.fetchone()
        if kind=='episode':
            q.execute('SELECT title FROM library WHERE rating_key=%s',(show,));name=q.fetchone()[0]
        q.execute("INSERT INTO watch_history VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(event or key,owner,key,kind,kw.get('title',name),show,played,kw.get('at','2026-11-01 00:00:00')))
    db.commit()


def feedback(db,key,state,owner='alice'):
    execute(db,'INSERT INTO user_feedback(username,rating_key,feedback) VALUES(%s,%s,%s)',(owner,key,state))


def get(db,keys=(2,),owner='alice'):
    return v.lookup(owner,[{'rating_key':k} for k in keys],connect=lambda:psycopg2.connect(db.dsn))


def common(db,kind='cast'):
    title(db,1);title(db,2)
    link(db,kind,1,'Shared Person' if kind!='genre' else 'Drama')
    link(db,kind,2,'Shared Person' if kind!='genre' else 'Drama')
    if kind=='genre':
        link(db,'genre',1,'Action');link(db,'genre',2,'Action')
    watch(db,1)


@pytest.mark.parametrize('relation',['cast','director','genre'])
def test_real_factual_connections_persist_and_reuse(db,monkeypatch,relation):
    common(db,relation)
    first,_=get(db);c=first[2]
    assert c['relationship_type']==relation and c['viewer_evidence']=='watched'
    assert c['source_title']=='Film 1'
    assert 'because' not in c['display_text'] and 'you like' not in c['display_text'].lower()
    assert set(c)=={'relationship_type','source_title','source_media_type','shared_elements','viewer_evidence','display_text','target_scope'}
    monkeypatch.setattr(v,'derive',lambda *a:pytest.fail('Warm read rediscovered history'))
    second,reused=get(db);assert first==second and reused
    assert scalar(db,'SELECT count(*) FROM viewing_connection_context')==1


def test_publication_does_not_own_context(db,monkeypatch):
    common(db);first,_=get(db)
    execute(db,"INSERT INTO recommendations(username,rating_key,score) VALUES('alice',2,.9)")
    execute(db,'TRUNCATE recommendations RESTART IDENTITY')
    execute(db,"INSERT INTO recommendations(username,rating_key,score) VALUES('alice',2,.8)")
    monkeypatch.setattr(v,'derive',lambda *a:pytest.fail('Rescoring invalidated factual context'))
    assert get(db)[0]==first


def test_no_connection_is_cached(db,monkeypatch):
    title(db,1);title(db,2);watch(db,1)
    assert get(db)[0]=={2:None}
    monkeypatch.setattr(v,'derive',lambda *a:pytest.fail('No-result cache missed'))
    assert get(db)[0]=={2:None}
    assert scalar(db,"SELECT status FROM viewing_connection_context")=='none'


@pytest.mark.parametrize('state,expected',[('interested',None),('never_watch',None),('watched_dislike',None),('watched_like','explicitly_liked')])
def test_intent_negative_and_explicit_likes(db,state,expected):
    common(db);execute(db,'DELETE FROM watch_history');feedback(db,1,state)
    c=get(db)[0][2]
    assert (c or {}).get('viewer_evidence')==expected
    if c:assert c['display_text'].startswith('You liked Film 1')


@pytest.mark.parametrize('played,qualifies',[(0,False),(2999,False),(3000,True),(6000,True)])
def test_existing_half_runtime_watching_convention(db,played,qualifies):
    common(db);execute(db,'UPDATE watch_history SET played_duration=%s',(played,))
    assert bool(get(db)[0][2]) is qualifies


def test_negative_change_undo_and_viewer_isolation(db):
    common(db);assert get(db)[0][2]
    assert get(db,owner='bob')[0][2] is None
    feedback(db,1,'watched_dislike');assert get(db)[0][2] is None
    execute(db,'DELETE FROM user_feedback');assert get(db)[0][2]
    execute(db,"UPDATE watch_history SET username='bob'")
    assert get(db)[0][2] is None and get(db,owner='bob')[0][2]


@pytest.mark.parametrize('change',["DELETE FROM watch_history","UPDATE watch_history SET played_duration=0","UPDATE library SET plex_guid='plex://movie/changed' WHERE rating_key=1","DELETE FROM media_actors WHERE media_id=1","UPDATE actors SET name='Corrected Person'"])
def test_source_changes_invalidate_saved_results(db,change):
    common(db);old=get(db)[0][2];execute(db,change);new,reused=get(db)
    assert not reused
    if 'UPDATE actors' in change:assert new[2]['shared_elements']==['Corrected Person']
    elif 'plex_guid' in change:assert new[2]  # Recomputed using current canonical source, never old context.
    else:assert new[2] is None


def test_no_result_invalidates_when_new_metadata_relationship_arrives(db):
    title(db,1);title(db,2);watch(db,1);assert get(db)[0][2] is None
    link(db,'cast',1,'Actor');link(db,'cast',2,'Actor');assert get(db)[0][2]


def test_rolled_back_source_mutation_preserves_cache(db,monkeypatch):
    common(db);first=get(db)[0]
    with db.cursor() as q:q.execute('DELETE FROM watch_history')
    db.rollback()
    monkeypatch.setattr(v,'derive',lambda *a:pytest.fail('Rolled-back mutation invalidated cache'))
    assert get(db)[0]==first


def television(db):
    title(db,10,'show');title(db,11,'season',parent_rating_key=10,show_rating_key=10,season_number=1)
    title(db,12,'episode',parent_rating_key=11,show_rating_key=10,season_number=1,episode_number=1)
    title(db,13,'episode',parent_rating_key=11,show_rating_key=10,season_number=1,episode_number=2)


def test_show_facts_and_continuity_for_all_television_views(db):
    television(db);watch(db,12)
    values={key:get(db,(key,))[0][key] for key in (10,11,13)}
    assert all(c['relationship_type']=='series' for c in values.values())
    assert all(c['display_text']=="You've watched some of Film 10." for c in values.values())
    title(db,2);link(db,'cast',10,'Series Actor');link(db,'cast',2,'Series Actor')
    c=get(db)[0][2];assert c['source_title']=='Film 10' and c['source_media_type']=='show'
    assert 'episode' not in c['display_text'].lower() and 'Series Actor' in c['display_text']


def test_episode_like_is_not_claimed_as_whole_show_like(db):
    television(db);title(db,2);link(db,'cast',10,'Actor');link(db,'cast',2,'Actor');feedback(db,12,'watched_like')
    assert get(db)[0][2]['display_text'].startswith('You liked an episode of Film 10. The series')


@pytest.mark.parametrize('key',[10,11,12])
def test_tv_negative_hierarchy(db,key):
    television(db);watch(db,12);assert get(db,(13,))[0][13]
    feedback(db,key,'watched_dislike');assert get(db,(13,))[0][13] is None


def test_canonical_aliases_coalesce_and_conflicts_abstain(db):
    common(db);title(db,3,guid='plex://movie/1')
    execute(db,"UPDATE library SET title='Film 1' WHERE rating_key=3");link(db,'cast',3,'Shared Person')
    watch(db,3,event=3);assert get(db)[0][2]
    execute(db,"UPDATE library SET title='Different identity' WHERE rating_key=3");assert get(db)[0][2] is None


def test_conflicting_alias_credits_abstain(db):
    common(db);title(db,3,guid='plex://movie/1');execute(db,"UPDATE library SET title='Film 1' WHERE rating_key=3")
    assert get(db)[0][2] is None


@pytest.mark.parametrize('guid',[None,'plex://show/wrong','bad://identity',' plex://movie/1'])
def test_unsupported_or_conflicting_identities_abstain(db,guid):
    common(db);execute(db,'UPDATE library SET plex_guid=%s WHERE rating_key=1',(guid,));assert get(db)[0][2] is None


def test_episode_parent_conflict_abstains(db):
    television(db);watch(db,12);execute(db,'UPDATE library SET season_number=2 WHERE rating_key=12')
    assert get(db,(13,))[0][13] is None


def test_policy_changes_invalidate(db,monkeypatch):
    common(db);get(db);monkeypatch.setattr(v,'POLICY','viewing-history-connections/changed')
    assert not get(db)[1]
    assert scalar(db,'SELECT policy_version FROM viewing_connection_context')==v.POLICY


def test_transaction_generation_detects_out_of_order_commits(db):
    common(db);get(db)
    other=psycopg2.connect(db.dsn)
    try:
        with db.cursor() as q:q.execute("INSERT INTO user_feedback(username,rating_key,feedback) VALUES('bob',2,'interested')")
        with other.cursor() as q:q.execute("INSERT INTO user_feedback(username,rating_key,feedback) VALUES('alice',1,'watched_dislike')")
        other.commit();db.commit()
        assert get(db)[0][2] is None
    finally:other.close()


def test_source_changes_during_derivation_never_publish_stale_result(db,monkeypatch):
    common(db);original=v.derive
    def changed(cur,owner,rows):
        result=original(cur,owner,rows)
        other=psycopg2.connect(db.dsn)
        try:
            with other.cursor() as q:q.execute('DELETE FROM watch_history')
            other.commit()
        finally:other.close()
        return result
    monkeypatch.setattr(v,'derive',changed)
    assert get(db)[0]=={}
    assert scalar(db,'SELECT count(*) FROM viewing_connection_context')==0


def test_concurrent_requests_are_bounded_and_unique(db,monkeypatch):
    common(db);entered=Event();release=Event();original=v.derive
    def slow(*args):
        entered.set();assert release.wait(10);return original(*args)
    monkeypatch.setattr(v,'derive',slow)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(get,db);assert entered.wait(10)
        assert get(db)[0]=={}
        release.set();assert first.result()[0][2]
    assert scalar(db,'SELECT count(*) FROM viewing_connection_context')==1


def test_account_removal_purges_private_context(db):
    common(db);execute(db,"INSERT INTO users VALUES('alice')");get(db)
    execute(db,"DELETE FROM users WHERE username='alice'")
    assert scalar(db,'SELECT count(*) FROM viewing_connection_context')==0


def test_truncation_invalidates_without_changing_predictions(db):
    common(db);get(db);execute(db,'TRUNCATE watch_history')
    assert get(db)[0][2] is None


def test_feature_off_does_no_io_and_keeps_old_contract(monkeypatch):
    monkeypatch.delenv('PLEXINTEL_VIEWING_CONNECTIONS_ENABLED',raising=False)
    monkeypatch.setattr(v,'lookup',lambda *a:pytest.fail('Disabled feature queried persistence'))
    rows=[{'rating_key':1,'score':.9,'explanation':'Old'}];v.attach(rows,'alice')
    assert rows==[{'rating_key':1,'score':.9,'explanation':'Old'}]


def test_failures_abstain_without_breaking_recommendations(monkeypatch):
    monkeypatch.setenv('PLEXINTEL_VIEWING_CONNECTIONS_ENABLED','true')
    def fail(*args):raise psycopg2.OperationalError('private failure details')
    monkeypatch.setattr(v,'lookup',fail)
    rows=[{'rating_key':1,'score':.9}];v.attach(rows,'alice')
    assert rows==[{'rating_key':1,'score':.9,'viewing_history_connection':None}]


def test_genre_combination_and_deterministic_selection(db):
    common(db,'genre')
    first=get(db)[0][2];assert first['shared_elements']==['Action','Drama']
    execute(db,"DELETE FROM viewing_connection_context")
    assert get(db)[0][2]==first


def test_selection_prioritizes_specificity_then_explicit_liking(db):
    common(db,'cast');title(db,3);link(db,'cast',3,'Shared Person');feedback(db,3,'watched_like')
    assert get(db)[0][2]['source_title']=='Film 3'
    link(db,'director',1,'Director');link(db,'director',2,'Director')
    assert get(db)[0][2]['relationship_type']=='director'


def test_recycled_history_key_title_conflict_abstains(db):
    common(db);execute(db,"UPDATE watch_history SET title='Former title identity'")
    assert get(db)[0][2] is None


def test_readonly_preview_does_not_persist_or_allocate_generations(db):
    common(db);db.set_session(readonly=True)
    with db.cursor(cursor_factory=RealDictCursor) as q:result=v.derive(q,'alice',[{'rating_key':2}])
    assert result[2][1] and scalar(db,'SELECT count(*) FROM viewing_connection_context')==0
    db.rollback();db.set_session(readonly=False)


def test_failed_metadata_receipt_does_not_invalidate(db,monkeypatch):
    common(db);first=get(db)[0]
    execute(db,"""INSERT INTO metadata_ingestion_events(operation_id,rating_key,operation,outcome,contract_version,operator,reason)
        VALUES('00000000-0000-0000-0000-000000000001',99,'ingest','failed','test','fixture','failed attempt')""")
    monkeypatch.setattr(v,'derive',lambda *a:pytest.fail('Failure receipt changed factual inputs'))
    assert get(db)[0]==first


def test_bulk_history_change_bumps_each_owner_once(db):
    common(db);watch(db,2,owner='bob');get(db);get(db,owner='bob')
    def generations():
        with db.cursor() as q:q.execute("SELECT owner,revision FROM viewing_connection_state WHERE scope='viewer'");return dict(q.fetchall())
    before=generations();execute(db,'UPDATE watch_history SET played_duration=played_duration+1')
    assert generations()=={k:val+1 for k,val in before.items()}


def test_statement_timeout_abstains_and_can_recover(db,monkeypatch):
    common(db);original=v.DISCOVERY;monkeypatch.setattr(v,'DISCOVERY','SELECT pg_sleep(3)')
    with pytest.raises(psycopg2.errors.QueryCanceled):get(db)
    assert scalar(db,'SELECT count(*) FROM viewing_connection_context')==0
    monkeypatch.setattr(v,'DISCOVERY',original);assert get(db)[0][2]


def test_private_source_state_is_not_in_public_rendering():
    raw={'relationship_type':'cast','shared_names':['Actor'],'shared_ids':[1234],
        'source_identity':'movie:plex://movie/private','source_title':'A <title>','source_media_type':'movie',
        'source_year':2020,'evidence':{'basis':'watched','event_count':99,'fraction':1,'last_seen':'private'}}
    public=v.present(raw)
    assert all(secret not in json.dumps(public) for secret in ('1234','plex://','last_seen','event_count','fraction'))
    assert public['display_text']=="You've watched A <title>, which also features Actor."


@pytest.mark.parametrize('view',['all','movies','shows','seasons','episodes'])
def test_enabled_session_enrichment_preserves_page_and_query_contract(monkeypatch,view):
    from types import SimpleNamespace
    from api.routes import recommendation_routes as r
    row={'rating_key':2,'title':'Film 2','scored_at':None,'predicted_probability':.9,'title_traits':['Old trait'],'taste_match':['Old match']}
    class Cursor:
        closed=False
        def __init__(self):self.calls=[]
        def execute(self,sql,params=None):self.calls.append((sql,params))
        def fetchall(self):return [deepcopy(row),dict(row,rating_key=3)] if len(self.calls)==1 else []
        def close(self):self.closed=True
    class Conn:
        closed=False
        def __init__(self):self.q=Cursor()
        def cursor(self,**kw):return self.q
        def close(self):self.closed=True
    conn=Conn();monkeypatch.setattr(r,'connect_db',lambda:conn);monkeypatch.setattr(r,'register_vector',lambda c:None)
    monkeypatch.setattr(r,'get_plex_username',lambda token,**kwargs:'alice');monkeypatch.setattr(r,'get_default_display_threshold',lambda:.7)
    monkeypatch.setattr(r,'fetch_score_model_refresh_status',lambda q:False)
    monkeypatch.setattr(r,'_decorate_recommendation_rows',lambda rows:None)
    monkeypatch.setenv('PLEXINTEL_VIEWING_CONNECTIONS_ENABLED','true')
    calls=[]
    def lookup(owner,rows):
        calls.append((owner,[x['rating_key'] for x in rows]));return {2:{'display_text':'Factual context'}},set()
    monkeypatch.setattr(v,'lookup',lookup)
    response=r.get_recommendations(SimpleNamespace(session={'plex_token':'fixture'}),view=view,show_rating_key=None,season_rating_key=None,search=None,limit=1,offset=0,sort=None,min_probability=None,max_probability=None)
    assert calls==[('alice',[2])]  # Paging sentinel never enters discovery.
    assert response['has_more'] and response['next_offset']==1
    got=response['recommendations'][0];assert {k:got[k] for k in row}==row
    assert got['viewing_history_connection']['display_text']=='Factual context'
    from api.services.recommendation_query_service import _build_recommendations_query
    expected,params=_build_recommendations_query(username='alice',view=view,show_rating_key=None,season_rating_key=None,search=None,sort=None,display_threshold=.7)
    assert conn.q.calls[0]==(expected+' LIMIT %s OFFSET %s',tuple(params+[2,0]))


def test_session_requires_auth_before_connection_access(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from api.routes import recommendation_routes as r
    monkeypatch.setenv('PLEXINTEL_VIEWING_CONNECTIONS_ENABLED','true')
    monkeypatch.setattr(v,'lookup',lambda *a:pytest.fail('Anonymous history lookup'))
    with pytest.raises(HTTPException) as failure:r.get_recommendations(SimpleNamespace(session={}))
    assert failure.value.status_code==401


def test_authorized_agent_and_digest_keep_semantic_fields(monkeypatch):
    from api.services import agent_tool_service as a,digest_service as d
    from tests.test_agent_tool_service import FakeConnection
    row={'rating_key':2,'title':'Film 2','media_type':'movie','predicted_probability':.9,'semantic_themes':'Original theme'}
    monkeypatch.setattr(a,'_get_conn',lambda:FakeConnection([row.copy()]))
    monkeypatch.setenv('PLEXINTEL_VIEWING_CONNECTIONS_ENABLED','true')
    monkeypatch.setattr(v,'lookup',lambda user,rows:({2:{'display_text':'A shared credit.'}},set()))
    response=a.get_agent_recommendations(user='alice')
    assert response.items[0].explanation=='Original theme'
    assert response.items[0].viewing_history_connection=={'display_text':'A shared credit.'}
    text=d._build_item_subtitle(dict(row,viewing_history_connection={'display_text':'A shared credit.'}))
    assert 'Original theme' not in text and 'Connections to Your Viewing History' not in text
    html=d._render_item_card(dict(row,viewing_history_connection={'display_text':'A shared credit.'}))
    assert 'Taste Match' in html and 'A shared credit.' in html


def test_context_refresh_endpoint_is_session_scoped_and_bounded(db,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.sessions import SessionMiddleware
    from api.routes import recommendation_routes as r
    common(db);title(db,99)
    execute(db,"INSERT INTO recommendations(username,rating_key,score) VALUES('alice',2,.9),('bob',99,.9)")
    app=FastAPI();app.add_middleware(SessionMiddleware,secret_key='fixture-only-signing-key')
    app.include_router(r.router,prefix='/api')
    @app.get('/fixture-login')
    def login(request:__import__('starlette.requests',fromlist=['Request']).Request):
        request.session['plex_token']='fixture';return {}
    monkeypatch.setenv('PLEXINTEL_VIEWING_CONNECTIONS_ENABLED','true')
    monkeypatch.setattr(r,'get_plex_username',lambda token,**kwargs:'alice')
    monkeypatch.setattr(r,'connect_db',lambda:psycopg2.connect(db.dsn))
    original=v.lookup
    monkeypatch.setattr(v,'lookup',lambda username,rows:original(username,rows,connect=lambda:psycopg2.connect(db.dsn)))
    with TestClient(app) as client:
        path='/api/recommendations/viewing-history-connections'
        assert client.get(path,params={'rating_key':2}).status_code==401
        client.get('/fixture-login')
        response=client.get(path,params=[('rating_key',2),('rating_key',99),('user','bob')])
        assert response.status_code==200
        assert set(response.json()['connections'])=={'2'}
        assert response.json()['connections']['2']['source_title']=='Film 1'
        assert client.get(path,params=[('rating_key',2)]*251).status_code==422
        execute(db,'DELETE FROM watch_history')
        assert client.get(path,params={'rating_key':2}).json()['connections']['2'] is None


def test_approved_metadata_correction_and_inverse_invalidate_atomically(db):
    from api.services import metadata_ingestion as m
    common(db);assert get(db)[0][2]
    person=scalar(db,"SELECT id FROM actors WHERE name='Shared Person'")
    with db.cursor() as q:
        plan=m.make_plan(q,1,operator='fixture',reason='Approved scoped removal',relationships={'actors':{'action':'remove','values':[person]}})
        m.apply_plan(q,plan)
    db.commit();assert get(db)[0][2] is None
    event=scalar(db,"SELECT max(event_id) FROM metadata_ingestion_events WHERE operation='correct' AND outcome='applied'")
    with db.cursor() as q:
        inverse=m.inverse_plan(q,event,operator='fixture',reason='Approved scoped inverse')
        m.apply_plan(q,inverse)
    db.commit();assert get(db)[0][2]
    assert scalar(db,'SELECT count(*) FROM recommendations')==0


def test_new_accepted_title_recovers_previously_unlinked_watching(db):
    from api.services import metadata_ingestion as m
    from tests.test_metadata_ingestion import item
    from uuid import uuid4
    title(db,2);link(db,'cast',2,'Shared Person')
    execute(db,"""INSERT INTO watch_history VALUES(1,'alice',1,'movie','Fixture 1',NULL,4000,'2026-11-01')""")
    assert get(db)[0][2] is None
    candidate=item(1,actors=['Shared Person'])
    with db.cursor() as q:m.accept(q,candidate,operation_id=uuid4())
    db.commit()
    assert get(db)[0][2]['source_title']=='Fixture 1'


@pytest.mark.parametrize('kind',['cast','director','genre'])
def test_episode_card_explicitly_names_target_series_fact_scope(db,kind):
    television(db);title(db,1);watch(db,1)
    link(db,kind,1,'Shared');link(db,kind,10,'Shared')
    if kind=='genre':
        link(db,'genre',1,'Other');link(db,'genre',10,'Other')
    c=get(db,(13,))[0][13]
    assert c['target_scope']=={'title':'Film 10','media_type':'show'}
    assert 'the series Film 10' in c['display_text']
    assert 'Film 13' not in c['display_text']
    assert c['source_media_type']=='movie'


def test_single_shared_genre_abstains_and_reuses_no_result(db,monkeypatch):
    title(db,1);title(db,2);watch(db,1)
    link(db,'genre',1,'Comedy');link(db,'genre',2,'Comedy')
    assert get(db)[0]=={2:None}
    assert scalar(db,"SELECT status FROM viewing_connection_context")=='none'
    monkeypatch.setattr(v,'derive',lambda *args:pytest.fail('Single-genre abstention rediscovered'))
    assert get(db)[0]=={2:None}


def test_target_cast_prominence_precedes_raw_event_count(db):
    for key in (1,2,3):title(db,key)
    link(db,'cast',1,'Small target role',order=0);link(db,'cast',2,'Small target role',order=20)
    link(db,'cast',3,'Prominent target role',order=0);link(db,'cast',2,'Prominent target role',order=0)
    for event in range(10):watch(db,1,played=6000,event=100+event)
    watch(db,3,played=6000)
    c=get(db)[0][2]
    assert c['shared_elements']==['Prominent target role']
    assert c['source_title']=='Film 3'


def test_source_cast_prominence_breaks_tie_before_event_count(db):
    for key in (1,2,3):title(db,key)
    link(db,'cast',1,'Actor',order=30);link(db,'cast',2,'Actor',order=0);link(db,'cast',3,'Actor',order=0)
    for event in range(10):watch(db,1,played=6000,event=100+event)
    watch(db,3,played=6000)
    assert get(db)[0][2]['source_title']=='Film 3'


def test_unknown_cast_order_is_available_but_known_order_wins(db):
    for key in (1,2,3):title(db,key)
    link(db,'cast',1,'Unknown role',order=None);link(db,'cast',2,'Unknown role',order=None)
    watch(db,1,played=6000);assert get(db)[0][2]
    link(db,'cast',3,'Known role',order=0);link(db,'cast',2,'Known role',order=0);watch(db,3,played=6000)
    assert get(db)[0][2]['shared_elements']==['Known role']


def test_repetition_suppression_preserves_every_saved_selection(db,monkeypatch):
    common(db);title(db,3);link(db,'cast',3,'Shared Person')
    first,_=get(db,(3,2));assert first[3] and first[2] is None
    assert scalar(db,"SELECT count(*) FROM viewing_connection_context WHERE status='ready'")==2
    monkeypatch.setattr(v,'derive',lambda *args:pytest.fail('Suppression discarded a saved selection'))
    assert get(db,(3,2))[0]==first
    assert get(db,(2,))[0][2]  # A different page can reuse the suppressed choice.
    reverse=get(db,(2,3))[0];assert reverse[2] and reverse[3] is None


def test_same_actor_from_different_sources_is_still_repetitive(db):
    for key in (1,2,3,4):title(db,key)
    for key in (1,2,3,4):link(db,'cast',key,'Actor')
    watch(db,1);watch(db,3)
    result=get(db,(2,4))[0]
    assert sum(bool(c) for c in result.values())==1


def test_series_repetition_and_short_wording(db):
    television(db);watch(db,12)
    result=get(db,(13,11,10))[0]
    assert result[13]['display_text']=="You've watched some of Film 10."
    assert result[11] is None and result[10] is None
    assert scalar(db,"SELECT count(*) FROM viewing_connection_context WHERE status='ready'")==3


@pytest.mark.parametrize('kind',['cast','director','genre'])
def test_episode_like_sentence_never_attaches_series_credit_to_episode(db,kind):
    television(db);title(db,2);feedback(db,12,'watched_like')
    link(db,kind,10,'Shared');link(db,kind,2,'Shared')
    if kind=='genre':link(db,kind,10,'Other');link(db,kind,2,'Other')
    text=get(db)[0][2]['display_text']
    assert text.startswith('You liked an episode of Film 10. The series')
    assert 'episode of Film 10, which' not in text
    assert 'because' not in text


def test_policy_two_replaces_old_results_once_without_source_mutation(db,monkeypatch):
    common(db);get(db)
    execute(db,"UPDATE viewing_connection_context SET policy_version='viewing-history-connections/1'")
    before=scalar(db,'SELECT count(*) FROM watch_history')
    original=v.derive;calls=[]
    def counted(*args):calls.append(1);return original(*args)
    monkeypatch.setattr(v,'derive',counted)
    assert get(db)[0][2] and get(db)[0][2]
    assert calls==[1] and scalar(db,'SELECT count(*) FROM watch_history')==before
    assert scalar(db,'SELECT policy_version FROM viewing_connection_context')=='viewing-history-connections/2'


def test_different_facts_from_one_source_are_not_arbitrarily_limited(db):
    for key in (1,2,3):title(db,key)
    link(db,'cast',1,'Actor A');link(db,'cast',1,'Actor B',order=1)
    link(db,'cast',2,'Actor A');link(db,'cast',3,'Actor B')
    watch(db,1)
    result=get(db,(2,3))[0]
    assert result[2] and result[3]
    assert result[2]['shared_elements']!=result[3]['shared_elements']


def test_same_series_liked_episode_wording_is_short_and_scoped(db):
    television(db);feedback(db,12,'watched_like')
    assert get(db,(13,))[0][13]['display_text']=='You liked an episode of Film 10.'


def test_independent_refresh_preserves_requested_presentation_order(db,monkeypatch):
    from types import SimpleNamespace
    from api.routes import recommendation_routes as r
    common(db);title(db,3);link(db,'cast',3,'Shared Person')
    execute(db,"INSERT INTO recommendations(username,rating_key,score) VALUES('alice',2,.9),('alice',3,.8)")
    monkeypatch.setenv('PLEXINTEL_VIEWING_CONNECTIONS_ENABLED','true')
    monkeypatch.setattr(r,'get_plex_username',lambda token,**kwargs:'alice')
    monkeypatch.setattr(r,'connect_db',lambda:psycopg2.connect(db.dsn))
    original=v.lookup
    monkeypatch.setattr(v,'lookup',lambda owner,rows:original(owner,rows,connect=lambda:psycopg2.connect(db.dsn)))
    request=SimpleNamespace(session={'plex_token':'fixture'})
    response=r.get_viewing_history_connections(request,[3,2])
    assert list(response['connections'])==[3,2]
    assert response['connections'][3] and response['connections'][2] is None
    reverse=r.get_viewing_history_connections(request,[2,3])
    assert reverse['connections'][2] and reverse['connections'][3] is None
