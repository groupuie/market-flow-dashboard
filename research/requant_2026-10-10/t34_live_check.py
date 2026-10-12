# t34 線上複驗:Pages 上線後(BUILD 2026-10-12T02:45Z)桌機 BKNG/NVDA/MU、手機 BKNG 的量化狀態列與詳情「接下來」那一行;頁面錯誤、HTTP ≥400 回應
#   用法:python3 t34_live_check.py > t34_live_check.json
import asyncio, os, json
from playwright.async_api import async_playwright
URL="https://groupuie.github.io/market-flow-dashboard/"
CAP="""()=>{const q=document.querySelector('#qstrip .sbar');const txt=h=>String(h||'').replace(/<br>/g,' ⏎ ').replace(/<[^>]+>/g,'').replace(/\\s+/g,' ').trim();const pop=q?txt(q._pop):'';
 return {build:BUILD,sym:CHIP_SYM,bar:q?txt(q.innerHTML):'',next:(pop.match(/接下來:[^⏎]*/)||[''])[0].slice(0,110),plot:!!document.querySelector('#cockpit .plot-container')};}"""
async def main():
    out={}
    async with async_playwright() as p:
        b=await p.chromium.launch(args=["--ignore-certificate-errors","--proxy-server="+os.environ.get("HTTPS_PROXY","")])
        for tag,kw in (("desktop",dict(viewport={"width":1440,"height":1000})),("mobile",dict(viewport={"width":390,"height":844},is_mobile=True,has_touch=True,device_scale_factor=3))):
            ctx=await b.new_context(ignore_https_errors=True,service_workers="block",**kw); pg=await ctx.new_page(); errs=[]; bad=[]
            pg.on("pageerror",lambda e:errs.append(str(e)[:200])); pg.on("response",lambda r: bad.append((r.status,r.url[:120])) if r.status>=400 else None)
            await pg.goto(URL+"?v=chk2",wait_until="domcontentloaded",timeout=120000)
            for _ in range(90):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&!!EXTDF"): break
                await pg.wait_for_timeout(1000)
            r={}
            for s in (["BKNG","NVDA","MU"] if tag=="desktop" else ["BKNG"]):
                await pg.fill("#chipInput",s); await pg.press("#chipInput","Enter")
                for _ in range(40):
                    await pg.wait_for_timeout(500)
                    if await pg.evaluate("(s)=>CHIP_SYM===s&&!!(CHIPK[s]&&CHIPK[s].bars)&&(document.getElementById('cockpit').dataset.sig||'').startsWith(s+':')",s): break
                await pg.wait_for_timeout(2500); r[s]=await pg.evaluate(CAP)
            out[tag]={"syms":r,"errors":errs,"bad":bad}; await ctx.close()
        await b.close()
    print(json.dumps(out,ensure_ascii=False,indent=1))
asyncio.run(main())
