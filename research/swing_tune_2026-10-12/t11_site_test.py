# t11:v1.0 網站驗收(頂恢復原色、買點加破底計數 ②③…)— Playwright、本機伺服器、行情照網站從 gist 即時抓
#   用法:python3 t11_site_test.py <舊版 index.html(線上 v0.9)> <新版 index.html> <輸出.json>
#   ⑤ 記號日期和舊版相同;頂全部原色、滑過有「減一小部分」;底/回的字 = 底/回 + 破底計數(Python swing_ref_v10)
#   ① 短線關:新版所有圖層 = 舊版(這次只改短線層)
#   ② 短線開:非短線、非量化的圖層和短線關時相同;量化的字(名稱/日期/文字/說明)相同,只可能往外移
#   ③ JS ↔ Python:底/頂/回檔日期、這檔來回成績(swing_ref_v08.sw_py_v08);QQQ CTA(flow_climate.cta_pos,誤差 <1e-9);
#      圖上每個底的強/弱/未分 = Python(CTA ≤0 強、>0 弱;指數不分)
#   ④ MUU = MU(含強弱);SQQQ 不標;週K 不標;手機無橫向捲動;頁面錯誤 0
import asyncio, json, os, subprocess, sys, time, tempfile, shutil, math
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(REPO, "scripts"))
from swing_ref_v10 import sw_py_v10 as sw_py_v08
import flow_climate as FCx
OLD, NEW, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SYMS = ["MU", "SNDK", "NVDA", "NBIS", "QQQ", "SPY", "AAPL", "TSLA", "AVGO", "META", "PLTR", "MUU", "SQQQ"]
WINS = [100, 250]
QGRAY = "#8b8f98"

CAP = """()=>{const gd=document.getElementById('cockpit');const D=(gd&&gd.data)||[];
  const clean=t=>{const o={};Object.keys(t).forEach(k=>{if(k!=='uid')o[k]=t[k];});return o;};
  const all=D.map(clean);
  const isQ=t=>/^量化/.test(t.name||''), isW=t=>t.meta==='swing', isP=t=>t.name==='qpad';
  const other=all.filter(t=>!isQ(t)&&!isW(t)&&!isP(t));
  const qpts=t=>{const o=[];(t.x||[]).forEach((x,i)=>{const tx=Array.isArray(t.text)?t.text[i]:t.text;const y=Array.isArray(t.y)?t.y[i]:null;if(x!=null&&y!=null)o.push([t.name,x,tx,Array.isArray(t.customdata)?t.customdata[i]:null,y]);});return o;};
  const Q=all.filter(isQ).flatMap(qpts);
  const W=all.filter(t=>isW(t)&&/^短線/.test(t.name||'')).flatMap(t=>t.x.map((x,i)=>[t.name,x,t.y[i],t.customdata[i],Array.isArray(t.marker.color)?t.marker.color[i]:t.marker.color,Array.isArray(t.text)?t.text[i]:t.text]));
  let dates=[];try{const rows=cockpitRows(CHIP_SYM)||[];const w=Math.max(30,Math.min(CHIP_WIN,250));dates=rows.slice(-w).map(r=>r.d);}catch(_){}
  const ann=((gd&&gd.layout&&gd.layout.annotations)||[]).map(a=>a.text||'').join(' | ');
  return {sym:CHIP_SYM,all:JSON.stringify(all),other:JSON.stringify(other),Q:Q,W:W,dates:dates,ann:ann,
    xType:gd&&gd._fullLayout&&gd._fullLayout.xaxis?gd._fullLayout.xaxis.type:null,sw:(typeof CHIP_SW!=='undefined')?CHIP_SW:null};}"""
GO = """async ([s,w,pd,sw])=>{CHIP_SYM=s;CHIP_WIN=w;CHIP_PD=pd;if(typeof CHIP_SW!=='undefined')CHIP_SW=sw;
  try{ensureChipK(s);const u=TK_UL[s];if(u)ensureChipK(u);ensureQQQK();}catch(_){}
  document.getElementById('cockpit').dataset.sig='';renderChips();return true;}"""
READY = """(s)=>{const u=TK_UL[s]||s;const ok=k=>!!(CHIPK[k]&&CHIPK[k].bars);return ok(s)&&ok(u)&&!!QQQK;}"""
JSW = """(s)=>{const u=TK_UL[s]||s;const B=(chipBars(u,'d')||[]).filter(b=>b[0]<=tjLastDone());const W=swSeriesJS(B);
  const q=qqqCloses();const ld=tjLastDone();const ds=Object.keys(q).filter(d=>d<=ld).sort();const qc=ds.map(d=>+q[d]);const cta=ctaPosJS(qc);
  const rep={};Object.keys(W.rep).forEach(i=>{rep[W.D[+i]]=W.rep[i];});
  return {bars:B.map(b=>[b[0],+b[1],+b[2],+b[3],+b[4]]),bot:W.bot.map(i=>W.D[i]),top:W.top.map(i=>W.D[i]),b2:W.b2.map(i=>W.D[i]),rt:W.rt,rep:rep,
    qd:ds,qc:qc,cta:cta,ul:u};}"""

def start_server(html, port):
    www = tempfile.mkdtemp(prefix="sw_t7_")
    shutil.copy(html, os.path.join(www, "index.html")); os.symlink(os.path.join(REPO, "data"), os.path.join(www, "data"))
    for f in ("astra-flow.js", "astra-dashboard-adapter.js", "astra-v03-events.json"): shutil.copy(os.path.join(REPO, f), os.path.join(www, f))
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=www, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, www

async def open_page(b, port, vw=1440, vh=1000):
    ctx = await b.new_context(viewport={"width": vw, "height": vh}, service_workers="block")
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console." + m.type + ": " + m.text) if m.type == "error" else None)
    await pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded", timeout=180000)
    for _ in range(180):
        if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&Object.keys(chipDaily()).length>=200"): break
        await pg.wait_for_timeout(1000)
    await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
    for _ in range(40):
        if await pg.evaluate("()=>!!QQQK"): break
        await pg.wait_for_timeout(500)
    return ctx, pg, errs

async def show(pg, s, w, pd="d", sw=True):
    for attempt in range(3):   # gist 偶發擋 CORS(限流)→ 清掉「無K線」旗標重抓
        if attempt:
            await pg.wait_for_timeout(4000)
            await pg.evaluate("(s)=>{const u=TK_UL[s];[s,u].forEach(k=>{if(k&&!CHIPK[k]){delete CHIPK[k+'_none'];delete CHIPK[k+'_r'];}});}", s)
        await pg.evaluate(GO, [s, w, pd, sw]); ok = False
        for _ in range(60):
            await pg.wait_for_timeout(400)
            if await pg.evaluate(READY, s): ok = True; break
        if ok: break
    await pg.wait_for_timeout(1200)
    await pg.evaluate("()=>{document.getElementById('cockpit').dataset.sig='';renderChips();}")
    await pg.wait_for_timeout(900)
    return await pg.evaluate(CAP)

def qkey(Q): return sorted((a, b, c, d) for a, b, c, d, _ in Q)

def grade_of(name, hover, color):
    if name != "短線 底": return None
    if "<b>強</b>" in hover: return "強"
    if "弱</b>" in hover: return "弱" if color == QGRAY else "弱(顏色錯)"
    if "還沒到" in hover: return "未分"
    return "不分(指數)"

async def main():
    res = {"old": {}, "checks": [], "jspy": {}, "scen": {}}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        srv, www = start_server(OLD, 8857)
        try:
            ctx, pg, errs = await open_page(b, 8857)
            res["old_build"] = await pg.evaluate("()=>BUILD")
            for s in SYMS:
                for w in WINS:
                    r = await show(pg, s, w, "d", False); res["old"][f"{s}:{w}:off"] = r["all"]
                    r = await show(pg, s, w, "d", True); res["old"][f"{s}:{w}:on"] = {"other": r["other"], "Q": r["Q"], "W": sorted([x[0], x[1]] for x in r["W"])}
            res["old_errors"] = errs[:10]; await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        srv, www = start_server(NEW, 8858)
        try:
            ctx, pg, errs = await open_page(b, 8858)
            res["new_build"] = await pg.evaluate("()=>BUILD"); res["default_sw_on"] = await pg.evaluate("()=>CHIP_SW===true")
            for s in SYMS:
                for w in WINS:
                    off = await show(pg, s, w, "d", False); on = await show(pg, s, w, "d", True)
                    o_on = res["old"][f"{s}:{w}:on"]
                    names = sorted({x[0] for x in on["W"]})
                    c = {"key": f"{s}:{w}",
                         "off_all_same_as_old": off["all"] == res["old"][f"{s}:{w}:off"],
                         "on_other_same_as_off": on["other"] == off["other"],
                         "on_other_same_as_old_on": on["other"] == o_on["other"],
                         "on_quant_text_same": qkey(on["Q"]) == qkey(off["Q"]) == qkey(o_on["Q"]),
                         "x_category": on["xType"] == "category", "n_swing": len(on["W"]), "names": names,
                         "marks_same_as_old": sorted([x[0], x[1]] for x in on["W"]) == o_on["W"],
                         "legend": ("△回檔" in on["ann"]) if on["W"] else None}
                    # 圖上每個底的強弱 vs Python
                    j = await pg.evaluate(JSW, s)
                    pyc = FCx.cta_pos(j["qc"]); cmap = {d: v for d, v in zip(j["qd"], pyc) if not (v is None or (isinstance(v, float) and math.isnan(v)))}
                    xl = {d[5:]: d for d in on["dates"]}
                    isidx = j["ul"] in ("SPY", "QQQ")
                    gr_ok = True; gr_n = {"強": 0, "弱": 0, "未分": 0, "不分(指數)": 0}
                    for name, x, y, hov, col, txt in on["W"]:
                        g = grade_of(name, hov, col)
                        if g is None: continue
                        d = xl.get(x); cv = cmap.get(d)
                        exp = "不分(指數)" if isidx else ("未分" if cv is None else ("強" if cv <= 0 else "弱"))
                        gr_n[g] = gr_n.get(g, 0) + 1
                        if g != exp: gr_ok = False
                    c["grade_match_py"] = gr_ok; c["grades"] = gr_n
                    tg_ok = True; tg = {"灰": 0, "原": 0}; rp_ok = True; rp = {}
                    CIRC = "②③④⑤⑥⑦⑧⑨⑩"
                    for name, x, y, hov, col, txt in on["W"]:
                        d = xl.get(x)
                        if name == "短線 頂":
                            gray = (col == QGRAY); tg["灰" if gray else "原"] += 1
                            if gray or "減一小部分" not in hov: tg_ok = False
                        else:
                            k = j["rep"].get(d, 1); base = "底" if name == "短線 底" else "回"
                            want = base + (CIRC[k - 2] if 2 <= k <= 10 else (f"({k})" if k > 10 else ""))
                            rp[k] = rp.get(k, 0) + 1
                            if txt != want or (("破底中的第 " + str(k) + " 個") in hov) != (k >= 2): rp_ok = False
                    c["top_gray_match_py"] = tg_ok and tg["灰"] == 0; c["tops"] = tg; c["rep_match_py"] = rp_ok; c["reps"] = rp
                    res["checks"].append(c)
                j = await pg.evaluate(JSW, s)
                py = sw_py_v08(j["bars"]); pyc = FCx.cta_pos(j["qc"])
                dif = max((abs(a - b_) for a, b_ in zip(j["cta"], pyc) if a is not None and not (isinstance(b_, float) and math.isnan(b_))), default=0)
                nn = sum(1 for a, b_ in zip(j["cta"], pyc) if (a is None) != (b_ is None or (isinstance(b_, float) and math.isnan(b_))))
                res["jspy"][s] = {"bars": len(j["bars"]), "same_bot": j["bot"] == py["bot"], "same_top": j["top"] == py["top"], "same_b2": j["b2"] == py["b2"], "same_tup": j["rep"] == py["rep"],
                                  "same_rt": j["rt"] == py["rt"], "cta_maxdiff": dif, "cta_null_mismatch": nn,
                                  "n_bot": len(py["bot"]), "n_top": len(py["top"]), "n_b2": len(py["b2"]), "rt": py["rt"]}
            mu = await show(pg, "MU", 250, "d", True); muu = await show(pg, "MUU", 250, "d", True)
            def sw_set(r):
                xl = {d[5:]: d for d in r["dates"]}
                return sorted((n_, xl[x], grade_of(n_, h, c), tx_) for n_, x, y, h, c, tx_ in r["W"] if x in xl)
            a, bb = sw_set(mu), sw_set(muu)
            res["scen"]["MUU_follows_MU"] = {"MU": len(a), "MUU": len(bb), "MUU_subset_of_MU": set(bb) <= set(a)}
            r = await show(pg, "SQQQ", 250, "d", True); res["scen"]["inverse_SQQQ_no_swing"] = len(r["W"]) == 0
            r = await show(pg, "MU", 100, "w", True); res["scen"]["weekly_no_swing"] = len(r["W"]) == 0
            r = await show(pg, "MU", 250, "d", True)
            samp = {}
            for n_, x, y, h, c, tx_ in r["W"]:
                k = n_ + ":" + str(grade_of(n_, h, c)) + ":" + tx_
                if k not in samp: samp[k] = h[:400]
            res["scen"]["hover_samples"] = samp
            r = await show(pg, "QQQ", 250, "d", True)
            res["scen"]["hover_samples_QQQ"] = {n_: h[:400] for n_, x, y, h, c, tx_ in r["W"][:1]}
            res["new_errors"] = errs[:20]; await ctx.close()
            ctx, pg, errs = await open_page(b, 8858, 390, 844)
            r = await show(pg, "MU", 100, "d", True)
            res["mobile"] = {"n_swing": len(r["W"]), "overflow": await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1"), "errors": errs[:10],
                             "legend": "△回檔" in r["ann"]}
            await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        await b.close()
    res.pop("old", None)
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1, default=str)
    C = res["checks"]
    print(f"舊版 BUILD {res['old_build']} / 新版 BUILD {res['new_build']} / 短線預設開 {res['default_sw_on']}")
    for k in ("off_all_same_as_old", "on_other_same_as_off", "on_other_same_as_old_on", "on_quant_text_same", "x_category", "grade_match_py", "marks_same_as_old", "top_gray_match_py", "rep_match_py"):
        bad = [c["key"] for c in C if not c[k]]
        print(f"  {k}: {len(C)-len(bad)}/{len(C)} {'OK' if not bad else 'FAIL ' + str(bad)}")
    print("  記號數 / 種類:", {c["key"]: (c["n_swing"], c["names"]) for c in C})
    print("  強弱:", {c["key"]: c["grades"] for c in C})
    print("  頂 灰/原:", {c["key"]: c["tops"] for c in C})
    print("  破底計數:", {c["key"]: c["reps"] for c in C})
    print("JS↔Python:", {s: (v["same_bot"], v["same_top"], v["same_b2"], v["same_rt"], v["same_tup"], f"cta差{v['cta_maxdiff']:.1e}", v["cta_null_mismatch"], v["n_bot"], v["n_top"], v["n_b2"]) for s, v in res["jspy"].items()})
    print("情境:", json.dumps(res["scen"], ensure_ascii=False)[:3000])
    print("手機:", res["mobile"]); print("頁面錯誤 舊:", res.get("old_errors"), " 新:", res.get("new_errors"))

asyncio.run(main())
