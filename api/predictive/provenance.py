"""Reproducible source/settings evidence, not an approval or activation registry."""
import hashlib
from pathlib import Path
from importlib.metadata import version,PackageNotFoundError

ROOT=Path(__file__).resolve().parents[2]


def source_sha256():
    files=list((ROOT/'api/predictive').glob('*.py'))
    files.extend(ROOT/name for name in ('scripts/predictive_pipeline.py','fetch_tautulli_data.py','api/services/watch_history_sync.py','api/services/app_settings.py'))
    digest=hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path.relative_to(ROOT)).encode()+b'\0'+path.read_bytes()+b'\0')
    return digest.hexdigest()


def versions():
    result={}
    for package in ('numpy','xgboost','scikit-learn','joblib','pgvector','psycopg2-binary'):
        try:result[package]=version(package)
        except PackageNotFoundError:result[package]='unavailable'
    return result
