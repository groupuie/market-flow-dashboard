import asyncio, os, sys, json, subprocess, time, tempfile, shutil
from playwright.async_api import async_playwright
from t25_browser_q3 import REPO, OLD, TRJS
PORT=8797; CASES=[("BKNG","2026-08-27"),("MRNA","2026-07-16"),("CRDO","2025-01-27"),("TWLO","2026-08-07")]
async def main():
    root=tempfile.mkdtemp(prefix="q3c_")
    for nm in os.listdir(REPO):
        if nm not in ("out","research",".git"): os.symlink(os.path.join(REPO,nm),os.path.join(root,nm))
    shutil.copy(OLD,os.path.join(root,"index_old.html"))
    srv=subprocess.Popen([sys.executable,"-m","http.server",str(PORT),"--bind","127.0.0.1"],cwd=root,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); time.sleep(1)
    res={}
    try:
        async with async_playwright() as p:
            b=await p.chromium.launch(args=["--ignore-certificate-errors","--proxy-server="+os.environ.get("HTTPS_PROXY"),"--proxy-bypass-list=127.0.0.1;localhost"])
            for tag,page in (("old","index_old.html"),("new","index.html")):
                ctx=await b.new_context(viewport={"width":1400,"height":1000},ignore_https_errors=True,service_workers="block"); pg=await ctx.new_page(); errs=[]
                pg.on("pageerror",lambda e: errs.append("PAGEERROR "+str(e)))
                await pg.goto(f"http://127.0.0.1:{PORT}/{page}",wait_until="domcontentloaded",timeout=120000)
                for _ in range(120):
                    if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL"): break
                    await pg.wait_for_timeout(1000)
                await pg.evaluate("()=>{try{ensureQQQK();}catch(_){};window.__ld=tjLastDone;window.__sd=snapDate;}")
                for s,d in CASES:
                    await pg.evaluate("(s)=>{ensureChipK(s);}",s)
                    for _ in range(30):
                        await pg.wait_for_timeout(500)
                        if await pg.evaluate("(s)=>!!(CHIPK[s]&&CHIPK[s].bars)",s): break
                    await pg.evaluate("([s,d])=>{tjLastDone=()=>d;snapDate=()=>d;CHIP_SYM=s;document.getElementById('cockpit').dataset.sig='';renderChips();}",[s,d])
                    await pg.wait_for_timeout(2500)
                    t=await pg.evaluate(TRJS); btn=await pg.query_selector("#qstrip .sbib"); await btn.click(); await pg.wait_for_timeout(500)
                    pop=await pg.evaluate("()=>{const p=document.getElementById('stripPop');return p&&p.style.display!=='none'?p.innerText:null;}")
                    await btn.click(); await pg.wait_for_timeout(200)
                    lines=(pop or "").split("\n"); why=[l for l in lines if l.startswith("為什麼") or l.startswith("接下來")]
                    res.setdefault(tag,{})[f"{s}@{d}"]={"bar":t["bar"],"why":why}
                    print(tag,s,d,"|",t["bar"][:90],"|"," / ".join(why)[:220],flush=True)
                print(tag,"errors",errs[:5]); await ctx.close()
            await b.close()
    finally:
        srv.terminate(); shutil.rmtree(root,ignore_errors=True)
    json.dump(res,open("q3_conflict_real.json","w"),ensure_ascii=False,indent=1)
asyncio.run(main())
