"""Explicit historical-source recovery. No encoder calls or production writes.

Identity follows a stable Plex GUID, never a title search. Historical fallback
uses captured library fields and separately captured stored semantic associations.
"""
from datetime import datetime, timezone
from psycopg2.extras import RealDictCursor
from .contracts import ContractError, fingerprint, metadata,utc,MEDIA_VERSION,POSTER_HIERARCHY
from .io import SourceError

POLICY = 'verified-plex-or-stored-history/1.0'


def context_keys(sources,keys):
    result=set(map(str,keys));pending=list(result)
    while pending:
        source=sources.get(pending.pop(),{})
        for field in ('show_rating_key','parent_rating_key'):
            value=source.get(field)
            if value is not None and str(value) not in result:
                result.add(str(value));pending.append(str(value))
    return sorted(result)


def load_associations(conn, keys):
    """Read the existing genre/cast/director associations without schema helpers."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('''SELECT l.rating_key,
            ARRAY(SELECT g.name FROM public.media_genres mg JOIN public.genres g ON g.id=mg.genre_id
                  WHERE mg.media_id=l.rating_key ORDER BY g.name) AS genres,
            ARRAY(SELECT d.name FROM public.media_directors md JOIN public.directors d ON d.id=md.director_id
                  WHERE md.media_id=l.rating_key ORDER BY d.name) AS directors,
            COALESCE((SELECT jsonb_agg(jsonb_build_object('tag',a.name,'order',ma.cast_order)
                         ORDER BY ma.cast_order NULLS LAST,a.name)
                      FROM public.media_actors ma JOIN public.actors a ON a.id=ma.actor_id
                      WHERE ma.media_id=l.rating_key),'[]'::jsonb) AS cast
            FROM public.library l WHERE l.rating_key=ANY(%s)''',([int(k) for k in keys],))
        return {str(r['rating_key']):dict(r) for r in cur.fetchall()}


def historical_raw(source, associations):
    """Explicit mapping, not a claim to be an original Plex API response."""
    kind=source['media_type'];captured=source.get('metadata') or {}
    def base(field,semantic):return source[field] if field in source else captured.get(semantic)
    result=dict(ratingKey=str(source['rating_key']),type=kind,title=base('title','title'),
        summary=base('summary','synopsis'),year=base('year','year'),duration=source.get('duration',
            captured['runtime_minutes']*60000 if captured.get('runtime_minutes') is not None else None),
        guid=source.get('plex_guid'),thumb=source.get('thumb_path'),
        parentRatingKey=str(source['parent_rating_key']) if source.get('parent_rating_key') is not None else None,
        grandparentRatingKey=str(source['show_rating_key']) if kind=='episode' and source.get('show_rating_key') is not None else None,
        index=source.get('episode_number') if kind=='episode' else source.get('season_number') if kind=='season' else None,
        parentIndex=source.get('season_number') if kind=='episode' else None,
        Genre=[dict(tag=v) for v in associations.get('genres',[])],
        Role=associations.get('cast',[]),Director=[dict(tag=v) for v in associations.get('directors',[])])
    for target,field in [('originalTitle','original_title'),('studio','studio'),('tagline','tagline'),
        ('contentRating','content_rating'),('originalLanguage','original_language')]:
        if field in captured:result[target]=captured[field]
    for target,field in [('Genre','genres'),('Director','directors'),('Writer','writers'),('Creator','creators'),
        ('ProductionCompany','production_companies'),('Country','countries'),('Collection','collections')]:
        if field in captured:result[target]=[dict(tag=v) for v in captured[field]]
    if 'cast' in captured:result['Role']=[dict(tag=v,order=i) for i,v in enumerate(captured['cast'])]
    if 'audio_languages' in captured:result['Media']=[dict(Part=[dict(Stream=[dict(streamType=2,languageCode=v) for v in captured['audio_languages']])])]
    return result


def safe_raw(raw):
    fields=('ratingKey','type','title','originalTitle','summary','year','duration','guid','thumb',
        'parentRatingKey','grandparentRatingKey','parentIndex','index','Genre','Role','Director',
        'Writer','Creator','studio','ProductionCompany','tagline','contentRating','Country',
        'originalLanguage','Collection')
    selected={k:raw[k] for k in fields if k in raw}
    # Preserve language input without storing filenames or other technical data.
    selected['Media']=[dict(Part=[dict(Stream=[{k:s.get(k) for k in ('streamType','language','languageCode')}
        for s in p.get('Stream',[]) if s.get('streamType')==2]) for p in m.get('Part',[])]) for m in raw.get('Media',[])]
    return selected


def validate_origin(source,key):
    approval=source.get('_metadata_recovery',{});origin=source.get('metadata_origin',{})
    if approval.get('policy')!=POLICY or not approval.get('reason') or origin.get('policy')!=POLICY:
        raise ContractError('Historical metadata recovery is not explicitly approved/versioned')
    utc(approval['approved_at'])
    raw=origin.get('raw_inputs',{})
    if fingerprint(raw)!=origin.get('raw_inputs_hash') or metadata(raw.get('media',{}),raw.get('show'),raw.get('season'))!=source['metadata']:
        raise ContractError('Recovered metadata differs from its attributed input snapshot')
    if origin.get('components',{}).get('media',{}).get('original_key')!=str(key):
        raise ContractError('Recovered media identity/lineage mismatch')
    for name,component in origin['components'].items():
        if component.get('source') not in ('plex-current','plex-guid-replacement','stored-library') or name not in raw:
            raise ContractError('Unrecognized historical metadata source')
        if component['source']=='stored-library':
            if str(raw[name].get('ratingKey'))!=component.get('original_key'):
                raise ContractError('Historical source identity mismatch')
        else:
            if str(raw[name].get('ratingKey'))!=component.get('resolved_key'):
                raise ContractError('Resolved source identity mismatch')
        if component['source']=='plex-guid-replacement':
            if component.get('verified_guid'):
                if component['verified_guid']!=raw[name].get('guid'):raise ContractError('Replacement stable GUID mismatch')
            elif not (component.get('verified_show_guid')==raw.get('show',{}).get('guid')
                and component.get('verified_show_guid') and raw[name].get('type')=='season'
                and component.get('season_number')==raw[name].get('index')):
                raise ContractError('Unverified replacement Plex identity')


class Resolver:
    def __init__(self, plex, sources, associations):
        self.plex=plex;self.sources=sources;self.associations=associations
        self.catalog=None;self.cache={}

    def _catalog(self):
        if self.catalog is None:
            self.catalog=[{k:r.get(k) for k in ('ratingKey','type','guid','parentRatingKey','index')}
                          for r in self.plex.catalog()]
        return self.catalog

    def get(self, key):
        key=str(key)
        if key in self.cache:return self.cache[key]
        source=self.sources.get(key)
        if not source:raise ContractError('Historical TV context is absent from the captured library')
        kind=source['media_type'];guid=source.get('plex_guid')
        try:
            raw=self.plex.metadata(source['rating_key'])
            if raw.get('type')!=kind or guid and raw.get('guid')!=guid:
                raise ContractError('Original Plex key now identifies a different entity')
            origin=dict(source='plex-current',original_key=key,resolved_key=str(raw['ratingKey']),verified_guid=guid)
        except SourceError as exc:
            if str(exc)!='HTTP_404':raise
            candidates=[]
            if guid and guid.startswith(('plex://','imdb://','tmdb://','tvdb://')):
                candidates=[r for r in self._catalog() if r['type']==kind and r['guid']==guid]
            if not candidates and kind=='season' and source.get('show_rating_key') is not None and source.get('season_number') is not None:
                parent,parent_origin=self.get(source['show_rating_key'])
                if parent_origin['source']!='stored-library' and parent_origin.get('verified_guid'):
                    candidates=[r for r in self._catalog() if r['type']=='season'
                        and str(r['parentRatingKey'])==str(parent['ratingKey']) and r['index']==source['season_number']]
            identities={str(r['ratingKey']) for r in candidates}
            if len(identities)>1:raise ContractError('Ambiguous stable Plex identity; explicit reconciliation required')
            if identities:
                raw=self.plex.metadata(next(iter(identities)))
                if raw.get('type')!=kind or (kind!='season' and raw.get('guid')!=guid):
                    raise ContractError('Replacement Plex identity verification failed')
                if kind=='season':
                    parent,parent_origin=self.get(source['show_rating_key'])
                    if (str(raw.get('parentRatingKey'))!=str(parent['ratingKey']) or raw.get('index')!=source['season_number']):
                        raise ContractError('Replacement season context verification failed')
                exact=bool(guid and raw.get('guid')==guid)
                origin=dict(source='plex-guid-replacement',original_key=key,resolved_key=str(raw['ratingKey']),
                    verified_guid=guid if exact else None,
                    identity_rule='exact-stable-guid' if exact else 'verified-show-guid-and-season-index')
                if not exact:origin.update(verified_show_guid=parent_origin['verified_guid'],season_number=source['season_number'])
            else:
                raw=historical_raw(source,self.associations.get(key,{}))
                origin=dict(source='stored-library',original_key=key,resolved_key=None,verified_guid=None,
                    stored_guid=guid,source_limitations='Only library/captured-generation fields; associations may contain prior importer inheritance or stale tags')
        if not raw.get('title'):raise ContractError('Historical metadata has no recorded title')
        self.cache[key]=(raw,origin)
        return raw,origin

    def payload(self, source):
        raw,origin=self.get(source['rating_key']);show=None;season=None
        origins=dict(media=origin);raws=dict(media=safe_raw(raw))
        kind=source['media_type']
        if kind in ('season','episode'):
            show_key=source.get('show_rating_key') or (source.get('parent_rating_key') if kind=='season' else None)
            if show_key is None:raise ContractError('Historical child has no recorded show identity')
            show,show_origin=self.get(show_key)
            if show.get('type')!='show':raise ContractError('Historical parent is not a show')
            # A live recovered child must belong to the verified same show.
            if origin['source']!='stored-library':
                parent_key=raw.get('grandparentRatingKey') if kind=='episode' else raw.get('parentRatingKey')
                if str(parent_key)!=str(show['ratingKey']):raise ContractError('Recovered child belongs to a different show')
            origins['show']=show_origin;raws['show']=safe_raw(show)
            if kind=='episode':
                parent=source.get('parent_rating_key')
                if parent is not None:
                    season,season_origin=self.get(parent)
                    if season.get('type')!='season':raise ContractError('Historical episode parent is not a season')
                    origins['season']=season_origin;raws['season']=safe_raw(season)
        value=metadata(raw,show,season)
        sources=[raw] if kind in ('movie','show') else [raw,show] if kind=='season' else [show,season,raw]
        reference={k:raw.get(k) for k in ('type','ratingKey','thumb','parentRatingKey','grandparentRatingKey')}
        reference['_poster_sources']=[{k:r.get(k) for k in ('type','ratingKey','thumb')} for r in sources if r]
        provenance=dict(policy=POLICY,components=origins,raw_inputs=raws,raw_inputs_hash=fingerprint(raws))
        return value,reference,provenance


def prepare(store,gid,plex,*,reason,progress=lambda value:None):
    """Retry only 404 preparation failures under an explicit operator policy."""
    from .backfill import checkpoint_metadata,safe_error
    import time
    if not reason or not reason.strip():raise ContractError('recover-metadata requires --reason recording the historical-source decision')
    generation=store.mutable(gid)
    if generation['contract']['media_serializer']!=MEDIA_VERSION or generation['contract']['poster_hierarchy']!=POSTER_HIERARCHY:
        raise ContractError('Recovery metadata/hierarchy contract differs from this implementation')
    rows=store.items(gid,'media_text');sources={r['item_key']:r['source'] for r in rows}
    targets=[]
    for row in rows:
        prep=store.preparation(gid,row['item_key'],'metadata')
        if prep and prep['status']=='failed' and (prep['provenance'].get('error')=='SourceError:HTTP_404'
            or prep['provenance'].get('policy')==POLICY or row['source'].get('_metadata_recovery',{}).get('policy')==POLICY):targets.append(row)
    if not targets:return
    approval=dict(policy=POLICY,reason=reason.strip(),approved_at=datetime.now(timezone.utc).isoformat())
    with store.writer(gid):
        resolver=Resolver(plex,sources,load_associations(store.conn,context_keys(sources,[r['item_key'] for r in targets])))
        for row in targets:
            started=time.perf_counter();error=None
            try:
                value,reference,origin=resolver.payload(row['source'])
                source={**row['source'],'metadata':value,'poster_reference':reference,'_plex_revision':None,
                    '_metadata_recovery':approval,'metadata_origin':origin}
                validate_origin(source,row['item_key'])
                checkpoint_metadata(store,gid,row,source,value,
                    provenance=dict(source='explicit-recovery',**approval,components=origin['components'],raw_inputs_hash=origin['raw_inputs_hash']),
                    timing=dict(metadata_seconds=time.perf_counter()-started,recovered=True))
                store.conn.commit()
            except Exception as exc:
                error=safe_error(exc);store.conn.rollback()
                store.preparation(gid,row['item_key'],'metadata',status='failed',provenance=dict(error=error,**approval),
                    timing=dict(metadata_seconds=time.perf_counter()-started));store.conn.commit()
            progress(dict(stage='metadata-recovery',item_key=row['item_key'],error=error))
