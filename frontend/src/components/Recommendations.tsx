// src/components/Recommendations.tsx
import { useEffect, useState } from 'react';

console.log("🔥 Recommendations.tsx loaded");

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
  const [sortOrder, setSortOrder] = useState<Array<{ column: keyof Recommendation; direction: 'asc' | 'desc' }>>([]);
  const [plexUser, setPlexUser] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

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
      });
  }, []);

  const handleSort = (column: keyof Recommendation, shiftKey = false) => {
    setSortOrder((prev) => {
      if (!Array.isArray(prev)) return [];
      const existing = prev.find((s) => s?.column === column);

      if (existing) {
        const toggled = prev.map((s) =>
          s.column === column ? { ...s, direction: (s.direction === 'asc' ? 'desc' : 'asc') as 'asc' | 'desc' } : s
        );
        return toggled;
      } else {
        const newSort = { column: column as keyof Recommendation, direction: 'asc' as 'asc' | 'desc' };
        return shiftKey ? [...prev, newSort] : [newSort];
      }
    });
  };

  console.log("recs:", recs.slice(0, 5));
  console.log("sortOrder:", sortOrder);

  const filteredRecs = [...recs].filter((rec: Recommendation) => {
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

  if (sortOrder.length > 0) {
    filteredRecs.sort((a: Recommendation, b: Recommendation) => {
      for (const { column, direction } of sortOrder) {
        const aVal = a[column];
        const bVal = b[column];

        if (aVal == null || bVal == null) continue;

        if (aVal == null) return 1;
        if (bVal == null) return -1;

        if (column === 'season_number' && aVal === bVal) {
          const aEp = a.episode_number ?? 0;
          const bEp = b.episode_number ?? 0;
          const result = direction === 'asc' ? aEp - bEp : bEp - aEp;
          if (result !== 0) return result;
        }

        if (typeof aVal === 'string' && typeof bVal === 'string') {
          const result = direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
          if (result !== 0) return result;
        } else if (typeof aVal === 'number' && typeof bVal === 'number') {
          const result = direction === 'asc' ? aVal - bVal : bVal - aVal;
          if (result !== 0) return result;
        }
      }
      return 0;
    });
  }

  const getSortArrow = (column: keyof Recommendation) => {
    console.log("🧪 inside getSortArrow with column:", column);
    const current = sortOrder.find((s) => s && s.column === column);
    return current ? (current.direction === 'asc' ? '↑' : '↓') : '';
  };
  
  
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
              <th className="px-4 py-3 border-r border-gray-200 cursor-pointer select-none" onClick={(e) => handleSort('title', e.shiftKey)}>
                Title {getSortArrow('title')}
              </th>
              <th className="px-4 py-3 border-r border-gray-200">Show</th>
              <th className="px-4 py-3 border-r border-gray-200 cursor-pointer select-none" onClick={(e) => handleSort('season_number', e.shiftKey)}>
                Season {getSortArrow('season_number')}
              </th>
              <th className="px-4 py-3 border-r border-gray-200 cursor-pointer select-none" onClick={(e) => handleSort('episode_number', e.shiftKey)}>
                Episode {getSortArrow('episode_number')}
              </th>
              <th className="px-4 py-3 border-r border-gray-200 cursor-pointer select-none" onClick={(e) => handleSort('year', e.shiftKey)}>
                Year {getSortArrow('year')}
              </th>
              <th className="px-4 py-3 border-r border-gray-200">Genres</th>
              <th className="px-4 py-3 border-r border-gray-200">Why this?</th>
              <th className="px-4 py-3 cursor-pointer select-none" onClick={(e) => handleSort('predicted_probability', e.shiftKey)}>
                Score {getSortArrow('predicted_probability')}
              </th>
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
                <td className="px-4 py-3 text-sm text-gray-700 border-r border-gray-200">{rec.show_title || '—'}</td>
                <td className="px-4 py-3 text-sm text-gray-600 border-r border-gray-200">{rec.season_number ?? '—'}</td>
                <td className="px-4 py-3 text-sm text-gray-600 border-r border-gray-200">{rec.episode_number ?? '—'}</td>
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

      {lastUpdated && (
        <div className="mt-4 text-sm text-gray-500 text-right">
          Last updated: {new Date(lastUpdated).toLocaleString()}
        </div>
      )}
    </div>
  );
}