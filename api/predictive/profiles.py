"""Canonical qualification arithmetic, shared by historical and current profiles."""
def qualifying_profiles(events, media, threshold):
    """Exact original qualification/weighting: max ratio > threshold OR count >=5.

    Media vectors are each used once per rating key; means are not normalized.
    Availability cutoffs are applied separately by the historical feature builder.
    """
    pairs = {}
    for event in events:
        key = str(event['rating_key'])
        parent = media.get(key)
        if not parent or event.get('played_seconds') is None:
            continue
        runtime = runtime_seconds(parent)
        if not runtime or runtime <= 0:
            continue
        pair = pairs.setdefault((event['username'], key), dict(count=0, ratio=0))
        pair['count'] += 1
        pair['ratio'] = max(pair['ratio'], event['played_seconds'] / runtime)
    profiles = {}
    for (owner, key), stats in pairs.items():
        if stats['ratio'] > threshold or stats['count'] >= 5:
            profiles.setdefault(owner, []).append(key)
    return {owner: sorted(keys) for owner, keys in profiles.items()}

def runtime_seconds(parent):
    source = parent['source']
    if 'duration' in source:
        return source['duration'] / 1000 if source['duration'] is not None else None
    value = source['metadata'].get('runtime_minutes')
    return value * 60 if value is not None else None
