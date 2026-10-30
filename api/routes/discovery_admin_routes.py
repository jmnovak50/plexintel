"""Session-admin Content Discovery API; operational gates live on the server."""
from datetime import date,datetime,timezone
from typing import Literal
from uuid import UUID
from urllib.parse import urlsplit
from functools import lru_cache
import requests
from fastapi import APIRouter,Depends,HTTPException,Query,Request,Response
from pydantic import BaseModel,Field,ConfigDict
from api.routes.admin_routes import require_admin
from api.services import discovery_workspace as workspace,discovery_workflow as workflow
from api.services.seerr_client import SeerrError

router=APIRouter(prefix='/admin/discovery',dependencies=[Depends(require_admin)])
Media=Literal['movie','tv']

def mutation(request:Request):
    # Existing sessions use SameSite=Lax; additionally enforce browser origin and
    # a custom JSON action header. Never trust a client-supplied role/CSRF flag.
    origin=request.headers.get('origin')
    try:parsed=urlsplit(origin or '')
    except ValueError:raise HTTPException(403,'Invalid action origin') from None
    if not origin or parsed.netloc!=request.url.netloc or parsed.scheme!=request.url.scheme:
        raise HTTPException(403,'Same-origin discovery action required')
    if request.headers.get('x-discovery-action')!='1' or request.headers.get('sec-fetch-site')=='cross-site':
        raise HTTPException(403,'Discovery action header required')

def call(fn,*args,**kwargs):
    try:return fn(*args,**kwargs)
    except workflow.WorkflowError as e:raise HTTPException(e.status,e.code) from None
    except SeerrError as e:raise HTTPException(503,e.code) from None
    except ValueError:raise HTTPException(422,'invalid_discovery_parameters') from None
    except Exception:raise HTTPException(503,'discovery_unavailable') from None

@router.get('/overview')
def overview():return call(workspace.overview)

@router.get('/settings')
def settings():return call(workflow.settings_payload)

class Updates(BaseModel):
    model_config=ConfigDict(extra='forbid')
    updates:dict[str,bool|str|int]=Field(default_factory=dict,max_length=20)

@router.patch('/settings',dependencies=[Depends(mutation)])
def update_settings(body:Updates,user=Depends(require_admin)):
    call(workflow.update_settings,body.updates,user['username']);return call(workflow.settings_payload)

@router.get('/titles')
def titles(page:int=Query(1,ge=1,le=100000),limit:int=Query(25,ge=1,le=100),search:str|None=Query(None,max_length=200),
           media_type:Media|None=None,language:str|None=Query(None,pattern=r'^[a-z]{2,3}$'),
           enrichment_status:Literal['pending','success','failed']|None=None,
           classification:Literal['eligible','provisional','excluded','unknown']|None=None,
           media_state:Literal['unknown','known','requests_unknown','requested','no_requests_observed']|None=None,
           release_from:date|None=None,release_to:date|None=None,
           discovered_from:datetime|None=None,discovered_to:datetime|None=None,
           sort:Literal['title','premiere_date','first_discovered_at','last_observed_at','last_enriched_at','popularity']='first_discovered_at',
           direction:Literal['asc','desc']='desc'):
    if any(x is not None and x.tzinfo is None for x in (discovered_from,discovered_to)):
        raise HTTPException(422,'Discovery timestamp filters require a timezone')
    if release_from and release_to and release_from>release_to:raise HTTPException(422,'Invalid release range')
    if discovered_from and discovered_to and discovered_from>=discovered_to:raise HTTPException(422,'Invalid discovery range')
    return call(workspace.inventory,page=page,limit=limit,search=search,media_type=media_type,language=language,
                enrichment_status=enrichment_status,classification=classification,media_state=media_state,
                release_from=release_from,release_to=release_to,discovered_from=discovered_from,discovered_to=discovered_to,sort=sort,direction=direction)

@router.get('/titles/{media_type}/{ident}')
def title(media_type:Media,ident:int,history_page:int=Query(1,ge=1,le=100000),limit:int=Query(25,ge=1,le=100),diagnostics:bool=False):
    if ident<=0:raise HTTPException(422,'Invalid TMDB identity')
    result=call(workspace.title,media_type,ident,history_page=history_page,limit=limit,diagnostics=diagnostics)
    if result is None:raise HTTPException(404,'Discovery title not found')
    return result

@lru_cache(maxsize=128)
def _image(path):
    # Fixed CDN host + validated TMDB path, no user URL, cookie or API key.
    with requests.get('https://image.tmdb.org/t/p/w185'+path,timeout=8,allow_redirects=False,stream=True) as r:
        kind=r.headers.get('Content-Type','').split(';')[0]
        if r.status_code!=200 or kind not in ('image/jpeg','image/png','image/webp'):return None
        data=bytearray()
        for chunk in r.iter_content(65536):
            data.extend(chunk)
            if len(data)>2*1024*1024:return None
        return bytes(data),kind

@router.get('/titles/{media_type}/{ident}/poster')
def poster(media_type:Media,ident:int):
    path=call(workspace.poster_path,media_type,ident)
    if not path:raise HTTPException(404,'Poster unknown')
    try:payload=_image(path)
    except requests.RequestException:raise HTTPException(502,'Poster unavailable') from None
    if not payload:raise HTTPException(404,'Poster unavailable')
    return Response(payload[0],media_type=payload[1],headers={'Cache-Control':'private, max-age=3600','X-Content-Type-Options':'nosniff'})

@router.get('/runs')
def runs(page:int=Query(1,ge=1,le=100000),limit:int=Query(25,ge=1,le=100),status:Literal['running','success','partial','failed']|None=None):
    return call(workspace.runs,page,limit,status)

@router.get('/runs/{run_id}')
def run(run_id:UUID,page:int=Query(1,ge=1,le=100000),limit:int=Query(25,ge=1,le=100)):
    result=call(workspace.run_detail,run_id,page,limit)
    if result is None:raise HTTPException(404,'Discovery run not found')
    return result

@router.post('/plan',dependencies=[Depends(mutation)])
def plan(body:workflow.Execution):return call(workflow.plan,body)

@router.post('/jobs',status_code=202,dependencies=[Depends(mutation)])
def submit(body:workflow.Execution,user=Depends(require_admin)):return call(workflow.submit,body,user['username'])

@router.get('/jobs')
def jobs(page:int=Query(1,ge=1,le=100000),limit:int=Query(25,ge=1,le=100)):return call(workflow.jobs,page=page,limit=limit)

@router.get('/jobs/{job_id}')
def job(job_id:int):
    result=call(workflow.jobs,job_id=job_id)
    if not result['items']:raise HTTPException(404,'Discovery job not found')
    return result['items'][0]
