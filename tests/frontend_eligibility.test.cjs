// Isolated static UI contracts; no API, browser sessions or production assets.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createRequire}=require('node:module');
const requireFrontend=createRequire(path.resolve(__dirname,'../frontend/package.json'));
const ts=requireFrontend('typescript');
const React=requireFrontend('react');
const {renderToStaticMarkup}=requireFrontend('react-dom/server');
function compile(file,loader=requireFrontend) {
 const source=fs.readFileSync(path.resolve(__dirname,'../frontend/src/'+file),'utf8');
 const code=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS}}).outputText;
 const m={exports:{}};new Function('require','module','exports',code)(loader,m,m.exports);return m.exports;
}
const content=compile('lib/contentLifecycle.ts');
const views=compile('components/EligibilityViews.tsx',name=>name==='../lib/contentLifecycle'?content:requireFrontend(name));
const render=(component,props)=>renderToStaticMarkup(React.createElement(component,props));
test('funnel shows actual supplied snapshot counts and uncertainty',()=>{
 const html=render(views.EligibilityFunnel,{counts:{total:10,excluded:2,retained:8,incomplete:6,movies:7,tv:3}});
 for(const text of ['Discovered superset','Definitively excluded','Retained for future engagement','6 titles','20%','80%'])assert.ok(html.includes(text));
 assert.match(html,/not a prediction or acquisition decision/);
});
test('empty funnel never produces NaN or invents results',()=>{
 const html=render(views.EligibilityFunnel,{counts:{total:0,excluded:0,retained:0,incomplete:0,movies:0,tv:0}});
 assert.doesNotMatch(html,/NaN|Infinity/);assert.match(html,/0 titles/);
});
for(const stage of ['engagement','requests','queue'])test(stage+' foundation states its boundaries without fake controls',()=>{
 const html=render(views.FoundationSections,{stage});
 assert.match(html,/Foundation only/);assert.doesNotMatch(html,/<button|<input|<form/);
});
test('future contracts preserve neutral non-response and evidence driven assignments',()=>{
 const text=JSON.stringify(content.FOUNDATION_CONTENT);
 assert.match(text,/Ignored notifications are neutral/);assert.match(text,/no arbitrary expiry/);
 assert.match(text,/separate assignment decision/);assert.match(text,/explicit release\/decline/);
});
