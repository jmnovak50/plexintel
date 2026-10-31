import { FOUNDATION_CONTENT } from '../lib/contentLifecycle';
export interface Counts {total:number;excluded:number;retained:number;incomplete:number;movies:number;tv:number}
export function EligibilityFunnel({counts}:{counts:Counts}) {
  return <section className="recs-panel p-5" aria-label="Discovery to retained population">
    <h2 className="mb-4 text-lg font-semibold">Discovery → definitive exclusions → retained subset</h2>
    <div className="grid gap-3 sm:grid-cols-3">{[['Discovered superset',counts.total],['Definitively excluded',counts.excluded],['Retained for future engagement',counts.retained]].map(([label,count])=><div key={label} className="rounded-lg border border-slate-300 p-4"><p className="text-sm">{label}</p><p className="text-3xl font-semibold">{Number(count).toLocaleString()}</p></div>)}</div>
    <div className="mt-4 flex h-4 overflow-hidden rounded bg-slate-200" aria-hidden="true"><div className="bg-red-500" style={{width:`${counts.total?100*counts.excluded/counts.total:0}%`}}/><div className="bg-emerald-500" style={{width:`${counts.total?100*counts.retained/counts.total:0}%`}}/></div>
    <p className="mt-3 text-sm">{counts.incomplete.toLocaleString()} titles have incomplete exclusion evidence. Uncertainty can coexist with a definitive exclusion under another rule. Retained means no definitive exclusion; it is not a prediction or acquisition decision.</p>
  </section>;
}

export function FoundationSections({stage}:{stage:keyof typeof FOUNDATION_CONTENT}) {
  return <div className="space-y-4"><p role="status" className="recs-panel p-4">Foundation only — functionality is not implemented.</p>{FOUNDATION_CONTENT[stage].sections.map(([title,body])=><section className="recs-panel p-5" key={title}><h2 className="text-lg font-semibold">{title}</h2><p className="mt-2 text-sm text-slate-600">{body}</p></section>)}</div>;
}
