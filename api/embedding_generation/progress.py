"""Bounded operational events. No embedding/model contract or import-time IO."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
import time
from .contracts import ContractError

EVENT = 'plexintel.pipeline-stage/1'
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
)
STAGE_NAMES = dict(STAGES)
STATUSES = {'pending', 'started', 'success', 'failed', 'cancelled', 'skipped', 'not_recorded'}
METRICS = {'expected', 'completed', 'failed', 'pending', 'succeeded', 'reused', 'inferred',
           'new', 'regenerated', 'rebuilt', 'rows', 'users', 'predictions', 'contexts',
           'contributions', 'limited_history_skips', 'label_policy_skips', 'metadata_seconds',
           'context_seconds', 'inference_seconds', 'checkpoint_reused', 'previous_seconds',
           'chronological_balanced_accuracy', 'chronological_average_precision',
           'show_balanced_accuracy', 'quality_passed', 'new_media', 'new_watch_events',
           'quarantined', 'verified_vectors', 'poster_requests', 'seconds', 'requests'}


def clean_metrics(values):
    if not isinstance(values, dict):return {}
    return {key: value for key, value in values.items() if key in METRICS
            and isinstance(value, (int, float, bool)) and -1e15 <= value <= 1e15 and math.isfinite(value)}


class Reporter:
    """Accumulate disjoint spans (scoring/SHAP interleave) without double timing."""
    def __init__(self, output, *, clock=time.perf_counter):
        self.output, self.clock = output, clock
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

    def emit(self, key, status, *, message=None, **metrics):
        self.metrics.setdefault(key, {}).update(clean_metrics(metrics))
        event = dict(event=EVENT, stage_key=key, status=status,
                     at=datetime.now(timezone.utc).isoformat(),
                     elapsed_seconds=self.elapsed.get(key, 0.) + (self.clock()-self.running[key] if key in self.running else 0.),
                     timing_active=key in self.running, metrics=dict(self.metrics[key]))
        if self.run_id:event['generation_run_id'] = self.run_id
        if message:event['message'] = message[:240]
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
    return dict(row, label=STAGE_NAMES.get(row['stage_key'], row['stage_key']),
                metrics=clean_metrics(event.get('metrics') or {}),
                duration_seconds=event.get('elapsed_seconds'), message=row.get('stderr_tail') if interrupted else event.get('message'),
                timing_active=not interrupted and event.get('timing_active', False), observed_at=event.get('at'),
                detail_source='structured_events')
