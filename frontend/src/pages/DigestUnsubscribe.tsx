import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

interface UnsubscribePayload {
  username: string;
  display_name: string;
  email: string | null;
  digest_enabled: boolean;
}

export default function DigestUnsubscribe() {
  const { token } = useParams();
  const [payload, setPayload] = useState<UnsubscribePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadDetails() {
      if (!token) {
        setError("Missing unsubscribe token.");
        setLoading(false);
        return;
      }

      try {
        const response = await fetch(`/api/digest/unsubscribe/${encodeURIComponent(token)}`);
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || `Unable to load unsubscribe link (${response.status})`);
        }
        if (!mounted) return;
        setPayload(data);
      } catch (caught) {
        if (!mounted) return;
        setError(caught instanceof Error ? caught.message : "Unable to load unsubscribe link.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    void loadDetails();
    return () => {
      mounted = false;
    };
  }, [token]);

  async function unsubscribe() {
    if (!token) return;
    setSubmitting(true);
    setError(null);
    setStatus(null);
    try {
      const response = await fetch(`/api/digest/unsubscribe/${encodeURIComponent(token)}`, {
        method: "POST",
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Unable to unsubscribe (${response.status})`);
      }
      setPayload(data);
      setStatus("You have been unsubscribed from PlexIntel recommendation emails.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to unsubscribe.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-stone-100 px-4 py-12 text-slate-900">
      <div className="mx-auto max-w-xl space-y-5 rounded-lg border border-stone-200 bg-white p-6 shadow-sm">
        <div className="space-y-2 border-b border-stone-200 pb-4">
          <p className="text-xs uppercase tracking-[0.28em] text-amber-700">Email Preferences</p>
          <h1 className="text-3xl font-semibold tracking-tight">Unsubscribe</h1>
          <p className="text-sm text-slate-600">
            Use this page to stop receiving scheduled PlexIntel recommendation emails.
          </p>
        </div>

        {loading && <p className="text-sm text-slate-500">Loading unsubscribe link…</p>}
        {error && (
          <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {status && (
          <div className="rounded-md border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {status}
          </div>
        )}

        {!loading && payload && (
          <div className="space-y-4">
            <div className="rounded-md border border-stone-200 bg-stone-50 px-4 py-4 text-sm text-slate-700">
              <p>
                <span className="font-medium text-slate-900">User:</span> {payload.display_name}
              </p>
              <p className="mt-1">
                <span className="font-medium text-slate-900">Email:</span> {payload.email || "Unavailable"}
              </p>
              <p className="mt-1">
                <span className="font-medium text-slate-900">Current status:</span>{" "}
                {payload.digest_enabled ? "Subscribed" : "Already unsubscribed"}
              </p>
            </div>

            <button
              type="button"
              onClick={() => void unsubscribe()}
              disabled={submitting || !payload.digest_enabled}
              className="inline-flex items-center rounded-md border border-red-300 bg-red-50 px-4 py-2 text-sm text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Unsubscribing…" : payload.digest_enabled ? "Unsubscribe from emails" : "Already unsubscribed"}
            </button>

            <div className="pt-2 text-sm text-slate-500">
              <Link to="/" className="text-sky-700 underline hover:text-sky-800">
                Return to PlexIntel
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
