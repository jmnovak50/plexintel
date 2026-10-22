"""Migration runner regressions; all database calls are mocked, never production."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import runpy
from unittest.mock import AsyncMock, MagicMock, call, patch

import psycopg2
import pytest

from api.db import schema


REPO_ROOT = Path(__file__).resolve().parents[1]
SUPERSEDED_SQL = (REPO_ROOT / 'api/db/migrations/003_watch_history_playback.sql').read_text()
LOCK_SQL = 'SELECT pg_advisory_xact_lock(184725, 0)'


@pytest.fixture
def migrations(tmp_path, monkeypatch):
    directory = tmp_path / 'migrations'
    directory.mkdir()
    monkeypatch.setattr(schema, '__file__', str(tmp_path / 'schema.py'))
    return directory


@pytest.fixture
def connection(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(schema, 'connect_db', lambda: conn)
    monkeypatch.setattr(schema, 'get_database_url', lambda: 'mock-database-only')
    for name in ('ensure_settings_schema', 'sync_setting_descriptions', 'bootstrap_settings_from_env'):
        monkeypatch.setattr(schema, name, MagicMock())
    return conn


@pytest.mark.parametrize('sql', [
    '', ' \t\r\n\f\v', '-- comment', '-- one\n-- two\r-- three',
    '/* comment */', '/* outer /* nested */ outer */',
    ' \n-- line\r\n/* block */\t-- trailing', SUPERSEDED_SQL,
])
def test_empty_and_comment_only_migrations_are_skipped(migrations, connection, sql):
    (migrations / '001_noop.sql').write_text(sql)
    schema.apply_dimension_schema(connection)
    assert connection.cursor.return_value.__enter__.return_value.execute.call_args_list == [call(LOCK_SQL)]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


@pytest.mark.parametrize('sql', [
    'SELECT 1;',
    '-- leading comment\nCREATE TABLE example (id integer);',
    "SELECT '-- literal /* text */', E'escaped\\\\text', \"--identifier\";",
    "'--literal';",
    '/* prefix */ DO $$ BEGIN /* body */ PERFORM 1; END $$;',
    "-- prefix\nCREATE FUNCTION example() RETURNS text LANGUAGE sql AS $body$\n"
    "SELECT '--not a comment /* still text */'\n$body$;",
    '/* prefix */ $tag$-- untouched dollar-quoted contents$tag$;',
])
def test_executable_migrations_are_passed_through_verbatim(migrations, connection, sql):
    (migrations / '001_valid.sql').write_text(sql)
    schema.apply_dimension_schema(connection)
    assert connection.cursor.return_value.__enter__.return_value.execute.call_args_list == [call(LOCK_SQL), call(sql)]
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()


def test_filename_order_and_advisory_lock_are_preserved(migrations, connection):
    for name, sql in [('010_last.sql', 'SELECT 10;'), ('003_noop.sql', SUPERSEDED_SQL),
                      ('002_second.sql', 'SELECT 2;'), ('001_first.sql', 'SELECT 1;')]:
        (migrations / name).write_text(sql)
    schema.apply_dimension_schema(connection)
    assert connection.cursor.return_value.__enter__.return_value.execute.call_args_list == [
        call(LOCK_SQL), call('SELECT 1;'), call('SELECT 2;'), call('SELECT 10;'),
    ]


@pytest.mark.parametrize('sql', ['THIS IS INVALID SQL;', '/* unterminated', '/* nested /* open */'])
def test_real_sql_errors_fail_initialization_and_close_connection(migrations, connection, sql):
    (migrations / '001_noop.sql').write_text(SUPERSEDED_SQL)
    (migrations / '002_invalid.sql').write_text(sql)
    (migrations / '003_later.sql').write_text('SELECT 3;')
    error = psycopg2.ProgrammingError('SQL execution failure')
    cursor = connection.cursor.return_value.__enter__.return_value
    def execute(statement, *args):
        if statement == sql:
            raise error
    cursor.execute.side_effect = execute
    with pytest.raises(psycopg2.ProgrammingError) as raised:
        schema.ensure_app_schema()
    assert raised.value is error
    assert call('SELECT 3;') not in cursor.execute.call_args_list
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()  # Existing close-on-error behavior remains.
    connection.close.assert_called_once()


def test_ensure_app_schema_skips_real_superseded_migration_and_commits(migrations, connection):
    (migrations / '003_watch_history_playback.sql').write_text(SUPERSEDED_SQL)
    (migrations / '004_valid.sql').write_text('SELECT 4;')
    schema.ensure_app_schema()
    executed = connection.cursor.return_value.__enter__.return_value.execute.call_args_list
    assert call(SUPERSEDED_SQL) not in executed
    assert executed[-2:] == [call(LOCK_SQL), call('SELECT 4;')]
    connection.commit.assert_called_once()
    connection.close.assert_called_once()
    schema.bootstrap_settings_from_env.assert_called_once_with(connection)


def test_fastapi_startup_runs_shared_schema_path_with_comment_only_migration(migrations, connection):
    from api import main
    (migrations / '003_watch_history_playback.sql').write_text(SUPERSEDED_SQL)
    @asynccontextmanager
    async def runtime():
        yield
    async def startup():
        async with main.lifespan(main.app):
            pass
    with patch.object(main.mcp_runtime, 'lifespan', runtime), \
         patch.object(main, 'start_digest_scheduler'), \
         patch.object(main, 'start_pipeline_scheduler'), \
         patch.object(main, 'start_dimension_review_worker'), \
         patch.object(main, 'stop_digest_scheduler', new_callable=AsyncMock), \
         patch.object(main, 'stop_pipeline_scheduler', new_callable=AsyncMock), \
         patch.object(main, 'stop_dimension_review_worker', new_callable=AsyncMock):
        asyncio.run(startup())
    connection.commit.assert_called_once()
    connection.close.assert_called_once()
    assert call(SUPERSEDED_SQL) not in connection.cursor.return_value.__enter__.return_value.execute.call_args_list


def test_embedding_entrypoint_initializes_schema_without_running_embeddings(migrations, connection):
    (migrations / '003_watch_history_playback.sql').write_text(SUPERSEDED_SQL)
    class StopBeforeEmbeddingWork(Exception):
        pass
    # The real __main__ guard calls ensure_app_schema before main's connection.
    # Stop at that connection, before reading history or generating any embeddings.
    with patch('api.db.connection.connect_db', side_effect=StopBeforeEmbeddingWork), \
         patch('api.services.app_settings.get_setting_value', return_value=0.5):
        with pytest.raises(StopBeforeEmbeddingWork):
            runpy.run_path(str(REPO_ROOT / 'build_user_embeddings.py'), run_name='__main__')
    connection.commit.assert_called_once()
    connection.close.assert_called_once()
    assert call(SUPERSEDED_SQL) not in connection.cursor.return_value.__enter__.return_value.execute.call_args_list
