# t32 線上複驗:Pages 上線後,桌機/手機各開一次(不攔截、用線上資料)— BUILD、頁面錯誤、6 檔 250 日記號與 t32 S9(新開頁面)相同
#   用法:python3 t32_live_check.py t32_refresh_test.json
import asyncio, json, os, sys
from playwright.async_api import async_playwright
URL="https://groupuie.github.io/market-flow-dashboard/"
SY=["MU","SNDK","TSM","NVDA","META","SLB"]
CAP="""()=>{const T=(document.getElementById('cockpit')||{}).data||[];const m=[];T.filter(t=>/^量化/.test(t.name||'')&&t.name!=='量化盤中').forEach(t=>t.y.forEach((v,i)=>{if(v!=null&&String(t.text[i]||'').trim())m.push(t.name.slice(2)+'|'+String(t.x[i]));}));
 const q=document.querySelector('#qstrip .sbar');return {build:BUILD,sym:CHIP_SYM,marks:m.sort(),qbar:q?q.innerText.replace(/\\s+/g,' ').trim():'',plot:!!document.querySelector('#cockpit .plot-container')};}"""
async def main():
    ref=json.load(open(sys.argv[1]))["res"]["new"]["S9_13檔"]["res"]
    out={}
    async with async_playwright() as p:
        b=await p.chromium.launch(args=["--ignore-certificate-errors","--proxy-server="+os.environ.get("HTTPS_PROXY","")])
        for tag,kw in (("desktop",dict(viewport={"width":1400,"height":1000})),("mobile",dict(viewport={"width":390,"height":844},is_mobile=True,has_touch=True,device_scale_factor=3))):
            ctx=await b.new_context(ignore_https_errors=True,service_workers="block",**kw); pg=await ctx.new_page(); errs=[]
            pg.on("pageerror",lambda e:errs.append(str(e)))
            await pg.goto(URL+"?v=chk",wait_until="domcontentloaded",timeout=120000)
            for _ in range(120):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&!!EXTDF"): break
                await pg.wait_for_timeout(1000)
            r={"build":await pg.evaluate("()=>BUILD"),"syms":{}}
            syms=SY if tag=="desktop" else ["NVDA","MU"]
            for s in syms:
                await pg.evaluate("(s)=>{CHIP_WIN=250;CHIP_SYM=s;ensureChipK(s);renderChips();}",s)
                for _ in range(40):
                    await pg.wait_for_timeout(500)
                    if await pg.evaluate("(s)=>!!(CHIPK[s]&&CHIPK[s].bars)&&(document.getElementById('cockpit').dataset.sig||'').startsWith(s+':')",s): break
                await pg.wait_for_timeout(2500)
                c=await pg.evaluate(CAP); c["same_marks_as_t32_S9"]=(c["marks"]==ref[s]["marks"]) if s in ref else None
                r["syms"][s]=c
            r["errors"]=errs[:5]; out[tag]=r; await ctx.close()
        await b.close()
    json.dump(out,open(os.path.join(os.path.dirname(sys.argv[1]),"t32_live_check.json"),"w"),ensure_ascii=False,indent=1)
    for tag,r in out.items():
        print(tag,"BUILD",r["build"],"errors",r["errors"])
        for s,c in r["syms"].items(): print("  ",s,"plot",c["plot"],"marks",len(c["marks"]),"same_as_S9",c["same_marks_as_t32_S9"],"|",c["qbar"][:46])
asyncio.run(main())
