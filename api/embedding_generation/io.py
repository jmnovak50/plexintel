"""Bounded Plex reads, deterministic artwork, immutable Ollama requests."""
from dataclasses import asdict, dataclass
import base64
import hashlib
from io import BytesIO
from pathlib import Path
import time
from datetime import datetime, timezone
import warnings
from urllib.parse import urlsplit

from PIL import Image, ImageOps, UnidentifiedImageError
import requests

from .contracts import ContractError, Encoder, IMAGE_VERSION, fingerprint, vector

MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000


class SourceError(RuntimeError):
    pass


def call(session, method, url, *, attempts=3, timeout=(5, 30), accepted=(200,), **kwargs):
    for attempt in range(attempts):
        try:
            response = session.request(method, url, timeout=timeout, allow_redirects=False, **kwargs)
            if response.status_code in accepted:
                response._plexintel_attempts=attempt+1
                return response
            if response.status_code not in (429, 500, 502, 503, 504):
                response.close()
                raise SourceError(f'HTTP_{response.status_code}')
            response.close()
        except requests.RequestException as exc:
            if method=='POST' and not isinstance(exc,requests.ConnectTimeout):
                raise SourceError('ambiguous_inference_network_failure_not_retried') from None
            if attempt == attempts-1:
                raise SourceError('network_failure') from None
        if attempt < attempts-1:
            time.sleep(min(2**attempt, 4))
    raise SourceError('retry_limit')


def preprocess(raw, content_type):
    """Keep aspect/pixels up to max1536; Ollama owns its vision-tower transform."""
    mime = content_type.partition(';')[0].strip().lower()
    if mime not in ('image/jpeg', 'image/png', 'image/webp') or not raw or len(raw) > MAX_IMAGE_BYTES:
        raise SourceError('invalid_image_mime_or_size')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as probe:
                expected = {'image/jpeg':'JPEG', 'image/png':'PNG', 'image/webp':'WEBP'}[mime]
                if probe.format != expected or probe.width*probe.height > MAX_IMAGE_PIXELS or getattr(probe, 'n_frames', 1) != 1:
                    raise SourceError('invalid_image_dimensions_or_format')
                probe.verify()
            with Image.open(BytesIO(raw)) as source:
                picture = ImageOps.exif_transpose(source).convert('RGB')
                picture.thumbnail((1536,1536), Image.Resampling.LANCZOS)
                output = BytesIO()
                picture.save(output, format='PNG', optimize=False, compress_level=6)
                return output.getvalue(), picture.size
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise SourceError('image_decode_failed') from None


@dataclass
class Poster:
    provenance: dict
    data: bytes | None
    timing: dict | None = None


class Plex:
    def __init__(self, base, token, cache, session=None):
        parsed = urlsplit(base)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.query:
            raise SourceError('invalid_plex_endpoint')
        self.base = base.rstrip('/')
        self.headers = {'X-Plex-Token':token, 'Accept':'application/json',
                        'X-Plex-Product':'PlexIntel', 'X-Plex-Client-Identifier':'plexintel-embedding-generation'}
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.session = session or requests.Session()
        self.metadata_cache = {}

    def revisions(self):
        """Cheap paginated revision scan; detailed reads only for changed keys.

        An absent updatedAt is unknown and never authorizes cache reuse. Source
        thumb identities and parent revisions are included by prepare_metadata.
        """
        result={}
        for raw in self.catalog():
            if raw.get('updatedAt') is not None:
                result[str(raw['ratingKey'])]=fingerprint({k:raw.get(k) for k in (
                    'updatedAt','thumb','parentThumb','grandparentThumb','parentRatingKey','grandparentRatingKey')})
        return result

    def catalog(self):
        """Read the complete current catalog; stable GUIDs identify replacements."""
        sections=call(self.session,'GET',self.base+'/library/sections',headers=self.headers).json().get('MediaContainer',{}).get('Directory',[])
        for section in sections:
            types=(1,) if section.get('type')=='movie' else (2,3,4) if section.get('type')=='show' else ()
            for kind in types:
                offset=0
                for _ in range(10000):
                    container=call(self.session,'GET',self.base+f"/library/sections/{int(section['key'])}/all",
                        headers={**self.headers,'X-Plex-Container-Start':str(offset),'X-Plex-Container-Size':'500'},
                        params={'type':kind}).json().get('MediaContainer',{})
                    records=container.get('Metadata',[])
                    yield from records
                    offset+=len(records)
                    total=container.get('totalSize')
                    if total is not None and offset>=int(total) or total is None and len(records)<500:break
                    if not records:raise SourceError('truncated_plex_revision_scan')
                else:raise SourceError('plex_revision_page_limit')

    def metadata(self, key):
        key = int(key)
        if key not in self.metadata_cache:
            response = call(self.session,'GET',f'{self.base}/library/metadata/{key}', headers=self.headers)
            records = response.json().get('MediaContainer',{}).get('Metadata',[])
            if len(records) != 1 or int(records[0]['ratingKey']) != key:
                raise SourceError('metadata_identity_mismatch')
            self.metadata_cache[key] = records[0]
        return self.metadata_cache[key]

    def poster(self, raw, lookup=lambda k:None, save=lambda k,v:None, *, force=False,force_checked=None):
        kind = raw['type']
        sources = [raw]
        if '_poster_sources' in raw:
            sources=raw['_poster_sources']
        elif kind in ('season', 'episode'):
            show_key = raw.get('grandparentRatingKey') if kind == 'episode' else raw.get('parentRatingKey')
            show = self.metadata(show_key) if show_key else None
            season = self.metadata(raw['parentRatingKey']) if kind == 'episode' and raw.get('parentRatingKey') else None
            sources = [show, season, raw] if kind == 'episode' else [raw,show]
        failures = []
        retrieval=0.0
        preprocessing=0.0
        for source in sources:
            if not source or not source.get('thumb'):
                failures.append('missing_reference')
                continue
            path = source['thumb']
            parts = urlsplit(path)
            if parts.scheme or parts.netloc or parts.query or not path.startswith('/library/metadata/') or '..' in path:
                raise SourceError('invalid_poster_reference')
            try:
                source_id=fingerprint(dict(server=self.base,source=path,preprocessing=IMAGE_VERSION))
                force_source=force and (force_checked is None or source_id not in force_checked)
                cached=lookup(source_id)
                if cached and cached.get('state')=='joint':cached={**cached,'state':'available'}
                now=datetime.now(timezone.utc)
                if cached and cached.get('state')=='unavailable':
                    if not force_source and (now-datetime.fromisoformat(cached['checked_at'])).total_seconds()<3600:
                        failures.append(cached['error']);continue
                    cached=None
                target=None
                if cached and cached.get('content_sha256'):
                    target=self.cache/(cached['content_sha256']+'.png')
                    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=cached['content_sha256']:
                        cached=None
                if cached and not force_source and (now-datetime.fromisoformat(cached['checked_at'])).total_seconds()<86400:
                    provenance={k:v for k,v in cached.items() if k not in ('etag','last_modified','checked_at')}
                    provenance['fallback_chain']=list(failures)
                    return Poster(provenance,target.read_bytes(),dict(retrieval_seconds=retrieval,preprocessing_seconds=preprocessing,cache_hit=True))
                validators={}
                if cached and cached.get('etag'):validators['If-None-Match']=cached['etag']
                if cached and cached.get('last_modified'):validators['If-Modified-Since']=cached['last_modified']
                started=time.perf_counter()
                if force_checked is not None:force_checked.add(source_id)
                try:
                    response = call(self.session,'GET',self.base+path,
                        headers={**self.headers,'Accept':'image/jpeg,image/png,image/webp',**validators},
                        stream=True,accepted=(200,304))
                except SourceError:
                    retrieval+=time.perf_counter()-started;raise
                retrieval_recorded=False
                try:
                    if response.status_code==304:
                        if not cached:raise SourceError('not_modified_without_cache')
                        retrieval+=time.perf_counter()-started
                        retrieval_recorded=True
                        cached['checked_at']=now.isoformat();cached['fallback_chain']=list(failures);save(source_id,cached)
                        return Poster({k:v for k,v in cached.items() if k not in ('etag','last_modified','checked_at')},
                            target.read_bytes(),dict(retrieval_seconds=retrieval,preprocessing_seconds=preprocessing,cache_hit=True))
                    if int(response.headers.get('Content-Length',0)) > MAX_IMAGE_BYTES:
                        raise SourceError('image_too_large')
                    data = bytearray()
                    for chunk in response.iter_content(65536):
                        data.extend(chunk)
                        if len(data) > MAX_IMAGE_BYTES:
                            raise SourceError('image_too_large')
                    retrieval+=time.perf_counter()-started
                    retrieval_recorded=True
                    pre_start=time.perf_counter()
                    try:processed, size = preprocess(bytes(data), response.headers.get('Content-Type',''))
                    finally:preprocessing+=time.perf_counter()-pre_start
                finally:
                    if not retrieval_recorded:retrieval+=time.perf_counter()-started
                    response.close()
                digest = hashlib.sha256(processed).hexdigest()
                target = self.cache / (digest+'.png')
                if not target.exists():
                    import os, tempfile
                    fd, name = tempfile.mkstemp(dir=self.cache, suffix='.png')
                    try:
                        with os.fdopen(fd,'wb') as f:
                            f.write(processed);f.flush();os.fsync(f.fileno())
                        os.replace(name,target)
                    finally:
                        if os.path.exists(name):os.unlink(name)
                provenance=dict(state='available', source_key=int(source['ratingKey']), source=path,source_id=source_id,
                    source_sha256=hashlib.sha256(data).hexdigest(), content_sha256=digest,
                    preprocessing=IMAGE_VERSION, width=size[0],height=size[1],
                    mime='image/png', fallback_chain=failures)
                save(source_id,{**provenance,'checked_at':now.isoformat(),'etag':response.headers.get('ETag'),
                                'last_modified':response.headers.get('Last-Modified')})
                return Poster(provenance, processed,dict(retrieval_seconds=retrieval,
                    preprocessing_seconds=preprocessing,cache_hit=False))
            except SourceError as exc:
                failures.append(str(exc))
                save(source_id,dict(state='unavailable',error=str(exc),checked_at=datetime.now(timezone.utc).isoformat()))
        return Poster(dict(state='missing_art', content_sha256=None,
                           preprocessing=IMAGE_VERSION, fallback_chain=failures), None,
                           dict(retrieval_seconds=retrieval,preprocessing_seconds=preprocessing,cache_hit=False))


class Ollama:
    def __init__(self, host, encoder=None, session=None, timeout=300,*,num_thread=None,inference_attempts=3):
        self.host=host.rstrip('/')
        self.encoder=encoder
        self.session=session or requests.Session()
        self.timeout=timeout
        self.before_request=lambda:None
        if num_thread is not None and (type(num_thread) is not int or not encoder or not 1<=num_thread<=encoder.num_thread):
            raise ContractError('Execution thread override must be an integer reduction of the pinned default')
        if type(inference_attempts) is not int or not 1<=inference_attempts<=3:
            raise ContractError('Inference retry bound must be 1..3')
        self.num_thread_override=num_thread
        self.inference_attempts=inference_attempts
        self.execution_validation=None

    def resolve(self, threads=16):
        tags=call(self.session,'GET',self.host+'/api/tags').json()['models']
        selected=[m for m in tags if m['name']=='embeddinggemma-2:latest']
        if len(selected)!=1:
            raise ContractError('Required model is not installed; automatic pulls are forbidden')
        tag=selected[0]
        digest=tag['digest'].removeprefix('sha256:')
        info=call(self.session,'POST',self.host+'/api/show',json={'model':'sha256:'+digest}).json()
        if not {'embedding','vision'}.issubset(info.get('capabilities',[])):
            raise ContractError('Pinned variant does not support joint vision embeddings')
        projector=info.get('projector_info') or {}
        if not projector.get('clip.has_vision_encoder'):
            raise ContractError('Missing vision projector')
        self.encoder=Encoder(tag['name'],digest,tag['details'].get('parent_model') or tag['details']['family'],
            tag['details']['quantization_level'],fingerprint(projector), num_thread=int(threads or 16))
        return self.encoder

    def verify_pinned(self):
        if not self.encoder:raise ContractError('Pinned encoder is required')
        info=call(self.session,'POST',self.host+'/api/show',json={'model':self.encoder.reference}).json()
        if not {'embedding','vision'}.issubset(info.get('capabilities',[])) or fingerprint(info.get('projector_info') or {})!=self.encoder.projector_hash:
            raise ContractError('Installed immutable encoder/projector differs from the pinned generation')
        return self.encoder

    def embed(self, text=None, poster=None):
        if not self.encoder:
            raise ContractError('Resolve immutable model first')
        if (text is not None)==(poster is not None):
            raise ContractError('Canonical embedding requires exactly one modality; joint inference is experimental only')
        if text is not None and (not isinstance(text,str) or not text):
            raise ContractError('Text embedding requires nonempty text')
        self.before_request()
        item={} if text is None else {'text':text}
        if poster is not None:
            item['image']=base64.b64encode(poster).decode()
        payload=dict(model=self.encoder.reference, input=item, dimensions=768, truncate=False,
            keep_alive='15m', options={'num_ctx':self.encoder.num_ctx,
                'num_thread':self.num_thread_override if self.num_thread_override is not None else self.encoder.num_thread,
                'num_batch':self.encoder.num_batch})
        start=time.perf_counter()
        response=call(self.session,'POST',self.host+'/api/embed',json=payload,timeout=(5,self.timeout),attempts=self.inference_attempts)
        elapsed=time.perf_counter()-start
        data=response.json()
        if data.get('model') != self.encoder.reference:
            raise ContractError('Response encoder identity differs from pinned request')
        values=data.get('embeddings')
        if not isinstance(values,list) or len(values)!=1:
            raise ContractError('Expected one vector for one native multimodal operation')
        result=vector(values[0],unit=True)
        stats={k:data[k] for k in ('model','total_duration','load_duration','prompt_eval_count') if k in data}
        stats['client_seconds']=elapsed
        stats['request_attempts']=response._plexintel_attempts
        stats['output_dimensions']=768
        stats['output_norm']=sum(v*v for v in result)**.5
        stats['output_finite']=True
        stats['execution']=dict(policy='ollama-cpu-threads/1.0',requested_num_thread=payload['options']['num_thread'],
            manifest_num_thread=self.encoder.num_thread,source='operator-override' if self.num_thread_override is not None else 'manifest-default',
            semantic_encoder_hash=self.encoder.semantic_identity)
        if self.execution_validation:stats['execution']['validation']=self.execution_validation
        if 'total_duration' in stats and 'load_duration' in stats:
            stats['server_nonload_seconds']=(stats['total_duration']-stats['load_duration'])/1e9
        return result, stats
