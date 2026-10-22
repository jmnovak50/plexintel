from pathlib import Path
from unittest.mock import patch
import os

import pytest
from api.services import private_config
from scripts.configure_watch_sessions import write_credentials
from openwebui_pipelines.plexintel_recommendation_pipeline import Pipeline,PipelineHttpError


def test_private_configuration_preserves_secrets_and_rejects_open_files(tmp_path,monkeypatch,capsys):
    directory=tmp_path/'private';directory.mkdir(mode=0o700)
    path=directory/'sessions.env'
    secret="host=fixture dbname=plexintel user=plexintel_session_ingest password='literal$secret#value'"
    write_credentials(path,{'WATCH_SESSIONS_DATABASE_URL':secret})
    assert path.stat().st_mode & 0o777 == 0o600
    monkeypatch.setenv('WATCH_SESSIONS_CREDENTIALS_FILE',str(path))
    monkeypatch.setenv('WATCH_SESSIONS_DATABASE_URL','initial-fixture-value')
    private_config.load_session_credentials()
    assert os.environ['WATCH_SESSIONS_DATABASE_URL']==secret
    assert secret not in capsys.readouterr().out
    with pytest.raises(FileExistsError):
        write_credentials(path,{'WATCH_SESSIONS_DATABASE_URL':'replacement'})
    path.chmod(0o644)
    with pytest.raises(private_config.PrivateConfigError):
        private_config.load_session_credentials()
    path.chmod(0o600)
    link=directory/'link';link.symlink_to(path)
    with pytest.raises(private_config.PrivateConfigError):
        private_config.read_private_file(link)


def test_private_config_rejects_model_connection_override(tmp_path,monkeypatch):
    path=tmp_path/'unsafe.env';path.write_text('DATABASE_URL=do-not-override-model');path.chmod(0o600)
    monkeypatch.setenv('WATCH_SESSIONS_CREDENTIALS_FILE',str(path))
    with pytest.raises(private_config.PrivateConfigError):
        private_config.load_session_credentials()


def test_pipeline_auth_is_sent_only_to_plexintel_and_not_to_ollama(monkeypatch):
    monkeypatch.setenv('PLEXINTEL_API_TOKEN','fixture-service-bearer-token')
    pipe=Pipeline()
    response=__import__('unittest.mock',fromlist=['Mock']).Mock(status_code=200)
    response.json.return_value={}
    with patch('requests.request',return_value=response) as request:
        pipe._plex_get('/api/agent/users')
        assert request.call_args.kwargs['headers']=={'Authorization':'Bearer fixture-service-bearer-token'}
        assert request.call_args.kwargs['allow_redirects'] is False
        pipe._ollama_post('/api/chat',{})
        assert request.call_args.kwargs['headers'] is None
    assert 'fixture-service-bearer-token' not in repr(pipe.valves)


def test_pipeline_credential_file_and_missing_auth_are_fail_closed(tmp_path,monkeypatch):
    monkeypatch.delenv('PLEXINTEL_API_TOKEN',raising=False)
    monkeypatch.delenv('PLEXINTEL_API_TOKEN_FILE',raising=False)
    pipe=Pipeline()
    with pytest.raises(PipelineHttpError):
        pipe._plex_get('/api/agent/users')
    path=tmp_path/'token';path.write_text('fixture-'+('x'*32));path.chmod(0o600)
    monkeypatch.setenv('PLEXINTEL_API_TOKEN_FILE',str(path))
    assert pipe._plex_headers()['Authorization'].startswith('Bearer fixture-')
    path.chmod(0o644)
    with pytest.raises(PipelineHttpError):
        pipe._plex_headers()


def test_session_cli_failure_never_logs_connection_values(monkeypatch,capsys):
    import fetch_tautulli_data as cli
    import psycopg2
    secret='postgresql://user:do-not-log@private/db'
    monkeypatch.setenv('WATCH_SESSIONS_DATABASE_URL',secret)
    with patch('api.services.private_config.load_session_credentials'),patch('psycopg2.connect',side_effect=psycopg2.OperationalError(secret)):
        result=cli.run_watch_sessions(incremental=True)
    assert result['errors']==1
    assert secret not in capsys.readouterr().out


def test_unit_runs_only_independent_sync_and_timer_is_daily():
    service=Path('deploy/systemd/plexintel-watch-sessions.service').read_text()
    timer=Path('deploy/systemd/plexintel-watch-sessions.timer').read_text()
    assert '--mode watch-sessions-sync' in service
    assert 'run_daily_pipeline' not in service and 'train_model' not in service
    assert 'WATCH_SESSIONS_CREDENTIALS_FILE=' in service
    assert 'OnCalendar=*-*-* 04:15:00 America/Chicago' in timer
    assert 'Persistent=true' in timer


def test_credential_check_is_read_only_and_checks_ip_trigger(tmp_path,capsys):
    from scripts import configure_watch_sessions as setup
    from unittest.mock import MagicMock
    path=tmp_path/'check.env'
    write_credentials(path,{'WATCH_SESSIONS_DATABASE_URL':'fixture-only-dsn'})
    connection=MagicMock()
    cursor=connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect=[(False,),('plexintel_session_ingest','plexintel',0),(0,),(True,)]
    with patch.object(setup.psycopg2,'connect',return_value=connection) as connect:
        assert setup.main(['--file',str(path),'--check'])==0
    assert 'default_transaction_read_only=on' in connect.call_args.kwargs['options']
    assert all(call.args[0].lstrip().startswith('SELECT') for call in cursor.execute.call_args_list)
    connection.rollback.assert_called_once()
    connection.close.assert_called_once()
    assert 'fixture-only-dsn' not in capsys.readouterr().out


def test_deployment_probe_uses_only_reads_and_withholds_payloads(tmp_path,capsys):
    from scripts import verify_agent_access as probe
    from unittest.mock import Mock
    path=tmp_path/'token';path.write_text('fixture-'+('x'*32));path.chmod(0o600)
    responses=[]
    for status in [401,401,200,200,403,403]:
        response=Mock(status_code=status)
        response.json.return_value={'results':[{'title':'personal-do-not-display'}]}
        responses.append(response)
    with patch.object(probe.requests,'get',side_effect=responses) as request,patch.object(probe,'getpass',return_value='private-user-jwt'):
        assert probe.main(['--base-url','https://fixture.invalid','--service-token-file',str(path),'--ordinary-jwt'])==0
    assert request.call_count==6
    assert all(call.kwargs['allow_redirects'] is False for call in request.call_args_list)
    out=capsys.readouterr().out
    assert 'private-user-jwt' not in out and 'personal-do-not-display' not in out
    assert 'passed=true' in out


def test_deployment_probe_rejects_sensitive_response_fields(capsys):
    from scripts import verify_agent_access as probe
    from unittest.mock import Mock
    response=Mock(status_code=200)
    response.json.return_value={'results':[{'ip_address':'do-not-print'}]}
    with patch.object(probe.requests,'get',return_value=response):
        assert probe.main(['--base-url','https://fixture.invalid'])==1
    assert 'do-not-print' not in capsys.readouterr().out
