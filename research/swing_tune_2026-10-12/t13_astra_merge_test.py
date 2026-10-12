# t13:「短線」併進 🧪Astra、📊量化 回到原本(抄底看資金氣候)的網站驗收 — Playwright、本機伺服器、行情照網站從 gist 即時抓
#   用法:python3 t13_astra_merge_test.py <V0 原版 index.html(3dc3cca,短線之前)> <V1 線上 index.html(918d4a3,有短線)> <新版 index.html> <輸出.json>
#   ① Astra 關:📊量化 的字(名稱/日期/文字/說明/位置)= V0;📊量化 以外的圖層 = V1(短線關)
#   ② Astra 開 vs 關:📊量化 的字(名稱/日期/文字/說明/位置)一模一樣;其他非 Astra 圖層一模一樣;版面(y 軸範圍)一樣
#   ③ Astra 記號 = V1 的「短線」記號(名稱對應、日期、字、說明、顏色);位置可以不同(改成找空位)
#   ④ Astra 記號不壓到別的字(同一根K棒同一側,距離 ≥ 0.8 格)
#   ⑤ 第一版 Astra(A候/A進/A出、v0.3 軌道)不畫;「短線」按鈕不見了;Astra 預設關;點按鈕會開關
#   ⑥ 狀態列:Astra 開 → 有一行;關 → 隱藏;週K → 只標日K;SQQQ → 反向 ETF 不適用
#   ⑦ 📊量化 狀態列 / 詳情:新版 vs V0(只允許「接下來」那一行不同)
#   ⑧ JS = Python(swing_ref_v10);MUU 跟著 MU;手機無橫向捲動;頁面錯誤 0
import asyncio, json, os, subprocess, sys, time, tempfile, shutil, math, re
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from swing_ref_v10 import sw_py_v10
V0, V1, NEW, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
SYMS = ["MU", "SNDK", "NVDA", "NBIS", "QQQ", "SPY", "AAPL", "TSLA", "AVGO", "META", "PLTR", "BKNG", "MUU", "SQQQ"]
WINS = [100, 250]

CAP = """()=>{const gd=document.getElementById('cockpit');const D=(gd&&gd.data)||[];
  const clean=t=>{const o={};Object.keys(t).forEach(k=>{if(k!=='uid')o[k]=t[k];});return o;};
  const all=D.map(clean);
  const isQ=t=>/^量化/.test(t.name||''), isW=t=>t.meta==='swing', isLeg=t=>/^Astra (ENTRY|EXIT|WATCH)/.test(t.name||'')||t.yaxis==='y12';
  const pts=t=>{const o=[];(t.x||[]).forEach((x,i)=>{const tx=Array.isArray(t.text)?t.text[i]:t.text;const y=Array.isArray(t.y)?t.y[i]:null;if(x!=null&&y!=null)o.push([t.name,x,tx,Array.isArray(t.customdata)?t.customdata[i]:null,y]);});return o;};
  const nonA=all.filter(t=>!isW(t)&&!isLeg(t)), nonQA=nonA.filter(t=>!isQ(t)&&t.name!=='qpad');
  const Q=all.filter(isQ).flatMap(pts);
  const W=all.filter(t=>isW(t)&&t.name!=='swpad').flatMap(t=>t.x.map((x,i)=>[t.name,x,t.y[i],t.customdata[i],Array.isArray(t.marker.color)?t.marker.color[i]:t.marker.color,Array.isArray(t.text)?t.text[i]:t.text]));
  const txt=all.filter(t=>t.type==='scatter'&&t.mode&&t.mode!=='lines'&&!(t.yaxis&&t.yaxis!=='y')&&!/^(tdTxt|qpad|swpad)/.test(t.name||'')&&t.meta!=='swing').flatMap(pts);
  const cs=all.find(t=>t.type==='candlestick');let o3=null,hi=null,lo=null;
  if(cs){const H=cs.high,L=cs.low;o3=(Math.max(...H)-Math.min(...L))*0.088;hi={};lo={};cs.x.forEach((x,i)=>{hi[x]=H[i];lo[x]=L[i];});}
  let dates=[];try{const rows=cockpitRows(CHIP_SYM)||[];const w=Math.max(30,Math.min(CHIP_WIN,250));dates=rows.slice(-w).map(r=>r.d);}catch(_){}
  const ann=((gd&&gd.layout&&gd.layout.annotations)||[]).map(a=>a.text||'').join(' | ');
  const st=id=>{const h=document.getElementById(id);if(!h)return null;const b=h.firstChild;return {shown:h.style.display!=='none',bar:h.innerText||'',pop:(b&&b._pop)||''};};
  const ya=gd&&gd.layout&&gd.layout.yaxis?JSON.stringify(gd.layout.yaxis.domain):null;
  return {sym:CHIP_SYM,all:JSON.stringify(all),nonA:JSON.stringify(nonA),nonQA:JSON.stringify(nonQA),Q:Q,W:W,leg:all.filter(isLeg).length,txt:txt,o3:o3,hi:hi,lo:lo,dates:dates,ann:ann,
    qs:st('qstrip'),as:st('astrastrip'),ydom:ya,xType:gd&&gd._fullLayout&&gd._fullLayout.xaxis?gd._fullLayout.xaxis.type:null};}"""
GO = """async ([s,w,pd,on])=>{CHIP_SYM=s;CHIP_WIN=w;CHIP_PD=pd;if(typeof CHIP_SW!=='undefined')CHIP_SW=on;CHIP_ASTRA=(typeof CHIP_SW==='undefined')?on:false;
  try{ensureChipK(s);const u=TK_UL[s];if(u)ensureChipK(u);ensureQQQK();}catch(_){}
  document.getElementById('cockpit').dataset.sig='';renderChips();return true;}"""
READY = """(s)=>{const u=TK_UL[s]||s;const ok=k=>!!(CHIPK[k]&&CHIPK[k].bars);return ok(s)&&ok(u)&&!!QQQK;}"""
JSW = """(s)=>{const u=TK_UL[s]||s;const B=(chipBars(u,'d')||[]).filter(b=>b[0]<=tjLastDone());const W=swSeriesJS(B);
  const rep={};Object.keys(W.rep).forEach(i=>{rep[W.D[+i]]=W.rep[i];});
  return {bars:B.map(b=>[b[0],+b[1],+b[2],+b[3],+b[4]]),bot:W.bot.map(i=>W.D[i]),top:W.top.map(i=>W.D[i]),b2:W.b2.map(i=>W.D[i]),rt:W.rt,rep:rep,ul:u};}"""

def start_server(html, port, astra_from=None):
    www = tempfile.mkdtemp(prefix="sw_t13_")
    shutil.copy(html, os.path.join(www, "index.html")); os.symlink(os.path.join(REPO, "data"), os.path.join(www, "data"))
    for f in ("astra-flow.js", "astra-dashboard-adapter.js", "astra-v03-events.json"): shutil.copy(os.path.join(REPO, f), os.path.join(www, f))
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=www, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, www

async def open_page(b, port, vw=1440, vh=1000):
    ctx = await b.new_context(viewport={"width": vw, "height": vh}, service_workers="block")
    pg = await ctx.new_page(); errs = []; reqs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console." + m.type + ": " + m.text) if m.type == "error" else None)
    pg.on("request", lambda r: reqs.append(r.url))
    await pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded", timeout=180000)
    for _ in range(180):
        if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&Object.keys(chipDaily()).length>=200"): break
        await pg.wait_for_timeout(1000)
    await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
    for _ in range(40):
        if await pg.evaluate("()=>!!QQQK"): break
        await pg.wait_for_timeout(500)
    return ctx, pg, errs, reqs

async def show(pg, s, w, pd="d", on=False):
    for attempt in range(3):   # gist 偶發擋 CORS(限流)→ 清掉「無K線」旗標重抓
        if attempt:
            await pg.wait_for_timeout(4000)
            await pg.evaluate("(s)=>{const u=TK_UL[s];[s,u].forEach(k=>{if(k&&!CHIPK[k]){delete CHIPK[k+'_none'];delete CHIPK[k+'_r'];}});}", s)
        await pg.evaluate(GO, [s, w, pd, on]); ok = False
        for _ in range(60):
            await pg.wait_for_timeout(400)
            if await pg.evaluate(READY, s): ok = True; break
        if ok: break
    await pg.wait_for_timeout(1200)
    await pg.evaluate("()=>{document.getElementById('cockpit').dataset.sig='';renderChips();}")
    await pg.wait_for_timeout(900)
    return await pg.evaluate(CAP)

def qkey(Q, ypos=True): return sorted((a, b, c, d, round(y, 9) if ypos else 0) for a, b, c, d, y in Q)
def wkey(W): return sorted((n.replace("短線 ", "Astra "), x, h, c, t) for n, x, y, h, c, t in W)
NEXT_RE = re.compile(r"接下來[^<]*?(?:<br>|</div>|$)")
def strip_next(h):   # 量化 詳情:去掉「接下來」那一句再比
    return re.sub(r"收盤站回 [^<]*?(?=<|$)", "收盤站回 …", h or "")

async def main():
    res = {"V0": {}, "V1": {}, "checks": [], "jspy": {}, "scen": {}}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        for tag, html, port in (("V0", V0, 8871), ("V1", V1, 8872)):
            srv, www = start_server(html, port)
            try:
                ctx, pg, errs, reqs = await open_page(b, port)
                res[tag + "_build"] = await pg.evaluate("()=>BUILD")
                for s in SYMS:
                    for w in WINS:
                        if tag == "V0":
                            r = await show(pg, s, w, "d", False); res["V0"][f"{s}:{w}"] = {"all": r["all"], "Q": r["Q"], "qs": r["qs"]}
                        else:
                            r0 = await show(pg, s, w, "d", False); r = await show(pg, s, w, "d", True); res["V1"][f"{s}:{w}"] = {"W": r["W"], "nonQA": r0["nonQA"]}
                res[tag + "_errors"] = errs[:10]; await ctx.close()
            finally:
                srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        srv, www = start_server(NEW, 8873)
        try:
            ctx, pg, errs, reqs = await open_page(b, 8873)
            res["new_build"] = await pg.evaluate("()=>BUILD")
            res["default"] = await pg.evaluate("()=>({astra:CHIP_ASTRA,legacy:ASTRA_LEGACY,hasSW:typeof CHIP_SW!=='undefined',chipW:!!document.querySelector('.cidxchipW'),"
                                               "chipA:(document.querySelector('.cidxchipA')||{}).textContent||null,pressed:(document.querySelector('.cidxchipA')||{getAttribute:()=>null}).getAttribute('aria-pressed')})")
            for s in SYMS:
                for w in WINS:
                    off = await show(pg, s, w, "d", False); on = await show(pg, s, w, "d", True)
                    v0 = res["V0"][f"{s}:{w}"]; v1 = res["V1"][f"{s}:{w}"]
                    # ④ 不壓字
                    over = 0; minsep = None
                    if on["o3"]:
                        occ = {}
                        for n_, x, t, h, y in on["txt"]: occ.setdefault(x, []).append(y)
                        for n_, x, y, h, c, t in on["W"]:
                            side_hi = y > on["hi"].get(x, y)
                            for yy in occ.get(x, []):
                                if (yy > on["hi"][x]) != side_hi: continue
                                d_ = abs(yy - y) / on["o3"]; minsep = d_ if minsep is None else min(minsep, d_)
                                if d_ < 0.8 - 1e-9: over += 1
                    qs_n, qs_0 = (on["qs"] or {}), (v0["qs"] or {})
                    c = {"key": f"{s}:{w}",
                         "off_quant_same_as_V0": qkey(off["Q"]) == qkey(v0["Q"]),
                         "off_nonquant_same_as_V1": off["nonQA"] == v1["nonQA"],
                         "on_quant_same_as_off": qkey(on["Q"]) == qkey(off["Q"]),
                         "on_nonAstra_same_as_off": on["nonA"] == off["nonA"],
                         "on_ydomain_same": on["ydom"] == off["ydom"],
                         "marks_same_as_V1_shortline": wkey(on["W"]) == wkey(v1["W"]),
                         "no_overlap": over == 0, "min_sep_o3": None if minsep is None else round(minsep, 3),
                         "no_legacy": on["leg"] == 0 and off["leg"] == 0,
                         "astra_strip_on": bool(on["as"] and on["as"]["shown"]), "astra_strip_off_hidden": not (off["as"] and off["as"]["shown"]),
                         "qstrip_bar_same_as_V0": (qs_n.get("bar") == qs_0.get("bar")),
                         "qstrip_pop_same_except_next": strip_next(qs_n.get("pop")) == strip_next(qs_0.get("pop")),
                         "qstrip_pop_identical": qs_n.get("pop") == qs_0.get("pop"),
                         "x_category": on["xType"] == "category", "n_astra": len(on["W"]),
                         "names": sorted({x[0] for x in on["W"]}), "legend": ("=Astra" in on["ann"]) if on["W"] else None,
                         "strip_text": (on["as"] or {}).get("bar", "")[:160]}
                    if not c["qstrip_pop_identical"]:
                        a_, b_ = qs_0.get("pop") or "", qs_n.get("pop") or ""
                        i = 0
                        while i < min(len(a_), len(b_)) and a_[i] == b_[i]: i += 1
                        c["pop_diff"] = {"V0": a_[max(0, i - 60):i + 160], "new": b_[max(0, i - 60):i + 200]}
                    res["checks"].append(c)
                j = await pg.evaluate(JSW, s)
                py = sw_py_v10(j["bars"])
                res["jspy"][s] = {"bars": len(j["bars"]), "same_bot": j["bot"] == py["bot"], "same_top": j["top"] == py["top"], "same_b2": j["b2"] == py["b2"],
                                  "same_rep": j["rep"] == py["rep"], "same_rt": j["rt"] == py["rt"]}
            mu = await show(pg, "MU", 250, "d", True); muu = await show(pg, "MUU", 250, "d", True)
            def xs(r):
                dm = {d[5:]: d for d in r["dates"]}
                return {(n_, dm.get(x, x), t) for n_, x, y, h, c_, t in r["W"]}
            res["scen"]["MUU_follows_MU"] = {"subset": xs(muu) <= xs(mu), "MU": len(mu["W"]), "MUU": len(muu["W"])}
            r = await show(pg, "SQQQ", 250, "d", True); res["scen"]["SQQQ"] = {"n": len(r["W"]), "strip": (r["as"] or {}).get("bar", "")}
            r = await show(pg, "MU", 100, "w", True); res["scen"]["weekly"] = {"n": len(r["W"]), "strip": (r["as"] or {}).get("bar", "")}
            r = await show(pg, "NBIS", 100, "d", True); res["scen"]["NBIS_strip"] = r["as"]
            # 真的點按鈕
            await pg.evaluate("()=>{CHIP_SYM='NVDA';CHIP_WIN=100;CHIP_PD='d';CHIP_ASTRA=false;document.getElementById('cockpit').dataset.sig='';renderChips();}")
            await pg.wait_for_timeout(1500)
            n0 = len((await pg.evaluate(CAP))["W"])
            await pg.click(".cidxchipA"); await pg.wait_for_timeout(1500)
            r1 = await pg.evaluate(CAP); pressed = await pg.evaluate("()=>document.querySelector('.cidxchipA').getAttribute('aria-pressed')")
            await pg.click(".cidxchipA"); await pg.wait_for_timeout(1500)
            n2 = len((await pg.evaluate(CAP))["W"])
            res["scen"]["chip_click"] = {"before": n0, "after_on": len(r1["W"]), "pressed": pressed, "after_off": n2}
            res["legacy_requests"] = [u for u in reqs if "astra-v03-events" in u]
            res["new_errors"] = errs[:20]; await ctx.close()
            ctx, pg, errs, reqs = await open_page(b, 8873, 390, 844)
            r = await show(pg, "MU", 100, "d", True)
            res["mobile"] = {"n_astra": len(r["W"]), "overflow": await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1"), "errors": errs[:10],
                             "strip": (r["as"] or {}).get("bar", "")[:120]}
            await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        await b.close()
    res.pop("V0", None); res.pop("V1", None)
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1, default=str)
    C = res["checks"]
    print(f"V0 {res.get('V0_build')} / V1 {res.get('V1_build')} / 新版 {res['new_build']} / 預設 {res['default']}")
    for k in ("off_quant_same_as_V0", "off_nonquant_same_as_V1", "on_quant_same_as_off", "on_nonAstra_same_as_off", "on_ydomain_same", "marks_same_as_V1_shortline", "no_overlap", "no_legacy",
              "astra_strip_on", "astra_strip_off_hidden", "qstrip_bar_same_as_V0", "qstrip_pop_same_except_next", "qstrip_pop_identical", "x_category"):
        bad = [c["key"] for c in C if not c[k]]
        print(f"  {k}: {len(C)-len(bad)}/{len(C)} {'OK' if not bad else 'FAIL ' + str(bad)}")
    print("  記號數:", {c["key"]: c["n_astra"] for c in C})
    print("  最近距離(格):", {c["key"]: c["min_sep_o3"] for c in C})
    print("  狀態列:", {c["key"]: c["strip_text"] for c in C if c["key"].endswith(":100")})
    print("  詳情差異:", {c["key"]: c.get("pop_diff") for c in C if c.get("pop_diff")})
    print("JS=Python:", {s: (v["same_bot"], v["same_top"], v["same_b2"], v["same_rep"], v["same_rt"]) for s, v in res["jspy"].items()})
    print("情境:", json.dumps(res["scen"], ensure_ascii=False)[:2500])
    print("v0.3 檔請求:", res["legacy_requests"]); print("手機:", res["mobile"])
    print("頁面錯誤 V0:", res.get("V0_errors"), " V1:", res.get("V1_errors"), " 新:", res.get("new_errors"))

asyncio.run(main())
