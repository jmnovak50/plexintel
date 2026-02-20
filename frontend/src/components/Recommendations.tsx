// Fully restored Recommendations.tsx with feedback logic + working sort
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

interface Recommendation {
  friendly_name: string;
  media_type: string;
  rating_key: number;
  title: string;
  show_title: string | null;
  year: number | null;
  predicted_probability: number;
  genres: string | null;
  semantic_themes: string | null;
  season_number: number | null;
  episode_number: number | null;
  show_rating_key?: number | null;
  parent_rating_key?: number | null;
  score_band?: string | null;
}

export default function Recommendations() {
  const [search, setSearch] = useState('');
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [darkMode, setDarkMode] = useState(false);
  const [viewMode, setViewMode] = useState<'all' | 'movies' | 'shows' | 'seasons' | 'episodes'>('all');
  const [selectedShow, setSelectedShow] = useState<{ key: number; title: string } | null>(null);
  const [selectedSeason, setSelectedSeason] = useState<{ key: number; title: string } | null>(null);
  const [minScore, setMinScore] = useState(0);
  const [plexUser, setPlexUser] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [feedbackSubmittedKeys, setFeedbackSubmittedKeys] = useState<number[]>([]);
  const [feedbackPendingKeys, setFeedbackPendingKeys] = useState<number[]>([]);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<Array<{ column: keyof Recommendation; direction: 'asc' | 'desc' }>>([]);

  useEffect(() => {
    const baseUrl = window.location.origin;
    const params = new URLSearchParams({ view: viewMode });
    if (selectedShow?.key && (viewMode === 'seasons' || viewMode === 'episodes')) {
      params.set('show_rating_key', String(selectedShow.key));
    }
    if (selectedSeason?.key && viewMode === 'episodes') {
      params.set('season_rating_key', String(selectedSeason.key));
    }

    fetch(`${baseUrl}/api/recommendations?${params.toString()}`, {
      credentials: 'include'
    })
      .then((res) => res.json())
      .then((data) => {
        setRecs(data.recommendations);
        setPlexUser(data.username);
        setLastUpdated(data.last_updated);
        if (data.feedback_keys) {
          setFeedbackSubmittedKeys(data.feedback_keys);
        }
      });
  }, [viewMode, selectedShow, selectedSeason]);

  useEffect(() => {
    let mounted = true;

    fetch('/api/admin/me', { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!mounted) return;
        setIsAdmin(Boolean(data?.is_admin));
      })
      .catch(() => {
        if (!mounted) return;
        setIsAdmin(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const sendFeedback = async (ratingKey: number, feedback: 'up' | 'down') => {
    if (!plexUser) {
      setFeedbackError('Unable to submit feedback: user session is missing.');
      return;
    }
    if (feedbackPendingKeys.includes(ratingKey)) {
      return;
    }

    const payload = { username: plexUser, rating_key: ratingKey, feedback };
    setFeedbackError(null);
    setFeedbackPendingKeys((prev) => (prev.includes(ratingKey) ? prev : [...prev, ratingKey]));
    setFeedbackSubmittedKeys((prev) => (prev.includes(ratingKey) ? prev : [...prev, ratingKey]));

    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        let reason = `Failed to submit feedback (${res.status})`;
        try {
          const data = await res.json();
          if (typeof data?.detail === 'string' && data.detail.trim()) {
            reason = data.detail;
          }
        } catch {
          // Ignore body parse errors and keep status-based fallback.
        }
        throw new Error(reason);
      }
    } catch (error) {
      console.error(error);
      // Roll back optimistic hide if the write failed.
      setFeedbackSubmittedKeys((prev) => prev.filter((key) => key !== ratingKey));
      setFeedbackError(error instanceof Error ? error.message : 'Failed to submit feedback.');
    } finally {
      setFeedbackPendingKeys((prev) => prev.filter((key) => key !== ratingKey));
    }
  };

  const handleSort = (column: keyof Recommendation, shiftKey = false) => {
    setSortOrder((prev) => {
      const existing = prev.find((s) => s?.column === column);

      if (existing) {
        return prev.map((s) =>
          s.column === column
            ? { ...s, direction: s.direction === 'asc' ? 'desc' : 'asc' }
            : s
        );
      } else {
        const newSort = { column, direction: 'asc' as const };
        return shiftKey ? [...prev, newSort] : [newSort];
      }
    });
  };

  const handleViewSelect = (nextView: 'all' | 'movies' | 'shows' | 'seasons' | 'episodes') => {
    setViewMode(nextView);
    setSelectedShow(null);
    setSelectedSeason(null);
  };

  const handleRowClick = (rec: Recommendation) => {
    if (viewMode === 'shows') {
      const showKey = rec.show_rating_key ?? rec.rating_key;
      if (!showKey) return;
      setSelectedShow({ key: showKey, title: rec.title });
      setSelectedSeason(null);
      setViewMode('seasons');
    } else if (viewMode === 'seasons') {
      const showKey = rec.show_rating_key;
      if (showKey && !selectedShow) {
        setSelectedShow({ key: showKey, title: rec.show_title || 'Show' });
      }
      setSelectedSeason({ key: rec.rating_key, title: rec.title });
      setViewMode('episodes');
    }
  };

  const filteredRecs = [...recs]
    .filter((rec) => {
      const score = rec.predicted_probability * 100;
      const searchLower = search.toLowerCase();
      return (
        score >= minScore &&
        (
          rec.title?.toLowerCase().includes(searchLower) ||
          rec.show_title?.toLowerCase().includes(searchLower) ||
          rec.genres?.toLowerCase().includes(searchLower) ||
          rec.semantic_themes?.toLowerCase().includes(searchLower)
        )
      );
    })
    .sort((a, b) => {
      for (const { column, direction } of sortOrder) {
        const aVal = a[column];
        const bVal = b[column];
        if (aVal == null || bVal == null) continue;

        if (typeof aVal === 'string' && typeof bVal === 'string') {
          const result = aVal.localeCompare(bVal);
          if (result !== 0) return direction === 'asc' ? result : -result;
        } else if (typeof aVal === 'number' && typeof bVal === 'number') {
          const result = aVal - bVal;
          if (result !== 0) return direction === 'asc' ? result : -result;
        }
      }
      return 0;
    });

  return (
    <div className={`p-4 max-w-7xl mx-auto ${darkMode ? 'bg-gray-900 text-white' : 'bg-white text-black'}`}>
      <h1 className="text-3xl font-bold mb-2">🎬 Recommendations for {recs[0]?.friendly_name || plexUser || 'user'}</h1>

      <div className="mb-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          {isAdmin && (
            <Link
              to="/admin"
              className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100"
            >
              Admin View
            </Link>
          )}
          <label className="flex items-center space-x-2 text-sm">
            <input type="checkbox" checked={darkMode} onChange={() => setDarkMode(!darkMode)} />
            <span>Dark Mode</span>
          </label>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <input
          type="text"
          placeholder="Search by title, show, genre, or theme..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
        />

        <select
          value={viewMode}
          onChange={(e) => handleViewSelect(e.target.value as 'all' | 'movies' | 'shows' | 'seasons' | 'episodes')}
          className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
        >
          <option value="all">All</option>
          <option value="movies">Movies</option>
          <option value="shows">Shows</option>
          <option value="seasons">Seasons</option>
          <option value="episodes">Episodes</option>
        </select>

        <div className="col-span-1 sm:col-span-2">
          <label htmlFor="score-range" className="block text-sm font-medium text-gray-700 mb-1">
            Minimum Score: {minScore}%
          </label>
          <input
            id="score-range"
            type="range"
            min="0"
            max="100"
            step="1"
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            className="w-full"
          />
        </div>
      </div>

      {feedbackError && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          Feedback error: {feedbackError}
        </div>
      )}

      {(viewMode === 'seasons' || viewMode === 'episodes') && selectedShow && (
        <div className="mb-4 flex items-center gap-2 text-sm text-gray-600">
          <button
            onClick={() => {
              setSelectedSeason(null);
              setViewMode('shows');
            }}
            className="text-blue-600 underline hover:text-blue-800"
          >
            Back to Shows
          </button>
          <span>Show: {selectedShow.title}</span>
          {viewMode === 'episodes' && selectedSeason && (
            <>
              <span>•</span>
              <button
                onClick={() => {
                  setSelectedSeason(null);
                  setViewMode('seasons');
                }}
                className="text-blue-600 underline hover:text-blue-800"
              >
                Back to Seasons
              </button>
              <span>Season: {selectedSeason.title}</span>
            </>
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full bg-white text-gray-900 shadow rounded-xl border border-gray-200">
          <thead>
            <tr className="text-left text-gray-600 text-sm border-b bg-gray-100">
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Show</th>
              <th className="px-4 py-3 cursor-pointer" onClick={() => handleSort('season_number')}>Season</th>
              <th className="px-4 py-3 cursor-pointer" onClick={() => handleSort('episode_number')}>Episode</th>
              <th className="px-4 py-3">Year</th>
              <th className="px-4 py-3">Genres</th>
              <th className="px-4 py-3">Why this?</th>
              <th className="px-4 py-3">Score</th>
            </tr>
          </thead>
          <tbody>
            {filteredRecs.map((rec) => (
              <tr
                key={rec.rating_key}
                onClick={() => handleRowClick(rec)}
                className={`group border-b transition-colors duration-300 ${feedbackSubmittedKeys.includes(rec.rating_key) ? 'bg-green-50' : 'hover:bg-gray-100'} ${viewMode === 'shows' || viewMode === 'seasons' ? 'cursor-pointer' : ''}`}
              >
                <td className="px-4 py-2">{rec.media_type}</td>
                <td className="px-4 py-2">{rec.title}</td>
                <td className="px-4 py-2">{rec.show_title || '—'}</td>
                <td className="px-4 py-2">{rec.season_number ?? '—'}</td>
                <td className="px-4 py-2">{rec.episode_number ?? '—'}</td>
                <td className="px-4 py-2">{rec.year}</td>
                <td className="px-4 py-2">{rec.genres || '—'}</td>
                <td className="px-4 py-2">
                  {rec.semantic_themes
                    ? rec.semantic_themes.split(',').map((tag, i) => (
                      <span key={i} className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full mr-1">
                        {tag.trim()}
                      </span>
                    ))
                    : null}
                </td>
                <td className="px-4 py-2 relative">
                  <div className="flex flex-col">
                    <span className="text-sm mb-1">{(rec.predicted_probability * 100).toFixed(1)}%</span>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${(rec.predicted_probability * 100).toFixed(0)}%` }}></div>
                    </div>
                    {rec.score_band && (
                      <span className="text-xs text-gray-500 mt-2">Band: {rec.score_band}</span>
                    )}
                    {feedbackPendingKeys.includes(rec.rating_key) && (
                      <span className="text-xs text-gray-500 mt-2">Submitting feedback...</span>
                    )}
                    {feedbackSubmittedKeys.includes(rec.rating_key) && (
                      <span className="text-xs font-medium text-green-700 mt-2">Feedback submitted</span>
                    )}
                    {(rec.media_type === 'movie' || rec.media_type === 'episode') && !feedbackSubmittedKeys.includes(rec.rating_key) ? (
                      <div className="mt-2 flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                        <button
                          type="button"
                          aria-label={`Give thumbs up feedback for ${rec.title}`}
                          title="Thumbs up"
                          disabled={feedbackPendingKeys.includes(rec.rating_key)}
                          onClick={(event) => {
                            event.preventDefault();
                            event.stopPropagation();
                            sendFeedback(rec.rating_key, 'up');
                          }}
                          className="inline-flex items-center justify-center text-base leading-none transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-500 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          👍
                        </button>
                        <button
                          type="button"
                          aria-label={`Give thumbs down feedback for ${rec.title}`}
                          title="Thumbs down"
                          disabled={feedbackPendingKeys.includes(rec.rating_key)}
                          onClick={(event) => {
                            event.preventDefault();
                            event.stopPropagation();
                            sendFeedback(rec.rating_key, 'down');
                          }}
                          className="inline-flex items-center justify-center text-base leading-none transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          👎
                        </button>
                      </div>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {lastUpdated && (
        <div className="mt-4 text-sm text-gray-500 text-right">
          Last updated: {new Date(lastUpdated).toLocaleString()}
        </div>
      )}
    </div>
  );
}
