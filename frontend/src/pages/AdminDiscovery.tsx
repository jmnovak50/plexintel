import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../components/AppShell';
import { DiscoveryState } from '../components/DiscoveryState';
import { displayValue as val, coverageLabel } from '../lib/discoveryFormatting';

type Values = Record<string, unknown>;
interface Page<T> {items:T[];total:number;page:number;limit:number}
interface Title {media_type:string;tmdb_id:number;title:string;original_title?:string;original_language:string|null;
  premiere_date:string|null;first_discovered_at:string;last_observed_at:string;last_enriched_at:string|null;
  enrichment_status:string;media_status:number|null;media_status_4k:number|null;media_state:Values;
  classification:{state:string;reason:string}|null;poster_url:string;synopsis?:string;genres?:Values[];
  runtime?:number|null;cast_members?:Values[];crew_members?:Values[];release_events?:Values[]|null;
  field_states?:Values;tv_metadata?:Values;first_discovery_run_id?:string;metadata_source_key?:string;
  history?:Page<Membership>}
interface Membership {run_id?:string;media_type?:string;tmdb_id?:number;title?:string;observed_at?:string;
  enrichment_outcome:string;enrichment_error?:string;is_new?:boolean;scope_name:string;eligibility?:Values;changed_fields?:string[]}
interface Run {run_id:string;status:string;operation:string;started_at:string;completed_at:string|null;duration_seconds:number;
  discovery_complete:boolean;enrichment_complete:boolean;parameters:Values;counts:Record<string,number>;
  errors:Values[];warnings:string[];pagination?:Values[];memberships?:Page<Membership>}
interface Job {job_id:number;status:string;stale:boolean;details:{progress?:Values;result?:Values;error?:string;discovery_run_id?:string}}
interface Settings {provider:string;effective:Values;editable_schedule:Record<string,string|boolean|number>;
  capabilities:{preview:boolean;persistence:boolean;scheduling:boolean};next_executions:Values;precedence:string;controls_read_only:string[]}
interface Overview {inventory:Record<string,number>;tv_classification:Record<string,number>;latest_run:Run|null;
  last_complete_discovery:Run|null;running_run:Run|null;last_diagnostic:Run|null;observations:number;runs:number;active_job:{job_id:number;status:string}|null}
interface Me {username:string;display_name?:string;is_admin:boolean}
const base='/api/admin/discovery';
async function api<T>(path:string,body?:unknown,method='POST'):Promise<T> {
  const response=await fetch(base+path,{credentials:'include',...(body===undefined?{}:{method,
    headers:{'Content-Type':'application/json','X-Discovery-Action':'1'},body:JSON.stringify(body)})});
  const data=await response.json();
  if (!response.ok) throw new Error(typeof data.detail==='string'?data.detail:`Discovery request failed (${response.status})`);
  return data as T;
}
function stamp(value:string|null|undefined) {return value?new Date(value).toLocaleString():'Unknown';}
function Badge({status}:{status:string}) {
  const style=status==='success'||status==='eligible'?'recs-status-emerald':status==='failed'?'recs-status-red':status==='partial'||status==='provisional'?'recs-status-orange':'recs-status-slate';
  return <span className={`${style} rounded px-2 py-1 text-xs`}>{status}</span>;
}
function Fields({data}:{data:Values}) {return <dl className="grid gap-3 sm:grid-cols-2">{Object.entries(data).map(([key,value])=><div key={key} className="min-w-0"><dt className="text-xs text-slate-500">{key.replace(/_/g,' ')}</dt><dd className="break-words text-sm">{val(value)}</dd></div>)}</dl>;}
function Paging({page,total,limit=25,onChange}:{page:number;total:number;limit?:number;onChange:(page:number)=>void}) {
  return <div className="flex items-center justify-between gap-3 py-3 text-sm"><span>{total} records · Page {page}</span><div className="flex gap-2"><button className="recs-btn-secondary" disabled={page<=1} onClick={()=>onChange(page-1)}>Previous</button><button className="recs-btn-secondary" disabled={page*limit>=total} onClick={()=>onChange(page+1)}>Next</button></div></div>;
}
function RunSummary({run}:{run:Run|null}) {return run?<div className="space-y-3"><Badge status={run.status}/><p>{coverageLabel(run.status,run.discovery_complete,run.enrichment_complete)}</p><Fields data={{run_id:run.run_id,started:stamp(run.started_at),completed:stamp(run.completed_at),duration_seconds:run.duration_seconds,...run.counts}}/><details><summary>Query scope</summary><Fields data={run.parameters}/></details></div>:<p>No recorded run.</p>;}

export default function AdminDiscovery() {
  const navigate=useNavigate();const [me,setMe]=useState<Me|null>(null);const [authError,setAuthError]=useState<string|null>(null);
  const [reload,setReload]=useState(0);const [tab,setTab]=useState('Overview');const [overview,setOverview]=useState<Overview|null>(null);const [settings,setSettings]=useState<Settings|null>(null);
  const [items,setItems]=useState<Page<Title>|null>(null);const [runs,setRuns]=useState<Page<Run>|null>(null);const [jobs,setJobs]=useState<Page<Job>|null>(null);
  const [page,setPage]=useState(1);const [runPage,setRunPage]=useState(1);const [jobPage,setJobPage]=useState(1);const [loading,setLoading]=useState(true);
  const [error,setError]=useState<string|null>(null);const [notice,setNotice]=useState<string|null>(null);const [busy,setBusy]=useState(false);
  const [filters,setFilters]=useState<Record<string,string>>({sort:'first_discovered_at',direction:'desc'});
  const [selected,setSelected]=useState<Title|null>(null);const [selectedRun,setSelectedRun]=useState<Run|null>(null);
  const [form,setForm]=useState({media:'movie,tv',start:'',end:'',languages:'all',max_pages:50,max_requests:1000,persist:false});
  const [requestId,setRequestId]=useState(()=>crypto.randomUUID());const [plan,setPlan]=useState<Values|null>(null);
  const [schedule,setSchedule]=useState<Record<string,string|number|boolean>>({});
  useEffect(()=>{let active=true;fetch('/api/admin/me',{credentials:'include'}).then(async r=>{
    if (!r.ok) {navigate('/',{replace:true});return;} const user=await r.json() as Me;
    if (!user.is_admin){navigate('/recs',{replace:true});return;}if(active)setMe(user);
  }).catch(()=>{if(active)setAuthError('Unable to verify administrator identity.');});return()=>{active=false;};},[navigate]);
  const refresh=useCallback(async()=>{
    const [o,c,j]=await Promise.all([api<Overview>('/overview'),api<Settings>('/settings'),api<Page<Job>>(`/jobs?page=${jobPage}`)]);
    setOverview(o);setSettings(c);setJobs(j);setSchedule(old=>Object.keys(old).length?old:c.editable_schedule);
  },[jobPage]);
  useEffect(()=>{if(!me)return;let active=true;setLoading(true);setError(null);
    refresh().catch(e=>{if(active)setError(String(e.message));}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};},[me,refresh,reload]);
  useEffect(()=>{if(!me||tab!=='Discovered Titles')return;const controller=new AbortController();let active=true;
    setLoading(true);setItems(null);setError(null);const q=new URLSearchParams({page:String(page),limit:'25',...Object.fromEntries(Object.entries(filters).filter(([,v])=>v))});
    const timer=window.setTimeout(()=>{api<Page<Title>>('/titles?'+q).then(v=>{if(active)setItems(v);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});},250);
    return()=>{active=false;controller.abort();clearTimeout(timer);};},[me,tab,page,filters,reload]);
  useEffect(()=>{if(!me||tab!=='Execution History')return;let active=true;setLoading(true);setRuns(null);setError(null);
    api<Page<Run>>(`/runs?page=${runPage}`).then(v=>{if(active)setRuns(v);}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[me,tab,runPage,reload]);
  const running=!!overview?.active_job||!!jobs?.items.some(j=>j.status==='started');
  useEffect(()=>{if(!me||!running)return;const timer=window.setInterval(()=>{void refresh().catch(e=>setError(e.message));},5000);return()=>clearInterval(timer);},[me,running,refresh]);
  function filter(key:string,value:string){setFilters(old=>({...old,[key]:value}));setPage(1);}
  async function openTitle(t:Title,historyPage=1){setBusy(true);setError(null);try{setSelected(await api<Title>(`/titles/${t.media_type}/${t.tmdb_id}?history_page=${historyPage}`));requestAnimationFrame(()=>document.getElementById('discovery-title-detail')?.focus());}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function openRun(id:string,p=1){setBusy(true);setError(null);try{setSelectedRun(await api<Run>(`/runs/${id}?page=${p}`));requestAnimationFrame(()=>document.getElementById('discovery-run-detail')?.focus());}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  function request(){return {request_id:requestId,media_types:form.media.split(','),start:form.start,end:form.end,languages:form.languages.split(',').map(s=>s.trim()),max_pages:form.max_pages,max_requests:form.max_requests,persist:form.persist,confirmed:false};}
  async function previewPlan(){setBusy(true);setError(null);try{setPlan(await api<Values>('/plan',request()));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function execute(){if(form.persist&&!window.confirm(`Persist ${form.media} discovery for ${form.start} through ${form.end}, languages ${form.languages}, at most ${form.max_requests} HTTP attempts and ${form.max_pages} pages per scope?`))return;
    setBusy(true);setError(null);try{const result=await api<{job_id:number;duplicate:boolean}>('/jobs',{...request(),confirmed:form.persist});setNotice(`Job ${result.job_id} ${result.duplicate?'already recorded':'submitted'}. No automatic resubmission.`);await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function save(){setBusy(true);setError(null);try{const c=await api<Settings>('/settings',{updates:schedule},'PATCH');setSettings(c);setNotice('Scheduling intent saved. Server gates still apply.');}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  const canRun=!!settings&&(form.persist?settings.capabilities.persistence:settings.capabilities.preview);
  const panels=['Overview','Discovered Titles','Execution History','Settings & Scheduling'];
  return <AppShell title="Content Discovery" eyebrow="Administration" signedInAs={me?.display_name||me?.username} description="Seerr release-window inventory and metadata. Discovery classification does not authorize acquisition.">
    <DiscoveryState loading={!me&&!authError} error={authError}><>
      <div className="mb-5 flex flex-wrap gap-2" role="tablist" aria-label="Content discovery sections">{panels.map(p=><button key={p} role="tab" aria-selected={tab===p} className={tab===p?'recs-view-pill-active':'recs-view-pill-inactive'} onClick={()=>{setTab(p);setError(null);}}>{p}</button>)}</div>
      {notice&&<p role="status" className="mb-4 recs-panel p-3">{notice}</p>}
      {error&&<div role="alert" className="mb-4 recs-panel p-3 text-red-700">{error} <button className="recs-btn-secondary" onClick={()=>{setError(null);setReload(n=>n+1);}}>Retry read</button></div>}
      <DiscoveryState loading={loading}>
        {tab==='Overview'&&overview&&<div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Object.entries({...overview.inventory,observations:overview.observations,runs:overview.runs}).map(([k,v])=><div key={k} className="recs-panel p-4"><p className="text-sm text-slate-500">{k.replace(/_/g,' ')}</p><p className="text-2xl font-semibold">{v.toLocaleString()}</p></div>)}</div>
          <p className="text-sm text-slate-500">First discovered counts use rolling UTC 24-hour/seven-day windows. Refresh due follows the instance TTL, source binding and failed-attempt cooldown. TV classification uses the latest release-discovery observation, excluding refresh-only membership.</p>
          <section className="recs-panel space-y-3 p-5"><h2 className="text-lg font-semibold">Operational status</h2><Fields data={{provider:settings?.provider,discovery_enabled:settings?.effective.enabled,manual_preview_available:settings?.capabilities.preview,manual_persistence_available:settings?.capabilities.persistence,scheduler_available:settings?.capabilities.scheduling,next_executions:settings?.next_executions,TV_classifications:overview.tv_classification,running_canonical_run:overview.running_run?.run_id??null,running_workspace_job:overview.active_job?.job_id??null}}/>{jobs?.items.filter(j=>j.status==='started').map(j=><div key={j.job_id}><Badge status={j.status}/><p>Job {j.job_id}{j.stale?' — heartbeat stale; operator review required':''}</p><Fields data={j.details.progress||{}}/></div>)}</section>
          <div className="grid gap-5 lg:grid-cols-2"><section className="recs-panel p-5"><h2 className="mb-3 text-lg font-semibold">Most recent run</h2><RunSummary run={overview.latest_run}/></section><section className="recs-panel p-5"><h2 className="mb-3 text-lg font-semibold">Last complete discovery</h2><RunSummary run={overview.last_complete_discovery}/><p className="mt-3 text-sm">Completeness applies to that run’s listed scopes, not the entire catalog.</p></section></div>
          <section className="recs-panel p-5"><h2 className="mb-3 text-lg font-semibold">Latest warning or error</h2>{overview.last_diagnostic?<Fields data={{run_id:overview.last_diagnostic.run_id,errors:overview.last_diagnostic.errors,warnings:overview.last_diagnostic.warnings}}/>:<p>No recorded diagnostics.</p>}</section>
        </div>}
        {tab==='Discovered Titles'&&<section className="recs-panel p-4"><div className="mb-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <label>Search<input className="recs-input w-full" value={filters.search||''} onChange={e=>filter('search',e.target.value)}/></label>
          {([['media_type','Media type',['movie','tv']],['enrichment_status','Enrichment',['pending','success','failed']],['classification','TV classification',['eligible','provisional','excluded','unknown']],['media_state','Known state',['unknown','known','requests_unknown','requested','no_requests_observed']],['sort','Sort',['first_discovered_at','title','premiere_date','last_observed_at','last_enriched_at','popularity']],['direction','Direction',['asc','desc']]] as [string,string,string[]][]).map(([k,label,opts])=><label key={k}>{label}<select className="recs-input w-full" value={filters[k]||''} onChange={e=>filter(k,e.target.value)}><option value="">All</option>{opts.map(o=><option key={o}>{o}</option>)}</select></label>)}
          <label>Language code<input className="recs-input w-full" value={filters.language||''} onChange={e=>filter('language',e.target.value)}/></label>
          {(['release_from','release_to'] as const).map(k=><label key={k}>{k.replace(/_/g,' ')}<input type="date" className="recs-input w-full" onChange={e=>filter(k,e.target.value)}/></label>)}
          {(['discovered_from','discovered_to'] as const).map(k=><label key={k}>{k==='discovered_to'?'First discovered before (exclusive)':'First discovered since'}<input type="datetime-local" className="recs-input w-full" onChange={e=>filter(k,e.target.value?new Date(e.target.value).toISOString():'')}/></label>)}
        </div><DiscoveryState empty={items?.total===0}><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{['Title','Type / language','Premiere','First discovered','Last observed','Last enriched','Metadata','TV classification','Known state'].map(h=><th className="p-2" key={h}>{h}</th>)}</tr></thead><tbody>{items?.items.map(t=><tr key={`${t.media_type}:${t.tmdb_id}`} className="border-t border-slate-200"><td className="p-2"><button className="flex items-center gap-3 text-left underline" disabled={busy} onClick={()=>void openTitle(t)}><img className="h-16 w-11 rounded object-cover" loading="lazy" src={t.poster_url} alt="" onError={e=>{e.currentTarget.style.visibility='hidden';}}/>{t.title||'Unknown title'}</button></td><td className="p-2">{t.media_type} / {val(t.original_language)}</td><td className="p-2">{val(t.premiere_date)}</td><td className="p-2">{stamp(t.first_discovered_at)}</td><td className="p-2">{stamp(t.last_observed_at)}</td><td className="p-2">{stamp(t.last_enriched_at)}</td><td className="p-2"><Badge status={t.enrichment_status}/></td><td className="p-2">{t.media_type==='tv'?val(t.classification?.state):'Not applicable'}</td><td className="p-2">Media: {val(t.media_status)} · requests: {val(t.media_state?.request_count)}</td></tr>)}</tbody></table></div></DiscoveryState>{items&&<Paging page={page} total={items.total} onChange={setPage}/>}</section>}
        {tab==='Execution History'&&<div className="space-y-5"><section className="recs-panel p-4"><h2 className="mb-3 text-lg font-semibold">Canonical discovery runs</h2><DiscoveryState empty={runs?.total===0}><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{['Run','Started / duration','Status','Coverage','New / known','Fetch / cache / failed / deferred','HTTP / retries'].map(h=><th className="p-2" key={h}>{h}</th>)}</tr></thead><tbody>{runs?.items.map(r=><tr key={r.run_id} className="border-t border-slate-200"><td className="p-2"><button className="underline" onClick={()=>void openRun(r.run_id)}>{r.run_id.slice(0,8)} · {r.operation}</button></td><td className="p-2">{stamp(r.started_at)} / {Math.round(r.duration_seconds)}s</td><td className="p-2"><Badge status={r.status}/></td><td className="p-2">{coverageLabel(r.status,r.discovery_complete,r.enrichment_complete)}</td><td className="p-2">{r.counts.new_titles} / {r.counts.existing_titles}</td><td className="p-2">{['enrichment_success','enrichment_cached','enrichment_failed','enrichment_deferred'].map(k=>r.counts[k]??'Unknown').join(' / ')}</td><td className="p-2">{val(r.counts.http_requests)} / {val(r.counts.http_retries)}</td></tr>)}</tbody></table></div></DiscoveryState>{runs&&<Paging page={runPage} total={runs.total} onChange={setRunPage}/>}</section>
          <section className="recs-panel p-4"><h2 className="mb-3 text-lg font-semibold">Workspace jobs, including previews</h2>{jobs?.items.map(j=><article className="mb-3 border-b p-2" key={j.job_id}><Badge status={j.status}/> Job {j.job_id} {j.stale&&'— stale heartbeat; review before recovery'}<Fields data={j.details as Values}/>{j.details.discovery_run_id&&<button className="underline" onClick={()=>void openRun(j.details.discovery_run_id!)}>Inspect canonical run</button>}</article>)}{jobs&&<Paging page={jobPage} total={jobs.total} onChange={setJobPage}/>}</section>
        </div>}
        {tab==='Settings & Scheduling'&&settings&&<div className="space-y-5"><section className="recs-panel space-y-3 p-5"><h2 className="text-lg font-semibold">Effective instance configuration · read-only</h2><p className="text-sm">{settings.precedence}</p><div className="grid gap-4 lg:grid-cols-3">{([
            ['Discovery scope',['enabled','source_id','media_types','languages','lookback_days','lookahead_days','window_days','sort_by']],
            ['Metadata',['cache_enabled','metadata_ttl_hours','failed_retry_hours','refresh_batch_size']],
            ['API safety',['max_pages','max_requests','timeout','retries','interval','max_retry_after']]
          ] as [string,string[]][]).map(([label,keys])=><section key={label}><h3 className="mb-3 font-semibold">{label}</h3><Fields data={Object.fromEntries(keys.map(k=>[k,settings.effective[k]]))}/></section>)}</div><p>Credentials are never returned. Scope defaults, metadata policy and safety limits use the existing operator configuration.</p></section>
          <section className="recs-panel space-y-3 p-5"><h2 className="text-lg font-semibold">Scheduling intent</h2><p>Server scheduling gate: {settings.capabilities.scheduling?'available':'disabled'}. No schedule is activated by displaying this workspace.</p><fieldset disabled={!settings.capabilities.scheduling||busy} className="grid gap-3 sm:grid-cols-3">{Object.entries(schedule).map(([k,v])=><label key={k} className="text-sm">{k.replace('discovery.','')}{typeof v==='boolean'?<input type="checkbox" className="ml-2" checked={v} onChange={e=>setSchedule(s=>({...s,[k]:e.target.checked}))}/>:<input className="recs-input w-full" type={typeof v==='number'?'number':k.endsWith('.time')?'time':'text'} value={String(v)} onChange={e=>setSchedule(s=>({...s,[k]:typeof v==='number'?Number(e.target.value):e.target.value}))}/>}</label>)}</fieldset><button className="recs-btn-secondary" disabled={busy||!settings.capabilities.scheduling} onClick={()=>void save()}>Save scheduling intent</button><Fields data={settings.next_executions}/><p className="text-sm">Weekly sweep day: Monday=0 through Sunday=6. Wider release searches do not detect every newly cataloged title.</p></section>
        </div>}
      </DiscoveryState>
      {settings&&<section className="recs-panel mt-6 space-y-4 p-5"><h2 className="text-lg font-semibold">Run Discovery</h2><p className="text-sm">Preview contacts Seerr and stores workspace job history, but does not persist canonical discovery records. Persistence requires server authorization and confirmation. Partial results never retry automatically.</p><fieldset disabled={busy} className="grid gap-3 sm:grid-cols-3">
        <label>Media<select className="recs-input w-full" value={form.media} onChange={e=>{setForm({...form,media:e.target.value});setPlan(null);setRequestId(crypto.randomUUID());}}><option value="movie,tv">Movies and TV</option><option value="movie">Movies</option><option value="tv">TV</option></select></label>
        {(['start','end'] as const).map(k=><label key={k}>{k}<input type="date" className="recs-input w-full" value={form[k]} onChange={e=>{setForm({...form,[k]:e.target.value});setPlan(null);setRequestId(crypto.randomUUID());}}/></label>)}
        <label>Languages (comma separated)<input className="recs-input w-full" value={form.languages} onChange={e=>{setForm({...form,languages:e.target.value});setPlan(null);setRequestId(crypto.randomUUID());}}/></label>
        {(['max_pages','max_requests'] as const).map(k=><label key={k}>{k.replace(/_/g,' ')}<input type="number" min={1} max={Number(settings.effective[k])} className="recs-input w-full" value={form[k]} onChange={e=>{setForm({...form,[k]:Number(e.target.value)});setPlan(null);setRequestId(crypto.randomUUID());}}/></label>)}
        <label><input type="checkbox" disabled={!settings.capabilities.persistence} checked={form.persist} onChange={e=>{setForm({...form,persist:e.target.checked});setPlan(null);setRequestId(crypto.randomUUID());}}/> Persist to canonical inventory</label>
      </fieldset><div className="flex flex-wrap gap-3"><button className="recs-btn-secondary" disabled={busy||!form.start||!form.end} onClick={()=>void previewPlan()}>Review scope · no Seerr requests</button><button className="recs-btn-primary" disabled={busy||!plan||!canRun||!!running} onClick={()=>void execute()}>{form.persist?'Confirm & persist':'Run GET-only preview'}</button><button className="recs-btn-secondary" disabled={busy||!!running} onClick={()=>{setRequestId(crypto.randomUUID());setPlan(null);setNotice(null);}}>Prepare new execution</button></div>{!canRun&&<p>Execution is disabled by the server. Scope review remains available.</p>}{plan&&<Fields data={plan}/>}</section>}
      {selected&&<section id="discovery-title-detail" tabIndex={-1} aria-label="Discovered title detail" className="recs-panel mt-6 space-y-4 p-5"><button className="recs-btn-secondary" onClick={()=>setSelected(null)}>Close title detail</button><h2 className="text-2xl font-semibold">{selected.title}</h2><p>{val(selected.synopsis)}</p><Fields data={Object.fromEntries(Object.entries(selected).filter(([k])=>!['history','poster_url','synopsis'].includes(k)))}/><h3 className="font-semibold">Discovery membership history</h3>{selected.history?.items.map((h,i)=><div key={i} className="border-t p-2"><button className="underline" onClick={()=>void openRun(h.run_id!)}>{h.run_id}</button><Fields data={{...h}}/></div>)}{selected.history&&<Paging page={selected.history.page} total={selected.history.total} onChange={p=>void openTitle(selected,p)}/>}</section>}
      {selectedRun&&<section id="discovery-run-detail" tabIndex={-1} aria-label="Discovery execution detail" className="recs-panel mt-6 space-y-4 p-5"><button className="recs-btn-secondary" onClick={()=>setSelectedRun(null)}>Close execution detail</button><RunSummary run={selectedRun}/><Fields data={{pagination:selectedRun.pagination,errors:selectedRun.errors,warnings:selectedRun.warnings}}/><h3 className="font-semibold">Observed new and existing titles</h3>{selectedRun.memberships?.items.map((h,i)=><div className="border-t p-2" key={i}><p>{h.title} · {h.media_type}:{h.tmdb_id} · {h.is_new?'New':'Previously known'}</p><Fields data={{...h}}/></div>)}{selectedRun.memberships&&<Paging page={selectedRun.memberships.page} total={selectedRun.memberships.total} onChange={p=>void openRun(selectedRun.run_id,p)}/>}</section>}
    </></DiscoveryState>
  </AppShell>;
}
