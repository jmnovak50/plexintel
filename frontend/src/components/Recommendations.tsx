import { useEffect, useMemo, useState, type KeyboardEvent } from 'react';
import {
  Ban,
  BookmarkPlus,
  Clapperboard,
  Layers,
  Play,
  RotateCcw,
  ThumbsDown,
  ThumbsUp,
  Tv,
  type LucideIcon,
} from 'lucide-react';
import { Link } from 'react-router-dom';

type FeedbackAction = 'interested' | 'never_watch' | 'watched_like' | 'watched_dislike';
type FeedbackFilter = 'all' | 'saved' | 'unsaved';
type ViewMode = 'all' | 'movies' | 'shows' | 'seasons' | 'episodes';
type SortState = { column: keyof Recommendation; direction: 'asc' | 'desc' };
type ScopedSelection = { key: number; title: string };

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
  feedback_state?: FeedbackAction | null;
  feedback_suppress?: boolean;
  feedback_reason_code?: string | null;
  plex_watchlist_status?: string | null;
}

interface RecommendationsResponse {
  username?: string | null;
  recommendations?: Recommendation[];
  last_updated?: string | null;
}

interface FeedbackApiResponse {
  status: string;
  feedback?: {
    feedback: FeedbackAction;
    feedback_label: string;
    plex_watchlist_status: string | null;
    suppress: boolean;
  };
}

interface UndoState {
  recommendation: Recommendation;
  action: FeedbackAction;
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
  episodes: { icon: Play, label: 'Episode', className: 'text-emerald-600' },
};

const FEEDBACK_ACTIONS: Array<{
  action: FeedbackAction;
  label: string;
  groupLabel: string;
  icon: LucideIcon;
  className: string;
  activeClassName: string;
}> = [
  {
    action: 'interested',
    label: 'Want to watch',
    groupLabel: 'Not watched',
    icon: BookmarkPlus,
    className: 'border-blue-200 text-blue-700 hover:bg-blue-50',
    activeClassName: 'border-blue-300 bg-blue-50 text-blue-800',
  },
  {
    action: 'never_watch',
    label: 'Never watch',
    groupLabel: 'Not watched',
    icon: Ban,
    className: 'border-red-200 text-red-700 hover:bg-red-50',
    activeClassName: 'border-red-300 bg-red-50 text-red-800',
  },
  {
    action: 'watched_like',
    label: 'Watched, liked',
    groupLabel: 'Already watched',
    icon: ThumbsUp,
    className: 'border-emerald-200 text-emerald-700 hover:bg-emerald-50',
    activeClassName: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  },
  {
    action: 'watched_dislike',
    label: 'Watched, disliked',
    groupLabel: 'Already watched',
    icon: ThumbsDown,
    className: 'border-amber-200 text-amber-700 hover:bg-amber-50',
    activeClassName: 'border-amber-300 bg-amber-50 text-amber-800',
  },
];

function getMediaTypeConfig(mediaType: string) {
  return MEDIA_TYPE_ICONS[mediaType.toLowerCase()] ?? null;
}

function canSubmitLeafFeedback(mediaType: string) {
  const typeKey = mediaType.toLowerCase();
  return typeKey === 'movie' || typeKey === 'episode';
}

function feedbackActionLabel(action: FeedbackAction | null | undefined) {
  return FEEDBACK_ACTIONS.find((config) => config.action === action)?.label ?? null;
}

function watchlistStatusLabel(status: string | null | undefined) {
  switch (status) {
    case 'synced':
      return 'Plex watchlist synced';
    case 'failed':
      return 'Plex watchlist sync failed';
    case 'auth_required':
      return 'Plex login required';
    case 'unresolved':
      return 'Plex sync unavailable';
    case 'not_supported':
      return 'Plex watchlist unsupported';
    default:
      return null;
  }
}

function watchlistStatusClassName(status: string | null | undefined) {
  switch (status) {
    case 'synced':
      return 'border-blue-200 bg-blue-50 text-blue-700';
    case 'failed':
      return 'border-amber-200 bg-amber-50 text-amber-700';
    case 'auth_required':
      return 'border-slate-200 bg-slate-100 text-slate-700';
    case 'unresolved':
    case 'not_supported':
      return 'border-slate-200 bg-slate-50 text-slate-600';
    default:
      return '';
  }
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
  compact = false,
}: {
  rec: Recommendation;
  isPending: boolean;
  compact?: boolean;
}) {
  const scorePct = rec.predicted_probability * 100;

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
        <span className="mt-2 text-xs text-gray-500">Saving feedback...</span>
      )}
    </div>
  );
}

function FeedbackStateBadges({ rec }: { rec: Recommendation }) {
  const feedbackLabel = feedbackActionLabel(rec.feedback_state);
  const watchlistLabel = rec.feedback_state === 'interested'
    ? watchlistStatusLabel(rec.plex_watchlist_status)
    : null;

  if (!feedbackLabel && !watchlistLabel) {
    return null;
  }

  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {feedbackLabel && (
        <span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700">
          Saved
        </span>
      )}
      {watchlistLabel && (
        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${watchlistStatusClassName(rec.plex_watchlist_status)}`}>
          {watchlistLabel}
        </span>
      )}
    </div>
  );
}

function FeedbackActionButtons({
  rec,
  isPending,
  onAction,
  onUndo,
  alwaysVisible = false,
}: {
  rec: Recommendation;
  isPending: boolean;
  onAction: (rec: Recommendation, action: FeedbackAction) => void;
  onUndo: (rec: Recommendation) => void;
  alwaysVisible?: boolean;
}) {
  if (!canSubmitLeafFeedback(rec.media_type)) {
    return null;
  }

  const groups = ['Not watched', 'Already watched'];
  const visibilityClass = alwaysVisible
    ? 'flex'
    : 'flex opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100';

  return (
    <div className={`flex-col gap-3 ${visibilityClass}`}>
      {groups.map((groupLabel) => (
        <div key={groupLabel} className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">{groupLabel}</p>
          <div className="flex flex-wrap gap-2">
            {FEEDBACK_ACTIONS.filter((config) => config.groupLabel === groupLabel).map((config) => {
              const Icon = config.icon;
              const isActive = rec.feedback_state === config.action;
              return (
                <button
                  key={config.action}
                  type="button"
                  aria-label={`${config.label} for ${rec.title}`}
                  title={config.label}
                  disabled={isPending || isActive}
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    onAction(rec, config.action);
                  }}
                  className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60 ${isActive ? config.activeClassName : config.className}`}
                >
                  <Icon aria-hidden="true" size={14} strokeWidth={2} />
                  <span>{config.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      ))}
      {rec.feedback_state === 'interested' && (
        <button
          type="button"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onUndo(rec);
          }}
          disabled={isPending}
          className="inline-flex items-center gap-2 rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RotateCcw aria-hidden="true" size={14} strokeWidth={2} />
          <span>Undo</span>
        </button>
      )}
    </div>
  );
}

function RecommendationTitleCell({
  rec,
  isCompact = false,
}: {
  rec: Recommendation;
  isCompact?: boolean;
}) {
  return (
    <div className={`flex ${isCompact ? 'flex-col items-center text-center' : 'items-start gap-3'}`}>
      <RecommendationPoster posterUrl={rec.poster_url} />
      <div className={isCompact ? 'mt-2' : ''}>
        <p className="text-sm font-semibold leading-tight text-gray-900">{rec.title}</p>
        <FeedbackStateBadges rec={rec} />
      </div>
    </div>
  );
}

function DesktopRecommendationsTable({
  recommendations,
  pendingKeys,
  onSort,
  onRowClick,
  onAction,
  onUndo,
  isRowClickable,
}: {
  recommendations: Recommendation[];
  pendingKeys: number[];
  onSort: (column: keyof Recommendation, shiftKey?: boolean) => void;
  onRowClick: (rec: Recommendation) => void;
  onAction: (rec: Recommendation, action: FeedbackAction) => void;
  onUndo: (rec: Recommendation) => void;
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
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {recommendations.map((rec) => {
              const isPending = pendingKeys.includes(rec.rating_key);

              return (
                <tr
                  key={rec.rating_key}
                  onClick={() => onRowClick(rec)}
                  className={`group border-b transition-colors duration-300 hover:bg-gray-50 ${isRowClickable ? 'cursor-pointer' : ''}`}
                >
                  <td className="px-4 py-2 text-center">
                    <MediaTypeIcon mediaType={rec.media_type} />
                  </td>
                  <td className="px-4 py-2">
                    <RecommendationTitleCell rec={rec} />
                  </td>
                  <td className="px-4 py-2">{rec.show_title || '—'}</td>
                  <td className="px-4 py-2">{rec.season_number ?? '—'}</td>
                  <td className="px-4 py-2">{rec.episode_number ?? '—'}</td>
                  <td className="px-4 py-2">{rec.year ?? '—'}</td>
                  <td className="px-4 py-2">{rec.genres || '—'}</td>
                  <td className="px-4 py-2">
                    <RecommendationThemeChips semanticThemes={rec.semantic_themes} />
                  </td>
                  <td className="px-4 py-2">
                    <RecommendationScore rec={rec} isPending={isPending} />
                  </td>
                  <td className="px-4 py-2">
                    <FeedbackActionButtons
                      rec={rec}
                      isPending={isPending}
                      onAction={onAction}
                      onUndo={onUndo}
                      alwaysVisible={rec.feedback_state === 'interested'}
                    />
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
  pendingKeys,
  onRowClick,
  onAction,
  onUndo,
  isRowClickable,
}: {
  recommendations: Recommendation[];
  pendingKeys: number[];
  onRowClick: (rec: Recommendation) => void;
  onAction: (rec: Recommendation, action: FeedbackAction) => void;
  onUndo: (rec: Recommendation) => void;
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
        const isPending = pendingKeys.includes(rec.rating_key);

        return (
          <div
            key={rec.rating_key}
            role={isRowClickable ? 'button' : undefined}
            tabIndex={isRowClickable ? 0 : undefined}
            onClick={() => onRowClick(rec)}
            onKeyDown={(event) => handleCardKeyDown(event, rec)}
            className={`rounded-xl border border-gray-200 bg-white p-4 text-gray-900 shadow-sm ${isRowClickable ? 'cursor-pointer active:bg-gray-50' : ''}`}
          >
            <div className="flex items-start justify-between gap-3">
              <MediaTypeBadge mediaType={rec.media_type} />
              <RecommendationScore rec={rec} isPending={isPending} compact />
            </div>

            <div className="mt-4">
              <RecommendationTitleCell rec={rec} isCompact />
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
              <FeedbackActionButtons
                rec={rec}
                isPending={isPending}
                onAction={onAction}
                onUndo={onUndo}
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
  const [pendingKeys, setPendingKeys] = useState<number[]>([]);
  const [pageError, setPageError] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<SortState[]>([]);
  const [feedbackFilter, setFeedbackFilter] = useState<FeedbackFilter>('all');
  const [undoState, setUndoState] = useState<UndoState | null>(null);

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

  const sendFeedback = async (rec: Recommendation, action: FeedbackAction) => {
    if (!plexUser) {
      setPageError('Unable to submit feedback: user session is missing.');
      return;
    }
    if (pendingKeys.includes(rec.rating_key)) {
      return;
    }

    setPageError(null);
    setPendingKeys((prev) => (prev.includes(rec.rating_key) ? prev : [...prev, rec.rating_key]));

    try {
      const res = await fetch('/api/feedback', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: plexUser,
          rating_key: rec.rating_key,
          feedback: action,
        }),
      });

      if (!res.ok) {
        throw new Error(await extractErrorMessage(res, `Failed to submit feedback (${res.status})`));
      }

      const data = await res.json() as FeedbackApiResponse;
      const returnedFeedback = data.feedback;

      if (action === 'interested') {
        setRecs((prev) => prev.map((item) => (
          item.rating_key === rec.rating_key
            ? {
                ...item,
                feedback_state: 'interested',
                feedback_suppress: false,
                feedback_reason_code: returnedFeedback?.feedback ?? 'interested',
                plex_watchlist_status: returnedFeedback?.plex_watchlist_status ?? 'unresolved',
              }
            : item
        )));
        setUndoState(null);
      } else {
        setRecs((prev) => prev.filter((item) => item.rating_key !== rec.rating_key));
        setUndoState({
          recommendation: {
            ...rec,
            feedback_state: null,
            feedback_suppress: false,
            feedback_reason_code: null,
            plex_watchlist_status: 'not_applicable',
          },
          action,
        });
      }
    } catch (error) {
      console.error(error);
      setPageError(error instanceof Error ? error.message : 'Failed to submit feedback.');
    } finally {
      setPendingKeys((prev) => prev.filter((key) => key !== rec.rating_key));
    }
  };

  const undoFeedback = async (rec: Recommendation) => {
    if (!plexUser) {
      setPageError('Unable to undo feedback: user session is missing.');
      return;
    }
    if (pendingKeys.includes(rec.rating_key)) {
      return;
    }

    setPageError(null);
    setPendingKeys((prev) => (prev.includes(rec.rating_key) ? prev : [...prev, rec.rating_key]));

    try {
      const res = await fetch(`/api/feedback/${rec.rating_key}?username=${encodeURIComponent(plexUser)}`, {
        method: 'DELETE',
        credentials: 'include',
      });

      if (!res.ok) {
        throw new Error(await extractErrorMessage(res, `Failed to remove feedback (${res.status})`));
      }

      setRecs((prev) => {
        const exists = prev.some((item) => item.rating_key === rec.rating_key);
        if (exists) {
          return prev.map((item) => (
            item.rating_key === rec.rating_key
              ? {
                  ...item,
                  feedback_state: null,
                  feedback_suppress: false,
                  feedback_reason_code: null,
                  plex_watchlist_status: 'not_applicable',
                }
              : item
          ));
        }
        return [
          ...prev,
          {
            ...rec,
            feedback_state: null,
            feedback_suppress: false,
            feedback_reason_code: null,
            plex_watchlist_status: 'not_applicable',
          },
        ];
      });
      setUndoState(null);
    } catch (error) {
      console.error(error);
      setPageError(error instanceof Error ? error.message : 'Failed to undo feedback.');
    } finally {
      setPendingKeys((prev) => prev.filter((key) => key !== rec.rating_key));
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

  const filteredRecs = useMemo(() => (
    [...recs]
      .filter((rec) => {
        const score = rec.predicted_probability * 100;
        const searchLower = search.toLowerCase();
        const usesSavedFilter = viewMode !== 'shows' && viewMode !== 'seasons';
        const matchesSearch = (
          rec.title?.toLowerCase().includes(searchLower) ||
          rec.show_title?.toLowerCase().includes(searchLower) ||
          rec.genres?.toLowerCase().includes(searchLower) ||
          rec.semantic_themes?.toLowerCase().includes(searchLower)
        );
        const matchesSavedFilter = (
          !usesSavedFilter ||
          feedbackFilter === 'all' ||
          (feedbackFilter === 'saved' && rec.feedback_state === 'interested') ||
          (feedbackFilter === 'unsaved' && rec.feedback_state !== 'interested')
        );
        return score >= minScore && matchesSearch && matchesSavedFilter;
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
        return b.predicted_probability - a.predicted_probability;
      })
  ), [feedbackFilter, minScore, recs, search, sortOrder, viewMode]);

  const isRowClickable = viewMode === 'shows' || viewMode === 'seasons';

  return (
    <div className={`mx-auto w-full max-w-7xl overflow-x-hidden px-3 py-4 sm:px-4 ${darkMode ? 'bg-gray-900 text-white' : 'bg-white text-black'}`}>
      <h1 className="mb-2 text-2xl font-bold md:text-3xl">
        Recommendations for {recs[0]?.friendly_name || plexUser || 'user'}
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

      {undoState && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
          <span>
            {feedbackActionLabel(undoState.action)} saved for <span className="font-medium">{undoState.recommendation.title}</span>.
          </span>
          <button
            type="button"
            onClick={() => undoFeedback(undoState.recommendation)}
            className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100"
          >
            <RotateCcw aria-hidden="true" size={14} strokeWidth={2} />
            <span>Undo</span>
          </button>
        </div>
      )}

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

        {viewMode !== 'shows' && viewMode !== 'seasons' && (
          <div className="col-span-1 sm:col-span-2">
            <div className="flex flex-wrap gap-2">
              {(['all', 'saved', 'unsaved'] as FeedbackFilter[]).map((filterValue) => (
                <button
                  key={filterValue}
                  type="button"
                  onClick={() => setFeedbackFilter(filterValue)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                    feedbackFilter === filterValue
                      ? 'border-blue-300 bg-blue-50 text-blue-700'
                      : 'border-gray-300 bg-white text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {filterValue === 'all' ? 'All' : filterValue === 'saved' ? 'Saved' : 'Unsaved'}
                </button>
              ))}
            </div>
          </div>
        )}
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
            pendingKeys={pendingKeys}
            onRowClick={handleRowClick}
            onAction={sendFeedback}
            onUndo={undoFeedback}
            isRowClickable={isRowClickable}
          />
          <DesktopRecommendationsTable
            recommendations={filteredRecs}
            pendingKeys={pendingKeys}
            onSort={handleSort}
            onRowClick={handleRowClick}
            onAction={sendFeedback}
            onUndo={undoFeedback}
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
