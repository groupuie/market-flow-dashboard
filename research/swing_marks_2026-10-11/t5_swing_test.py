# t5:📍短線 底/頂 + 📊量化 抄底(不看資金)網站驗收(Playwright;本機伺服器;行情照網站從 gist 即時抓)
#   用法:python3 t5_swing_test.py <舊版 index.html> <新版 index.html> <輸出.json>
#   ① 新版 短線關:除了 量化抄底(本來就要改)以外,所有圖層和舊版相同;量化其他字(名稱/日期/文字/說明)相同
#   ② 新版 短線開 vs 關:非 短線、非 量化 的圖層相同;量化的字只可能往外移一層(名稱/日期/文字/說明相同)
#   ③ JS ↔ Python:網頁用的那份日K,底/頂日期與這檔來回成績 = Python 逐行移植(同 s1 定義)
#   ④ 槓桿 ETF(MUU)看正股 MU;反向 ETF(SQQQ)不標;週K 不標;頁面錯誤 0;手機無橫向捲動
import asyncio, json, os, subprocess, sys, time, tempfile, shutil, math
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD, NEW, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SYMS = ["MU", "SNDK", "NVDA", "QQQ", "SPY", "AAPL", "TSLA", "AVGO", "INTC", "META", "MUU", "SQQQ"]
WINS = [100, 250]

CAP = """()=>{const gd=document.getElementById('cockpit');const D=(gd&&gd.data)||[];
  const clean=t=>{const o={};Object.keys(t).forEach(k=>{if(k!=='uid')o[k]=t[k];});return o;};
  const all=D.map(clean);
  const isQ=t=>/^量化/.test(t.name||''), isW=t=>t.meta==='swing', isP=t=>t.name==='qpad';   // qpad = 量化 撐軸的隱形點(短線開時字往外排 → 跟著往外)
  const other=all.filter(t=>!isQ(t)&&!isW(t)&&!isP(t));
  const qpts=t=>{const o=[];(t.x||[]).forEach((x,i)=>{const tx=Array.isArray(t.text)?t.text[i]:t.text;const y=Array.isArray(t.y)?t.y[i]:null;if(x!=null&&y!=null)o.push([t.name,x,tx,Array.isArray(t.customdata)?t.customdata[i]:null,y]);});return o;};
  const Q=all.filter(isQ).flatMap(qpts), W=all.filter(t=>isW(t)&&/^短線/.test(t.name||'')).flatMap(t=>t.x.map((x,i)=>[t.name,x,t.y[i],t.customdata[i]]));
  const qpad=all.filter(isP).map(t=>t.y[0]);
  const strip=id=>{const e=document.getElementById(id);return (e&&e.style.display!=='none')?e.innerText.replace(/\\s+/g,' ').trim():'';};
  let dates=[];try{const rows=cockpitRows(CHIP_SYM)||[];const w=Math.max(30,Math.min(CHIP_WIN,250));dates=rows.slice(-w).map(r=>r.d);}catch(_){}
  return {sym:CHIP_SYM,win:CHIP_WIN,other:JSON.stringify(other),Q:Q,W:W,qpad:qpad,q:strip('qstrip'),a:strip('astrastrip'),
    xType:gd&&gd._fullLayout&&gd._fullLayout.xaxis?gd._fullLayout.xaxis.type:null,dates:dates,sw:(typeof CHIP_SW!=='undefined')?CHIP_SW:null};}"""
GO = """async ([s,w,pd,sw])=>{CHIP_SYM=s;CHIP_WIN=w;CHIP_PD=pd;if(typeof CHIP_SW!=='undefined')CHIP_SW=sw;
  try{ensureChipK(s);const u=TK_UL[s];if(u)ensureChipK(u);}catch(_){}
  document.getElementById('cockpit').dataset.sig='';renderChips();return true;}"""
READY = """(s)=>{const u=TK_UL[s]||s;const ok=k=>!!(CHIPK[k]&&CHIPK[k].bars);return ok(s)&&ok(u)&&!!QQQK;}"""
JSW = """(s)=>{const u=TK_UL[s]||s;const B=(chipBars(u,'d')||[]).filter(b=>b[0]<=tjLastDone());const W=swSeriesJS(B);
  return {bars:B.map(b=>[b[0],+b[1],+b[2],+b[3],+b[4]]),bot:W.bot.map(i=>W.D[i]),top:W.top.map(i=>W.D[i]),rt:W.rt};}"""

def sw_py(B):   # s1 定義的逐行移植(單一檔、日K list)
    n = len(B); D = [b[0] for b in B]; O = [b[1] for b in B]; H = [b[2] for b in B]; L = [b[3] for b in B]; C = [b[4] for b in B]
    r2 = [None] * n
    if n >= 4:
        g = [max(C[i] - C[i - 1], 0) for i in range(1, n)]; l = [max(C[i - 1] - C[i], 0) for i in range(1, n)]
        ag = (g[0] + g[1]) / 2; al = (l[0] + l[1]) / 2; r2[2] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
        for i in range(3, n):
            ag = (ag + g[i - 1]) / 2; al = (al + l[i - 1]) / 2; r2[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    lo = [None] * n; up = [None] * n
    for i in range(19, n):
        w = C[i - 19:i + 1]; m = sum(w) / 20; sd = math.sqrt(sum((v - m) ** 2 for v in w) / 20); lo[i] = m - 2 * sd; up[i] = m + 2 * sd
    tb = [0] * n; ts = [0] * n
    for i in range(4, n):
        tb[i] = tb[i - 1] + 1 if C[i] < C[i - 4] else 0; ts[i] = ts[i - 1] + 1 if C[i] > C[i - 4] else 0
    os_ = lambda i: (r2[i] is not None and r2[i] <= 10) or (lo[i] is not None and C[i] <= lo[i]) or tb[i] == 9
    ob_ = lambda i: (r2[i] is not None and r2[i] >= 90) or (up[i] is not None and C[i] >= up[i]) or ts[i] == 9
    bot, top = [], []; lb = lt = -10**9
    for i in range(2, n):
        if (os_(i) or os_(i - 1) or os_(i - 2)) and C[i] > H[i - 1] and i - lb > 5: lb = i; bot.append(i)
        if (ob_(i) or ob_(i - 1) or ob_(i - 2)) and C[i] < L[i - 1] and i - lt > 5: lt = i; top.append(i)
    rt = {"bn": 0, "bw": 0, "tn": 0, "tw": 0}
    def nxt(A, i):
        for k in A:
            if k > i: return k if k - i <= 40 else None
        return None
    for i in bot:
        k = nxt(top, i)
        if k is None or k + 1 >= n or i + 1 >= n: continue
        rt["bn"] += 1; rt["bw"] += O[k + 1] > O[i + 1]
    for i in top:
        k = nxt(bot, i)
        if k is None or k + 1 >= n or i + 1 >= n: continue
        rt["tn"] += 1; rt["tw"] += O[k + 1] < O[i + 1]
    return {"bot": [D[i] for i in bot], "top": [D[i] for i in top], "rt": rt}

def start_server(html, port):
    www = tempfile.mkdtemp(prefix="sw_t5_")
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
    for attempt in range(3):   # gist 偶發擋 CORS(限流)→ 清掉「無K線」旗標重抓(等同使用者重新整理)
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

def qkey(Q, drop=()):   # 量化的字:名稱/位置/文字/說明(不含 y)
    return sorted((a, b, c, d) for a, b, c, d, _ in Q if a not in drop)

async def main():
    res = {"old": {}, "checks": [], "jspy": {}, "scen": {}}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        srv, www = start_server(OLD, 8851)
        try:
            ctx, pg, errs = await open_page(b, 8851)
            res["old_build"] = await pg.evaluate("()=>BUILD")
            for s in SYMS:
                for w in WINS: res["old"][f"{s}:{w}"] = await show(pg, s, w, "d", True)
            res["old_errors"] = errs[:10]; await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        srv, www = start_server(NEW, 8852)
        try:
            ctx, pg, errs = await open_page(b, 8852)
            res["new_build"] = await pg.evaluate("()=>BUILD"); res["default_sw_on"] = await pg.evaluate("()=>CHIP_SW===true")
            for s in SYMS:
                for w in WINS:
                    o = res["old"][f"{s}:{w}"]
                    off = await show(pg, s, w, "d", False); on = await show(pg, s, w, "d", True)
                    newQ_bars = {x for a, x, *_ in off["Q"] if a == "量化抄底"}
                    xl = [d[5:] for d in off["dates"]]; cd_idx = sorted(xl.index(x) for x in newQ_bars if x in xl)
                    qa, qb = set(qkey(o["Q"], ("量化抄底",))), set(qkey(off["Q"], ("量化抄底",)))
                    def explained(p):   # 舊有、新沒有:只允許「買」落在新抄底當天~3 根內(原本就有的規則:3 根內已有抄底就不再標買)
                        if p[0] != "量化買" or p[1] not in xl: return False
                        i = xl.index(p[1]); return any(0 <= i - j <= 3 for j in cd_idx)
                    c = {"key": f"{s}:{w}",
                         "off_other_same_as_old": off["other"] == o["other"] and not off["W"],
                         "off_quant_same_except_chaodi": not (qb - qa) and all(explained(p) for p in qa - qb),
                         "buy_hidden_by_new_chaodi": sorted(p[1] for p in qa - qb),
                         "qpad_outward": (not on["qpad"] and not off["qpad"]) or (bool(on["qpad"]) and bool(off["qpad"]) and on["qpad"][0] >= off["qpad"][0] - 1e-9),
                         "off_quant_y_changed_only_on_chaodi_bars": all((x in newQ_bars) for (a, x, t, h, y) in off["Q"] if a != "量化抄底"
                                                                       and (a, x, t, h, y) not in set(map(tuple, o["Q"]))),
                         "old_chaodi": sum(1 for a, *_ in o["Q"] if a == "量化抄底"), "new_chaodi": sum(1 for a, *_ in off["Q"] if a == "量化抄底"),
                         "on_other_same_as_off": on["other"] == off["other"],
                         "on_quant_same_text": qkey(on["Q"]) == qkey(off["Q"]),
                         "x_category": on["xType"] == "category", "n_swing": len(on["W"]),
                         "qstrip_same": on["q"] == off["q"]}
                    res["checks"].append(c)
                # JS ↔ Python(網頁那份日K)
                j = await pg.evaluate(JSW, s)
                py = sw_py(j["bars"])
                res["jspy"][s] = {"bars": len(j["bars"]), "same_bot": j["bot"] == py["bot"], "same_top": j["top"] == py["top"], "same_rt": j["rt"] == py["rt"],
                                  "n_bot": len(py["bot"]), "n_top": len(py["top"]), "rt": py["rt"]}
            # 槓桿 ETF 看正股:MUU 的 短線 日期 = MU 的(在 MUU 視窗內)
            mu = await show(pg, "MU", 250, "d", True); muu = await show(pg, "MUU", 250, "d", True)
            def sw_dates(r):
                xl = [r["dates"][i][5:] for i in range(len(r["dates"]))]
                return sorted((n_, r["dates"][xl.index(x)]) for n_, x, *_ in r["W"] if x in xl)
            a, bb = sw_dates(mu), sw_dates(muu)
            res["scen"]["MUU_follows_MU"] = {"MU": len(a), "MUU": len(bb), "MUU_subset_of_MU": set(bb) <= set(a)}
            r = await show(pg, "SQQQ", 250, "d", True); res["scen"]["inverse_SQQQ_no_swing"] = len(r["W"]) == 0
            r = await show(pg, "MU", 100, "w", True); res["scen"]["weekly_no_swing"] = len(r["W"]) == 0
            r = await show(pg, "MU", 250, "d", True)
            res["scen"]["hover_sample"] = r["W"][0][3][:300] if r["W"] else None
            res["scen"]["toggle_off"] = len((await show(pg, "MU", 250, "d", False))["W"]) == 0
            res["new_errors"] = errs[:20]; await ctx.close()
            ctx, pg, errs = await open_page(b, 8852, 390, 844)
            r = await show(pg, "MU", 100, "d", True)
            res["mobile"] = {"n_swing": len(r["W"]), "overflow": await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1"), "errors": errs[:10]}
            await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        await b.close()
    for v in res["old"].values(): v.pop("other", None)
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1, default=str)
    C = res["checks"]
    print(f"舊版 BUILD {res['old_build']} / 新版 BUILD {res['new_build']} / 短線預設開 {res['default_sw_on']}")
    for k in ("off_other_same_as_old", "off_quant_same_except_chaodi", "off_quant_y_changed_only_on_chaodi_bars", "on_other_same_as_off", "qpad_outward", "on_quant_same_text", "x_category"):
        bad = [c["key"] for c in C if not c[k]]
        print(f"  {k}: {len(C)-len(bad)}/{len(C)} {'OK' if not bad else 'FAIL ' + str(bad)}")
    print("  抄底 舊→新:", {c["key"]: (c["old_chaodi"], c["new_chaodi"]) for c in C})
    print("  新抄底 3 根內不再標的「買」:", {c["key"]: c["buy_hidden_by_new_chaodi"] for c in C if c["buy_hidden_by_new_chaodi"]})
    print("  短線記號數:", {c["key"]: c["n_swing"] for c in C})
    print("  量化狀態列(短線開關)相同:", all(c["qstrip_same"] for c in C))
    print("JS↔Python:", {s: (v["same_bot"], v["same_top"], v["same_rt"], v["n_bot"], v["n_top"]) for s, v in res["jspy"].items()})
    print("情境:", json.dumps(res["scen"], ensure_ascii=False)[:1500])
    print("手機:", res["mobile"]); print("頁面錯誤 舊:", res.get("old_errors"), " 新:", res.get("new_errors"))

asyncio.run(main())
