const BACKEND=process.env.I9_API_URL||'http://127.0.0.1:8000';
async function proxy(request:Request,context:{params:Promise<{path:string[]}>}){
 const {path}=await context.params;const url=new URL(request.url);
 try{const headers=new Headers({'Content-Type':'application/json'});for(const key of ['X-Admin-Key','X-API-Key']){const v=request.headers.get(key);if(v)headers.set(key,v)}
 const r=await fetch(BACKEND+'/api/v3/'+path.map(encodeURIComponent).join('/')+url.search,{method:request.method,headers,body:request.method==='POST'?await request.text():undefined,signal:AbortSignal.timeout(120000)});
 const h=new Headers({'Cache-Control':'no-store'});const type=r.headers.get('content-type');if(type)h.set('content-type',type);return new Response(r.body,{status:r.status,headers:h})
 }catch{return Response.json({detail:'Serviço de dados indisponível. Verifique se a API está em execução.'},{status:503})}
}
export const GET=proxy;export const POST=proxy;
