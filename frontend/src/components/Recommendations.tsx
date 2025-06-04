// Fully restored Recommendations.tsx with feedback logic + working sort
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface Recommendation {
  friendly_name: string;
  media_type: string;
  rating_key: number;
  title: string;
  show_title: string | null;
  year: number;
  predicted_probability: number;
  genres: string;
  semantic_themes: string;
  season_number: number | null;
  episode_number: number | null;
}

interface FeedbackReason {
  code: string;
  label: string;
}

export default function Recommendations() {
  const [search, setSearch] = useState('');
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [darkMode, setDarkMode] = useState(false);
  const [mediaTypeFilter, setMediaTypeFilter] = useState('');
  const [minScore, setMinScore] = useState(0);
  const [plexUser, setPlexUser] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [feedbackOpenKey, setFeedbackOpenKey] = useState<number | null>(null);
  const [feedbackType, setFeedbackType] = useState<'up' | 'down' | null>(null);
  const [feedbackSubmittedKeys, setFeedbackSubmittedKeys] = useState<number[]>([]);
  const [feedbackOptions, setFeedbackOptions] = useState<{ up: FeedbackReason[]; down: FeedbackReason[] }>({
  up: [],
  down: [],
});
  const feedbackList = feedbackType === 'up'
    ? feedbackOptions.up
    : feedbackType === 'down'
      ? feedbackOptions.down
      : [];
  const [sortOrder, setSortOrder] = useState<Array<{ column: keyof Recommendation; direction: 'asc' | 'desc' }>>([]);

  useEffect(() => {
    const baseUrl = window.location.origin;
    fetch(`${baseUrl}/api/recommendations`, {
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
        if (data.feedback_options) {
          setFeedbackOptions(data.feedback_options);
        }
      });
  }, []);

  const sendFeedback = (rating_key: number, feedback: 'up' | 'down', reason_code: string) => {
    const payload = { username: plexUser, rating_key, feedback, reason_code };
    fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(() => {
      setFeedbackSubmittedKeys((prev) => [...prev, rating_key]);
      setTimeout(() => {
        setFeedbackOpenKey(null);
        setFeedbackType(null);
      }, 300);
    });
  };

  const undoFeedback = (rating_key: number) => {
    setFeedbackSubmittedKeys((prev) => prev.filter((key) => key !== rating_key));
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

  const filteredRecs = [...recs]
    .filter((rec) => {
      const score = rec.predicted_probability * 100;
      const searchLower = search.toLowerCase();
      return (
        (!mediaTypeFilter || rec.media_type === mediaTypeFilter) &&
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
        <label className="flex items-center space-x-2 text-sm">
          <input type="checkbox" checked={darkMode} onChange={() => setDarkMode(!darkMode)} />
          <span>Dark Mode</span>
        </label>
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
          value={mediaTypeFilter}
          onChange={(e) => setMediaTypeFilter(e.target.value)}
          className="w-full p-2 border border-gray-300 rounded-md shadow-sm"
        >
          <option value="">All Types</option>
          <option value="movie">Movie</option>
          <option value="show">Show</option>
          <option value="episode">Episode</option>
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

      <div className="overflow-x-auto">
        <table className="min-w-full bg-white shadow rounded-xl border border-gray-200">
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
                className={`group border-b hover:bg-gray-100 transition-colors duration-300 ${feedbackSubmittedKeys.includes(rec.rating_key) ? 'bg-green-50' : ''}`}
              >
                <td className="px-4 py-2">{rec.media_type}</td>
                <td className="px-4 py-2">{rec.title}</td>
                <td className="px-4 py-2">{rec.show_title || '—'}</td>
                <td className="px-4 py-2">{rec.season_number ?? '—'}</td>
                <td className="px-4 py-2">{rec.episode_number ?? '—'}</td>
                <td className="px-4 py-2">{rec.year}</td>
                <td className="px-4 py-2">{rec.genres || '—'}</td>
                <td className="px-4 py-2">
                  {rec.semantic_themes?.split(',').map((tag, i) => (
                    <span key={i} className="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full mr-1">
                      {tag.trim()}
                    </span>
                  ))}
                </td>
                <td className="px-4 py-2 relative">
                  <div className="flex flex-col">
                    <span className="text-sm mb-1">{(rec.predicted_probability * 100).toFixed(1)}%</span>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${(rec.predicted_probability * 100).toFixed(0)}%` }}></div>
                    </div>
                    {feedbackSubmittedKeys.includes(rec.rating_key) ? (
                      <div className="text-green-600 text-xs mt-2 flex items-center gap-2">
                        ✅ Feedback received
                        <button
                          onClick={() => undoFeedback(rec.rating_key)}
                          className="text-blue-600 underline text-xs hover:text-blue-800"
                        >Undo</button>
                      </div>
                    ) : (
                      <div className="flex gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => { setFeedbackOpenKey(rec.rating_key); setFeedbackType('up'); }}>👍</button>
                        <button onClick={() => { setFeedbackOpenKey(rec.rating_key); setFeedbackType('down'); }}>👎</button>
                      </div>
                    )}
                    <AnimatePresence>
                      {feedbackOpenKey === rec.rating_key && !feedbackSubmittedKeys.includes(rec.rating_key) && (
                        <motion.div
                          initial={{ opacity: 0, y: -5 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -5 }}
                          className="mt-2 text-xs bg-gray-100 p-2 rounded shadow"
                        >
                        {feedbackList.map(({ code, label }: FeedbackReason) => (
                          <button
                            key={code}
                            onClick={() => sendFeedback(rec.rating_key, feedbackType!, code)}
                            className="bg-gray-200 px-2 py-1 mr-1 mb-1 rounded hover:bg-blue-600 hover:text-white"
                          >
                            {label}
                          </button>
                        ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
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
