# t15:網站 v1.5(🧪 Astra 擴大範圍 + 底/回「強」+ 200 日線 + Astra 訊號分頁)本機測試
#   V0 = 改之前的 index.html、V1 = 改之後;資料:gist(追蹤股)+ astra-data 分支(線上)
#   1. 追蹤股(MU NVDA QQQ NBIS BKNG MUU)× 100/250 根:
#      Astra 關:V1 整張圖(所有 trace + shapes + annotations)= V0 → 量化與其他圖層一點都沒變
#      Astra 開:量化 = Astra 關;Astra 記號(日期、種類)= Python sw_series;「強」= regime.json 那天分數 ≥ 2;200 日線虛線 = regime.json 跌破/站回的日子
#   2. 不在追蹤清單、在擴大範圍名單的股票:畫得出駕駛艙、日K = astra-data 檔、Astra 記號 = Python、資料條有「加入追蹤」
#   3. 不在任何名單的代號:照舊顯示「加入追蹤」動作區
#   4. 🧪 Astra 訊號分頁:列 = today.json、篩選、點代號打開那檔並自動開 Astra
#   5. 桌機 + 手機:頁面錯誤 0、沒有橫向捲動
#   用法:python3 t15_site_test.py <V0.html> <V1.html> <輸出.json>
import asyncio, json, os, sys, time, shutil, urllib.request
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "swing_tune_2026-10-12")); sys.path.insert(0, os.path.join(REPO, "scripts"))
import t13_astra_merge_test as T
import astra_data as AD
V0 = V1 = OUT = None   # 參數在 __main__ 才讀(t16 會 import 這支)
AX = "https://raw.githubusercontent.com/groupuie/market-flow-dashboard/astra-data/"
SYMS = ["MU", "NVDA", "QQQ", "NBIS", "BKNG", "MUU"]; WINS = [100, 250]
REG = json.loads(urllib.request.urlopen(urllib.request.Request(AX + "regime.json", headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
TODAY = json.loads(urllib.request.urlopen(urllib.request.Request(AX + "today.json", headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
RI = {d: i for i, d in enumerate(REG["d"])}

LAY = """()=>{const gd=document.getElementById('cockpit');const L=(gd&&gd.layout)||{};
  return {shapes:JSON.stringify(L.shapes||[]),ann:JSON.stringify((L.annotations||[]).map(a=>({t:a.text,x:a.x,y:a.y,h:a.hovertext||null}))),
    d200:(L.shapes||[]).filter(s=>s.type==='line'&&s.xref==='x'&&s.line&&s.line.dash==='dot').map(s=>s.x0),
    d200a:(L.annotations||[]).filter(a=>a.xref==='x'&&/200/.test(a.text||'')).map(a=>[a.x,a.text]),
    band:(L.shapes||[]).filter(s=>s.type==='rect'&&s.xref==='x').map(s=>[s.x0,s.x1])};}"""

def py_marks(bars, dates):
    W = AD.sw_series([[b[0], b[1], b[2], b[3], b[4], 0] for b in bars]); ds = set(dates); out = set()
    for kind, nm, arr in (("底", "Astra 底", W["bot"]), ("回", "Astra 回檔", W["b2"]), ("頂", "Astra 頂", W["top"])):
        for j in arr:
            d = W["D"][j]
            if d not in ds: continue
            i = RI.get(d); last = REG["d"][-1]
            if i is None and d > last: i = len(REG["d"]) - 1
            st = (i is not None and REG["sc"][i] >= 2) if kind != "頂" else False
            out.add((nm, d, st))
    return out

def py_d200(sym, dates):
    key = "s" if sym == "SPY" else "q"; cr = []
    for i2, d in enumerate(dates):
        i = RI.get(d)
        if i is None or i < 1: continue
        a, b = REG[key][i - 1], REG[key][i]
        if a is not None and b is not None and a != b: cr.append(i2)
    return cr

async def show_v1(pg, s, w, on):
    C = await T.show(pg, s, w, "d", on); L = await pg.evaluate(LAY); C["lay"] = L; return C

async def main():
    res = {"tracked": [], "fallback": [], "notin": None, "list": None, "mobile": None}
    async with async_playwright() as p:
        br = await p.chromium.launch(args=["--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        # ---- V0:Astra 關的整張圖
        srv, www = T.start_server(V0, 8893)
        v0 = {}
        try:
            ctx, pg, errs0, _ = await T.open_page(br, 8893)
            for s in SYMS:
                for w in WINS:
                    C = await T.show(pg, s, w, "d", False); L = await pg.evaluate(LAY); v0[f"{s}:{w}"] = (C, L)
            await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        # ---- V1
        srv, www = T.start_server(V1, 8894)
        try:
            ctx, pg, errs, reqs = await T.open_page(br, 8894)
            bad = []; pg.on("response", lambda r: bad.append((r.status, r.url)) if r.status >= 400 else None)
            for _ in range(60):
                if await pg.evaluate("()=>!!AXU"): break
                await pg.wait_for_timeout(500)
            for s in SYMS:
                for w in WINS:
                    off = await show_v1(pg, s, w, False)
                    a0, l0 = v0[f"{s}:{w}"]
                    on = await show_v1(pg, s, w, True)
                    for _ in range(30):   # regime.json 到了才算數
                        if await pg.evaluate("()=>!!AXR"): break
                        await pg.wait_for_timeout(500)
                    on = await show_v1(pg, s, w, True)
                    j = await pg.evaluate(T.JSW, s)
                    want = py_marks(j["bars"], on["dates"])
                    dm = {d[5:]: d for d in on["dates"]}
                    got = {(n_, dm.get(x), "強" in (t or "")) for n_, x, y, h, c, t in on["W"]}
                    under = j["ul"] or s
                    cr = py_d200(under, on["dates"])
                    res["tracked"].append({"key": f"{s}:{w}",
                        "off_traces_same_as_V0": off["all"] == a0["all"], "off_layout_same_as_V0": off["lay"]["shapes"] == l0["shapes"] and off["lay"]["ann"] == l0["ann"],
                        "quant_on_same_as_off": T.qkey(on["Q"]) == T.qkey(off["Q"]),
                        "nonastra_on_same_as_off": on["nonA"] == off["nonA"],
                        "astra_eq_python": got == want, "n_marks": len(got), "n_strong": sum(1 for g in got if g[2]),
                        "d200_eq_python": sorted(on["lay"]["d200"]) == cr and sorted(a[0] for a in on["lay"]["d200a"]) == cr, "n_d200": len(cr),
                        "strip": (on["as"] or {}).get("bar", "")[:160]})
            # ---- 擴大範圍(不在追蹤清單)
            cand = await pg.evaluate("()=>{const t=new Set(chipSyms());return AXU.k.filter(s=>!t.has(s));}")
            pick = [s for s in ["BRK-B", "LLY", "JPM", "HUBS", "GTLB", "MMM", "ZTS", "XOM"] if s in cand][:6]
            for s in pick:
                C = await show_v1(pg, s, 250, True)
                info = await pg.evaluate("(s)=>{const K=CHIPK[s]||{};const dq=document.getElementById('dqstrip');return {ax:K.ax||0,src:K.src||'',n:(K.bars||[]).length,plot:!!document.querySelector('#cockpit .plot-container'),dq:dq?dq.innerText:'',btn:!!document.getElementById('chipFreeBtn')};}", s)
                kf = json.loads(urllib.request.urlopen(urllib.request.Request(AX + "k/" + s + ".json", headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())["bars"]
                j = await pg.evaluate(T.JSW, s)
                same_bars = [b[:5] for b in j["bars"]] == [[b[0], b[1], b[2], b[3], b[4]] for b in kf if b[0] <= j["bars"][-1][0]]
                want = py_marks(j["bars"], C["dates"]); dm = {d[5:]: d for d in C["dates"]}
                got = {(n_, dm.get(x), "強" in (t or "")) for n_, x, y, h, c, t in C["W"]}
                res["fallback"].append({"sym": s, **info, "bars_eq_astra_file": same_bars, "astra_eq_python": got == want, "n_marks": len(got), "q_marks": len(C["Q"])})
            # 用 . 的寫法(BRK.B)也找得到
            await pg.evaluate("()=>{CHIP_SYM='BRK.B';CHIP_WIN=100;CHIP_ASTRA=false;document.getElementById('cockpit').dataset.sig='';renderChips();}")
            await pg.wait_for_timeout(5000)
            res["dot_alias"] = await pg.evaluate("()=>({ax:(CHIPK['BRK.B']||{}).ax||0,plot:!!document.querySelector('#cockpit .plot-container')})")
            # ---- 不在任何名單
            await pg.evaluate("()=>{CHIP_SYM='QQQQX';document.getElementById('cockpit').dataset.sig='';renderChips();}")
            await pg.wait_for_timeout(2500)
            res["notin"] = await pg.evaluate("()=>({action:!!document.getElementById('chipFreeBtn')&&/還不在追蹤宇宙/.test(document.getElementById('cockpit').innerText)})")
            # ---- Astra 訊號分頁
            await pg.evaluate("()=>{CHIP_SYM='NVDA';CHIP_ASTRA=false;document.getElementById('cockpit').dataset.sig='';renderChips();}")
            await pg.wait_for_timeout(2500)
            await pg.click('.wsxTab[data-wt="astra"]')
            for _ in range(40):
                if await pg.evaluate("()=>!!document.querySelector('#axpanel table')"): break
                await pg.wait_for_timeout(500)
            day = TODAY["days"][0]; want_all = sorted((r["s"], r["k"]) for r in TODAY["rows"] if r["d"] == day)
            got_all = await pg.evaluate("()=>Array.from(document.querySelectorAll('#axpanel tr')).slice(1).map(tr=>[tr.querySelector('[data-axsym]').dataset.axsym,tr.children[1].innerText.trim().slice(1,2)])")
            await pg.click('#axpanel [data-axg="hw"]'); await pg.wait_for_timeout(400)
            hw = await pg.evaluate("()=>Array.from(document.querySelectorAll('#axpanel [data-axsym]')).map(e=>e.dataset.axsym)")
            hw_want = sorted(r["s"] for r in TODAY["rows"] if r["d"] == day and await_ai(r["s"]) == "hw")
            first = hw[0] if hw else None
            if first:
                await pg.click(f'#axpanel [data-axsym="{first}"]'); await pg.wait_for_timeout(4000)
            clicked = await pg.evaluate("()=>({sym:CHIP_SYM,astra:CHIP_ASTRA,plot:!!document.querySelector('#cockpit .plot-container'),strip:(document.getElementById('astrastrip')||{}).innerText||''})")
            res["list"] = {"day": day, "rows_eq_today": sorted(map(tuple, got_all)) == want_all, "n": len(got_all), "hw_eq": sorted(hw) == hw_want, "n_hw": len(hw),
                           "clicked": clicked, "clicked_ok": bool(first) and clicked["sym"] == first and clicked["astra"] and clicked["plot"]}
            res["overflow_desktop"] = await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1")
            res["errors"] = [e for e in errs if "Failed to load resource" not in e][:10]
            res["http_bad"] = [b for b in bad if not (b[0] == 404 and "gist.githubusercontent.com" in b[1] and "/kline_" in b[1])][:10]   # 不在追蹤清單 → gist 沒有 kline 檔(本來就會 404,再改抓 astra-data)
            await ctx.close()
            # ---- 手機
            ctx, pg, errs2, _ = await T.open_page(br, 8894, 390, 844)
            for _ in range(60):
                if await pg.evaluate("()=>!!AXU"): break
                await pg.wait_for_timeout(500)
            C = await show_v1(pg, "NVDA", 100, True)
            await pg.evaluate("()=>{const e=document.getElementById('axpanel');if(e)e.scrollIntoView({block:'center'});}")   # 手機沒有分頁列:捲到清單就會載入
            for _ in range(40):
                if await pg.evaluate("()=>!!document.querySelector('#axpanel table')"): break
                await pg.wait_for_timeout(500)
            res["mobile"] = {"marks": len(C["W"]), "overflow": await pg.evaluate("()=>document.documentElement.scrollWidth>window.innerWidth+1"),
                             "list_rows": await pg.evaluate("()=>document.querySelectorAll('#axpanel [data-axsym]').length"),
                             "tabrow_hidden": await pg.evaluate("()=>getComputedStyle(document.getElementById('wsxTabRow')).display==='none'"),
                             "errors": [e for e in errs2 if "Failed to load resource" not in e][:10]}
            await pg.screenshot(path=os.path.join(HERE, "t15_mobile_list.png"), full_page=False)
            await ctx.close()
        finally:
            srv.terminate(); shutil.rmtree(www, ignore_errors=True)
        await br.close()
    tr = res["tracked"]; fb = res["fallback"]
    res["ok"] = (all(c["off_traces_same_as_V0"] and c["off_layout_same_as_V0"] and c["quant_on_same_as_off"] and c["nonastra_on_same_as_off"] and c["astra_eq_python"] and c["d200_eq_python"] for c in tr)
                 and len(fb) >= 4 and all(f["ax"] == 1 and f["plot"] and f["bars_eq_astra_file"] and f["astra_eq_python"] and f["btn"] for f in fb)
                 and res["dot_alias"]["ax"] == 1 and res["notin"]["action"] and res["list"]["rows_eq_today"] and res["list"]["hw_eq"] and res["list"]["clicked_ok"]
                 and not res["overflow_desktop"] and not res["errors"] and not res["http_bad"] and not res["mobile"]["overflow"] and not res["mobile"]["errors"] and res["mobile"]["list_rows"] > 0)
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("tracked",)}, ensure_ascii=False)[:3000])
    for c in tr: print(c)
    print("OK" if res["ok"] else "NOT OK")

UNI = json.loads(urllib.request.urlopen(urllib.request.Request(AX + "uni.json", headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
def await_ai(s): return (UNI.get("ai", {}).get(s) or [None])[0]

if __name__ == "__main__":
    V0, V1, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
    asyncio.run(main())
