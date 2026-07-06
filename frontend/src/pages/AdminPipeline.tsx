import { Fragment, useCallback, useEffect, useState } from "react";
import { CircleStop } from "lucide-react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import { ErrorBanner, SuccessBanner } from "../components/StatusBanner";

interface AdminMe {
  username: string;
  friendly_name: string | null;
  display_name: string | null;
  is_admin: boolean;
}

interface PipelineStage {
  stage_id: number;
  run_id: number;
  stage_key: string;
  status: string;
  exit_code: number | null;
  stdout_tail: string | null;
  stderr_tail: string | null;
  started_at: string | null;
  completed_at: string | null;
}

interface PipelineRun {
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

function statusChip(status: string) {
  switch (status) {
    case "success":
      return "recs-status-emerald";
    case "failed":
      return "recs-status-red";
    case "cancelled":
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
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [cancellingRunId, setCancellingRunId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);
  const hasActiveRun = runs.some((run) => isActiveRun(run.status));

  const loadRuns = useCallback(async () => {
    const response = await fetch("/api/admin/pipeline/runs?limit=50", { credentials: "include" });
    if (!response.ok) {
      throw new Error(`Unable to load pipeline runs (${response.status})`);
    }
    const data = await response.json();
    setRuns(data.runs ?? []);
  }, []);

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
      setLoading(true);
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
        if (mounted) setLoading(false);
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
            disabled={triggering || loading}
            className="recs-btn-primary"
          >
            {triggering ? "Starting…" : "Run pipeline now"}
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
          <div className="border-b border-slate-100 bg-slate-50/80 px-5 py-4">
            <h2 className="text-lg font-semibold text-slate-900">Recent runs</h2>
            <p className="text-sm text-slate-500">
              Scheduled runs appear when the in-app scheduler is enabled and a slot completes successfully once per
              schedule key. Failed scheduled runs retry until success.
            </p>
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
                        <tr className="hover:bg-amber-50/30">
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
                                {run.current_stage_key}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 text-slate-700">{durationMs(run.started_at, run.completed_at)}</td>
                          <td className="px-4 py-3 text-slate-700">{run.triggered_by || "—"}</td>
                          <td className="max-w-[180px] truncate px-4 py-3 text-xs text-slate-600" title={run.schedule_key || ""}>
                            {run.schedule_key || "—"}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <button
                                type="button"
                                onClick={() => toggleExpand(run.run_id)}
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
                          <tr>
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
                              <div className="space-y-3">
                                {(run.stages || []).map((st) => (
                                  <div key={st.stage_id} className="recs-surface-muted p-3">
                                    <div className="flex flex-wrap items-center gap-2 text-sm">
                                      <span className="font-mono font-medium text-slate-900">{st.stage_key}</span>
                                      <span
                                        className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${statusChip(st.status)}`}
                                      >
                                        {st.status}
                                      </span>
                                      {st.exit_code !== null && st.exit_code !== undefined && (
                                        <span className="text-xs text-slate-500">exit {st.exit_code}</span>
                                      )}
                                      <span className="text-xs text-slate-500">
                                        {durationMs(st.started_at, st.completed_at)}
                                      </span>
                                    </div>
                                    {(st.stderr_tail || st.stdout_tail) && (
                                      <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-slate-900/90 p-3 text-xs text-slate-100">
                                        {st.stderr_tail ? `stderr:\n${st.stderr_tail}\n\n` : ""}
                                        {st.stdout_tail ? `stdout:\n${st.stdout_tail}` : ""}
                                      </pre>
                                    )}
                                  </div>
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
