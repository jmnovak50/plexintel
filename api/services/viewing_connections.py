"""Current factual viewing context. No inference, source acquisition or prediction writes.

Only attach() is an activation boundary. derive() is also usable with an explicitly
read-only production connection for private previews. Never render stored JSON directly.
"""
from collections import defaultdict
import logging
import os

from psycopg2.extras import RealDictCursor, Json, execute_values
from api.db.connection import connect_db
from api.predictive.recovery import stable_identity, IdentityError

POLICY = 'viewing-history-connections/2'
MAX_PAGE = 250
log = logging.getLogger(__name__)


def enabled():
    return os.getenv('PLEXINTEL_VIEWING_CONNECTIONS_ENABLED', '').lower() in ('1', 'true', 'yes', 'on')


def identity(row):
    try:
        return stable_identity(row['media_type'], row['plex_guid'])
    except (IdentityError, KeyError, TypeError):
        return None


class Catalog:
    """Temporary scalar identity index, not another persisted metadata catalog."""
    def __init__(self, rows):
        self.rows = {r['rating_key']: r for r in rows}
        self.groups = defaultdict(list)
        self.ids = {k: identity(r) for k, r in self.rows.items()}
        for key, canonical in self.ids.items():
            if canonical: self.groups[canonical].append(key)
        bad = set()
        for canonical, keys in self.groups.items():
            signatures = set()
            for key in keys:
                r = self.rows[key]; kind = r['media_type']
                signature = (kind, (r.get('title') or '').strip().casefold(), r.get('year'))
                if not signature[1]: bad.add(canonical)
                if kind in ('episode', 'season'):
                    show = self.rows.get(r.get('show_rating_key'), {})
                    parent = self.rows.get(r.get('parent_rating_key'), {})
                    if show.get('media_type') != 'show' or parent.get('media_type') != ('show' if kind == 'season' else 'season'):
                        bad.add(canonical)
                    if kind == 'episode' and self.ids.get(parent.get('show_rating_key')) != self.ids.get(show.get('rating_key')):
                        bad.add(canonical)
                    if type(r.get('season_number')) is not int or r['season_number'] < 0:
                        bad.add(canonical)
                    if kind == 'episode' and (type(r.get('episode_number')) is not int or r['episode_number'] < 0 or parent.get('season_number') != r['season_number']):
                        bad.add(canonical)
                    signature += (self.ids.get(r.get('show_rating_key')), r.get('season_number'), r.get('episode_number'))
                    if not signature[-3]: bad.add(canonical)
                signatures.add(signature)
            if len(signatures) != 1: bad.add(canonical)
        # A poisoned parent also poisons descendants, regardless of iteration order.
        for _ in range(2):
            for key, r in self.rows.items():
                if r['media_type'] in ('episode', 'season') and (self.ids.get(r.get('show_rating_key')) in bad or self.ids.get(r.get('parent_rating_key')) in bad):
                    bad.add(self.ids[key])
        self.bad = bad

    def canonical(self, key):
        value = self.ids.get(key)
        return value if value and value not in self.bad else None

    def representative(self, key):
        canonical = self.canonical(key)
        return min(self.groups[canonical]) if canonical else None

    def group(self, key):
        row = self.rows.get(key, {})
        if not self.canonical(key): return None
        return self.representative(row.get('show_rating_key')) if row.get('media_type') in ('episode', 'season') else self.representative(key)


def _catalog(cur):
    cur.execute('''SELECT rating_key,plex_guid,media_type,title,year,duration,
        parent_rating_key,show_rating_key,season_number,episode_number FROM public.library''')
    return Catalog(cur.fetchall())


def _evidence(cur, username, catalog):
    # Exactly one viewer-history/feedback retrieval; no raw sessions or provenance.
    cur.execute('''SELECT 'watch' kind,watch_id id,rating_key,media_type,title,show_rating_key,
            played_duration,watched_at happened_at,NULL::text feedback FROM public.watch_history WHERE username=%s
        UNION ALL SELECT 'feedback',id,rating_key,NULL,NULL,NULL,NULL,
            coalesce(modified_at,created_at),feedback FROM
            (SELECT DISTINCT ON (rating_key) * FROM public.user_feedback WHERE username=%s
             ORDER BY rating_key,coalesce(modified_at,created_at) DESC NULLS LAST,id DESC) f''', (username, username))
    observations = cur.fetchall()
    feedback = defaultdict(set)
    for r in observations:
        if r['kind'] == 'feedback' and catalog.canonical(r['rating_key']):
            feedback[catalog.canonical(r['rating_key'])].add(r['feedback'])
    negative = {'never_watch', 'watched_dislike'}
    def rejected(key):
        row = catalog.rows.get(key, {})
        return any(feedback[catalog.canonical(k)] & negative for k in (key, row.get('parent_rating_key'), row.get('show_rating_key')) if catalog.canonical(k))
    groups = {}
    for r in observations:
        key = r['rating_key']; group = catalog.group(key)
        if group is None or rejected(key): continue
        row = catalog.rows[key]; src = catalog.rows[group]
        liked = r['kind'] == 'feedback' and r['feedback'] == 'watched_like'
        watched = False; fraction = 0.0
        if r['kind'] == 'watch' and row['media_type'] in ('movie', 'episode'):
            duration = row.get('duration') or 0
            fraction = min(1.0, max(0.0, (r['played_duration'] or 0) * 1000 / duration)) if duration > 0 else 0.0
            # Same half-runtime convention as watch_history_enriched_v, not a like label.
            watched = fraction >= .5 and r['media_type'] == row['media_type']
            if r.get('show_rating_key') is not None and row['media_type'] == 'episode':
                watched &= catalog.canonical(r['show_rating_key']) == catalog.canonical(row.get('show_rating_key'))
            # Detect stale/recycled local-key evidence; no fuzzy matching.
            if r.get('title') and r['title'].strip().casefold() != src['title'].strip().casefold():
                watched = False
        if not watched and not liked: continue
        state = groups.setdefault(group, dict(fact_key=group,canonical=catalog.canonical(group),title=src['title'],
            media_type=src['media_type'],year=src.get('year'),like_scope=None,liked=False,fraction=0.0,events=set(),last_seen=''))
        if liked and (state['like_scope'] is None or ('show','movie','season','episode').index(row['media_type']) < ('show','movie','season','episode').index(state['like_scope'])):
            state['like_scope'] = row['media_type']
        state['liked'] |= liked
        if watched:
            state['fraction'] = max(state['fraction'], fraction)
            state['events'].add(r['id'])
        if r['happened_at'] is not None: state['last_seen'] = max(state['last_seen'], r['happened_at'].isoformat())
    for r in groups.values():
        r['event_count'] = len(r.pop('events'))
        r['basis'] = 'explicitly_liked' if r['liked'] else 'watched'
    return list(groups.values()), rejected


def _consistent_facts(cur, catalog, keys):
    """Aliases must agree about normalized facts; conflicting groups abstain."""
    keys = sorted({alias for key in keys if catalog.canonical(key) for alias in catalog.groups[catalog.canonical(key)]})
    if not keys: return set()
    cur.execute('''SELECT l.rating_key,
      ARRAY(SELECT actor_id::text||':'||coalesce(cast_order::text,'?') FROM media_actors WHERE media_id=l.rating_key ORDER BY actor_id) actors,
      ARRAY(SELECT director_id FROM media_directors WHERE media_id=l.rating_key ORDER BY director_id) directors,
      ARRAY(SELECT genre_id FROM media_genres WHERE media_id=l.rating_key ORDER BY genre_id) genres
      FROM library l WHERE rating_key=ANY(%s)''',(keys,))
    signatures = defaultdict(set)
    for r in cur.fetchall():
        signatures[catalog.canonical(r['rating_key'])].add(tuple(tuple(r[k]) for k in ('actors','directors','genres')))
    return {canonical for canonical, values in signatures.items() if len(values) == 1}


DISCOVERY = '''WITH targets AS MATERIALIZED (
 SELECT * FROM jsonb_to_recordset(%s::jsonb) AS x(target text,fact_key int,group_identity text)),
 sources AS MATERIALIZED (
 SELECT * FROM jsonb_to_recordset(%s::jsonb) AS x(fact_key int,canonical text,title text,media_type text,year int,
 liked boolean,fraction float,event_count int,last_seen text,basis text,like_scope text)),
 continuity AS MATERIALIZED (
 SELECT t.target,s.canonical,0 tier,'series' relation,ARRAY[]::text[] names,ARRAY[]::int[] ids,0 prominence,0 source_prominence FROM targets t JOIN sources s ON s.canonical=t.group_identity WHERE s.media_type='show'),
 direction AS MATERIALIZED (
 SELECT t.target,s.canonical,1,'director',ARRAY[d.name],ARRAY[d.id],0,0 FROM targets t JOIN media_directors a ON a.media_id=t.fact_key JOIN media_directors b ON b.director_id=a.director_id JOIN sources s ON s.fact_key=b.media_id JOIN directors d ON d.id=a.director_id WHERE s.canonical<>t.group_identity AND NOT EXISTS(SELECT 1 FROM continuity h WHERE h.target=t.target)),
 cast_matches AS MATERIALIZED (
 SELECT t.target,s.canonical,2,'cast',ARRAY[p.name],ARRAY[p.id],coalesce(a.cast_order,2147483647),coalesce(b.cast_order,2147483647) FROM targets t JOIN media_actors a ON a.media_id=t.fact_key JOIN media_actors b ON b.actor_id=a.actor_id JOIN sources s ON s.fact_key=b.media_id JOIN actors p ON p.id=a.actor_id WHERE s.canonical<>t.group_identity AND NOT EXISTS(SELECT 1 FROM continuity h WHERE h.target=t.target) AND NOT EXISTS(SELECT 1 FROM direction h WHERE h.target=t.target)),
 genre_matches AS MATERIALIZED (
 SELECT t.target,s.canonical,3,'genre',array_agg(g.name ORDER BY g.name COLLATE "C"),array_agg(g.id ORDER BY g.name COLLATE "C"),0,0 FROM targets t JOIN media_genres a ON a.media_id=t.fact_key JOIN media_genres b ON b.genre_id=a.genre_id JOIN sources s ON s.fact_key=b.media_id JOIN genres g ON g.id=a.genre_id WHERE s.canonical<>t.group_identity AND NOT EXISTS(SELECT 1 FROM continuity h WHERE h.target=t.target) AND NOT EXISTS(SELECT 1 FROM direction h WHERE h.target=t.target) AND NOT EXISTS(SELECT 1 FROM cast_matches h WHERE h.target=t.target) GROUP BY t.target,s.canonical HAVING count(*)>=2),
 candidates AS(SELECT * FROM continuity UNION ALL SELECT * FROM direction UNION ALL SELECT * FROM cast_matches UNION ALL SELECT * FROM genre_matches),
 ranked AS (
 SELECT c.*,to_jsonb(s) evidence,row_number() OVER(PARTITION BY target ORDER BY tier,liked DESC,fraction DESC,prominence,source_prominence,event_count DESC,last_seen DESC,s.canonical COLLATE "C",ids) position
 FROM candidates c JOIN sources s ON s.canonical=c.canonical)
 SELECT target,relation,names,ids,evidence,prominence,source_prominence FROM ranked WHERE position=1'''


def derive(cur, username, rows):
    """Read-only derivation for a page. Returns private structured selections."""
    if len(rows) > MAX_PAGE: raise ValueError('Connection pages are limited to 250 targets')
    catalog = _catalog(cur)
    sources, rejected = _evidence(cur, username, catalog)
    targets = {}
    for row in rows:
        key = row['rating_key']; canonical = catalog.canonical(key); group = catalog.group(key)
        if not canonical or group is None or rejected(key): continue
        targets[canonical] = dict(target=canonical,fact_key=group,group_identity=catalog.canonical(group))
    valid = _consistent_facts(cur, catalog, [s['fact_key'] for s in sources]+[t['fact_key'] for t in targets.values()])
    sources = [s for s in sources if s['canonical'] in valid]
    targets = {k:t for k,t in targets.items() if t['group_identity'] in valid}
    found = {}
    if targets and sources:
        cur.execute(DISCOVERY,(Json(list(targets.values())),Json(sources)))
        for r in cur.fetchall():
            evidence = r['evidence']
            found[r['target']] = {'relationship_type':r['relation'],'shared_names':r['names'],'shared_ids':r['ids'],
                'source_identity':evidence['canonical'],'source_title':evidence['title'],
                'source_media_type':evidence['media_type'],'source_year':evidence['year'],
                'evidence':{k:evidence[k] for k in ('basis','event_count','fraction','last_seen','like_scope')},
                'target_fact_identity':targets[r['target']]['group_identity'],
                'target_fact_title':catalog.rows[targets[r['target']]['fact_key']]['title'],
                'target_fact_media_type':catalog.rows[targets[r['target']]['fact_key']]['media_type'],
                'cast_orders':{scope:(r[field] if r[field]!=2147483647 else None) for scope,field in (('target','prominence'),('source','source_prominence'))} if r['relation']=='cast' else None}
    # Invalid/unsupported targets are explicit no-results too when identity is typed.
    return {row['rating_key']: (identity(catalog.rows.get(row['rating_key'],{})), found.get(catalog.canonical(row['rating_key']))) for row in rows}


def present(connection):
    """Allowlist public output; distinguish liking a part from its series facts."""
    if not connection: return None
    source = connection['source_title']
    basis = connection['evidence']['basis']
    scope = connection['evidence'].get('like_scope')
    part_like = basis == 'explicitly_liked' and scope in ('episode','season')
    like_prefix = {'episode':'an episode of ', 'season':'a season of '}.get(scope, '')
    start = f'You liked {like_prefix}{source}' if basis == 'explicitly_liked' else f"You've watched {source}"
    relation = connection['relationship_type']; names = connection['shared_names'][:3]
    if relation not in ('series','cast','director','genre'): return None
    joined = ', '.join(names[:-1])+' and '+names[-1] if len(names)>1 else (names[0] if names else '')
    # The relative clause must not attach a series credit to the liked episode.
    bridge = '. The series' if part_like else ', which'
    target_series = connection.get('target_fact_media_type') == 'show'
    if relation == 'series':
        text = start + '.' if basis == 'explicitly_liked' else f"You've watched some of {source}."
    elif relation == 'cast':
        text = start + bridge + (' shares cast member '+joined+' with the series '+connection['target_fact_title']+'.' if target_series else ' also features '+joined+'.')
        if part_like and target_series:
            text = start + '. The series '+source+' and '+connection['target_fact_title']+' both feature '+joined+'.'
    elif relation == 'director':
        text = start + bridge + (' shares director '+joined+' with the series '+connection['target_fact_title']+'.' if target_series else ' shares a director: '+joined+'.')
        if part_like and target_series:
            text = start + '. The series '+source+' and '+connection['target_fact_title']+' share director '+joined+'.'
    else:
        if target_series:
            text = start + '. ' + (('The series '+source+' and '+connection['target_fact_title']) if part_like else (source+' and the series '+connection['target_fact_title'])) + ' both list the genres '+joined+'.'
        else:
            text = start + ('. The series and this title both list the genres ' if part_like else '. Both list the genres ') + joined+'.'
    return {'relationship_type':relation,'source_title':source,'source_media_type':connection['source_media_type'],
            'shared_elements':names,'viewer_evidence':basis,'display_text':text,
            'target_scope':{'title':connection.get('target_fact_title'),'media_type':connection.get('target_fact_media_type')}}


def present_page(rows, selections):
    """Show each repeated fact once in input page order; retain every saved choice.

    Actor/director IDs are local to their relation. A genre combination uses the
    three displayed tags; series continuity uses its canonical series identity.
    This is presentation suppression, never a persisted claim of absent evidence.
    A different page/single-card request can reuse the suppressed saved selection.
    """
    seen = set(); result = {}
    for row in rows:
        key = row['rating_key']; connection = selections.get(key)
        rendered = present(connection)
        if rendered is not None:
            relation = connection['relationship_type']
            fact = connection['source_identity'] if relation=='series' else tuple(connection['shared_ids'][:3])
            signature = (relation, fact)
            if signature in seen: rendered = None
            else: seen.add(signature)
        result[key] = rendered
    return result


def _versions(cur, username, *, lock=False):
    cur.execute("SELECT scope,revision FROM viewing_connection_state WHERE (scope='catalog' AND owner='') OR (scope='viewer' AND owner=%s) ORDER BY scope"+(' FOR SHARE NOWAIT' if lock else ''),(username,))
    return {r['scope']:r['revision'] for r in cur.fetchall()}


def lookup(username, rows, *, connect=None):
    """Batch cache/read/derive/save; a failure never makes recommendations fail."""
    if not rows: return {}, set()
    if not isinstance(username,str) or not username or len(rows)>MAX_PAGE: return {}, set()
    conn = (connect or connect_db)()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL lock_timeout='100ms'; SET LOCAL statement_timeout='2s'")
            cur.execute("SELECT to_regclass('public.viewing_connection_context') relation")
            if cur.fetchone()['relation'] is None: return {}, set()
            cur.execute("INSERT INTO viewing_connection_state(scope,owner) VALUES('viewer',%s) ON CONFLICT DO NOTHING",(username,))
        conn.commit()
        conn.set_session(isolation_level='REPEATABLE READ')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='2s'")
            versions = _versions(cur, username)
            cur.execute('SELECT rating_key,media_type,plex_guid FROM library WHERE rating_key=ANY(%s)',([r['rating_key'] for r in rows],))
            identities = {r['rating_key']:identity(r) for r in cur.fetchall()}
            cur.execute('''SELECT target_identity,connection FROM viewing_connection_context WHERE username=%s
                AND target_identity=ANY(%s) AND policy_version=%s AND catalog_revision=%s AND viewer_revision=%s''',
                (username,list(filter(None,identities.values())),POLICY,versions['catalog'],versions['viewer']))
            cached = {r['target_identity']:r['connection'] for r in cur.fetchall()}
            misses = [r for r in rows if identities.get(r['rating_key']) and identities[r['rating_key']] not in cached]
            if misses:
                cur.execute('SELECT pg_try_advisory_lock(184728,hashtext(%s)) acquired',(username,))
                if not cur.fetchone()['acquired']: return {},set()
                derived = derive(cur,username,misses)
            else: derived = {}
        conn.commit()
        conn.set_session(isolation_level='READ COMMITTED')
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL lock_timeout='100ms'; SET LOCAL statement_timeout='2s'")
            if _versions(cur,username,lock=True) != versions: return {},set()
            values = [(username,canonical,POLICY,versions['catalog'],versions['viewer'],'ready' if connection else 'none',Json(connection) if connection else None)
                      for canonical,connection in {v[0]:v for v in derived.values() if v[0]}.values()]
            if values:
                execute_values(cur,'''INSERT INTO viewing_connection_context(username,target_identity,policy_version,catalog_revision,viewer_revision,status,connection) VALUES %s
                    ON CONFLICT(username,target_identity) DO UPDATE SET policy_version=excluded.policy_version,catalog_revision=excluded.catalog_revision,viewer_revision=excluded.viewer_revision,status=excluded.status,connection=excluded.connection,updated_at=now()''',values)
        conn.commit()
        merged = {**cached,**{v[0]:v[1] for v in derived.values() if v[0]}}
        return present_page(rows,{r['rating_key']:merged.get(identities.get(r['rating_key'])) for r in rows}),set(cached)
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()  # Also releases any session advisory lock.


def attach(rows, username):
    """Call after existing authorization, filtering, ordering and pagination."""
    if not enabled() or not rows: return
    try:
        result,_ = lookup(username, rows)
    except Exception as exc:
        log.warning('Viewing-history connection lookup unavailable (%s)',type(exc).__name__)
        result = {}
    for row in rows: row['viewing_history_connection'] = result.get(row['rating_key'])
