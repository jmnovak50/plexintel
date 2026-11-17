"""Associate retained output with recorded stages; no jobs, writes or schema changes."""
from collections import defaultdict
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
from threading import Lock

from api.predictive.progress import EVENT, ITEM_EVENT
from api.services.pipeline_service import get_pipeline_log_path
from api.services.pipeline_log_format import item_line,stage_line,completion_summary,plain_line

WORKERS = {'predictive_daily', 'embeddinggemma2_generation'}
GROUPS = {'source_sync': ('source_sync', 'media_text'),
          'score_model': ('score_model', 'shap'),
          'publication': ('publication', 'verification', 'semantic_labels')}
ALIASES = {'user': 'users', 'historical-features': 'training_data',
           'context': 'media_text', 'metadata': 'media_text', 'training': 'train_model',
           'scoring': 'score_model', 'validation': 'publication'}
HEADER = re.compile(r'^\[[^\]]+\] \[run:(\d+)\] \[stage:([^\]]+)\] (stdout:|stderr:|end|command:.*|exit_code:.*)\s*$')
RUN_LINE = re.compile(r'^\[[^\]]+\] \[(?:run:\d+|pipeline-launcher)\] ')
_INDEX_LOCK = Lock()
PAGE_CHARS = 128 * 1024
SECRET_ENV = re.compile(r'(?:^|_)(?:TOKEN|API_KEY|APIKEY|SECRET|PASSWORD)(?:_|$)',re.I)
QUERY_SECRET = re.compile(r'(apikey|api_key|x-plex-token|password|token)=([^&\s]+)',re.I)
AUTH_SECRET = re.compile(r'(authorization\s*:\s*(?:bearer|basic)\s+)\S+',re.I)
JSON_SECRET = re.compile(r'("(?:token|api_key|password|secret|authorization)"\s*:\s*")(?:\\.|[^"\\])*',re.I)


def _redactor():
    # Snapshot credential values once per parsed stream, rather than scan the
    # process environment twice for every item in a large retained log.
    values = tuple(value for key,value in os.environ.items() if value and SECRET_ENV.search(key))
    def scrub(text):
        for value in values:text = text.replace(value,'[REDACTED]')
        text = QUERY_SECRET.sub(r'\1=[REDACTED]',text)
        text = AUTH_SECRET.sub(r'\1[REDACTED]',text)
        return JSON_SECRET.sub(r'\1[REDACTED]',text)
    return scrub


def redact(text):
    return _redactor()(text)


def readable_line(line, value=None):
    """Classic console presentation; recorded view retains the original fields."""
    if value is None:
        try:value = json.loads(line)
        except ValueError:return line
    if not isinstance(value,dict):return line
    try:
        if value.get('event') == ITEM_EVENT:return item_line(value)
        if value.get('event') == EVENT:return stage_line(value)
    except (TypeError,ValueError,KeyError,AttributeError):
        pass  # Preserve malformed or future records rather than break history.
    return json.dumps(value,ensure_ascii=False,indent=2)


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


def _parse_stream(text, owner, stream, keys, emit, item_stages=None, view="operator"):
    active = None
    scrub = _redactor()
    for raw in text.splitlines(keepends=True):
        line = scrub(raw.rstrip('\r\n'))
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
                summary=completion_summary(stage,fields) if view=='operator' else ''
                if summary:emit(stage,stream,scrub(summary))
                emit(stage, stream, scrub('\n'.join([
                    '\nRecorded completion diagnostics (from this execution’s retained stdout receipt):',
                    *_diagnostic_lines(fields)])), 'completion')
            if remainder:emit(owner, stream, scrub(readable_line('', remainder)))
            continue
        key = owner
        if owner in WORKERS:
            original_key = (value.get('stage_key') or value.get('stage')) if isinstance(value, dict) else None
            explicit = ALIASES.get(original_key, original_key) if isinstance(original_key,str) else None
            if isinstance(value,dict) and value.get('event') == ITEM_EVENT and explicit in keys and item_stages is not None:
                item_stages.add(explicit)
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
        # Normalize JSON escapes before credential scrubbing in the recorded
        # view too; an escaped secret must not bypass redaction.
        formatted=(json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else line) if view=='recorded' else readable_line(line,value)
        if view=='operator' and owner in WORKERS and value is None:formatted=plain_line(line)
        if formatted is not None:
            kind='reuse' if view=='operator' and isinstance(value,dict) and value.get('event')==ITEM_EVENT and value.get('operation')=='reused' else 'main'
            if (view=='operator' and isinstance(value,dict) and value.get('event')==EVENT
                    and value.get('status')=='started' and not value.get('message')
                    and isinstance(value.get('metrics'),dict) and any(value['metrics'].get(k) for k in ('completed','users','predictions'))):
                kind='progress'
            emit(key,stream,scrub(formatted),kind)


def _signature(path):
    st = path.stat()
    return (str(path), st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)


@lru_cache(maxsize=4)
def _index_files(run_id, physical, keys, files, combined, view):
    output = defaultdict(list)
    completion = defaultdict(list)
    reused = defaultdict(list)
    progress = defaultdict(list)
    sources = defaultdict(set)
    present = set()
    item_stages = set()
    def emit(key, stream, line, source, kind="main"):
        targets = [key]
        if set(physical) & WORKERS:
            parent = next((parent for parent,children in GROUPS.items() if key in children),None)
            if parent:
                targets = [parent,'exact:'+key]
        for target in targets:
            destination=completion if kind=='completion' else reused if kind=='reuse' else progress if kind=='progress' else output
            destination[(target,stream)].append(line)
            sources[(target,stream)].add(source)
    for owner,stream,signature in files:
        path,_,_,size,_ = signature
        try:
            with open(path,'rb') as handle:text = handle.read(size).decode('utf-8',errors='replace')
        except OSError:continue
        present.add((owner,stream))
        _parse_stream(text,owner,stream,keys,lambda key,s,line,kind='main':emit(key,s,line,'retained stage file',kind),item_stages,view)
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
                          lambda key,s,line,kind='main':emit(key,s,line,'exact run/stage section in pipeline.log',kind),item_stages,view)
    supplemental=set(completion)|set(reused)|set(progress)
    for key in supplemental:
        if progress[key]:output[key].append('\nRecorded progress details:\n'+'\n'.join(progress[key]))
        if reused[key]:output[key].append('\nRecorded cache reuse details ('+str(len(reused[key]))+(' item' if len(reused[key])==1 else ' items')+'):\n'+'\n'.join(reused[key]))
        output[key].extend(completion[key])
    return ({key:'\n'.join(lines) for key,lines in output.items()},
            {key:', '.join(sorted(values)) for key,values in sources.items()},present,item_stages,supplemental)


def _stream_page(text, offset, limit, source, note=None):
    # A shortened/rotated stream must never be spliced onto old output.
    start = offset if offset <= len(text) else 0
    end = min(start+limit,len(text))
    return dict(text=text[start:end],offset=start,next_offset=end if end<len(text) else None,
                total_characters=len(text),source=source,note=note,
                identity=hashlib.sha256(text[:256].encode()).hexdigest())


def get_stage_logs(run, stage_key, *, stdout_offset=0, stderr_offset=0, limit=PAGE_CHARS, log_path=None, view="operator"):
    """Read complete available streams in bounded pages, preserving within-stage order."""
    if view not in ('operator','recorded'):raise ValueError('Unknown log view')
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
        output,sources,present,item_stages,supplemental = _index_files(run['run_id'],tuple(sorted(physical)),keys,tuple(files),combined,view)
    children = {child for parent,group in GROUPS.items() for child in group if child != parent}
    lookup = 'exact:'+stage_key if workers and stage_key in children else stage_key
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
                    values.append('\n'.join(redact(line) if view=='recorded' else redact(readable_line(redact(line)) or '') for line in raw.splitlines()))
            if values:
                text='\n'.join(values);source='saved stage record only'
                note='Only the saved stage output remains; the full retained file/section is unavailable.'
        if stage_key in WORKERS:
            note='Worker output without a retained phase key. Untagged stderr cannot be assigned to a logical stage.'
        elif ambiguous:
            note=note or 'Ambiguous retained filenames were not guessed; only exactly associated output is shown.'
        if stream == 'stdout' and workers:
            missing = None
            if stage_key in ('source_sync','media_text') and 'media_text' in valid and 'media_text' not in item_stages:
                missing='Per-title embedding decisions were not retained in this execution’s logs; totals cannot identify which titles were embedded or reused.'
            elif stage_key == 'score_model' and 'score_model' not in item_stages:
                missing='Per-user scoring and ranked SHAP log lines were not retained in this execution’s logs; the available completion diagnostics are shown below.'
            if missing:
                if run.get('status') in ('started','cancel_requested'):
                    missing='Item-level output is not available yet. Earlier workers may retain only progress totals.'
                note=' '.join(filter(None,(note,missing)))
        streams[stream] = _stream_page(text, max(0,int(offset)),min(PAGE_CHARS,max(1,int(limit))),source,note)
        streams[stream]['has_supplement'] = (lookup,stream) in supplemental
        streams[stream]['has_item_details'] = bool(set(GROUPS.get(stage_key,(stage_key,))) & item_stages)
    return dict(run_id=run['run_id'],stage_key=stage_key,**streams)
