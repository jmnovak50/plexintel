import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import ts from 'typescript';
const source = readFileSync(new URL('../src/utils/pipelineStages.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { stageLabels, stageMetrics, stageDuration, stageProgress, readablePipelineLog, operatorStages } = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

test('production, optional, legacy and worker stages have human-readable labels', () => {
  assert.match(stageLabels.semantic_labels, /semantic/);
  assert.match(stageLabels.predictive_daily, /worker/);
  assert.match(stageLabels.batch_label, /labeling/);
  assert.match(stageLabels.shap, /SHAP/);
  assert.match(stageLabels.verification, /Final/);
});

test('unmeasured SHAP never falls back to a fabricated timestamp duration', () => {
  assert.equal(stageDuration(null, 'success', '2026-11-12T00:00:00Z', '2026-11-12T01:00:00Z', undefined, false, false), 'Not separately timed');
});

test('progress uses completed items or scored users with bounded percentages', () => {
  assert.deepEqual(stageProgress({completed: 2, expected: 5}), {completed: 2, expected: 5, percent: 40});
  assert.equal(stageProgress({users: 30, expected: 30}).percent, 100);
  assert.equal(stageProgress({completed: 0, expected: 0}), null);
  assert.equal(stageProgress({completed: 4, expected: 3}).percent, 100);
});

test('structured and plain logs remain readable with raw evidence available separately', () => {
  const output = readablePipelineLog('stdout:\n'+JSON.stringify({event: 'plexintel.pipeline-stage/1', stage_key: 'watch', status: 'started', elapsed_seconds: 12,
    message: 'Refreshing vectors', metrics: {completed: 2, expected: 5, reused: 0}})+'\nSource collection finished');
  assert.match(output, /Watch embedding refresh · started · Refreshing vectors/);
  assert.match(output, /Completed: 2 · Expected: 5 · Reused: 0 · Elapsed: 12s/);
  assert.match(output, /Source collection finished/);
  assert.doesNotMatch(output, /"event"/);
  assert.match(readablePipelineLog(JSON.stringify({phase: 'boosting round 11/100; examples=1000'})), /boosting round 11/);
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


test('single-worker runs use eight operator blocks and keep related work in their logs', () => {
  const keys = ['source_sync','media_text','watch','users','training_data','train_model','score_model','shap','publication','verification','semantic_labels'];
  const details = keys.map(stage_key => ({stage_key,status: 'success',duration_seconds: 1,stdout_tail: stage_key+' log'}));
  details.find(s=>s.stage_key==='shap').duration_seconds=null;
  const stages = operatorStages([{stage_key: 'predictive_daily',status: 'success'}],details);
  assert.equal(stages.filter(s=>!s.worker_output).length,8);
  assert.equal(stages.filter(s=>s.worker_output).length,1);
  assert.equal(stages.find(s=>s.stage_key==='score_model').stdout_tail,'score_model log');
  assert.equal(stages.find(s=>s.stage_key==='publication').stdout_tail,'publication log');
  assert.equal(stages.find(s=>s.stage_key==='score_model').duration_seconds,1);
  const legacy = ['tautulli_incremental','library_embeddings','watch_embeddings','user_embeddings','training_data','train_model','score_model','batch_label'].map(stage_key=>({stage_key,status:'success'}));
  assert.deepEqual(operatorStages(legacy),legacy);
});

test('grouped verification failure and active scoring remain visible', () => {
  const stages=operatorStages([{stage_key:'predictive_daily',status:'failed'}],[
    {stage_key:'publication',status:'success'}, {stage_key:'verification',status:'failed',stderr_tail:'verification failed'},
    {stage_key:'score_model',status:'started'}, {stage_key:'shap',status:'pending'}]);
  assert.equal(stages.find(s=>s.stage_key==='publication').status,'failed');
  // Streams are fetched by group key; the frontend does not relabel child stderr.
  assert.equal(stages.find(s=>s.stage_key==='publication').stderr_tail,undefined);
  assert.equal(stages.find(s=>s.stage_key==='score_model').status,'started');
});

test('stage records remain untouched while full output is loaded separately', () => {
  const stages=operatorStages([{stage_key:'predictive_daily',status:'success'}],[
    {stage_key:'train_model',status:'success',stdout_tail:JSON.stringify({event:'plexintel.pipeline-stage/1',metrics:{}}),metrics:{chronological_average_precision:.9}},
    {stage_key:'publication',status:'pending'}]);
  assert.equal(stages[0].stdout_tail,JSON.stringify({event:'plexintel.pipeline-stage/1',metrics:{}}));
  assert.equal(stages[1].stdout_tail,undefined);
});
