"""Fail-closed cloud policy; real SQL tests require an explicitly isolated DSN."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time
from unittest.mock import MagicMock, Mock
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json
import pytest

from api.services import app_settings, pipeline_labeling as auto
from api.services.labeling_costs import BudgetExceeded, Pricing, UsageLedger
from tests.test_pipeline_labeling import setup
from tests.test_semantic_labeling import sql_db


@pytest.fixture
def authorized_env(monkeypatch):
    for key, value in dict(PIPELINE_LABELING_ENABLED='true', PIPELINE_LABELING_CLOUD_AUTHORIZED='true',
                           PIPELINE_LABELING_BUDGET_USD='100', PIPELINE_LABELING_REQUEST_LIMIT='100').items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize('failure', ['connect', 'query'])
def test_settings_outage_cannot_fall_back_to_authorized_environment(setup, authorized_env, monkeypatch, failure):
    *_, execute, store, events, run = setup
    monkeypatch.setattr(auto, 'resolve_settings', app_settings.resolve_settings)
    db = MagicMock()
    db.cursor.return_value.__enter__.return_value.execute.side_effect = psycopg2.OperationalError('synthetic outage')
    monkeypatch.setattr(app_settings, 'connect_db', Mock(side_effect=psycopg2.OperationalError('synthetic outage'))
                        if failure == 'connect' else Mock(return_value=db))
    assert run()['status'] == 'skipped'
    execute.assert_not_called()
    setup[5].assert_not_called()  # No labeling connection or provider work.


def test_generic_unrelated_settings_keep_environment_fallback(monkeypatch):
    monkeypatch.setenv('OLLAMA_HOST', 'http://fictional.invalid:11434')
    monkeypatch.setattr(app_settings, 'connect_db', Mock(side_effect=psycopg2.OperationalError('synthetic outage')))
    assert app_settings.get_setting_value('ollama.host') == 'http://fictional.invalid:11434'


@pytest.mark.parametrize('key,value', [
    ('pipeline.labeling_cloud_authorized', 'false'), ('pipeline.labeling_enabled', 'false'),
    ('pipeline.labeling_budget_usd', '0'), ('pipeline.labeling_request_limit', '0'),
    ('pipeline.labeling_cloud_authorized', 'invalid'), ('pipeline.labeling_budget_usd', 'invalid'),
])
def test_stored_denial_or_invalid_policy_wins_over_conflicting_environment(setup, authorized_env, monkeypatch, key, value):
    monkeypatch.setattr(auto, 'resolve_settings', app_settings.resolve_settings)
    db = MagicMock()
    db.cursor.return_value.__enter__.return_value.fetchall.return_value = [
        dict(key=key, raw_value=value, source=app_settings.ADMIN_SOURCE)]
    monkeypatch.setattr(app_settings, 'connect_db', Mock(return_value=db))
    assert setup[-1]()['status'] == 'skipped'
    setup[7].assert_not_called()
    setup[5].assert_not_called()


def test_authorized_environment_requires_successful_single_policy_read(authorized_env, monkeypatch):
    db = MagicMock(); cur = db.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = []
    monkeypatch.setattr(app_settings, 'connect_db', Mock(return_value=db))
    assert auto.limits() == dict(budget_usd=100., request_limit=100)
    assert cur.execute.call_count == 1
    assert cur.execute.call_args.args[1] == (list(auto.POLICY_KEYS),)
    db.close.assert_called_once()


@pytest.fixture
def policy_db(sql_db, monkeypatch):
    conn, schema = sql_db
    monkeypatch.setattr(app_settings, 'SETTINGS_TABLE', schema + '.app_settings')
    monkeypatch.setattr(app_settings, 'connect_db', lambda **kw: psycopg2.connect(conn.dsn, **kw))
    conn.set_session(isolation_level='READ COMMITTED')
    app_settings.ensure_settings_schema(conn)
    conn.commit()
    app_settings.save_settings(updates=dict(zip(auto.POLICY_KEYS, (True, True, 1., 100))), clear_keys=[], updated_by='fixture')
    return conn, schema


def ledger_for(conn, *, prompt='fixture'):
    batch_id = str(uuid4())
    with conn.cursor() as cur:
        cur.execute('''INSERT INTO embedding_label_batches(batch_id,config_id,generation_id,model,dimensions,forecast,pricing)
            VALUES(%s,'fixture','fixture','gemma4:31b-cloud','[0]',%s,%s)''',
            (batch_id, Json(dict(automation_scope=auto.SCOPE, automation_prompts={'0': prompt})), Json(vars(Pricing()))))
    conn.commit()
    return UsageLedger(conn, batch_id, Pricing(), automation=dict(scope=auto.SCOPE, generation_id='fixture',
        prompts={'0': prompt}, max_attempts=3, limits=auto.limits))


def call_provider(ledger, monkeypatch):
    import gpt_utils as gpt
    cloud = Mock(return_value=dict(label='synthetic'))
    monkeypatch.setattr(gpt, '_call_ollama_for_label_result', cloud)
    def invoke():
        return gpt.call_llm_for_label_result('synthetic', provider='ollama', model='gemma4:31b-cloud',
            max_retries=1, max_output_tokens=1024,
            before_attempt=lambda attempt: ledger.start(0, 'media', attempt, 'synthetic', 'system', 1024))
    return cloud, invoke


def request_count(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM embedding_label_requests')
        return cur.fetchone()[0]


@pytest.mark.parametrize('updates', [
    {'pipeline.labeling_cloud_authorized': False}, {'pipeline.labeling_enabled': False},
    {'pipeline.labeling_budget_usd': .000001}, {'pipeline.labeling_request_limit': 0},
])
def test_sql_committed_reduction_overrides_earlier_authorized_snapshot(policy_db, authorized_env, monkeypatch, updates):
    conn, _ = policy_db
    assert auto.limits()['budget_usd'] == 1.
    ledger = ledger_for(conn)
    app_settings.save_settings(updates=updates, clear_keys=[], updated_by='fixture')
    cloud, invoke = call_provider(ledger, monkeypatch)
    with pytest.raises(BudgetExceeded): invoke()
    cloud.assert_not_called()
    conn.rollback()
    assert request_count(conn) == 0


def test_sql_failure_before_provider_cannot_use_earlier_snapshot(policy_db, monkeypatch):
    conn, schema = policy_db
    assert auto.limits()['request_limit'] == 100
    ledger = ledger_for(conn)
    monkeypatch.setattr(app_settings, 'SETTINGS_TABLE', schema + '.missing_settings')
    cloud, invoke = call_provider(ledger, monkeypatch)
    with pytest.raises(BudgetExceeded): invoke()
    cloud.assert_not_called()
    conn.rollback()
    assert request_count(conn) == 0


def wait_for_advisory_wait(conn, pid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS(SELECT 1 FROM pg_locks WHERE pid=%s AND locktype='advisory' AND NOT granted)", (pid,))
            if cur.fetchone()[0]: return
        time.sleep(.01)
    raise AssertionError('Reservation did not reach the deterministic advisory-lock wait')


def test_sql_revocation_committed_while_waiting_for_reservation_is_seen(policy_db, monkeypatch):
    conn, _ = policy_db
    ledger = ledger_for(conn)
    assert auto.limits()['budget_usd'] == 1.
    blocker = psycopg2.connect(conn.dsn)
    cloud, invoke = call_provider(ledger, monkeypatch)
    try:
        with blocker.cursor() as cur: cur.execute('SELECT pg_advisory_xact_lock(184726,51)')
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(invoke)
            try:
                wait_for_advisory_wait(blocker, conn.get_backend_pid())
                # Atomic admin update: stale true/new higher cap must never mix.
                app_settings.save_settings(updates={'pipeline.labeling_cloud_authorized': False,
                    'pipeline.labeling_budget_usd': 100.}, clear_keys=[], updated_by='fixture')
            finally:
                blocker.commit()
            with pytest.raises(BudgetExceeded): future.result(timeout=5)
        cloud.assert_not_called()
        conn.rollback()
        assert request_count(conn) == 0
    finally:
        blocker.close()


def test_sql_policy_lock_covers_missing_rows_until_reservation_commit(policy_db, authorized_env, monkeypatch):
    conn, _ = policy_db
    with conn.cursor() as cur:
        cur.execute(sql.SQL('DELETE FROM {} WHERE key=%s').format(sql.Identifier(*app_settings.SETTINGS_TABLE.split('.'))),
                    ('pipeline.labeling_cloud_authorized',))
    conn.commit()  # Successful absence permits environment authorization.
    ledger = ledger_for(conn)
    read, release = Event(), Event()
    real_resolve = auto.resolve_settings
    def resolve(**kwargs):
        result = real_resolve(**kwargs)
        if kwargs.get('lock'):
            read.set()
            assert release.wait(5), 'Test did not release the reservation'
        return result
    monkeypatch.setattr(auto, 'resolve_settings', resolve)
    cloud, invoke = call_provider(ledger, monkeypatch)
    writer = psycopg2.connect(conn.dsn)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(invoke)
            try:
                assert read.wait(5)
                with writer.cursor() as cur:
                    with pytest.raises(psycopg2.errors.LockNotAvailable):
                        cur.execute(sql.SQL('LOCK TABLE {} IN ROW EXCLUSIVE MODE NOWAIT')
                            .format(sql.Identifier(*app_settings.SETTINGS_TABLE.split('.'))))
                writer.rollback()
            finally:
                release.set()
            assert future.result(timeout=5)['label'] == 'synthetic'
        cloud.assert_called_once()
        assert request_count(conn) == 1
        conn.rollback()
        # Publication-independent admin writes can proceed after reservation.
        app_settings.save_settings(updates={'pipeline.labeling_cloud_authorized': False}, clear_keys=[], updated_by='fixture')
        cloud.reset_mock()
        with pytest.raises(BudgetExceeded): invoke()
        cloud.assert_not_called()
    finally:
        release.set()
        writer.close()
        conn.rollback()


def test_sql_pending_policy_write_fails_closed_without_waiting_or_sending(policy_db, monkeypatch):
    conn, _ = policy_db
    ledger = ledger_for(conn)
    writer = psycopg2.connect(conn.dsn)
    cloud, invoke = call_provider(ledger, monkeypatch)
    try:
        with writer.cursor() as cur:
            cur.execute(sql.SQL('UPDATE {} SET raw_value=\'false\' WHERE key=%s')
                .format(sql.Identifier(*app_settings.SETTINGS_TABLE.split('.'))), ('pipeline.labeling_cloud_authorized',))
        with pytest.raises(BudgetExceeded): invoke()
        cloud.assert_not_called()
        conn.rollback()
        assert request_count(conn) == 0
    finally:
        writer.rollback(); writer.close()


def test_sql_repeatable_read_cannot_admit_using_an_old_policy_snapshot(policy_db, monkeypatch):
    conn, _ = policy_db
    ledger = ledger_for(conn)
    conn.set_session(isolation_level='REPEATABLE READ')
    with conn.cursor() as cur: cur.execute('SELECT COUNT(*) FROM embedding_label_requests')
    app_settings.save_settings(updates={'pipeline.labeling_cloud_authorized': False}, clear_keys=[], updated_by='fixture')
    cloud, invoke = call_provider(ledger, monkeypatch)
    with pytest.raises(BudgetExceeded): invoke()
    cloud.assert_not_called()
    conn.rollback()
    assert request_count(conn) == 0


def test_sql_connection_loss_before_provider_never_sends(policy_db, monkeypatch):
    conn, _ = policy_db
    # A separate disposable connection avoids disrupting fixture cleanup.
    lost = psycopg2.connect(conn.dsn)
    with lost.cursor() as cur:
        cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(policy_db[1])))
    ledger = ledger_for(lost)
    cloud, invoke = call_provider(ledger, monkeypatch)
    lost.close()
    with pytest.raises(psycopg2.InterfaceError): invoke()
    cloud.assert_not_called()
    assert request_count(conn) == 0


@pytest.mark.parametrize('ceiling', ['budget', 'requests'])
def test_sql_policy_and_cumulative_pending_accounting_survive_new_ledger(policy_db, monkeypatch, ceiling):
    conn, _ = policy_db
    first = ledger_for(conn)
    cloud, invoke = call_provider(first, monkeypatch)
    invoke(); cloud.assert_called_once()
    spent = first.total_cost()
    conn.rollback()
    updates = {'pipeline.labeling_budget_usd': spent} if ceiling == 'budget' else {'pipeline.labeling_request_limit': 1}
    app_settings.save_settings(updates=updates, clear_keys=[], updated_by='fixture')
    restarted = ledger_for(conn, prompt='changed-prompt')
    cloud, invoke = call_provider(restarted, monkeypatch)
    with pytest.raises(BudgetExceeded): invoke()
    cloud.assert_not_called()
    conn.rollback()
    assert request_count(conn) == 1  # Pending prior attempt remains charged.


def test_sql_reservation_commit_failure_never_invokes_provider(policy_db, monkeypatch):
    conn, _ = policy_db
    ledger = ledger_for(conn)
    # Delegate real SQL, but fail before acknowledging a durable reservation.
    proxy = Mock(wraps=conn)
    proxy.commit.side_effect = psycopg2.OperationalError('synthetic commit connection failure')
    ledger.conn = proxy
    cloud, invoke = call_provider(ledger, monkeypatch)
    with pytest.raises(psycopg2.OperationalError): invoke()
    cloud.assert_not_called()
    conn.rollback()
    assert request_count(conn) == 0
