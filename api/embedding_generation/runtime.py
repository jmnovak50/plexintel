"""Inactive until optional schema installation; no import-time IO."""
from pathlib import Path
import hashlib
import json
import os
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parents[2]
MARKER=ROOT/'artifacts/embeddinggemma2/installed.json'
TRANSITION=ROOT/'artifacts/embeddinggemma2/transition.json'


def active_generation():
    if not MARKER.is_file():return None
    from api.db.connection import connect_db
    conn=connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT active_generation FROM embedding_v2.control WHERE singleton')
            row=cur.fetchone()
            if not row:raise RuntimeError('Embedding generation control is missing')
            return row[0]
    finally:conn.rollback();conn.close()


def assert_legacy_allowed():
    if TRANSITION.exists():
        raise RuntimeError('Embedding publication is in progress; legacy writers are blocked')
    if active_generation():
        raise RuntimeError('Legacy embedding/model writers are disabled for an active EmbeddingGemma 2 generation; use the generation pipeline')


def legacy_writer_pids():
    names={'fetch_tautulli_data.py','build_user_embeddings.py','build_training_data.py','train_model.py','score_model.py','ollama_embeddings.py','register_dimension_config.py','batch_label_embeddings.py','label_embeddings.py'}
    found=[]
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name)==os.getpid():continue
        try:
            tokens=(entry/'cmdline').read_bytes().split(b'\0')
            if any(Path(t.decode(errors='replace')).name in names for t in tokens if t):found.append(int(entry.name))
        except (FileNotFoundError,PermissionError,ProcessLookupError):continue
    return found


@contextmanager
def publication_barrier():
    TRANSITION.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    try:fd=os.open(TRANSITION,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:raise RuntimeError('Existing transition marker requires operator recovery') from None
    try:
        with os.fdopen(fd,'w') as handle:
            json.dump({'pid':os.getpid(),'code_sha256':code_hash()},handle);handle.flush();os.fsync(handle.fileno())
        if legacy_writer_pids():raise RuntimeError('Legacy writers are running; publication refused')
        yield
    finally:
        TRANSITION.unlink(missing_ok=True)


def code_hash():
    paths=sorted((ROOT/'api/embedding_generation').glob('*.py'))
    paths+=[ROOT/'scripts/embeddinggemma2_migration.py',ROOT/'scripts/register_dimension_config.py',ROOT/'api/services/pipeline_service.py',ROOT/'api/routes/admin_routes.py',ROOT/'run_daily_pipeline.sh',
            *sorted((ROOT/'api/db/migrations/optional/embedding_generation').glob('*.sql')),
            *[ROOT/path for path in ('api/services/dimension_config.py','api/services/dimension_explorer.py',
                'api/services/recommendation_query_service.py','api/routes/dimension_admin_routes.py',
                'frontend/src/pages/AdminDimensions.tsx')],
            *[ROOT/name for name in ('fetch_tautulli_data.py','ollama_embeddings.py','build_user_embeddings.py','build_training_data.py','train_model.py','score_model.py','label_embeddings.py','batch_label_embeddings.py')]]
    digest=hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode())
        # API-only distribution images omit offline CLI/model scripts. They must
        # still import normally, and their receipt must differ from a full host.
        digest.update(path.read_bytes() if path.is_file() else b'ABSENT_SOURCE_FILE')
    return digest.hexdigest()
