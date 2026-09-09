'use strict';
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtDate = (value) => { if(!value)return 'Not recorded'; const date=typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)?new Date(...value.split('-').map((n,i)=>Number(n)-(i===1?1:0))):new Date(typeof value==='number'?value*1000:value); return date.toLocaleDateString(); };
const today = () => new Date().toLocaleDateString('en-CA');
const list = (data, key) => Array.isArray(data) ? data : data?.[key] || data?.items || [];
const state = {user:null,status:{},vaults:[],documents:[],answer:null,question:'',uploads:[],epoch:0,timer:null,documentOffset:0,documentTotal:0,summary:{},session:0,uploadBusy:false};
const brand = '<span class="brand"><span class="brand-icon">§</span> Legal Library</span>';
function notice(text, kind='') { return `<div class="notice ${kind}" role="status">${esc(text)}</div>`; }
function button(label, action, data='', kind='') { return `<button type="button" class="btn ${kind}" data-action="${action}" data-id="${esc(data)}">${label}</button>`; }
function input(name,label,type='text',value='',extra='') { return `<div class="field"><label for="${name}">${label}</label><input id="${name}" name="${name}" type="${type}" value="${esc(value)}" ${extra}></div>`; }
function select(name,label,options,value='') { return `<div class="field"><label for="${name}">${label}</label><select id="${name}" name="${name}">${options.map(([v,t])=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(t)}</option>`).join('')}</select></div>`; }
function toast(message,error=false) { const node=document.createElement('div');node.className='toast'+(error?' error':'');node.textContent=message;$('notifications').append(node);setTimeout(()=>node.remove(),6000); }
function modal(title,html) { $('dialog').innerHTML=`<div class="dialog-head"><h2 id="dialogTitle">${esc(title)}</h2><button class="close" data-action="close" aria-label="Close dialog">×</button></div><div class="dialog-body">${html}</div>`;if(!$('dialog').open)$('dialog').showModal(); }
function head(title,subtitle,actions='') {return `<div class="page-head"><div><div class="eyebrow">Your organization’s knowledge</div><h1>${title}</h1><p class="muted">${subtitle}</p></div><div class="actions">${actions}</div></div>`;}
function empty(title,description,action=''){return `<div class="empty"><div class="symbol">◇</div><h2>${title}</h2><p>${description}</p>${action}</div>`;}
const labels={UPLOADED:'Queued',OCR_PENDING:'Reading file',OCR_COMPLETED:'Text extracted',PARSING:'Organizing content',PARSED:'Content organized',OCR_RUNNING:'Reading file',PARSING_RUNNING:'Organizing content',CHUNKING_RUNNING:'Preparing passages',EMBEDDING_RUNNING:'Building search',INDEXING_RUNNING:'Finishing',CHUNKING:'Preparing passages',CHUNKED:'Passages prepared',EMBEDDING:'Building search',EMBEDDED:'Search prepared',INDEXING:'Finishing',READY:'Ready',FAILED:'Needs attention',ARCHIVED:'Archived'};
function statusBadge(status){return `<span class="badge ${status==='READY'?'ready':status==='FAILED'?'failed':status==='ARCHIVED'?'':'working'}">${esc(labels[status]||status||'Queued')}</span>`;}
function routeParts(){const raw=(location.hash||'#/').slice(1);const [path,query]=raw.split('?');return {path:path||'/',params:new URLSearchParams(query||'')};}
function navigate(path){location.hash='#'+path;}
function formError(form,error){let box=form.querySelector('[data-error]');if(!box){box=document.createElement('div');box.dataset.error='';form.prepend(box)}box.innerHTML=notice(error.message,'error');box.scrollIntoView({block:'nearest'});}
async function withForm(form,fn){const submit=form.querySelector('[type=submit]');if(submit?.disabled)return;if(submit)submit.disabled=true;try{await fn(Object.fromEntries(new FormData(form)))}catch(error){formError(form,error)}finally{if(submit)submit.disabled=false}}

async function init(){
 try{state.status=await api.get('/v1/setup/status');const me=await api.get('/v1/auth/me').catch(()=>null);if(!me?.account&&state.user)clearSession();state.user=me?.account||null;await render()}
 catch(error){$('root').innerHTML=empty('The server is unavailable',esc(error.message),button('Try again','reload','','primary'))}
}
function authPage(mode){
 const first=state.status.needs_admin;
 if(first)mode='bootstrap';else if(!['login','signup','reset'].includes(mode))mode='login';
 const titles={login:'Welcome back',signup:'Create your account',bootstrap:'Set up your library',reset:'Reset your password'};
 const description={login:'Sign in to your organization’s document library.',signup:'Your administrator will approve access, unless you have an invitation.',bootstrap:'Create the first administrator account on this server.',reset:'Ask your administrator for a recovery code. It is valid for one hour.'};
 const params=routeParts().params;
 let fields='';
 if(mode==='bootstrap')fields+=input('code','Server setup code','password',params.get('code')||'','required autocomplete="off"')+'<p class="muted">Find this code in Legal Library Server on the host machine. It prevents someone else on the network from claiming your server.</p>';
 if(mode==='signup'||mode==='bootstrap')fields+=input('display_name','Your name','text','','required maxlength="120" autocomplete="name"');
 if(mode!=='reset')fields+=input('username','Username','text','','required minlength="3" maxlength="80" autocomplete="username"');
 if(mode==='signup')fields+=input('email','Email (optional)','email','','autocomplete="email"')+input('code','Invitation code (optional)','text',params.get('code')||'','autocomplete="off"');
 if(mode==='reset')fields+=input('code','Recovery code','password','','required autocomplete="off"');
 fields+=input(mode==='reset'?'new_password':'password',mode==='reset'?'New password':'Password','password','',`required ${mode==='login'?'':'minlength="12"'} maxlength="256" autocomplete="${mode==='login'?'current-password':'new-password'}"`);
 if(mode!=='login')fields+='<small>Use at least 12 characters. A memorable phrase works well.</small>'+input('confirm_password','Confirm password','password','','required minlength="12" autocomplete="new-password"');
 const links=mode==='login'?'<a href="#/signup">Create an account</a><a href="#/reset">Forgot password?</a>':'<a href="#/login">Back to sign in</a>';
 $('root').innerHTML=`<div class="auth-layout"><aside class="auth-story">${brand}<div><div class="eyebrow">Knowledge you can check</div><h1>Find the answer.<br>See the source.</h1><p>A shared home for your policies and legal documents, with passages you can verify and references you can keep.</p></div><small>Built for Vietnamese documents. Available to your team.</small></aside><main class="auth-area" id="content"><div class="auth-card">${brand}<h1>${titles[mode]}</h1><p class="muted">${description[mode]}</p><form data-form="auth" data-mode="${mode}"><div data-error></div>${fields}<button class="btn primary block" type="submit">${mode==='login'?'Sign in':mode==='signup'?'Request access':mode==='bootstrap'?'Create administrator':'Reset password'}</button></form><div class="auth-links">${first?'':links}</div></div></main></div>`;
 if(params.has('code'))history.replaceState(null,'','#/'+(first?'welcome':mode));
}
function shell(path){
 const nav=[['/','Overview'],['/ask','Ask your documents'],['/search','Search'],['/documents','Documents'],['/vaults','Collections'],['/history','Saved answers']];
 if(state.user.role==='admin')nav.push(['/users','People'],['/settings','Server settings']);
 $('root').innerHTML=`<div class="shell"><aside class="sidebar">${brand}<small>Find it. Verify it. Keep it.</small><nav class="nav" aria-label="Main navigation">${nav.map(([href,label])=>`<a href="#${href}" ${path===href?'aria-current="page"':''} class="${path===href?'active':''}">${label}</a>`).join('')}</nav><div class="sidebar-bottom"><a href="#/account">${esc(state.user.display_name)}</a><br><small>${state.user.role==='admin'?'Administrator':'Team member'}</small><br>${button('Sign out','logout','','small')}</div></aside><section class="workspace"><header class="topbar"><span class="mode"><span class="dot"></span>${state.status.mode==='ai'?'AI-assisted source selection':'Local document library'}</span><div class="row"><a href="#/help">Help</a><a class="pill" href="#/account">${esc(state.user.display_name)}</a></div></header><main class="content" id="content" tabindex="-1"><div class="loading"><span class="spinner"></span> Loading…</div></main></section></div>`;
}
async function loadCollections(){
 const epoch=state.epoch;const vaults=[];let offset=0;
 do{const result=await api.get('/v1/vaults',{limit:100,offset});if(epoch!==state.epoch)return;
  const page=list(result,'vaults');vaults.push(...page);offset+=page.length;
  if(!page.length||offset>=(result.total??offset))break;
 }while(true);
 state.vaults=vaults;return vaults;
}
async function loadDocuments(params=routeParts().params){
 const epoch=state.epoch;const view=params.get('view')||'ACTIVE';
 const offset=Math.max(0,Math.min(2147483647,Number.parseInt(params.get('offset'),10)||0));
 const result=await api.get('/v1/documents',{limit:100,offset,vault_id:params.get('vault'),q:params.get('q'),
  status:view==='ALL'?'':view==='ARCHIVED'?'ARCHIVED':'ACTIVE',
  processing:['READY','FAILED','PROCESSING'].includes(view)?view:''});
 if(epoch!==state.epoch)return;
 state.documentOffset=offset;state.documentTotal=result.total??list(result).length;
 state.documents=list(result,'documents');return state.documents;
}
async function loadSummary(){const epoch=state.epoch;const summary=await api.get('/v1/documents/summary');if(epoch===state.epoch)state.summary=summary;}
function documentCount(){return `Documents ${state.documents.length?state.documentOffset+1:0}–${state.documents.length?state.documentOffset+state.documents.length:0} of ${state.documentTotal}. Processing updates automatically.`;}
function documentPaging(){return `${state.documentOffset?button('Previous','previous-documents'):''}${state.documentOffset+100<state.documentTotal?button('Next','next-documents'):''}`;}
function stopPendingWork(){api.cancelPending();state.session++;state.uploads=[];state.uploadBusy=false;}
function clearSession(){
 stopPendingWork();state.epoch++;clearTimeout(state.timer);
 Object.assign(state,{user:null,vaults:[],documents:[],answer:null,question:'',uploads:[],uploadBusy:false,summary:{},detail:null,config:null});
 if($('dialog').open)$('dialog').close();$('dialog').innerHTML='';$('notifications').innerHTML='';
}
async function render(){
 clearTimeout(state.timer);const epoch=++state.epoch;const {path,params}=routeParts();
 if(!state.user){authPage(path.slice(1)||'login');return}
 shell(path);
 try{
  let html;
  if(path==='/'){await Promise.all([loadCollections(),loadSummary()]);html=overview()}
  else if(path==='/vaults'){await loadCollections();html=collections()}
  else if(path==='/documents'){await Promise.all([loadCollections(),loadDocuments()]);html=documents(params)}
  else if(path==='/upload'){await loadCollections();html=uploadPage(params)}
  else if(path==='/ask'||path==='/search'){await loadCollections();html=questionPage(path,params)}
  else if(path==='/history'){html=historyPage(list(await api.get('/v1/history')))}
  else if(path==='/account'){html=accountPage(list(await api.get('/v1/account/sessions')))}
  else if(path==='/users'&&state.user.role==='admin'){html=usersPage(list(await api.get('/v1/accounts')))}
  else if(path==='/settings'&&state.user.role==='admin'){html=settingsPage(await api.get('/v1/setup/config'))}
  else if(path==='/help'){html=helpPage()}
  else{navigate('/');return}
  if(epoch!==state.epoch)return;$('content').innerHTML=html;
  if(path==='/documents'&&state.documents.some(d=>!['READY','FAILED'].includes(d.processing_state)&&d.status!=='ARCHIVED'))pollDocuments(epoch,params);
 }catch(error){if(epoch===state.epoch&&$('content'))$('content').innerHTML=notice(error.message,'error')+button('Try again','reload','','primary')}
}
function overview(){const ready=state.summary.ready||0;return `<section class="hero"><div class="eyebrow">Your evidence, in one place</div><h1>Good answers start<br>with the right documents.</h1><p>Search your team’s knowledge and find source passages you can inspect, share and return to.</p><div class="actions"><a class="btn primary" href="#/ask">Ask your documents →</a><a class="btn" href="#/upload">Upload documents</a></div></section><div class="grid"><div class="card"><div class="stat">${ready}</div><p>Documents ready to use</p></div><div class="card"><div class="stat">${state.vaults.length}</div><p>Collections you can access</p></div><div class="card"><div class="stat">${state.summary.failed||0}</div><p>Documents needing attention</p></div></div><br><div class="panel"><h2>A simple path to your first answer</h2><div class="grid"><div><div class="step-number">01 / COLLECT</div><h3>Create a collection</h3><p class="muted">Keep a set of policies together. Share it with the people who need it.</p><a href="#/vaults">Manage collections →</a></div><div><div class="step-number">02 / UPLOAD</div><h3>Add your source documents</h3><p class="muted">Upload PDF or DOCX files. You’ll see when each document is ready.</p><a href="#/upload">Add documents →</a></div><div><div class="step-number">03 / VERIFY</div><h3>Ask and inspect the source</h3><p class="muted">Choose your scope and date, then open the passage behind each result.</p><a href="#/ask">Ask a question →</a></div></div></div>${state.status.mode==='local'?notice('Local mode keeps document processing on this machine. Your administrator can enable an AI provider for assisted passage selection.'):notice('AI-assisted selection is enabled. Your administrator controls which provider processes questions and relevant document passages.')}`;}
function collections(){return head('Collections','Organize documents and choose who can read or contribute.',button('+ New collection','new-collection','','primary'))+(state.vaults.length?`<div class="grid">${state.vaults.map(v=>`<article class="card collection-card"><div class="source-label">${esc({PERSONAL:'Personal collection',DEPARTMENT:'Team collection',COMMON:'Shared collection'}[v.vault_type]||'Collection')}</div><h2>${esc(v.name)}</h2><p>${esc(v.description||'A collection of your team’s documents.')}</p><p>${v.document_count||0} documents · ${esc(v.status)}</p><div class="actions"><a class="btn small" href="#/documents?vault=${v.id}">Open</a><a class="btn small" href="#/ask?vault=${v.id}">Ask</a>${v.can_manage?button('Sharing','sharing',v.id,'small'):''}</div></article>`).join('')}</div>`:empty('Create a home for your documents','Start with a collection such as Procurement policies or Internal procedures.',button('Create collection','new-collection','','primary')))}
function collectionOptions(allLabel='All accessible collections'){return [[allLabel?'':state.vaults[0]?.id||'',allLabel||'Choose a collection'],...state.vaults.filter(v=>v.status==='ACTIVE').map(v=>[v.id,v.name])];}
function documents(params){
 return head('Documents','Find a document across your library, inspect its source and track processing.','<a class="btn primary" href="#/upload">+ Upload documents</a>')+
 `<form data-form="document-filters" class="toolbar">
 ${select('vault','Collection',collectionOptions(),params.get('vault')||'')}
 ${input('q','Title or document number','search',params.get('q')||'','maxlength="200" placeholder="Search all matching documents…"')}
 ${select('view','Show',[['ACTIVE','Active documents'],['READY','Ready to use'],['FAILED','Needs attention'],['PROCESSING','Processing'],['ARCHIVED','Archived'],['ALL','All documents']],params.get('view')||'ACTIVE')}
 <button type="submit" class="btn primary">Apply filters</button><a class="btn" href="#/documents">Clear filters</a></form>
 <div class="panel table-wrap" id="document-table">${documentRows(state.documents)}</div>
 <div class="row-between"><p class="muted" id="document-count">${documentCount()}</p><div class="actions" id="document-paging">${documentPaging()}</div></div>`;
}
function documentRows(rows){return rows.length?`<table><thead><tr><th>Document</th><th>Status</th><th>Effective date</th><th>Actions</th></tr></thead><tbody>${rows.map(d=>`<tr data-document-title="${esc(d.title.toLowerCase())}"><td><button class="link-button title" data-action="document" data-id="${d.id}">${esc(d.title)}</button><small>${esc(d.issuing_authority)}</small>${d.processing_error?`<small class="error-text">${esc(d.processing_error)}</small>`:''}</td><td>${statusBadge(d.status==='ARCHIVED'?'ARCHIVED':d.processing_state)}</td><td>${esc(d.effective_date||'Not verified')}</td><td><div class="actions">${d.processing_state==='READY'&&d.status==='ACTIVE'?`<a class="btn small" href="#/ask?document=${d.id}&vault=${d.vault_id}">Ask</a>`:''}${d.can_manage&&d.status==='ACTIVE'&&d.processing_state==='FAILED'?button('Retry','retry',d.id,'small'):''}${button('Details','document',d.id,'small')}</div></td></tr>`).join('')}</tbody></table>`:empty('No matching documents','Try another collection, title or status. You can also add a document to a collection you contribute to.','<a class="btn" href="#/documents">Clear filters</a>');}
function pollDocuments(epoch,params){state.timer=setTimeout(async()=>{
 if(epoch!==state.epoch)return;
 try{await loadDocuments(params);if(epoch!==state.epoch)return;
  if($('document-table'))$('document-table').innerHTML=documentRows(state.documents);
  if($('document-count'))$('document-count').textContent=documentCount();
  if($('document-paging'))$('document-paging').innerHTML=documentPaging();
  if(state.documents.some(d=>!['READY','FAILED'].includes(d.processing_state)&&d.status!=='ARCHIVED'))pollDocuments(epoch,params);
 }catch(error){if(epoch===state.epoch&&error.name!=='AbortError')toast('Could not refresh processing status. Reload to try again.',true);}
 },4000)}
function uploadPage(params){if(state.uploadBusy)return head('Uploading documents','Your current batch is being sent to the server.')+notice('Keep this browser open until uploading finishes. You can browse other pages while processing continues.')+'<a class="btn" href="#/documents">View documents</a>';return head('Add documents','Choose files, check their names and let the library prepare them.')+(!state.vaults.some(v=>v.can_upload&&v.status==='ACTIVE')?empty('Choose a collection you can contribute to','Ask a collection manager for contributor access, or create your own collection.',button('Create collection','new-collection','','primary')):`<form data-form="upload" id="upload-form"><div class="panel"><div class="form-grid">${select('vault_id','Save to collection',[['','Choose a collection'],...state.vaults.filter(v=>v.can_upload&&v.status==='ACTIVE').map(v=>[v.id,v.name])],params.get('vault')||'')}${input('issuing_authority','Issued by (optional)','text','','placeholder="e.g. Your organization"')}</div><div class="dropzone"><h2>Select your documents</h2><p class="muted">PDF and DOCX · up to 25 MB per file · up to 50 files per batch</p><input type="file" id="upload-files" multiple accept=".pdf,.docx" aria-label="Select documents"><p><button class="link-button" type="button" data-action="choose-folder">Or choose a folder</button></p><input class="hidden" id="folder-files" type="file" webkitdirectory multiple aria-label="Select a document folder"></div><div id="upload-preview">${uploadPreview()}</div><details><summary>Document details (optional)</summary><div class="form-grid">${select('document_type','Document type',[['INTERNAL_REGULATION','Policy or internal document'],['DECISION','Decision'],['CIRCULAR','Circular'],['DECREE','Decree'],['LAW','Law']])}${input('effective_date','Effective from','date')}${input('expiration_date','Effective until','date')}${input('tags','Tags','text','','placeholder="procurement, internal"')}</div><p class="muted">Dates apply to this batch. Leave them empty if they have not been verified.</p></details><div data-error></div><div class="row-between"><small>Scanned pages need OCR on the server. Unreadable files remain visible for correction.</small><button type="submit" class="btn primary" id="upload-submit">Upload documents</button></div></div></form><div id="upload-summary"></div>`);}
function uploadPreview(){return state.uploads.map((u,i)=>`<div class="upload-item"><div class="row-between"><strong>${esc(u.file.name)}</strong><small>${(u.file.size/1048576).toFixed(1)} MB</small></div>${input('file-title-'+i,'Document title','text',u.title,'required maxlength="300"')}<div id="upload-state-${i}">${u.done?notice('Uploaded. Processing continues in Documents.','success'):u.error?notice(u.error,'error'):''}</div></div>`).join('')}
function questionPage(path,params){const ask=path==='/ask';const documentId=params.get('document');return head(ask?'Ask your documents':'Search the library',ask?'Find relevant source passages, then check the wording and context.':'Look up a policy, phrase, document number or topic.')+`<form data-form="${ask?'ask':'search'}" class="panel" id="question-form"><div class="toolbar">${select('vault_id','Collection',collectionOptions(),params.get('vault')||'')}${input('as_of','Effective on','date',today())}</div>${documentId?notice('This question is limited to the document you selected.')+`<input type="hidden" name="document_id" value="${esc(documentId)}">`:''}<div class="search-box"><label class="field" for="query">${ask?'Your question':'Search terms'}<textarea name="query" id="query" required maxlength="4000" placeholder="${ask?'Ví dụ: Hồ sơ đề nghị mua sắm cần những tài liệu nào?':'e.g. đấu thầu, Article 5, procurement approval'}">${esc(params.get('q')||'')}</textarea></label></div><div class="row-between"><small>Only collections you can access are searched. Unknown effective dates are marked.</small><button class="btn primary" type="submit">${ask?'Find supporting passages':'Search'}</button></div><div data-error></div></form><div id="results" aria-live="polite"></div>`;}
function resultSource(c,index,text=''){return `<article class="source-card"><div class="source-label">Source ${index+1}</div><h3>${esc(c.document_title||c.label||'Document')}</h3><div class="row"><span class="badge">${esc(c.source_anchor?.canonical_reference||c.label||'Source passage')}</span><small>Page ${c.source_anchor?.page||'—'} · Effective: ${esc(c.effective_date||'Not verified')}</small></div>${text?`<div class="quote">${esc(text)}</div>`:''}<p class="muted">${esc(c.authority||'')}</p><button class="btn small" type="button" data-action="source" data-document="${c.document_id}" data-version="${c.document_version_id}" data-node="${c.knowledge_node_id}" data-page="${c.source_anchor?.page||1}">Inspect source →</button></article>`;}
function answerView(answer,question){state.answer=answer;state.question=question;const noEvidence=answer.status==='NO_EVIDENCE';return `<section class="panel"><div class="row-between"><span class="eyebrow">${noEvidence?'More evidence needed':'Source quotations'}</span><span class="badge">${noEvidence?'No supporting evidence':'Review source context'}</span></div><h2>${esc(question)}</h2><div class="answer-meta"><span>Effective on ${esc(answer.as_of||today())}</span><span>${answer.citations?.length||0} sources</span><span>Saved privately to your account</span></div>${noEvidence?notice('No sufficiently relevant source was found in this scope. Try a more specific question, a different collection, or add the missing document.','warning'):`<div class="result-text answer-body">${esc(answer.response?.content)}</div>`}${(answer.limitations||[]).map(l=>notice(l.description||l,'warning')).join('')}${(answer.citations||[]).map((c,i)=>resultSource(c,i)).join('')}<div class="answer-tools"><div class="actions">${button('Copy with references','copy-answer')}${button('Download answer','download-answer')}<label for="answer-feedback">Was this useful?</label><select id="answer-feedback" class="feedback-select"><option value="">Choose feedback…</option><option value="useful">Useful</option><option value="wrong_source">Wrong source</option><option value="outdated">Outdated information</option><option value="incomplete">Incomplete</option><option value="unsupported">Does not support the question</option></select></div><p class="source-footer">Quotations are checked against your uploaded documents. Relevance, completeness and legal applicability still need review.</p></div></section>`;}
function historyPage(rows){return head('Saved answers','Your questions and source references, available when you need them.')+`<div class="panel">${rows.length?rows.map(r=>`<div class="list-line row-between"><div><button class="link-button" data-action="history" data-id="${r.id}">${esc(r.question)}</button><small class="muted"> · ${fmtDate(r.created_at)}</small>${r.feedback?` <span class="badge">${esc(r.feedback.replaceAll('_',' '))}</span>`:''}</div>${button('Delete','delete-history',r.id,'small danger')}</div>`).join(''):empty('Your research will appear here','Ask a question to save its answer and source references.','<a class="btn primary" href="#/ask">Ask a question</a>')}</div><div id="results"></div>`;}
function accountPage(sessions){return head('Your account','Manage your profile, password and signed-in devices.')+`<div class="panel account-form"><h2>Profile</h2><form data-form="profile">${input('display_name','Name','text',state.user.display_name,'required maxlength="120"')}${input('email','Email','email',state.user.email,'maxlength="254"')}<small>Username: ${esc(state.user.username)}</small><div data-error></div><br><button type="submit" class="btn primary">Save profile</button></form></div><div class="panel account-form"><h2>Change password</h2><form data-form="password">${input('current_password','Current password','password','','required autocomplete="current-password"')}${input('new_password','New password','password','','required minlength="12" maxlength="256" autocomplete="new-password"')}${input('confirm_password','Confirm new password','password','','required minlength="12" autocomplete="new-password"')}<p class="muted">Changing your password signs out all devices.</p><div data-error></div><button class="btn primary" type="submit">Update password</button></form></div><div class="panel"><h2>Signed-in sessions</h2>${sessions.map(s=>`<div class="list-line row-between"><div>${s.current?'This browser':'Browser session'}<small class="muted"> · Signed in ${fmtDate(s.created_at)} · Expires ${fmtDate(s.expires_at)}</small></div>${button('Sign out','revoke-session',s.id,'small')}</div>`).join('')}<hr class="divider">${button('Sign out of this browser','logout','','danger')}</div>`;}
function usersPage(rows){return head('People','Approve access, invite colleagues and manage accounts.',button('Create invitation','invite','','primary'))+notice('Each person needs their own account. Collection owners decide which documents to share.')+`<div class="panel table-wrap"><table><thead><tr><th>Person</th><th>Role</th><th>Access</th><th>Manage</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.display_name)}</strong><small>${esc(r.username)}${r.email?' · '+esc(r.email):''}</small></td><td>${esc(r.role)}</td><td><span class="badge ${r.state}">${esc(r.state)}</span></td><td><div class="actions">${r.state==='pending'?button('Approve','approve',r.id,'small primary'):''}${r.id!==state.user.id?button(r.state==='disabled'?'Enable':'Disable',r.state==='disabled'?'approve':'disable',r.id,'small'):''}${button('Recovery code','reset-code',r.id,'small')}${r.id!==state.user.id?button(r.role==='admin'?'Make member':'Make admin',r.role==='admin'?'make-member':'make-admin',r.id,'small'):''}</div></td></tr>`).join('')}</tbody></table></div>`;}
function settingsPage(config){state.config=config;return head('Server settings','Choose how this installation processes documents and questions.')+`<div class="panel"><h2>Processing mode</h2><p>Local mode searches and quotes documents on this machine. AI-assisted mode sends your question and relevant passages to the provider configured below.</p>${notice(state.status.mode==='ai'?'AI-assisted source selection is enabled.':'Local mode is active. No AI account is required.')}${state.status.mode==='ai'?button('Switch to local mode','local-mode'):'<a class="btn" href="#/upload">Continue with local mode</a>'}</div><form data-form="provider" class="panel"><h2>Optional AI provider</h2><p class="muted">Use an Ollama server with an embedding model and a chat model. Changing models may require rebuilding document search.</p>${input('base_url','Provider address','url',config.base_url,'required placeholder="http://localhost:11434/v1"')}${input('model','Chat model','text',config.model,'required placeholder="qwen3:8b"')}${input('embedding_model','Embedding model','text',config.embedding_model||'bge-m3','required')}${input('api_key',config.has_api_key?'Provider key (leave empty to keep at the same address)':'Provider key (if required)','password','','autocomplete="off"')}<details><summary>Advanced options</summary><div class="form-grid">${input('timeout_seconds','Response timeout (seconds)','number',config.timeout_seconds||60,'min="1" max="120"')}${input('max_tokens','Maximum response tokens','number',config.max_tokens||4096,'min="256" max="8192"')}${select('reasoning_effort','Reasoning',[['none','None'],['low','Low'],['medium','Medium']],config.reasoning_effort||'none')}</div></details><label class="check"><input type="checkbox" id="provider-consent" required><span>I have approved this destination to process my organization’s questions and document passages.</span></label><div data-error></div><br><div class="actions">${button('Test connection','test-provider')}<button type="submit" class="btn primary">Save and enable</button></div><div id="provider-test"></div></form><div class="panel"><h2>Server operations</h2><p>Use the Legal Library Server application on the host machine to manage the service, port, HTTPS certificate, backups and recovery.</p>${button('Check server status','server-status')}<div id="server-status"></div></div>`;}
function helpPage(){return head('Help','A quick guide to using your library.')+`<div class="panel"><h2>Getting started</h2><ol><li>Create a collection and add colleagues in Sharing.</li><li>Upload PDF or DOCX files. Optional dates and tags help people understand them.</li><li>Wait for <strong>Ready</strong>. If a file needs attention, inspect the reason and retry.</li><li>Ask a specific question and select the relevant collection.</li><li>Open each source, check its version and surrounding text, then copy the answer with references.</li></ol><h2>Finding a document</h2><p>In Documents, choose a collection, enter part of its title or document number and choose Apply filters. Vietnamese titles also match without accents. Filters search the whole accessible library. Show lets you find ready, processing, needs-attention or archived documents. Clear filters returns to active documents.</p><h2>Contributing and uploading</h2><p>Viewers can read sources. Contributors can upload and edit details. Collection managers can also share access, retry processing, archive, restore and replace versions. Upload destinations only include collections you can contribute to.</p><p>You can browse this library while a batch uploads. Keep the browser open until all files have been sent; processing then continues on the server. Signing out cancels remaining transfers and clears selected files from this browser. A file already accepted by the server can still finish processing.</p><h2>Understanding the answer</h2><p>Answers contain exact source passages. With AI enabled, the model selects passages; the server verifies the quotations before showing them. A source can be accurately quoted and still be incomplete, outdated or inapplicable to your situation.</p><p>The effective date filter uses the dates recorded on your documents. Unknown dates are labelled. It does not automatically discover amendments or certify current law.</p><h2>Who can see my work?</h2><p>Collection owners control document access. Saved answers are private to your account and are hidden if you lose access to their source collections. Server administrators control accounts and processing settings; the host operator can access server backups.</p><h2>Scanned documents</h2><p>Scans need Tesseract with Vietnamese language data on the server. Unreadable pages are reported instead of quietly skipped. Ask your administrator to enable OCR or upload a text-based file.</p><h2>Need access or a password reset?</h2><p>Contact your organization’s administrator. They can approve an account, issue an invitation, or give you a recovery code. A password reset signs out existing sessions.</p></div>`;}

document.addEventListener('submit',event=>{
 const form=event.target;if(!form.dataset.form)return;event.preventDefault();
 withForm(form,async body=>{
  const type=form.dataset.form;
  if(type==='auth'){
   const mode=form.dataset.mode;if(mode!=='login'&&body.confirm_password!==(body.password||body.new_password))throw new Error('Passwords do not match.');
   delete body.confirm_password;
   if(mode==='reset'){await api.post('/v1/auth/reset',body);toast('Password reset. Sign in with your new password.');navigate('/login');return}
   if(mode==='signup'||mode==='bootstrap'){
    const result=await api.post('/v1/auth/'+(mode==='bootstrap'?'bootstrap':'signup'),body);
    if(result.requires_approval){modal('Access requested',notice('Your account is waiting for administrator approval. You can sign in once it is approved.','success')+'<a class="btn primary" href="#/login" data-action="close">Back to sign in</a>');return}
   }
   const login=await api.post('/v1/auth/login',{username:body.username,password:body.password});state.user=login.account;state.status=await api.get('/v1/setup/status');navigate('/');await render();return;
  }
  if(type==='document-filters'){const params=new URLSearchParams();for(const key of ['vault','q','view'])if(body[key])params.set(key,body[key].trim());navigate('/documents?'+params);return}
  if(type==='collection'){await api.post('/v1/vaults',{name:body.name,description:body.description,vault_type:'DEPARTMENT'});$('dialog').close();toast('Collection created.');navigate('/vaults');await render()}
  if(type==='upload'){await uploadBatch(form,body);return}
  if(type==='ask'||type==='search'){
   const epoch=state.epoch;const session=state.session;
   $('results').innerHTML='<div class="panel loading"><span class="spinner"></span> Finding relevant source passages…</div>';
   try{const data=await api.post(type==='ask'?'/v1/answers':'/v1/search',body);if(epoch!==state.epoch||session!==state.session||!$('results'))return;$('results').innerHTML=type==='ask'?answerView(data,body.query):(data.evidence?.length?`<p class="muted">${data.evidence.length} passages · ${esc(data.strategy)} search</p>`+data.evidence.map((e,i)=>resultSource(e,i,e.text)).join(''):empty('No results in this scope','Try a document number, a distinctive phrase, or a broader collection.'))}catch(error){if(epoch!==state.epoch||session!==state.session)return;if($('results'))$('results').innerHTML='';throw error}return;
  }
  if(type==='profile'){state.user=await api.patch('/v1/account',body);toast('Profile saved.');await render()}
  if(type==='password'){if(body.new_password!==body.confirm_password)throw new Error('Passwords do not match.');stopPendingWork();await api.post('/v1/account/password',body);clearSession();toast('Password changed. Please sign in again.');navigate('/login');await render()}
  if(type==='share'){await api.post('/v1/vaults/'+form.dataset.id+'/members',body);toast('Sharing updated.');await showSharing(form.dataset.id)}
  if(type==='provider'){if(!body.api_key&&body.base_url.replace(/\/$/,'')===state.config.base_url.replace(/\/$/,''))delete body.api_key;await api.post('/v1/setup/config',body);await api.post('/v1/setup/complete');state.status=await api.get('/v1/setup/status');toast('AI provider enabled. New uploads will use this configuration.');await render()}
  if(type==='version'){const data=new FormData(form);data.append('replace_document_id',form.dataset.id);const file=data.get('file');if(file.size>25*1048576)throw new Error('Choose a file of at most 25 MB.');await api.post('/v1/uploads',data);$('dialog').close();toast('New version uploaded and queued.');await render();return}
  if(type==='metadata'){const id=form.dataset.id;await api.patch('/v1/documents/'+id,body);toast('Document details updated.');$('dialog').close();await render()}
 });
});

async function uploadBatch(form,body){
 if(state.uploadBusy)throw new Error('Another batch is uploading. Wait for it to finish.');
 if(!body.vault_id)throw new Error('Choose a collection.');if(!state.uploads.length)throw new Error('Choose at least one PDF or DOCX file.');
 if(body.effective_date&&body.expiration_date&&body.effective_date>body.expiration_date)throw new Error('The end date must be after the effective date.');
 const batch=state.uploads;const session=state.session;
 batch.forEach((u,i)=>{u.title=$('file-title-'+i)?.value.trim()||u.title;if(!u.title)throw new Error('Every file needs a title.');if(u.file.size>25*1048576)throw new Error(u.file.name+' exceeds 25 MB.')});
 state.uploadBusy=true;
 const controls=[...form.querySelectorAll('input,select,button')];controls.forEach(el=>el.disabled=true);
 try{
  for(let i=0;i<batch.length;i++){
   if(session!==state.session)return;
   const u=batch[i];if(u.done)continue;
   const target=form.isConnected?$('upload-state-'+i):null;
   if(target)target.innerHTML='<div class="row"><span class="spinner"></span> Uploading…</div>';
   const fd=new FormData();fd.append('file',u.file);fd.append('title',u.title);fd.append('filename',u.file.name);
   for(const key of ['vault_id','document_type','effective_date','expiration_date','tags'])if(body[key])fd.append(key,body[key]);
   fd.append('issuing_authority',body.issuing_authority||'Not recorded');
   try{const result=await api.post('/v1/uploads',fd);if(session!==state.session)return;u.result=result;u.done=true;u.error='';if(target)target.innerHTML=notice('Uploaded. Preparing document…','success');}
   catch(error){if(session!==state.session||error.name==='AbortError')return;u.error=error.message;if(target)target.innerHTML=notice(error.message,'error');}
  }
  if(session!==state.session)return;
  const done=batch.filter(u=>u.done).length;const failed=batch.length-done;
  const summary=`<div class="panel"><h2>${done} uploaded${failed?', '+failed+' need attention':''}</h2><p>Processing continues on the server. You can leave this page.</p><a class="btn primary" href="#/documents?vault=${encodeURIComponent(body.vault_id)}">View processing progress →</a>${failed?notice('Correct any reported problems and choose Upload documents again. Successful files will not be uploaded twice.','warning'):''}</div>`;
  if(form.isConnected&&$('upload-summary'))$('upload-summary').innerHTML=summary;
  else toast(`${done} documents uploaded${failed?'; '+failed+' need attention':''}.`);
  if(!failed){state.uploads=[];if(form.isConnected&&$('upload-submit'))$('upload-submit').textContent='Choose more files to upload';}
 }finally{
  if(session===state.session){state.uploadBusy=false;controls.forEach(el=>el.disabled=false);
   if(!form.isConnected&&routeParts().path==='/upload')await render();}
 }
}

document.addEventListener('change',async event=>{
 const target=event.target;
 if(target.id==='upload-files'||target.id==='folder-files'){
  if(state.uploadBusy){toast('Wait for the current upload batch to finish.',true);return}
  const files=[...target.files].filter(f=>!f.name.startsWith('~$')&&/\.(pdf|docx)$/i.test(f.name));
  if(files.length>50){toast('Choose up to 50 documents at a time.',true);return}
  state.uploads=files.map(file=>({file,title:file.name.replace(/\.(pdf|docx)$/i,'').replaceAll('_',' '),done:false}));
  $('upload-preview').innerHTML=uploadPreview();if($('upload-summary'))$('upload-summary').innerHTML='';
  if(files.length!==target.files.length)toast('Skipped unsupported files and Office temporary files.');
 }

 if(target.id==='answer-feedback'&&state.answer?.history_id){try{await api.patch('/v1/history/'+state.answer.history_id,{feedback:target.value||null});toast('Feedback saved. Thank you.')}catch(error){toast(error.message,true)}}
});


async function showSharing(id){
 const [members,people]=await Promise.all([api.get('/v1/vaults/'+id+'/members'),api.get('/v1/people')]);
 modal('Collection sharing',`<p>Only people listed here can use this collection.</p>${members.map(m=>`<div class="list-line row-between"><span>${esc(m.name)} <span class="badge">${esc(m.role)}</span></span>${m.role!=='OWNER'?`<button class="btn small danger" data-action="remove-member" data-id="${m.user_id}" data-vault="${id}">Remove</button>`:''}</div>`).join('')}<hr class="divider"><form data-form="share" data-id="${id}">${select('user_id','Person',people.map(p=>[p.id,p.display_name+' ('+p.username+')']))}${select('role','Access',[['VIEWER','Can read and ask'],['CONTRIBUTOR','Can read and upload'],['MANAGER','Can manage documents and sharing']])}<div data-error></div><button type="submit" class="btn primary">Save access</button></form>`);
}
async function showDocument(id){
 const d=await api.get('/v1/documents/'+id);state.detail=d;
 modal(d.title,`${statusBadge(d.processing_state)} ${d.status==='ARCHIVED'?'<span class="badge">Archived</span>':''}${d.processing_error?notice(d.processing_error,'warning'):''}<div class="actions"><br>${d.status==='ACTIVE'&&d.processing_state==='READY'?`<a class="btn primary" href="#/ask?document=${d.id}&vault=${d.vault_id}" data-action="close">Ask this document</a>`:''}${button('Original file','download-original',d.id)}${d.can_manage&&d.status==='ACTIVE'&&d.processing_state==='FAILED'?button('Retry processing','retry',d.id):''}</div><hr class="divider"><form data-form="metadata" data-id="${d.id}">${input('title','Title','text',d.title,'required maxlength="300"')}${input('description','Description','text',d.description||'','maxlength="2000"')}<div class="form-grid">${input('effective_date','Effective from','date',d.effective_date||'')}${input('expiration_date','Effective until','date',d.expiration_date||'')}${input('tags','Tags','text',(d.tags||[]).join(', '))}${input('issuing_authority','Issued by','text',d.issuing_authority||'')}</div><div data-error></div><br><button type="submit" class="btn">Save details</button></form>${d.can_manage&&d.status==='ACTIVE'?button('Upload new version','new-version',d.id):''}<details><summary>Source and versions</summary><p>Original: ${esc(d.original_filename||'Not recorded')}</p>${(d.versions||[]).map(v=>`<div class="list-line">Version ${v.version_number} · ${esc(v.status)} · ${fmtDate(v.created_at)}<button class="btn small" data-action="download-original" data-id="${d.id}" data-version="${v.version_id}">Download this version</button></div>`).join('')}</details><hr class="divider">${d.can_manage?(d.status==='ARCHIVED'?button('Restore document','restore-document',id):button('Archive document','archive-document',id,'danger')):''}<p class="source-footer">Archiving removes a document from normal search and preserves its source. Only authorized collection managers can change its lifecycle.</p>`);
 if(!d.can_update)$('dialog').querySelectorAll('form input,form button').forEach(el=>el.disabled=true);
}
function answerExport(){const a=state.answer;return `${state.question}\n\n${a.response?.content||''}\n\nSources:\n${(a.citations||[]).map((c,i)=>`[${i+1}] ${c.document_title} — ${c.label||''}; version ${c.document_version_id}; effective ${c.effective_date||'unknown'}; page ${c.source_anchor?.page||'unknown'}`).join('\n')}\n\nEffective-on filter: ${a.as_of||today()}\nSource quotations; verify applicability and completeness.\n`;}
function download(content,name,type='text/plain;charset=utf-8'){const blob=content instanceof Blob?content:new Blob([content],{type});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),15000)}
document.addEventListener('click',async event=>{
 const el=event.target.closest('[data-action]');if(!el)return;const action=el.dataset.action,id=el.dataset.id;
 if(action==='close'){$('dialog').close();return}
 if(el.tagName==='BUTTON')event.preventDefault();if(el.disabled)return;
 try{
  if(action==='reload'){await init();return}
  if(action==='logout'){stopPendingWork();try{await api.post('/v1/auth/logout');}catch(error){await render();throw error;}clearSession();navigate('/login');await render()}
  if(action==='new-collection')modal('New collection',`<form data-form="collection">${input('name','Collection name','text','','required maxlength="120" placeholder="e.g. Procurement policies"')}${input('description','Description (optional)','text','','maxlength="500"')}<p class="muted">Only you can access a new collection until you add people in Sharing.</p><div data-error></div><button class="btn primary" type="submit">Create collection</button></form>`);
  if(action==='choose-folder')$('folder-files').click();
  if(action==='sharing')await showSharing(id);
  if(action==='remove-member'){await api.delete('/v1/vaults/'+el.dataset.vault+'/members/'+id);await showSharing(el.dataset.vault);toast('Access removed.')}
  if(action==='previous-documents'||action==='next-documents'){const params=routeParts().params;params.set('offset',Math.max(0,state.documentOffset+(action==='next-documents'?100:-100)));navigate('/documents?'+params)}
  if(action==='document')await showDocument(id);
  if(action==='retry'){el.disabled=true;await api.post('/v1/retry',{document_id:id});toast('Queued for processing.');if($('dialog').open)$('dialog').close();await render()}
  if(action==='archive-document')modal('Archive document?',`<p>This removes the document from normal search. Its source file will be kept.</p>${button('Archive','confirm-archive',id,'danger')}`);
  if(action==='confirm-archive'){await api.delete('/v1/documents/'+id);$('dialog').close();toast('Document archived.');await render()}
  if(action==='restore-document'){await api.post('/v1/restore',{document_id:id});$('dialog').close();toast('Document restored.');await render()}
  if(action==='new-version')modal('Upload a new version',`<p>This keeps previous source files and citations, and replaces the version used for new searches.</p><form data-form="version" data-id="${id}"><label for="revision-file">PDF or DOCX</label><input id="revision-file" name="file" type="file" accept=".pdf,.docx" required><div data-error></div><br><button type="submit" class="btn primary">Upload version</button></form>`);
  if(action==='download-original'){const d=await api.get('/v1/documents/'+id+'/source',{include_original:true,...(el.dataset.version?{version_id:el.dataset.version}:{})});const data=Uint8Array.from(atob(d.content_base64),c=>c.charCodeAt(0));download(new Blob([data],{type:d.mime_type}),d.filename||'source.pdf')}
  if(action==='source'){
   const d=await api.get('/v1/documents/'+el.dataset.document+'/source',{version_id:el.dataset.version,node_id:el.dataset.node,page:el.dataset.page});
   modal(d.title,`<p class="muted">${esc(d.filename)} · Page ${d.page?.number||el.dataset.page}</p><span class="badge">Version ${esc(d.document_version_id)}</span>${notice(d.extraction_warning||'Inspect this page and compare with the original file.')}<h3>Extracted source text</h3><div class="quote">${esc(d.page?.text||d.node?.text||'No extracted text available for this page.')}</div><details><summary>Surrounding page text</summary><div class="quote">${esc(d.page?.text||'Not available')}</div></details><button class="btn" data-action="download-original" data-id="${d.document_id}" data-version="${d.document_version_id}">Download original</button>`);
  }
  if(action==='copy-answer'){const text=answerExport();try{await navigator.clipboard.writeText(text);toast('Answer and references copied.')}catch{modal('Copy answer',`<textarea class="quote" rows="14" id="copy-text" readonly>${esc(text)}</textarea><p>Select the text and copy it.</p>`);$('copy-text').select()}}
  if(action==='download-answer')download(answerExport(),'legal-library-answer.txt');
  if(action==='history'){const epoch=state.epoch;const h=await api.get('/v1/history/'+id);if(epoch!==state.epoch||!$('results'))return;$('results').innerHTML=answerView(h.answer,h.question);$('results').scrollIntoView({block:'start'})}
  if(action==='delete-history'){await api.delete('/v1/history/'+id);toast('Saved answer deleted.');await render()}
  if(action==='revoke-session'){await api.delete('/v1/account/sessions/'+id);await init()}
  if(action==='invite'){const data=await api.post('/v1/invitations',{});modal('Invitation created',`<p>Share this one-time link privately with a colleague. It expires ${fmtDate(data.expires_at)}.</p><code class="code">${esc(location.origin+'/#/signup?code='+data.code)}</code><p class="muted">The recipient can create an approved member account. Collections still need to be shared separately.</p>`)}
  if(action==='reset-code'){const data=await api.post('/v1/accounts/'+id+'/reset-code');modal('Password recovery code',`<p>Give this code privately to the account owner. It expires in one hour and can be used once.</p><code class="code">${esc(data.code)}</code><p>They can choose “Forgot password?” on the sign-in page.</p>`)}
  if(['approve','disable','make-admin','make-member'].includes(action)){const update=action==='approve'?{state:'active'}:action==='disable'?{state:'disabled'}:{role:action==='make-admin'?'admin':'member'};await api.patch('/v1/accounts/'+id,update);toast('Account updated.');await render()}
  if(action==='test-provider'){const form=el.closest('form');if(!form.reportValidity())return;const body=Object.fromEntries(new FormData(form));if(!body.api_key&&body.base_url.replace(/\/$/,'')===state.config.base_url.replace(/\/$/,''))delete body.api_key;el.disabled=true;const data=await api.post('/v1/setup/test',body);$('provider-test').innerHTML=notice(data.message,data.reachable?'success':'warning')}
  if(action==='local-mode'){await api.post('/v1/setup/local');state.status=await api.get('/v1/setup/status');toast('Local processing enabled.');await render()}
  if(action==='server-status'){const data=await api.get('/v1/system');$('server-status').innerHTML=notice('The server is responding. '+(data.document_count??'')+' documents visible to your account.','success')}
 }catch(error){if(error.name!=='AbortError')toast(error.message,true)}finally{el.disabled=false}
});
window.addEventListener('hashchange',()=>{if($('dialog').open)$('dialog').close();render()});
window.addEventListener('beforeunload',event=>{if(state.uploadBusy){event.preventDefault();event.returnValue='';}});
window.addEventListener('session-expired',()=>{if(state.user){clearSession();toast('Your session ended. Please sign in again.');navigate('/login');render()}});
init();
