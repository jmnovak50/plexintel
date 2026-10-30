import type { ReactNode } from 'react';

export function DiscoveryState({loading, error, empty, children}: {
  loading?: boolean; error?: string | null; empty?: boolean; children: ReactNode;
}) {
  if (loading) return <p role="status" className="recs-panel p-6">Loading discovery…</p>;
  if (error) return <p role="alert" className="recs-panel p-6 text-red-700">{error}</p>;
  if (empty) return <p className="recs-panel p-6">No discovery records match this view.</p>;
  return <>{children}</>;
}
