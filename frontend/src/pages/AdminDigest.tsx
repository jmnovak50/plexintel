import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/AppShell";
import { ErrorBanner, SuccessBanner } from "../components/StatusBanner";

interface AdminMe {
  username: string;
  friendly_name: string | null;
  display_name: string | null;
  plex_email?: string | null;
  is_admin: boolean;
}

interface AdminUser {
  user_id: number;
  username: string;
  friendly_name: string | null;
  display_name: string | null;
  plex_email?: string | null;
  is_admin: boolean;
}

interface DigestContentResponse {
  message_html: string;
  updated_at: string | null;
  updated_by: string | null;
}

interface DigestPreviewResponse {
  subject: string;
  html: string;
  text: string;
  counts: {
    movies: number;
    shows: number;
  };
  rendered_for: {
    username: string;
    display_name: string;
  };
  recipient: {
    username: string;
    display_name: string;
    email: string | null;
  };
}

interface DigestRun {
  run_id: number;
  delivery_type: string;
  schedule_key: string | null;
  triggered_by: string | null;
  sample_username: string | null;
  subject: string | null;
  status: string;
  recipient_count: number;
  success_count: number;
  failure_count: number;
  notes: string | null;
  started_at: string | null;
  completed_at: string | null;
}

interface DigestDelivery {
  delivery_id: number;
  run_id: number;
  delivery_type: string;
  recipient_username: string | null;
  recipient_email: string;
  rendered_for_username: string | null;
  status: string;
  error_message: string | null;
  sent_at: string | null;
}

function formatDate(value: string | null) {
  if (!value) return "Never";
  return new Date(value).toLocaleString();
}

function choiceLabel(choice: string) {
  if (choice === "self") return "Send Test to Me";
  if (choice === "all_admins") return "Send Test to All Admins";
  return choice;
}

function runStatusClass(status: string) {
  switch (status) {
    case "completed":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "completed_with_failures":
      return "bg-amber-50 text-amber-700 border-amber-200";
    case "failed":
      return "bg-red-50 text-red-700 border-red-200";
    default:
      return "bg-slate-50 text-slate-700 border-slate-200";
  }
}

export default function AdminDigest() {
  const navigate = useNavigate();
  const editorRef = useRef<HTMLDivElement | null>(null);
  const previewFrameRef = useRef<HTMLIFrameElement | null>(null);
  const editorDraftRef = useRef("");
  const [me, setMe] = useState<AdminMe | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [sampleUsername, setSampleUsername] = useState("");
  const [editorSeedHtml, setEditorSeedHtml] = useState("");
  const [editorVersion, setEditorVersion] = useState(0);
  const [preview, setPreview] = useState<DigestPreviewResponse | null>(null);
  const [runs, setRuns] = useState<DigestRun[]>([]);
  const [deliveries, setDeliveries] = useState<DigestDelivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [testingTarget, setTestingTarget] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [contentMeta, setContentMeta] = useState<{ updated_at: string | null; updated_by: string | null }>({
    updated_at: null,
    updated_by: null,
  });

  const sampleOptions = useMemo(
    () => users.map((user) => ({ value: user.username, label: user.display_name || user.username })),
    [users]
  );

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
      setLoading(true);
      setError(null);
      try {
        const [meRes, usersRes, contentRes, historyRes] = await Promise.all([
          fetch("/api/admin/me", { credentials: "include" }),
          fetch("/api/admin/users", { credentials: "include" }),
          fetch("/api/admin/digest/content", { credentials: "include" }),
          fetch("/api/admin/digest/history", { credentials: "include" }),
        ]);

        if (!meRes.ok) {
          if (meRes.status === 401 || meRes.status === 403) {
            navigate("/", { replace: true });
            return;
          }
          throw new Error(`Unable to load admin identity (${meRes.status})`);
        }
        if (!usersRes.ok) throw new Error(`Unable to load users (${usersRes.status})`);
        if (!contentRes.ok) throw new Error(`Unable to load digest content (${contentRes.status})`);
        if (!historyRes.ok) throw new Error(`Unable to load digest history (${historyRes.status})`);

        const meData: AdminMe = await meRes.json();
        const usersData = await usersRes.json();
        const contentData: DigestContentResponse = await contentRes.json();
        const historyData = await historyRes.json();
        if (!mounted) return;

        if (!meData.is_admin) {
          navigate("/recs", { replace: true });
          return;
        }

        const nextUsers: AdminUser[] = usersData.users ?? [];
        const nextHtml = contentData.message_html || "";
        setMe(meData);
        setUsers(nextUsers);
        setSampleUsername(nextUsers[0]?.username || meData.username);
        editorDraftRef.current = nextHtml;
        setEditorSeedHtml(nextHtml);
        setEditorVersion((value) => value + 1);
        setContentMeta({
          updated_at: contentData.updated_at,
          updated_by: contentData.updated_by,
        });
        setRuns(historyData.runs ?? []);
        setDeliveries(historyData.deliveries ?? []);
      } catch (caught) {
        if (!mounted) return;
        setError(caught instanceof Error ? caught.message : "Failed to load digest studio.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    bootstrap();
    return () => {
      mounted = false;
    };
  }, [navigate]);

  useEffect(() => {
    if (!sampleUsername || loading) return;
    void refreshPreview(sampleUsername, editorDraftRef.current || editorSeedHtml);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sampleUsername, loading, editorSeedHtml]);

  useEffect(() => {
    normalizeEditorDirection();
  }, [editorVersion]);

  useEffect(() => {
    if (!preview?.html) return;
    const timers = [100, 350, 900].map((delay) => window.setTimeout(() => resizePreviewFrame(), delay));
    return () => {
      timers.forEach((timer) => window.clearTimeout(timer));
    };
  }, [preview?.html]);

  function normalizeEditorDirection() {
    const editor = editorRef.current;
    if (!editor) return;

    editor.setAttribute("dir", "ltr");
    editor.style.direction = "ltr";
    editor.style.unicodeBidi = "normal";
    editor.style.textAlign = "left";
    editor.style.writingMode = "horizontal-tb";

    editor.querySelectorAll<HTMLElement>("div, p, li, ul, ol, blockquote, span").forEach((node) => {
      node.setAttribute("dir", "ltr");
      node.style.direction = "ltr";
      node.style.unicodeBidi = "normal";
      node.style.textAlign = "left";
      node.style.writingMode = "horizontal-tb";
    });
  }

  function syncEditorHtml() {
    normalizeEditorDirection();
    const nextHtml = editorRef.current?.innerHTML ?? "";
    editorDraftRef.current = nextHtml;
    return nextHtml;
  }

  function resetEditorHtml(nextHtml: string) {
    editorDraftRef.current = nextHtml;
    setEditorSeedHtml(nextHtml);
    setEditorVersion((value) => value + 1);
  }

  function applyCommand(command: string, value?: string) {
    editorRef.current?.focus();
    document.execCommand(command, false, value);
    normalizeEditorDirection();
    syncEditorHtml();
  }

  function resizePreviewFrame() {
    const frame = previewFrameRef.current;
    const doc = frame?.contentDocument;
    if (!frame || !doc) return;
    const nextHeight = Math.max(
      doc.documentElement?.scrollHeight || 0,
      doc.body?.scrollHeight || 0,
      720
    );
    frame.style.height = `${nextHeight}px`;
  }

  async function loadHistory() {
    const response = await fetch("/api/admin/digest/history", { credentials: "include" });
    if (!response.ok) {
      throw new Error(`Unable to load digest history (${response.status})`);
    }
    const data = await response.json();
    setRuns(data.runs ?? []);
    setDeliveries(data.deliveries ?? []);
  }

  async function refreshPreview(nextSampleUsername = sampleUsername, nextHtml = editorDraftRef.current || editorSeedHtml) {
    if (!nextSampleUsername) return;
    setPreviewing(true);
    setError(null);
    try {
      const response = await fetch("/api/admin/digest/preview", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample_username: nextSampleUsername,
          message_html: nextHtml,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Failed generating preview (${response.status})`);
      }
      setPreview(data);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed generating preview.");
    } finally {
      setPreviewing(false);
    }
  }

  async function saveContent() {
    setSaving(true);
    setError(null);
    setStatus(null);
    const nextHtml = syncEditorHtml();
    try {
      const response = await fetch("/api/admin/digest/content", {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message_html: nextHtml }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Failed saving digest content (${response.status})`);
      }
      resetEditorHtml(data.message_html || "");
      setContentMeta({
        updated_at: data.updated_at,
        updated_by: data.updated_by,
      });
      setStatus("Digest content saved.");
      await refreshPreview(sampleUsername, data.message_html || "");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed saving digest content.");
    } finally {
      setSaving(false);
    }
  }

  async function sendTest(target: "self" | "all_admins") {
    setTestingTarget(target);
    setError(null);
    setStatus(null);
    const nextHtml = syncEditorHtml();
    try {
      const response = await fetch("/api/admin/digest/test-send", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target,
          sample_username: sampleUsername,
          message_html: nextHtml,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Failed sending test email (${response.status})`);
      }
      const skipped = Array.isArray(data.skipped_admins) && data.skipped_admins.length > 0
        ? ` Skipped admins without email: ${data.skipped_admins.join(", ")}.`
        : "";
      setStatus(`Test send complete. ${data.success_count} sent, ${data.failure_count} failed.${skipped}`);
      await loadHistory();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed sending test email.");
    } finally {
      setTestingTarget(null);
    }
  }

  if (loading) {
    return (
      <AppShell
        eyebrow="Digest Studio"
        title="Email digests"
        description="Loading digest studio…"
        signedInAs={me?.display_name || me?.username || null}
        maxWidthClass="max-w-6xl"
      >
        <div className="recs-surface-muted px-6 py-8 text-sm text-slate-500">
          Loading digest studio…
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell
      eyebrow="Digest Studio"
      title="Email digests"
      description="Edit the shared message, preview exactly what users will receive, and send test emails before the scheduled digest runs."
      signedInAs={me?.display_name || me?.username || "…"}
      maxWidthClass="max-w-6xl"
    >
      {error && <ErrorBanner message={error} />}
      {status && <SuccessBanner message={status} />}

      <div className="grid gap-5">
        <section className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr] lg:gap-6">
          <div className="recs-surface space-y-4 p-5">
            <div className="flex flex-col gap-2 border-b border-slate-100 pb-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-xl font-semibold">Shared message</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Formatting mirrors a simple newsletter editor. Images must use public URLs.
                </p>
              </div>
              <div className="text-xs text-slate-500">
                Updated {formatDate(contentMeta.updated_at)}
                {contentMeta.updated_by ? ` by ${contentMeta.updated_by}` : ""}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => applyCommand("bold")}
                className="recs-btn-secondary px-3 py-1.5 text-sm"
              >
                Bold
              </button>
              <button
                type="button"
                onClick={() => applyCommand("italic")}
                className="recs-btn-secondary px-3 py-1.5 text-sm"
              >
                Italic
              </button>
              <button
                type="button"
                onClick={() => applyCommand("strikeThrough")}
                className="recs-btn-secondary px-3 py-1.5 text-sm"
              >
                Strike
              </button>
              <button
                type="button"
                onClick={() => applyCommand("insertUnorderedList")}
                className="recs-btn-secondary px-3 py-1.5 text-sm"
              >
                Bullets
              </button>
              <button
                type="button"
                onClick={() => applyCommand("insertOrderedList")}
                className="recs-btn-secondary px-3 py-1.5 text-sm"
              >
                Numbers
              </button>
              <button
                type="button"
                onClick={() => {
                  const url = window.prompt("Enter a URL for the link");
                  if (url) applyCommand("createLink", url);
                }}
                className="recs-btn-secondary px-3 py-1.5 text-sm"
              >
                Link
              </button>
              <button
                type="button"
                onClick={() => {
                  const url = window.prompt("Enter a public image URL");
                  if (url) applyCommand("insertImage", url);
                }}
                className="recs-btn-secondary px-3 py-1.5 text-sm"
              >
                Image URL
              </button>
              <button
                type="button"
                onClick={() => applyCommand("removeFormat")}
                className="recs-btn-secondary px-3 py-1.5 text-sm"
              >
                Clear Format
              </button>
            </div>

            <div
              key={editorVersion}
              ref={editorRef}
              contentEditable
              dir="ltr"
              suppressContentEditableWarning
              onInput={() => {
                normalizeEditorDirection();
                syncEditorHtml();
              }}
              onFocus={() => normalizeEditorDirection()}
              dangerouslySetInnerHTML={{ __html: editorSeedHtml }}
              className="recs-editor"
              style={{ direction: "ltr", unicodeBidi: "normal", textAlign: "left", writingMode: "horizontal-tb" }}
            />

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void refreshPreview(sampleUsername, syncEditorHtml())}
                disabled={previewing}
                className="recs-btn-sky"
              >
                {previewing ? "Refreshing Preview…" : "Refresh Preview"}
              </button>
              <button
                type="button"
                onClick={() => void saveContent()}
                disabled={saving}
                className="recs-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? "Saving…" : "Save Message"}
              </button>
            </div>
          </div>

          <div className="recs-surface space-y-4 p-5">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-xl font-semibold">Preview and test</h2>
              <p className="mt-1 text-sm text-slate-500">
                Choose a sample user, then preview the exact digest layout or send a test email.
              </p>
              <p className="mt-2 text-sm text-slate-500">
                <span className="font-medium text-slate-700">Send Test to Me</span> uses the selected sample user.
                <span className="font-medium text-slate-700"> Send Test to All Admins</span> now renders each admin&apos;s
                own recommendation data, matching a scheduled run.
              </p>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-700">Sample user</label>
              <select
                value={sampleUsername}
                onChange={(event) => setSampleUsername(event.target.value)}
                className="recs-input"
              >
                {sampleOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-wrap gap-3">
              {(["self", "all_admins"] as const).map((target) => (
                <button
                  key={target}
                  type="button"
                  onClick={() => void sendTest(target)}
                  disabled={testingTarget !== null || !sampleUsername}
                  className="recs-btn-amber"
                >
                  {testingTarget === target ? "Sending…" : choiceLabel(target)}
                </button>
              ))}
            </div>

            <div className="recs-callout">
              SMTP server, port, username, password, encryption, From, and Reply-To are managed in
              <span className="font-medium"> Admin Settings </span>
              so the digest mailer matches Tautulli-style SMTP configuration. Gmail and Google Workspace usually
              need an App Password or relay setup rather than a normal account password. Poster images in sent
              digests are embedded as resized thumbnails so they render in email clients without blowing up the
              message size.
            </div>
          </div>
        </section>

        <section className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr] lg:gap-6">
          <div className="recs-surface p-5">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-xl font-semibold">Email preview</h2>
              <p className="text-sm text-slate-500">
                {preview
                  ? `${preview.subject} for ${preview.rendered_for.display_name} (${preview.counts.movies} movies, ${preview.counts.shows} shows)`
                  : "Preview not generated yet."}
              </p>
            </div>
            <div className="recs-surface-muted mt-5 p-4">
              {preview ? (
                <iframe
                  ref={previewFrameRef}
                  title="Digest email preview"
                  srcDoc={preview.html}
                  onLoad={() => resizePreviewFrame()}
                  className="mx-auto block w-full max-w-3xl rounded-md border-0 bg-white"
                  style={{ minHeight: "720px" }}
                />
              ) : (
                <p className="text-sm text-slate-500">Choose a sample user and refresh the preview.</p>
              )}
            </div>
          </div>

          <div className="recs-surface p-5">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-xl font-semibold">Plain text</h2>
              <p className="mt-1 text-sm text-slate-500">Fallback body for email clients that do not render HTML.</p>
            </div>
            <pre className="recs-pre mt-4 max-h-[520px]">
              {preview?.text || "Preview not generated yet."}
            </pre>
          </div>
        </section>

        <section className="grid gap-5 lg:grid-cols-2 lg:gap-6">
          <div className="recs-surface p-5">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-xl font-semibold">Recent runs</h2>
              <p className="mt-1 text-sm text-slate-500">Recent scheduled and test sends.</p>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="border-b border-slate-200 text-left text-slate-500">
                  <tr>
                    <th className="px-2 py-2">Type</th>
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Recipients</th>
                    <th className="px-2 py-2">Started</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.run_id} className="border-b border-slate-100 align-top">
                      <td className="px-2 py-3">
                        <div className="font-medium text-slate-800">{run.delivery_type}</div>
                        <div className="text-xs text-slate-500">{run.subject || "No subject"}</div>
                      </td>
                      <td className="px-2 py-3">
                        <span className={`inline-flex rounded-md border px-2 py-1 text-xs ${runStatusClass(run.status)}`}>
                          {run.status}
                        </span>
                        {run.notes && <div className="mt-2 text-xs text-slate-500">{run.notes}</div>}
                      </td>
                      <td className="px-2 py-3">
                        <div>{run.success_count} sent</div>
                        <div className="text-xs text-slate-500">{run.failure_count} failed / {run.recipient_count} total</div>
                      </td>
                      <td className="px-2 py-3 text-xs text-slate-500">{formatDate(run.started_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {runs.length === 0 && <p className="px-2 py-4 text-sm text-slate-500">No digest runs yet.</p>}
            </div>
          </div>

          <div className="recs-surface p-5">
            <div className="border-b border-slate-100 pb-4">
              <h2 className="text-xl font-semibold">Recent deliveries</h2>
              <p className="mt-1 text-sm text-slate-500">Latest recipient-level results.</p>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="border-b border-slate-200 text-left text-slate-500">
                  <tr>
                    <th className="px-2 py-2">Recipient</th>
                    <th className="px-2 py-2">Rendered For</th>
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Sent</th>
                  </tr>
                </thead>
                <tbody>
                  {deliveries.map((delivery) => (
                    <tr key={delivery.delivery_id} className="border-b border-slate-100 align-top">
                      <td className="px-2 py-3">
                        <div className="font-medium text-slate-800">{delivery.recipient_username || delivery.recipient_email}</div>
                        <div className="text-xs text-slate-500">{delivery.recipient_email}</div>
                      </td>
                      <td className="px-2 py-3 text-xs text-slate-500">{delivery.rendered_for_username || "—"}</td>
                      <td className="px-2 py-3">
                        <span className={`inline-flex rounded-md border px-2 py-1 text-xs ${runStatusClass(delivery.status)}`}>
                          {delivery.status}
                        </span>
                        {delivery.error_message && (
                          <div className="mt-2 text-xs text-red-600">{delivery.error_message}</div>
                        )}
                      </td>
                      <td className="px-2 py-3 text-xs text-slate-500">{formatDate(delivery.sent_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {deliveries.length === 0 && <p className="px-2 py-4 text-sm text-slate-500">No delivery history yet.</p>}
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
