import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
const source = readFileSync(new URL('../src/utils/pipelineStages.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { stageLabels, stageMetrics, stageDuration } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

test('all ten production stages have human-readable labels', () => {
  assert.equal(Object.keys(stageLabels).length, 10);
  assert.match(stageLabels.shap, /SHAP/);
  assert.match(stageLabels.verification, /Final/);
});
test('historical missing and combined timings are not fabricated', () => {
  assert.equal(stageDuration(undefined, 'success'), 'Not separately timed');
  assert.equal(stageDuration(undefined, 'not_recorded'), 'Not recorded');
  assert.equal(stageDuration(0, 'skipped'), '0s');
  assert.equal(stageDuration(131.85, 'success'), '2m 12s');
});
test('metric rendering preserves zeros, reused work and quality diagnostics', () => {
  const values = stageMetrics({ inferred: 0, reused: 8414, checkpoint_reused: true, chronological_average_precision: 0.97121, secret: 123 });
  assert.equal(values.find(v => v.key === 'inferred').value, '0');
  assert.equal(values.find(v => v.key === 'checkpoint_reused').value, 'Yes');
  assert.equal(values.find(v => v.key === 'chronological_average_precision').value, '0.9712');
  assert.ok(!values.some(v => v.key === 'secret'));
});
test('active durations tick only during that stage span', () => {
  const now = Date.now;
  Date.now = () => 100000;
  try {
    assert.equal(stageDuration(10, 'started', null, null, new Date(95000).toISOString(), true), '15s');
    assert.equal(stageDuration(10, 'started', null, null, new Date(95000).toISOString(), false), '10s');
  } finally { Date.now = now; }
});
