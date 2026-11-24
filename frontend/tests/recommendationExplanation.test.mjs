import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';
import { build } from 'esbuild';

const result = await build({
  stdin: { contents: `
    import React from 'react';
    import { renderToStaticMarkup } from 'react-dom/server';
    import { RecommendationExplanation, hasRecommendationExplanation } from './src/components/RecommendationExplanation';
    export const render = props => renderToStaticMarkup(<RecommendationExplanation {...props} />);
    export const has = hasRecommendationExplanation;
  `, resolveDir: new URL('..', import.meta.url).pathname, loader: 'tsx' },
  bundle: true, write: false, platform: 'node', format: 'cjs', packages: 'external', jsx: 'automatic',
});
const module = { exports: {} };
new Function('require','module','exports',result.outputFiles[0].text)(createRequire(import.meta.url),module,module.exports);
const {render,has}=module.exports;

for (const compact of [false,true]) {
  test(`factual Taste Match and unchanged Title Traits render together, compact=${compact}`, () => {
    const html=render({titleTraits:['Existing title trait'],connection:{display_text:'You liked Film A. Both films share a director.'},compact,tasteMatch:['Legacy preference']});
    assert.match(html,/Title Traits/);assert.match(html,/Existing title trait/);assert.match(html,/border-blue-100/);
    assert.equal((html.match(/Taste Match/g)||[]).length,1);
    assert.match(html,/You liked Film A\. Both films share a director\./);assert.match(html,/text-emerald-800/);
    assert.doesNotMatch(html,/Legacy preference|Connections to Your Viewing History/);
  });
}
test('missing factual evidence omits Taste Match despite legacy payload', () => {
  const html=render({titleTraits:['Existing trait'],connection:null,tasteMatch:['Legacy preference']});
  assert.match(html,/Title Traits/);assert.doesNotMatch(html,/Taste Match|Legacy preference/);
  assert.equal(render({titleTraits:[],connection:null,tasteMatch:['Legacy preference']}),'');
  assert.equal(has([],null),false);assert.equal(has([], {display_text:'  '}),false);
  assert.equal(has([], {display_text:'A factual relationship.'}),true);
});
test('factual statements preserve scope and escape source text', () => {
  const html=render({titleTraits:[],connection:{display_text:'You liked an episode of <Series>. The series shares a director.'}});
  assert.match(html,/an episode of &lt;Series&gt;/);assert.doesNotMatch(html,/<Series>/);
});
