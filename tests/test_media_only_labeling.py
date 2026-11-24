"""Scope/privacy boundaries and representative evidence; no real model requests."""
from unittest.mock import MagicMock, Mock
import hashlib
import numpy as np
import pandas as pd
import pytest
import gpt_utils as gpt
from api.services.dimension_config import require_semantic_media, semantic_media_range
from api.services.dimension_labeling import Evidence
from api.services.dimension_sampling import sample_groups, representative_tail
from api.services import dimension_label_batch as batch
from tests.test_semantic_labeling import context_fixture


def test_ownership_uses_contract_group_not_a_second_fixed_boundary():
    config=dict(media_dimensions=12,user_dimensions=7)
    assert semantic_media_range(config)==(0,12)
    assert require_semantic_media(config,11)==11
    for d in (-1,12,18,True):
        with pytest.raises(ValueError):require_semantic_media(config,d)
    config=context_fixture()[0]
    assert semantic_media_range(config)==(0,768)
    with pytest.raises(ValueError):require_semantic_media(config,768)


def test_media_evidence_constructor_never_reads_users_or_training(monkeypatch):
    from api.services import dimension_labeling as labeling
    ctx=context_fixture()[2];monkeypatch.setattr(labeling,'current_context',lambda c:ctx)
    vector=np.arange(768,dtype='<f4')
    row=dict(id=1,embedding=vector,record=dict(feature_space_id=ctx['feature_space_id'],encoder_digest=ctx['encoder_digest'],vector_sha256=hashlib.sha256(vector.tobytes()).hexdigest()))
    conn=MagicMock();cur=conn.cursor.return_value.__enter__.return_value
    cur.fetchall.side_effect=[[row],[dict(rating_key=1,media_type='movie',plex_guid='plex://movie/a',show_rating_key=None)]]
    metadata=Mock(return_value=pd.DataFrame());monkeypatch.setattr(gpt,'get_media_metadata',metadata)
    users=Mock(side_effect=AssertionError('private evidence read'));monkeypatch.setattr(gpt,'get_user_positive_training_examples',users)
    evidence=Evidence(conn)
    assert set(evidence.vectors)=={'media'}
    queries=' '.join(c.args[0] for c in cur.execute.call_args_list)
    assert 'user_embeddings' not in queries and 'training_data' not in queries and 'watch_history' not in queries
    users.assert_not_called();metadata.assert_called_once_with([1])
    with pytest.raises(ValueError):evidence.prompt(768)


@pytest.mark.parametrize('dimension,scope',[(768,'all'),(1535,'media'),(0,'user')])
def test_explicit_ineligible_requests_stop_before_evidence(monkeypatch,dimension,scope):
    from contextlib import nullcontext
    monkeypatch.setattr(batch,'batch_lock',lambda:nullcontext())
    monkeypatch.setattr(batch,'connect_db',MagicMock())
    monkeypatch.setattr(batch,'get_active_config',lambda c:context_fixture()[0])
    monkeypatch.setattr(gpt,'label_output_limit',lambda n:1024)
    monkeypatch.setattr(gpt,'resolve_label_backend',lambda *a:('ollama','gemma4:31b-cloud'))
    evidence=Mock();monkeypatch.setattr(batch,'Evidence',evidence)
    with pytest.raises(SystemExit):batch.main(['--dry-run','--dimension',str(dimension),'--dim-type',scope])
    evidence.assert_not_called()


@pytest.mark.parametrize('provider',['public','ollama','openai'])
def test_user_provider_admission_precedes_settings_credentials_and_network(monkeypatch,provider):
    resolve=Mock(side_effect=AssertionError('provider resolved'));monkeypatch.setattr(gpt,'resolve_label_backend',resolve)
    settings=Mock(side_effect=AssertionError('credential read'));monkeypatch.setattr(gpt,'get_setting_value',settings)
    fn={'public':gpt.call_llm_for_label_result,'ollama':gpt._call_ollama_for_label_result,'openai':gpt._call_openai_for_label_result}[provider]
    with pytest.raises(ValueError):fn('must not send',model='fictional',dimension_mode='user')
    resolve.assert_not_called();settings.assert_not_called()


def test_representatives_retain_population_extremes_rank_and_tv():
    ids=list(range(1000));values=np.arange(1000,dtype='f4').reshape(-1,1)
    library=[dict(rating_key=k,media_type='movie',plex_guid=f'plex://movie/{k}') for k in ids]
    library += [dict(rating_key=2000,media_type='show',plex_guid='plex://show/series')]
    for k in range(995,1000):library[k]=dict(rating_key=k,media_type='episode',plex_guid=f'plex://episode/{k}',show_rating_key=2000)
    # A duplicate canonical movie is also correlated, even with another local key.
    library[994]['plex_guid']=library[993]['plex_guid']
    groups=sample_groups(library);before=values.copy()
    high=representative_tail(ids,values,0,6,groups);low=representative_tail(ids,values,0,4,groups,True)
    assert high==[999,994,992,991,990,989] and low==[0,1,2,3]
    assert all(k>=950 for k in high) and not set(high)&set(low)
    assert np.array_equal(values,before)
    values[:]=0
    assert not set(representative_tail(ids,values,0,6,groups))&set(representative_tail(ids,values,0,4,groups,True))


def test_no_padding_when_only_one_independent_series_in_tail():
    ids=list(range(1000));values=np.arange(1000,dtype='f4').reshape(-1,1)
    groups={k:dict(canonical=k,family='one series') for k in ids}
    assert representative_tail(ids,values,0,6,groups)==[999]


def test_selected_user_row_cannot_create_batch_or_reserve_request():
    conn=MagicMock()
    with pytest.raises(ValueError):
        batch.execute(conn,Mock(context=context_fixture()[2]),[],[dict(dimension=768,side='media')],None,None,None)
    conn.cursor.assert_not_called()


# Real PostgreSQL queue preservation and diagnostic ownership, using only the named fixture DB.
from tests.test_dimension_explorer import database


def test_historical_user_reviews_are_visible_and_not_dispatched(database,monkeypatch):
    from api.services import dimension_review_worker as worker, dimension_explorer as explorer, dimension_governance as governance
    from fastapi import HTTPException
    connect,config=database
    monkeypatch.setattr(worker,'connect_db',connect)
    lock=Mock(side_effect=AssertionError('historical queue attempted execution'))
    monkeypatch.setattr(worker,'try_acquire_pipeline_lock',lock)
    with connect() as conn,conn.cursor() as q:
        q.execute('''INSERT INTO embedding_dimension_reviews(config_id,dimension,requested_by,reason,status)
            VALUES(%s,800,'fixture','historical','queued'),(%s,801,'fixture','historical','running')''',(config['config_id'],config['config_id']))
    worker.dispatch_review();lock.assert_not_called()
    with connect() as conn,conn.cursor() as q:
        q.execute('SELECT dimension,status FROM embedding_dimension_reviews ORDER BY dimension')
        assert q.fetchall()==[(800,'queued'),(801,'running')]
        q.execute('SELECT count(*) FROM embedding_dimension_actions');before=q.fetchone()[0]
    with pytest.raises(HTTPException) as exc:
        governance.apply_action(config['config_id'],800,'fixture','review','ineligible',0)
    assert exc.value.status_code==409
    data=explorer.get_dimension(800,dict(model_version='legacy',top_n=0))
    assert data['rows'][0]['labeling_scope']=='historical_only' and data['reviews_total']==1
    data=explorer.get_register(dict(model_version='legacy',top_n=0),limit=1)
    assert data['overview']['labeling_inventory_count']==768
    assert data['overview']['historical_only_dimensions']==768
    with connect() as conn,conn.cursor() as q:
        q.execute('SELECT count(*) FROM embedding_dimension_actions');assert q.fetchone()[0]==before


def test_active_prompts_allow_abstention_without_franchise_escape_hatch():
    assert 'one MEDIA embedding dimension' in gpt.SYSTEM_PROMPT
    assert 'correlated evidence' in gpt.SYSTEM_PROMPT
    assert 'For user dimensions' not in gpt.SYSTEM_PROMPT
    assert 'Gossip Girl episode cluster' not in gpt.USER_PROMPT_TEMPLATE
    assert 'unless the label is a very narrow mechanical label' not in gpt.USER_PROMPT_TEMPLATE
    assert 'HIGH end only' in gpt.SYSTEM_PROMPT
