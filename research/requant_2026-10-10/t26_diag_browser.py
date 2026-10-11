# t26 執行器:在網頁(本機伺服器上的 index.html,行情從 gist 即時抓)裡跑 t26_qmdiag.js,
#   ① 五檔(MU、SNDK、TSM、NVDA、META)2025-10-10~2026-10-09 逐日逐條件 → t26_diag_5.json
#   ② 圖層:250 日圖上實際畫出的字、圖的日期範圍 → 與事件比對
#   ③ 全追蹤宇宙(chipSyms 去掉槓桿/反向 ETF、日K ≥70 根)同一期間的條件統計 → t26_diag_universe.json
# 用法:python3 t26_diag_browser.py(需要 Playwright + Chromium;repo 根目錄當網站根目錄)
import asyncio, json, os, subprocess, sys, time
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FROM, TO = "2025-10-10", "2026-10-09"; FIVE = ["MU", "SNDK", "TSM", "NVDA", "META"]; PORT = 8799
DIAG = open(os.path.join(HERE, "t26_qmdiag.js"), encoding="utf-8").read()
CHART = """()=>{const D=document.getElementById('cockpit').data||[];const k=D.find(t=>t.type==='candlestick');
  const marks=[];D.filter(t=>/^量化/.test(t.name||'')&&t.name!=='量化盤中').forEach(t=>t.y.forEach((v,i)=>{if(v!=null&&String(t.text[i]||'').trim())marks.push(t.name.slice(2)+'|'+String(t.x[i]));}));
  return {n:k?k.x.length:0,x0:k?String(k.x[0]):null,x1:k?String(k.x[k.x.length-1]):null,marks:marks.sort()};}"""
async def main():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); out = {"five": {}, "universe": {}}
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
            ctx = await b.new_context(viewport={"width": 1400, "height": 1000}, ignore_https_errors=True, service_workers="block")
            pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="domcontentloaded", timeout=120000)
            for _ in range(120):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL"): break
                await pg.wait_for_timeout(1000)
            await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
            for _ in range(40):
                if await pg.evaluate("()=>!!QQQK"): break
                await pg.wait_for_timeout(500)
            await pg.add_script_tag(content=DIAG)
            out["build"] = await pg.evaluate("()=>BUILD"); out["lastDone"] = await pg.evaluate("()=>tjLastDone()")
            await pg.evaluate("()=>{CHIP_WIN=250;}")
            for s in FIVE:
                await pg.evaluate("(s)=>{CHIP_SYM=s;ensureChipK(s);renderChips();}", s)
                for _ in range(40):
                    await pg.wait_for_timeout(500)
                    if await pg.evaluate("(s)=>!!(CHIPK[s]&&CHIPK[s].bars)", s): break
                await pg.wait_for_timeout(2500)
                r = await pg.evaluate("([s,a,z])=>{const r=qmDiag(s,a,z);r.summary=qmDiagSummary(r);return r;}", [s, FROM, TO]); r["chart"] = await pg.evaluate(CHART)
                out["five"][s] = r; print(s, "rows", len(r["rows"]), "replay", r["replayMatches"], "chart", r["chart"]["n"], r["chart"]["x0"], "→", r["chart"]["x1"], flush=True)
            syms = await pg.evaluate("()=>chipSyms().filter(s=>!(s in TK_UL)&&!TK_INV.has(s))")
            for k in range(0, len(syms), 25):
                chunk = syms[k:k + 25]
                await pg.evaluate("(L)=>L.forEach(s=>{try{ensureChipK(s);}catch(_){}})", chunk)
                for _ in range(40):
                    if await pg.evaluate("(L)=>L.filter(s=>CHIPK[s]&&CHIPK[s].bars).length", chunk) == len(chunk): break
                    await pg.wait_for_timeout(500)
                for s in chunk:
                    if await pg.evaluate("(s)=>!!(CHIPK[s]&&CHIPK[s].bars&&chipBars(s,'d').length>=70)", s):
                        try: out["universe"][s] = await pg.evaluate("([s,a,z])=>{const r=qmDiag(s,a,z);return {sym:s,bars:r.bars,first:r.first,last:r.last,fmDays:r.fmDays,replayMatches:r.replayMatches,summary:qmDiagSummary(r),events:r.events};}", [s, FROM, TO])
                        except Exception as e: out["universe"][s] = {"err": str(e)[:200]}
            out["universeCandidates"] = len(syms); out["errors"] = errs[:10]
            print("universe", len(out["universe"]), "of", len(syms), "errors", errs[:3], flush=True)
            await b.close()
    finally: srv.terminate()
    json.dump(out["five"], open(os.path.join(HERE, "t26_diag_5.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    uni = {s: {k: v for k, v in r.items()} for s, r in out["universe"].items()}
    json.dump({"build": out["build"], "lastDone": out["lastDone"], "candidates": out["universeCandidates"], "rows": uni},
              open(os.path.join(HERE, "t26_diag_universe.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    json.dump({"build": out["build"], "lastDone": out["lastDone"], "errors": out["errors"]}, open(os.path.join(HERE, "t26_diag_meta.json"), "w"))
asyncio.run(main())
