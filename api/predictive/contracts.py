"""Versioned text inputs; no migration or publication state."""
from datetime import datetime, timezone
from functools import lru_cache
import hashlib,json,math,unicodedata
MEDIA_VERSION='plexintel-media/2.1'
WATCH_VERSION='plexintel-watch/2.0'
WATCH_SCOPE_VERSION='library-linked-unembedded-quarantine/1.0'
PROFILE_VERSION='canonical-text-mean/1.0'
FEATURE_VERSION=TEXT_FEATURE_VERSION='canonical-text-user/1.0'
LABEL_VERSION='legacy-engagement-060/1.0'
DIMENSIONS=768
CAST_LIMIT=20
POSTER_HIERARCHY='unused-text-only'
class ContractError(ValueError):
    pass

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

@lru_cache(maxsize=65536)
def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ContractError('An explicit UTC/offset timestamp is required')
    return value.astimezone(timezone.utc)

def timestamp(value):
    return utc(value).isoformat()

def clean(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ContractError('Expected text')
    value = ' '.join(unicodedata.normalize('NFC', value).split())
    if len(value) > 50000:
        raise ContractError('Metadata field exceeds documented bound; no silent truncation')
    return value or None

def names(values, *, ordered=False, limit=None):
    result = []
    for value in values or []:
        if isinstance(value, dict):
            value = value.get('tag', value.get('name'))
        value = clean(value)
        if value and value not in result:
            result.append(value)
    if not ordered:
        result.sort(key=lambda v: (v.casefold(), v))
    return result[:limit] if limit else result

def number(value, *, minimum=0):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise ContractError('Boolean is not numeric metadata')
    value = float(value)
    if not math.isfinite(value) or value < minimum:
        raise ContractError('Invalid numeric metadata')
    return int(value) if value.is_integer() else value

def metadata(raw, show=None, season=None):
    """Project Plex JSON only; absent fields stay null/empty, never invented.

    Numeric ratings/votes/popularity, user state and technical file details are
    deliberately not selected. Parent context is an explicitly separate source.
    """
    kind = raw.get('type')
    if kind not in ('movie', 'show', 'season', 'episode'):
        raise ContractError('Unsupported media type')
    title = clean(raw.get('title'))
    if not title:
        raise ContractError('Missing title')
    cast = raw.get('Role') or []
    cast = sorted(enumerate(cast), key=lambda p: (p[1].get('order') is None, number(p[1]['order']) if p[1].get('order') is not None else p[0], p[0]))
    parent = None
    if kind in ('season', 'episode'):
        if not show or show.get('type') != 'show' or (not clean(show.get('title'))):
            raise ContractError('TV child requires verified parent-show metadata')
        parent = {k: v for k, v in metadata(show).items() if k in ('title', 'original_title', 'year', 'synopsis', 'genres', 'creators', 'studio', 'production_companies', 'countries', 'original_language', 'collections', 'cast', 'writers', 'directors', 'content_rating')}
    return dict(media_type=kind, title=title, original_title=clean(raw.get('originalTitle')), year=number(raw.get('year')), runtime_minutes=number(raw['duration']) / 60000 if raw.get('duration') is not None else None, genres=names(raw.get('Genre')), synopsis=clean(raw.get('summary')), cast=names([v for _, v in cast], ordered=True, limit=CAST_LIMIT), directors=names(raw.get('Director')), writers=names(raw.get('Writer')), creators=names(raw.get('Creator')), studio=clean(raw.get('studio')), production_companies=names(raw.get('ProductionCompany')), tagline=clean(raw.get('tagline')), content_rating=clean(raw.get('contentRating')), countries=names(raw.get('Country')), original_language=clean(raw.get('originalLanguage')), audio_languages=names([s.get('languageCode') or s.get('language') for m in raw.get('Media') or [] for p in m.get('Part') or [] for s in p.get('Stream') or [] if s.get('streamType') == 2]), collections=names(raw.get('Collection')), show_context=parent, season_context=dict(title=clean(season.get('title')), synopsis=clean(season.get('summary')), year=number(season.get('year')), season_number=number(season.get('index'))) if kind == 'episode' and season and (season.get('type') == 'season') else None, season_number=number(raw.get('parentIndex') if kind == 'episode' else raw.get('index')) if kind in ('episode', 'season') else None, episode_number=number(raw.get('index')) if kind == 'episode' else None, episode_title=title if kind == 'episode' else None, episode_synopsis=clean(raw.get('summary')) if kind == 'episode' else None)

def media_text(value):
    return MEDIA_VERSION + '\n' + canonical(value)

def watch_text(event, media):
    """No username, display name, IP, player/device or session identifiers."""
    behavior = dict(played_seconds=number(event.get('played_seconds')), percent_complete=number(event.get('percent_complete')))
    return WATCH_VERSION + '\n' + canonical({'media': media, 'behavior': behavior})

def vector(value, *, unit=False):
    if hasattr(value, 'to_numpy'):
        value = value.to_numpy()
    result = [float(v) for v in value]
    if len(result) != DIMENSIONS or not all((math.isfinite(v) for v in result)):
        raise ContractError('Embedding must contain exactly 768 finite values')
    norm = math.sqrt(sum((v * v for v in result)))
    if norm <= 0 or (unit and abs(norm - 1) > 0.0001):
        raise ContractError('Embedding normalization violated')
    return result

def cosine(a, b):
    a, b = (vector(a), vector(b))
    return sum((x * y for x, y in zip(a, b))) / math.sqrt(sum((x * x for x in a)) * sum((y * y for y in b)))

def specification(encoder, *, policy=None):
    policy=policy or {}
    return dict(encoder=encoder,media_serializer=MEDIA_VERSION,watch_serializer=WATCH_VERSION,
        profile=PROFILE_VERSION,features=FEATURE_VERSION,labels=LABEL_VERSION,ordering='media_text,user',
        dimensions=768,embedding_dimensions=1536,
        profile_threshold=float(policy.get('user_embeddings.engagement_threshold',.5)),watch_threshold=.5,
        movie_revisit_days=int(policy.get('training.movie_revisit_pending_days',21)),
        tv_revisit_days=int(policy.get('training.tv_revisit_pending_days',14)))

def modality_contract(spec,kind):
    if kind not in ('media_text','watch','user'):raise ContractError('Only text modalities supported')
    fields={'encoder':spec['encoder'],'kind':kind}
    if kind in ('media_text','watch'):fields['media_serializer']=spec['media_serializer']
    if kind=='watch':fields['watch_serializer']=spec['watch_serializer']
    if kind=='user':fields.update(profile=spec['profile'],profile_threshold=spec['profile_threshold'])
    return fields
