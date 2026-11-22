#!/usr/bin/env python3
"""Scoped normalized-metadata previews and explicit application; no schema jobs."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from api.db.connection import connect_db
from api.services import metadata_ingestion as metadata


def apply_transaction(conn, plan):
    try:
        with conn.cursor() as cur:
            # Ordinary ingestion deliberately does not acquire this: its parent
            # predictive runner already owns the session lock during collection.
            cur.execute('SELECT pg_try_advisory_xact_lock(184726,72) AS acquired')
            if not metadata.row_dict(cur,cur.fetchone())['acquired']:
                raise metadata.Busy('predictive_writer_busy')
            outcome = metadata.apply_plan(cur, plan)
        metadata.commit_metadata(conn,plan['rating_key'],plan['operation_id'])
        return outcome
    except metadata.CommitUncertain:
        raise
    except Exception as exc:
        conn.rollback()
        try:
            with conn.cursor() as cur:
                metadata.record_failure(cur, plan['rating_key'], plan['operation_id'], exc,
                                        operation=plan['mode'], operator=plan['operator'])
            conn.commit()
        except Exception:
            conn.rollback()
        raise


def order_repairs(adapter, *, rating_keys, operator, reason, apply=False, plans=None):
    if not rating_keys: raise metadata.MetadataError('explicit_rating_keys_required')
    if apply and plans is None: raise metadata.MetadataError('reviewed_plan_required')
    if plans is not None:
        if not isinstance(plans,list) or {p['rating_key'] for p in plans} != set(rating_keys):
            raise metadata.MetadataError('plan_target_scope_mismatch')
        for p in plans:
            if p.get('mode')!='complete' or p.get('fields') or set(p.get('relationships',{}))!={'actors'} or p['relationships']['actors'].get('action')!='orders' or p.get('operator')!=operator or p.get('reason')!=reason:
                raise metadata.MetadataError('plan_order_scope_mismatch')
    conn = adapter.connect_db(); conn.set_session(readonly=not apply)
    prepared=[]
    try:
        if plans is not None:
            for p in plans:
                if apply: apply_transaction(conn,p)
                else:
                    with conn.cursor() as cur: metadata.validate_preview(cur,p)
                    conn.rollback()
            return plans
        for key in sorted(set(rating_keys)):
            raw = adapter.fetch_tautulli_data('get_metadata', {'rating_key':key})
            with conn.cursor() as cur:
                plan=metadata.cast_order_plan(cur,key,raw,operator=operator,reason=reason)
            conn.rollback(); prepared.append(plan)
        return prepared
    finally: conn.rollback(); conn.close()


def _write(path, value):
    # Exclusive creation and owner-only permissions; never overwrite a preview.
    fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(value,handle,indent=2,default=str); handle.write('\n')


def cli(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    status=commands.add_parser('status',help='Read acceptance evidence without certifying legacy data')
    status.add_argument('--rating-key',type=int,required=True)
    status.add_argument('--dry-run',action='store_true',help='Status is always read-only')
    preview=commands.add_parser('preview')
    preview.add_argument('--rating-key',type=int,required=True)
    preview.add_argument('--changes',type=Path,required=True,help='JSON with explicit fields and/or relationships')
    preview.add_argument('--operator',required=True); preview.add_argument('--reason',required=True)
    preview.add_argument('--completion',action='store_true')
    preview.add_argument('--output',type=Path,required=True)
    preview.add_argument('--dry-run',action='store_true',help='Preview is always read-only')
    orders=commands.add_parser('orders')
    orders.add_argument('--rating-key',type=int,required=True)
    orders.add_argument('--operator',required=True); orders.add_argument('--reason',required=True)
    orders.add_argument('--reorder',action='store_true',help='Explicitly authorize known-order changes, never membership changes')
    orders.add_argument('--output',type=Path,required=True)
    orders.add_argument('--dry-run',action='store_true',help='Order preparation is always read-only')
    inverse=commands.add_parser('inverse',help='Prepare an audited reversal; never applies automatically')
    inverse.add_argument('--event-id',type=int,required=True)
    inverse.add_argument('--operator',required=True);inverse.add_argument('--reason',required=True)
    inverse.add_argument('--output',type=Path,required=True)
    inverse.add_argument('--dry-run',action='store_true',help='Inverse preparation is always read-only')
    apply=commands.add_parser('apply')
    apply.add_argument('--plan',type=Path,required=True)
    apply.add_argument('--dry-run',action='store_true')
    args=parser.parse_args(argv)
    conn=None
    try:
        conn=connect_db(); conn.set_session(readonly=args.command!='apply' or args.dry_run)
        if args.command=='status':
            with conn.cursor() as cur: print(json.dumps(metadata.ingestion_status(cur,args.rating_key)))
            conn.rollback()
        elif args.command=='preview':
            changes=json.loads(args.changes.read_text())
            if not isinstance(changes,dict) or set(changes)-{'fields','relationships'}:
                raise metadata.MetadataError('invalid_change_scope')
            with conn.cursor() as cur:
                plan=metadata.make_plan(cur,args.rating_key,operator=args.operator,reason=args.reason,
                                        mode='complete' if args.completion else 'correct',**changes)
            conn.rollback(); _write(args.output,plan)
        elif args.command=='orders':
            from api.services.library_service import fetch_tautulli_metadata
            raw=fetch_tautulli_metadata(args.rating_key)
            with conn.cursor() as cur:
                plan=metadata.cast_order_plan(cur,args.rating_key,raw,operator=args.operator,
                                             reason=args.reason,reorder=args.reorder)
            conn.rollback(); _write(args.output,plan)
        elif args.command=='inverse':
            with conn.cursor() as cur:
                plan=metadata.inverse_plan(cur,args.event_id,operator=args.operator,reason=args.reason)
            conn.rollback();_write(args.output,plan)
        else:
            plan=json.loads(args.plan.read_text())
            if args.dry_run:
                with conn.cursor() as cur:
                    metadata.validate_preview(cur,plan)
                conn.rollback(); print('Validated preview; no database changes')
            else: print(apply_transaction(conn,plan))
        return 0
    except Exception as exc:
        if conn: conn.rollback()
        print('Metadata operation failed: '+type(exc).__name__+': '+metadata.error_code(exc),file=sys.stderr)
        return 1
    finally:
        if conn: conn.close()


if __name__=='__main__': raise SystemExit(cli())
