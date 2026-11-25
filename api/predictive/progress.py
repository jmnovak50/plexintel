"""Bounded operational events. No embedding/model contract or import-time IO."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
import time
from .contracts import ContractError

EVENT = 'plexintel.pipeline-stage/1'
ITEM_EVENT = 'plexintel.pipeline-log/1'


def media_log_fields(key, source):
    """Identify the actual item without logging its synopsis, vector or sessions."""
    metadata = source.get('metadata') or source
    show = metadata.get('show_context') or {}
    return {key: value for key, value in dict(rating_key=str(key),title=metadata.get('title'),
        media_type=metadata.get('media_type'),show_title=show.get('title') or source.get('show_title'),
        season=metadata.get('season_number'),episode=metadata.get('episode_number')).items() if value is not None}

STAGES = (
    ('source_sync', 'Tautulli / library synchronization'),
    ('media_text', 'Media-text embedding refresh'),
    ('watch', 'Watch embedding refresh'),
    ('users', 'User-profile reconstruction'),
    ('training_data', 'Training data preparation'),
    ('train_model', 'Model training and quality validation'),
    ('score_model', 'Recommendation scoring'),
    ('shap', 'SHAP explanation generation'),
    ('publication', 'Production publication'),
    ('verification', 'Final verification'),
    ('semantic_labels', 'Semantic dimension labeling'),
)
STAGE_NAMES = dict(STAGES)
STATUSES = {'pending', 'started', 'success', 'failed', 'cancelled', 'skipped', 'not_recorded'}
METRICS = {'expected', 'completed', 'failed', 'pending', 'succeeded', 'reused', 'inferred',
           'new', 'regenerated', 'rebuilt', 'rows', 'users', 'predictions', 'contexts',
           'contributions', 'limited_history_skips', 'label_policy_skips', 'metadata_seconds',
           'context_seconds', 'inference_seconds', 'checkpoint_reused', 'previous_seconds',
           'chronological_balanced_accuracy', 'chronological_average_precision',
           'show_balanced_accuracy', 'quality_passed', 'quality_warning_count', 'new_media', 'new_watch_events',
           'quarantined', 'verified_vectors', 'poster_requests', 'seconds', 'requests'}
METRICS.update({'successes','abstentions','input_tokens','output_tokens','total_tokens','estimated_cost_usd'})
METRICS.update({'selected','assessed','reviews','failures','skipped','unprocessed',
                'cumulative_requests','cumulative_cost_usd','budget_usd','request_limit'})
METRICS.update({'cached_input_tokens','cumulative_input_tokens','cumulative_output_tokens','cumulative_total_tokens'})


def labeling_status(value):
    if value in ('success','completed','empty'):return 'success'
    if value in ('skipped','budget_stopped'):return 'skipped'
    if value == 'cancelled':return 'cancelled'
    return 'failed'


def labeling_metrics(value):
    """Project only recorded counters; absent historical counts stay unknown."""
    result=clean_metrics(value)
    result.pop('seconds',None)  # Stage spans, not batch counters, own the clock.
    usage=value.get('usage') or value.get('tokens') or {}
    result.update(clean_metrics(usage))
    cumulative=value.get('cumulative_usage') or {}
    for source,target in [('requests','cumulative_requests'),('estimated_cost_usd','cumulative_cost_usd'),
            ('input_tokens','cumulative_input_tokens'),('output_tokens','cumulative_output_tokens'),('total_tokens','cumulative_total_tokens')]:
        if source in cumulative:result[target]=cumulative[source]
    for key in ('budget_usd','request_limit'):
        if key in value.get('limits',{}):result[key]=value['limits'][key]
    if 'assessed' in result:result['completed']=result['assessed']
    if 'selected' in result:result['expected']=result['selected']
    elif isinstance(value.get('total'),int):result['expected']=value['total']
    return clean_metrics(result)


def clean_metrics(values):
    if not isinstance(values, dict):return {}
    return {key: value for key, value in values.items() if key in METRICS
            and isinstance(value, (int, float, bool)) and -1e15 <= value <= 1e15 and math.isfinite(value)}


class Reporter:
    """Accumulate disjoint spans (scoring/SHAP interleave) without double timing."""
    def __init__(self, output, *, clock=time.perf_counter, log_titles=True):
        self.output, self.clock = output, clock
        self.log_titles = log_titles
        self.run_id = None
        self.active = None
        self.elapsed = {}
        self.metrics = {}
        self.last_update = 0.
        self.details = {}
        self.running = {}
        self.work_counts = {}

    def bind(self, run_id):
        self.run_id = run_id

    def log(self, stage_key, operation, **fields):
        """Keep item diagnostics in stdout, separate from throttled stage state.

        EventReader deliberately ignores this event type: per-item messages must
        not replace the stage's status/progress record or create database rows.
        """
        if not self.log_titles:
            fields = {key:value for key,value in fields.items() if key not in ('title','show_title')}
        self.output(dict(event=ITEM_EVENT,stage_key=stage_key,operation=operation,
                         at=datetime.now(timezone.utc).isoformat(),**fields))

    def emit(self, key, status, *, message=None, timing_known=True, **metrics):
        self.metrics.setdefault(key, {}).update(clean_metrics(metrics))
        event = dict(event=EVENT, stage_key=key, status=status,
                     at=datetime.now(timezone.utc).isoformat(),
                     elapsed_seconds=self.elapsed.get(key, 0.) + (self.clock()-self.running[key] if key in self.running else 0.),
                     timing_active=key in self.running, timing_known=timing_known, metrics=dict(self.metrics[key]))
        if self.run_id:event['generation_run_id'] = self.run_id
        if message:event['message'] = message[:240]
        # The labeling stream owns live operator messages and the final summary.
        # Subsequent stage-state snapshots update cards without re-announcing
        # the stage or copying those messages into stdout a second time.
        if key=='semantic_labels' and key in self.details:event['log_output']=False
        self.details[key] = dict(event)
        self.output(event)

    @contextmanager
    def span(self, key, **metrics):
        previous = self.active
        self.active = key
        start = self.clock()
        self.running[key] = start
        self.emit(key, 'started', **metrics)
        try:
            yield
        except BaseException as exc:
            self.elapsed[key] = self.elapsed.get(key, 0.) + self.clock() - start
            self.running.pop(key, None)
            message = type(exc).__name__ + (': '+str(exc)[:200] if isinstance(exc, ContractError) else '')
            self.emit(key, 'failed', message=message)
            raise
        finally:
            self.active = previous
        self.elapsed[key] = self.elapsed.get(key, 0.) + self.clock() - start
        self.running.pop(key, None)
        # Success is explicit: an interleaved span is only a measured part of a stage.
        self.emit(key, 'started')

    def done(self, key, **metrics):
        status = 'skipped' if key in ('watch', 'users') and self.metrics.get(key, {}).get('checkpoint_reused') else 'success'
        self.emit(key, status, **metrics)

    def progress(self, key, *, phase=None, **metrics):
        """Adapt existing callbacks without changing work or flooding the monitor."""
        first = key not in self.details
        self.metrics.setdefault(key, {}).update(clean_metrics(metrics))
        if 'seconds' in metrics:
            self.elapsed[key] = metrics['seconds']
            self.running.pop(key, None)
            self.done(key)
            return
        if first:
            self.running.setdefault(key, self.clock())
        if first or phase or self.clock() - self.last_update >= 1.:
            self.last_update = self.clock()
            message = phase if isinstance(phase, str) and phase.startswith(
                ('boosting round ', 'candidate batch ', 'candidate labels/', 'canonical eligibility')) else None
            self.emit(key, 'started', message=message)

    def skip(self, key, **metrics):
        self.emit(key, 'skipped', checkpoint_reused=True, **metrics)

    def __call__(self, value):
        self.output(value)  # Retain existing complete CLI logs.
        key = value.get('stage')
        values = clean_metrics(value)
        if key in ('media_text', 'watch', 'user'):
            counter = self.work_counts.setdefault(key, dict(completed=0, failed=0, reused=0, inferred=0))
            counter['completed'] += 1
            counter['failed'] += bool(value.get('error'))
            counter['reused'] += bool(value.get('reused'))
            counter['inferred'] += not value.get('error') and not value.get('reused')
            values = counter
        if self.active and self.clock() - self.last_update >= 1.:
            self.last_update = self.clock()
            phase = value.get('phase') or ''
            message = phase if phase.startswith(('boosting round ', 'candidate batch ', 'candidate labels/')) else None
            self.emit(self.active, 'started', message=message, **values)


class EventReader:
    """pread never moves the file offset shared with the writing subprocess."""
    def __init__(self, handle):
        self.handle, self.offset, self.buffer = handle, 0, b''
        self.discard = False

    def read(self):
        events = []
        # Bound work per poll; subsequent polls/drain consume any remaining bytes.
        chunk = os.pread(self.handle.fileno(), 256 * 1024, self.offset)
        self.offset += len(chunk)
        for part in chunk.splitlines(keepends=True):
            ends = part.endswith(b'\n')
            if not self.discard:
                self.buffer += part
                if len(self.buffer) > 16 * 1024:
                    self.buffer = b'';self.discard = True
            if ends:
                if not self.discard:
                    try:
                        event = json.loads(self.buffer)
                        if (isinstance(event, dict) and event.get('event') == EVENT
                            and event.get('stage_key') in STAGE_NAMES and event.get('status') in STATUSES):
                            events.append(event)
                    except (ValueError, UnicodeError):pass
                self.buffer = b'';self.discard = False
        return events, bool(chunk)


def event_details(row):
    """Interpret only our tagged payload; ordinary historical stdout stays raw."""
    try:event = json.loads(row.get('stdout_tail') or '')
    except (ValueError, TypeError):return dict(row)
    if not isinstance(event, dict) or event.get('event') != EVENT:return dict(row)
    interrupted = row.get('status') in {'failed','cancelled','skipped'} and event.get('status') == 'started'
    # Older restored runs timed SHAP within scoring, but emitted a misleading zero.
    known = event.get('timing_known', True) and not (
        row['stage_key'] == 'shap' and str(event.get('message', '')).startswith('Measured within scoring'))
    return dict(row, label=STAGE_NAMES.get(row['stage_key'], row['stage_key']),
                metrics=clean_metrics(event.get('metrics') or {}),
                duration_seconds=event.get('elapsed_seconds') if known else None, timing_known=known,
                message=row.get('stderr_tail') if interrupted else event.get('message'),
                timing_active=not interrupted and event.get('timing_active', False), observed_at=event.get('at'),
                detail_source='structured_events')
