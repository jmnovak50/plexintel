"""Audited suppression containment; this never resolves uncertain episode identity.

Only the eight inspected local-key Friends records may use this exception.
Unknown watch history still fails closed before this policy is considered.
"""
from .contracts import ContractError
from .recovery import IdentityError, validate_origin

QUARANTINE_POLICY = 'audited-series-suppression/1.0'
FRIENDS_IDENTITY = 'show:plex://show/5d9c086d2192ba001f3101c6'
# Rating keys and episode coordinates from the read-only identity reconciliation.
AUDITED_EPISODES = {
    '14808': (4, 24), '14833': (5, 24), '14858': (6, 24), '14859': (6, 25),
    '14884': (7, 24), '14909': (8, 24), '14934': (9, 24), '14953': (10, 18),
}


def suppression_scope(identity, key):
    """Return a verified series containment scope, never a target identity."""
    key = str(key)
    source = identity.media.get(key, {}).get('source', {})
    meta = source.get('metadata', {})
    coordinates = AUDITED_EPISODES.get(key)
    if (coordinates is None or source.get('plex_guid') != 'local://' + key
        or str(source.get('rating_key')) != key
        or source.get('media_type') != 'episode' or meta.get('media_type') != 'episode'
        or any(type(meta.get(field)) is not int or type(source.get(field)) is not int
               for field in ('season_number', 'episode_number'))
        or (meta.get('season_number'), meta.get('episode_number')) != coordinates
        or (source.get('season_number'), source.get('episode_number')) != coordinates):
        raise IdentityError('Unresolved suppression lacks audited series containment')
    if source.get('metadata_origin') or source.get('_metadata_recovery'):
        try:
            validate_origin(source, key)
        except (ContractError, KeyError, TypeError) as exc:
            raise IdentityError('Invalid containment-source provenance') from exc
    show = identity.identity(str(source.get('show_rating_key')))
    if show != FRIENDS_IDENTITY:
        raise IdentityError('Audited suppression has a different/unverified series')
    return show


def profile_exclusions(identity, groups):
    """Exclude resolved series members; unresolved watches are never bypassed."""
    excluded = set()
    for key in identity.media:
        try:
            if identity.group(key) in groups:
                excluded.add(key)
        except IdentityError:
            continue  # Candidate/history validation retains its fail-closed checks.
    return identity.expand(excluded)
