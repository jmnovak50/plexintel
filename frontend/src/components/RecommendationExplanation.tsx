// Factual Taste Match consumes the existing connection; selection stays server-side.
export type ViewingHistoryConnection = { display_text: string };

export function factualTasteMatch(connection?: ViewingHistoryConnection | null): string | null {
  const text = connection?.display_text;
  return typeof text === 'string' && text.trim() ? text : null;
}

export function hasRecommendationExplanation(titleTraits: string[], connection?: ViewingHistoryConnection | null): boolean {
  return (Array.isArray(titleTraits) && titleTraits.length > 0) || factualTasteMatch(connection) !== null;
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

export function RecommendationExplanation({ titleTraits, connection, compact = false }: {
  titleTraits: string[];
  connection?: ViewingHistoryConnection | null;
  compact?: boolean;
}) {
  const safeTitleTraits = Array.isArray(titleTraits) ? titleTraits : [];
  const tasteMatch = factualTasteMatch(connection);
  if (!safeTitleTraits.length && !tasteMatch) return null;
  return (
    <div className="flex flex-col gap-2">
      <RecommendationChipGroup
        label="Title Traits"
        chips={safeTitleTraits}
        chipClassName="border-blue-100 bg-blue-50/80 text-blue-800"
        compact={compact}
      />
      {tasteMatch && (
        <section className="min-w-0">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">Taste Match</p>
          <p className={`rounded-lg border border-emerald-100 bg-emerald-50/80 px-3 py-2 leading-relaxed text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200 whitespace-normal break-words ${compact ? 'text-xs' : 'text-sm'}`}>{tasteMatch}</p>
        </section>
      )}
    </div>
  );
}
