# t26 補充:全追蹤宇宙的涵蓋清單(哪些代號有進 t26_diag_universe.json、哪些沒有、為什麼)
#   候選 = chipSyms() 去掉槓桿/反向 ETF(TK_UL / TK_INV)—— 與 t26_diag_browser.py 同一個篩法
#   沒進的原因:日K 不到 70 根,或網頁抓不到日K(CHIPK[s] 沒有 bars)
# 輸出 t26_diag_coverage.json:{build,lastDone,candidates:[...],bars:{sym:n 或 null}}
import asyncio, json, os, subprocess, sys, time
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", "..")); PORT = 8798
async def main():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); out = {}
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
            ctx = await b.new_context(viewport={"width": 1400, "height": 1000}, ignore_https_errors=True, service_workers="block")
            pg = await ctx.new_page()
            await pg.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="domcontentloaded", timeout=120000)
            for _ in range(120):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL"): break
                await pg.wait_for_timeout(1000)
            out["build"] = await pg.evaluate("()=>BUILD"); out["lastDone"] = await pg.evaluate("()=>tjLastDone()")
            syms = await pg.evaluate("()=>chipSyms().filter(s=>!(s in TK_UL)&&!TK_INV.has(s))")
            out["candidates"] = syms; out["allChipSyms"] = await pg.evaluate("()=>chipSyms().length")
            for k in range(0, len(syms), 25):
                chunk = syms[k:k + 25]
                await pg.evaluate("(L)=>L.forEach(s=>{try{ensureChipK(s);}catch(_){}})", chunk)
                for _ in range(40):
                    if await pg.evaluate("(L)=>L.filter(s=>(CHIPK[s]&&CHIPK[s].bars)||CHIPK[s+'_none']).length", chunk) == len(chunk): break
                    await pg.wait_for_timeout(500)
            out["bars"] = await pg.evaluate("(L)=>{const o={};L.forEach(s=>{o[s]=(CHIPK[s]&&CHIPK[s].bars)?chipBars(s,'d').filter(b=>b[0]<=tjLastDone()).length:(CHIPK[s+'_none']?'none':null);});return o;}", syms)
            await b.close()
    finally: srv.terminate()
    json.dump(out, open(os.path.join(HERE, "t26_diag_coverage.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    miss = {s: n for s, n in out["bars"].items() if not (isinstance(n, int) and n >= 70)}
    print("candidates", len(out["candidates"]), "of chipSyms", out["allChipSyms"], "| <70 bars or no K:", len(miss), miss)
asyncio.run(main())
