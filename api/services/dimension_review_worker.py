"""Durable targeted queue, dispatched outside HTTP using the existing pipeline lock."""
import asyncio
import contextlib
import subprocess
from psycopg2.extras import RealDictCursor
from api.db.connection import connect_db
from api.services.pipeline_service import (
    REPO_ROOT, _python_executable, build_pipeline_environment, try_acquire_pipeline_lock, _append_pipeline_log,
)
from api.services.dimension_governance import LOCK_NAMESPACE

_task = None


def dispatch_review():
    # Do not contend for (or log acquisition of) the pipeline lock when there is no work.
    with contextlib.closing(connect_db()) as conn, conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT 1 FROM embedding_dimension_reviews q
                JOIN embedding_feature_config c USING(config_id)
                LEFT JOIN embedding_dimension_admin a USING(config_id,dimension)
                WHERE c.active AND (q.status='running' OR
                    (q.status='queued' AND NOT COALESCE(a.paused,false))) LIMIT 1""")
            if not cur.fetchone():
                return
    lock = try_acquire_pipeline_lock(source='dimension-review')
    if lock is None:
        return  # Keep queued until the scheduled/CLI/web pipeline releases its lock.
    try:
        with contextlib.closing(connect_db(cursor_factory=RealDictCursor)) as conn, conn:
            with conn.cursor() as cur:
                # A worker restart is not proof that a label assessment failed.
                cur.execute("SELECT * FROM embedding_dimension_reviews WHERE status='running' ORDER BY review_id")
                for stale in cur.fetchall():
                    cur.execute('SELECT pg_try_advisory_lock(%s,%s) AS acquired', (LOCK_NAMESPACE, stale['dimension']))
                    if not cur.fetchone()['acquired']:
                        continue
                    cur.execute('SELECT pg_advisory_unlock(%s,%s)', (LOCK_NAMESPACE, stale['dimension']))
                    cur.execute("""UPDATE embedding_dimension_reviews SET status='interrupted',
                        outcome='Worker interrupted; inspect assessment history before retrying', completed_at=now()
                        WHERE review_id=%s""", (stale['review_id'],))
                cur.execute('''SELECT q.* FROM embedding_dimension_reviews q
                    JOIN embedding_feature_config c USING(config_id)
                    LEFT JOIN embedding_dimension_admin a USING(config_id,dimension)
                    WHERE q.status='queued' AND c.active AND NOT COALESCE(a.paused,false)
                    ORDER BY q.review_id LIMIT 1 FOR UPDATE OF q SKIP LOCKED''')
                job = cur.fetchone()
                if not job:
                    return
                cur.execute("UPDATE embedding_dimension_reviews SET status='running',started_at=now(),error=NULL WHERE review_id=%s", (job['review_id'],))
            conn.commit()
        error = None
        try:
            environment = build_pipeline_environment()
            environment['PLEXINTEL_DIMENSION_REVIEW_ID'] = str(job['review_id'])
            process = subprocess.run([
                _python_executable(), str(REPO_ROOT / 'batch_label_embeddings.py'),
                '--dimension', str(job['dimension']), '--dim_type', 'all',
                '--selection_mode', 'review', '--label', '--save_label',
            ], cwd=REPO_ROOT, env=environment, capture_output=True, text=True, pass_fds=(lock.handle.fileno(),))
            _append_pipeline_log(f"[dimension-review:{job['review_id']}]\n{getattr(process,'stdout','')}\n{getattr(process,'stderr','')}\n")
            if process.returncode:
                # Do not publish raw process output, which can include connection secrets.
                error = f'Labeling process exited with code {process.returncode}; inspect server logs.'
        except Exception as exc:
            error = f'Unable to execute labeling process ({type(exc).__name__}). Check the model host interpreter and scripts.'
        with contextlib.closing(connect_db(cursor_factory=RealDictCursor)) as conn, conn:
            with conn.cursor() as cur:
                cur.execute('''SELECT a.* FROM embedding_dimension_assessments a
                    WHERE a.review_id=%s
                    ORDER BY assessment_id DESC LIMIT 1''', (job['review_id'],))
                assessment = cur.fetchone()
                if assessment:
                    result = assessment['result']
                    status = 'error' if result.get('processing_error') else 'completed'
                    outcome = assessment['outcome']
                elif error:
                    status, outcome = 'error', 'Processing error; current label unchanged unless an assessment was committed'
                else:
                    status, outcome = 'queued', 'Waiting: dimension paused or another assessment is in flight'
                cur.execute('''UPDATE embedding_dimension_reviews SET status=%s,outcome=%s,error=%s,
                    completed_at=CASE WHEN %s='queued' THEN NULL ELSE now() END WHERE review_id=%s''',
                    (status,outcome,error,status,job['review_id']))
    finally:
        lock.release()


async def _loop():
    while True:
        try:
            await asyncio.to_thread(dispatch_review)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f'Dimension review dispatcher error ({type(exc).__name__})')
        await asyncio.sleep(5)


def start_dimension_review_worker():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop(), name='dimension-review-worker')


async def stop_dimension_review_worker():
    global _task
    if _task:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
        _task = None
