const BACKEND=process.env.I9_API_URL||'http://127.0.0.1:8000';
async function proxy(request:Request,context:{params:Promise<{path:string[]}>}){
 const {path}=await context.params;const url=new URL(request.url);
 try{const r=await fetch(BACKEND+'/api/v1/'+path.map(encodeURIComponent).join('/')+url.search,{method:request.method,headers:{'Content-Type':'application/json',...(request.headers.get('X-Admin-Key')?{'X-Admin-Key':request.headers.get('X-Admin-Key')!}:{})},body:request.method==='POST'?await request.text():undefined,signal:AbortSignal.timeout(120000)});const h=new Headers();for(const n of ['content-type','content-disposition']){const v=r.headers.get(n);if(v)h.set(n,v)}h.set('Cache-Control','no-store');return new Response(r.body,{status:r.status,headers:h})}catch{return Response.json({detail:'API indisponível. Inicie o servidor Python da i9+.'},{status:503})}
}
export const GET=proxy;export const POST=proxy;
