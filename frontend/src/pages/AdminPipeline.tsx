import { Fragment, useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

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
      return "bg-emerald-50 text-emerald-800 border-emerald-200";
    case "failed":
      return "bg-red-50 text-red-800 border-red-200";
    case "started":
      return "bg-amber-50 text-amber-900 border-amber-200";
    default:
      return "bg-slate-50 text-slate-700 border-slate-200";
  }
}

export default function AdminPipeline() {
  const navigate = useNavigate();
  const [me, setMe] = useState<AdminMe | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);

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
        const text = await response.text();
        throw new Error(text || `Trigger failed (${response.status})`);
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

  function toggleExpand(runId: number) {
    setExpandedRunId((prev) => (prev === runId ? null : runId));
  }

  return (
    <div className="min-h-screen bg-stone-100 text-slate-900">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6">
        <div className="flex flex-col gap-4 border-b border-stone-300 pb-5 md:flex-row md:items-start md:justify-between">
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-[0.28em] text-amber-700">Operations</p>
            <h1 className="text-3xl font-semibold tracking-tight">Pipeline runs</h1>
            <p className="max-w-2xl text-sm text-slate-600">
              Monitor nightly training pipeline executions, inspect per-stage logs, and start a manual run. Schedule
              and enable the in-app scheduler under Settings → Nightly pipeline.
            </p>
            <p className="text-sm text-slate-500">
              Signed in as {me?.display_name || me?.username || "…"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void triggerRun()}
              disabled={triggering || loading}
              className="inline-flex items-center rounded-md border border-slate-900 bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {triggering ? "Starting…" : "Run pipeline now"}
            </button>
            <button
              type="button"
              onClick={() => void loadRuns()}
              className="inline-flex items-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
            >
              Refresh
            </button>
            <Link
              to="/admin/settings"
              className="inline-flex items-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
            >
              Pipeline settings
            </Link>
            <Link
              to="/admin/digest"
              className="inline-flex items-center rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900 hover:bg-amber-100"
            >
              Digest Studio
            </Link>
            <Link
              to="/admin"
              className="inline-flex items-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
            >
              Admin View
            </Link>
          </div>
        </div>

        {error && (
          <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}
        {status && (
          <div className="rounded-md border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {status}
          </div>
        )}

        {loading ? (
          <div className="rounded-lg border border-stone-200 bg-white px-5 py-6 text-sm text-slate-500 shadow-sm">
            Loading runs…
          </div>
        ) : (
          <section className="rounded-lg border border-stone-200 bg-white shadow-sm">
            <div className="border-b border-stone-200 px-5 py-4">
              <h2 className="text-lg font-semibold text-slate-900">Recent runs</h2>
              <p className="text-sm text-slate-500">
                Scheduled runs appear when the in-app scheduler is enabled and a slot completes successfully once per
                schedule key. Failed scheduled runs retry until success.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-stone-200 text-sm">
                <thead className="bg-stone-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
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
                <tbody className="divide-y divide-stone-100">
                  {runs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                        No pipeline runs recorded yet.
                      </td>
                    </tr>
                  ) : (
                    runs.map((run) => (
                      <Fragment key={run.run_id}>
                        <tr className="hover:bg-stone-50">
                          <td className="whitespace-nowrap px-4 py-3 text-slate-800">{formatDate(run.started_at)}</td>
                          <td className="px-4 py-3 capitalize text-slate-700">{run.delivery_type}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${statusChip(run.status)}`}
                            >
                              {run.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-slate-700">{durationMs(run.started_at, run.completed_at)}</td>
                          <td className="px-4 py-3 text-slate-700">{run.triggered_by || "—"}</td>
                          <td className="max-w-[180px] truncate px-4 py-3 text-xs text-slate-600" title={run.schedule_key || ""}>
                            {run.schedule_key || "—"}
                          </td>
                          <td className="px-4 py-3">
                            <button
                              type="button"
                              onClick={() => toggleExpand(run.run_id)}
                              className="text-sky-700 hover:underline"
                            >
                              {expandedRunId === run.run_id ? "Hide stages" : "Show stages"}
                            </button>
                          </td>
                        </tr>
                        {expandedRunId === run.run_id && (
                          <tr className="bg-stone-50">
                            <td colSpan={7} className="px-4 py-4">
                              {run.notes && (
                                <p className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                                  {run.notes}
                                </p>
                              )}
                              <div className="space-y-4">
                                {(run.stages || []).map((st) => (
                                  <div key={st.stage_id} className="rounded-md border border-stone-200 bg-white p-3">
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
      </div>
    </div>
  );
}
