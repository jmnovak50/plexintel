"""Associate retained output with recorded stages; no jobs, writes or schema changes."""
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
from threading import Lock

from api.predictive.progress import EVENT
from api.services.pipeline_service import get_pipeline_log_path

WORKERS = {'predictive_daily', 'embeddinggemma2_generation'}
GROUPS = {'score_model': ('score_model', 'shap'),
          'publication': ('publication', 'verification', 'semantic_labels')}
ALIASES = {'user': 'users', 'historical-features': 'training_data',
           'context': 'media_text', 'metadata': 'media_text', 'training': 'train_model',
           'scoring': 'score_model', 'validation': 'publication'}
HEADER = re.compile(r'^\[[^\]]+\] \[run:(\d+)\] \[stage:([^\]]+)\] (stdout:|stderr:|end|command:.*|exit_code:.*)\s*$')
RUN_LINE = re.compile(r'^\[[^\]]+\] \[(?:run:\d+|pipeline-launcher)\] ')
_INDEX_LOCK = Lock()
PAGE_CHARS = 128 * 1024


def redact(text):
    for key, value in os.environ.items():
        if value and re.search(r'(?:^|_)(?:TOKEN|API_KEY|APIKEY|SECRET|PASSWORD)(?:_|$)', key, re.I):
            text = text.replace(value, '[REDACTED]')
    text = re.sub(r'(?i)(apikey|api_key|x-plex-token|password|token)=([^&\s]+)', r'\1=[REDACTED]', text)
    text = re.sub(r'(?i)(authorization\s*:\s*(?:bearer|basic)\s+)\S+', r'\1[REDACTED]', text)
    return re.sub(r'(?i)("(?:token|api_key|password|secret|authorization)"\s*:\s*")(?:\\.|[^"\\])*',
                  r'\1[REDACTED]', text)


def readable_line(line, value=None):
    """Keep every message/event; unknown JSON retains all fields, pretty printed."""
    if value is None:
        try:value = json.loads(line)
        except ValueError:return line
    if not isinstance(value, dict):return line
    if value.get('event') != EVENT:
        return json.dumps(value, ensure_ascii=False, indent=2)
    parts = []
    if value.get('at'):parts.append('[' + str(value['at']) + ']')
    parts.append('[' + str(value.get('stage_key', '')) + ']')
    if value.get('status'):parts.append(str(value['status']))
    if value.get('message'):parts.append(str(value['message']))
    metrics = value.get('metrics')
    if isinstance(metrics, dict):
        parts.extend(f'{key}={json.dumps(number,ensure_ascii=False)}' for key, number in metrics.items())
    elif metrics is not None:parts.append('metrics='+json.dumps(metrics,ensure_ascii=False))
    seconds = value.get('elapsed_seconds')
    if isinstance(seconds, (int,float)) and value.get('timing_known', True):
        if not (value.get('stage_key') == 'shap' and str(value.get('message', '')).startswith('Measured within scoring')):
            parts.append('elapsed_seconds=' + str(round(seconds, 2)))
    rendered = {'event','at','stage_key','status','message','metrics','elapsed_seconds'}
    parts.extend(f'{key}={json.dumps(item,ensure_ascii=False)}' for key,item in value.items() if key not in rendered)
    return '  '.join(parts)


def _diagnostic_lines(value, indent='', path=()):
    """Render recorded fields, not newly evaluated/model-derived measurements."""
    if isinstance(value, dict):
        # End with the recorded validation reports and matrices so the original
        # tail-first log view opens on useful outcomes, rather than vocabularies.
        last = ('evaluation', 'chronological', 'show_heldout', 'confusion_matrix')
        ordered = [key for key in value if key not in last] + [key for key in last if key in value]
        class_fields = {'negative_precision', 'negative_recall', 'negative', 'precision', 'recall', 'positive'}
        matrix = value.get('confusion_matrix')
        class_report = class_fields.issubset(value) and isinstance(matrix, list) and len(matrix) == 2 and all(
            isinstance(row, list) and len(row) == 2 for row in matrix)
        for key in ordered:
            if class_report and key in class_fields:continue
            item = value[key]
            label = str(key).replace('_', ' ')
            if key == 'confusion_matrix' and isinstance(item, list) and len(item) == 2 and all(
                    isinstance(row, list) and len(row) == 2 for row in item):
                if class_report:
                    context = ' [' + ' / '.join(path).replace('_', ' ') + ']' if path else ''
                    yield indent + 'Class report' + context + ' (recorded precision / recall / support):'
                    yield indent + '  class | precision | recall | support'
                    for label, fields in ((0, ('negative_precision','negative_recall','negative')),
                                          (1, ('precision','recall','positive'))):
                        yield indent + f'  {label} | ' + ' | '.join(str(value[field]) for field in fields)
                yield indent + 'Confusion matrix (actual rows / predicted columns; labels 0, 1):'
                yield indent + '                  predicted 0    predicted 1'
                for index, row in enumerate(item):
                    yield indent + f'  actual {index}:      {row[0]!s:>10}     {row[1]!s:>10}'
            elif isinstance(item, (dict, list)):
                yield indent + label + ':'
                yield from _diagnostic_lines(item, indent + '  ', path + (str(key),))
            else:
                yield indent + label + ': ' + (json.dumps(item, ensure_ascii=False) if not isinstance(item, str) else item)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield indent + f'[{index}]:'
            yield from _diagnostic_lines(item, indent + '  ', path + (str(index),))
    else:
        yield indent + (json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value)


def _completion_diagnostics(value, keys):
    """Split this stdout receipt by its explicit field meanings, once per field.

    This is completion evidence, not an event that was emitted during a stage.
    Unknown fields and fields without a recorded destination stay with the worker.
    """
    remainder = dict(value)
    sections = defaultdict(dict)

    def assign(field, stage):
        if field in remainder and stage in keys:
            sections[stage][field] = remainder.pop(field)

    assign('evaluation', 'train_model')
    assign('summary', 'training_data')
    assign('ranking_comparison', 'score_model')
    assign('semantic_labeling', 'semantic_labels')
    for field in ('feature_space_id', 'model_sha256', 'source_sha256', 'software_versions'):
        assign(field, 'train_model')
    for field in ('verified', 'run_id', 'promotion_id'):
        assign(field, 'publication')
    count_stages = dict(media_embeddings='media_text', watch_embeddings='watch',
                        user_embeddings='users', training_data='training_data',
                        recommendations='score_model', shap_impact='shap', shap_prediction_context='shap')
    counts = dict(remainder['counts'])
    for field, stage in count_stages.items():
        if field in counts and stage in keys:
            sections[stage].setdefault('published counts', {})[field] = counts.pop(field)
    if counts:remainder['counts'] = counts
    else:remainder.pop('counts')
    return sections, remainder


def _parse_stream(text, owner, stream, keys, emit):
    active = None
    for raw in text.splitlines(keepends=True):
        line = redact(raw.rstrip('\r\n'))
        try:value = json.loads(line)
        except ValueError:value = None
        # Don't assign an incomplete JSON marker to the preceding stage.
        if not raw.endswith(('\n','\r')) and line.lstrip().startswith('{') and value is None:
            continue
        if (owner == 'predictive_daily' and stream == 'stdout' and isinstance(value, dict)
                and value.get('verified') is True and value.get('run_id')
                and not value.get('stage_key') and not value.get('stage')
                and all(isinstance(value.get(field), dict) for field in ('counts', 'evaluation', 'summary'))):
            sections, remainder = _completion_diagnostics(value, keys)
            for stage, fields in sections.items():
                emit(stage, stream, redact('\n'.join([
                    '\nRecorded completion diagnostics (from this execution’s retained stdout receipt):',
                    *_diagnostic_lines(fields)])))
            if remainder:emit(owner, stream, redact(readable_line('', remainder)))
            continue
        key = owner
        if owner in WORKERS:
            original_key = (value.get('stage_key') or value.get('stage')) if isinstance(value, dict) else None
            explicit = ALIASES.get(original_key, original_key) if isinstance(original_key,str) else None
            if explicit in keys:
                key = explicit
            elif original_key is None and stream == 'stdout' and active:
                key = active
            # stderr is a separate stream: stdout order cannot establish its phase.
            if isinstance(value, dict) and value.get('event') == EVENT and explicit in keys and stream == 'stdout':
                if value.get('status') == 'started':
                    if value.get('timing_active') is not False:active = explicit
                    elif active == explicit:active = None
                elif value.get('status') in ('success','failed','cancelled','skipped','not_recorded') and active == explicit:
                    active = None
        emit(key, stream, redact(readable_line(line, value)))


def _signature(path):
    st = path.stat()
    return (str(path), st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)


@lru_cache(maxsize=4)
def _index_files(run_id, physical, keys, files, combined):
    output = defaultdict(list)
    sources = defaultdict(set)
    present = set()
    def emit(key, stream, line, source):
        targets = [key]
        if set(physical) & WORKERS:
            parent = next((parent for parent,children in GROUPS.items() if key in children),None)
            if parent:
                targets = [parent,'exact:'+key]
        for target in targets:
            output[(target,stream)].append(line)
            sources[(target,stream)].add(source)
    for owner,stream,signature in files:
        path,_,_,size,_ = signature
        try:
            with open(path,'rb') as handle:text = handle.read(size).decode('utf-8',errors='replace')
        except OSError:continue
        present.add((owner,stream))
        _parse_stream(text,owner,stream,keys,lambda key,s,line:emit(key,s,line,'retained stage file'))
    if combined:
        path,_,_,size,_ = combined
        captured = defaultdict(list)
        current = None
        try:
            with open(path,'rb') as handle:
                while handle.tell() < size:
                    raw = handle.readline(size-handle.tell()).decode('utf-8',errors='replace')
                    marker = HEADER.match(raw)
                    if marker:
                        rid,owner,kind = marker.groups()
                        candidate = (owner,kind[:-1])
                        current = candidate if (int(rid)==run_id and owner in physical
                            and kind in ('stdout:','stderr:') and candidate not in present) else None
                        if current:present.add(('combined-'+owner,kind[:-1]))
                    elif RUN_LINE.match(raw):current = None
                    elif current:captured[current].append(raw)
        except OSError:pass
        for (owner,stream),lines in captured.items():
            _parse_stream(''.join(lines),owner,stream,keys,
                          lambda key,s,line:emit(key,s,line,'exact run/stage section in pipeline.log'))
    return ({key:'\n'.join(lines) for key,lines in output.items()},
            {key:', '.join(sorted(values)) for key,values in sources.items()},present)


def _stream_page(text, offset, limit, source, note=None):
    # A shortened/rotated stream must never be spliced onto old output.
    start = offset if offset <= len(text) else 0
    end = min(start+limit,len(text))
    return dict(text=text[start:end],offset=start,next_offset=end if end<len(text) else None,
                total_characters=len(text),source=source,note=note,
                identity=hashlib.sha256(text[:256].encode()).hexdigest())


def get_stage_logs(run, stage_key, *, stdout_offset=0, stderr_offset=0, limit=PAGE_CHARS, log_path=None):
    """Read complete available streams in bounded pages, preserving within-stage order."""
    rows = run.get('stages') or []
    details = run.get('stage_details') or []
    valid = {s['stage_key'] for s in rows+details}
    if stage_key not in valid:raise KeyError(stage_key)
    workers = {s['stage_key'] for s in rows if s['stage_key'] in WORKERS}
    physical = workers or {s['stage_key'] for s in rows}
    keys = tuple(sorted(valid))
    path = Path(log_path) if log_path is not None else get_pipeline_log_path()
    directory = path.parent
    files = []
    ambiguous = False
    for owner in sorted(physical):
        if not re.fullmatch(r'[A-Za-z0-9_-]+',owner):continue
        for stream in ('stdout','stderr'):
            paths = list(directory.glob(f'pipeline-run-{int(run["run_id"])}-{owner}-*.{stream}.log'))
            if len(paths)==1:
                try:files.append((owner,stream,_signature(paths[0])))
                except OSError:pass
            elif len(paths)>1:ambiguous = True
    combined = None
    if len(files)<len(physical)*2:
        try:combined = _signature(path)
        except OSError:pass
    with _INDEX_LOCK:
        output,sources,present = _index_files(run['run_id'],tuple(sorted(physical)),keys,tuple(files),combined)
    lookup = 'exact:'+stage_key if workers and stage_key in ('shap','verification','semantic_labels') else stage_key
    streams = {}
    for stream,offset in [('stdout',stdout_offset),('stderr',stderr_offset)]:
        text = output.get((lookup,stream),'')
        source = sources.get((lookup,stream),'')
        note = None
        if not text:
            values = []
            for key in (GROUPS.get(stage_key,(stage_key,)) if workers and stage_key not in WORKERS else (stage_key,)):
                row = next((r for r in rows if r['stage_key']==key),None)
                if not row:row = next((r for r in details if r['stage_key']==key),None)
                raw = (row or {}).get(stream+'_tail')
                if raw:
                    # Worker tails contain all phases. Never duplicate them if a
                    # retained stream or exact combined section was recovered.
                    recovered = workers and stage_key in WORKERS and any(
                        p[1] == stream and (p[0] in workers or p[0].removeprefix('combined-') in workers) for p in present)
                    if recovered:continue
                    values.append('\n'.join(redact(readable_line(redact(line))) for line in raw.splitlines()))
            if values:
                text='\n'.join(values);source='saved stage record only'
                note='Only the saved stage output remains; the full retained file/section is unavailable.'
        if stage_key in WORKERS:
            note='Worker output without a retained phase key. Untagged stderr cannot be assigned to a logical stage.'
        elif ambiguous:
            note=note or 'Ambiguous retained filenames were not guessed; only exactly associated output is shown.'
        streams[stream] = _stream_page(text, max(0,int(offset)),min(PAGE_CHARS,max(1,int(limit))),source,note)
    return dict(run_id=run['run_id'],stage_key=stage_key,**streams)
