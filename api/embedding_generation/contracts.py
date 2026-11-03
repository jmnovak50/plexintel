"""Canonical descriptive/behavioral contracts. Changes require new versions."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import unicodedata
from functools import lru_cache

MEDIA_VERSION = 'plexintel-media/2.1'
WATCH_VERSION = 'plexintel-watch/2.0'
WATCH_SCOPE_VERSION = 'library-linked-unembedded-quarantine/1.0'
PROFILE_VERSION = 'rating-key-text-mean/2.0'
FEATURE_VERSION = 'independent-text-poster-user-prospective/3.0'
LABEL_VERSION = 'legacy-engagement-060/1.0'
IMAGE_VERSION = 'exif-rgb-png-max1536/1.0'
DIMENSIONS = 768
CAST_LIMIT = 20
REPRESENTATION = 'independent-text-poster/1.0'
KINDS = ('media_text','media_poster','watch','user')
FEATURE_GROUPS = (('media_text',0,768),('media_poster',768,768),('user',1536,768))
POSTER_HIERARCHY = 'movie:self;show:self;season:self,show;episode:show,season,self/1.0'


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
    # Explicit credit order wins; ties retain source order. Missing orders use
    # returned Plex order, and this policy is part of MEDIA_VERSION.
    cast = sorted(enumerate(cast), key=lambda p: (p[1].get('order') is None,
                  number(p[1]['order']) if p[1].get('order') is not None else p[0], p[0]))
    parent = None
    if kind in ('season', 'episode'):
        if not show or show.get('type') != 'show' or not clean(show.get('title')):
            raise ContractError('TV child requires verified parent-show metadata')
        parent = {k: v for k, v in metadata(show).items() if k in (
            'title', 'original_title', 'year', 'synopsis', 'genres', 'creators', 'studio',
            'production_companies', 'countries', 'original_language', 'collections',
            'cast','writers','directors','content_rating')}
    return dict(media_type=kind, title=title, original_title=clean(raw.get('originalTitle')),
        year=number(raw.get('year')), runtime_minutes=(number(raw['duration']) / 60000
             if raw.get('duration') is not None else None),
        genres=names(raw.get('Genre')), synopsis=clean(raw.get('summary')),
        cast=names([v for _, v in cast], ordered=True, limit=CAST_LIMIT),
        directors=names(raw.get('Director')), writers=names(raw.get('Writer')),
        creators=names(raw.get('Creator')), studio=clean(raw.get('studio')),
        production_companies=names(raw.get('ProductionCompany')), tagline=clean(raw.get('tagline')),
        content_rating=clean(raw.get('contentRating')), countries=names(raw.get('Country')),
        original_language=clean(raw.get('originalLanguage')),
        audio_languages=names([s.get('languageCode') or s.get('language')
             for m in raw.get('Media') or [] for p in m.get('Part') or []
             for s in p.get('Stream') or [] if s.get('streamType') == 2]),
        collections=names(raw.get('Collection')), show_context=parent,
        season_context=(dict(title=clean(season.get('title')),synopsis=clean(season.get('summary')),
            year=number(season.get('year')),season_number=number(season.get('index')))
            if kind=='episode' and season and season.get('type')=='season' else None),
        season_number=number(raw.get('parentIndex') if kind == 'episode' else raw.get('index'))
             if kind in ('episode', 'season') else None,
        episode_number=number(raw.get('index')) if kind == 'episode' else None,
        episode_title=title if kind == 'episode' else None,
        episode_synopsis=clean(raw.get('summary')) if kind == 'episode' else None)


def media_text(value):
    return MEDIA_VERSION + '\n' + canonical(value)


def watch_text(event, media):
    """No username, display name, IP, player/device or session identifiers."""
    behavior = dict(played_seconds=number(event.get('played_seconds')),
                    percent_complete=number(event.get('percent_complete')))
    return WATCH_VERSION + '\n' + canonical({'media': media, 'behavior': behavior})


@dataclass(frozen=True)
class Encoder:
    name: str
    digest: str
    variant: str
    quantization: str
    projector_hash: str
    dimensions: int = DIMENSIONS
    normalization: str = 'ollama-l2-unit/1.0'
    num_ctx: int = 8192
    num_thread: int = 16
    num_batch: int = 2048

    def __post_init__(self):
        if self.name != 'embeddinggemma-2:latest' or not re.fullmatch(r'[0-9a-f]{64}', self.digest):
            raise ContractError('Only the installed, digest-pinned EmbeddingGemma 2 is supported')
        if self.dimensions != DIMENSIONS or not self.variant or not self.projector_hash:
            raise ContractError('Unverified encoder contract')

    @property
    def reference(self):
        return 'sha256:' + self.digest

    @property
    def identity(self):
        return fingerprint(asdict(self))


def contract(encoder, profile_threshold=0.5):
    return dict(representation=REPRESENTATION,encoder=asdict(encoder), media_serializer=MEDIA_VERSION,
        watch_serializer=WATCH_VERSION, watch_scope=WATCH_SCOPE_VERSION, image=IMAGE_VERSION, profile=PROFILE_VERSION,
        features=FEATURE_VERSION, labels=LABEL_VERSION, profile_threshold=profile_threshold,
        watch_threshold=0.5, label_positive_threshold=0.60, cast_limit=CAST_LIMIT,
        label_weights=dict(interested=.75,watched_like=3.,negative=5.,rewatch_step=.5,maximum=5.),
        feedback_bonus=.1,
        ordering='media_text,media_poster,user', dimensions=768, embedding_dimensions=2304,
        missing_art_policy='null-image-vector-xgboost-missing-indicator/1.0',
        visual_user_profile=None,
        poster_hierarchy=POSTER_HIERARCHY)


def modality_contract(specification,kind):
    """Only dependencies that can change this modality's input or arithmetic.

    Feature vocabularies, other modalities and label policy cannot force an
    unrelated image/text request. The full generation contract still pins the
    complete downstream model, while per-modality contracts authorize reuse.
    """
    if specification.get('representation')!=REPRESENTATION or kind not in KINDS:
        raise ContractError('Unsupported representation/modality contract')
    encoder=dict(specification['encoder'])
    if kind!='media_poster':encoder.pop('projector_hash',None)
    value=dict(modality=kind,encoder=encoder,dimensions=768,
        normalization='equal-mean-not-renormalized' if kind=='user' else specification['encoder']['normalization'])
    if kind=='media_text':value.update(serializer=specification['media_serializer'],input='text-only/1.0')
    elif kind=='media_poster':value.update(preprocessing=specification['image'],input='image-only/1.0',
        missing=specification['missing_art_policy'])
    elif kind=='watch':value.update(serializer=specification['watch_serializer'],media_serializer=specification['media_serializer'],input='text-only/1.0')
    else:value.update(profile=specification['profile'],profile_modality='media_text',
        profile_threshold=specification['profile_threshold'],media_text_contract=fingerprint(modality_contract(specification,'media_text')))
    return value


def embedding_input_hash(specification,kind,*,metadata=None,poster_hash=None,text=None,event_hash=None,media_hash=None,source=None,dependencies=()):
    value=dict(modality_contract=fingerprint(modality_contract(specification,kind)))
    if kind=='media_text':value.update(metadata_hash=fingerprint(metadata),text=media_text(metadata))
    elif kind=='media_poster':value.update(poster_hash=poster_hash)
    elif kind=='watch':value.update(text=text,event_hash=event_hash,media_hash=media_hash)
    elif kind=='user':value.update(source=source,dependencies=dependencies)
    return fingerprint(value)


def vector(value, *, unit=False):
    if hasattr(value, 'to_numpy'):
        value = value.to_numpy()
    result = [float(v) for v in value]
    if len(result) != DIMENSIONS or not all(math.isfinite(v) for v in result):
        raise ContractError('Embedding must contain exactly 768 finite values')
    norm = math.sqrt(sum(v*v for v in result))
    if norm <= 0 or unit and abs(norm - 1) > 1e-4:
        raise ContractError('Embedding normalization violated')
    return result


def same_generation(*values):
    ids = {v['generation_id'] for v in values}
    contracts = {v['contract_hash'] for v in values}
    if len(ids) != 1 or len(contracts) != 1 or any(v['status'] != 'succeeded' for v in values):
        raise ContractError('Mixed, incomplete or incompatible embedding generations')


def cosine(a, b):
    a, b = vector(a), vector(b)
    return sum(x*y for x,y in zip(a,b)) / math.sqrt(sum(x*x for x in a)*sum(y*y for y in b))
