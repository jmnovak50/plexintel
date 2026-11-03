from copy import deepcopy

import pytest

from api.embedding_generation.contracts import ContractError,fingerprint
from api.embedding_generation.history_scope import partition_history,coverage_report


def snapshot():
    return dict(media=[dict(rating_key=1)],events=[dict(watch_id=1,rating_key=1,username='owner'),
        dict(watch_id=2,rating_key=1,username='owner'),dict(watch_id=3,rating_key=2,username='private-owner')],
        legacy_watch_ids=[1],feedback=[])


def test_scope_includes_existing_and_new_library_events_and_accounts_for_all_history():
    original=snapshot();before=deepcopy(original)
    scoped=partition_history(original)
    assert original==before
    assert [e['watch_id'] for e in scoped['events']]==[1,2]
    assert scoped['quarantined_events'][0]['event']==original['events'][2]
    coverage=coverage_report(scoped,details=True)
    assert coverage['source_watch_events']==3
    assert coverage['eligible_watch_events']==2 and coverage['quarantined_watch_events']==1
    assert coverage['existing_watch_embeddings_covered']==1 and coverage['new_library_linked_events']==1
    assert 'username' not in str(coverage) and 'private-owner' not in str(coverage)
    assert fingerprint(partition_history(scoped))==fingerprint(scoped)


def test_quarantined_event_reenters_when_media_is_restored():
    scoped=partition_history(snapshot())
    scoped['media'].append(dict(rating_key=2))
    refreshed=partition_history(scoped)
    assert [e['watch_id'] for e in refreshed['events']]==[1,2,3]
    assert refreshed['quarantined_events']==[]
    assert refreshed['watch_coverage']['quarantined_watch_events']==0


def test_existing_vector_or_orphaned_vector_membership_cannot_be_excluded():
    data=snapshot();data['legacy_watch_ids'].append(3)
    with pytest.raises(ContractError,match='Existing watch vector has unlinked media'):partition_history(data)
    data['legacy_watch_ids']=[99]
    with pytest.raises(ContractError,match='lacks its source event'):partition_history(data)


def test_quarantine_tampering_and_duplicate_identity_fail():
    scoped=partition_history(snapshot())
    scoped['quarantined_events'][0]['event']['rating_key']=1234
    with pytest.raises(ContractError,match='Corrupt historical quarantine'):partition_history(scoped)
    data=snapshot();data['events'].append(deepcopy(data['events'][0]))
    with pytest.raises(ContractError,match='Duplicate watch identity'):partition_history(data)
