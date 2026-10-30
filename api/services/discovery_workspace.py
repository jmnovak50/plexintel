"""Bounded, read-only administrative discovery projections. No schema bootstrap."""
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import re

from psycopg2.extras import RealDictCursor
from api.db.connection import connect_db
from api.db.seerr_discovery import require_unified_schema
from api.services.seerr_client import load_seerr_config, SeerrError

# The typed title/observed-at index supplies this lookup. Refresh-only observations
# must never replace the most recent release-window discovery classification.
CLASSIFICATION = """LEFT JOIN LATERAL (
 SELECT o.eligibility,o.run_id,o.observed_at,o.detail_observed_at FROM public.seerr_discovery_observations o
 WHERE o.media_type=t.media_type AND o.tmdb_id=t.tmdb_id
 AND o.observation_kind='discovery' AND o.eligibility IS NOT NULL
 ORDER BY o.observed_at DESC,o.observation_id DESC LIMIT 1
) cl ON true"""
TITLE_FIELDS = """t.media_type,t.tmdb_id,t.title,t.original_language,t.premiere_date,
t.first_discovered_at,t.last_observed_at,t.last_enriched_at,t.enrichment_status,
t.media_status,t.media_status_4k,t.media_state,cl.eligibility AS classification,
cl.run_id AS classification_run_id,cl.observed_at AS classification_observed_at,
cl.detail_observed_at AS classification_detail_observed_at"""
SORTS = {'title':'t.title','premiere_date':'t.premiere_date',
 'first_discovered_at':'t.first_discovered_at','last_observed_at':'t.last_observed_at',
 'last_enriched_at':'t.last_enriched_at','popularity':'t.popularity'}
RUN_FIELDS = """run_id,started_at,completed_at,operation,status,parameters,
counts,discovery_complete,enrichment_complete,errors,warnings,
EXTRACT(EPOCH FROM (COALESCE(completed_at,now())-started_at)) AS duration_seconds"""

@contextmanager
def reader():
    conn=connect_db()
    try:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='15s'")
            cur.execute("SET LOCAL lock_timeout='2s'")
            require_unified_schema(conn)
            yield cur
    finally:
        conn.rollback();conn.close()

def effective_config():
    c=load_seerr_config()
    # Explicit public projection: never serialize url, key or private file paths.
    return c, {k:v for k,v in asdict(c).items() if k not in ('url','api_key')}

def poster_url(media_type, ident):
    return f'/api/admin/discovery/titles/{media_type}/{ident}/poster'

def _titles(rows):
    return [{**dict(r),'poster_url':poster_url(r['media_type'],r['tmdb_id'])} for r in rows]

def inventory(*, page=1, limit=25, search=None, media_type=None, language=None,
              enrichment_status=None, classification=None, media_state=None,
              release_from=None, release_to=None, discovered_from=None, discovered_to=None,
              sort='first_discovered_at', direction='desc'):
    if sort not in SORTS or direction not in ('asc','desc') or page<1 or not 1<=limit<=100:
        raise ValueError('Invalid inventory pagination or sort')
    where=[];args=[]
    for column,value in [('media_type',media_type),('original_language',language),('enrichment_status',enrichment_status)]:
        if value is not None:where.append(f't.{column}=%s');args.append(value)
    if search:
        where.append("(t.title ILIKE %s OR t.original_title ILIKE %s)")
        # Literal search: SQL binding and explicit wildcard escaping.
        term='%'+search.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%';args.extend([term,term])
    for col,op,v in [('premiere_date','>=',release_from),('premiere_date','<=',release_to),
                     ('first_discovered_at','>=',discovered_from),('first_discovered_at','<',discovered_to)]:
        if v is not None:where.append(f't.{col}{op}%s');args.append(v)
    if classification:
        where.append("COALESCE(cl.eligibility->>'state','unknown')=%s AND t.media_type='tv'");args.append(classification)
    states={'unknown':"t.media_status IS NULL",'known':"t.media_status IS NOT NULL",
            'requests_unknown':"t.media_state->>'request_count' IS NULL",
            'requested':"(t.media_state->>'request_count')::int>0",
            'no_requests_observed':"t.media_state->>'requests'='value' AND t.media_state->>'request_count'='0'"}
    if media_state:
        if media_state not in states:raise ValueError('Invalid media state')
        where.append(states[media_state])
    clause=' AND '.join(where) or 'true'
    with reader() as cur:
        cur.execute(f'SELECT count(*) AS total FROM public.seerr_discovered_titles t {CLASSIFICATION} WHERE {clause}',args)
        total=cur.fetchone()['total']
        cur.execute(f'SELECT {TITLE_FIELDS} FROM public.seerr_discovered_titles t {CLASSIFICATION} WHERE {clause} ORDER BY {SORTS[sort]} {direction} NULLS LAST,t.media_type,t.tmdb_id LIMIT %s OFFSET %s',[*args,limit,(page-1)*limit])
        return dict(items=_titles(cur.fetchall()),total=total,page=page,limit=limit)

def overview():
    cfg,_=effective_config()
    with reader() as cur:
        cur.execute("""SELECT count(*) AS total,
        count(*) FILTER(WHERE media_type='movie') AS movies,
        count(*) FILTER(WHERE media_type='tv') AS tv,
        count(*) FILTER(WHERE first_discovered_at>=now()-interval '24 hours') AS first_24h,
        count(*) FILTER(WHERE first_discovered_at>=now()-interval '7 days') AS first_7d,
        count(*) FILTER(WHERE %s OR (enrichment_status='failed' AND
          (last_enrichment_attempt_at IS NULL OR last_enrichment_attempt_at<=now()-(%s*interval '1 hour')))
          OR (enrichment_status<>'failed' AND (metadata_source_key IS DISTINCT FROM %s
          OR last_enriched_at IS NULL OR last_enriched_at<=now()-(%s*interval '1 hour')))) AS refresh_due
        FROM public.seerr_discovered_titles""",(not cfg.cache_enabled,cfg.failed_retry_hours,cfg.source_key,cfg.metadata_ttl_hours))
        counts=dict(cur.fetchone())
        cur.execute(f"SELECT COALESCE(cl.eligibility->>'state','unknown') AS state,count(*) AS count FROM public.seerr_discovered_titles t {CLASSIFICATION} WHERE t.media_type='tv' GROUP BY 1")
        classifications={r['state']:r['count'] for r in cur.fetchall()}
        result=dict(inventory=counts,tv_classification=classifications,provider='Seerr')
        for name,clause in [('latest_run','true'),('last_complete_discovery',"operation='discover' AND status='success' AND discovery_complete AND enrichment_complete"),('running_run',"status='running'"),('last_diagnostic',"errors<>'[]'::jsonb OR warnings<>'[]'::jsonb")]:
            cur.execute(f'SELECT {RUN_FIELDS} FROM public.seerr_discovery_runs WHERE {clause} ORDER BY started_at DESC LIMIT 1')
            row=cur.fetchone();result[name]=dict(row) if row else None
        cur.execute('SELECT count(*) AS total FROM public.seerr_discovery_observations');result['observations']=cur.fetchone()['total']
        cur.execute('SELECT count(*) AS total FROM public.seerr_discovery_runs');result['runs']=cur.fetchone()['total']
        cur.execute("SELECT run_id AS job_id,status,last_heartbeat_at FROM public.pipeline_runs WHERE left(delivery_type,18)='content_discovery_' AND status='started' ORDER BY started_at DESC LIMIT 1")
        active=cur.fetchone();result['active_job']=dict(active) if active else None
        return result

def title(media_type, ident, *, history_page=1, limit=25, diagnostics=False):
    with reader() as cur:
        # Source JSON is extracted only for one selected title, never dashboard scans.
        cur.execute(f'SELECT t.*,cl.eligibility AS classification,cl.run_id AS classification_run_id,cl.observed_at AS classification_observed_at,cl.detail_observed_at AS classification_detail_observed_at FROM public.seerr_discovered_titles t {CLASSIFICATION} WHERE t.media_type=%s AND t.tmdb_id=%s',(media_type,ident))
        row=cur.fetchone()
        if not row:return None
        result=dict(row);source=result.pop('source_metadata')
        cur.execute("SELECT source_key,parameters->>'source_id' AS source_id FROM public.seerr_discovery_runs WHERE run_id=%s",(str(result['first_discovery_run_id']),))
        result['discovery_source']={'provider':'Seerr',**dict(cur.fetchone())}
        result['poster_url']=poster_url(media_type,ident)
        if diagnostics:result['source_diagnostics']=source
        cur.execute('SELECT count(*) AS total FROM public.seerr_discovery_observations WHERE media_type=%s AND tmdb_id=%s',(media_type,ident));total=cur.fetchone()['total']
        cur.execute('''SELECT observation_id,run_id,scope_name,scope_key,observation_kind,query_parameters,
        observed_at,detail_observed_at,enrichment_outcome,enrichment_error,eligibility,is_new,changed_fields
        FROM public.seerr_discovery_observations WHERE media_type=%s AND tmdb_id=%s
        ORDER BY observed_at DESC,observation_id DESC LIMIT %s OFFSET %s''',(media_type,ident,limit,(history_page-1)*limit))
        result['history']=dict(items=[dict(r) for r in cur.fetchall()],total=total,page=history_page,limit=limit)
        return result

def runs(page=1,limit=25,status=None):
    where='WHERE status=%s' if status else '';args=[status] if status else []
    with reader() as cur:
        cur.execute(f'SELECT count(*) AS total FROM public.seerr_discovery_runs {where}',args);total=cur.fetchone()['total']
        cur.execute(f'SELECT {RUN_FIELDS} FROM public.seerr_discovery_runs {where} ORDER BY started_at DESC,run_id DESC LIMIT %s OFFSET %s',[*args,limit,(page-1)*limit])
        return dict(items=[dict(r) for r in cur.fetchall()],total=total,page=page,limit=limit)

def run_detail(run_id,page=1,limit=25):
    with reader() as cur:
        cur.execute(f'SELECT {RUN_FIELDS},pagination FROM public.seerr_discovery_runs WHERE run_id=%s',(str(run_id),));row=cur.fetchone()
        if not row:return None
        result=dict(row)
        cur.execute('SELECT count(*) AS total FROM public.seerr_discovery_observations WHERE run_id=%s',(str(run_id),));total=cur.fetchone()['total']
        cur.execute('''SELECT o.media_type,o.tmdb_id,t.title,o.is_new,o.eligibility,o.enrichment_outcome,
        o.enrichment_error,o.changed_fields,o.scope_name FROM public.seerr_discovery_observations o
        JOIN public.seerr_discovered_titles t USING(media_type,tmdb_id) WHERE o.run_id=%s
        ORDER BY o.media_type,o.tmdb_id,o.scope_key LIMIT %s OFFSET %s''',(str(run_id),limit,(page-1)*limit))
        result['memberships']=dict(items=[dict(r) for r in cur.fetchall()],total=total,page=page,limit=limit)
        return result

def poster_path(media_type,ident):
    with reader() as cur:
        cur.execute("SELECT COALESCE(source_metadata#>>'{detail,posterPath}',source_metadata#>>'{discovery,posterPath}') AS path FROM public.seerr_discovered_titles WHERE media_type=%s AND tmdb_id=%s",(media_type,ident))
        row=cur.fetchone();path=row['path'] if row else None
        return path if path and re.fullmatch(r'/[A-Za-z0-9_-]+\.(jpg|png|webp)',path) else None
