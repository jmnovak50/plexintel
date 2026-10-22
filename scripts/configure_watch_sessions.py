#!/usr/bin/env python3
"""Offline setup or read-only verification of the existing session account."""
import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import sys

REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0,str(REPO_ROOT))

import psycopg2
from api.services.private_config import read_private_file
from dotenv import dotenv_values
from io import StringIO


def write_credentials(path,values):
    path=Path(path).expanduser()
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if path.parent.stat().st_mode & 0o077:
        raise ValueError('Credential directory must be owner-only')
    if any('\n' in value or '\r' in value for value in values.values()):
        raise ValueError('Credential values cannot contain newlines')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as handle:
        for key,value in values.items():
            handle.write(key+'='+json.dumps(value)+'\n')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',type=Path,default=Path.home()/'.config/plexintel/watch-sessions.env')
    parser.add_argument('--check',action='store_true',help='Read-only account, privilege and zero-IP-policy verification')
    args=parser.parse_args(argv)
    connection=None
    try:
        if args.check:
            from api.services.watch_session_sync import require_session_writer
            values=dotenv_values(stream=StringIO(read_private_file(args.file)),interpolate=False)
            connection=psycopg2.connect(values['WATCH_SESSIONS_DATABASE_URL'],connect_timeout=10,
                options='-c default_transaction_read_only=on -c statement_timeout=10000')
            with connection.cursor() as cur:
                require_session_writer(cur)
                cur.execute('SELECT current_user, current_database(), ip_retention_days FROM watch_session_policy WHERE singleton')
                user,database,days=cur.fetchone()
                if (user,database,days)!=('plexintel_session_ingest','plexintel',0):
                    raise ValueError('Account, database or zero-IP policy differs from the approved deployment')
                cur.execute('SELECT count(*) FILTER (WHERE ip_address IS NOT NULL) FROM watch_sessions')
                if cur.fetchone()[0]:
                    raise ValueError('Stored IPs require separate operator review')
                cur.execute("SELECT EXISTS(SELECT FROM pg_trigger WHERE tgrelid='watch_sessions'::regclass AND tgname='watch_session_ip_policy' AND tgenabled IN ('O','A'))")
                if not cur.fetchone()[0]:
                    raise ValueError('The approved policy trigger must be enabled')
            print('Session credential verified read-only; restricted existing account and zero-IP policy confirmed')
            return 0
        if args.file.expanduser().exists():
            print('Refusing to overwrite existing credentials. Use --check; credential rotation requires separate approval.',file=sys.stderr)
            return 1
        host=input('Existing PostgreSQL host: ').strip()
        port=input('PostgreSQL port [5432]: ').strip() or '5432'
        password=getpass('Existing plexintel_session_ingest password (not rotated): ')
        source=input('Existing Tautulli API base URL: ').strip()
        key=getpass('Existing Tautulli API key (not rotated): ')
        from urllib.parse import urlsplit
        parts=urlsplit(source)
        if not host or not password or not key or parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.query:
            raise ValueError('Invalid configuration')
        dsn=psycopg2.extensions.make_dsn(host=host,port=port,dbname='plexintel',user='plexintel_session_ingest',password=password)
        write_credentials(args.file,{'WATCH_SESSIONS_DATABASE_URL':dsn,'TAUTULLI_API_URL':source,
            'TAUTULLI_API_KEY':key,'WATCH_SESSIONS_RECONCILIATION_DAYS':'30','WATCH_SESSIONS_RETRIES':'1'})
        print('Created owner-only credential file. No credentials displayed; run --check before scheduling.')
        return 0
    except Exception:
        print('Session credential setup/verification failed. Check file permissions, existing credentials, reachability and account privileges; details withheld.',file=sys.stderr)
        return 1
    finally:
        if connection:
            connection.rollback();connection.close()


if __name__=='__main__':
    raise SystemExit(main())
