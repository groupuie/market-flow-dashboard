# t28 執行器(Codex v0.3 買點診斷核對):在網頁裡(本機伺服器上的 repo index.html,行情與⑦資金照網站從 gist 即時抓)
#   ① 五檔 SPY、QQQ、AMD、PLTR、AVGO 在 2026-09-01~10-09 的正式事件、研究副本(拿掉近 40 根新高)事件、逐日條件 → t28_buydiag.json
#   ② 截斷檢查:每個截斷日只用 ≤ 那天的日K與⑦重算,那天以前的 買/加 要與全資料相同(正式版與研究副本各一次)
# 用法:python3 t28_buydiag_browser.py(需要 Playwright + Chromium;repo 根目錄當網站根目錄)
import asyncio, json, os, subprocess, sys, time
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
FROM, TO = "2026-09-01", "2026-10-09"; SYMS = ["SPY", "QQQ", "AMD", "PLTR", "AVGO"]; PORT = 8797
JS = [open(os.path.join(HERE, f), encoding="utf-8").read() for f in ("t28_qmBuyDay_codex.js", "t28_buydiag.js")]
async def main():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); out = {"window": {}, "prefix": []}
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
            ctx = await b.new_context(viewport={"width": 1400, "height": 1000}, ignore_https_errors=True, service_workers="block")
            pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(f"http://127.0.0.1:{PORT}/index.html", wait_until="domcontentloaded", timeout=120000)
            for _ in range(180):   # 等:圖、資金氣候、⑦ 擴充檔(ext_flows)、⑦ 深歷史(≥250 天)
                ok = await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&!!EXTDF&&Object.keys(chipDaily()).length>=250")
                if ok: break
                await pg.wait_for_timeout(1000)
            await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
            for s in SYMS: await pg.evaluate("(s)=>{try{ensureChipK(s);}catch(_){}}", s)
            for _ in range(80):
                if await pg.evaluate("(L)=>!!QQQK&&L.every(s=>CHIPK[s]&&CHIPK[s].bars)", SYMS): break
                await pg.wait_for_timeout(500)
            for js in JS: await pg.add_script_tag(content=js)
            out["build"] = await pg.evaluate("()=>BUILD"); out["lastDone"] = await pg.evaluate("()=>tjLastDone()")
            out["flowDays"] = await pg.evaluate("()=>{const k=Object.keys(chipDaily()).sort();return [k.length,k[0],k[k.length-1]];}")
            out["climateLast"] = await pg.evaluate("()=>FCL&&FCL._ld||null")
            for s in SYMS:
                r = await pg.evaluate("([s,a,z])=>qm28Window(s,a,z)", [s, FROM, TO]); out["window"][s] = r
                print(s, "bars", r["bars"], r["first"], "→", r["last"], "⑦", r["fmDays"], "| 正式", [e for e in r["eventsOrig"] if e[0] in "買加"], "| 研究副本", [e for e in r["eventsNoHigh"] if e[0] in "買加"], flush=True)
            for s in SYMS:
                for v in ("orig", "nohigh"):
                    r = await pg.evaluate("([s,a,z,v])=>qm28Prefix(s,a,z,v)", [s, FROM, TO, v]); out["prefix"].append(r)
                    print("截斷", s, v, r["cutDates"], "天,不一致", r["mismatches"], flush=True)
            out["errors"] = errs[:10]
            await b.close()
    finally: srv.terminate()
    json.dump(out, open(os.path.join(HERE, "t28_buydiag.json"), "w"), ensure_ascii=False, separators=(",", ":"))
    print("errors", out["errors"])
asyncio.run(main())
