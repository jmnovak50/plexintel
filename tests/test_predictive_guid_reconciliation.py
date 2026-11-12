"""Source-only GUID reconciliation must not relax the restored identity boundary."""
from collections import Counter
from copy import deepcopy
from unittest.mock import Mock

import numpy as np
import pytest

from api.predictive.contracts import ContractError, fingerprint, metadata, media_text, modality_contract, specification
from api.predictive.features import ProfileContext, feature_row, training_rows, unseen_candidate_keys
from api.predictive.prepare import record, refresh_vector
from api.predictive.recovery import CanonicalTitles, POLICY, Resolver

OLD = 'plex://movie/prior-match'
CURRENT = 'plex://movie/current-match'


@pytest.fixture
def rematch():
    # Anonymous shape of 6344: same key, type, year, full semantic input; stale GUID.
    raw = dict(ratingKey='6344', type='movie', guid=CURRENT, title='Recorded movie',
               year=2023, duration=6000000, summary='The complete recorded synopsis.',
               Director=[dict(tag='Recorded director')], Role=[dict(tag='Recorded actor')],
               Guid=[dict(id='imdb://tt1234567'), dict(id='tmdb://12345')])
    source = dict(rating_key=6344, media_type='movie', plex_guid=OLD,
                  title=raw['title'], year=2023, duration=6000000,
                  metadata=metadata(raw))
    plex = Mock()
    plex.metadata.return_value = raw
    return source, raw, plex


def resolved_source(source, raw):
    plex = Mock()
    plex.metadata.return_value = raw
    value, _, origin = Resolver(plex, {str(source['rating_key']): source}, {}).payload(source)
    return dict(source, metadata=value, metadata_origin=origin,
                _metadata_recovery=dict(policy=POLICY, reason='Verified current source',
                                        approved_at='2024-02-01T00:00:00+00:00'))


def unit(n):
    result = [0.] * 768
    result[n] = 1.
    return result


def test_previous_ordinary_metadata_path_did_not_check_the_stored_guid(rematch):
    # Evidence of the previous behavior, not approval to restore its missing check.
    from api.embedding_generation.backfill import media_payload
    source, raw, plex = rematch
    value, returned = media_payload(plex, source)
    assert value == source['metadata'] and returned['guid'] != source['plex_guid']
    with pytest.raises(ContractError, match='different entity'):
        Resolver(plex, {'6344': source}, {}).payload(source)


@pytest.mark.parametrize('change', [{}, {'title': 'Unrelated movie'}, {'year': 1998},
                                     {'type': 'episode'}, {'guid': 'plex://movie/third-match'}])
def test_matching_names_or_provider_ids_never_automatically_override_stale_identity(rematch, change):
    source, raw, plex = rematch
    plex.metadata.return_value = dict(raw, **change)
    original = deepcopy(source)
    with pytest.raises(ContractError, match='different entity'):
        Resolver(plex, {'6344': source}, {}).payload(source)
    assert source == original  # Resolver does not repair the source behind the caller's back.


def test_corrected_source_guid_passes_with_exactly_the_original_numeric_input(rematch):
    source, raw, _ = rematch
    corrected = dict(source, plex_guid=CURRENT)
    resolved = resolved_source(corrected, raw)
    assert metadata(raw) == source['metadata'] == resolved['metadata']
    assert {k for k in corrected if corrected[k] != source[k]} == {'plex_guid'}
    identity = CanonicalTitles({'6344': dict(source=resolved)})
    assert identity.identity('6344') == 'movie:' + CURRENT
    assert not identity.errors


def test_guid_only_source_repair_reuses_verified_vector_without_encoder_call(rematch):
    source, raw, _ = rematch
    spec = specification(dict(name='embeddinggemma-2:latest', digest='a' * 64))
    text = media_text(source['metadata'])
    digest = fingerprint(dict(contract=modality_contract(spec, 'media_text'), text=text))
    previous = record(spec, 'media_text', '6344', source, unit(0), digest)
    old = {'6344': dict(embedding=previous['embedding'],
                        provenance={k: v for k, v in previous.items() if k != 'embedding'})}
    corrected = resolved_source(dict(source, plex_guid=CURRENT), raw)
    encoder = Mock()
    stats = Counter()
    current = refresh_vector(spec, 'media_text', '6344', corrected,
                             media_text(corrected['metadata']), old, encoder, stats)
    encoder.embed.assert_not_called()
    assert stats == {'reused': 1}
    np.testing.assert_array_equal(current['embedding'], previous['embedding'])
    assert current['input_hash'] == previous['input_hash']
    assert current['vector_sha256'] == previous['vector_sha256']
    assert current['source']['plex_guid'] == CURRENT


def test_corrected_identity_keeps_alias_exclusion_watch_sim_and_candidate_suppression(rematch):
    source, raw, _ = rematch
    spec = specification(dict(name='embeddinggemma-2:latest', digest='a' * 64))
    media = {}
    for key, guid, title in ((6344, CURRENT, 'Recorded movie'),
                             (9000, CURRENT, 'Recorded movie'),
                             (1, 'plex://movie/prior-other', 'Earlier movie'),
                             (2, 'plex://movie/unseen-other', 'Other candidate')):
        r = dict(raw, ratingKey=str(key), guid=guid, title=title)
        s = resolved_source(dict(source, rating_key=key, plex_guid=guid, title=title), r)
        media[str(key)] = record(spec, 'media_text', str(key), s,
                                 unit(0 if key in (6344, 9000) else 1), str(key))
    def event(ident, key, day):
        return dict(watch_id=ident, rating_key=key, username='viewer', played_seconds=4800,
                    percent_complete=80, watched_at=f'2024-01-{day:02}T00:00:00+00:00',
                    verified_started_at=f'2024-01-{day:02}T00:00:00+00:00',
                    available_at=f'2024-01-{day:02}T01:00:00+00:00')
    events = [event(1, 1, 1), event(2, 6344, 2), event(3, 9000, 3)]
    watches = {str(e['watch_id']): record(spec, 'watch', str(e['watch_id']), e,
                unit(1 if e['rating_key'] == 1 else 0), str(e['watch_id'])) for e in events}
    inputs = dict(contract=spec, feature_space_id=fingerprint(spec), contract_hash=fingerprint(spec), snapshot=dict(events=events, feedback=[],
                                             as_of='2024-02-01T00:00:00+00:00'))
    identity = CanonicalTitles(media)
    assert identity.aliases(6344) == {'6344', '9000'}
    args = (inputs, media, watches, events, 'viewer', '6344', inputs['snapshot']['as_of'])
    context = ProfileContext(inputs, media, watches, events, 'viewer',
                             inputs['snapshot']['as_of'], identity=identity)
    before = feature_row(*args, context=context, identity=identity)
    assert before['dependencies']['profile_keys'] == ['1']
    assert before['watch_sim'] == pytest.approx(0.)
    for key in ('2', '3'):
        watches[key].update(embedding=unit(4), input_hash='changed-target')
    after = feature_row(*args, identity=identity)
    np.testing.assert_array_equal(before['embedding'], after['embedding'])
    assert before['watch_sim'] == after['watch_sim']
    assert unseen_candidate_keys(media, events, [], 'viewer', identity) == ['2']
    rows, _ = training_rows(inputs, media, watches)
    assert len([r for r in rows if r['canonical_identity'] == 'movie:' + CURRENT]) == 1
