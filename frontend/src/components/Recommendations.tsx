import { useEffect, useState, type KeyboardEvent } from 'react';
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
type ViewMode = 'all' | 'movies' | 'shows' | 'seasons' | 'episodes';
type SortState = { column: keyof Recommendation; direction: 'asc' | 'desc' };
type ScopedSelection = { key: number; title: string };

interface Recommendation {
  friendly_name: string;
  media_type: string;
  rating_key: number;
  title: string;
  poster_url?: string | null;
  plex_item_url?: string | null;
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
  descendant_feedback_suppress_count?: number | null;
  descendant_interested_count?: number | null;
  descendant_never_watch_count?: number | null;
  descendant_watched_like_count?: number | null;
  descendant_watched_dislike_count?: number | null;
  visible_recommendation_episode_count?: number | null;
  visible_recommendation_season_count?: number | null;
  feedback_state?: FeedbackAction | null;
  feedback_suppress?: boolean;
  feedback_reason_code?: string | null;
  plex_watchlist_status?: string | null;
}

interface RecommendationsResponse {
  username?: string | null;
  recommendations?: Recommendation[];
  last_updated?: string | null;
  has_more?: boolean;
  next_offset?: number | null;
  limit?: number;
  offset?: number;
}

interface FeedbackApiResponse {
  status: string;
  feedback?: {
    rating_key: number;
    feedback: FeedbackAction;
    feedback_label: string;
    reason_code: string | null;
    saved_at: string | null;
    plex_watchlist_status: string | null;
    suppress: boolean;
  };
}

interface BulkFeedbackApiResponse {
  status: string;
  target_rating_key: number;
  target_media_type: 'show' | 'season';
  target_title: string;
  feedback: 'interested' | 'never_watch';
  descendant_total: number;
  updated_count: number;
  skipped_watched_count: number;
}

interface UndoState {
  recommendation: Recommendation;
  action: FeedbackAction;
}

interface EmailPreferencesResponse {
  email: string | null;
  has_email: boolean;
  digest_enabled: boolean;
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
const RECOMMENDATION_PAGE_LIMIT = 100;

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

function canSubmitBulkFeedback(mediaType: string) {
  const typeKey = mediaType.toLowerCase();
  return typeKey === 'show' || typeKey === 'series' || typeKey === 'tv_show' || typeKey === 'season';
}

function feedbackActionLabel(action: FeedbackAction | null | undefined) {
  return FEEDBACK_ACTIONS.find((config) => config.action === action)?.label ?? null;
}

function pluralize(count: number, singular: string, plural = `${singular}s`) {
  return count === 1 ? singular : plural;
}

const BULK_FEEDBACK_ACTIONS: Array<{
  action: 'interested' | 'never_watch';
  label: string;
  groupLabel: string;
  icon: LucideIcon;
  className: string;
  activeClassName: string;
  bulkLabel: string;
}> = FEEDBACK_ACTIONS
  .filter((config): config is typeof FEEDBACK_ACTIONS[number] & { action: 'interested' | 'never_watch' } => (
    config.action === 'interested' || config.action === 'never_watch'
  ))
  .map((config) => ({
    ...config,
    bulkLabel: config.action === 'interested' ? 'Want to watch all' : 'Never watch all',
  }));

function getDescendantCounts(rec: Recommendation) {
  return {
    total: rec.descendant_episode_count ?? 0,
    tagged: rec.descendant_feedback_total_count ?? 0,
    interested: rec.descendant_interested_count ?? 0,
    neverWatch: rec.descendant_never_watch_count ?? 0,
    watchedLike: rec.descendant_watched_like_count ?? 0,
    watchedDislike: rec.descendant_watched_dislike_count ?? 0,
  };
}

function getVisibleRecommendationCounts(rec: Recommendation) {
  return {
    episodes: rec.visible_recommendation_episode_count ?? 0,
    seasons: rec.visible_recommendation_season_count ?? 0,
  };
}

function getVisibleRecommendationSummary(rec: Recommendation) {
  const visible = getVisibleRecommendationCounts(rec);
  const typeKey = rec.media_type.toLowerCase();
  const parts = [
    `${visible.episodes} visible ${pluralize(visible.episodes, 'recommendation')}`,
  ];

  if (typeKey === 'show' || typeKey === 'series' || typeKey === 'tv_show') {
    parts.push(`${visible.seasons} visible ${pluralize(visible.seasons, 'season')}`);
  }

  return parts.join(', ');
}

function getAggregateStatusMessage(rec: Recommendation) {
  const counts = getDescendantCounts(rec);
  const visibleSummary = getVisibleRecommendationSummary(rec);
  if (counts.total <= 0) {
    return `${visibleSummary}; no library episodes`;
  }

  const parts = [
    counts.interested > 0 ? `${counts.interested} want to watch` : null,
    counts.neverWatch > 0 ? `${counts.neverWatch} never watch` : null,
    counts.watchedLike > 0 ? `${counts.watchedLike} liked` : null,
    counts.watchedDislike > 0 ? `${counts.watchedDislike} disliked` : null,
  ].filter(Boolean);

  if (parts.length === 0) {
    return `${visibleSummary}; 0 / ${counts.total} library episodes tagged`;
  }

  return `${visibleSummary}; ${counts.tagged} / ${counts.total} library episodes tagged (${parts.join(', ')})`;
}

function getFeedbackStatusMessage(rec: Recommendation) {
  const label = feedbackActionLabel(rec.feedback_state);
  return label ? `Recorded: ${label}` : null;
}

function isBulkActionComplete(rec: Recommendation, action: 'interested' | 'never_watch') {
  const counts = getDescendantCounts(rec);
  if (counts.total <= 0) {
    return true;
  }

  const mutableCount = counts.total - counts.watchedLike - counts.watchedDislike;
  if (mutableCount <= 0) {
    return true;
  }

  return action === 'interested'
    ? counts.interested >= mutableCount
    : counts.neverWatch >= mutableCount;
}

function canDrillIntoRecommendation(rec: Recommendation, viewMode: ViewMode) {
  const visible = getVisibleRecommendationCounts(rec);
  if (viewMode === 'shows') {
    return visible.seasons > 0;
  }
  if (viewMode === 'seasons') {
    return visible.episodes > 0;
  }
  return false;
}

function getEmptyRecommendationsMessage(
  viewMode: ViewMode,
  selectedShow: ScopedSelection | null,
  selectedSeason: ScopedSelection | null,
) {
  if ((viewMode === 'seasons' && selectedShow) || (viewMode === 'episodes' && (selectedShow || selectedSeason))) {
    return 'No visible child recommendations remain at the current threshold or feedback filters.';
  }
  return 'No recommendations match the current filters.';
}

function buildBulkConfirmationMessage(rec: Recommendation, action: 'interested' | 'never_watch') {
  const counts = getDescendantCounts(rec);
  const actionLabel = action === 'interested' ? 'Want to watch all' : 'Never watch all';
  const targetLabel = rec.media_type.toLowerCase() === 'season' ? 'this season' : 'this show';
  return `Apply "${actionLabel}" to all ${counts.total} episodes under ${targetLabel}? Episodes already marked "Watched, liked" or "Watched, disliked" will be left unchanged.`;
}

function buildBulkResultMessage(result: BulkFeedbackApiResponse) {
  const actionLabel = result.feedback === 'interested' ? 'Want to watch' : 'Never watch';
  const skippedMessage = result.skipped_watched_count > 0
    ? ` ${result.skipped_watched_count} watched outcome${result.skipped_watched_count === 1 ? ' was' : 's were'} left unchanged.`
    : '';

  if (result.updated_count > 0) {
    return `Updated ${result.updated_count} of ${result.descendant_total} episodes under ${result.target_title} with "${actionLabel}".${skippedMessage}`;
  }
  return `No descendant episodes changed under ${result.target_title}.${skippedMessage || ' All mutable episodes were already tagged that way.'}`;
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
  search,
  minScore,
  sortOrder,
  offset,
  signal,
}: {
  viewMode: ViewMode;
  selectedShow: ScopedSelection | null;
  selectedSeason: ScopedSelection | null;
  search: string;
  minScore: number;
  sortOrder: SortState[];
  offset: number;
  signal?: AbortSignal;
}) {
  const baseUrl = window.location.origin;
  const params = new URLSearchParams({
    view: viewMode,
    limit: String(RECOMMENDATION_PAGE_LIMIT),
    offset: String(offset),
    min_probability: (minScore / 100).toFixed(4),
  });
  const normalizedSearch = search.trim();
  if (normalizedSearch) {
    params.set('search', normalizedSearch);
  }
  if (selectedShow?.key && (viewMode === 'seasons' || viewMode === 'episodes')) {
    params.set('show_rating_key', String(selectedShow.key));
  }
  if (selectedSeason?.key && viewMode === 'episodes') {
    params.set('season_rating_key', String(selectedSeason.key));
  }
  sortOrder.forEach(({ column, direction }) => {
    params.append('sort', `${String(column)}:${direction}`);
  });

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
    hasMore: Boolean(data.has_more),
    nextOffset: typeof data.next_offset === 'number' ? data.next_offset : null,
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

function RecommendationPoster({
  posterUrl,
  plexItemUrl,
  title,
}: {
  posterUrl?: string | null;
  plexItemUrl?: string | null;
  title: string;
}) {
  const [hasImageError, setHasImageError] = useState(false);

  useEffect(() => {
    setHasImageError(false);
  }, [posterUrl]);

  const poster = !posterUrl || hasImageError ? (
    <span
      aria-hidden="true"
      className="inline-flex h-20 w-14 shrink-0 items-center justify-center overflow-hidden rounded-md border border-gray-200 bg-gray-100 text-[9px] font-semibold uppercase tracking-wide text-gray-400"
    >
      No Art
    </span>
  ) : (
    <img
      src={posterUrl}
      alt=""
      loading="lazy"
      decoding="async"
      onError={() => setHasImageError(true)}
      className="h-20 w-14 shrink-0 rounded-md border border-gray-200 bg-gray-100 object-cover"
    />
  );

  if (!plexItemUrl) {
    return poster;
  }

  return (
    <a
      href={plexItemUrl}
      target="_blank"
      rel="noreferrer"
      aria-label={`Open ${title} in Plex`}
      title={`Open ${title} in Plex`}
      onClick={(event) => event.stopPropagation()}
      className="inline-flex h-20 w-14 shrink-0 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
    >
      {poster}
    </a>
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
  compact = false,
}: {
  rec: Recommendation;
  isPending: boolean;
  statusMessage?: string | null;
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
      {!isPending && statusMessage && (
        <span className="mt-2 text-xs text-gray-500">{statusMessage}</span>
      )}
    </div>
  );
}

function FeedbackActionButtons({
  rec,
  isPending,
  onAction,
  onBulkAction,
  onUndo,
  alwaysVisible = false,
}: {
  rec: Recommendation;
  isPending: boolean;
  onAction: (rec: Recommendation, action: FeedbackAction) => void;
  onBulkAction: (rec: Recommendation, action: 'interested' | 'never_watch') => void;
  onUndo: (rec: Recommendation) => void;
  alwaysVisible?: boolean;
}) {
  if (canSubmitLeafFeedback(rec.media_type)) {
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
        {rec.feedback_state && (
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

  if (!canSubmitBulkFeedback(rec.media_type)) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="space-y-1">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">All episodes</p>
        <div className="flex flex-wrap gap-2">
          {BULK_FEEDBACK_ACTIONS.map((config) => {
            const Icon = config.icon;
            const isComplete = isBulkActionComplete(rec, config.action);
            return (
              <button
                key={config.action}
                type="button"
                aria-label={`${config.bulkLabel} for ${rec.title}`}
                title={config.bulkLabel}
                disabled={isPending || isComplete}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onBulkAction(rec, config.action);
                }}
                className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-60 ${config.className}`}
              >
                <Icon aria-hidden="true" size={14} strokeWidth={2} />
                <span>{config.bulkLabel}</span>
              </button>
            );
          })}
        </div>
      </div>
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
      <RecommendationPoster posterUrl={rec.poster_url} plexItemUrl={rec.plex_item_url} title={rec.title} />
      <div className={isCompact ? 'mt-2' : ''}>
        <p className="text-sm font-semibold leading-tight text-gray-900">{rec.title}</p>
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
  onBulkAction,
  onUndo,
  isRowClickable,
}: {
  recommendations: Recommendation[];
  pendingKeys: number[];
  onSort: (column: keyof Recommendation, shiftKey?: boolean) => void;
  onRowClick: (rec: Recommendation) => void;
  onAction: (rec: Recommendation, action: FeedbackAction) => void;
  onBulkAction: (rec: Recommendation, action: 'interested' | 'never_watch') => void;
  onUndo: (rec: Recommendation) => void;
  isRowClickable: (rec: Recommendation) => boolean;
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
              const canOpenRow = isRowClickable(rec);
              const statusMessage = canSubmitBulkFeedback(rec.media_type)
                ? getAggregateStatusMessage(rec)
                : getFeedbackStatusMessage(rec);

              return (
                <tr
                  key={rec.rating_key}
                  onClick={() => {
                    if (canOpenRow) {
                      onRowClick(rec);
                    }
                  }}
                  className={`group border-b transition-colors duration-300 hover:bg-gray-50 ${canOpenRow ? 'cursor-pointer' : ''}`}
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
                    <RecommendationScore rec={rec} isPending={isPending} statusMessage={statusMessage} />
                  </td>
                  <td className="px-4 py-2">
                    <FeedbackActionButtons
                      rec={rec}
                      isPending={isPending}
                      onAction={onAction}
                      onBulkAction={onBulkAction}
                      onUndo={onUndo}
                      alwaysVisible={false}
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
  onBulkAction,
  onUndo,
  isRowClickable,
}: {
  recommendations: Recommendation[];
  pendingKeys: number[];
  onRowClick: (rec: Recommendation) => void;
  onAction: (rec: Recommendation, action: FeedbackAction) => void;
  onBulkAction: (rec: Recommendation, action: 'interested' | 'never_watch') => void;
  onUndo: (rec: Recommendation) => void;
  isRowClickable: (rec: Recommendation) => boolean;
}) {
  const handleCardKeyDown = (
    event: KeyboardEvent<HTMLDivElement>,
    rec: Recommendation,
  ) => {
    if (!isRowClickable(rec)) {
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
        const canOpenRow = isRowClickable(rec);
        const statusMessage = canSubmitBulkFeedback(rec.media_type)
          ? getAggregateStatusMessage(rec)
          : getFeedbackStatusMessage(rec);

        return (
          <div
            key={rec.rating_key}
            role={canOpenRow ? 'button' : undefined}
            tabIndex={canOpenRow ? 0 : undefined}
            onClick={() => {
              if (canOpenRow) {
                onRowClick(rec);
              }
            }}
            onKeyDown={(event) => handleCardKeyDown(event, rec)}
            className={`rounded-xl border border-gray-200 bg-white p-4 text-gray-900 shadow-sm ${canOpenRow ? 'cursor-pointer active:bg-gray-50' : ''}`}
          >
            <div className="flex items-start justify-between gap-3">
              <MediaTypeBadge mediaType={rec.media_type} />
              <RecommendationScore rec={rec} isPending={isPending} statusMessage={statusMessage} compact />
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
                onBulkAction={onBulkAction}
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
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [darkMode, setDarkMode] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('all');
  const [selectedShow, setSelectedShow] = useState<ScopedSelection | null>(null);
  const [selectedSeason, setSelectedSeason] = useState<ScopedSelection | null>(null);
  const [minScore, setMinScore] = useState(70);
  const [plexUser, setPlexUser] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [pendingKeys, setPendingKeys] = useState<number[]>([]);
  const [pageError, setPageError] = useState<string | null>(null);
  const [pageMessage, setPageMessage] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<SortState[]>([]);
  const [undoState, setUndoState] = useState<UndoState | null>(null);
  const [emailPreferences, setEmailPreferences] = useState<EmailPreferencesResponse | null>(null);
  const [emailPreferencesBusy, setEmailPreferencesBusy] = useState(false);
  const [emailPreferencesError, setEmailPreferencesError] = useState<string | null>(null);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedSearch(search);
    }, 300);
    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [search]);

  const applyRecommendationsData = (data: RecommendationsResponse, append = false) => {
    const normalized = normalizeRecommendationsResponse(data);
    setRecs((prev) => {
      if (!append) {
        return normalized.recommendations;
      }
      const existingKeys = new Set(prev.map((rec) => rec.rating_key));
      return [
        ...prev,
        ...normalized.recommendations.filter((rec) => !existingKeys.has(rec.rating_key)),
      ];
    });
    setPlexUser(normalized.username);
    setLastUpdated(normalized.lastUpdated);
    setHasMore(normalized.hasMore);
    setNextOffset(normalized.nextOffset);
  };

  const refreshRecommendations = async (signal?: AbortSignal, append = false, offset = 0) => {
    const data = await loadRecommendationsData({
      viewMode,
      selectedShow,
      selectedSeason,
      search: debouncedSearch,
      minScore,
      sortOrder,
      offset,
      signal,
    });
    applyRecommendationsData(data, append);
  };

  useEffect(() => {
    const controller = new AbortController();

    setIsLoadingRecommendations(true);
    refreshRecommendations(controller.signal)
      .then(() => {
        if (controller.signal.aborted) {
          return;
        }
        setPageError(null);
      })
      .catch((error) => {
        if (controller.signal.aborted) {
          return;
        }
        console.error(error);
        setPageError(error instanceof Error ? error.message : 'Failed to load recommendations.');
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoadingRecommendations(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [viewMode, selectedShow, selectedSeason, debouncedSearch, minScore, sortOrder]);

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

  useEffect(() => {
    let mounted = true;

    fetch('/api/me/email-preferences', { credentials: 'include' })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(await extractErrorMessage(res, `Failed to load email preferences (${res.status})`));
        }
        return res.json() as Promise<EmailPreferencesResponse>;
      })
      .then((data) => {
        if (!mounted) return;
        setEmailPreferences(data);
      })
      .catch((error) => {
        if (!mounted) return;
        setEmailPreferencesError(error instanceof Error ? error.message : 'Failed to load email preferences.');
      });

    return () => {
      mounted = false;
    };
  }, []);

  const updateEmailPreference = async (enabled: boolean) => {
    if (!emailPreferences) return;
    setEmailPreferencesBusy(true);
    setEmailPreferencesError(null);
    try {
      const res = await fetch('/api/me/email-preferences', {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ digest_enabled: enabled }),
      });
      if (!res.ok) {
        throw new Error(await extractErrorMessage(res, `Failed to update email preferences (${res.status})`));
      }
      const data = await res.json() as EmailPreferencesResponse;
      setEmailPreferences(data);
      setPageMessage(enabled ? 'Recommendation emails enabled.' : 'Recommendation emails disabled.');
    } catch (error) {
      setEmailPreferencesError(error instanceof Error ? error.message : 'Failed to update email preferences.');
    } finally {
      setEmailPreferencesBusy(false);
    }
  };

  const sendFeedback = async (rec: Recommendation, action: FeedbackAction) => {
    if (!plexUser) {
      setPageError('Unable to submit feedback: user session is missing.');
      return;
    }
    if (pendingKeys.includes(rec.rating_key)) {
      return;
    }

    setPageError(null);
    setPageMessage(null);
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
      const savedAction = returnedFeedback?.feedback ?? action;
      const savedRec: Recommendation = {
        ...rec,
        feedback_state: savedAction,
        feedback_suppress: returnedFeedback?.suppress ?? savedAction !== 'interested',
        feedback_reason_code: returnedFeedback?.reason_code ?? savedAction,
        plex_watchlist_status: returnedFeedback?.plex_watchlist_status ?? 'not_applicable',
      };

      setRecs((prev) => prev.map((item) => (
        item.rating_key === rec.rating_key ? { ...item, ...savedRec } : item
      )));
      setUndoState({
        recommendation: savedRec,
        action: savedAction,
      });
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
    setPageMessage(null);
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

  const sendBulkFeedback = async (rec: Recommendation, action: 'interested' | 'never_watch') => {
    if (!plexUser) {
      setPageError('Unable to submit feedback: user session is missing.');
      return;
    }
    if (pendingKeys.includes(rec.rating_key) || isBulkActionComplete(rec, action)) {
      return;
    }
    if (!window.confirm(buildBulkConfirmationMessage(rec, action))) {
      return;
    }

    setPageError(null);
    setPageMessage(null);
    setPendingKeys((prev) => (prev.includes(rec.rating_key) ? prev : [...prev, rec.rating_key]));

    try {
      const res = await fetch('/api/feedback/bulk', {
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
        throw new Error(await extractErrorMessage(res, `Failed to submit bulk feedback (${res.status})`));
      }

      const result = await res.json() as BulkFeedbackApiResponse;
      await refreshRecommendations();
      setPageMessage(buildBulkResultMessage(result));
    } catch (error) {
      console.error(error);
      setPageError(error instanceof Error ? error.message : 'Failed to submit bulk feedback.');
    } finally {
      setPendingKeys((prev) => prev.filter((key) => key !== rec.rating_key));
    }
  };

  const loadMoreRecommendations = async () => {
    if (!hasMore || nextOffset == null || isLoadingMore) {
      return;
    }

    setIsLoadingMore(true);
    setPageError(null);
    try {
      await refreshRecommendations(undefined, true, nextOffset);
    } catch (error) {
      console.error(error);
      setPageError(error instanceof Error ? error.message : 'Failed to load more recommendations.');
    } finally {
      setIsLoadingMore(false);
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
    setPageMessage(null);
  };

  const handleRowClick = (rec: Recommendation) => {
    if (!canDrillIntoRecommendation(rec, viewMode)) {
      return;
    }
    if (viewMode === 'shows') {
      const showKey = rec.show_rating_key ?? rec.rating_key;
      if (!showKey) return;
      setSelectedShow({ key: showKey, title: rec.title });
      setSelectedSeason(null);
      setViewMode('seasons');
      setPageMessage(null);
    } else if (viewMode === 'seasons') {
      const showKey = rec.show_rating_key;
      if (showKey && !selectedShow) {
        setSelectedShow({ key: showKey, title: rec.show_title || 'Show' });
      }
      setSelectedSeason({ key: rec.rating_key, title: rec.title });
      setViewMode('episodes');
      setPageMessage(null);
    }
  };

  const isRowClickable = (rec: Recommendation) => canDrillIntoRecommendation(rec, viewMode);
  const emptyRecommendationsMessage = getEmptyRecommendationsMessage(viewMode, selectedShow, selectedSeason);

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

      {emailPreferences && (
        <div className="mb-4 rounded-md border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-slate-700">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-medium text-slate-900">Recommendation emails</p>
              <p className="mt-1 text-slate-600">
                {emailPreferences.has_email
                  ? `Scheduled digests will be sent to ${emailPreferences.email}.`
                  : 'No email address is currently available for this account.'}
              </p>
              {emailPreferencesError && (
                <p className="mt-2 text-xs text-red-600">{emailPreferencesError}</p>
              )}
            </div>
            <label className="inline-flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={emailPreferences.digest_enabled}
                disabled={emailPreferencesBusy || !emailPreferences.has_email}
                onChange={(event) => void updateEmailPreference(event.target.checked)}
              />
              <span>{emailPreferences.digest_enabled ? 'Emails enabled' : 'Emails disabled'}</span>
            </label>
          </div>
        </div>
      )}

      {undoState && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
          <span>
            {feedbackActionLabel(undoState.action)} recorded for <span className="font-medium">{undoState.recommendation.title}</span>.
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
      </div>

      {pageError && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          Error: {pageError}
        </div>
      )}

      {pageMessage && (
        <div className="mb-4 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">
          {pageMessage}
        </div>
      )}

      {(viewMode === 'seasons' || viewMode === 'episodes') && selectedShow && (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-gray-600">
          <button
            onClick={() => {
              setSelectedSeason(null);
              setViewMode('shows');
              setPageMessage(null);
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
                  setPageMessage(null);
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

      {isLoadingRecommendations && recs.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white px-4 py-6 text-sm text-gray-500 shadow-sm">
          Loading recommendations...
        </div>
      ) : recs.length === 0 ? (
        <div className="rounded-xl border border-gray-200 bg-white px-4 py-6 text-sm text-gray-500 shadow-sm">
          {emptyRecommendationsMessage}
        </div>
      ) : (
        <>
          <MobileRecommendationsList
            recommendations={recs}
            pendingKeys={pendingKeys}
            onRowClick={handleRowClick}
            onAction={sendFeedback}
            onBulkAction={sendBulkFeedback}
            onUndo={undoFeedback}
            isRowClickable={isRowClickable}
          />
          <DesktopRecommendationsTable
            recommendations={recs}
            pendingKeys={pendingKeys}
            onSort={handleSort}
            onRowClick={handleRowClick}
            onAction={sendFeedback}
            onBulkAction={sendBulkFeedback}
            onUndo={undoFeedback}
            isRowClickable={isRowClickable}
          />
          <div className="mt-4 flex items-center justify-center">
            {hasMore ? (
              <button
                type="button"
                onClick={() => void loadMoreRecommendations()}
                disabled={isLoadingMore}
                className="inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoadingMore ? 'Loading...' : 'Load more'}
              </button>
            ) : (
              <span className="text-sm text-gray-500">Showing all loaded matches</span>
            )}
          </div>
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
