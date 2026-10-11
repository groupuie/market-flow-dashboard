# 診斷:t3 第二輪 old_vs_new_off_layout_same 有 3 組只差 layout.autosize(Plotly responsive 重排旗標)→ 舊/新各畫 8 次、逐鍵比對
import asyncio, json, os, sys, shutil, tempfile, subprocess, time
sys.path.insert(0,'/home/claude/market-flow-dashboard/research/astra_v0.4_2026-10-11')
REPO='/home/claude/market-flow-dashboard'; SP='/tmp/claude-0/-home-claude-market-flow-dashboard/6a667a86-bd96-51e3-8a50-02ea95c10282/scratchpad'
from playwright.async_api import async_playwright
import importlib.util
spec=importlib.util.spec_from_file_location('t3',REPO+'/research/astra_v0.4_2026-10-11/t3_astra_lane_test.py')
src=open(REPO+'/research/astra_v0.4_2026-10-11/t3_astra_lane_test.py').read()
src=src.split('async def main():')[0].replace('OLD, NEW, OUT = sys.argv[1], sys.argv[2], sys.argv[3]','')
ns={'__file__':REPO+'/research/astra_v0.4_2026-10-11/t3_astra_lane_test.py'}; exec(src,ns)
LAY="""()=>{const L=document.getElementById('cockpit').layout;const o={};Object.keys(L).forEach(k=>{if(k!=='annotations'&&k!=='datarevision')o[k]=L[k];});return JSON.stringify(o);}"""
async def grab(b,html,port,events):
    srv,www=ns['start_server'](html,port,events)
    try:
        ctx,pg,errs=await ns['open_page'](b,port)
        out={}
        for s,w in (('INTC',250),('NVDA',30),('NVDA',250),('MU',100)):
            for rep in (1,2):
                await ns['show'](pg,s,w,'d',False)
                out[f'{s}:{w}:{rep}']=json.loads(await pg.evaluate(LAY))
        await ctx.close(); return out
    finally:
        srv.terminate(); shutil.rmtree(www,ignore_errors=True)
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(args=["--proxy-server="+os.environ.get("HTTPS_PROXY",""),"--proxy-bypass-list=127.0.0.1;localhost"])
        A=await grab(b,SP+'/index_before_v04.html',8841,False)
        B=await grab(b,SP+'/index_final_v04.html',8842,True)
        await b.close()
    def diff(a,b,path=''):
        out=[]
        if isinstance(a,dict) and isinstance(b,dict):
            for k in sorted(set(a)|set(b)):
                if k not in a or k not in b: out.append((path+'/'+k,'missing', a.get(k) if isinstance(a,dict) else None, b.get(k)))
                else: out+=diff(a[k],b[k],path+'/'+k)
        elif isinstance(a,list) and isinstance(b,list) and len(a)==len(b):
            for i,(x,y) in enumerate(zip(a,b)): out+=diff(x,y,path+f'[{i}]')
        elif a!=b: out.append((path,str(a)[:120],str(b)[:120]))
        return out
    for k in A:
        d=diff(A[k],B[k]); kk=k[:-1]+('2' if k.endswith('1') else '1'); d2=diff(A[k],A[kk])
        print(k,'old-vs-new diffs:',len(d), d[:6]); print('   old rep1 vs rep2 diffs:',len(d2), d2[:3])
asyncio.run(main())
