# t3:Astra 按鈕更新(v0.3「只標日期」研究軌道 + 共識文字)本機驗收(Playwright,本機伺服器;行情照網站從 gist 即時抓)
#   用法:python3 t3_astra_lane_test.py <舊版 index.html> <新版 index.html> <輸出.json>
#   ① 舊版 vs 新版(Astra 關):駕駛艙全部 traces、版面(layout)、各狀態列逐項相同
#   ② 新版 Astra 開 vs 關:非 Astra 的 traces 全部相同;📊量化 開關(CHIP_Q)不變;v0.1 記號 = 舊版 Astra 開的 v0.1 記號
#   ③ 軌道:只在 v0.3 研究的 30 檔畫;點的日期與動作 = 事件檔(視窗內);全部 y = 0.5、掛在 y12(沒有價格座標);
#      K 線區底邊只上移 0.016(桌機)/ 0.014(手機);視窗內沒事件 → 只留標籤;不在名單 → 版面跟 Astra 關一樣
#   ④ 週/月 K、全史不畫;關掉 Astra 恢復原版面;事件檔抓不到 → 狀態列寫明、不畫、不報錯;詳情窗只有點 ⓘ 才開
import asyncio, json, os, subprocess, sys, time, tempfile, shutil, hashlib
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OLD, NEW, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SYMS = ["MU", "INTC", "NVDA", "AVGO", "AAPL", "SNDK", "SPY", "NVDL"]
WINS = [30, 100, 250]
EV = json.load(open(os.path.join(REPO, "astra-v03-events.json")))

CAP = """()=>{const gd=document.getElementById('cockpit');const D=(gd&&gd.data)||[];
  const clean=t=>{const o={};Object.keys(t).forEach(k=>{if(k!=='uid')o[k]=t[k];});return o;};
  const all=D.map(clean), V1=all.filter(t=>t.meta==='astra-flow'), A3=all.filter(t=>t.meta==='astra-v03'),
        O=all.filter(t=>t.meta!=='astra-flow'&&t.meta!=='astra-v03');
  const strip=id=>{const e=document.getElementById(id);return (e&&e.style.display!=='none')?e.innerText.replace(/\\s+/g,' ').trim():'';};
  let dates=[];try{const rows=cockpitRows(CHIP_SYM)||[];const w=Math.max(30,Math.min(CHIP_WIN,250));dates=rows.slice(-w).map(r=>r.d);}catch(_){}
  const xl=(O[0]&&O[0].x)||[];
  const L=(gd&&gd.layout)||{};
  const lay={};Object.keys(L).forEach(k=>{if(k!=='annotations'&&k!=='datarevision'&&k!=='autosize')lay[k]=L[k];});   // autosize:Plotly responsive 重排時自己加上的旗標(看事件時機,和內容無關)
  const anns=(L.annotations||[]).map(a=>a.text);
  return {sym:CHIP_SYM,win:CHIP_WIN,pd:CHIP_PD,chipQ:CHIP_Q,nAll:all.length,nV1:V1.length,nA3:A3.length,
    other:JSON.stringify(O), v1:JSON.stringify(V1), layoutNoAnn:JSON.stringify(lay), anns:JSON.stringify(anns),
    a3ann:anns.filter(t=>String(t).indexOf('Astra v0.3')>=0),
    lane:A3.map(t=>({name:t.name,yaxis:t.yaxis,mode:t.mode,ys:Array.from(new Set((t.y||[]).filter(v=>v!=null))),
      pts:(t.x||[]).map((xx,i)=>xx==null?null:{x:xx,date:dates[xl.indexOf(xx)]||null}).filter(p=>p),
      tips:t.customdata||null,cliponaxis:t.cliponaxis})),
    yDom:L.yaxis&&L.yaxis.domain, y7Dom:L.yaxis7&&L.yaxis7.domain, y12:L.yaxis12||null,
    q:strip('qstrip'),a:strip('astrastrip'),tj:strip('tjstrip'),fc:strip('fcstrip'),pos:strip('posstrip'),dq:strip('dqstrip'),
    xType:gd&&gd._fullLayout&&gd._fullLayout.xaxis?gd._fullLayout.xaxis.type:null,
    winDates:dates.length?[dates[0],dates[dates.length-1]]:null,
    a3st:(typeof ASTRA3!=='undefined')?ASTRA3.st:null};}"""
GO = """async ([s,w,pd,on])=>{CHIP_SYM=s;CHIP_WIN=w;CHIP_PD=pd;if(typeof CHIP_ASTRA!=='undefined')CHIP_ASTRA=on;
  try{ensureChipK(s);const u=TK_UL[s];if(u)ensureChipK(u);}catch(_){}
  document.getElementById('cockpit').dataset.sig='';renderChips();return true;}"""
READY = """(s)=>{const u=TK_UL[s]||s;const ok=k=>!!(CHIPK[k]&&CHIPK[k].bars);
  return ok(s)&&ok(u)&&(typeof CHIP_ASTRA==='undefined'||!CHIP_ASTRA||((!!(CHIPK.SPY&&CHIPK.SPY.bars)||!!CHIPK.SPY_none)
    &&(typeof ASTRA3==='undefined'||ASTRA3.st==='ok'||ASTRA3.st==='err')));}"""


def start_server(html, port, events=True):
    www = tempfile.mkdtemp(prefix="astra_t3_")
    shutil.copy(html, os.path.join(www, "index.html"))
    os.symlink(os.path.join(REPO, "data"), os.path.join(www, "data"))
    for f in ("astra-flow.js", "astra-dashboard-adapter.js") + (("astra-v03-events.json",) if events else ()):
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


def expected_lane(sym, d0, d1, win_dates_set):
    if sym not in EV["symbols"]: return None
    out = []
    for c in EV["campaigns"].get(sym, []):
        e, z = c["f"][0][1], c["f"][-1][1]
        if z < d0 or e > d1: continue
        for k, d, _ in c["f"]:
            if d0 <= d <= d1 and d in win_dates_set: out.append((k, d))
    return sorted(out)


def lane_got(r):
    got = []
    for t in r["lane"]:
        if t["mode"] != "markers": continue
        k = t["name"].replace("Astra3 ", "")
        got += [(k, p["date"]) for p in t["pts"]]
    return sorted(got)


async def main():
    res = {"old": {}, "new": {}, "checks": [], "scenarios": {}}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        # ---------- 舊版(現在線上那版)----------
        srv, www = start_server(OLD, 8821, events=False)
        try:
            ctx, pg, errs = await open_page(b, 8821)
            res["old_build"] = await pg.evaluate("()=>BUILD")
            for s in SYMS:
                for w in WINS:
                    res["old"][f"{s}:{w}:off"] = await show(pg, s, w, "d", False)
                    res["old"][f"{s}:{w}:on"] = await show(pg, s, w, "d", True)
            res["old_errors"] = errs[:10]; await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        # ---------- 新版 ----------
        srv, www = start_server(NEW, 8822, events=True)
        try:
            ctx, pg, errs = await open_page(b, 8822)
            res["new_build"] = await pg.evaluate("()=>BUILD")
            res["default"] = await pg.evaluate("()=>({astraOff:CHIP_ASTRA===false,stripHidden:document.getElementById('astrastrip').style.display==='none',a3:ASTRA3.st})")
            for s in SYMS:
                for w in WINS:
                    off = await show(pg, s, w, "d", False)
                    on = await show(pg, s, w, "d", True)
                    off2 = await show(pg, s, w, "d", False)
                    o_off, o_on = res["old"][f"{s}:{w}:off"], res["old"][f"{s}:{w}:on"]
                    wd = set()
                    if on["winDates"]:
                        rows = await pg.evaluate("([s,w])=>{const r=cockpitRows(s)||[];return r.slice(-Math.max(30,Math.min(w,250))).map(x=>x.d);}", [s, w])
                        wd = set(rows)
                    exp = expected_lane(s, *(on["winDates"] or ["", ""]), wd)
                    got = lane_got(on)
                    inU = s in EV["symbols"]
                    c = {"key": f"{s}:{w}",
                         "old_vs_new_off_traces_same": o_off["other"] == off["other"] and off["nV1"] == 0 and off["nA3"] == 0,
                         "old_vs_new_off_layout_same": o_off["layoutNoAnn"] == off["layoutNoAnn"] and o_off["anns"] == off["anns"],
                         "old_vs_new_off_strips_same": all(o_off[k] == off[k] for k in ("q", "tj", "fc", "pos", "dq", "a")),
                         "on_vs_off_nonastra_same": on["other"] == off["other"],
                         "on_vs_off_qstrip_same": on["q"] == off["q"],
                         "chipQ_unchanged": on["chipQ"] == off["chipQ"] == True,
                         "v1_same_as_old_on": on["v1"] == o_on["v1"],
                         "off_again_restored": off2["nV1"] == 0 and off2["nA3"] == 0 and off2["a"] == "" and off2["other"] == off["other"]
                                               and off2["layoutNoAnn"] == off["layoutNoAnn"] and off2["anns"] == off["anns"],
                         "x_category": on["xType"] == "category",
                         "lane_events_match": (exp == got) if inU else (got == [] and on["nA3"] == 0),
                         "lane_no_price": all(t["yaxis"] == "y12" and t["ys"] == [0.5] and t["cliponaxis"] is False for t in on["lane"]),
                         "layout_shift": (abs(on["yDom"][0] - off["yDom"][0] - 0.016) < 1e-9 and on["y12"] and on["y12"]["domain"] == [on["y7Dom"][1], on["yDom"][0]]
                                          and on["y12"]["range"] == [0, 1] and len(on["a3ann"]) == 1) if inU else
                                         (on["yDom"] == off["yDom"] and on["y12"] is None and on["a3ann"] == []),
                         "tips_ok": all(all('只標日期' in x for x in (t["tips"] or [])) for t in on["lane"] if t["mode"] == "markers"),
                         "n_lane_events": len(got), "a3ann": on["a3ann"], "strip_on": on["a"]}
                    if inU and exp != got: c["lane_diff"] = {"expected_only": sorted(set(exp) - set(got)), "chart_only": sorted(set(got) - set(exp))}
                    res["checks"].append(c)
            sc = res["scenarios"]
            # 週 / 月 K、全史:不畫軌道
            for pd in ("w", "m"):
                r = await show(pg, "MU", 100, pd, True); sc["period_" + pd] = {"nA3": r["nA3"], "y12": r["y12"], "strip": r["a"]}
            r = await show(pg, "MU", "max", "d", True); sc["max"] = {"nA3": r["nA3"], "strip": r["a"]}
            r = await show(pg, "MU", 250, "d", True); sc["back_to_daily"] = {"nA3": r["nA3"], "n": len(lane_got(r))}
            # 縮放後 x 軸仍是 category、軌道還在
            sc["zoom"] = await pg.evaluate("""async ()=>{const gd=document.getElementById('cockpit');
              const n=gd.data[0].x.length; await Plotly.relayout(gd,{'xaxis.range':[n-60,n-0.5]});
              await new Promise(r=>setTimeout(r,500));
              return {xType:gd._fullLayout.xaxis.type,a3:gd.data.filter(t=>t.meta==='astra-v03').length,y12:!!gd._fullLayout.yaxis12};}""")
            # 詳情窗:只有點「ⓘ 詳情」才開;內容先講結論
            async def popover():
                return await pg.evaluate("""async ()=>{const h=document.getElementById('astrastrip');const bar=h.querySelector('.sbar');
                  const sp=()=>{const p=document.getElementById('stripPop');return !!p&&p.style.display!=='none';};
                  bar.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));bar.click();const a=sp();
                  h.querySelector('.sbib').click();const b=sp();const txt=b?document.getElementById('stripPop').innerText.replace(/\\s+/g,' ').trim():'';
                  h.querySelector('.sbib').click();const c=sp();return {afterHoverOrBarClick:a,afterInfoClick:b,afterSecondClick:c,text:txt};}""")
            sc["popover"] = {}
            for s in ("MU", "AAPL", "SNDK"):
                await show(pg, s, 250, "d", True); sc["popover"][s] = await popover()
            # 滑過軌道的點:看得到說明(用 Plotly 的 hover 事件模擬)
            await show(pg, "MU", 250, "d", True)
            pos = await pg.evaluate("""()=>{const gd=document.getElementById('cockpit');
              const i=gd.data.findIndex(t=>t.meta==='astra-v03'&&t.mode==='markers'); if(i<0)return null;
              const fl=gd._fullLayout, xa=fl.xaxis, ya=fl.yaxis12, t=gd.data[i]; const k=t.x.length-1;
              const xi=gd.data[0].x.indexOf(t.x[k]); const r=gd.getBoundingClientRect();
              return {x:r.left+xa._offset+xa.c2p(xi), y:r.top+ya._offset+ya.c2p(0.5), name:t.name};}""")
            if pos:
                await pg.mouse.move(pos["x"], pos["y"]); await pg.wait_for_timeout(500)
                sc["hover"] = {"trace": pos["name"], "text": await pg.evaluate("()=>{const h=document.querySelector('#cockpit .hoverlayer');return h?h.textContent.replace(/\\s+/g,' ').trim().slice(0,240):'';}")}
                await pg.mouse.move(5, 5)
            else:
                sc["hover"] = None
            res["new_errors"] = errs[:20]
            await ctx.close()
            # ---------- 手機 390 ----------
            ctx, pg, errs = await open_page(b, 8822, 390, 844)
            r = await show(pg, "MU", 100, "d", True); r_off = await show(pg, "MU", 100, "d", False)
            res["mobile"] = {"nA3": r["nA3"], "lane_n": len(lane_got(r)), "strip": r["a"], "a3ann": r["a3ann"],
                             "shift": (r["yDom"][0] - r_off["yDom"][0]) if r["yDom"] and r_off["yDom"] else None,
                             "overflow": await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1"),
                             "errors": errs[:10]}
            await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        # ---------- 事件檔抓不到(404)----------
        srv, www = start_server(NEW, 8823, events=False)
        try:
            ctx, pg, errs = await open_page(b, 8823)
            r = await show(pg, "MU", 250, "d", True); r0 = await show(pg, "MU", 250, "d", False)
            res["scenarios"]["events_404"] = {"a3st": r["a3st"], "nA3": r["nA3"], "nV1": r["nV1"], "strip": r["a"],
                                              "layout_same_as_off": r["layoutNoAnn"] == r0["layoutNoAnn"],
                                              "errors_other_than_404": [e for e in errs if "404" not in e and "Failed to load resource" not in e][:5]}
            await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        await b.close()
    for k in ("old", "new"):
        for v in res[k].values():
            for f in ("other", "v1", "layoutNoAnn", "anns"):
                if f in v: v[f + "_sha256"] = hashlib.sha256(v.pop(f).encode("utf-8")).hexdigest()
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    C = res["checks"]
    keys = ["old_vs_new_off_traces_same", "old_vs_new_off_layout_same", "old_vs_new_off_strips_same", "on_vs_off_nonastra_same",
            "on_vs_off_qstrip_same", "chipQ_unchanged", "v1_same_as_old_on", "off_again_restored", "x_category",
            "lane_events_match", "lane_no_price", "layout_shift", "tips_ok"]
    print(f"舊版 BUILD {res['old_build']} / 新版 BUILD {res['new_build']} / 預設:{res['default']}")
    for k in keys:
        bad = [c["key"] for c in C if not c[k]]
        print(f"  {k}: {len(C)-len(bad)}/{len(C)} {'OK' if not bad else 'FAIL ' + str(bad)}")
    print("  軌道點數:", {c["key"]: c["n_lane_events"] for c in C})
    for c in C:
        if c.get("lane_diff"): print("   diff", c["key"], c["lane_diff"])
    print("  狀態列(開):", {c["key"]: c["strip_on"] for c in C if c["key"].endswith(":250")})
    print("情境:", json.dumps(res["scenarios"], ensure_ascii=False)[:5000])
    print("手機:", res["mobile"])
    print("頁面錯誤 舊:", res.get("old_errors"), " 新:", res.get("new_errors"))

asyncio.run(main())
