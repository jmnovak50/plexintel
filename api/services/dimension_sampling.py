"""Representative labeling examples from bounded coordinate tails.

The full media population is retained. Only prompt examples are grouped, using
existing typed canonical GUIDs and stored TV hierarchy, never guessed franchises.
"""
import math
from api.predictive.recovery import stable_identity, IdentityError

SAMPLE_POLICY = 'canonical-series-tail/1'
TAIL_FRACTION = .05


def sample_groups(library):
    rows = {r['rating_key']: r for r in library}
    def canonical(row):
        try: return stable_identity(row.get('media_type'), row.get('plex_guid'))
        except IdentityError: return ('unknown', row['rating_key'])
    result = {}
    for key, row in rows.items():
        identity = canonical(row)
        show = row if row.get('media_type') == 'show' else rows.get(row.get('show_rating_key'))
        series = canonical(show) if show and show.get('media_type') == 'show' else None
        if isinstance(series, tuple): series = None  # Unknown identity is not independent support.
        result[key] = dict(canonical=identity, series=series,
                           family=series or identity, known=not isinstance(identity, tuple))
    return result


def representative_tail(ids, values, index, count, groups, ascending=False):
    import numpy as np
    count = min(count, len(ids)//2)
    if count <= 0: return []
    order = np.argsort(values[:, index] if ascending else -values[:, index], kind='stable')
    # Preserve rank order and the true extreme; never search the middle to fill a prompt.
    width = min(len(ids)//2, max(count, math.ceil(len(ids)*TAIL_FRACTION)))
    if ascending:
        high_region = set(np.argsort(-values[:, index], kind='stable')[:width])
        order = [i for i in order if i not in high_region]
    selected, canonical_seen, family_seen = [], set(), set()
    for i in order[:width]:
        key = ids[i]
        group = groups.get(key, dict(canonical=('unknown',key),family=('unknown',key)))
        if group['canonical'] in canonical_seen or group['family'] in family_seen:
            continue
        selected.append(key)
        canonical_seen.add(group['canonical']); family_seen.add(group['family'])
        if len(selected) >= count: break
    return selected
