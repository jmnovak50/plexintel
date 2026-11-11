"""Verify the runtime import closure, rather than grepping the retired reference package."""
import ast,importlib.util
from pathlib import Path
import sys
from unittest.mock import Mock
import pytest
from api.predictive.contracts import ContractError
from api.predictive.encoder import TextEncoder

ROOT=Path(__file__).resolve().parents[1]


def closure(starts):
    pending=list(starts);seen=set()
    while pending:
        path=pending.pop().resolve()
        if path in seen or not path.is_file():continue
        seen.add(path);tree=ast.parse(path.read_text())
        assert 'embedding_generation' not in path.parts
        for node in ast.walk(tree):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                assert 'embedding_v2.' not in node.value,(path,node.lineno)
            modules=[]
            if isinstance(node,ast.Import):modules=[name.name for name in node.names]
            elif isinstance(node,ast.ImportFrom):
                if node.level:
                    base=path.parent
                    for _ in range(node.level-1):base=base.parent
                    relative=(node.module or '').replace('.','/')
                    pending.append(base/(relative+'.py'))
                    pending.extend(base/relative/(name.name+'.py') for name in node.names)
                else:modules=[node.module or '']+[(node.module or '')+'.'+name.name for name in node.names]
            for name in modules:
                assert not name.startswith('api.embedding_generation'),(path,node.lineno)
                item=ROOT/name.replace('.','/')
                if item.with_suffix('.py').is_file():pending.append(item.with_suffix('.py'))
                elif item.is_dir():pending.append(item/'__init__.py')
    return seen


def test_active_web_daily_collection_and_labeling_closure_has_zero_migration_dependency():
    seen=closure([ROOT/'api/main.py',ROOT/'api/services/pipeline_service.py',ROOT/'scripts/predictive_pipeline.py',
        ROOT/'api/services/pipeline_labeling.py',ROOT/'batch_label_embeddings.py',ROOT/'fetch_tautulli_data.py'])
    assert ROOT/'api/predictive/runner.py' in seen
    assert ROOT/'api/predictive/publication.py' in seen
    assert ROOT/'api/services/dimension_labeling.py' in seen
    assert not any('embedding_generation' in path.parts for path in seen)


def test_admin_subprocess_allowlist_and_config_tool_have_no_migration_dependency():
    from api.routes.admin_routes import ALLOWED_SCRIPTS
    seen=closure([ROOT/name for name in ALLOWED_SCRIPTS]+[ROOT/'scripts/register_dimension_config.py'])
    assert ROOT/'label_embeddings.py' in seen
    assert ROOT/'api/services/dimension_label_batch.py' in seen


def test_encoder_is_text_only_digest_pinned_and_has_no_fallback():
    session=Mock()
    responses=[dict(models=[dict(name='embeddinggemma-2:latest',digest='a'*64)]),dict(capabilities=['embedding']),
        dict(model='sha256:'+'a'*64,embeddings=[[1.]+[0.]*767])]
    session.request.side_effect=[Mock(status_code=200,json=lambda r=r:r) for r in responses]
    encoder=TextEncoder('http://mock.invalid',session=session)
    assert len(encoder.embed('title metadata'))==768
    payload=session.request.call_args.kwargs['json']
    assert payload['input']=={'text':'title metadata'} and payload['dimensions']==768
    assert payload['truncate'] is False and payload['model']=='sha256:'+'a'*64
    session=Mock();session.request.return_value=Mock(status_code=200,json=lambda:dict(models=[]))
    with pytest.raises(ContractError,match='no pulls or fallback'):TextEncoder('http://mock.invalid',session=session)
    assert session.request.call_count==1


def test_obsolete_numeric_writers_fail_closed_without_database_access():
    from api.predictive.retired import assert_legacy_allowed
    with pytest.raises(ContractError,match='retired'):assert_legacy_allowed()


def test_replay_is_explicitly_complete_and_never_fabricates_a_missing_live_record():
    from api.predictive.io import FrozenPlex,SourceError
    with pytest.raises(ContractError):FrozenPlex(dict(metadata=[],catalog=[]))
    replay=FrozenPlex(dict(complete_catalog=True,metadata=[dict(ratingKey='2',title='captured')],
        catalog=[dict(ratingKey='2'),dict(ratingKey='3')]))
    assert replay.metadata('2')['title']=='captured'
    with pytest.raises(SourceError,match='incomplete_recorded_metadata'):replay.metadata('3')
    with pytest.raises(SourceError,match='HTTP_404'):replay.metadata('retired')


def test_source_connection_failure_cannot_be_reported_as_a_completed_daily_collection(monkeypatch):
    import fetch_tautulli_data as collector
    monkeypatch.setattr(collector,'connect_to_db',lambda:(None,None))
    with pytest.raises(RuntimeError,match='connection unavailable'):collector.run_incremental_load(embed=False)


def test_backup_subprocess_never_places_password_in_arguments():
    from api.predictive.publication import pg_connection
    dsn,environment=pg_connection(Mock(dsn='dbname=isolated user=fixture password=synthetic-secret host=/tmp/private'))
    assert 'synthetic-secret' not in dsn and 'password' not in dsn
    assert environment['PGPASSWORD']=='synthetic-secret'


@pytest.mark.parametrize('empty_checkout',[False,True])
def test_worker_loads_only_explicit_checkout_environment_without_overriding_destination(tmp_path,monkeypatch,empty_checkout):
    import os
    parent=tmp_path/'parent';checkout=parent/'checkout';checkout.mkdir(parents=True)
    (parent/'.env').write_text('PLEXINTEL_TEST_ENV_SENTINEL=ancestor\n')
    (checkout/'.env').write_text('' if empty_checkout else 'PLEXINTEL_TEST_ENV_SENTINEL=checkout\nDATABASE_URL=postgresql:///wrong\n')
    monkeypatch.delenv('PLEXINTEL_TEST_ENV_SENTINEL',raising=False)
    monkeypatch.setenv('DATABASE_URL','postgresql:///explicit-isolated')
    spec=importlib.util.spec_from_file_location('predictive_cli_test',ROOT/'scripts/predictive_pipeline.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    monkeypatch.setattr(cli,'ROOT',checkout)
    conn=Mock();monkeypatch.setattr(cli,'connect_db',lambda:conn)
    monkeypatch.setattr(cli,'current_config',lambda _:dict())
    monkeypatch.setattr(cli,'verify',lambda *args:dict())
    assert cli.main(['verify'])==0
    assert os.getenv('DATABASE_URL')=='postgresql:///explicit-isolated'
    assert os.getenv('PLEXINTEL_TEST_ENV_SENTINEL')==(None if empty_checkout else 'checkout')
    conn.set_session.assert_called_once_with(readonly=True,isolation_level='REPEATABLE READ')
