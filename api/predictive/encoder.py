"""Digest-pinned local Gemma 2 text inference, with no fallback or model pulls."""
import re
import requests
from .contracts import ContractError,vector
from .io import call


class TextEncoder:
    def __init__(self,host,*,threads=2,timeout=300,session=None):
        self.host=host.rstrip('/');self.session=session or requests.Session()
        self.timeout=timeout;self.threads=int(threads)
        if self.threads<1:raise ContractError('Positive worker thread allocation required')
        models=call(self.session,'GET',self.host+'/api/tags').json()['models']
        found=[m for m in models if m['name']=='embeddinggemma-2:latest']
        if len(found)!=1:raise ContractError('Installed EmbeddingGemma 2 required; no pulls or fallback')
        digest=found[0]['digest'].removeprefix('sha256:')
        if not re.fullmatch('[a-f0-9]{64}',digest):raise ContractError('Invalid installed model digest')
        self.reference='sha256:'+digest
        info=call(self.session,'POST',self.host+'/api/show',json={'model':self.reference}).json()
        if 'embedding' not in info.get('capabilities',[]):raise ContractError('Encoder lacks embedding capability')
        self.identity=dict(name='embeddinggemma-2:latest',digest=digest,dimensions=768,
            normalization='ollama-l2-unit/1.0',num_ctx=8192,num_batch=2048)

    def embed(self,text):
        if not isinstance(text,str) or not text:raise ContractError('Nonempty text required')
        response=call(self.session,'POST',self.host+'/api/embed',attempts=1,timeout=(5,self.timeout),
            json=dict(model=self.reference,input={'text':text},dimensions=768,truncate=False,keep_alive='15m',
                options=dict(num_ctx=8192,num_batch=2048,num_thread=self.threads)))
        payload=response.json()
        if payload.get('model')!=self.reference or len(payload.get('embeddings',[]))!=1:
            raise ContractError('Inference response identity/count mismatch')
        return vector(payload['embeddings'][0],unit=True)
