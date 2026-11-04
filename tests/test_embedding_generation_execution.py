from dataclasses import asdict,replace
from copy import deepcopy
import json
from unittest.mock import Mock
import numpy as np
import pytest
from psycopg2 import sql
from api.embedding_generation.contracts import contract,fingerprint,modality_contract,embedding_input_hash,ContractError
from api.embedding_generation.io import Ollama
from api.embedding_generation import execution
from api.embedding_generation.backfill import run_media_poster,run_media_text
from tests.test_embedding_generation import unit
from tests.test_embedding_generation_database import store,encoder,prepared_fixture,run_both


def test_thread_execution_identity_is_separate_without_rehashing_legacy_contracts(encoder):
    original=asdict(encoder);spec=contract(encoder)
    digest=fingerprint(spec);input_hash=embedding_input_hash(spec,'media_poster',poster_hash='poster')
    client=Ollama('http://fixture.invalid',encoder,num_thread=8)
    assert asdict(client.encoder)==original and fingerprint(spec)==digest
    assert embedding_input_hash(spec,'media_poster',poster_hash='poster')==input_hash
    assert encoder.semantic_identity==replace(encoder,num_thread=8).semantic_identity
    assert encoder.identity!=replace(encoder,num_thread=8).identity
    assert encoder.semantic_identity!=replace(encoder,digest='c'*64).semantic_identity
    assert modality_contract(spec,'media_poster')['encoder']['num_thread']==16


@pytest.mark.parametrize('threads',[0,-1,17,1.5,True])
def test_unsafe_thread_overrides_are_rejected(encoder,threads):
    with pytest.raises(ContractError):Ollama('http://fixture.invalid',encoder,num_thread=threads)


def test_transport_overrides_only_cpu_threads_and_records_actual_execution(encoder):
    session=Mock();session.request.return_value=Mock(status_code=200,json=lambda:dict(model=encoder.reference,
        embeddings=[unit()],total_duration=100,load_duration=10,prompt_eval_count=5))
    client=Ollama('http://fixture.invalid',encoder,session,num_thread=8)
    client.execution_validation=dict(validated_num_thread=8,receipt_sha256='proof')
    values,timing=client.embed(poster=b'pixels')
    payload=session.request.call_args.kwargs['json']
    assert payload['options']==dict(num_ctx=8192,num_thread=8,num_batch=2048)
    assert payload['model']==encoder.reference and payload['dimensions']==768
    assert timing['execution']['requested_num_thread']==8 and timing['execution']['manifest_num_thread']==16
    assert timing['execution']['validation']['receipt_sha256']=='proof'
    assert encoder.num_thread==16


def test_cosine_alone_does_not_hide_material_vector_changes():
    assert execution.compare(unit(),unit())['consistent']
    other=np.asarray(unit());other[0]=.999;other[1]=.04;other/=np.linalg.norm(other)
    assert not execution.compare(other,unit())['consistent']


def test_unvalidated_override_never_mutates_checkpoints(store,encoder,tmp_path):
    gid,raw,plex,base=prepared_fixture(store,encoder,tmp_path)
    before=execution.state(store,gid)
    with pytest.raises(ContractError,match='benchmark evidence'):
        run_media_poster(store,gid,tmp_path,Ollama('http://fixture.invalid',encoder,num_thread=8))
    assert execution.state(store,gid)==before


def test_single_poster_benchmark_is_read_only_and_bound_to_generation(store,encoder,tmp_path,monkeypatch):
    gid,raw,plex,client=prepared_fixture(store,encoder,tmp_path);run_both(store,gid,tmp_path,client)
    original=execution.state(store,gid);before=store.generation(gid)['contract_hash']
    row=store.items(gid,'media_poster')[0];values=row['embedding'];calls=[]
    class Client:
        def __init__(self,host,pinned,**kwargs):self.encoder=pinned;self.options=kwargs
        def verify_pinned(self):return self.encoder
        def embed(self,*,poster):
            threads=self.options['num_thread'];calls.append((threads,poster))
            return values,dict(request_attempts=1,client_seconds={8:.2,6:.21,16:.15}[threads],server_nonload_seconds={8:.2,6:.21,16:.15}[threads])
    monkeypatch.setattr(execution,'call',lambda *a,**kw:Mock(json=lambda:dict(version='test-version')))
    report=execution.benchmark(store,gid,{'ollama.host':'http://fixture.invalid','ollama.timeout_s':1},tmp_path,
        item_key=row['item_key'],client_class=Client,progress=lambda *a,**kw:None)
    assert [t for t,_ in calls]==[8,6,16] and len({data for _,data in calls})==1
    assert report['state_unchanged'] and report['recommended_threads']==6
    assert report['compatible_threads']==[6,8,16]
    assert execution.state(store,gid)==original and store.generation(gid)['contract_hash']==before
    receipt=tmp_path/'receipt.json';receipt.write_text(json.dumps(report))
    proof=execution.authorize(store,gid,'http://fixture.invalid',8,tmp_path,path=receipt,version='test-version')
    assert proof['validated_num_thread']==8
    for field,value in [('generation_id','different'),('encoder_digest','c'*64),('ollama_version','other')]:
        changed=deepcopy(report);changed['binding'][field]=value;receipt.write_text(json.dumps(changed))
        with pytest.raises(ContractError,match='incompatible'):execution.authorize(store,gid,'http://fixture.invalid',8,tmp_path,path=receipt,version='test-version')
    receipt.write_text(json.dumps(report))
    with pytest.raises(ContractError,match='not passed'):execution.authorize(store,gid,'http://fixture.invalid',7,tmp_path,path=receipt,version='test-version')
    # An override is process-local: completed rows are still skipped on resume.
    validated=Ollama('http://fixture.invalid',encoder,num_thread=8);validated.execution_validation=proof
    validated.embed=Mock(side_effect=AssertionError('Completed records must not be recomputed'))
    run_media_poster(store,gid,tmp_path,validated)
    validated.embed.assert_not_called();assert execution.state(store,gid)==original
    with pytest.raises(ContractError):run_media_text(store,gid,validated)


def test_cli_thread_flags_do_not_leak_to_other_stages(monkeypatch):
    from scripts import embeddinggemma2_migration as cli
    connect=Mock();monkeypatch.setattr(cli,'connect_db',connect)
    for stage in ('media-text','watch','users','create'):
        with pytest.raises(SystemExit):cli.main([stage,'--generation','fixture','--num-thread','8','--approved-production-change'])
    connect.assert_not_called()
