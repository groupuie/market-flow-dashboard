import asyncio, os, sys, json, subprocess, time, tempfile, shutil
from playwright.async_api import async_playwright
# 全追蹤宇宙:舊版(上線 16:19Z)vs 新版,同一份即時資料,7 種記號逐日比對(整段歷史)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t25_browser_q3 import EVJS, REPO, OLD, SCR
PORT = 8793
async def main():
    root = tempfile.mkdtemp(prefix="q3u_")
    for nm in os.listdir(REPO):
        if nm not in ("out", "research", ".git"): os.symlink(os.path.join(REPO, nm), os.path.join(root, nm))
    shutil.copy(OLD, os.path.join(root, "index_old.html"))
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); res = {}
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY"), "--proxy-bypass-list=127.0.0.1;localhost"])
            for tag, page in (("old", "index_old.html"), ("new", "index.html")):
                ctx = await b.new_context(viewport={"width": 1200, "height": 900}, ignore_https_errors=True, service_workers="block")
                pg = await ctx.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)))
                await pg.goto(f"http://127.0.0.1:{PORT}/{page}", wait_until="domcontentloaded", timeout=120000)
                for _ in range(120):
                    if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL"): break
                    await pg.wait_for_timeout(1000)
                await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
                syms = await pg.evaluate("()=>chipSyms().filter(s=>!(s in TK_UL)&&!TK_INV.has(s))")
                done = {}
                for k in range(0, len(syms), 25):
                    chunk = syms[k:k + 25]
                    await pg.evaluate("(L)=>L.forEach(s=>{try{ensureChipK(s);}catch(_){}})", chunk)
                    for _ in range(40):
                        ok = await pg.evaluate("(L)=>L.filter(s=>CHIPK[s]&&CHIPK[s].bars).length", chunk)
                        if ok == len(chunk): break
                        await pg.wait_for_timeout(500)
                    for s in chunk:
                        try:
                            if await pg.evaluate("(s)=>!!(CHIPK[s]&&CHIPK[s].bars&&chipBars(s,'d').length>=70)", s):
                                done[s] = await pg.evaluate(EVJS, s)
                        except Exception as e:
                            done[s] = {"err": str(e)[:200]}
                print(tag, await pg.evaluate("()=>BUILD"), "symbols", len(syms), "computed", len(done), "QQQK", await pg.evaluate("()=>!!QQQK"), "errors", errs[:5], flush=True)
                res[tag] = done; await ctx.close()
            await b.close()
    finally:
        srv.terminate(); shutil.rmtree(root, ignore_errors=True)
    json.dump(res, open(os.path.join(SCR, "q3_universe.json"), "w"), ensure_ascii=False)
asyncio.run(main())
