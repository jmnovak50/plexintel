import { useEffect, useState, type KeyboardEvent } from 'react';
import { Clapperboard, Layers, Play, Tv, type LucideIcon } from 'lucide-react';
import { Link } from 'react-router-dom';

interface Recommendation {
  friendly_name: string;
  media_type: string;
  rating_key: number;
  title: string;
  poster_url?: string | null;
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
  descendant_episode_count?: number | null;
  descendant_feedback_up_count?: number | null;
  descendant_feedback_down_count?: number | null;
  descendant_feedback_total_count?: number | null;
}

type ViewMode = 'all' | 'movies' | 'shows' | 'seasons' | 'episodes';
type Thumb = 'up' | 'down';
type SortState = { column: keyof Recommendation; direction: 'asc' | 'desc' };
type ScopedSelection = { key: number; title: string };

interface RecommendationsResponse {
  username?: string | null;
  recommendations?: Recommendation[];
  last_updated?: string | null;
  feedback_keys?: number[];
}

const MEDIA_TYPE_ICONS: Record<string, { icon: LucideIcon; label: string; className: string }> = {
  movie: { icon: Clapperboard, label: 'Movie', className: 'text-rose-600' },
  movies: { icon: Clapperboard, label: 'Movie', className: 'text-rose-600' },
  show: { icon: Tv, label: 'Show', className: 'text-sky-600' },
  shows: { icon: Tv, label: 'Show', className: 'text-sky-600' },
  series: { icon: Tv, label: 'Show', className: 'text-sky-600' },
  tv_show: { icon: Tv, label: 'Show', className: 'text-sky-600' },
  season: { icon: Layers, label: 'Season', className: 'text-amber-600' },
  seasons: { icon: Layers, label: 'Season', className: 'text-amber-600' },
  episode: { icon: Play, label: 'Episode', className: 'text-emerald-600' },
  episodes: { icon: Play, label: 'Episode', className: 'text-emerald-600' }
};

function getMediaTypeConfig(mediaType: string) {
  return MEDIA_TYPE_ICONS[mediaType.toLowerCase()] ?? null;
}

function canSubmitLeafFeedback(mediaType: string) {
  const typeKey = mediaType.toLowerCase();
  return typeKey === 'movie' || typeKey === 'episode';
}

function canSubmitBulkFeedback(mediaType: string) {
  const typeKey = mediaType.toLowerCase();
  return typeKey === 'show' || typeKey === 'series' || typeKey === 'tv_show' || typeKey === 'season';
}

function getBulkCounts(rec: Recommendation) {
  const total = rec.descendant_episode_count ?? 0;
  const up = rec.descendant_feedback_up_count ?? 0;
  const down = rec.descendant_feedback_down_count ?? 0;
  const rated = rec.descendant_feedback_total_count ?? 0;
  return { total, up, down, rated };
}

function getBulkStatusMessage(rec: Recommendation) {
  const { total, up, down, rated } = getBulkCounts(rec);
  if (total <= 0) {
    return 'No episodes available';
  }
  if (up === total) {
    return `All ${total} episodes thumbs up`;
  }
  if (down === total) {
    return `All ${total} episodes thumbs down`;
  }
  if (rated === 0) {
    return `0 / ${total} episodes rated`;
  }
  return `${rated} / ${total} rated (${up} up, ${down} down)`;
}

function isBulkDirectionComplete(rec: Recommendation, feedback: Thumb) {
  const { total, up, down } = getBulkCounts(rec);
  if (total <= 0) {
    return true;
  }
  return feedback === 'up' ? up === total : down === total;
}

function buildBulkConfirmationMessage(rec: Recommendation, feedback: Thumb) {
  const { total } = getBulkCounts(rec);
  const thumbLabel = feedback === 'up' ? 'thumbs up' : 'thumbs down';
  if (rec.media_type.toLowerCase() === 'season') {
    return `Apply ${thumbLabel} to all ${total} episodes in ${rec.title}? Existing feedback for episodes in this season will be overwritten.`;
  }
  return `Apply ${thumbLabel} to all ${total} episodes in ${rec.title}? Existing feedback for episodes under this show will be overwritten.`;
}

async function extractErrorMessage(res: Response, fallback: string) {
  try {
    const data = await res.json();
    if (typeof data?.detail === 'string' && data.detail.trim()) {
      return data.detail;
    }
  } catch {
    return fallback;
  }
  return fallback;
}

async function loadRecommendationsData({
  viewMode,
  selectedShow,
  selectedSeason,
  signal,
}: {
  viewMode: ViewMode;
  selectedShow: ScopedSelection | null;
  selectedSeason: ScopedSelection | null;
  signal?: AbortSignal;
}) {
  const baseUrl = window.location.origin;
  const params = new URLSearchParams({ view: viewMode });
  if (selectedShow?.key && (viewMode === 'seasons' || viewMode === 'episodes')) {
    params.set('show_rating_key', String(selectedShow.key));
  }
  if (selectedSeason?.key && viewMode === 'episodes') {
    params.set('season_rating_key', String(selectedSeason.key));
  }

  const res = await fetch(`${baseUrl}/api/recommendations?${params.toString()}`, {
    credentials: 'include',
    signal,
  });
  if (!res.ok) {
    throw new Error(await extractErrorMessage(res, `Failed to load recommendations (${res.status})`));
  }
  return res.json() as Promise<RecommendationsResponse>;
}

function normalizeRecommendationsResponse(data: RecommendationsResponse) {
  return {
    recommendations: Array.isArray(data.recommendations) ? data.recommendations : [],
    username: typeof data.username === 'string' ? data.username : null,
    lastUpdated: typeof data.last_updated === 'string' ? data.last_updated : null,
    feedbackKeys: Array.isArray(data.feedback_keys) ? data.feedback_keys : [],
  };
}

function MediaTypeIcon({ mediaType }: { mediaType: string }) {
  const iconConfig = getMediaTypeConfig(mediaType);

  if (!iconConfig) {
    return <span className="text-xs uppercase tracking-wide text-gray-500">{mediaType}</span>;
  }

  const Icon = iconConfig.icon;

  return (
    <span
      className={`inline-flex items-center justify-center ${iconConfig.className}`}
      title={iconConfig.label}
    >
      <Icon aria-hidden="true" size={16} strokeWidth={2} />
      <span className="sr-only">{iconConfig.label}</span>
    </span>
  );
}

function MediaTypeBadge({ mediaType }: { mediaType: string }) {
  const iconConfig = getMediaTypeConfig(mediaType);

  if (!iconConfig) {
    return <span className="text-xs uppercase tracking-wide text-gray-500">{mediaType}</span>;
  }

  const Icon = iconConfig.icon;

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide ${iconConfig.className}`}>
      <Icon aria-hidden="true" size={14} strokeWidth={2} />
      <span>{iconConfig.label}</span>
    </span>
  );
}

function RecommendationPoster({ posterUrl }: { posterUrl?: string | null }) {
  const [hasImageError, setHasImageError] = useState(false);

  useEffect(() => {
    setHasImageError(false);
  }, [posterUrl]);

  if (!posterUrl || hasImageError) {
    return (
      <span
        aria-hidden="true"
        className="inline-flex h-20 w-14 shrink-0 items-center justify-center overflow-hidden rounded-md border border-gray-200 bg-gray-100 text-[9px] font-semibold uppercase tracking-wide text-gray-400"
      >
        No Art
      </span>
    );
  }

  return (
    <img
      src={posterUrl}
      alt=""
      loading="lazy"
      decoding="async"
      onError={() => setHasImageError(true)}
      className="h-20 w-14 shrink-0 rounded-md border border-gray-200 bg-gray-100 object-cover"
    />
  );
}

function RecommendationThemeChips({
  semanticThemes,
  compact = false,
}: {
  semanticThemes: string | null;
  compact?: boolean;
}) {
  if (!semanticThemes) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-1">
      {semanticThemes.split(',').map((tag, index) => (
        <span
          key={`${tag}-${index}`}
          className={`inline-flex rounded-full bg-blue-100 text-blue-800 ${compact ? 'px-2 py-0.5 text-[11px]' : 'px-2 py-0.5 text-xs'}`}
        >
          {tag.trim()}
        </span>
      ))}
    </div>
  );
}

function RecommendationScore({
  rec,
  isPending,
  statusMessage,
  statusTone = 'muted',
  compact = false,
}: {
  rec: Recommendation;
  isPending: boolean;
  statusMessage?: string | null;
  statusTone?: 'muted' | 'success';
  compact?: boolean;
}) {
  const scorePct = rec.predicted_probability * 100;
  const statusClass = statusTone === 'success'
    ? 'mt-2 text-xs font-medium text-green-700'
    : 'mt-2 text-xs text-gray-500';

  return (
    <div className={`flex flex-col ${compact ? 'items-end text-right' : ''}`}>
      <span className={`${compact ? 'text-lg font-semibold leading-none' : 'mb-1 text-sm'}`}>
        {scorePct.toFixed(1)}%
      </span>
      <div className={`w-full rounded-full bg-gray-200 ${compact ? 'mt-2 h-1.5 max-w-[6rem]' : 'h-2'}`}>
        <div
          className={`rounded-full bg-blue-600 ${compact ? 'h-1.5' : 'h-2'}`}
          style={{ width: `${scorePct.toFixed(0)}%` }}
        />
      </div>
      {rec.score_band && (
        <span className="mt-2 text-xs text-gray-500">Band: {rec.score_band}</span>
      )}
      {isPending && (
        <span className="mt-2 text-xs text-gray-500">Submitting feedback...</span>
      )}
      {!isPending && statusMessage && (
        <span className={statusClass}>{statusMessage}</span>
      )}
    </div>
  );
}

function FeedbackButtons({
  alwaysVisible = false,
  upAriaLabel,
  downAriaLabel,
  upTitle,
  downTitle,
  upDisabled,
  downDisabled,
  onUp,
  onDown,
}: {
  alwaysVisible?: boolean;
  upAriaLabel: string;
  downAriaLabel: string;
  upTitle: string;
  downTitle: string;
  upDisabled: boolean;
  downDisabled: boolean;
  onUp: () => void;
  onDown: () => void;
}) {
  const visibilityClass = alwaysVisible
    ? 'flex'
    : 'flex opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100';

  return (
    <div className={`items-center gap-2 ${visibilityClass}`}>
      <button
        type="button"
        aria-label={upAriaLabel}
        title={upTitle}
        disabled={upDisabled}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onUp();
        }}
        className="inline-flex items-center justify-center text-base leading-none transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        👍
      </button>
      <button
        type="button"
        aria-label={downAriaLabel}
        title={downTitle}
        disabled={downDisabled}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          onDown();
        }}
        className="inline-flex items-center justify-center text-base leading-none transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        👎
      </button>
    </div>
  );
}

function RecommendationFeedbackActions({
  rec,
  isPending,
  isSubmitted,
  onLeafFeedback,
  onBulkFeedback,
  alwaysVisible = false,
}: {
  rec: Recommendation;
  isPending: boolean;
  isSubmitted: boolean;
  onLeafFeedback: (ratingKey: number, feedback: Thumb) => void;
  onBulkFeedback: (rec: Recommendation, feedback: Thumb) => void;
  alwaysVisible?: boolean;
}) {
  if (canSubmitLeafFeedback(rec.media_type)) {
    if (isSubmitted) {
      return null;
    }

    return (
      <FeedbackButtons
        alwaysVisible={alwaysVisible}
        upAriaLabel={`Give thumbs up feedback for ${rec.title}`}
        downAriaLabel={`Give thumbs down feedback for ${rec.title}`}
        upTitle="Thumbs up"
        downTitle="Thumbs down"
        upDisabled={isPending}
        downDisabled={isPending}
        onUp={() => onLeafFeedback(rec.rating_key, 'up')}
        onDown={() => onLeafFeedback(rec.rating_key, 'down')}
      />
    );
  }

  if (!canSubmitBulkFeedback(rec.media_type) || getBulkCounts(rec).total <= 0) {
    return null;
  }

  return (
    <FeedbackButtons
      alwaysVisible
      upAriaLabel={`Apply thumbs up to all episodes under ${rec.title}`}
      downAriaLabel={`Apply thumbs down to all episodes under ${rec.title}`}
      upTitle="Thumbs up all episodes"
      downTitle="Thumbs down all episodes"
      upDisabled={isPending || isBulkDirectionComplete(rec, 'up')}
      downDisabled={isPending || isBulkDirectionComplete(rec, 'down')}
      onUp={() => onBulkFeedback(rec, 'up')}
      onDown={() => onBulkFeedback(rec, 'down')}
    />
  );
}

function DesktopRecommendationsTable({
  recommendations,
  feedbackSubmittedKeys,
  feedbackPendingKeys,
  bulkFeedbackPendingKeys,
  onSort,
  onRowClick,
  onLeafFeedback,
  onBulkFeedback,
  isRowClickable,
}: {
  recommendations: Recommendation[];
  feedbackSubmittedKeys: number[];
  feedbackPendingKeys: number[];
  bulkFeedbackPendingKeys: number[];
  onSort: (column: keyof Recommendation, shiftKey?: boolean) => void;
  onRowClick: (rec: Recommendation) => void;
  onLeafFeedback: (ratingKey: number, feedback: Thumb) => void;
  onBulkFeedback: (rec: Recommendation, feedback: Thumb) => void;
  isRowClickable: boolean;
}) {
  return (
    <div className="hidden md:block">
      <div className="overflow-x-auto">
        <table className="min-w-full rounded-xl border border-gray-200 bg-white text-gray-900 shadow">
          <thead>
            <tr className="border-b bg-gray-100 text-left text-sm text-gray-600">
              <th className="px-4 py-3 text-center">Type</th>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Show</th>
              <th className="cursor-pointer px-4 py-3" onClick={(event) => onSort('season_number', event.shiftKey)}>Season</th>
              <th className="cursor-pointer px-4 py-3" onClick={(event) => onSort('episode_number', event.shiftKey)}>Episode</th>
              <th className="px-4 py-3">Year</th>
              <th className="px-4 py-3">Genres</th>
              <th className="px-4 py-3">Why this?</th>
              <th className="px-4 py-3">Score</th>
            </tr>
          </thead>
          <tbody>
            {recommendations.map((rec) => {
              const isBulkFeedback = canSubmitBulkFeedback(rec.media_type);
              const isSubmitted = feedbackSubmittedKeys.includes(rec.rating_key);
              const isLeafPending = feedbackPendingKeys.includes(rec.rating_key);
              const isBulkPending = bulkFeedbackPendingKeys.includes(rec.rating_key);
              const isPending = isBulkFeedback ? isBulkPending : isLeafPending;
              const statusMessage = isBulkFeedback
                ? getBulkStatusMessage(rec)
                : isSubmitted
                  ? 'Feedback submitted'
                  : null;
              const statusTone = !isBulkFeedback && isSubmitted ? 'success' as const : 'muted' as const;

              return (
                <tr
                  key={rec.rating_key}
                  onClick={() => onRowClick(rec)}
                  className={`group border-b transition-colors duration-300 ${isSubmitted ? 'bg-green-50' : 'hover:bg-gray-100'} ${isRowClickable ? 'cursor-pointer' : ''}`}
                >
                  <td className="px-4 py-2 text-center">
                    <MediaTypeIcon mediaType={rec.media_type} />
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex flex-col items-center gap-2 text-center">
                      <RecommendationPoster posterUrl={rec.poster_url} />
                      <span className="max-w-[8rem] text-sm font-semibold leading-tight text-gray-900">
                        {rec.title}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-2">{rec.show_title || '—'}</td>
                  <td className="px-4 py-2">{rec.season_number ?? '—'}</td>
                  <td className="px-4 py-2">{rec.episode_number ?? '—'}</td>
                  <td className="px-4 py-2">{rec.year ?? '—'}</td>
                  <td className="px-4 py-2">{rec.genres || '—'}</td>
                  <td className="px-4 py-2">
                    <RecommendationThemeChips semanticThemes={rec.semantic_themes} />
                  </td>
                  <td className="relative px-4 py-2">
                    <div className="flex flex-col">
                      <RecommendationScore
                        rec={rec}
                        isPending={isPending}
                        statusMessage={statusMessage}
                        statusTone={statusTone}
                      />
                      <RecommendationFeedbackActions
                        rec={rec}
                        isPending={isPending}
                        isSubmitted={isSubmitted}
                        onLeafFeedback={onLeafFeedback}
                        onBulkFeedback={onBulkFeedback}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function MobileRecommendationsList({
  recommendations,
  feedbackSubmittedKeys,
  feedbackPendingKeys,
  bulkFeedbackPendingKeys,
  onRowClick,
  onLeafFeedback,
  onBulkFeedback,
  isRowClickable,
}: {
  recommendations: Recommendation[];
  feedbackSubmittedKeys: number[];
  feedbackPendingKeys: number[];
  bulkFeedbackPendingKeys: number[];
  onRowClick: (rec: Recommendation) => void;
  onLeafFeedback: (ratingKey: number, feedback: Thumb) => void;
  onBulkFeedback: (rec: Recommendation, feedback: Thumb) => void;
  isRowClickable: boolean;
}) {
  const handleCardKeyDown = (
    event: KeyboardEvent<HTMLDivElement>,
    rec: Recommendation,
  ) => {
    if (!isRowClickable) {
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onRowClick(rec);
    }
  };

  return (
    <div className="space-y-3 md:hidden">
      {recommendations.map((rec) => {
        const isBulkFeedback = canSubmitBulkFeedback(rec.media_type);
        const isSubmitted = feedbackSubmittedKeys.includes(rec.rating_key);
        const isLeafPending = feedbackPendingKeys.includes(rec.rating_key);
        const isBulkPending = bulkFeedbackPendingKeys.includes(rec.rating_key);
        const isPending = isBulkFeedback ? isBulkPending : isLeafPending;
        const statusMessage = isBulkFeedback
          ? getBulkStatusMessage(rec)
          : isSubmitted
            ? 'Feedback submitted'
            : null;
        const statusTone = !isBulkFeedback && isSubmitted ? 'success' as const : 'muted' as const;

        return (
          <div
            key={rec.rating_key}
            role={isRowClickable ? 'button' : undefined}
            tabIndex={isRowClickable ? 0 : undefined}
            onClick={() => onRowClick(rec)}
            onKeyDown={(event) => handleCardKeyDown(event, rec)}
            className={`rounded-xl border bg-white p-4 text-gray-900 shadow-sm transition-colors duration-300 ${isSubmitted ? 'border-green-200 bg-green-50' : 'border-gray-200'} ${isRowClickable ? 'cursor-pointer active:bg-gray-50' : ''}`}
          >
            <div className="flex items-start justify-between gap-3">
              <MediaTypeBadge mediaType={rec.media_type} />
              <RecommendationScore
                rec={rec}
                isPending={isPending}
                statusMessage={statusMessage}
                statusTone={statusTone}
                compact
              />
            </div>

            <div className="mt-4 flex flex-col items-center gap-2 text-center">
              <RecommendationPoster posterUrl={rec.poster_url} />
              <span className="max-w-[14rem] text-sm font-semibold leading-tight text-gray-900">
                {rec.title}
              </span>
            </div>

            <div className="mt-4 space-y-1 text-sm text-gray-600">
              {rec.show_title && (
                <div>
                  <span className="font-medium text-gray-700">Show:</span> {rec.show_title}
                </div>
              )}
              {(rec.season_number != null || rec.episode_number != null) && (
                <div>
                  <span className="font-medium text-gray-700">Episode:</span>{' '}
                  {[
                    rec.season_number != null ? `Season ${rec.season_number}` : null,
                    rec.episode_number != null ? `Episode ${rec.episode_number}` : null,
                  ]
                    .filter(Boolean)
                    .join(' • ')}
                </div>
              )}
              {rec.year != null && (
                <div>
                  <span className="font-medium text-gray-700">Year:</span> {rec.year}
                </div>
              )}
              {rec.genres && (
                <div>
                  <span className="font-medium text-gray-700">Genres:</span> {rec.genres}
                </div>
              )}
            </div>

            {rec.semantic_themes && (
              <div className="mt-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Why this?</p>
                <RecommendationThemeChips semanticThemes={rec.semantic_themes} compact />
              </div>
            )}

            <div className="mt-4">
              <RecommendationFeedbackActions
                rec={rec}
                isPending={isPending}
                isSubmitted={isSubmitted}
                onLeafFeedback={onLeafFeedback}
                onBulkFeedback={onBulkFeedback}
                alwaysVisible
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Recommendations() {
  const [search, setSearch] = useState('');
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [darkMode, setDarkMode] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('all');
  const [selectedShow, setSelectedShow] = useState<ScopedSelection | null>(null);
  const [selectedSeason, setSelectedSeason] = useState<ScopedSelection | null>(null);
  const [minScore, setMinScore] = useState(0);
  const [plexUser, setPlexUser] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [feedbackSubmittedKeys, setFeedbackSubmittedKeys] = useState<number[]>([]);
  const [feedbackPendingKeys, setFeedbackPendingKeys] = useState<number[]>([]);
  const [bulkFeedbackPendingKeys, setBulkFeedbackPendingKeys] = useState<number[]>([]);
  const [pageError, setPageError] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<SortState[]>([]);

  useEffect(() => {
    const controller = new AbortController();

    loadRecommendationsData({
      viewMode,
      selectedShow,
      selectedSeason,
      signal: controller.signal,
    })
      .then((data) => {
        if (controller.signal.aborted) {
          return;
        }
        const normalized = normalizeRecommendationsResponse(data);
        setRecs(normalized.recommendations);
        setPlexUser(normalized.username);
        setLastUpdated(normalized.lastUpdated);
        setFeedbackSubmittedKeys(normalized.feedbackKeys);
        setPageError(null);
      })
      .catch((error) => {
        if (controller.signal.aborted) {
          return;
        }
        console.error(error);
        setPageError(error instanceof Error ? error.message : 'Failed to load recommendations.');
      });

    return () => {
      controller.abort();
    };
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

  const sendLeafFeedback = async (ratingKey: number, feedback: Thumb) => {
    if (!plexUser) {
      setPageError('Unable to submit feedback: user session is missing.');
      return;
    }
    if (feedbackPendingKeys.includes(ratingKey)) {
      return;
    }

    const payload = { username: plexUser, rating_key: ratingKey, feedback };
    setPageError(null);
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
        throw new Error(await extractErrorMessage(res, `Failed to submit feedback (${res.status})`));
      }
    } catch (error) {
      console.error(error);
      setFeedbackSubmittedKeys((prev) => prev.filter((key) => key !== ratingKey));
      setPageError(error instanceof Error ? error.message : 'Failed to submit feedback.');
    } finally {
      setFeedbackPendingKeys((prev) => prev.filter((key) => key !== ratingKey));
    }
  };

  const sendBulkFeedback = async (rec: Recommendation, feedback: Thumb) => {
    if (!plexUser) {
      setPageError('Unable to submit feedback: user session is missing.');
      return;
    }
    if (bulkFeedbackPendingKeys.includes(rec.rating_key) || getBulkCounts(rec).total <= 0) {
      return;
    }
    if (!window.confirm(buildBulkConfirmationMessage(rec, feedback))) {
      return;
    }

    const payload = { username: plexUser, rating_key: rec.rating_key, feedback };
    setPageError(null);
    setBulkFeedbackPendingKeys((prev) => (
      prev.includes(rec.rating_key) ? prev : [...prev, rec.rating_key]
    ));

    try {
      const res = await fetch('/api/feedback/bulk', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(await extractErrorMessage(res, `Failed to submit bulk feedback (${res.status})`));
      }

      const data = await loadRecommendationsData({
        viewMode,
        selectedShow,
        selectedSeason,
      });
      const normalized = normalizeRecommendationsResponse(data);
      setRecs(normalized.recommendations);
      setPlexUser(normalized.username);
      setLastUpdated(normalized.lastUpdated);
      setFeedbackSubmittedKeys(normalized.feedbackKeys);
      setPageError(null);
    } catch (error) {
      console.error(error);
      setPageError(error instanceof Error ? error.message : 'Failed to submit bulk feedback.');
    } finally {
      setBulkFeedbackPendingKeys((prev) => prev.filter((key) => key !== rec.rating_key));
    }
  };

  const handleSort = (column: keyof Recommendation, shiftKey = false) => {
    setSortOrder((prev) => {
      const existing = prev.find((sort) => sort?.column === column);

      if (existing) {
        return prev.map((sort) =>
          sort.column === column
            ? { ...sort, direction: sort.direction === 'asc' ? 'desc' : 'asc' }
            : sort
        );
      }

      const newSort = { column, direction: 'asc' as const };
      return shiftKey ? [...prev, newSort] : [newSort];
    });
  };

  const handleViewSelect = (nextView: ViewMode) => {
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

  const isRowClickable = viewMode === 'shows' || viewMode === 'seasons';

  return (
    <div className={`mx-auto w-full max-w-7xl overflow-x-hidden px-3 py-4 sm:px-4 ${darkMode ? 'bg-gray-900 text-white' : 'bg-white text-black'}`}>
      <h1 className="mb-2 text-2xl font-bold md:text-3xl">
        🎬 Recommendations for {recs[0]?.friendly_name || plexUser || 'user'}
      </h1>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-3">
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

      <div className="mb-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <input
          type="text"
          placeholder="Search by title, show, genre, or theme..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-md border border-gray-300 p-2 shadow-sm"
        />

        <select
          value={viewMode}
          onChange={(e) => handleViewSelect(e.target.value as ViewMode)}
          className="w-full rounded-md border border-gray-300 p-2 shadow-sm"
        >
          <option value="all">All</option>
          <option value="movies">Movies</option>
          <option value="shows">Shows</option>
          <option value="seasons">Seasons</option>
          <option value="episodes">Episodes</option>
        </select>

        <div className="col-span-1 sm:col-span-2">
          <label htmlFor="score-range" className="mb-1 block text-sm font-medium text-gray-700">
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

      {pageError && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          Error: {pageError}
        </div>
      )}

      {(viewMode === 'seasons' || viewMode === 'episodes') && selectedShow && (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-gray-600">
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

      {filteredRecs.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white px-4 py-6 text-sm text-gray-500 shadow-sm">
          No recommendations match the current filters.
        </div>
      ) : (
        <>
          <MobileRecommendationsList
            recommendations={filteredRecs}
            feedbackSubmittedKeys={feedbackSubmittedKeys}
            feedbackPendingKeys={feedbackPendingKeys}
            bulkFeedbackPendingKeys={bulkFeedbackPendingKeys}
            onRowClick={handleRowClick}
            onLeafFeedback={sendLeafFeedback}
            onBulkFeedback={sendBulkFeedback}
            isRowClickable={isRowClickable}
          />
          <DesktopRecommendationsTable
            recommendations={filteredRecs}
            feedbackSubmittedKeys={feedbackSubmittedKeys}
            feedbackPendingKeys={feedbackPendingKeys}
            bulkFeedbackPendingKeys={bulkFeedbackPendingKeys}
            onSort={handleSort}
            onRowClick={handleRowClick}
            onLeafFeedback={sendLeafFeedback}
            onBulkFeedback={sendBulkFeedback}
            isRowClickable={isRowClickable}
          />
        </>
      )}

      {lastUpdated && (
        <div className="mt-4 text-right text-sm text-gray-500">
          Last updated: {new Date(lastUpdated).toLocaleString()}
        </div>
      )}
    </div>
  );
}
