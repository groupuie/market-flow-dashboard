# t14:線上複驗(Astra 合併短線、量化回原版)— 線上檔 = repo;真的點 Astra 按鈕;量化(Astra 關/開)= V0 原版;Astra 記號 = Python;桌機 + 手機
#   用法:python3 t14_online_check.py <預期 BUILD> <V0 原版 index.html> <輸出.json>
import asyncio, json, os, sys, time, hashlib, urllib.request, subprocess, tempfile, shutil
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from swing_ref_v10 import sw_py_v10
import t13_astra_merge_test as T   # 共用 CAP / GO / READY / JSW / show / qkey(不會執行 main:只在 __main__ 跑)
WANT, V0, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SITE = "https://groupuie.github.io/market-flow-dashboard/"
SYMS = ["MU", "NVDA", "QQQ", "NBIS", "BKNG", "MUU"]; WINS = [100, 250]

def fetch(u):
    r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"})
    return urllib.request.urlopen(r, timeout=60).read()

async def main():
    res = {"want": WANT}
    for k in range(40):
        b = fetch(SITE + "index.html?nc=%d" % time.time())
        if WANT.encode() in b[:300]: break
        time.sleep(15)
    local = open(os.path.join(REPO, "index.html"), "rb").read()
    res["bytes_same"] = b == local; res["sha"] = hashlib.sha256(b).hexdigest()
    async with async_playwright() as p:
        br = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        srv, www = T.start_server(V0, 8891)
        try:
            ctx, pg, errs, reqs = await T.open_page(br, 8891)
            v0 = {}
            for s in SYMS:
                for w in WINS: v0[f"{s}:{w}"] = (await T.show(pg, s, w, "d", False))["Q"]
            await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        for tag, vw, vh in (("desktop", 1440, 1000), ("mobile", 390, 844)):
            ctx = await br.new_context(viewport={"width": vw, "height": vh}, service_workers="block")
            pg = await ctx.new_page(); errs = []; bad = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 and "favicon" not in r.url else None)
            await pg.goto(SITE + "?nc=t14" + tag, wait_until="domcontentloaded", timeout=180000)
            for _ in range(180):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&Object.keys(chipDaily()).length>=200"): break
                await pg.wait_for_timeout(1000)
            await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
            for _ in range(40):
                if await pg.evaluate("()=>!!QQQK"): break
                await pg.wait_for_timeout(500)
            R = {"build": await pg.evaluate("()=>BUILD"),
                 "default": await pg.evaluate("()=>({astra:CHIP_ASTRA,legacy:ASTRA_LEGACY,hasSW:typeof CHIP_SW!=='undefined',chipW:!!document.querySelector('.cidxchipW'),pressed:document.querySelector('.cidxchipA').getAttribute('aria-pressed')})"),
                 "checks": []}
            for s in SYMS:
                for w in WINS:
                    off = await T.show(pg, s, w, "d", False); on = await T.show(pg, s, w, "d", True)
                    j = await pg.evaluate(T.JSW, s); py = sw_py_v10(j["bars"])
                    dm = {d[5:]: d for d in on["dates"]}
                    want = set()
                    for d in py["bot"]: want.add(("Astra 底", d))
                    for d in py["b2"]: want.add(("Astra 回檔", d))
                    for d in py["top"]: want.add(("Astra 頂", d))
                    got = {(n_, dm.get(x)) for n_, x, y, h, c, t in on["W"]}
                    inwin = {(n_, d) for n_, d in want if d in set(on["dates"])}
                    R["checks"].append({"key": f"{s}:{w}", "quant_off_same_as_V0": T.qkey(off["Q"]) == T.qkey(v0[f"{s}:{w}"]),
                                        "quant_on_same_as_off": T.qkey(on["Q"]) == T.qkey(off["Q"]), "astra_marks_eq_python": got == inwin,
                                        "n": len(on["W"]), "strip": bool(on["as"] and on["as"]["shown"]), "legacy": on["leg"]})
            await pg.evaluate("()=>{CHIP_SYM='NVDA';CHIP_WIN=100;CHIP_PD='d';CHIP_ASTRA=false;document.getElementById('cockpit').dataset.sig='';renderChips();}")
            await pg.wait_for_timeout(1500); n0 = len((await pg.evaluate(T.CAP))["W"])
            await pg.click(".cidxchipA"); await pg.wait_for_timeout(1800); n1 = len((await pg.evaluate(T.CAP))["W"])
            await pg.click(".cidxchipA"); await pg.wait_for_timeout(1800); n2 = len((await pg.evaluate(T.CAP))["W"])
            R["click"] = [n0, n1, n2]
            R["overflow"] = await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1")
            R["errors"] = errs[:10]; R["http_bad"] = bad[:10]
            res[tag] = R; await ctx.close()
        await br.close()
    ok = res["bytes_same"]
    for tag in ("desktop", "mobile"):
        R = res[tag]; C = R["checks"]
        ok = ok and R["build"] == WANT and not R["default"]["astra"] and not R["default"]["hasSW"] and not R["default"]["chipW"] and not R["errors"] and not R["http_bad"] and not R["overflow"]
        ok = ok and all(c["quant_off_same_as_V0"] and c["quant_on_same_as_off"] and c["astra_marks_eq_python"] and c["strip"] and c["legacy"] == 0 for c in C)
        ok = ok and R["click"][0] == 0 and R["click"][1] > 0 and R["click"][2] == 0
    res["ONLINE_OK"] = bool(ok)
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("bytes_same", res["bytes_same"], res["sha"][:16])
    for tag in ("desktop", "mobile"):
        R = res[tag]; print(tag, R["build"], R["default"], "click", R["click"], "overflow", R["overflow"], "errors", R["errors"], "http_bad", R["http_bad"])
        for c in R["checks"]: print("  ", c)
    print("ONLINE_OK" if ok else "ONLINE FAIL")

if __name__ == "__main__":
    asyncio.run(main())
