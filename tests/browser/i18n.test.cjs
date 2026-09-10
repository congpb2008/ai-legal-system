// Run with node --test tests/browser/i18n.test.cjs; no third-party dependencies.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
function load(saved,blocked=false){
 const nodes=new Map();const element=key=>{if(!nodes.has(key))nodes.set(key,{});return nodes.get(key);};
 const values=new Map(saved?[['legal-library-language',saved]]:[]);
 const context=vm.createContext({window:{},document:{documentElement:{},querySelector:element,getElementById:element},
  localStorage:{getItem:key=>{if(blocked)throw Error('blocked');return values.get(key);},setItem:(k,v)=>{if(blocked)throw Error('blocked');values.set(k,v);}}});
 for(const file of ['vi.js','i18n.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../../frontend/js',file),'utf8'),context);
 return {context,api:vm.runInContext('i18n',context),values};
}
test('Vietnamese is the default, invalid preferences fall back, English is retained',()=>{
 for(const value of [undefined,'fr','../../bad']){const {api,context}=load(value);assert.equal(api.t('Sign in'),'Đăng nhập');assert.equal(context.document.documentElement.lang,'vi');}
 const {api,context}=load('en');assert.equal(api.t('Sign in'),'Sign in');assert.equal(context.document.documentElement.lang,'en');assert.equal(api.locale,'en-US');
});
test('language storage failure is recoverable',()=>{
 const {api}=load(undefined,true);assert.equal(api.language,'vi');assert.equal(api.change('en'),false);assert.equal(api.change('fr'),false);
 const normal=load();assert(normal.api.change('en'));assert.equal(normal.values.get('legal-library-language'),'en');
});
test('only template copy is translated; names, quotations, model IDs and markup stay intact',()=>{
 const {api}=load();const value='Documents <img src=x> {{0}}';
 assert.equal(api.html(['<h1>Documents</h1><p>','</p>'],value),'<h1>Tài liệu</h1><p>'+value+'</p>');
 assert.equal(api.html(['<input value="','" placeholder="Search all matching documents…">'],'Search'),'<input value="Search" placeholder="Tìm trong tất cả tài liệu phù hợp…">');
 assert.equal(api.html(['<code>','</code>'],'test-vision:latest'),'<code>test-vision:latest</code>');
 assert.equal(api.html(['Source ',''],3),'Nguồn 3');
 assert.equal(api.message('Provider detail: model-x'),'Provider detail: model-x');
});
test('all translated templates preserve placeholders and contain no added markup',()=>{
 const {context}=load();const dictionary=context.window.LEGAL_LIBRARY_VI;
 for(const [key,value] of Object.entries(dictionary)){
  assert.deepEqual((key.match(/\{\{\d+\}\}/g)||[]).sort(),(value.match(/\{\{\d+\}\}/g)||[]).sort(),key);
  assert(!/[<>]/.test(value),key);
 }
});
