# t10:v0.9 部署後線上複驗(GitHub Pages)— 同 t8,另查:上升趨勢中的頂是灰色 = Python 旗標、標題有「灰=較弱」
#   用法:python3 t8_online_check.py <預期 BUILD> <輸出.json>
#   ① 線上 index.html 與 repo 逐位元相同(Astra 三個檔也比對)
#   ② 桌機 1440 / 手機 390:QQQ、SPY、MU、NVDA、AAPL、MUU 的 底/頂/回檔 日期 = Python(swing_ref_v08);個股的底強弱 = Python(QQQ CTA)
#      真的點「短線」按鈕 → 記號消失、量化字不變 → 再點回來;SQQQ/週K 不標;頁面錯誤 0;手機無橫向捲動;標題有「△回檔」
import asyncio, hashlib, json, os, sys, math, urllib.request
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(REPO, "scripts"))
from swing_ref_v09 import sw_py_v09 as sw_py_v08
import flow_climate as FCx
BUILD, OUT = sys.argv[1], sys.argv[2]
SITE = "https://groupuie.github.io/market-flow-dashboard/"
QGRAY = "#8b8f98"; NAME = {"短線 底": "bot", "短線 頂": "top", "短線 回檔": "b2"}

def fetch(path):
    req = urllib.request.Request(SITE + path + ("&" if "?" in path else "?") + "nocache=" + str(os.getpid()), headers={"Cache-Control": "no-cache"})
    return urllib.request.urlopen(req, timeout=60).read()

CAP = """()=>{const gd=document.getElementById('cockpit');const D=(gd&&gd.data)||[];
  const W=D.filter(t=>t.meta==='swing'&&/^短線/.test(t.name||'')),Q=D.filter(t=>/^量化/.test(t.name||''));
  const rows=cockpitRows(CHIP_SYM)||[];const w=Math.max(30,Math.min(CHIP_WIN,250));const dates=rows.slice(-w).map(r=>r.d);const xl=D[0].x;
  return {W:W.flatMap(t=>t.x.map((x,i)=>[t.name,dates[xl.indexOf(x)],t.customdata[i],Array.isArray(t.marker.color)?t.marker.color[i]:t.marker.color])),
    q:JSON.stringify(Q.map(t=>({n:t.name,x:t.x,text:t.text,c:t.customdata}))),ann:((gd.layout&&gd.layout.annotations)||[]).map(a=>a.text||'').join(' | '),
    sw:CHIP_SW,xType:gd._fullLayout.xaxis.type,dates:dates};}"""
GO = """(a)=>{const [s,w,pd]=a;CHIP_SYM=s;CHIP_WIN=w;CHIP_PD=pd;try{ensureChipK(s);const u=TK_UL[s];if(u)ensureChipK(u);ensureQQQK();}catch(_){}renderChips();}"""
READY = """(s)=>{const u=TK_UL[s]||s;const ok=k=>!!(CHIPK[k]&&CHIPK[k].bars);return ok(s)&&ok(u)&&!!QQQK;}"""
JSB = """(s)=>{const u=TK_UL[s]||s;const q=qqqCloses();const ld=tjLastDone();const ds=Object.keys(q).filter(d=>d<=ld).sort();
  return {u:u,bars:(chipBars(u,'d')||[]).filter(b=>b[0]<=ld).map(b=>[b[0],+b[1],+b[2],+b[3],+b[4]]),qd:ds,qc:ds.map(d=>+q[d])};}"""

def grade(name, hov, col):
    if name != "短線 底": return None
    if "<b>強</b>" in hov: return "強"
    if "弱</b>" in hov: return "弱" if col == QGRAY else "弱(顏色錯)"
    if "還沒到" in hov: return "未分"
    return "不分"

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
        out["files"][f] = {"same": hashlib.sha256(fetch(f)).hexdigest() == hashlib.sha256(open(os.path.join(REPO, f), "rb").read()).hexdigest()}
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
            for s in ("QQQ", "SPY", "MU", "NVDA", "AAPL", "MUU"):
                on = await show(pg, s, 250)
                j = await pg.evaluate(JSB, s); py = sw_py_v08(j["bars"]); ds = set(on["dates"])
                exp = sorted([[k, d] for k, key in NAME.items() for d in py[key] if d in ds])
                got = sorted([[n_, d] for n_, d, h, c in on["W"]])
                cta = FCx.cta_pos(j["qc"]); cm = {d: v for d, v in zip(j["qd"], cta) if not (isinstance(v, float) and math.isnan(v))}
                isidx = j["u"] in ("SPY", "QQQ"); gok = True; gn = {}
                for n_, d, h, c in on["W"]:
                    g = grade(n_, h, c)
                    if g is None: continue
                    e = "不分" if isidx else ("未分" if cm.get(d) is None else ("強" if cm[d] <= 0 else "弱"))
                    gn[g] = gn.get(g, 0) + 1; gok &= (g == e)
                await pg.click("#chipidx .cidxchipW"); await pg.wait_for_timeout(1500)
                off = await pg.evaluate(CAP)
                await pg.click("#chipidx .cidxchipW"); await pg.wait_for_timeout(1500)
                back = await pg.evaluate(CAP)
                qt = lambda c: [(t["n"], t["x"], t["text"], t["c"]) for t in json.loads(c["q"])]
                tok = True; tn = {"灰": 0, "原": 0}
                for n_, d, h, c in on["W"]:
                    if n_ != "短線 頂": continue
                    gray = (c == QGRAY); tn["灰" if gray else "原"] += 1
                    if gray != bool(py["tup"].get(d)) or gray != ("上升趨勢中" in h): tok = False
                r["symbols"][s] = {"n": len(on["W"]), "match_py": got == exp, "grade_ok": gok, "grades": gn, "legend": "△回檔" in on["ann"] and "灰=較弱" in on["ann"],
                                   "top_gray_ok": tok, "tops": tn,
                                   "off_none": not off["W"] and off["sw"] is False, "quant_text_same": qt(on) == qt(off),
                                   "back_same": sorted(x[:2] for x in back["W"]) == sorted(x[:2] for x in on["W"]), "xType": on["xType"]}
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
        all(x["n"] > 0 and x["match_py"] and x["grade_ok"] and x["top_gray_ok"] and x["legend"] and x["off_none"] and x["quant_text_same"] and x["back_same"] and x["xType"] == "category"
            for x in out[t]["symbols"].values())
        for t in ("desktop", "mobile"))
    print("ONLINE OK" if ok else "ONLINE CHECK FAILED")

asyncio.run(main())
