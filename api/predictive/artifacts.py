"""Ordinary checksum-addressed model files; public feature config is the pointer."""
import hashlib,io,json,os,tempfile
from pathlib import Path
from .contracts import ContractError,fingerprint
from .recovery import IDENTITY_POLICY


def save_model(directory,bundle):
    import joblib
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    data=io.BytesIO();joblib.dump(bundle,data);raw=data.getvalue()
    digest=hashlib.sha256(raw).hexdigest();path=directory/(digest+'.joblib')
    fd,temp=tempfile.mkstemp(dir=directory,prefix='.model-')
    try:
        with os.fdopen(fd,'wb') as handle:handle.write(raw);handle.flush();os.fsync(handle.fileno())
        os.replace(temp,path)
        descriptor=os.open(directory,os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return str(path.resolve()),digest


def load_model(config):
    import joblib
    from .features import Vocabulary,SUPERVISION_POLICY
    if config.get('architecture')!='public-text-predictor/1.0':raise ContractError('Unsupported model architecture')
    path=Path(config['model_path']);raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=config['model_sha256']:raise ContractError('Model file checksum mismatch')
    bundle=joblib.load(io.BytesIO(raw))  # Trusted local owner-written artifacts only.
    if (bundle.get('source_sha256')!=config.get('source_sha256') or bundle['feature_space_id']!=config['feature_space_id'] or bundle['feature_names']!=config['feature_names']
        or bundle['contract_hash']!=config['contract_hash'] or fingerprint(config['contract'])!=config['contract_hash']
        or bundle['identity_policy']!=IDENTITY_POLICY or bundle['supervision_policy']!=SUPERVISION_POLICY):
        raise ContractError('Model/configuration/policy mismatch')
    vocabulary=Vocabulary(**bundle['vocabulary'])
    if vocabulary.names!=bundle['feature_names']:raise ContractError('Feature map mismatch')
    return bundle,vocabulary


def current_config(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT metadata FROM public.embedding_feature_config WHERE active')
        rows=cur.fetchall()
    if len(rows)>1:raise ContractError('Multiple active model configurations')
    return rows[0][0] if rows else None


def model_config(inputs,bundle,path,digest,evaluation):
    from .features import SUPERVISION_POLICY
    groups=[dict(name='media_text',start=0,width=768),dict(name='user',start=768,width=768)]
    return dict(architecture='public-text-predictor/1.0',config_id=inputs['feature_space_id'][:24],
        feature_space_id=inputs['feature_space_id'],contract=inputs['contract'],contract_hash=inputs['contract_hash'],
        encoder_digest=inputs['contract']['encoder']['digest'],embedding_model='embeddinggemma-2',
        ordering='media_text,user',media_dimensions=768,user_dimensions=768,embedding_dimensions=1536,
        feature_groups=groups,feature_names=bundle['feature_names'],embedding_features=bundle['feature_names'][:1536],
        model_path=path,model_sha256=digest,dataset_hash=bundle['dataset_hash'],evaluation=evaluation,
        identity_policy=IDENTITY_POLICY,supervision_policy=SUPERVISION_POLICY,
        shap_output='raw margin (log-odds)',poster_inference='disabled/1.0')
