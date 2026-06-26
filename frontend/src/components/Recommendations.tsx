import { useEffect, useState, type KeyboardEvent } from 'react';
import {
  AlertCircle,
  ArrowDown,
  ArrowUp,
  Ban,
  BookmarkPlus,
  CheckCircle2,
  ChevronRight,
  Clapperboard,
  Layers,
  Loader2,
  Moon,
  Play,
  RotateCcw,
  Search,
  Sun,
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
  title_traits: string[];
  taste_match: string[];
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
  is_refreshing?: boolean;
  has_more?: boolean;
  next_offset?: number | null;
  limit?: number;
  offset?: number;
}

interface RecommendationRefreshStatusResponse {
  is_refreshing?: boolean;
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

const MEDIA_TYPE_ICONS: Record<string, { icon: LucideIcon; label: string; className: string; badgeClassName: string }> = {
  movie: { icon: Clapperboard, label: 'Movie', className: 'text-rose-600', badgeClassName: 'border-rose-100 bg-rose-50 text-rose-700' },
  movies: { icon: Clapperboard, label: 'Movie', className: 'text-rose-600', badgeClassName: 'border-rose-100 bg-rose-50 text-rose-700' },
  show: { icon: Tv, label: 'Show', className: 'text-sky-600', badgeClassName: 'border-sky-100 bg-sky-50 text-sky-700' },
  shows: { icon: Tv, label: 'Show', className: 'text-sky-600', badgeClassName: 'border-sky-100 bg-sky-50 text-sky-700' },
  series: { icon: Tv, label: 'Show', className: 'text-sky-600', badgeClassName: 'border-sky-100 bg-sky-50 text-sky-700' },
  tv_show: { icon: Tv, label: 'Show', className: 'text-sky-600', badgeClassName: 'border-sky-100 bg-sky-50 text-sky-700' },
  season: { icon: Layers, label: 'Season', className: 'text-amber-600', badgeClassName: 'border-amber-100 bg-amber-50 text-amber-700' },
  seasons: { icon: Layers, label: 'Season', className: 'text-amber-600', badgeClassName: 'border-amber-100 bg-amber-50 text-amber-700' },
  episode: { icon: Play, label: 'Episode', className: 'text-emerald-600', badgeClassName: 'border-emerald-100 bg-emerald-50 text-emerald-700' },
  episodes: { icon: Play, label: 'Episode', className: 'text-emerald-600', badgeClassName: 'border-emerald-100 bg-emerald-50 text-emerald-700' },
};
const RECOMMENDATION_PAGE_LIMIT = 100;

const VIEW_MODE_OPTIONS: Array<{ value: ViewMode; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'movies', label: 'Movies' },
  { value: 'shows', label: 'Shows' },
  { value: 'seasons', label: 'Seasons' },
  { value: 'episodes', label: 'Episodes' },
];

function getScoreColorClasses(scorePct: number) {
  if (scorePct >= 80) {
    return {
      text: 'text-emerald-700',
      bar: 'bg-emerald-500',
      badge: 'border-emerald-200 bg-emerald-50 text-emerald-800 ring-emerald-200',
    };
  }
  if (scorePct >= 60) {
    return {
      text: 'text-amber-700',
      bar: 'bg-amber-500',
      badge: 'border-amber-200 bg-amber-50 text-amber-800 ring-amber-200',
    };
  }
  return {
    text: 'text-slate-600',
    bar: 'bg-slate-400',
    badge: 'border-slate-200 bg-slate-50 text-slate-700 ring-slate-200',
  };
}

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

async function loadRecommendationRefreshStatus(signal?: AbortSignal) {
  const res = await fetch('/api/recommendations/refresh-status', {
    credentials: 'include',
    signal,
  });
  if (!res.ok) {
    throw new Error(await extractErrorMessage(res, `Failed to load refresh status (${res.status})`));
  }
  const data = await res.json() as RecommendationRefreshStatusResponse;
  return Boolean(data.is_refreshing);
}

function normalizeRecommendationsResponse(data: RecommendationsResponse) {
  return {
    recommendations: Array.isArray(data.recommendations) ? data.recommendations : [],
    username: typeof data.username === 'string' ? data.username : null,
    lastUpdated: typeof data.last_updated === 'string' ? data.last_updated : null,
    isRefreshing: Boolean(data.is_refreshing),
    hasMore: Boolean(data.has_more),
    nextOffset: typeof data.next_offset === 'number' ? data.next_offset : null,
  };
}

function MediaTypeIcon({ mediaType }: { mediaType: string }) {
  const iconConfig = getMediaTypeConfig(mediaType);

  if (!iconConfig) {
    return <span className="text-xs uppercase tracking-wide text-slate-500">{mediaType}</span>;
  }

  const Icon = iconConfig.icon;

  return (
    <span
      className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border ${iconConfig.badgeClassName}`}
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
    return <span className="text-xs uppercase tracking-wide text-slate-500">{mediaType}</span>;
  }

  const Icon = iconConfig.icon;

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${iconConfig.badgeClassName}`}>
      <Icon aria-hidden="true" size={14} strokeWidth={2} />
      <span>{iconConfig.label}</span>
    </span>
  );
}

function RecommendationPoster({
  posterUrl,
  plexItemUrl,
  title,
  size = 'desktop',
}: {
  posterUrl?: string | null;
  plexItemUrl?: string | null;
  title: string;
  size?: 'desktop' | 'mobile';
}) {
  const [hasImageError, setHasImageError] = useState(false);
  const sizeClass = size === 'mobile' ? 'h-24 w-16' : 'h-20 w-14';

  useEffect(() => {
    setHasImageError(false);
  }, [posterUrl]);

  const poster = !posterUrl || hasImageError ? (
    <span
      aria-hidden="true"
      className={`inline-flex ${sizeClass} shrink-0 items-center justify-center overflow-hidden rounded-lg border border-amber-100 bg-amber-50/60 text-[9px] font-semibold uppercase tracking-wide text-amber-400 shadow-sm`}
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
      className={`${sizeClass} shrink-0 rounded-lg border border-slate-200/80 bg-slate-100 object-cover shadow-sm`}
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
      className={`inline-flex ${sizeClass} shrink-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400`}
    >
      {poster}
    </a>
  );
}

function RecommendationChipGroup({
  label,
  chips,
  chipClassName,
  compact,
}: {
  label: string;
  chips: string[];
  chipClassName: string;
  compact: boolean;
}) {
  if (chips.length === 0) {
    return null;
  }

  return (
    <div className="min-w-0">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <div className="flex flex-wrap gap-1">
        {chips.map((chip, index) => (
          <span
            key={`${chip}-${index}`}
            className={`inline-block min-w-0 max-w-full whitespace-normal break-words rounded-full border text-left leading-snug ${chipClassName} ${compact ? 'px-2 py-0.5 text-[11px]' : 'px-2 py-0.5 text-xs'}`}
          >
            {chip}
          </span>
        ))}
      </div>
    </div>
  );
}

function RecommendationExplanation({
  titleTraits,
  tasteMatch,
  compact = false,
}: {
  titleTraits: string[];
  tasteMatch: string[];
  compact?: boolean;
}) {
  const safeTitleTraits = Array.isArray(titleTraits) ? titleTraits : [];
  const safeTasteMatch = Array.isArray(tasteMatch) ? tasteMatch : [];

  if (safeTitleTraits.length === 0 && safeTasteMatch.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2">
      <RecommendationChipGroup
        label="Title Traits"
        chips={safeTitleTraits}
        chipClassName="border-blue-100 bg-blue-50/80 text-blue-800"
        compact={compact}
      />
      <RecommendationChipGroup
        label="Taste Match"
        chips={safeTasteMatch}
        chipClassName="border-emerald-100 bg-emerald-50/80 text-emerald-800"
        compact={compact}
      />
    </div>
  );
}

function RecommendationScore({
  rec,
  isPending,
  statusMessage,
  compact = false,
  badge = false,
}: {
  rec: Recommendation;
  isPending: boolean;
  statusMessage?: string | null;
  compact?: boolean;
  badge?: boolean;
}) {
  const scorePct = rec.predicted_probability * 100;
  const colors = getScoreColorClasses(scorePct);

  if (badge) {
    return (
      <div className="flex flex-col items-end text-right">
        <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-sm font-bold ring-2 ring-inset ${colors.badge}`}>
          {scorePct.toFixed(1)}%
        </span>
        {rec.score_band && (
          <span className="mt-1 text-[10px] text-slate-500">Band: {rec.score_band}</span>
        )}
        {isPending && (
          <span className="mt-1 text-[10px] text-slate-500">Saving...</span>
        )}
        {!isPending && statusMessage && (
          <span className="mt-1 max-w-[10rem] text-[10px] leading-snug text-slate-500">{statusMessage}</span>
        )}
      </div>
    );
  }

  return (
    <div className={`flex flex-col ${compact ? 'items-end text-right' : ''}`}>
      <span className={`font-semibold ${colors.text} ${compact ? 'text-lg leading-none' : 'mb-1 text-sm'}`}>
        {scorePct.toFixed(1)}%
      </span>
      <div className={`w-full rounded-full bg-slate-200 ${compact ? 'mt-2 h-1.5 max-w-[6rem]' : 'h-2'}`}>
        <div
          className={`rounded-full ${colors.bar} ${compact ? 'h-1.5' : 'h-2'}`}
          style={{ width: `${scorePct.toFixed(0)}%` }}
        />
      </div>
      {rec.score_band && (
        <span className="mt-2 text-xs text-slate-500">Band: {rec.score_band}</span>
      )}
      {isPending && (
        <span className="mt-2 text-xs text-slate-500">Saving feedback...</span>
      )}
      {!isPending && statusMessage && (
        <span className="mt-2 text-xs text-slate-500">{statusMessage}</span>
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
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{groupLabel}</p>
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
                    className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 disabled:cursor-not-allowed disabled:opacity-60 ${isActive ? config.activeClassName : config.className}`}
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
            className="recs-btn-secondary"
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
        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">All episodes</p>
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
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 disabled:cursor-not-allowed disabled:opacity-60 ${config.className}`}
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
  layout = 'desktop',
}: {
  rec: Recommendation;
  layout?: 'desktop' | 'mobile';
}) {
  if (layout === 'mobile') {
    return (
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <RecommendationPoster posterUrl={rec.poster_url} plexItemUrl={rec.plex_item_url} title={rec.title} size="mobile" />
        <div className="min-w-0 flex-1">
          <p className="text-base font-semibold leading-tight text-slate-900">{rec.title}</p>
          <div className="mt-1 space-y-0.5 text-sm text-slate-600">
            {[
              rec.show_title,
              [
                rec.season_number != null ? `S${rec.season_number}` : null,
                rec.episode_number != null ? `E${rec.episode_number}` : null,
              ].filter(Boolean).join(' • ') || null,
              rec.year != null ? String(rec.year) : null,
            ]
              .filter(Boolean)
              .join(' • ')}
            {rec.genres && (
              <p className="truncate text-xs text-slate-500">{rec.genres}</p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <RecommendationPoster posterUrl={rec.poster_url} plexItemUrl={rec.plex_item_url} title={rec.title} />
      <div>
        <p className="text-sm font-semibold leading-tight text-slate-900">{rec.title}</p>
      </div>
    </div>
  );
}

function SortableTableHeader({
  label,
  column,
  sortOrder,
  onSort,
}: {
  label: string;
  column: keyof Recommendation;
  sortOrder: SortState[];
  onSort: (column: keyof Recommendation, shiftKey?: boolean) => void;
}) {
  const activeSort = sortOrder.find((sort) => sort.column === column);

  return (
    <th
      className="cursor-pointer select-none px-4 py-3 transition-colors hover:text-slate-900"
      onClick={(event) => onSort(column, event.shiftKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {activeSort && (
          activeSort.direction === 'asc'
            ? <ArrowUp aria-hidden="true" size={12} strokeWidth={2} />
            : <ArrowDown aria-hidden="true" size={12} strokeWidth={2} />
        )}
      </span>
    </th>
  );
}

function DesktopRecommendationsTable({
  recommendations,
  pendingKeys,
  sortOrder,
  onSort,
  onRowClick,
  onAction,
  onBulkAction,
  onUndo,
  isRowClickable,
}: {
  recommendations: Recommendation[];
  pendingKeys: number[];
  sortOrder: SortState[];
  onSort: (column: keyof Recommendation, shiftKey?: boolean) => void;
  onRowClick: (rec: Recommendation) => void;
  onAction: (rec: Recommendation, action: FeedbackAction) => void;
  onBulkAction: (rec: Recommendation, action: 'interested' | 'never_watch') => void;
  onUndo: (rec: Recommendation) => void;
  isRowClickable: (rec: Recommendation) => boolean;
}) {
  return (
    <div className="recs-surface hidden overflow-hidden md:block">
      <div className="max-h-[70vh] overflow-auto">
        <table className="min-w-full text-slate-900">
          <thead className="sticky top-0 z-10 bg-slate-50/95 backdrop-blur">
            <tr className="border-b border-slate-200 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              <th className="px-4 py-3 text-center">Type</th>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Show</th>
              <SortableTableHeader label="Season" column="season_number" sortOrder={sortOrder} onSort={onSort} />
              <SortableTableHeader label="Episode" column="episode_number" sortOrder={sortOrder} onSort={onSort} />
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
                  className={`group border-b border-slate-100 transition-colors duration-200 hover:bg-amber-50/30 ${canOpenRow ? 'cursor-pointer hover:border-l-2 hover:border-l-amber-400' : ''}`}
                >
                  <td className="px-4 py-3 text-center">
                    <MediaTypeIcon mediaType={rec.media_type} />
                  </td>
                  <td className="px-4 py-3">
                    <RecommendationTitleCell rec={rec} />
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-700">{rec.show_title || '—'}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{rec.season_number ?? '—'}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{rec.episode_number ?? '—'}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{rec.year ?? '—'}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{rec.genres || '—'}</td>
                  <td className="px-4 py-3">
                    {(rec.title_traits?.length ?? 0) === 0 && (rec.taste_match?.length ?? 0) === 0 ? (
                      '—'
                    ) : (
                      <RecommendationExplanation
                        titleTraits={rec.title_traits}
                        tasteMatch={rec.taste_match}
                      />
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <RecommendationScore rec={rec} isPending={isPending} statusMessage={statusMessage} />
                  </td>
                  <td className="px-4 py-3">
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
        const hasExplanation = (rec.title_traits?.length ?? 0) > 0 || (rec.taste_match?.length ?? 0) > 0;

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
            className={`recs-surface p-4 transition-transform ${canOpenRow ? 'cursor-pointer active:scale-[0.99] active:bg-amber-50/20' : ''}`}
          >
            <div className="flex items-start justify-between gap-3">
              <MediaTypeBadge mediaType={rec.media_type} />
              <RecommendationScore rec={rec} isPending={isPending} statusMessage={statusMessage} badge />
            </div>

            <div className="mt-3">
              <RecommendationTitleCell rec={rec} layout="mobile" />
            </div>

            {hasExplanation && (
              <details className="mt-4 group/details">
                <summary className="cursor-pointer list-none text-xs font-semibold uppercase tracking-wide text-slate-500 [&::-webkit-details-marker]:hidden">
                  <span className="inline-flex items-center gap-1">
                    Why this?
                    <ChevronRight aria-hidden="true" size={14} className="transition-transform group-open/details:rotate-90" />
                  </span>
                </summary>
                <div className="mt-2">
                  <RecommendationExplanation
                    titleTraits={rec.title_traits}
                    tasteMatch={rec.taste_match}
                    compact
                  />
                </div>
              </details>
            )}

            <div className="mt-4 border-t border-slate-100 pt-4">
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

function RecommendationsLoadingSkeleton() {
  return (
    <>
      <div className="space-y-3 md:hidden">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={`mobile-skeleton-${index}`} className="recs-surface animate-pulse p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="h-6 w-20 rounded-full bg-slate-200" />
              <div className="h-8 w-14 rounded-full bg-slate-200" />
            </div>
            <div className="mt-3 flex gap-3">
              <div className="h-24 w-16 shrink-0 rounded-lg bg-slate-200" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-3/4 rounded bg-slate-200" />
                <div className="h-3 w-1/2 rounded bg-slate-200" />
                <div className="h-3 w-2/3 rounded bg-slate-200" />
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="recs-surface hidden animate-pulse overflow-hidden md:block">
        <div className="space-y-0 p-4">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={`desktop-skeleton-${index}`} className="flex items-center gap-4 border-b border-slate-100 py-4 last:border-b-0">
              <div className="h-8 w-8 rounded-lg bg-slate-200" />
              <div className="h-20 w-14 rounded-lg bg-slate-200" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-1/3 rounded bg-slate-200" />
                <div className="h-3 w-1/4 rounded bg-slate-200" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function RecommendationsEmptyState({ message }: { message: string }) {
  return (
    <div className="recs-surface-muted px-6 py-10 text-center">
      <p className="text-sm text-slate-600">{message}</p>
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
  const [isRefreshing, setIsRefreshing] = useState(false);
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
    setIsRefreshing(normalized.isRefreshing);
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
    let requestInFlight = false;
    const controller = new AbortController();

    const refreshStatus = () => {
      if (requestInFlight) {
        return;
      }
      requestInFlight = true;
      loadRecommendationRefreshStatus(controller.signal)
        .then((nextIsRefreshing) => {
          if (!mounted) return;
          setIsRefreshing(nextIsRefreshing);
        })
        .catch((error) => {
          if (!mounted || controller.signal.aborted) return;
          console.error(error);
        })
        .finally(() => {
          requestInFlight = false;
        });
    };

    refreshStatus();
    const intervalId = window.setInterval(refreshStatus, 15000);

    return () => {
      mounted = false;
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, []);

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
    <div className={`recs-page ${darkMode ? 'recs-dark' : ''}`}>
      <div className="mx-auto w-full max-w-7xl overflow-x-hidden px-3 py-6 sm:px-4 sm:py-8">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">
              Recommendations for {recs[0]?.friendly_name || plexUser || 'user'}
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {lastUpdated && (
                <span className="recs-pill-slate">
                  Last updated {new Date(lastUpdated).toLocaleString()}
                </span>
              )}
              {isRefreshing && (
                <span className="recs-pill-amber">
                  <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
                  Refreshing recommendations
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isAdmin && (
              <Link to="/admin" className="recs-btn-secondary px-4 py-2 text-sm">
                Admin View
              </Link>
            )}
            <button
              type="button"
              onClick={() => setDarkMode(!darkMode)}
              className="recs-btn-secondary px-3 py-2"
              aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
              aria-pressed={darkMode}
            >
              {darkMode ? (
                <Sun aria-hidden="true" size={16} strokeWidth={2} />
              ) : (
                <Moon aria-hidden="true" size={16} strokeWidth={2} />
              )}
              <span className="sr-only">{darkMode ? 'Light mode' : 'Dark mode'}</span>
            </button>
          </div>
        </div>

        {isRefreshing && (
          <div className="mb-4 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <Loader2 aria-hidden="true" className="mt-0.5 shrink-0 animate-spin text-amber-600" size={16} strokeWidth={2} />
            <p>Recommendations are currently being refreshed. You are seeing the last best version.</p>
          </div>
        )}

        {emailPreferences && (
          <div className="recs-surface mb-4 overflow-hidden">
            <div className="border-b border-slate-100 bg-slate-50/80 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Email preferences</p>
            </div>
            <div className="flex flex-col gap-3 px-4 py-4 text-sm text-slate-700 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-medium text-slate-900">Recommendation emails</p>
                <p className="mt-1 text-slate-600">
                  {emailPreferences.has_email
                    ? `Scheduled digests will be sent to ${emailPreferences.email}.`
                    : 'No email address is currently available for this account.'}
                </p>
                {emailPreferencesError && (
                  <p className="mt-2 flex items-center gap-1 text-xs text-red-600">
                    <AlertCircle aria-hidden="true" size={14} />
                    {emailPreferencesError}
                  </p>
                )}
              </div>
              <label className="inline-flex cursor-pointer items-center gap-3 text-sm text-slate-800">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300 text-amber-600 focus:ring-amber-400"
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
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <span className="flex items-center gap-2">
              <CheckCircle2 aria-hidden="true" size={16} className="text-amber-700" />
              {feedbackActionLabel(undoState.action)} recorded for <span className="font-medium">{undoState.recommendation.title}</span>.
            </span>
            <button
              type="button"
              onClick={() => undoFeedback(undoState.recommendation)}
              className="recs-btn-secondary bg-white"
            >
              <RotateCcw aria-hidden="true" size={14} strokeWidth={2} />
              <span>Undo</span>
            </button>
          </div>
        )}

        <div className="recs-surface mb-4 p-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">Filters</p>
          <div className="space-y-4">
            <div className="relative">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                size={16}
                strokeWidth={2}
              />
              <input
                type="text"
                placeholder="Search by title, show, genre, or theme..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="recs-input pl-9"
              />
            </div>

            <div>
              <p className="mb-2 text-xs font-medium text-slate-600">View</p>
              <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 snap-x snap-mandatory">
                {VIEW_MODE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => handleViewSelect(option.value)}
                    className={viewMode === option.value ? 'recs-view-pill-active' : 'recs-view-pill-inactive'}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between">
                <label htmlFor="score-range" className="text-xs font-medium text-slate-600">
                  Minimum score
                </label>
                <span className="recs-pill-amber font-semibold">{minScore}%</span>
              </div>
              <input
                id="score-range"
                type="range"
                min="0"
                max="100"
                step="1"
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="recs-score-slider"
              />
            </div>
          </div>
        </div>

        {pageError && (
          <div className="mb-4 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle aria-hidden="true" className="mt-0.5 shrink-0" size={16} strokeWidth={2} />
            <p>Error: {pageError}</p>
          </div>
        )}

        {pageMessage && (
          <div className="mb-4 flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
            <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0" size={16} strokeWidth={2} />
            <p>{pageMessage}</p>
          </div>
        )}

        {(viewMode === 'seasons' || viewMode === 'episodes') && selectedShow && (
          <nav aria-label="Drill-down navigation" className="mb-4 flex flex-wrap items-center gap-2 text-sm">
            <button
              type="button"
              onClick={() => {
                setSelectedSeason(null);
                setViewMode('shows');
                setPageMessage(null);
              }}
              className="recs-breadcrumb-pill"
            >
              Shows
            </button>
            <ChevronRight aria-hidden="true" size={14} className="text-slate-400" />
            <span className="recs-pill-slate max-w-[12rem] truncate" title={selectedShow.title}>
              {selectedShow.title}
            </span>
            {viewMode === 'episodes' && selectedSeason && (
              <>
                <ChevronRight aria-hidden="true" size={14} className="text-slate-400" />
                <button
                  type="button"
                  onClick={() => {
                    setSelectedSeason(null);
                    setViewMode('seasons');
                    setPageMessage(null);
                  }}
                  className="recs-breadcrumb-pill"
                >
                  Seasons
                </button>
                <ChevronRight aria-hidden="true" size={14} className="text-slate-400" />
                <span className="recs-pill-slate max-w-[12rem] truncate" title={selectedSeason.title}>
                  {selectedSeason.title}
                </span>
              </>
            )}
          </nav>
        )}

        {isLoadingRecommendations && recs.length === 0 ? (
          <RecommendationsLoadingSkeleton />
        ) : recs.length === 0 ? (
          <RecommendationsEmptyState message={emptyRecommendationsMessage} />
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
              sortOrder={sortOrder}
              onSort={handleSort}
              onRowClick={handleRowClick}
              onAction={sendFeedback}
              onBulkAction={sendBulkFeedback}
              onUndo={undoFeedback}
              isRowClickable={isRowClickable}
            />
            <div className="mt-6 flex items-center justify-center">
              {hasMore ? (
                <button
                  type="button"
                  onClick={() => void loadMoreRecommendations()}
                  disabled={isLoadingMore}
                  className="recs-btn-secondary px-5 py-2.5 text-sm"
                >
                  {isLoadingMore ? (
                    <>
                      <Loader2 aria-hidden="true" className="animate-spin" size={16} strokeWidth={2} />
                      Loading...
                    </>
                  ) : (
                    'Load more'
                  )}
                </button>
              ) : (
                <span className="text-sm text-slate-500">Showing all loaded matches</span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
