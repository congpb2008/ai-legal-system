'use strict';
class ApiClient {
 async request(method,path,body,params={}) {
  const url=new URL('/api'+path,location.origin);
  Object.entries(params).forEach(([k,v])=>{if(v!==''&&v!=null)url.searchParams.set(k,v)});
  const opts={method,credentials:'same-origin',headers:{'X-Requested-With':'LegalPlatform'}};
  if(body instanceof FormData)opts.body=body;
  else if(body!==undefined){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body)}
  try {
   const response=await fetch(url,opts);const result=await response.json();
   if(!result.success)throw Object.assign(new Error(result.error?.message||'Please try again.'),{status:response.status,code:result.error?.code});
   return result.data;
  } catch(error) {
   if(error.status===401&&!path.startsWith('/v1/auth/'))window.dispatchEvent(new Event('session-expired'));
   throw error instanceof TypeError?new Error('Cannot reach the server. Check your connection and try again.'):error;
  }
 }
 get(p,q){return this.request('GET',p,undefined,q)}
 post(p,b={}){return this.request('POST',p,b)}
 patch(p,b={}){return this.request('PATCH',p,b)}
 delete(p){return this.request('DELETE',p)}
}
localStorage.removeItem('auth_token');
const api=new ApiClient();