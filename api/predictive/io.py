"""Bounded local source access; text inference only."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
import requests,time
from .contracts import ContractError,fingerprint,vector
class SourceError(RuntimeError):
    pass

def call(session, method, url, *, attempts=3, timeout=(5, 30), accepted=(200,), **kwargs):
    for attempt in range(attempts):
        try:
            response = session.request(method, url, timeout=timeout, allow_redirects=False, **kwargs)
            if response.status_code in accepted:
                response._plexintel_attempts = attempt + 1
                return response
            if response.status_code not in (429, 500, 502, 503, 504):
                response.close()
                raise SourceError(f'HTTP_{response.status_code}')
            response.close()
        except requests.RequestException as exc:
            if method == 'POST' and (not isinstance(exc, requests.ConnectTimeout)):
                raise SourceError('ambiguous_inference_network_failure_not_retried') from None
            if attempt == attempts - 1:
                raise SourceError('network_failure') from None
        if attempt < attempts - 1:
            time.sleep(min(2 ** attempt, 4))
    raise SourceError('retry_limit')
class Plex:

    def __init__(self, base, token, cache, session=None):
        parsed = urlsplit(base)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.query:
            raise SourceError('invalid_plex_endpoint')
        self.base = base.rstrip('/')
        self.headers = {'X-Plex-Token': token, 'Accept': 'application/json', 'X-Plex-Product': 'PlexIntel', 'X-Plex-Client-Identifier': 'plexintel-embedding-generation'}
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True, mode=448)
        self.session = session or requests.Session()
        self.metadata_cache = {}

    def revisions(self, *, include_art=True):
        """Cheap paginated revision scan; detailed reads only for changed keys.

        An absent updatedAt is unknown and never authorizes cache reuse. Source
        thumb identities and parent revisions are included by prepare_metadata.
        """
        result = {}
        for raw in self.catalog():
            if raw.get('updatedAt') is not None:
                fields = ('updatedAt', 'parentRatingKey', 'grandparentRatingKey')
                if include_art:
                    fields += ('thumb', 'parentThumb', 'grandparentThumb')
                result[str(raw['ratingKey'])] = fingerprint({k: raw.get(k) for k in fields})
        return result

    def catalog(self):
        """Read the complete current catalog; stable GUIDs identify replacements."""
        sections = call(self.session, 'GET', self.base + '/library/sections', headers=self.headers).json().get('MediaContainer', {}).get('Directory', [])
        for section in sections:
            types = (1,) if section.get('type') == 'movie' else (2, 3, 4) if section.get('type') == 'show' else ()
            for kind in types:
                offset = 0
                for _ in range(10000):
                    container = call(self.session, 'GET', self.base + f"/library/sections/{int(section['key'])}/all", headers={**self.headers, 'X-Plex-Container-Start': str(offset), 'X-Plex-Container-Size': '500'}, params={'type': kind}).json().get('MediaContainer', {})
                    records = container.get('Metadata', [])
                    yield from records
                    offset += len(records)
                    total = container.get('totalSize')
                    if total is not None and offset >= int(total) or (total is None and len(records) < 500):
                        break
                    if not records:
                        raise SourceError('truncated_plex_revision_scan')
                else:
                    raise SourceError('plex_revision_page_limit')

    def metadata(self, key):
        key = int(key)
        if key not in self.metadata_cache:
            response = call(self.session, 'GET', f'{self.base}/library/metadata/{key}', headers=self.headers)
            records = response.json().get('MediaContainer', {}).get('Metadata', [])
            if len(records) != 1 or int(records[0]['ratingKey']) != key:
                raise SourceError('metadata_identity_mismatch')
            self.metadata_cache[key] = records[0]
        return self.metadata_cache[key]
