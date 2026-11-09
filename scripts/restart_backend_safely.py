"""Guard the existing service restart with the pipeline lock; never run a job."""
import argparse
from contextlib import closing
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from api.db.connection import connect_db
from api.services.pipeline_service import try_acquire_pipeline_lock, _process_exists


def active_workers():
    with closing(connect_db()) as conn:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute("""SELECT current_pid FROM pipeline_runs WHERE status IN ('started','cancel_requested')
                AND current_pid IS NOT NULL AND delivery_type NOT LIKE 'content_discovery_%'""")
            return [row[0] for row in cur.fetchall() if _process_exists(row[0])]


def guarded_restart(*, check_only=False):
    lock = try_acquire_pipeline_lock(source='guarded-backend-deployment')
    if lock is None:
        raise RuntimeError('Backend restart refused: a pipeline or labeling job holds the shared execution lock')
    try:
        if active_workers():
            raise RuntimeError('Backend restart refused: a registered pipeline worker is still alive')
        if not check_only:
            subprocess.run(['sudo','-n','systemctl','restart','plexintel-backend.service'],check=True)
        print('Backend restart safety check passed' if check_only else 'Backend restarted with the shared pipeline lock held')
    finally:
        lock.release()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    flags = parser.add_mutually_exclusive_group(required=True)
    flags.add_argument('--check-only',action='store_true')
    flags.add_argument('--restart',action='store_true')
    args = parser.parse_args()
    try:
        guarded_restart(check_only=args.check_only)
    except RuntimeError as exc:
        parser.exit(1,str(exc)+'\n')
