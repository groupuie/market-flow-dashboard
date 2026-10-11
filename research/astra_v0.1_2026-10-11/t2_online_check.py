# t2:部署後線上複驗(GitHub Pages)
#   用法:python3 t2_online_check.py <預期 BUILD> <expected_events_node.json> <輸出.json>
#   ① 線上三個檔(index.html、astra-flow.js、astra-dashboard-adapter.js)與 repo 逐位元相同
#   ② 桌機 1440 / 手機 390:真的點「Astra」按鈕;MU、TSM、NVDA 的記號日期 = Node 離線結果;Astra 開關前後 量化記號與狀態列相同;頁面錯誤 0
import asyncio, hashlib, json, os, sys, urllib.request
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BUILD, EXP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
EXPECTED = json.load(open(EXP)); SITE = "https://groupuie.github.io/market-flow-dashboard/"

def fetch(path):
    req = urllib.request.Request(SITE + path + ("&" if "?" in path else "?") + "nocache=" + str(os.getpid()), headers={"Cache-Control": "no-cache"})
    return urllib.request.urlopen(req, timeout=60).read()

CAP = """()=>{const gd=document.getElementById('cockpit');const D=(gd&&gd.data)||[];
  const A=D.filter(t=>t.meta==='astra-flow'),Q=D.filter(t=>/^量化/.test(t.name||''));
  const rows=cockpitRows(CHIP_SYM)||[];const w=Math.max(30,Math.min(CHIP_WIN,250));const dates=rows.slice(-w).map(r=>r.d);const xl=D[0].x;
  const strip=id=>{const e=document.getElementById(id);return (e&&e.style.display!=='none')?e.innerText.replace(/\\s+/g,' ').trim():'';};
  return {astra:A.flatMap(t=>t.x.map(x=>[t.name.replace('Astra ',''),dates[xl.indexOf(x)]])).sort(),
    q:JSON.stringify(Q.map(t=>({n:t.name,x:t.x,y:t.y,text:t.text,c:t.customdata}))),qbar:strip('qstrip'),abar:strip('astrastrip'),
    win:dates.length?[dates[0],dates[dates.length-1]]:null,xType:gd._fullLayout.xaxis.type};}"""

async def main():
    out = {"files": {}}
    for f in ("index.html", "astra-flow.js?v=0.1.0", "astra-dashboard-adapter.js?v=0.1.0"):
        live = hashlib.sha256(fetch(f)).hexdigest()
        local = hashlib.sha256(open(os.path.join(REPO, f.split("?")[0]), "rb").read()).hexdigest()
        out["files"][f] = {"live": live, "repo": local, "same": live == local}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        for tag, vw, vh in (("desktop", 1440, 1000), ("mobile", 390, 844)):
            ctx = await b.new_context(viewport={"width": vw, "height": vh}, service_workers="block")
            pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append("console.error: " + m.text) if m.type == "error" else None)
            await pg.goto(SITE + "?nocache=" + tag, wait_until="domcontentloaded", timeout=180000)
            for _ in range(180):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&!!document.querySelector('#chipidx .cidxchipA')"): break
                await pg.wait_for_timeout(1000)
            r = {"build": await pg.evaluate("()=>BUILD"), "astraLoaded": await pg.evaluate("()=>!!window.AstraDashboard&&AstraDashboard.VERSION"),
                 "defaultOff": await pg.evaluate("()=>CHIP_ASTRA===false"), "symbols": {}}
            for s in ("MU", "TSM", "NVDA"):
                await pg.evaluate("(s)=>{CHIP_SYM=s;CHIP_WIN=250;CHIP_PD='d';if(CHIP_ASTRA){CHIP_ASTRA=false;}ensureChipK(s);renderChips();}", s)
                for _ in range(40):
                    await pg.wait_for_timeout(500)
                    if await pg.evaluate("(s)=>!!(CHIPK[s]&&CHIPK[s].bars)", s): break
                await pg.wait_for_timeout(1500)
                off = await pg.evaluate(CAP)
                await pg.click("#chipidx .cidxchipA")   # 真的點按鈕
                for _ in range(40):
                    await pg.wait_for_timeout(500)
                    if await pg.evaluate("()=>CHIP_ASTRA&&!!(CHIPK.SPY&&CHIPK.SPY.bars)&&document.getElementById('cockpit').data.some(t=>t.meta==='astra-flow')"): break
                await pg.wait_for_timeout(1200)
                on = await pg.evaluate(CAP)
                exp = sorted([e["kind"], e["date"]] for e in EXPECTED[s]["events"] if on["win"] and on["win"][0] <= e["date"] <= on["win"][1])
                r["symbols"][s] = {"events_match_node": on["astra"] == exp, "n": len(on["astra"]), "quant_same_on_off": on["q"] == off["q"] and on["qbar"] == off["qbar"],
                                   "astra_bar": on["abar"], "xType": on["xType"]}
                await pg.click("#chipidx .cidxchipA"); await pg.wait_for_timeout(800)   # 關掉,下一檔重來
            r["overflow"] = await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1")
            r["errors"] = errs[:10]
            out[tag] = r
            await ctx.close()
        await b.close()
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    ok = all(v["same"] for v in out["files"].values()) and all(
        out[t]["build"] == BUILD and not out[t]["errors"] and all(x["events_match_node"] and x["quant_same_on_off"] for x in out[t]["symbols"].values())
        for t in ("desktop", "mobile"))
    print("ONLINE OK" if ok else "ONLINE CHECK FAILED")

asyncio.run(main())
