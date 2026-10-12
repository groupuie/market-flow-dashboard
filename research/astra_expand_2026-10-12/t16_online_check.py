# t16:v1.5 線上複驗(GitHub Pages)— 線上檔 = repo;桌機 + 手機:
#   Astra 預設關;追蹤股 NVDA/QQQ/MUU × 250 根 Astra 開:記號/強/200 日線 = Python;擴大範圍 HUBS/BRK-B 畫得出來;
#   🧪 Astra 訊號分頁(手機:捲到清單)= today.json;頁面錯誤 0、意外 HTTP 錯誤 0、沒有橫向捲動
#   用法:python3 t16_online_check.py <預期 BUILD> <輸出.json>
import asyncio, json, os, sys, time, hashlib, urllib.request
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(REPO, "research", "swing_tune_2026-10-12"))
import t13_astra_merge_test as T
import t15_site_test as S   # REG / TODAY / UNI / py_marks / py_d200 / LAY(只在 __main__ 跑 main)
WANT, OUT = sys.argv[1], sys.argv[2]
SITE = "https://groupuie.github.io/market-flow-dashboard/"

def fetch(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"}), timeout=60).read()

async def main():
    res = {"want": WANT}
    for k in range(40):
        b = fetch(SITE + "index.html?nc=%d" % time.time())
        if WANT.encode() in b[:300]: break
        time.sleep(15)
    res["bytes_same"] = b == open(os.path.join(REPO, "index.html"), "rb").read(); res["sha"] = hashlib.sha256(b).hexdigest()
    async with async_playwright() as p:
        br = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", "")])
        for tag, vw, vh in (("desktop", 1440, 1000), ("mobile", 390, 844)):
            ctx = await br.new_context(viewport={"width": vw, "height": vh}, service_workers="block")
            pg = await ctx.new_page(); errs = []; bad = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 and "favicon" not in r.url else None)
            await pg.goto(SITE + "?nc=t16" + tag, wait_until="domcontentloaded", timeout=180000)
            for _ in range(180):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&Object.keys(chipDaily()).length>=200&&!!AXU"): break
                await pg.wait_for_timeout(1000)
            await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
            R = {"build": await pg.evaluate("()=>BUILD"), "astra_default": await pg.evaluate("()=>CHIP_ASTRA"), "checks": [], "fallback": []}
            for s in ["NVDA", "QQQ", "MUU"]:
                C = await S.show_v1(pg, s, 250, True)
                for _ in range(30):
                    if await pg.evaluate("()=>!!AXR"): break
                    await pg.wait_for_timeout(500)
                C = await S.show_v1(pg, s, 250, True)
                j = await pg.evaluate(T.JSW, s); want = S.py_marks(j["bars"], C["dates"]); dm = {d[5:]: d for d in C["dates"]}
                got = {(n_, dm.get(x), "強" in (t or "")) for n_, x, y, h, c, t in C["W"]}
                cr = S.py_d200(j["ul"] or s, C["dates"])
                R["checks"].append({"sym": s, "astra_eq_python": got == want, "n": len(got), "strong": sum(1 for g in got if g[2]),
                                    "d200_eq_python": sorted(C["lay"]["d200"]) == cr, "n_d200": len(cr), "strip": (C["as"] or {}).get("bar", "").replace("\n", " ")[:140]})
            for s in ["HUBS", "BRK-B"]:
                C = await S.show_v1(pg, s, 100, True)
                R["fallback"].append(await pg.evaluate("(s)=>({sym:s,ax:(CHIPK[s]||{}).ax||0,n:((CHIPK[s]||{}).bars||[]).length,plot:!!document.querySelector('#cockpit .plot-container'),btn:!!document.getElementById('chipFreeBtn')})", s) | {"marks": len(C["W"])})
            if tag == "desktop": await pg.click('.wsxTab[data-wt="astra"]')
            else: await pg.evaluate("()=>{const e=document.getElementById('axpanel');if(e)e.scrollIntoView({block:'center'});}")
            for _ in range(40):
                if await pg.evaluate("()=>!!document.querySelector('#axpanel table')"): break
                await pg.wait_for_timeout(500)
            day = S.TODAY["days"][0]
            got_all = await pg.evaluate("()=>Array.from(document.querySelectorAll('#axpanel tr')).slice(1).map(tr=>[tr.querySelector('[data-axsym]').dataset.axsym,tr.children[1].innerText.trim().slice(1,2)])")
            R["list_eq_today"] = sorted(map(tuple, got_all)) == sorted((r["s"], r["k"]) for r in S.TODAY["rows"] if r["d"] == day); R["list_n"] = len(got_all)
            R["overflow"] = await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1")
            R["errors"] = [e for e in errs][:10]
            R["http_bad"] = [x for x in bad if not (x[0] == 404 and "gist.githubusercontent.com" in x[1] and "/kline_" in x[1])][:10]
            res[tag] = R; await ctx.close()
        await br.close()
    ok = res["bytes_same"]
    for tag in ("desktop", "mobile"):
        R = res[tag]
        ok = ok and R["build"] == WANT and R["astra_default"] is False and all(c["astra_eq_python"] and c["d200_eq_python"] for c in R["checks"])
        ok = ok and all(f["ax"] == 1 and f["plot"] and f["btn"] and f["n"] > 1000 for f in R["fallback"]) and R["list_eq_today"] and R["list_n"] > 0
        ok = ok and not R["overflow"] and not R["errors"] and not R["http_bad"]
    res["ok"] = bool(ok)
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False)[:2500]); print("ONLINE_OK" if ok else "ONLINE_NOT_OK")

if __name__ == "__main__":
    asyncio.run(main())
