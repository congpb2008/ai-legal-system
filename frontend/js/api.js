'use strict';
class ApiClient {
 constructor(){this.pending=new Set();this.generation=0;}
 cancelPending(){this.generation++;for(const controller of this.pending)controller.abort();this.pending.clear();}
 async request(method,path,body,params={}) {
  const generation=this.generation;const controller=new AbortController();this.pending.add(controller);
  const url=new URL('/api'+path,location.origin);
  Object.entries(params).forEach(([k,v])=>{if(v!==''&&v!=null)url.searchParams.set(k,v)});
  const opts={method,credentials:'same-origin',signal:controller.signal,headers:{'X-Requested-With':'LegalPlatform'}};
  if(body instanceof FormData)opts.body=body;
  else if(body!==undefined){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body)}
  try {
   const response=await fetch(url,opts);const result=await response.json();
   if(generation!==this.generation)throw new DOMException('Request cancelled.','AbortError');
   if(!result.success)throw Object.assign(new Error(i18n.message(result.error?.message||'Please try again.')),{status:response.status,code:result.error?.code});
   return result.data;
  } catch(error) {
   if(generation!==this.generation)throw new DOMException('Request cancelled.','AbortError');
   if(error.status===401&&!path.startsWith('/v1/auth/'))window.dispatchEvent(new Event('session-expired'));
   throw error instanceof TypeError?new Error(i18n.t('Cannot reach the server. Check your connection and try again.')):error;
  } finally {this.pending.delete(controller);}
 }
 get(p,q){return this.request('GET',p,undefined,q)}
 post(p,b={}){return this.request('POST',p,b)}
 patch(p,b={}){return this.request('PATCH',p,b)}
 delete(p){return this.request('DELETE',p)}
}
try{localStorage.removeItem('auth_token');}catch{}
const api=new ApiClient();
