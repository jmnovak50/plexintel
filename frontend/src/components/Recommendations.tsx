// src/components/Recommendations.tsx
import { useEffect, useState } from 'react';

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

export default function Recommendations() {
  const [search, setSearch] = useState('');
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [themeFilter, setThemeFilter] = useState('');
  const [darkMode, setDarkMode] = useState(false);
  const [mediaTypeFilter, setMediaTypeFilter] = useState('');
  const [minScore, setMinScore] = useState(0);

  const filteredRecs = recs.filter((rec) => {
    const score = rec.predicted_probability * 100;
    const searchLower = search.toLowerCase();
  
    return (
      (!mediaTypeFilter || rec.media_type === mediaTypeFilter) &&
      (!themeFilter || rec.semantic_themes?.toLowerCase().includes(themeFilter.toLowerCase())) &&
      score >= minScore &&
      (
        rec.title?.toLowerCase().includes(searchLower) ||
        rec.show_title?.toLowerCase().includes(searchLower) ||
        rec.genres?.toLowerCase().includes(searchLower) ||
        rec.semantic_themes?.toLowerCase().includes(searchLower)
      )
    );
  });
  
  const [plexUser, setPlexUser] = useState<string | null>(null);

  useEffect(() => {
    const baseUrl = window.location.origin;
    fetch(`${baseUrl}/api/recommendations`, {
      credentials: 'include'  // 🔑 This ensures cookies (session) are sent!
    })
      .then((res) => res.json())
      .then((data) => {
        setRecs(data.recommendations);
        setPlexUser(data.username);
      });
  }, []);

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
              <th className="px-4 py-3 border-r border-gray-200">Type</th>
              <th className="px-4 py-3 border-r border-gray-200">Title</th>
              <th className="px-4 py-3 border-r border-gray-200">Show</th>
              <th className="px-4 py-3 border-r border-gray-200">Year</th>
              <th className="px-4 py-3 border-r border-gray-200">Genres</th>
              <th className="px-4 py-3 border-r border-gray-200">Why this?</th>
              <th className="px-4 py-3">Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filteredRecs.map((rec, idx) => (
              <tr
                key={rec.rating_key}
                className={`border-b border-gray-200 hover:bg-gray-100 ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}`}
              >
                <td className="px-4 py-3 text-sm text-gray-700 border-r border-gray-200">{rec.media_type}</td>
                <td className="px-4 py-3 font-medium text-gray-900 border-r border-gray-200">{rec.title}</td>
                <td className="px-4 py-3 text-sm text-gray-700 border-r border-gray-200">
                  {rec.show_title ? `${rec.show_title} (S${rec.season_number}E${rec.episode_number})` : '—'}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600 border-r border-gray-200">{rec.year}</td>
                <td className="px-4 py-3 text-sm text-gray-600 border-r border-gray-200">{rec.genres || '—'}</td>
                <td className="px-4 py-3 border-r border-gray-200">
                  <div className="flex flex-wrap gap-1">
                    {rec.semantic_themes?.split(',').map((tag, i) => (
                      <button
                        key={i}
                        className={`px-2 py-0.5 rounded-full text-xs border ${tag.trim() === themeFilter ? 'bg-blue-600 text-white border-blue-600' : 'bg-blue-100 text-blue-800 border-transparent'}`}
                        onClick={() => setThemeFilter(tag.trim() === themeFilter ? '' : tag.trim())}
                      >
                        {tag.trim()}
                      </button>
                    )) || '—'}
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-gray-800">
                  <div className="flex flex-col">
                    <span className="text-sm mb-1">{(rec.predicted_probability * 100).toFixed(1)}%</span>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full"
                        style={{ width: `${(rec.predicted_probability * 100).toFixed(0)}%` }}
                      ></div>
                    </div>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
