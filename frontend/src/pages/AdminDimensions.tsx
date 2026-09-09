import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import AppShell from '../components/AppShell';
import { ErrorBanner, SuccessBanner } from '../components/StatusBanner';

type RecordData = Record<string, unknown>;
interface Dimension {
  dimension: number; side: string; local_index: number; label: string | null; display_label: string | null;
  label_row_count: number | null; label_type: string | null; eligible: boolean; needs_review: boolean | null; validation_status: string | null;
  review_attempt_count: number; last_reviewed_at: string | null; next_review_at: string | null;
  in_flight: boolean; paused: boolean; suppressed: boolean; cooldown: boolean; due: boolean; version: number;
  investigation_status: string; investigation_reason: string | null; observed_count: number;
  mean_abs_shap: number | null; positive_count: number | null; negative_count: number | null;
  zero_count: number | null; unknown_count: number | null; selected_count: number; semantic_selected_count: number;
  job_status: string | null; outcome: string | null;
}
interface Prediction {
  username: string; rating_key: number; title: string; rank: number | null; predicted_probability: number;
  scored_at: string; media_type: string; shap_value: number | null; selected_groups: string[];
}
interface Payload {
  scope: { model_version: string };
  recent_labeling_runs?: { run_id: number; status: string; exit_code: number | null; started_at: string; completed_at: string | null }[];
  model_versions: { model_version: string; generated_at: string }[];
  config: { config_id: string; media_dimensions: number; user_dimensions: number; model_sha256: string; embedding_model: string; feature_names: string[] };
  rows: Dimension[]; total: number; users: string[]; limitations: string[]; overview: Record<string, number | string | null>;
  thresholds: { repeated_attempts: number; frequent_selections: number };
  recommendations?: Prediction[]; recommendation_total?: number;
  history?: RecordData[]; assessments?: RecordData[]; actions?: RecordData[]; reviews?: RecordData[];
  history_total?: number; assessments_total?: number; actions_total?: number; reviews_total?: number;
  prediction?: Prediction;
  contributions?: (Dimension & { shap_value: number | null; selected_groups: string[] })[];
  selected?: { group_name: string; display_label: string; dimensions: number[] }[];
}

const date = (value: unknown) => {
  if (!value) return 'Not recorded';
  const text = String(value);
  return /(?:Z|[+-]\d{2}:\d{2})$/.test(text)
    ? new Date(text).toLocaleString()
    : `${text.replace('T', ' ')} (DB local)`;
};
const magnitude = (value: number | null) => value == null ? 'No observation' : value.toFixed(5);
const panel = 'recs-surface p-4 sm:p-5';
const td = 'px-3 py-3 align-top';
const linkStyle = 'text-sky-700 underline underline-offset-2';

function SignedBar({ value, max }: { value: number | null; max: number }) {
  if (value == null) return <span>Unknown</span>;
  const width = max ? Math.min(50, Math.abs(value) / max * 50) : 0;
  return <div className="min-w-32"><span className="font-mono text-xs">{value > 0 ? '+' : ''}{value.toFixed(5)}</span>
    <div className="relative mt-1 h-2 w-32 rounded bg-slate-100" aria-hidden="true">
      <span className="absolute left-1/2 h-2 border-l border-slate-500" />
      <span className={`absolute h-2 rounded ${value < 0 ? 'bg-orange-500' : 'bg-emerald-600'}`} style={{ width: `${width}%`, left: value < 0 ? `${50 - width}%` : '50%' }} />
    </div></div>;
}

function Pager({ offset, total, size, onChange }: { offset: number; total: number; size: number; onChange: (offset: number) => void }) {
  return <div className="mt-3 flex items-center gap-3 text-sm">
    <button className="recs-btn-secondary" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - size))}>Previous</button>
    <span>{total ? `${offset + 1}–${Math.min(offset + size, total)} of ${total}` : 'No matching records'}</span>
    <button className="recs-btn-secondary" disabled={offset + size >= total} onClick={() => onChange(offset + size)}>Next</button>
  </div>;
}

function Governance({ row }: { row: Dimension }) {
  return <div className="space-y-1 text-xs">
    {(row.label_row_count || 0) > 1 && <p className="text-orange-700">Multiple saved rows: latest timestamped wording shown. Investigate before review.</p>}
    <p>{row.label_type || 'Unclassified'} · {row.eligible ? 'Explanation eligible' : 'Explanation ineligible'}</p>
    <p>{row.needs_review ? 'Unresolved review' : row.label ? 'No unresolved review' : 'Not assessed'} · Candidate validation: {row.validation_status || 'Not retained'}</p>
    <p>{row.paused ? 'Review paused' : row.cooldown ? 'Cooldown' : row.due ? 'Review due' : 'No scheduled review'} · {row.review_attempt_count} attempts</p>
    {row.suppressed && <p>Administrator display suppression</p>}
    {row.investigation_status === 'open' && <p>Investigation open</p>}
    {row.in_flight && <p className="text-orange-700">Assessment in flight (may finish while paused)</p>}
    {row.job_status && <p>Latest request: {row.job_status}</p>}
  </div>;
}

function Evidence({ assessment }: { assessment: RecordData }) {
  const prompt = assessment.prompt as RecordData;
  const result = assessment.result as RecordData;
  return <details className="recs-surface-muted p-3">
    <summary className="cursor-pointer">{date(assessment.created_at)} · {String(assessment.outcome)} · validation {String(result.validation_status || 'unknown')}</summary>
    <p className="mt-2 text-sm">Actual retained assessment · {String(assessment.source)} · {String(assessment.provider)}:{String(assessment.model)}</p>
    <p className="text-sm">Candidate: {String(result.label || 'None')} · Saved: {assessment.saved ? 'yes' : 'no'}. A saved valid candidate can remain unresolved.</p>
    <p className="my-2 text-sm">{String(result.explanation || '')} {String(prompt.skipped_reason || '')}</p>
    <ul className="list-inside list-disc text-sm">{((result.validation_notes || []) as string[]).map((note, i) => <li key={i}>{note}</li>)}</ul>
    <p className="mt-2 text-sm">HIGH eligible: {String(prompt.valid_positive_count)} · LOW eligible: {String(prompt.valid_negative_count)} · flagged: {String(prompt.flagged_item_count)}</p>
    {(['positive_items', 'negative_items'] as const).map(key => <div className="mt-3" key={key}>
      <h4 className="font-semibold">{key === 'positive_items' ? 'Supporting HIGH evidence used' : 'Contrasting LOW evidence used'}</h4>
      <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr><th>Title / user</th><th>Watch seconds</th><th>Engagement</th><th>Training label</th></tr></thead>
        <tbody>{((prompt[key] || []) as RecordData[]).map((item, i) => <tr key={i}><td className="py-2">{String(item.display_title || item.title || 'Unknown')} {String(item.username || '')}</td><td>{String(item.played_duration ?? 'Not retained')}</td><td>{String(item.engagement_ratio ?? 'Not retained')}</td><td>{String(item.training_label ?? 'Not retained')}</td></tr>)}</tbody>
      </table></div>
    </div>)}
    <p className="mt-2 text-xs">User samples follow the existing positive training-label and engagement ≥ 0.50 evidence rule. Watch history alone does not establish preference.</p>
    <details className="mt-2"><summary>Exact prompt and assessment states</summary><pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{String(prompt.prompt_text || 'Not retained')}{'\n'}{JSON.stringify({ before: assessment.before_state, after: assessment.after_state, result }, null, 2)}</pre></details>
  </details>;
}

export default function AdminDimensions() {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [reason, setReason] = useState('');
  const [action, setAction] = useState('review');
  const dimension = params.get('dimension');
  const prediction = params.get('prediction');
  const query = params.toString();
  const pageOffset = Number(params.get('offset') || 0);
  const recOffset = Number(params.get('rec_offset') || 0);
  const historyOffset = Number(params.get('history_offset') || 0);
  function change(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    if (!['offset', 'rec_offset', 'history_offset'].includes(key)) {
      next.delete('offset'); next.delete('rec_offset'); next.delete('history_offset');
    }
    setParams(next);
  }
  function href(updates: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    if (data?.scope?.model_version) next.set('model_version', data.scope.model_version);
    Object.entries(updates).forEach(([key, value]) => value == null ? next.delete(key) : next.set(key, value));
    return `/admin/dimensions?${next}`;
  }
  useEffect(() => {
    const controller = new AbortController();
    const q = new URLSearchParams(query);
    let endpoint = '/api/admin/dimensions';
    if (prediction) {
      endpoint += '/prediction';
      q.set('username', q.get('prediction_user') || '');
      q.set('rating_key', prediction);
    } else if (dimension !== null) {
      endpoint += `/${dimension}`; q.set('offset', q.get('rec_offset') || '0'); q.set('limit', '25');
    }
    setLoading(true); setError('');
    const timer = window.setTimeout(() => fetch(`${endpoint}?${q}`, { credentials: 'include', signal: controller.signal })
      .then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`); return body; })
      .then(body => { setData(body); setLoading(false); })
      .catch(err => { if (!controller.signal.aborted) { setError(String(err.message)); setLoading(false); } }), 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [query, dimension, prediction, refresh]);
  useEffect(() => { setReason(''); setAction('review'); setMessage(''); }, [dimension]);
  const pending = data?.rows?.some(row => row.in_flight || ['queued', 'running'].includes(row.job_status || ''));
  useEffect(() => {
    if (!pending) return;
    const timer = window.setInterval(() => setRefresh(n => n + 1), 10000);
    return () => window.clearInterval(timer);
  }, [pending]);
  async function intervene() {
    if (!data || !data.rows[0]) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await fetch(`/api/admin/dimensions/${dimension}/actions`, {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config_id: data.config.config_id, version: data.rows[0].version, action, reason }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || 'Action failed');
      setMessage(action === 'review' ? `Review ${body.status}. No label change occurs until assessment and validation finish.` : 'Intervention recorded.');
      setAction('review'); setReason(''); setRefresh(n => n + 1);
    } catch (err) { setError(err instanceof Error ? err.message : 'Action failed'); }
    finally { setBusy(false); }
  }
  const row = data?.rows?.[0];
  const contributions = data?.contributions || [];
  const maxShap = Math.max(0, ...contributions.map(item => Math.abs(item.shap_value || 0)));
  return <AppShell eyebrow="Administration" title="Dimension & Label Explorer" description="Trace embedding features, recommendation evidence, and automated label reviews.">
    <div className="space-y-4">
      {error && <ErrorBanner message={error} />}{message && <SuccessBanner message={message} />}
      <div className="flex flex-wrap items-center gap-3">
        {(dimension !== null || prediction) && <Link className={linkStyle} to={href({ dimension: null, prediction: null, prediction_user: null, scored_at: null, rec_offset: null, history_offset: null })}>← Dimension register</Link>}
        {prediction && dimension !== null && <Link className={linkStyle} to={href({ prediction: null, prediction_user: null, scored_at: null })}>← Dimension {dimension}</Link>}
        <button className="recs-btn-secondary" onClick={() => setRefresh(n => n + 1)} disabled={loading}>Refresh</button>
      </div>
      {!prediction && <section className={panel} aria-label="Scope and register filters">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <label className="text-xs">User<select className="recs-input mt-1 w-full" value={params.get('username') || ''} onChange={e => change('username', e.target.value)}><option value="">All users</option>{data?.users?.map(user => <option key={user}>{user}</option>)}</select></label>
          <label className="text-xs">Media type<select className="recs-input mt-1 w-full" value={params.get('media_type') || ''} onChange={e => change('media_type', e.target.value)}>{['', 'movie', 'episode', 'show', 'season'].map(type => <option key={type} value={type}>{type || 'All types'}</option>)}</select></label>
          <label className="text-xs">Stored recommendation rank<select className="recs-input mt-1 w-full" value={params.get('top_n') || '100'} onChange={e => change('top_n', e.target.value)}>{[25, 100, 250, 1000, 0].map(n => <option key={n} value={n}>{n ? `Top ${n} per user (global rank)` : 'All ranks'}</option>)}</select></label>
          <label className="text-xs">Retained model snapshot<select className="recs-input mt-1 w-full" value={params.get('model_version') || data?.scope?.model_version || 'legacy'} onChange={e => change('model_version', e.target.value)}><option value="legacy">Legacy — model / run unverified</option>{data?.model_versions?.map(v => <option key={v.model_version} value={v.model_version}>{v.model_version.slice(0, 12)} · {date(v.generated_at)}</option>)}</select></label>
          {dimension === null && <>
            <label className="text-xs">Search wording or dimension ID<input className="recs-input mt-1 w-full" placeholder="Label, 768, emb_768, user:0" value={params.get('search') || ''} onChange={e => change('search', e.target.value)} /></label>
            <label className="text-xs">Embedding side<select className="recs-input mt-1 w-full" value={params.get('side') || ''} onChange={e => change('side', e.target.value)}><option value="">Both sides</option><option value="media">Media</option><option value="user">User</option></select></label>
            <label className="text-xs">Governance / exception filter<select className="recs-input mt-1 w-full" value={params.get('status') || ''} onChange={e => change('status', e.target.value)}>{Object.entries({ '': 'All dimensions', unlabeled: 'Unlabeled', unresolved: 'Unresolved review', due: 'Due reviews', cooldown: 'Cooldowns', paused: 'Paused', suppressed: 'Display suppressed', investigation: 'Investigation open', repeated: 'Unresolved with repeated attempts', rejected: 'Rejected replacement', overdue: 'Overdue reviews', frequent_review: 'Frequently selected under review', errors: 'Processing errors' }).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            <label className="text-xs">Sort<select className="recs-input mt-1 w-full" value={params.get('sort') || 'dimension'} onChange={e => change('sort', e.target.value)}>{Object.entries({ dimension: 'Dimension index', usage: 'Observed prediction count', magnitude: 'Mean absolute SHAP', selected: 'Current rule selection count', attempts: 'Review attempts', next_review: 'Next review date' }).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          </>}
        </div>
        <p className="mt-3 text-xs text-slate-500">Active scope: {params.get('username') || 'all users'} · {params.get('media_type') || 'all media types'} · {params.get('top_n') === '0' ? 'all ranks' : `top ${params.get('top_n') || 100}`} · {data?.scope?.model_version === 'legacy' ? 'unversioned legacy observations' : (data?.scope?.model_version || '').slice(0, 12)} · current snapshot only.</p>
      </section>}
      {loading && <p role="status" className={panel}>Loading scoped evidence…</p>}
      {!loading && !error && data && <>
        <section className={`${panel} text-sm`}>
          <p>Configuration <code>{data.config.config_id}</code> · {data.config.media_dimensions} media + {data.config.user_dimensions} user dimensions · {data.config.embedding_model}</p>
          <details className="mt-2"><summary className="cursor-pointer font-medium">Coverage, units, and historical limitations</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-xs">{data.limitations.map(item => <li key={item}>{item}</li>)}</ul><p className="mt-2 text-xs">Registered model artifact: {data.config.model_sha256}. This is metadata observed at registration, not a historical scoring-run association. {data.config.feature_names.length - data.config.media_dimensions - data.config.user_dimensions} non-embedding model features are outside this register.</p></details>
        </section>
        {!prediction && <>
          <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" aria-label="Inventory overview">
            {['inventory_count', 'unlabeled', 'unresolved', 'due', 'cooldown', 'repeated'].map(key => <div className={panel} key={key}><p className="text-2xl font-semibold">{data.overview[key]}</p><p className="text-xs capitalize">{key.replace('_', ' ')}</p></div>)}
          </section>
          <p className="text-xs text-slate-500">Scope denominator: {data.overview.scoped_predictions} current scored user/title instances; {data.overview.observed_predictions} have retained SHAP. Selected wordings: {data.overview.selected_wordings} across API groups; {data.overview.semantic_selected_wordings} legacy semantic themes (deduplicated before dimension attribution). Scores updated {date(data.overview.scored_at)}; SHAP updated {date(data.overview.shap_timestamp)}. Repeated = ≥{data.thresholds.repeated_attempts} attempts on a currently unresolved label (not a consecutive-failure count); frequent = ≥{data.thresholds.frequent_selections} current selections. These filters do not change automatic review policy. Unresolved labels are normally ineligible, so the frequent-under-review filter can be empty.</p>
        </>}
        {!prediction && dimension === null && <details className={panel}>
          <summary className="cursor-pointer font-medium">Recent labeling executions</summary>
          <p className="my-2 text-xs">Global pipeline stage records, outside the selected SHAP scope. Execution success does not establish review progress; resolution counts were not tracked.</p>
          {data.recent_labeling_runs?.length ? <ul className="space-y-1 text-sm">{data.recent_labeling_runs.map(run => <li key={run.run_id}>Run {run.run_id} · {run.status} · exit {run.exit_code ?? 'pending'} · {date(run.started_at)}</li>)}</ul> : <p className="text-sm">No retained pipeline labeling run records.</p>}
          <Link className={linkStyle} to="/admin/pipeline">Open pipeline runs</Link>
        </details>}
        {!prediction && dimension === null && <section className={panel}>
          <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="text-xs text-slate-500"><tr><th className={td}>Feature / local index</th><th className={td}>Current wording</th><th className={td}>Governance</th><th className={td}>Retained SHAP usage</th><th className={td}>Selected by current explanation rules</th><th className={td}>Review dates</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{data.rows.map(item => <tr key={item.dimension}><td className={td}><Link className={linkStyle} to={href({ dimension: String(item.dimension) })}>emb_{item.dimension}</Link><p className="text-xs">{item.side}:{item.local_index}</p></td><td className={td}>{item.display_label || item.label || <em>Unlabeled</em>}</td><td className={td}><Governance row={item} /></td><td className={td}><p>{item.observed_count} observed predictions</p><p className="text-xs">Mean |SHAP|: {magnitude(item.mean_abs_shap)}</p><p className="text-xs">+ {item.positive_count ?? '—'} / − {item.negative_count ?? '—'} / zero {item.zero_count ?? '—'} / unknown {item.unknown_count ?? '—'}</p></td><td className={td}>{item.selected_count} API group selections<p className="text-xs">{item.semantic_selected_count} legacy themes</p></td><td className={`${td} text-xs`}>Last: {date(item.last_reviewed_at)}<br />Next: {date(item.next_review_at)}</td></tr>)}</tbody>
          </table></div><Pager offset={pageOffset} total={data.total} size={50} onChange={n => change('offset', String(n))} />
        </section>}
        {!prediction && dimension !== null && row && <>
          <section className={panel}><h2 className="text-xl font-semibold">emb_{row.dimension} · {row.side}:{row.local_index}</h2><p className="my-2 text-lg">{row.display_label || row.label || 'Unlabeled'}</p><p className="mb-2 text-xs">Saved wording: {row.label || 'None'}</p><Governance row={row} /><p className="mt-2 text-sm">Last review: {date(row.last_reviewed_at)} · Next: {date(row.next_review_at)}</p><p className="mt-2 text-sm">{row.observed_count} observed user/title instances · mean |SHAP| {magnitude(row.mean_abs_shap)} · signs +{row.positive_count ?? '—'} / −{row.negative_count ?? '—'} / zero {row.zero_count ?? '—'} / unknown {row.unknown_count ?? '—'} · {row.selected_count} current API group selections / {row.semantic_selected_count} legacy theme selections</p></section>
          <section className={panel}><h2 className="mb-3 text-lg font-semibold">Scoped recommendation evidence</h2><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className={td}>User / title</th><th className={td}>Rank / score</th><th className={td}>Signed SHAP (raw margin)</th><th className={td}>Current selection groups</th></tr></thead><tbody>{data.recommendations?.map(item => <tr key={`${item.username}:${item.rating_key}`}><td className={td}><Link className={linkStyle} to={href({ prediction: String(item.rating_key), prediction_user: item.username, scored_at: item.scored_at })}>{item.title}</Link><p className="text-xs">{item.username} · {item.media_type}</p></td><td className={td}>{item.rank ?? '—'} / {item.predicted_probability.toFixed(5)}</td><td className={td}><SignedBar value={item.shap_value} max={Math.max(0, ...(data.recommendations || []).map(r => Math.abs(r.shap_value || 0)))} /></td><td className={td}>{item.selected_groups.join(', ') || 'Not selected'}</td></tr>)}</tbody></table></div><Pager offset={recOffset} total={data.recommendation_total || 0} size={25} onChange={n => change('rec_offset', String(n))} /></section>
          <section className={`${panel} space-y-3`}><h2 className="text-lg font-semibold">Review evidence & history</h2>
            {!data.assessments?.length && <p className="text-sm">No retained assessment evidence on this page. Older CSV exports are not imported or presented as original database review evidence.</p>}
            {data.assessments?.map(item => <Evidence key={String(item.assessment_id)} assessment={item} />)}
            {(['history', 'reviews', 'actions'] as const).map(key => <details key={key}><summary className="cursor-pointer capitalize">{key === 'history' ? 'Recorded wording revisions (legacy, configuration unrecorded)' : key} · {data[`${key}_total`] || 0} records</summary>{data[key]?.length ? data[key]?.map((item, i) => <pre className="my-2 max-h-60 overflow-auto whitespace-pre-wrap text-xs" key={i}>{JSON.stringify(item, null, 2)}</pre>) : <p className="text-sm">No records on this page.</p>}</details>)}
            <Pager offset={historyOffset} total={Math.max(data.history_total || 0, data.actions_total || 0, data.reviews_total || 0, data.assessments_total || 0)} size={20} onChange={n => change('history_offset', String(n))} />
          </section>
          <section className={`${panel} space-y-3`}><h2 className="text-lg font-semibold">Targeted intervention</h2><p className="text-sm">Review runs in the background and bypasses only this dimension’s cooldown. Pause prevents future selections; an in-flight assessment can finish. Resume keeps the existing next-review date. Suppression affects explanation wording only; shared wording can still appear through another eligible dimension. Investigation changes neither scheduling nor eligibility.</p><p className="text-sm">Investigation: {row.investigation_status} · {row.investigation_reason || 'No reason recorded'}</p>
            <label className="block text-xs">Action<select className="recs-input mt-1 w-full" value={action} onChange={e => setAction(e.target.value)}><option value="review">Request review / retry now</option><option value={row.paused ? 'resume' : 'pause'}>{row.paused ? 'Resume' : 'Pause'} automatic review</option><option value={row.suppressed ? 'restore' : 'suppress'}>{row.suppressed ? 'Restore' : 'Suppress'} explanation display</option><option value={row.investigation_status === 'open' ? 'clear' : 'investigate'}>{row.investigation_status === 'open' ? 'Clear' : 'Flag'} investigation</option></select></label>
            <label className="block text-xs">Reason (recorded with your administrator identity)<textarea className="recs-input mt-1 w-full" maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></label>
            <button className="recs-btn-primary" disabled={busy || !reason.trim() || (action === 'review' && row.paused)} onClick={intervene}>{busy ? 'Recording…' : 'Apply to this dimension'}</button>
            {row.paused && <p className="text-xs">Resume before requesting review. Pausing does not hide the current label.</p>}
          </section>
        </>}
        {prediction && data.prediction && <section className={panel}>
          <h2 className="text-xl font-semibold">{data.prediction.title} · {data.prediction.username}</h2><p className="my-2 text-sm">Current prediction {data.prediction.rating_key} · rank {data.prediction.rank ?? '—'} · score {data.prediction.predicted_probability.toFixed(5)} · scored {date(data.prediction.scored_at)}</p>
          <p className="text-sm">Current selected wording:</p><ul className="mb-4 text-sm">{data.selected?.map((item, i) => <li key={i}>{item.group_name}: {item.display_label} (dimensions {item.dimensions.join(', ')})</li>)}</ul>{!data.selected?.length && <p className="mb-4 text-sm">No wording selected. Show/season rollups do not have leaf-level explanations.</p>}
          <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className={td}>Feature</th><th className={td}>Current wording</th><th className={td}>Signed contribution</th><th className={td}>Selected groups</th></tr></thead><tbody>{contributions.map(item => <tr key={item.dimension}><td className={td}>{item.side === 'media' || item.side === 'user' ? <Link className={linkStyle} to={href({ dimension: String(item.dimension), prediction: null, prediction_user: null, scored_at: null, rec_offset: null, history_offset: null })}>emb_{item.dimension} · {item.side}:{item.local_index}</Link> : item.side}</td><td className={td}>{item.display_label || item.label || 'Unlabeled'}</td><td className={td}><SignedBar value={item.shap_value} max={maxShap} /></td><td className={td}>{item.selected_groups.join(', ') || 'Not selected'}</td></tr>)}</tbody></table></div>{!contributions.length && <p>No retained contributions for this current user/title context.</p>}
        </section>}
      </>}
    </div>
  </AppShell>;
}
