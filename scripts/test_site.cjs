// Fast DOM-contract tests with Node built-ins; browser tests remain separate.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname,'../blog-src/static/site.js'),'utf8');
let update;
const count = {textContent:''}, views = {hidden:true};
const summary = {focus(options){this.focused=true},scrollIntoView(){this.scrolled=true}};
const close = {hidden:true,addEventListener(event,callback){this[event]=callback}};
const donation = {open:false,querySelector(selector){return selector==='summary'?summary:close},addEventListener(event,callback){this[event]=callback}};
const document = {documentElement:{classList:{add(){}}},querySelectorAll(){return []},querySelector(selector){return {'#busuanzi_value_page_pv':count,'#article-views':views,'#donation-panel':donation}[selector]||null}};
vm.runInNewContext(source, {document,MutationObserver:class{constructor(callback){update=callback}observe(){}},window:{},navigator:{}});
assert.equal(views.hidden,true);
for(const value of ['42','0',' 123 ']){count.textContent=value;update();assert.equal(views.hidden,false)}
for(const value of ['','NaN','-1','null','12x']){count.textContent=value;update();assert.equal(views.hidden,true)}
assert.equal(close.hidden,false);
for(let i=0;i<2;i++){donation.open=true;close.click();assert.equal(donation.open,false);assert.equal(summary.focused,true)}
donation.open=true;let prevented=false;donation.keydown({key:'Escape',preventDefault(){prevented=true}});assert.equal(donation.open,false);assert.equal(prevented,true);
donation.open=true;donation.keydown({key:'Tab'});assert.equal(donation.open,true);
vm.runInNewContext(source, {document:{...document,querySelector(){return null}}});
console.log('PASS: counter empty/valid/invalid states, repeat close, Escape, focus restoration contract and non-article guard. Rendering/native keyboard behavior requires browser QA.');
