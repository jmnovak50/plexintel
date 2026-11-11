"""The original collect -> prepare -> fit -> score -> publish daily job.

No import-time database access, schema creation, generation lookup or fallback.
"""
from datetime import datetime,timezone
import json,math,re,subprocess,sys,time
from pathlib import Path
from pgvector.psycopg2 import register_vector
from api.db.connection import connect_db
from . import source
from .contracts import ContractError,fingerprint
from .encoder import TextEncoder
from .artifacts import current_config,model_config,save_model,load_model
from .prepare import prepare
from .train import train
from .scoring import score
from .publication import writer_lock,source_signature,install_staging,stage_vectors,stage_training,stage_predictions,publish,verify
from .recovery import load_associations
from .progress import Reporter
from .provenance import source_sha256,versions

ROOT=Path(__file__).resolve().parents[2]


def run(conn,directory,*,frozen_source=None,plex=None,encoder=None,allow_stored_history=False,
        incumbent_evaluation=None,collect=True,policy=None,output=lambda event:print(json.dumps(event),flush=True),label=True):
    started=time.monotonic();directory=Path(directory).resolve()
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    reporter=Reporter(output)
    register_vector(conn)
    with writer_lock(conn):
        # Exact incumbent pinned under the execution lock, before any work.
        code_sha=source_sha256();software=versions()
        incumbent=current_config(conn);conn.commit()
        policy=source.settings() if not frozen_source else policy
        incumbent_ap=None
        if incumbent:
            if not re.fullmatch('[a-f0-9]{64}',str(incumbent.get('model_sha256',''))):
                raise ContractError('Exact incumbent model checksum is required before work')
            if incumbent.get('architecture')=='public-text-predictor/1.0':
                load_model(incumbent)
                incumbent_ap=incumbent['evaluation']['chronological']['average_precision']
            else:
                if (not incumbent_evaluation or incumbent_evaluation.get('model_sha256')!=incumbent.get('model_sha256')):
                    raise ContractError('Initial cutover needs an explicit incumbent evaluation bound to its model checksum')
                incumbent_ap=incumbent_evaluation.get('average_precision')
            if not isinstance(incumbent_ap,(float,int)) or not math.isfinite(incumbent_ap) or not 0<=incumbent_ap<=1:
                raise ContractError('Invalid incumbent AP baseline')
        # Check the prepared schema before ingestion; the job never applies migrations.
        with conn.cursor() as cur:
            for table in ('media_embeddings','watch_embeddings','user_embeddings'):
                cur.execute('SELECT provenance FROM public.'+table+' LIMIT 0')
            cur.execute('SELECT diagnostics,sample_weight FROM public.training_data LIMIT 0')
        conn.commit()
        with reporter.span('source_sync'):
            if frozen_source:
                if collect:raise ContractError('Frozen replay cannot collect live inputs')
                snapshot=frozen_source
            else:
                if collect:
                    process=subprocess.run([sys.executable,str(ROOT/'fetch_tautulli_data.py'),'--mode','incremental','--no-embeddings'],
                        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1800)
                    if process.returncode:raise ContractError('Source collection failed; previous predictions preserved')
                config=policy
                # One short repeatable-read source snapshot, not a training-long transaction.
                conn.set_session(isolation_level='REPEATABLE READ',readonly=True)
                snapshot=source.read_snapshot(conn);snapshot['as_of']=datetime.now(timezone.utc).isoformat()
                source_hash=source_signature(conn,snapshot=snapshot)
                associations=load_associations(conn,[str(r['rating_key']) for r in snapshot['media']])
                conn.rollback();conn.set_session(isolation_level='READ COMMITTED',readonly=False)
                source.event_availability(config,snapshot)
                plex=plex or source.plex(config,directory/'plex-cache')
                encoder=encoder or TextEncoder(config['ollama.host'],threads=config['ollama.threads'],timeout=config['ollama.timeout_s'])
            if frozen_source:
                # A replay must describe this isolated database's exact raw sources.
                raw=source.read_snapshot(conn)
                for field in ('media','events','feedback'):
                    supplied=[{k:r.get(k) for k in expected} for r,expected in zip(snapshot[field],raw[field])]
                    if len(snapshot[field])!=len(raw[field]) or supplied!=raw[field]:
                        raise ContractError('Frozen replay differs from isolated source rows')
                source_hash=source_signature(conn,snapshot=raw)
                associations=load_associations(conn,[str(r['rating_key']) for r in snapshot['media']]);conn.commit()
            from .history_scope import partition_history
            snapshot=partition_history(snapshot)
        def progress(stage,**metrics):
            if 'seconds' in metrics:reporter.elapsed[stage]=metrics['seconds']
            reporter.emit(stage,'started',**metrics)
        # Preparation is in memory and temporary tables; live vectors stay unchanged.
        inputs,media,watches,users,rows,summary=prepare(conn,snapshot,plex,encoder,associations,
            allow_stored_history=allow_stored_history,policy=policy,progress=progress)
        conn.commit()
        for stage in ('source_sync','media_text','watch','users','training_data'):reporter.done(stage)
        with reporter.span('train_model'):
            bundle,vocabulary,evaluation=train(inputs,media,watches,rows,summary,incumbent_ap=incumbent_ap,
                progress=lambda **metrics:reporter.emit('train_model','started',**metrics))
        reporter.done('train_model')
        bundle.update(source_sha256=code_sha,software_versions=software)
        model_path,model_hash=save_model(directory,bundle)
        config=model_config(inputs,bundle,model_path,model_hash,evaluation)
        config.update(source_sha256=code_sha,software_versions=software,
                      fit_settings=dict(seed=42,threshold=.5,n_estimators=100,max_depth=6,learning_rate=.1,subsample=.8,n_jobs=2),
                      workload_id=fingerprint([model_hash,source_hash]),source_hash=source_hash,
                      completed_at=snapshot['as_of'],dataset_summary=summary)
        reporter.bind(config['workload_id'])
        install_staging(conn);stage_vectors(conn,media,watches,users);stage_training(conn,rows)
        with reporter.span('score_model'):
            count=stage_predictions(conn,score(inputs,media,watches,users,bundle,vocabulary,policy=policy,
                progress=lambda **metrics:reporter.emit('score_model','started',**metrics)),config,snapshot['as_of'])
        from .diagnostics import ranking_comparison
        ranking=ranking_comparison(conn);conn.commit()
        reporter.done('score_model',predictions=count)
        reporter.done('shap',message='Measured within scoring; raw-margin embedding contributions retained')
        if source_sha256()!=code_sha:raise ContractError('Predictor source changed during execution; no publication')
        with reporter.span('publication'):
            counts=publish(conn,config,incumbent,source_hash,backup_directory=directory)
        reporter.done('publication')
        try:
            with reporter.span('verification'):
                if verify(conn,config)!=counts:raise ContractError('Post-commit population mismatch')
                conn.commit()
        except Exception:
            raise ContractError('Publication committed but final verification is incomplete; run read-only verify, not an automatic workload retry') from None
        reporter.done('verification')
        result=dict(verified=True,run_id=config['workload_id'],promotion_id=config['workload_id'],
            feature_space_id=config['feature_space_id'],model_sha256=model_hash,source_sha256=code_sha,software_versions=config['software_versions'],counts=counts,summary=summary,
            evaluation=evaluation,ranking_comparison=ranking,predictive_seconds=time.monotonic()-started)
        # Normal outputs are aggregate-only. Owner/title training manifests remain in DB.
        if label:
            from api.services.pipeline_labeling import run_after_publication
            result['semantic_labeling']=run_after_publication(result,output=output)
        else:result['semantic_labeling']=dict(status='skipped',reason='Explicitly disabled for this execution')
        # Optional diagnostics/retention cannot reclassify a committed predictor.
        try:
            from .history import prune
            result['history_pruned']=prune(conn);conn.commit()
        except Exception:
            try:conn.rollback()
            except Exception:pass
            result['history_maintenance']='Deferred; predictor remains verified'
        # Keep current and one previous model, plus one ordinary last-good backup.
        keep={model_hash}
        if incumbent and incumbent.get('model_path'):keep.add(incumbent['model_sha256'])
        try:
            for path in directory.glob('*.joblib'):
                if path.stem not in keep:path.unlink()
            (directory/'latest-evaluation.json').write_text(json.dumps(result,indent=2,sort_keys=True))
        except OSError:
            result['artifact_housekeeping']='Publication succeeded; local report/retention maintenance requires attention'
        return result
