#!/usr/bin/env python3
"""Owner-only HTML preview from current recommendations; always database read-only."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from html import escape
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from api.db.connection import connect_db
from api.services.recommendation_query_service import _build_recommendations_query
from api.services.viewing_connections import derive, present


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', required=True, help='Explicit existing viewer username; never all users')
    parser.add_argument('--view', choices=['all','movies','shows','seasons','episodes'], default='all')
    parser.add_argument('--limit', type=int, default=20, choices=range(1,251), metavar='1..250')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    with closing(connect_db()) as conn:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='20s'; SET LOCAL lock_timeout='1s'")
            from api.services.app_settings import resolve_settings
            threshold = resolve_settings(keys=['recommendations.display_threshold'], conn=conn, require_database=True)['recommendations.display_threshold'].value
            query, params = _build_recommendations_query(username=args.user, view=args.view,
                show_rating_key=None,season_rating_key=None,search=None,sort=None,display_threshold=threshold)
            cur.execute(query+' LIMIT %s', params+[args.limit])
            rows = cur.fetchall()
            connections = derive(cur, args.user, rows)
        conn.rollback()
    cards = []
    for row in rows:
        connection = present(connections[row['rating_key']][1])
        if connection:
            detail = escape(connection['display_text'])
            facts = escape(connection['relationship_type']+' · '+connection['viewer_evidence'])
        else:
            detail = 'No suitable supported connection.'
            facts = 'Abstention'
        cards.append('<article><h2>'+escape(row['title'])+'</h2><p>'+facts+'</p><h3>Connections to Your Viewing History</h3><p>'+detail+'</p><small>New read-only derivation; no persistence writes.</small></article>')
    document = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Private viewing-history preview</title><style>body{font:16px/1.5 system-ui;max-width:960px;margin:40px auto;padding:16px}article{border:1px solid #ccd5e1;border-radius:12px;padding:18px;margin:18px 0}h3{font-size:14px;color:#4338ca}</style><h1>Private viewing-history connection preview</h1><p>Current recommendations; selected viewer only. '+datetime.now(timezone.utc).isoformat()+'</p><p>Read-only preview. Production connections and existing explanations are unchanged.</p>'+''.join(cards)+'</html>'
    fd = os.open(args.output, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write(document)
    print(f'Private preview written: {len(rows)} recommendations; no database writes.')


if __name__ == '__main__':
    main()
