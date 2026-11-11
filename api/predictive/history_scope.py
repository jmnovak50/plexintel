"""Approved history scope: encode library-linked events, retain unlinked evidence."""
from .contracts import ContractError, WATCH_SCOPE_VERSION, fingerprint


REASON='media_absent_from_library_without_existing_vector'


def event_hash(event):
    return fingerprint({k:v for k,v in event.items() if k!='observed_at'})


def partition_history(snapshot):
    """Return a new snapshot; never exclude an existing vector from rebuilding.

    Quarantine is generation-owned evidence, not a deletion from watch_history.
    Repartitioning is idempotent and admits a quarantined event if its media is
    subsequently restored. Existing-vector membership must be known to quarantine.
    """
    events=list(snapshot['events'])
    for record in snapshot.get('quarantined_events',[]):
        if record.get('reason')!=REASON or record.get('input_hash')!=event_hash(record['event']):
            raise ContractError('Corrupt historical quarantine provenance')
        events.append(record['event'])
    identities=[str(e['watch_id']) for e in events]
    if len(set(identities))!=len(identities):
        raise ContractError('Duplicate watch identity in eligible/quarantined history')
    legacy_known='legacy_watch_ids' in snapshot
    legacy={str(key) for key in snapshot.get('legacy_watch_ids',[])}
    if not legacy.issubset(identities):
        raise ContractError('Existing watch vector lacks its source event')
    media={str(row['rating_key']) for row in snapshot['media']}
    eligible=[];quarantined=[]
    for event in sorted(events,key=lambda row:int(row['watch_id'])):
        if str(event['rating_key']) in media:
            eligible.append(event)
        else:
            if not legacy_known:
                raise ContractError('Existing-vector coverage must be verified before quarantine')
            if str(event['watch_id']) in legacy:
                raise ContractError('Existing watch vector has unlinked media; explicit recovery required')
            quarantined.append(dict(reason=REASON,input_hash=event_hash(event),event=event))
    coverage=dict(policy=WATCH_SCOPE_VERSION,source_watch_events=len(events),
        eligible_watch_events=len(eligible),quarantined_watch_events=len(quarantined),
        quarantined_media_titles=len({str(q['event']['rating_key']) for q in quarantined}),
        existing_vector_coverage_verified=legacy_known,existing_watch_embeddings=len(legacy),
        existing_watch_embeddings_covered=len(legacy),new_library_linked_events=len(eligible)-len(legacy),
        quarantine_sha256=fingerprint(quarantined))
    return {**snapshot,'events':eligible,'quarantined_events':quarantined,'watch_coverage':coverage}


def coverage_report(snapshot,*,details=False):
    scoped=partition_history(snapshot)
    report=dict(scoped['watch_coverage'])
    if details:
        # A normal report needs identities/hashes, not owners or raw history.
        report['quarantined_events']=[dict(watch_id=q['event']['watch_id'],rating_key=q['event']['rating_key'],
            reason=q['reason'],input_hash=q['input_hash']) for q in scoped['quarantined_events']]
    return report
