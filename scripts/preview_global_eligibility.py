#!/usr/bin/env python3
"""Evaluate canonical inventory read-only, without installing eligibility history.

No Seerr, model or acquisition operations. A full private JSON audit is optional.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, help='Policy JSON; defaults to initial instance preferences')
    parser.add_argument('--output', type=Path, help='New owner-only full audit JSON; refuses to overwrite')
    args = parser.parse_args()
    from dotenv import load_dotenv
    from api.services import eligibility_workspace as workspace
    from api.services.global_eligibility import ENGINE_VERSION, Policy, digest, evaluate_all, summarize
    load_dotenv(ROOT/'.env', override=False)
    try:
        policy = Policy.model_validate_json(args.policy.read_text()) if args.policy else Policy()
        with workspace.transaction() as cur:
            inventory = workspace.inputs(cur)
            cur.execute("SHOW transaction_read_only")
            assert cur.fetchone()['transaction_read_only']=='on'
            cur.execute('SELECT count(*) AS observations FROM public.seerr_discovery_observations')
            observations = cur.fetchone()['observations']
            cur.execute('SELECT count(*) AS runs FROM public.seerr_discovery_runs')
            runs = cur.fetchone()['runs']
        results = [dict(title=t['title'], input_snapshot=t, **r)
                   for t, r in zip(inventory, evaluate_all(inventory, policy))]
        result = dict(evaluated_at=datetime.now(timezone.utc).isoformat(), engine_version=ENGINE_VERSION,
                      policy=policy.model_dump(), inventory_hash=digest(inventory), **summarize(results),
                      historical_observations=observations, discovery_runs=runs,
                      read_only=True, persisted=False, HTTP_requests=0, results=results)
        if args.output:
            descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as out:
                json.dump(result, out, ensure_ascii=False, indent=2)
                out.write('\n')
        public = {k: v for k, v in result.items() if k not in ('results', 'policy')}
        public['excluded_examples'] = [dict(title=r['title'], media_type=r['media_type'], tmdb_id=r['tmdb_id'], reasons=r['reasons']) for r in results if r['outcome']=='excluded'][:10]
        print(json.dumps(public, indent=2))
        return 0
    except Exception:
        # DB exceptions can contain credentials/DSNs. Keep raw errors private.
        print('Eligibility preview failed; no evaluation was persisted.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
