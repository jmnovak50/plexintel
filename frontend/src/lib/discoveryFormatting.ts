export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Unknown';
  return typeof value === 'object' ? JSON.stringify(value) : String(value);
}

export function coverageLabel(status: string, discovery: boolean | null, enrichment: boolean | null) {
  if (status === 'running' || status === 'started') return 'Running';
  if (status === 'success' && discovery === true && enrichment === true) return 'Complete';
  if (status === 'partial') return 'Partial — incomplete coverage or enrichment';
  if (status === 'failed') return 'Failed';
  return 'Completeness unknown';
}
