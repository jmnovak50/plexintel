import { Fragment, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { CircleStop, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import { ErrorBanner, SuccessBanner } from "../components/StatusBanner";
import { stageLabels, stageDuration, stageProgress, readablePipelineLog, operatorStages } from "../utils/pipelineStages";

interface AdminMe {
  username: string;
  friendly_name: string | null;
  display_name: string | null;
  is_admin: boolean;
}

interface PipelineStage {
  stage_id: number | string;
  run_id: number;
  stage_key: string;
  status: string;
  exit_code: number | null;
  stdout_tail: string | null;
  stderr_tail: string | null;
  started_at: string | null;
  completed_at: string | null;
  label?: string;
  duration_seconds?: number | null;
  metrics?: Record<string, number | boolean>;
  message?: string | null;
  detail_source?: string;
  observed_at?: string;
  timing_active?: boolean;
  timing_known?: boolean;
  worker_output?: boolean;
}

interface PipelineRun {
  embedded_media?: { rating_key: string; title: string | null; show_title: string | null; media_type: string | null }[];
  embedded_media_total?: number;
  embedded_media_note?: string;
  run_id: number;
  delivery_type: string;
  schedule_key: string | null;
  triggered_by: string | null;
  status: string;
  notes: string | null;
  cancel_requested_at: string | null;
  cancel_requested_by: string | null;
  last_heartbeat_at: string | null;
  current_stage_key: string | null;
  current_pid: number | null;
  started_at: string | null;
  completed_at: string | null;
  stages: PipelineStage[];
  stage_details?: PipelineStage[];
  stage_detail_note?: string;
  production_run_id?: string;
  publication_id?: string;
  semantic_labeling?: { status: string; reason: string };
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function durationMs(started: string | null, completed: string | null) {
  if (!started || !completed) return "—";
  const a = new Date(started).getTime();
  const b = new Date(completed).getTime();
  if (Number.isNaN(a) || Number.isNaN(b)) return "—";
  const sec = Math.round((b - a) / 1000);
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}m ${s}s`;
}

interface LogStream {
  text: string;
  offset: number;
  next_offset: number | null;
  total_characters: number;
  source: string;
  note?: string | null;
  identity: string;
}
interface StageLogs { stdout: LogStream; stderr: LogStream }

export function PipelineLog({ stdout, stderr, loading = false }: { stdout: string | null; stderr: string | null; loading?: boolean }) {
  return <div className="space-y-3">
    {([['stdout:', stdout], ['stderr:', stderr]] as const).map(([label, text]) => (text || label === 'stdout:') ? <section key={label} aria-label={label}>
      <h4 className="mb-1 font-mono text-xs font-semibold text-slate-700">{label}</h4>
      {text ? <pre data-stream={label} className="max-h-64 overflow-auto whitespace-pre-wrap rounded bg-slate-900/90 p-3 font-mono text-xs leading-5 text-slate-100">{text}</pre>
        : <p className="text-xs text-slate-500">{loading ? 'Loading retained stdout…' : 'No stdout output was retained for this stage.'}</p>}
    </section> : null)}
  </div>;
}

export function PipelineStageCard({ st, runId, activeRun = false }: { st: PipelineStage; runId?: number; activeRun?: boolean }) {
  const [open, setOpen] = useState(!st.worker_output);
  const [logs, setLogs] = useState<StageLogs | null>(null);
  const [logError, setLogError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);
  const content = useRef<HTMLDivElement>(null);
  const scrollPositions = useRef(new Map<string | undefined, { top: number; follow: boolean }>());
  const progress = stageProgress(st.metrics);

  useLayoutEffect(() => {
    if (!logs) return;
    content.current?.querySelectorAll('pre').forEach(el => {
      const previous = scrollPositions.current.get(el.dataset.stream);
      el.scrollTop = !previous || previous.follow ? el.scrollHeight : previous.top;
    });
  }, [logs]);

  useEffect(() => {
    if ((!open && !st.worker_output) || runId == null) return;
    const controller = new AbortController();
    let busy = false;
    async function load() {
      if (busy) return;
      busy = true;
      setFetching(true);
      try {
        let out = '', err = '', outOffset = 0, errOffset = 0;
        let outIdentity: string | undefined, errIdentity: string | undefined;
        let page: StageLogs;
        let resets = 0;
        while (true) {
          const response = await fetch(`/api/admin/pipeline/runs/${runId}/stages/${encodeURIComponent(st.stage_key)}/logs?stdout_offset=${outOffset}&stderr_offset=${errOffset}`, {
            credentials: 'include', cache: 'no-store', signal: controller.signal,
          });
          if (!response.ok) throw new Error(`Unable to load stage output (${response.status})`);
          page = await response.json();
          if ((outIdentity && outIdentity !== page.stdout.identity) || page.stdout.offset !== outOffset ||
              (errIdentity && errIdentity !== page.stderr.identity) || page.stderr.offset !== errOffset) {
            if (++resets > 3) throw new Error('Retained output changed while loading; close and reopen the stage to retry.');
            out = ''; err = ''; outOffset = 0; errOffset = 0;
            outIdentity = undefined; errIdentity = undefined;
            continue;
          }
          out += page.stdout.text;
          err += page.stderr.text;
          outIdentity = page.stdout.identity;
          errIdentity = page.stderr.identity;
          outOffset = page.stdout.next_offset ?? page.stdout.total_characters;
          errOffset = page.stderr.next_offset ?? page.stderr.total_characters;
          if (page.stdout.next_offset == null && page.stderr.next_offset == null) break;
        }
        if (controller.signal.aborted) return;
        scrollPositions.current = new Map(Array.from(content.current?.querySelectorAll('pre') || []).map(el => [el.dataset.stream, {
          top: el.scrollTop, follow: el.scrollHeight - el.scrollTop - el.clientHeight < 32,
        }]));
        setLogs({ stdout: { ...page.stdout, text: out }, stderr: { ...page.stderr, text: err } });
        setLogError(null);
      } catch (caught) {
        if (!controller.signal.aborted) setLogError(caught instanceof Error ? caught.message : 'Unable to load stage output.');
      } finally {
        busy = false;
        if (!controller.signal.aborted) setFetching(false);
      }
    }
    void load();
    const timer = activeRun ? window.setInterval(() => void load(), 5000) : undefined;
    return () => { controller.abort(); if (timer) window.clearInterval(timer); };
  }, [open, runId, st.stage_key, st.status, st.worker_output, activeRun]);

  if (st.worker_output && !logError && (!logs || (!logs.stdout.text && !logs.stderr.text))) return null;
  const stdout = logs ? logs.stdout.text : readablePipelineLog(st.stdout_tail);
  const stderr = logs ? logs.stderr.text : readablePipelineLog(st.stderr_tail);
  return <div className="recs-surface-muted p-3" data-stage-key={st.stage_key}>
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <h3 className="font-medium text-slate-900">{st.worker_output ? `${stageLabels[st.stage_key] || st.stage_key} — unattributed output` : st.label || stageLabels[st.stage_key] || st.stage_key}</h3>
      <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${statusChip(st.status)}`}>{st.status}</span>
      {st.exit_code != null && <span className="text-xs text-slate-500">exit {st.exit_code}</span>}
      <span className="text-xs text-slate-500">{stageDuration(st.duration_seconds, st.status, st.started_at, st.completed_at, st.observed_at, st.timing_active, st.timing_known)}</span>
      {progress && <span className="text-xs text-slate-500">Progress: {progress.percent}% ({progress.completed.toLocaleString()} / {progress.expected.toLocaleString()})</span>}
    </div>
    <details className="mt-2" open={open} onToggle={event => { setOpen(event.currentTarget.open); if (!event.currentTarget.open) setFetching(false); }}>
      <summary className="cursor-pointer text-xs text-slate-600">Stage output{fetching ? ' · Loading…' : ''}</summary>
      <div ref={content} className="mt-2">
        {logError && <p role="alert" className="recs-notice-red mb-2">{logError}</p>}
        {logs?.stdout.note && <p className="mb-2 text-xs text-slate-500">{logs.stdout.note}</p>}
        {logs?.stderr.note && logs.stderr.note !== logs.stdout.note && <p className="mb-2 text-xs text-slate-500">{logs.stderr.note}</p>}
        <PipelineLog stdout={stdout} stderr={stderr} loading={fetching && !logs} />
        {logs && (stdout || stderr) && <p className="mt-2 text-xs text-slate-500">{logError ? 'Previously loaded output; refresh failed.' : fetching ? 'Refreshing output…' : 'All currently available output loaded.'}</p>}
      </div>
    </details>
  </div>;
}

function statusChip(status: string) {
  switch (status) {
    case "success":
      return "recs-status-emerald";
    case "failed":
      return "recs-status-red";
    case "cancelled":
    case "skipped":
      return "recs-status-slate-muted";
    case "cancel_requested":
      return "recs-status-orange";
    case "started":
      return "recs-status-amber-strong";
    default:
      return "recs-status-slate";
  }
}

function isActiveRun(status: string) {
  return status === "started" || status === "cancel_requested";
}

async function responseMessage(response: Response, fallback: string) {
  const text = await response.text();
  if (!text) return fallback;
  try {
    const parsed = JSON.parse(text);
    return parsed.detail || fallback;
  } catch {
    return text;
  }
}

export default function AdminPipeline() {
  const navigate = useNavigate();
  const [me, setMe] = useState<AdminMe | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const initialized = useRef(false);
  const refreshVersion = useRef(0);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [purging, setPurging] = useState(false);
  const [cancellingRunId, setCancellingRunId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
  const [retentionChoice, setRetentionChoice] = useState("50");
  const [customRetention, setCustomRetention] = useState("50");
  const hasActiveRun = runs.some((run) => isActiveRun(run.status));
  const retentionCount = retentionChoice === "custom"
    ? Number(customRetention)
    : Number(retentionChoice);
  const retentionCountIsValid = Number.isInteger(retentionCount)
    && retentionCount >= 1
    && retentionCount <= 1000;

  const loadRuns = useCallback(async () => {
    const version = ++refreshVersion.current;
    const response = await fetch("/api/admin/pipeline/runs?limit=50", { credentials: "include", cache: "no-store" });
    if (!response.ok) throw new Error(`Unable to load pipeline runs (${response.status})`);
    const data = await response.json();
    const nextRuns: PipelineRun[] = data.runs ?? [];
    if (version !== refreshVersion.current) return;
    setRuns(nextRuns);
  }, []);

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
      if (!initialized.current) setLoading(true);
      setError(null);
      try {
        const meRes = await fetch("/api/admin/me", { credentials: "include" });
        if (!meRes.ok) {
          if (meRes.status === 401 || meRes.status === 403) {
            navigate("/", { replace: true });
            return;
          }
          throw new Error(`Unable to load admin identity (${meRes.status})`);
        }
        const meData: AdminMe = await meRes.json();
        if (!mounted) return;
        if (!meData.is_admin) {
          navigate("/recs", { replace: true });
          return;
        }
        setMe(meData);
        await loadRuns();
      } catch (caught) {
        if (!mounted) return;
        setError(caught instanceof Error ? caught.message : "Failed to load pipeline monitor.");
      } finally {
        if (mounted) {
          initialized.current = true;
          setLoading(false);
        }
      }
    }

    bootstrap();
    return () => {
      mounted = false;
    };
  }, [navigate, loadRuns]);

  useEffect(() => {
    if (!hasActiveRun) return undefined;
    const timer = window.setInterval(() => {
      void loadRuns().catch((caught) => {
        setError(caught instanceof Error ? caught.message : "Failed to refresh pipeline runs.");
      });
    }, 5000);
    return () => window.clearInterval(timer);
  }, [hasActiveRun, loadRuns]);

  async function triggerRun() {
    setTriggering(true);
    setStatus(null);
    setError(null);
    try {
      const response = await fetch("/api/admin/pipeline/trigger", {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error(await responseMessage(response, `Trigger failed (${response.status})`));
      }
      const data = await response.json();
      setStatus(data.detail || "Pipeline started in the background.");
      await loadRuns();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Trigger failed.");
    } finally {
      setTriggering(false);
    }
  }

  async function cancelRun(runId: number) {
    setCancellingRunId(runId);
    setStatus(null);
    setError(null);
    try {
      const response = await fetch(`/api/admin/pipeline/runs/${runId}/cancel`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error(await responseMessage(response, `Cancel failed (${response.status})`));
      }
      const data = await response.json();
      setStatus(data.detail || "Pipeline cancellation requested.");
      await loadRuns();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Cancel failed.");
    } finally {
      setCancellingRunId(null);
    }
  }

  async function purgeRuns() {
    if (!retentionCountIsValid) {
      setStatus(null);
      setError("Keep newest must be a whole number from 1 to 1000.");
      return;
    }

    const confirmed = window.confirm(
      `Purge completed pipeline runs older than the newest ${retentionCount}? `
      + "Active runs and the current scheduler record will be protected. This cannot be undone.",
    );
    if (!confirmed) return;

    setPurging(true);
    setStatus(null);
    setError(null);
    try {
      const response = await fetch(`/api/admin/pipeline/runs?keep=${retentionCount}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error(await responseMessage(response, `Purge failed (${response.status})`));
      }
      const data = await response.json();
      setStatus(data.detail || (
        data.deleted_count
          ? `Purged ${data.deleted_count} older pipeline runs.`
          : "No eligible pipeline runs were old enough to purge."
      ));
      setExpandedRunId(null);
      await loadRuns();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Purge failed.");
    } finally {
      setPurging(false);
    }
  }

  function toggleExpand(runId: number) {
    setExpandedRunId((prev) => (prev === runId ? null : runId));
  }

  return (
    <AppShell
      eyebrow="Operations"
      title="Pipeline runs"
      description="Monitor nightly training pipeline executions, inspect per-stage logs, and start a manual run. Schedule and enable the in-app scheduler under Settings → Nightly pipeline."
      signedInAs={me?.display_name || me?.username || "…"}
      maxWidthClass="max-w-6xl"
      headerActions={(
        <>
          <button
            type="button"
            onClick={() => void triggerRun()}
            disabled={triggering || loading || hasActiveRun}
            className="recs-btn-primary"
          >
            {triggering ? "Starting…" : hasActiveRun ? "Pipeline running" : "Run pipeline now"}
          </button>
          <button
            type="button"
            onClick={() => void loadRuns()}
            className="recs-btn-secondary px-4 py-2 text-sm"
          >
            Refresh
          </button>
        </>
      )}
    >
      {error && <ErrorBanner message={error} />}
      {status && <SuccessBanner message={status} />}

      {loading ? (
        <div className="recs-surface-muted px-5 py-6 text-sm text-slate-500">
          Loading runs…
        </div>
      ) : (
        <section className="recs-surface overflow-hidden">
          <div className="flex flex-col gap-4 border-b border-slate-100 bg-slate-50/80 px-5 py-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Recent runs</h2>
              <p className="text-sm text-slate-500">
                Scheduled runs appear when the in-app scheduler is enabled and a slot completes successfully once per
                schedule key. Failed scheduled runs retry until success.
              </p>
            </div>
            <div className="recs-notice-red flex flex-wrap items-end gap-2 p-3">
              <div>
                <label htmlFor="pipeline-retention" className="mb-1 block text-xs font-medium text-slate-700">
                  Keep newest
                </label>
                <select
                  id="pipeline-retention"
                  value={retentionChoice}
                  onChange={(event) => setRetentionChoice(event.target.value)}
                  disabled={purging}
                  className="recs-input w-28 py-2"
                >
                  <option value="10">10</option>
                  <option value="25">25</option>
                  <option value="50">50</option>
                  <option value="100">100</option>
                  <option value="custom">Custom</option>
                </select>
              </div>
              {retentionChoice === "custom" && (
                <div>
                  <label htmlFor="pipeline-custom-retention" className="mb-1 block text-xs font-medium text-slate-700">
                    Run count
                  </label>
                  <input
                    id="pipeline-custom-retention"
                    type="number"
                    min="1"
                    max="1000"
                    step="1"
                    value={customRetention}
                    onChange={(event) => setCustomRetention(event.target.value)}
                    disabled={purging}
                    aria-invalid={!retentionCountIsValid}
                    className="recs-input w-28 py-2"
                  />
                </div>
              )}
              <button
                type="button"
                onClick={() => void purgeRuns()}
                disabled={purging || !retentionCountIsValid}
                className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm font-medium text-red-800 transition-colors hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                {purging ? "Purging…" : "Purge older runs"}
              </button>
              {retentionChoice === "custom" && !retentionCountIsValid && (
                <p className="w-full text-xs text-red-700">Enter a whole number from 1 to 1000.</p>
              )}
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-100 text-sm text-slate-900">
              <thead className="bg-slate-50/95 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Started</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Duration</th>
                    <th className="px-4 py-3">Triggered by</th>
                    <th className="px-4 py-3">Schedule key</th>
                    <th className="px-4 py-3">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {runs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                        No pipeline runs recorded yet.
                      </td>
                    </tr>
                  ) : (
                    runs.map((run) => (
                      <Fragment key={run.run_id}>
                        <tr data-run-id={run.run_id} className="hover:bg-amber-50/30">
                          <td className="whitespace-nowrap px-4 py-3 text-slate-800">{formatDate(run.started_at)}</td>
                          <td className="px-4 py-3 capitalize text-slate-700">{run.delivery_type}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${statusChip(run.status)}`}
                            >
                              {run.status}
                            </span>
                            {isActiveRun(run.status) && run.current_stage_key && (
                              <div className="mt-1 max-w-[180px] truncate text-xs text-slate-500" title={run.current_stage_key}>
                                {stageLabels[run.current_stage_key] || run.current_stage_key}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 text-slate-700">{isActiveRun(run.status) ? stageDuration(undefined, "started", run.started_at) : durationMs(run.started_at, run.completed_at)}</td>
                          <td className="px-4 py-3 text-slate-700">{run.triggered_by || "—"}</td>
                          <td className="max-w-[180px] truncate px-4 py-3 text-xs text-slate-600" title={run.schedule_key || ""}>
                            {run.schedule_key || "—"}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <button
                                type="button"
                                onClick={() => toggleExpand(run.run_id)}
                                aria-expanded={expandedRunId === run.run_id}
                                aria-controls={`pipeline-stages-${run.run_id}`}
                                className="text-sky-700 hover:underline"
                              >
                                {expandedRunId === run.run_id ? "Hide stages" : "Show stages"}
                              </button>
                              {run.status === "started" && (
                                <button
                                  type="button"
                                  onClick={() => void cancelRun(run.run_id)}
                                  disabled={cancellingRunId === run.run_id}
                                  className="inline-flex items-center gap-1 rounded-md border border-red-300 bg-red-50 px-2 py-1 text-xs text-red-800 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  <CircleStop className="h-4 w-4" aria-hidden="true" />
                                  {cancellingRunId === run.run_id ? "Cancelling…" : "Cancel"}
                                </button>
                              )}
                              {run.status === "cancel_requested" && (
                                <span className="text-xs text-orange-700">Cancel requested</span>
                              )}
                            </div>
                          </td>
                        </tr>
                        {expandedRunId === run.run_id && (
                          <tr id={`pipeline-stages-${run.run_id}`}>
                            <td colSpan={7} className="px-4 py-4">
                              {run.cancel_requested_at && (
                                <p className="recs-notice-orange mb-3">
                                  Cancel requested by {run.cancel_requested_by || "admin"} at{" "}
                                  {formatDate(run.cancel_requested_at)}.
                                </p>
                              )}
                              {run.notes && (
                                <p className="recs-notice-red mb-3">
                                  {run.notes}
                                </p>
                              )}
                              {run.semantic_labeling && (
                                <p className="mb-3 text-sm text-slate-600">
                                  Semantic dimension labeling: {run.semantic_labeling.status}. {run.semantic_labeling.reason}
                                </p>
                              )}
                              {run.publication_id && <p className="mb-3 break-all text-xs text-slate-600">Publication: {run.publication_id}</p>}
                              {run.stage_detail_note && <p className="mb-3 text-sm text-slate-600">{run.stage_detail_note}</p>}
                              {run.embedded_media && (
                                <details className="mb-4" open={run.embedded_media_total !== undefined && run.embedded_media_total <= 10}>
                                  <summary className="cursor-pointer text-sm text-slate-700">Titles embedded: {run.embedded_media_total}</summary>
                                  <p className="my-2 text-xs text-slate-500">{run.embedded_media_note}</p>
                                  <ul className="max-h-64 space-y-1 overflow-auto text-sm text-slate-800">
                                    {run.embedded_media.map(media => <li key={media.rating_key}>
                                      {media.show_title ? `${media.show_title} — ` : ""}{media.title || `Title ${media.rating_key}`}
                                      {media.media_type ? ` (${media.media_type})` : ""}
                                    </li>)}
                                  </ul>
                                </details>
                              )}
                              <div className="space-y-3">
                                {operatorStages(run.stages || [], run.stage_details).map((st) => (
                                  <PipelineStageCard key={st.stage_id} st={st} runId={run.run_id} activeRun={isActiveRun(run.status)} />
                                ))}
                              </div>

                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}
    </AppShell>
  );
}
