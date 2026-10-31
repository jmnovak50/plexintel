"""Run lifecycle/discovery regressions ONLY against a dedicated TCP-disabled fixture.

Set SEERR_DISCOVERY_TEST_DSN to the existing disposable-cluster test contract.
This runner installs database and HTTP guards before importing any application code.
"""
import os
from pathlib import Path
import sys

import psycopg2
from psycopg2.extensions import parse_dsn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
dsn = os.environ.get('SEERR_DISCOVERY_TEST_DSN', '')
expected = parse_dsn(dsn)
root = Path(expected.get('host', ''))
if (expected.get('dbname') != 'plexintel_seerr_fixture' or
        not str(root).startswith('/tmp/plexintel-seerr-fixture.') or not (root/'data').is_dir()):
    raise SystemExit('Refusing tests without a dedicated local fixture')
original = psycopg2.connect


def guarded(dsn=None, **kwargs):
    params = parse_dsn(dsn or '') | {k: str(v) for k, v in kwargs.items() if k in ('host', 'port', 'dbname')}
    if any(params.get(k) != expected.get(k) for k in ('host', 'port', 'dbname')):
        raise AssertionError('Production/non-fixture database access forbidden')
    return original(dsn, **kwargs)


psycopg2.connect = guarded
with guarded(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT current_setting('data_directory'),current_setting('listen_addresses')")
        directory, listen = cur.fetchone()
        if Path(directory) != root/'data' or listen != '':
            raise SystemExit('Fixture must be TCP-disabled and isolated')
os.environ.update(DATABASE_URL=dsn, PLEXINTEL_AGENT_SERVICE_TOKEN_FILE='',
                  TAUTULLI_API_KEY='isolated-dummy-key', TAUTULLI_URL='https://example.invalid')
for key in ('SEERR_DISCOVERY_ENABLED', 'SEERR_DISCOVERY_WEB_PREVIEW_ENABLED',
            'SEERR_DISCOVERY_WEB_WRITES_ENABLED', 'SEERR_DISCOVERY_SCHEDULING_ENABLED',
            'GLOBAL_ELIGIBILITY_WRITES_ENABLED'):
    os.environ[key] = 'false'
import requests
def no_http(*args, **kwargs):
    raise AssertionError('Live HTTP forbidden')
requests.sessions.Session.request = no_http
import pytest
paths = ['tests/test_global_eligibility.py', 'tests/test_content_discovery.py',
         'tests/test_seerr_discovery.py', 'tests/test_seerr_unified_discovery.py',
         'tests/test_seerr_readiness_remediation.py', 'tests/test_pipeline_scheduler.py',
         'tests/test_pipeline_service.py', 'tests/test_pipeline_routes.py', 'tests/test_app_settings.py']
raise SystemExit(pytest.main(['-q', *paths, *sys.argv[1:]]))
