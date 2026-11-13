import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';
import { build } from 'esbuild';

// Render the actual page components against API-shaped records. No browser,
// network, worker trigger, or implementation-mirroring snapshot is required.
const result = await build({
  stdin: { contents: `
    import React from 'react';
    import { renderToStaticMarkup } from 'react-dom/server';
    import { PipelineStageCard, PipelineLog } from './src/pages/AdminPipeline';
    export const card = st => renderToStaticMarkup(<PipelineStageCard st={st} />);
    export const log = props => renderToStaticMarkup(<PipelineLog {...props} />);
  `, resolveDir: new URL('..', import.meta.url).pathname, loader: 'tsx' },
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
});
const module = { exports: {} };
new Function('require', 'module', 'exports', result.outputFiles[0].text)(createRequire(import.meta.url), module, module.exports);
const { card, log } = module.exports;

test('stages have separate collapsible stdout, timing and compact progress', () => {
  const html = card({stage_id: 1,stage_key: 'media_text',status: 'started',duration_seconds: 12,
    metrics: {completed: 2,expected: 5,inferred: 2,reused: 0},
    stdout_tail: JSON.stringify({event: 'plexintel.pipeline-stage/1',stage_key: 'media_text',status: 'started',metrics: {completed: 2}})});
  assert.match(html, /font-mono/);
  assert.match(html, /Media-text embedding refresh/);
  assert.match(html, /12s/);
  assert.match(html, /<pre/);
  assert.match(html, /Completed: 2/);
  assert.match(html, /<details[^>]*open/);
  assert.match(html, /stdout:/);
  assert.match(html, /Progress: 40%/);
  assert.doesNotMatch(html, /<dl/);
});

test('missing timing remains explicit in the earlier log layout', () => {
  const html = card({stage_id: 2,stage_key: 'shap',status: 'success',duration_seconds: null,timing_known: false,
    metrics: {contexts: 12,contributions: 480}});
  assert.match(html, /Not separately timed/);
  assert.doesNotMatch(html, /<dl|<progress/);
});

test('worker logs preserve stderr and plain text while translating structured progress', () => {
  const html = log({stderr: 'Historical diagnostic', stdout: 'Source collection finished\n'+JSON.stringify({phase: 'boosting round 11/100; examples=1000'})});
  assert.match(html, /Historical diagnostic/);
  assert.match(html, /Source collection finished/);
  assert.match(html, /boosting round 11\/100/);
});


test('multiline stdout and stderr remain separate and complete', () => {
  const output=Array.from({length:1200},(_,i)=>`actual stage line ${i}`).join('\n');
  const html=log({stdout:output,stderr:'first error\nsecond error'});
  assert.equal((html.match(/<pre/g)||[]).length,2);
  assert.match(html,/actual stage line 0\nactual stage line 1/);
  assert.match(html,/actual stage line 1199/);
  assert.match(html,/first error\nsecond error/);
  assert.ok(html.indexOf('stdout:')<html.indexOf('stderr:'));
});

test('missing historical output is an availability note, not a fabricated log', () => {
  const html=card({stage_id:9,stage_key:'training_data',status:'not_recorded'});
  assert.match(html,/No stdout output was retained/);
  assert.doesNotMatch(html,/<pre/);
});
