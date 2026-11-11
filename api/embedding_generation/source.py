"""Read-only inventory snapshot and existing Plex/Tautulli credential discovery."""
from datetime import datetime, timezone
from pathlib import Path

import requests
from psycopg2.extras import RealDictCursor

from api.db.connection import connect_db
from api.services.app_settings import resolve_settings
from .contracts import ContractError, fingerprint
from .io import Plex, SourceError, call


def serializable(value):
    if isinstance(value, datetime):
        # Existing watch_history/feedback writers use naive UTC.
        if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value,dict):return {k:serializable(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [serializable(v) for v in value]
    return value


def settings():
    keys=['ollama.host','ollama.threads','ollama.timeout_s','tautulli.api_url','tautulli.api_key','plex.redirect_uri',
          'user_embeddings.engagement_threshold','training.watch_embed_min_engagement',
          'scoring.watched_engagement_threshold','training.movie_revisit_pending_days',
          'training.tv_revisit_pending_days','training.interested_sample_weight',
          'training.watched_like_sample_weight','training.negative_sample_weight','training.feedback_bonus',
          'pipeline.max_attempts']
    values={k:v.value for k,v in resolve_settings(keys=keys).items()}
    if float(values['training.watch_embed_min_engagement'])!=0.5:
        raise ContractError('Changed watch qualification requires a separately versioned contract')
    if float(values['scoring.watched_engagement_threshold'])!=0.5:
        raise ContractError('Changed scoring qualification requires a separately versioned contract')
    for key,expected in [('training.interested_sample_weight',.75),('training.watched_like_sample_weight',3.),
                         ('training.negative_sample_weight',5.),('training.feedback_bonus',.1)]:
        if float(values[key])!=expected:
            raise ContractError('Changed label weights require a separately versioned label contract')
    return values


def tautulli(config,command,**params):
    # Request/response exceptions never contain credential-bearing URLs.
    response=call(requests.Session(),'GET',config['tautulli.api_url'],params={
        'cmd':command,'apikey':config['tautulli.api_key'],**params})
    try:
        envelope=response.json()['response']
        if envelope.get('result')!='success':raise SourceError('tautulli_read_failed')
        return envelope['data']
    except (KeyError,ValueError,TypeError):
        raise SourceError('invalid_tautulli_envelope') from None


def plex(config,cache):
    server=tautulli(config,'get_server_info')
    conn=connect_db()
    conn.set_session(readonly=True)
    try:
        with conn.cursor() as cur:
            cur.execute('''SELECT plex_token FROM public.users
                WHERE plex_token IS NOT NULL AND length(trim(plex_token))>0
                ORDER BY COALESCE(is_admin,false) DESC,user_id LIMIT 1''')
            row=cur.fetchone()
    finally:conn.rollback();conn.close()
    if not row:raise SourceError('existing_plex_credential_unavailable')
    return Plex(server['pms_url'],row[0],cache)


def read_snapshot(conn, *, media_keys=None, max_events=None):
    """No schema helpers or pipeline imports. Caller supplies read-only connection.

    Snapshot includes ALL identities, including source/vector orphan identities:
    unmatched legacy rows cause explicit failures rather than silent omission.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT l.rating_key,l.title,l.summary,l.year,l.duration,l.media_type,
            l.parent_rating_key,l.show_rating_key,l.season_number,l.episode_number,
            l.thumb_path,l.parent_thumb_path,l.grandparent_thumb_path,l.plex_guid
            FROM public.library l FULL JOIN public.media_embeddings m USING(rating_key)
            WHERE (%s::integer[] IS NULL OR COALESCE(l.rating_key,m.rating_key)=ANY(%s))
            ORDER BY COALESCE(l.rating_key,m.rating_key)''',(media_keys,media_keys))
        media=[dict(r) for r in cur.fetchall()]
        if any(r['rating_key'] is None for r in media):
            raise ContractError('Orphan legacy media vectors require explicit reconciliation')
        cur.execute('''SELECT wh.watch_id,we.watch_id AS legacy_watch_id,wh.username,wh.rating_key,wh.watched_at,
            wh.played_duration AS played_seconds,wh.percent_complete
            FROM public.watch_history wh FULL JOIN public.watch_embeddings we USING(watch_id)
            WHERE (%s::integer[] IS NULL OR wh.rating_key=ANY(%s)) ORDER BY wh.watch_id''',(media_keys,media_keys))
        events=[dict(r) for r in cur.fetchall()]
        if any(r['watch_id'] is None for r in events):
            raise ContractError('Orphan legacy watch vectors require explicit reconciliation')
        if max_events is not None:events=events[:max_events]
        legacy_watch_ids=[r['watch_id'] for r in events if r.pop('legacy_watch_id') is not None]
        cur.execute('''SELECT DISTINCT ON(username,rating_key) username,rating_key,feedback,suppress,
            created_at,COALESCE(modified_at,created_at) AS modified_at
            FROM public.user_feedback WHERE (%s::integer[] IS NULL OR rating_key=ANY(%s))
            ORDER BY username,rating_key,COALESCE(modified_at,created_at) DESC,id DESC''',(media_keys,media_keys))
        feedback=[dict(r) for r in cur.fetchall()]
    return serializable(dict(media=media,events=events,feedback=feedback,legacy_watch_ids=legacy_watch_ids))


def snapshot(*,media_keys=None,max_events=None):
    conn=connect_db()
    conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
    try:
        with conn.cursor() as cur:cur.execute("SET LOCAL statement_timeout='30s'")
        return read_snapshot(conn,media_keys=media_keys,max_events=max_events)
    finally:conn.rollback();conn.close()


def event_availability(config,snapshot,*,bounded=False,progress=lambda value:None):
    """Obtain real grouped stop times; never guess end from playback duration.

    Missing/inconsistent stop times remain unknown and cannot enter historical
    features. Full source membership/pagination is verified. No raw payload saved.
    """
    expected={int(e['watch_id']):e for e in snapshot['events']}
    found={}
    starts={}
    seen=set()
    filters=sorted({e['rating_key'] for e in snapshot['events']}) if bounded else [None]
    for key in filters:
        offset=0
        for _ in range(200):
            params=dict(grouping=1,start=offset,length=1000)
            if key is not None:params['rating_key']=key
            result=tautulli(config,'get_history',**params)
            rows=result.get('data')
            total=result.get('recordsFiltered')
            if not isinstance(rows,list) or not isinstance(total,int):
                raise SourceError('invalid_history_pagination')
            for raw in rows:
                ident=int(raw.get('id') or raw.get('row_id') or 0)
                if ident not in expected:continue
                seen.add(ident)
                event=expected[ident]
                if int(raw.get('rating_key',0))!=event['rating_key'] or raw.get('user')!=event['username']:
                    raise ContractError('History identity mismatch')
                end=raw.get('stopped') or raw.get('stop')
                start=raw.get('started') or raw.get('date')
                if type(end) in (int,float) and type(start) in (int,float) and end>=start>0:
                    found[ident]=datetime.fromtimestamp(end,timezone.utc).isoformat()
                    starts[ident]=datetime.fromtimestamp(start,timezone.utc).isoformat()
            offset+=len(rows)
            progress(dict(expected=len(expected),completed=len(seen),failed=0,phase='history availability'))
            if offset>=total:break
            if not rows:raise SourceError('truncated_history_pagination')
        else:raise SourceError('history_page_limit')
    for event in snapshot['events']:
        event['available_at']=found.get(int(event['watch_id']))
        event['verified_started_at']=starts.get(int(event['watch_id']))
    progress(dict(expected=len(expected),completed=len(expected),failed=0,phase='availability assessed; unknown end times remain explicit'))
    return dict(expected=len(expected),verified_end_times=len(found),unknown_end_times=len(expected)-len(found))
