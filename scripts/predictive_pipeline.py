#!/usr/bin/env python3
"""Direct daily prediction job. Execution is explicit; never enables scheduling."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv
from api.db.connection import connect_db
from api.predictive.artifacts import current_config
from api.predictive.publication import verify,restore_last_good
from api.predictive.runner import run
from api.predictive.failures import classify_failure,failure_message


def main(argv=None):
    load_dotenv(ROOT/'.env',override=False)  # Explicit checkout only; no ancestor discovery.
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('daily','verify','restore-last-good'))
    parser.add_argument('--execute',action='store_true',help='Run writes to the explicitly configured database')
    parser.add_argument('--artifacts',default=str(ROOT/'.secrets/predictor'))
    parser.add_argument('--no-labeling',action='store_true')
    parser.add_argument('--allow-stored-history',action='store_true',help='Explicitly approve descriptive fallback from stored library fields')
    parser.add_argument('--frozen-inputs',type=Path,help='Private snapshot + complete Plex JSON replay; no live ingestion')
    parser.add_argument('--encoder-host',help='Isolated/local Gemma 2 endpoint for replay rebuild')
    parser.add_argument('--incumbent-evaluation',type=Path,help='Initial cutover baseline JSON with model_sha256 and average_precision')
    args=parser.parse_args(argv)
    if args.action!='verify' and not args.execute:parser.error('Daily writes require --execute and an explicitly configured destination')
    if args.frozen_inputs and (not args.no_labeling or not args.encoder_host):
        parser.error('Frozen qualification requires --no-labeling and an explicit --encoder-host')
    conn=None
    try:
        conn=connect_db()
        if args.action=='verify':
            conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
            result=dict(verification_only=True,counts=verify(conn,current_config(conn)))
        elif args.action=='restore-last-good':
            result=restore_last_good(conn,args.artifacts)
        else:
            baseline=json.loads(args.incumbent_evaluation.read_text()) if args.incumbent_evaluation else None
            replay={}
            if args.frozen_inputs:
                from api.predictive.io import FrozenPlex
                from api.predictive.encoder import TextEncoder
                payload=json.loads(args.frozen_inputs.read_text())
                encoder=TextEncoder(args.encoder_host)
                if encoder.identity['digest']!=payload['encoder_digest']:
                    raise ValueError('Recorded and installed encoder digests differ')
                replay=dict(frozen_source=payload['snapshot'],plex=FrozenPlex(payload['plex']),encoder=encoder,collect=False)
            result=run(conn,args.artifacts,**replay,allow_stored_history=args.allow_stored_history,
                incumbent_evaluation=baseline,label=not args.no_labeling)
        print(json.dumps(result,sort_keys=True));return 0
    except Exception as exc:
        diagnostic=dict(error=failure_message(exc),classification=classify_failure(exc))
        if hasattr(exc,'evaluation'):diagnostic['evaluation']=exc.evaluation
        print(json.dumps(diagnostic),file=sys.stderr)
        return 75 if classify_failure(exc)['retryable'] else 78
    finally:
        if conn is not None:conn.close()


if __name__=='__main__':raise SystemExit(main())
