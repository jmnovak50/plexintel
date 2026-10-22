#!/usr/bin/env python3
"""Read-only REST deployment probes. Print statuses, never response payloads/tokens."""
import argparse
from getpass import getpass
from pathlib import Path
import sys
from urllib.parse import urlsplit

REPO_ROOT=Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0,str(REPO_ROOT))
import requests
from api.services.private_config import read_private_token


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--service-token-file',type=Path)
    parser.add_argument('--ordinary-jwt',action='store_true',help='Prompt invisibly for an existing ordinary-user access token')
    args=parser.parse_args(argv)
    base=urlsplit(args.base_url)
    if base.scheme not in ('http','https') or not base.hostname or base.username or base.password or base.query or base.fragment:
        parser.error('Use an absolute HTTP(S) base URL without credentials, query or fragment')
    endpoint=args.base_url.rstrip('/')+'/api/agent/watch-history'
    failures=0
    def probe(label,expected,headers=None,params=None):
        nonlocal failures
        response=requests.get(endpoint,headers=headers,params=params or {'limit':1},timeout=15,allow_redirects=False)
        valid=response.status_code==expected
        if response.status_code==200:
            data=response.json()
            restricted={'ip_address','session_id','ip_suppressed_at','source_event_id','source_reference_id'}
            valid=valid and not any(restricted & set(row) for row in data.get('results',[]))
        print(label+': status='+str(response.status_code)+' expected='+str(expected)+' passed='+str(valid).lower())
        failures+=not valid
    try:
        probe('anonymous',401)
        probe('spoofed_identity',401,{'X-OpenWebUI-User-Email':'untrusted@example.invalid'})
        if args.service_token_file:
            headers={'Authorization':'Bearer '+read_private_token(args.service_token_file)}
            probe('entitled_service_all_users',200,headers,{'all_users':'true','limit':1})
        if args.ordinary_jwt:
            headers={'Authorization':'Bearer '+getpass('Existing ordinary-user access token: ').strip()}
            probe('ordinary_self',200,headers)
            probe('ordinary_cross_user_denied',403,headers,{'user':'__authorization_probe__','limit':1})
            probe('ordinary_all_users_denied',403,headers,{'all_users':'true','limit':1})
    except Exception:
        print('Probe could not complete; check connectivity, credentials and source-network prerequisites. Details withheld.')
        return 1
    return 1 if failures else 0


if __name__=='__main__':
    raise SystemExit(main())
