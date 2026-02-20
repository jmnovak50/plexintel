import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

interface AdminMe {
  username: string;
  is_admin: boolean;
  created_at: string | null;
  last_login: string | null;
}

interface AdminUser {
  username: string;
  is_admin: boolean;
  created_at: string | null;
  last_login: string | null;
  recommendation_count: number;
  feedback_count: number;
}

interface AdminRecommendation {
  rating_key: number;
  title: string;
  media_type: string;
  show_title: string | null;
  year: number | null;
  predicted_probability: number;
  score_band: string | null;
}

interface AdminFeedbackItem {
  id: number;
  rating_key: number;
  feedback: "up" | "down";
  reason_code: string | null;
  reason_label: string | null;
  suppress: boolean;
  created_at: string;
  media_type: string | null;
  title: string | null;
  show_title: string | null;
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export default function Admin() {
  const navigate = useNavigate();
  const [me, setMe] = useState<AdminMe | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [selectedUser, setSelectedUser] = useState("");
  const [viewMode, setViewMode] = useState<"all" | "movies" | "shows" | "seasons" | "episodes">("all");
  const [recommendations, setRecommendations] = useState<AdminRecommendation[]>([]);
  const [feedbackRows, setFeedbackRows] = useState<AdminFeedbackItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
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
        setMe(meData);

        if (!meData.is_admin) {
          navigate("/recs", { replace: true });
          return;
        }

        const usersRes = await fetch("/api/admin/users", { credentials: "include" });
        if (!usersRes.ok) {
          throw new Error(`Unable to load user list (${usersRes.status})`);
        }
        const usersData = await usersRes.json();
        const nextUsers: AdminUser[] = usersData.users ?? [];
        if (!mounted) return;
        setUsers(nextUsers);
        if (nextUsers.length > 0) {
          setSelectedUser((prev) => prev || nextUsers[0].username);
        }
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load admin view.");
      }
    }

    bootstrap();
    return () => {
      mounted = false;
    };
  }, [navigate]);

  useEffect(() => {
    let mounted = true;

    async function loadPersonaData() {
      if (!me?.is_admin || !selectedUser) return;

      setLoading(true);
      setError(null);
      try {
        const recParams = new URLSearchParams({
          target_username: selectedUser,
          view: viewMode,
        });

        const [recsRes, feedbackRes] = await Promise.all([
          fetch(`/api/admin/recommendations?${recParams.toString()}`, {
            credentials: "include",
          }),
          fetch(
            `/api/admin/feedback?${new URLSearchParams({
              target_username: selectedUser,
              limit: "200",
            }).toString()}`,
            { credentials: "include" }
          ),
        ]);

        if (!recsRes.ok) {
          throw new Error(`Failed loading recommendations (${recsRes.status})`);
        }
        if (!feedbackRes.ok) {
          throw new Error(`Failed loading feedback history (${feedbackRes.status})`);
        }

        const recData = await recsRes.json();
        const feedbackData = await feedbackRes.json();
        if (!mounted) return;
        setRecommendations(recData.recommendations ?? []);
        setFeedbackRows(feedbackData.feedback ?? []);
      } catch (e) {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : "Failed to load persona data.");
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadPersonaData();
    return () => {
      mounted = false;
    };
  }, [me?.is_admin, selectedUser, viewMode]);

  const selectedUserMeta = useMemo(
    () => users.find((u) => u.username === selectedUser) || null,
    [users, selectedUser]
  );

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Admin Persona View</h1>
          <p className="text-sm text-gray-600">
            Signed in as {me?.username || "…"}
          </p>
        </div>
        <Link
          to="/recs"
          className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-100"
        >
          Back to Recommendations
        </Link>
      </div>

      {error && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {me?.is_admin ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Persona User
              </label>
              <select
                value={selectedUser}
                onChange={(e) => setSelectedUser(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                {users.map((u) => (
                  <option key={u.username} value={u.username}>
                    {u.username}{u.is_admin ? " (admin)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Recommendation View
              </label>
              <select
                value={viewMode}
                onChange={(e) => setViewMode(e.target.value as "all" | "movies" | "shows" | "seasons" | "episodes")}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              >
                <option value="all">All</option>
                <option value="movies">Movies</option>
                <option value="shows">Shows</option>
                <option value="seasons">Seasons</option>
                <option value="episodes">Episodes</option>
              </select>
            </div>
            <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm">
              <div>Last login: {formatDate(selectedUserMeta?.last_login ?? null)}</div>
              <div>Created: {formatDate(selectedUserMeta?.created_at ?? null)}</div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            <div className="rounded-md border border-gray-200 bg-white px-3 py-2">
              <p className="text-xs text-gray-500">Total recommendations</p>
              <p className="text-xl font-semibold">{recommendations.length}</p>
            </div>
            <div className="rounded-md border border-gray-200 bg-white px-3 py-2">
              <p className="text-xs text-gray-500">Feedback events</p>
              <p className="text-xl font-semibold">{feedbackRows.length}</p>
            </div>
            <div className="rounded-md border border-gray-200 bg-white px-3 py-2">
              <p className="text-xs text-gray-500">DB recommendation rows</p>
              <p className="text-xl font-semibold">{selectedUserMeta?.recommendation_count ?? 0}</p>
            </div>
            <div className="rounded-md border border-gray-200 bg-white px-3 py-2">
              <p className="text-xs text-gray-500">DB feedback rows</p>
              <p className="text-xl font-semibold">{selectedUserMeta?.feedback_count ?? 0}</p>
            </div>
          </div>

          {loading && <p className="text-sm text-gray-500">Loading persona data…</p>}

          <div className="rounded-xl border border-gray-200 bg-white shadow">
            <div className="border-b px-4 py-3">
              <h2 className="text-lg font-semibold">Recommendations</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="px-3 py-2 text-left">Type</th>
                    <th className="px-3 py-2 text-left">Title</th>
                    <th className="px-3 py-2 text-left">Show</th>
                    <th className="px-3 py-2 text-left">Year</th>
                    <th className="px-3 py-2 text-left">Score</th>
                    <th className="px-3 py-2 text-left">Band</th>
                  </tr>
                </thead>
                <tbody>
                  {recommendations.map((rec) => (
                    <tr key={rec.rating_key} className="border-t">
                      <td className="px-3 py-2">{rec.media_type}</td>
                      <td className="px-3 py-2">{rec.title}</td>
                      <td className="px-3 py-2">{rec.show_title || "—"}</td>
                      <td className="px-3 py-2">{rec.year ?? "—"}</td>
                      <td className="px-3 py-2">{(rec.predicted_probability * 100).toFixed(1)}%</td>
                      <td className="px-3 py-2">{rec.score_band || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-xl border border-gray-200 bg-white shadow">
            <div className="border-b px-4 py-3">
              <h2 className="text-lg font-semibold">Feedback History</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="px-3 py-2 text-left">When</th>
                    <th className="px-3 py-2 text-left">Thumb</th>
                    <th className="px-3 py-2 text-left">Title</th>
                    <th className="px-3 py-2 text-left">Type</th>
                    <th className="px-3 py-2 text-left">Reason</th>
                    <th className="px-3 py-2 text-left">Suppress</th>
                  </tr>
                </thead>
                <tbody>
                  {feedbackRows.map((row) => (
                    <tr key={row.id} className="border-t">
                      <td className="px-3 py-2">{formatDate(row.created_at)}</td>
                      <td className="px-3 py-2">{row.feedback === "up" ? "👍" : "👎"}</td>
                      <td className="px-3 py-2">{row.title || `rating_key ${row.rating_key}`}</td>
                      <td className="px-3 py-2">{row.media_type || "—"}</td>
                      <td className="px-3 py-2">{row.reason_label || row.reason_code || "—"}</td>
                      <td className="px-3 py-2">{row.suppress ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : (
        !error && <p className="text-sm text-gray-500">Checking admin access…</p>
      )}
    </div>
  );
}
