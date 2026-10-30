// Existing React/TypeScript dependencies only; no browser or network required.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createRequire}=require('node:module');
const requireFrontend=createRequire(path.resolve(__dirname,'../frontend/package.json'));
const ts=requireFrontend('typescript');
const React=requireFrontend('react');
const {renderToStaticMarkup}=requireFrontend('react-dom/server');
const source=fs.readFileSync(path.resolve(__dirname,'../frontend/src/components/DiscoveryState.tsx'),'utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS}}).outputText;
const target={exports:{}};
new Function('require','module','exports',compiled)(requireFrontend,target,target.exports);
const {DiscoveryState}=target.exports;
const formatSource=fs.readFileSync(path.resolve(__dirname,'../frontend/src/lib/discoveryFormatting.ts'),'utf8');
const formatCode=ts.transpileModule(formatSource,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const formatModule={exports:{}};
new Function('require','module','exports',formatCode)(requireFrontend,formatModule,formatModule.exports);
const {displayValue,coverageLabel}=formatModule.exports;
const render=props=>renderToStaticMarkup(React.createElement(DiscoveryState,props,React.createElement('p',null,'Inventory contents')));
test('loading state announces pending data and hides old contents',()=>{
 const html=render({loading:true});assert.match(html,/role="status"/);assert.match(html,/Loading discovery/);assert.doesNotMatch(html,/Inventory contents/);
});
test('empty inventory has an explicit message',()=>{
 assert.match(render({empty:true}),/No discovery records match/);
});
test('error state is visible, accessible, and escaped',()=>{
 const html=render({error:'<script>unavailable</script>'});assert.match(html,/role="alert"/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
});
test('loaded content is displayed',()=>assert.match(render({}),/Inventory contents/));
test('unknown values differ from a known zero or negative boolean',()=>{
 assert.equal(displayValue(null),'Unknown');assert.equal(displayValue(undefined),'Unknown');assert.equal(displayValue(0),'0');assert.equal(displayValue(false),'false');
});
test('partial and incomplete executions cannot masquerade as complete',()=>{
 assert.match(coverageLabel('partial',false,true),/^Partial/);
 assert.equal(coverageLabel('success',true,false),'Completeness unknown');
 assert.equal(coverageLabel('success',true,true),'Complete');
 assert.equal(coverageLabel('failed',false,false),'Failed');
 assert.equal(coverageLabel('running',false,false),'Running');
});
