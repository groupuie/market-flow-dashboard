# t6:部署後線上複驗(GitHub Pages)— 📍短線 底/頂 + 📊量化 抄底(不看資金)
#   用法:python3 t6_online_check.py <預期 BUILD> <輸出.json>
#   ① 線上 index.html 與 repo 逐位元相同(Astra 三個檔也比對,確認沒被動到)
#   ② 桌機 1440 / 手機 390:短線預設開;QQQ、SPY、MU、NVDA、MUU(看正股 MU)有 短線 記號,
#      底/頂日期 = Python 逐行移植(同 t5 sw_py);真的點「短線」按鈕 → 記號消失、📊量化 記號文字不變 → 再點回來
#   ③ SQQQ(反向)不標;週K 不標;頁面錯誤 0;手機無橫向捲動
import asyncio, hashlib, json, os, sys, urllib.request
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
BUILD, OUT = sys.argv[1], sys.argv[2]
SITE = "https://groupuie.github.io/market-flow-dashboard/"
sys.path.insert(0, HERE)
from swing_ref import sw_py

def fetch(path):
    req = urllib.request.Request(SITE + path + ("&" if "?" in path else "?") + "nocache=" + str(os.getpid()), headers={"Cache-Control": "no-cache"})
    return urllib.request.urlopen(req, timeout=60).read()

CAP = """()=>{const gd=document.getElementById('cockpit');const D=(gd&&gd.data)||[];
  const W=D.filter(t=>t.meta==='swing'&&/^短線/.test(t.name||'')),Q=D.filter(t=>/^量化/.test(t.name||''));
  const rows=cockpitRows(CHIP_SYM)||[];const w=Math.max(30,Math.min(CHIP_WIN,250));const dates=rows.slice(-w).map(r=>r.d);const xl=D[0].x;
  return {W:W.flatMap(t=>t.x.map(x=>[t.name,dates[xl.indexOf(x)]])).sort(),
    q:JSON.stringify(Q.map(t=>({n:t.name,x:t.x,text:t.text,c:t.customdata}))),
    sw:CHIP_SW,xType:gd._fullLayout.xaxis.type,dates:dates};}"""
GO = """(a)=>{const [s,w,pd]=a;CHIP_SYM=s;CHIP_WIN=w;CHIP_PD=pd;try{ensureChipK(s);const u=TK_UL[s];if(u)ensureChipK(u);}catch(_){}renderChips();}"""
READY = """(s)=>{const u=TK_UL[s]||s;const ok=k=>!!(CHIPK[k]&&CHIPK[k].bars);return ok(s)&&ok(u)&&!!QQQK;}"""
JSB = """(s)=>{const u=TK_UL[s]||s;return (chipBars(u,'d')||[]).filter(b=>b[0]<=tjLastDone()).map(b=>[b[0],+b[1],+b[2],+b[3],+b[4]]);}"""

async def show(pg, s, w, pd="d"):
    await pg.evaluate(GO, [s, w, pd])
    for _ in range(60):
        await pg.wait_for_timeout(500)
        if await pg.evaluate(READY, s): break
    await pg.wait_for_timeout(1500)
    await pg.evaluate("()=>{document.getElementById('cockpit').dataset.sig='';renderChips();}")
    await pg.wait_for_timeout(1000)
    return await pg.evaluate(CAP)

async def main():
    out = {"files": {}}
    for f in ("index.html", "astra-v03-events.json", "astra-flow.js", "astra-dashboard-adapter.js"):
        live = hashlib.sha256(fetch(f)).hexdigest(); local = hashlib.sha256(open(os.path.join(REPO, f), "rb").read()).hexdigest()
        out["files"][f] = {"same": live == local}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        for tag, vw, vh in (("desktop", 1440, 1000), ("mobile", 390, 844)):
            ctx = await b.new_context(viewport={"width": vw, "height": vh}, service_workers="block")
            pg = await ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append("console.error: " + m.text) if m.type == "error" else None)
            await pg.goto(SITE + "?nocache=" + tag, wait_until="domcontentloaded", timeout=180000)
            for _ in range(180):
                if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&!!document.querySelector('#chipidx .cidxchipW')"): break
                await pg.wait_for_timeout(1000)
            await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
            r = {"build": await pg.evaluate("()=>BUILD"), "default_on": await pg.evaluate("()=>CHIP_SW===true"), "symbols": {}}
            for s in ("QQQ", "SPY", "MU", "NVDA", "MUU"):
                on = await show(pg, s, 250)
                bars = await pg.evaluate(JSB, s); py = sw_py(bars); ds = set(on["dates"])
                exp = sorted([["短線 底", d] for d in py["bot"] if d in ds] + [["短線 頂", d] for d in py["top"] if d in ds])
                await pg.click("#chipidx .cidxchipW"); await pg.wait_for_timeout(1500)   # 真的點按鈕:關
                off = await pg.evaluate(CAP)
                await pg.click("#chipidx .cidxchipW"); await pg.wait_for_timeout(1500)   # 再點:開
                back = await pg.evaluate(CAP)
                qt = lambda c: [(t["n"], t["x"], t["text"], t["c"]) for t in json.loads(c["q"])]   # 名稱/日期/文字/說明(不含 y:短線開時量化往外移一層)
                r["symbols"][s] = {"n": len(on["W"]), "match_py": on["W"] == exp, "off_none": not off["W"] and off["sw"] is False,
                                   "quant_text_same": qt(on) == qt(off), "back_same": back["W"] == on["W"], "xType": on["xType"]}
            r["SQQQ_none"] = len((await show(pg, "SQQQ", 250))["W"]) == 0
            r["weekly_none"] = len((await show(pg, "MU", 100, "w"))["W"]) == 0
            r["overflow"] = await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1")
            r["errors"] = errs[:10]; out[tag] = r
            await ctx.close()
        await b.close()
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    ok = all(v["same"] for v in out["files"].values()) and all(
        out[t]["build"] == BUILD and out[t]["default_on"] and not out[t]["errors"] and not out[t]["overflow"] and out[t]["SQQQ_none"] and out[t]["weekly_none"] and
        all(x["n"] > 0 and x["match_py"] and x["off_none"] and x["quant_text_same"] and x["back_same"] and x["xType"] == "category" for x in out[t]["symbols"].values())
        for t in ("desktop", "mobile"))
    print("ONLINE OK" if ok else "ONLINE CHECK FAILED")

asyncio.run(main())
