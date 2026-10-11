# t1:Astra資金 v0.1 網站接入驗收(Playwright,本機伺服器;行情照網站從 gist 即時抓)
#   用法:python3 t1_astra_integration_test.py <舊版 index.html> <新版 index.html> <expected_events_node.json> <輸出.json>
#   ① 舊版 vs 新版(Astra 關):15 檔 × 30/100/250 日,駕駛艙「全部 traces」與各狀態列逐項相同
#   ② 新版 Astra 開 vs 關:非 Astra 的 traces 全部相同、CHIP_Q 不變;Astra 記號日期 = Node 離線計算的事件(同一份日K)
#   ③ 週/月/年/全史不畫、切回日K恢復;槓桿 ETF 不適用;縮放後 x 軸仍是 category
#   ④ 情境:SPY 晚到、資料落後(STALE)、截止日之後多一根盤中棒、歷史成交量被更正、程式檔沒載入
import asyncio, json, os, subprocess, sys, time, tempfile, shutil
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD, NEW, EXP, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
SYMS = ["NVDA", "TSM", "MU", "AMD", "PLTR", "AVGO", "META", "SNDK", "SPY", "QQQ", "AAPL", "MSFT", "SLB", "BKNG", "NVDL"]
WINS = [30, 100, 250]
EXPECTED = json.load(open(EXP))

CAP = """()=>{const gd=document.getElementById('cockpit');const D=(gd&&gd.data)||[];
  const clean=t=>{const o={};Object.keys(t).forEach(k=>{if(k!=='uid')o[k]=t[k];});return o;};
  const all=D.map(clean), A=all.filter(t=>t.meta==='astra-flow'), O=all.filter(t=>t.meta!=='astra-flow');
  const strip=id=>{const e=document.getElementById(id);return (e&&e.style.display!=='none')?e.innerText.replace(/\\s+/g,' ').trim():'';};
  let dates=[];try{const rows=cockpitRows(CHIP_SYM)||[];const w=Math.max(30,Math.min(CHIP_WIN,250));dates=rows.slice(-w).map(r=>r.d);}catch(_){}
  const xl=(O[0]&&O[0].x)||[];
  return {sym:CHIP_SYM,win:CHIP_WIN,pd:CHIP_PD,chipQ:CHIP_Q,nAll:all.length,nAstra:A.length,
    other:JSON.stringify(O),
    astra:A.map(t=>({name:t.name,pts:t.x.map((xx,i)=>({x:xx,date:dates[xl.indexOf(xx)]||null,y:t.y[i],text:t.text[i],tip:t.customdata[i]})),color:t.marker&&t.marker.color,textcolor:t.textfont&&t.textfont.color})),
    q:strip('qstrip'),a:strip('astrastrip'),tj:strip('tjstrip'),fc:strip('fcstrip'),pos:strip('posstrip'),dq:strip('dqstrip'),
    xType:gd&&gd._fullLayout&&gd._fullLayout.xaxis?gd._fullLayout.xaxis.type:null,
    yRange:gd&&gd._fullLayout&&gd._fullLayout.yaxis?gd._fullLayout.yaxis.range:null,
    winDates:dates.length?[dates[0],dates[dates.length-1]]:null,
    astraLoaded:!!window.AstraDashboard,astraRev:(typeof ASTRA_UI!=='undefined')?ASTRA_UI.rev:null};}"""
GO = """async ([s,w,pd,on])=>{CHIP_SYM=s;CHIP_WIN=w;CHIP_PD=pd;if(typeof CHIP_ASTRA!=='undefined')CHIP_ASTRA=on;
  try{ensureChipK(s);const u=TK_UL[s];if(u)ensureChipK(u);}catch(_){}
  document.getElementById('cockpit').dataset.sig='';renderChips();return true;}"""
READY = """(s)=>{const u=TK_UL[s]||s;const ok=k=>!!(CHIPK[k]&&CHIPK[k].bars);
  return ok(s)&&ok(u)&&(typeof CHIP_ASTRA==='undefined'||!CHIP_ASTRA||!!(CHIPK.SPY&&CHIPK.SPY.bars)||!!CHIPK.SPY_none);}"""


def start_server(html, port, with_astra):
    www = tempfile.mkdtemp(prefix="astra_t1_")
    shutil.copy(html, os.path.join(www, "index.html"))
    os.symlink(os.path.join(REPO, "data"), os.path.join(www, "data"))
    if with_astra:
        for f in ("astra-flow.js", "astra-dashboard-adapter.js"):
            shutil.copy(os.path.join(REPO, f), os.path.join(www, f))
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=www,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, www


async def open_page(b, port, vw=1440, vh=1000):
    ctx = await b.new_context(viewport={"width": vw, "height": vh}, service_workers="block")
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console." + m.type + ": " + m.text) if m.type == "error" else None)
    await pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded", timeout=180000)
    for _ in range(180):
        if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&Object.keys(chipDaily()).length>=200"):
            break
        await pg.wait_for_timeout(1000)
    await pg.evaluate("()=>{try{ensureQQQK();}catch(_){}}")
    for _ in range(40):
        if await pg.evaluate("()=>!!QQQK"): break
        await pg.wait_for_timeout(500)
    return ctx, pg, errs


async def show(pg, s, w, pd="d", on=False):
    await pg.evaluate(GO, [s, w, pd, on])
    for _ in range(60):
        await pg.wait_for_timeout(400)
        if await pg.evaluate(READY, s): break
    await pg.wait_for_timeout(1200)
    await pg.evaluate("()=>{document.getElementById('cockpit').dataset.sig='';renderChips();}")
    await pg.wait_for_timeout(900)
    return await pg.evaluate(CAP)


def expected_in_window(sym, d0, d1):
    e = EXPECTED.get(sym)
    if not e: return None
    return sorted((x["kind"], x["date"]) for x in e["events"] if d0 <= x["date"] <= d1)


async def main():
    res = {"old": {}, "new_off": {}, "new_on": {}, "checks": [], "scenarios": {}}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        # ---------- 舊版 ----------
        srv, www = start_server(OLD, 8811, False)
        try:
            ctx, pg, errs = await open_page(b, 8811)
            res["old_build"] = await pg.evaluate("()=>BUILD")
            for s in SYMS:
                for w in WINS:
                    res["old"][f"{s}:{w}"] = await show(pg, s, w)
            res["old_errors"] = errs[:10]; await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        # ---------- 新版 ----------
        srv, www = start_server(NEW, 8812, True)
        try:
            ctx, pg, errs = await open_page(b, 8812)
            res["new_build"] = await pg.evaluate("()=>BUILD")
            res["default_astra_off"] = await pg.evaluate("()=>CHIP_ASTRA===false&&document.getElementById('astrastrip').style.display==='none'")
            for s in SYMS:
                for w in WINS:
                    off = await show(pg, s, w, "d", False)
                    on = await show(pg, s, w, "d", True)
                    off2 = await show(pg, s, w, "d", False)
                    res["new_off"][f"{s}:{w}"] = off; res["new_on"][f"{s}:{w}"] = on
                    o = res["old"][f"{s}:{w}"]
                    c = {"key": f"{s}:{w}",
                         "old_vs_new_off_traces_same": o["other"] == off["other"],
                         "old_vs_new_off_strips_same": all(o[k] == off[k] for k in ("q", "tj", "fc", "pos", "dq")),
                         "on_vs_off_nonastra_same": on["other"] == off["other"],
                         "on_vs_off_qstrip_same": on["q"] == off["q"],
                         "chipQ_unchanged": on["chipQ"] == off["chipQ"] == True,
                         "off_again_no_astra": off2["nAstra"] == 0 and off2["a"] == "" and off2["other"] == off["other"],
                         "x_category": on["xType"] == "category",
                         "astra_traces": on["nAstra"], "astra_strip": on["a"]}
                    exp = expected_in_window(s, *(on["winDates"] or ["", ""])) if s != "NVDL" else []
                    got = sorted(({"Astra ENTRY": "ENTRY", "Astra EXIT": "EXIT", "Astra WATCH": "WATCH"}[t["name"]], pt["date"]) for t in on["astra"] for pt in t["pts"])
                    c["events_match_node"] = (exp == got)
                    if exp != got: c["events_diff"] = {"expected_only": sorted(set(exp) - set(got)), "chart_only": sorted(set(got) - set(exp))}
                    c["n_events_on_chart"] = len(got)
                    res["checks"].append(c)
            # ---------- ③ 週/月/年/全史、槓桿 ETF、縮放 ----------
            sc = res["scenarios"]
            for pd in ("w", "m", "y"):
                r = await show(pg, "TSM", 100, pd, True)
                sc["period_" + pd] = {"nAstra": r["nAstra"], "strip": r["a"]}
            r = await show(pg, "TSM", "max", "d", True); sc["max"] = {"nAstra": r["nAstra"], "strip": r["a"]}
            r = await show(pg, "TSM", 250, "d", True); sc["back_to_daily"] = {"nAstra": r["nAstra"], "n_points": sum(len(t["pts"]) for t in r["astra"]), "strip": r["a"]}
            r = await show(pg, "NVDL", 100, "d", True); sc["leveraged_NVDL"] = {"nAstra": r["nAstra"], "strip": r["a"]}
            r = await show(pg, "SQQQ", 100, "d", True); sc["inverse_SQQQ"] = {"nAstra": r["nAstra"], "strip": r["a"]}
            r = await show(pg, "SH", 100, "d", True); sc["inverse_SH_not_in_TK_INV"] = {"nAstra": r["nAstra"], "strip": r["a"]}
            # 債券/現金/商品/加密(資金流分類)→ 範圍外;每一類挑一檔
            cat = await pg.evaluate("""()=>{const D=chipDaily(),ds=Object.keys(D).sort(),m={};
              for(let i=ds.length-1;i>=Math.max(0,ds.length-10);i--)Object.entries(D[ds[i]]||{}).forEach(([s,v])=>{if(v&&v.c&&!m[v.c])m[v.c]=s;});return m;}""")
            sc["out_of_scope"] = {}
            for c in ("國債", "信用債", "現金", "金", "油", "銀", "Crypto"):
                s = cat.get(c)
                if not s: sc["out_of_scope"][c] = "no symbol"; continue
                r = await show(pg, s, 100, "d", True)
                sc["out_of_scope"][c] = {"sym": s, "nAstra": r["nAstra"], "strip": r["a"]}
            for c in ("板塊ETF", "大盤", "半導體"):
                s = cat.get(c)
                if s:
                    r = await show(pg, s, 100, "d", True)
                    sc["out_of_scope"]["in_scope_" + c] = {"sym": s, "nAstra": r["nAstra"], "strip": r["a"]}
            await show(pg, "MU", 250, "d", True)
            sc["zoom"] = await pg.evaluate("""async ()=>{const gd=document.getElementById('cockpit');
              const n=gd.data[0].x.length; await Plotly.relayout(gd,{'xaxis.range':[n-60,n-0.5]});
              await new Promise(r=>setTimeout(r,500));
              const a=gd._fullLayout.xaxis.type; const k=gd.data.filter(t=>t.meta==='astra-flow').length;
              xzApply(gd,()=>gd._HL,n-40,n-0.5); await new Promise(r=>setTimeout(r,500));
              return {afterRelayout:a,afterXzApply:gd._fullLayout.xaxis.type,astraTraces:k};}""")
            # 詳情窗:只有點「ⓘ 詳情」才開
            sc["popover"] = await pg.evaluate("""async ()=>{const h=document.getElementById('astrastrip');const bar=h.querySelector('.sbar');
              const sp=()=>{const p=document.getElementById('stripPop');return !!p&&p.style.display!=='none';};
              bar.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));bar.click();const a=sp();
              h.querySelector('.sbib').click();const b=sp();const txt=b?document.getElementById('stripPop').innerText.replace(/\\s+/g,' ').trim():'';
              h.querySelector('.sbib').click();const c=sp();return {afterHoverOrBarClick:a,afterInfoClick:b,afterSecondClick:c,text:txt};}""")
            # ---------- ④ 資料情境 ----------
            # (a) 截止日之後多一根「盤中」K棒(價量亂填)→ 已收盤事件不變、會重算(rev 變)
            sc["intraday_bar_after_cutoff"] = await pg.evaluate("""async ()=>{CHIP_SYM='TSM';CHIP_WIN=250;CHIP_PD='d';CHIP_ASTRA=true;
              document.getElementById('cockpit').dataset.sig='';renderChips();await new Promise(r=>setTimeout(r,600));   // 先算 TSM 原本的結果當基準
              const ev0=JSON.stringify(ASTRA_UI.res.events), r0=ASTRA_UI.rev, sym0=ASTRA_UI.res.symbol;
              const K=CHIPK.TSM, last=K.bars[K.bars.length-1]; const nd=new Date(last[0]+'T00:00:00Z'); nd.setUTCDate(nd.getUTCDate()+3);
              const fake=[nd.toISOString().slice(0,10),last[4],last[4]*1.5,last[4]*0.5,last[4]*0.6,last[5]*9,0];
              CHIPK.TSM={...K,bars:K.bars.concat([fake])};
              document.getElementById('cockpit').dataset.sig='';renderChips();await new Promise(r=>setTimeout(r,600));
              const out={baselineSym:sym0,recomputed:ASTRA_UI.rev!==r0,eventsSame:JSON.stringify(ASTRA_UI.res.events)===ev0,dataThrough:ASTRA_UI.res.dataThrough,fakeDate:fake[0]};
              CHIPK.TSM=K;document.getElementById('cockpit').dataset.sig='';renderChips();return out;}""")
            # (b) 歷史成交量被更正、最後收盤不變 → inputKey 變、重算
            sc["volume_revision_same_close"] = await pg.evaluate("""async ()=>{const K=CHIPK.TSM, r0=ASTRA_UI.rev;
              const bars=K.bars.map(b=>b.slice()); bars[bars.length-30][5]=bars[bars.length-30][5]*2;
              CHIPK.TSM={...K,bars:bars};document.getElementById('cockpit').dataset.sig='';renderChips();await new Promise(r=>setTimeout(r,600));
              const out={recomputed:ASTRA_UI.rev!==r0};CHIPK.TSM=K;document.getElementById('cockpit').dataset.sig='';renderChips();return out;}""")
            # (c) 資料落後:假裝最近已收盤日比檔案晚一天 → STALE、狀態列寫「資料未更新」
            sc["stale"] = await pg.evaluate("""async ()=>{const orig=window.tjLastDone; const K=CHIPK.TSM; const last=K.bars[K.bars.length-1][0];
              const nd=new Date(last+'T00:00:00Z'); do{nd.setUTCDate(nd.getUTCDate()+1);}while([0,6].includes(nd.getUTCDay()));
              const day=nd.toISOString().slice(0,10); window.tjLastDone=()=>day;
              const saveT=CHIPK.TSM._rt; CHIPK.TSM._rt=Date.now(); const sT=CHIPK.SPY._rt; CHIPK.SPY._rt=Date.now();   // 不讓它真的去重抓
              document.getElementById('cockpit').dataset.sig='';renderChips();await new Promise(r=>setTimeout(r,600));
              const s=document.getElementById('astrastrip').innerText.replace(/\\s+/g,' ').trim(), st=ASTRA_UI.res.status, n=document.getElementById('cockpit').data.filter(t=>t.meta==='astra-flow').length;
              window.tjLastDone=orig; CHIPK.TSM._rt=saveT; CHIPK.SPY._rt=sT; document.getElementById('cockpit').dataset.sig='';renderChips();
              return {status:st,strip:s,astraTracesStillShown:n,fakeLastDone:day};}""")
            # (d) SPY 還沒到 → 不先畫半套;SPY 到了 → 自動算出來
            sc["spy_late"] = await pg.evaluate("""async ()=>{const S=CHIPK.SPY; delete CHIPK.SPY; CHIPK.SPY_r=true;   // 假裝 SPY 請求還在路上
              CHIP_SYM='MU';document.getElementById('cockpit').dataset.sig='';renderChips();await new Promise(r=>setTimeout(r,500));
              const a={status:ASTRA_UI.res.status,strip:document.getElementById('astrastrip').innerText.replace(/\\s+/g,' ').trim(),
                astraTraces:document.getElementById('cockpit').data.filter(t=>t.meta==='astra-flow').length};
              CHIPK.SPY=S; delete CHIPK.SPY_r; renderChips(); await new Promise(r=>setTimeout(r,800));
              const b={status:ASTRA_UI.res.status,astraTraces:document.getElementById('cockpit').data.filter(t=>t.meta==='astra-flow').length};
              return {whileWaiting:a,afterArrive:b};}""")
            # (e) SPY 抓不到 → 不會標 A進,狀態列講清楚
            sc["spy_missing"] = await pg.evaluate("""async ()=>{const S=CHIPK.SPY; delete CHIPK.SPY; CHIPK.SPY_none=true; CHIPK.SPY_t=Date.now();
              CHIP_SYM='TSM';document.getElementById('cockpit').dataset.sig='';renderChips();await new Promise(r=>setTimeout(r,600));
              const ev=ASTRA_UI.res.events||[];
              const out={status:ASTRA_UI.res.status,entries:ev.filter(e=>e.kind==='ENTRY').length,watches:ev.filter(e=>e.kind==='WATCH').length,
                strip:document.getElementById('astrastrip').innerText.replace(/\\s+/g,' ').trim()};
              CHIPK.SPY=S; delete CHIPK.SPY_none; document.getElementById('cockpit').dataset.sig='';renderChips();await new Promise(r=>setTimeout(r,600));return out;}""")
            # (f) 程式檔沒載入 → 顯示錯誤、不畫記號、原圖照常
            sc["script_missing"] = await pg.evaluate("""async ()=>{const A=window.AstraDashboard; window.AstraDashboard=undefined;
              CHIP_SYM='TSM';document.getElementById('cockpit').dataset.sig='';renderChips();await new Promise(r=>setTimeout(r,500));
              const gd=document.getElementById('cockpit');
              const out={strip:document.getElementById('astrastrip').innerText.replace(/\\s+/g,' ').trim(),astraTraces:gd.data.filter(t=>t.meta==='astra-flow').length,chartTraces:gd.data.length};
              window.AstraDashboard=A; document.getElementById('cockpit').dataset.sig='';renderChips();await new Promise(r=>setTimeout(r,500));
              out.afterRestore=gd.data.filter(t=>t.meta==='astra-flow').length;return out;}""")
            # (g) 換股:記號換成新那檔的(不殘留上一檔)
            sc["switch_symbol"] = {}
            for s in ("MU", "NVDA", "TSM"):
                r = await show(pg, s, 250, "d", True)
                exp = expected_in_window(s, *(r["winDates"] or ["", ""]))
                got = sorted(({"Astra ENTRY": "ENTRY", "Astra EXIT": "EXIT", "Astra WATCH": "WATCH"}[t["name"]], pt["date"]) for t in r["astra"] for pt in t["pts"])
                sc["switch_symbol"][s] = exp == got
            res["new_errors"] = errs[:20]
            await ctx.close()
            # ---------- 手機 390 ----------
            ctx, pg, errs = await open_page(b, 8812, 390, 844)
            r = await show(pg, "MU", 100, "d", True)
            res["mobile"] = {"nAstra": r["nAstra"], "strip": r["a"],
                             "overflow": await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1"),
                             "stripOneLine": await pg.evaluate("()=>{const b=document.querySelector('#astrastrip .sbar');return b?b.getBoundingClientRect().height:null;}"),
                             "errors": errs[:10]}
            await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        await b.close()
    # 存檔瘦身:非 Astra traces 的完整 JSON 改存 SHA-256(比對已在上面做完)
    import hashlib
    for k in ("old", "new_off", "new_on"):
        for v in res[k].values():
            v["other_sha256"] = hashlib.sha256(v.pop("other").encode("utf-8")).hexdigest()
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    C = res["checks"]
    keys = ["old_vs_new_off_traces_same", "old_vs_new_off_strips_same", "on_vs_off_nonastra_same", "on_vs_off_qstrip_same",
            "chipQ_unchanged", "off_again_no_astra", "x_category", "events_match_node"]
    print(f"舊版 BUILD {res['old_build']} / 新版 BUILD {res['new_build']} / 新版預設 Astra 關:{res['default_astra_off']}")
    for k in keys:
        bad = [c["key"] for c in C if not c[k]]
        print(f"  {k}: {len(C)-len(bad)}/{len(C)} {'OK' if not bad else 'FAIL ' + str(bad)}")
    print("  Astra 記號數(各檔×視窗):", {c["key"]: c["n_events_on_chart"] for c in C})
    for c in C:
        if not c["events_match_node"]: print("   diff", c["key"], c.get("events_diff"))
    print("情境:", json.dumps(res["scenarios"], ensure_ascii=False)[:4000])
    print("手機:", res["mobile"])
    print("頁面錯誤 舊:", res.get("old_errors"), " 新:", res.get("new_errors"))

asyncio.run(main())
