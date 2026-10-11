# t32:資料補齊後「不靠測試清快取」網頁自己會不會重算 —— Codex v0.4 §5 的驗收(Playwright,本機伺服器)
#   用法:python3 t32_refresh_test.py run   <舊版 index.html> <新版 index.html> <快照資料夾>
#         python3 t32_refresh_test.py probe <index.html> <快照資料夾>      (挑測試股票用,順便把資料錄進快照)
#
# 做法(對應 Codex v0.4 §5 五條):
#   1. 固定回應:gist / raw.githubusercontent 的檔「第一次錄下、之後一律重播」(快照資料夾);情境要改的檔(QQQ、個股日K)
#      由測試直接給內容 → 不會像 t31 那樣在模擬裡意外抓到線上完整檔。日期用真實的「最近已收盤日 2026-10-09(週五)」,
#      週末跑,所以不必改 tjLastDone。
#   2. 先讓網頁照「舊資料」畫一次;放行回補 = 把時鐘往後撥 11 分鐘(網頁每 10 分鐘才重抓一次)並把回應換成新檔。
#      之後**不清 dataset.sig、不清 CKC、不換股票、不重新整理**,只等網頁自己的 20/120 秒輪詢。
#   3. 回補的請求被回應後,再等一次自然輪詢 + 5 秒,才讀畫面;跟「一開始就拿到完整資料的新開頁面」逐條比對
#      (圖上全部 trace、狀態列、詳情裡的 QQQ 條件)。
#   4. 另加:同筆數換日期(檔固定 1250 根,本來就是這樣)、末日與末收不變只改舊價(模擬配息前復權)。
#   5. 另加:來源失敗(500)舊圖不閃、內容不變不重畫、盤中不偷用未收盤棒、新開頁面 13 檔新舊版相同。
# 只用來驗證「資料接受與快取失效」;合成的資料改動(刪一天、舊價 ×0.995)都在情境說明裡寫明,不是真實行情。
import asyncio, json, os, sys, time, tempfile, shutil, subprocess, hashlib, copy
from datetime import datetime, timezone
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
D, D1, D2 = "2026-10-09", "2026-10-08", "2026-10-07"       # 最近已收盤日、前一天、前兩天
SYMS13 = ["SPY", "QQQ", "TSM", "NVDA", "MU", "AMD", "PLTR", "AVGO", "META", "SNDK", "NVDL", "SLB", "BKNG"]
GIST_HOSTS = ("gist.githubusercontent.com", "raw.githubusercontent.com")
OFFSET_JUMP = 11 * 60 * 1000                                  # 往後撥 11 分鐘 → 超過網頁的 10 分鐘重抓間隔

INIT_JS = r"""(()=>{const RD=Date;let off=0;
  function FD(...a){if(!new.target)return RD();return a.length?new RD(...a):new RD(RD.now()+off);}
  FD.prototype=RD.prototype;FD.now=()=>RD.now()+off;FD.UTC=RD.UTC;FD.parse=RD.parse;
  window.Date=FD;window.__t32={setOff:ms=>{off=ms;},getOff:()=>off};})();"""
# 只計數、不改行為:駕駛艙 Plotly.react 次數;駕駛艙出現「載入中/尚無日K」佔位(.miss)或圖被拿掉的次數
COUNT_JS = r"""()=>{if(window.__ck)return;window.__ck={react:0,miss:0,noplot:0};
  const P=window.Plotly,orig=P.react;
  P.react=function(gd){const id=typeof gd==='string'?gd:(gd&&gd.id);if(id==='cockpit')__ck.react++;return orig.apply(this,arguments);};
  const el=document.getElementById('cockpit');
  new MutationObserver(()=>{if(el.querySelector('.miss'))__ck.miss++;if(!el.querySelector('.plot-container'))__ck.noplot++;}).observe(el,{childList:true});}"""
CAPTURE_JS = r"""()=>{const el=document.getElementById('cockpit');const T=(el&&el.data)||[];
  const A=v=>v==null?null:Array.from(v).map(z=>z==null?null:(typeof z==='number'?+z.toFixed(6):String(z)));
  const traces=T.map(t=>({name:t.name||'',type:t.type||'',x:A(t.x),y:A(t.y),o:A(t.open),h:A(t.high),l:A(t.low),c:A(t.close),
    text:Array.isArray(t.text)?A(t.text):(t.text==null?null:String(t.text)),cd:Array.isArray(t.customdata)?t.customdata.map(v=>typeof v==='string'?v:JSON.stringify(v)):null}));
  const txt=h=>String(h||'').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
  const marks=[];T.filter(t=>/^量化/.test(t.name||'')&&t.name!=='量化盤中').forEach(t=>t.y.forEach((v,i)=>{if(v!=null&&String(t.text[i]||'').trim())marks.push(t.name.slice(2)+'|'+String(t.x[i]));}));
  const cs=T.find(t=>t.type==='candlestick'),q=document.querySelector('#qstrip .sbar'),dq=document.getElementById('dqstrip');
  const qc=(typeof qqqCloses==='function')?qqqCloses():null,ld=tjLastDone();
  const qs=qc?Object.keys(qc).filter(d=>d<=ld).sort():[];
  const ms=el&&el.querySelector('.miss'),as=document.getElementById('astrastrip');
  return {build:BUILD,sym:CHIP_SYM,lastDone:ld,sig:el?(el.dataset.sig||''):'',msg:ms?txt(ms.innerHTML).slice(0,80):'',traces:traces,marks:marks.sort(),kx:cs?A(cs.x):[],
    qbar:q?txt(q.innerHTML):'',qpop:q?txt(q._pop):'',astra:(as&&as.style.display!=='none')?txt(as.innerHTML):'',astraOn:(typeof CHIP_ASTRA!=='undefined')?CHIP_ASTRA:null,dq:(dq&&dq.style.display!=='none')?txt(dq.innerHTML):'',
    fileLast:(CHIPK[CHIP_SYM]&&CHIPK[CHIP_SYM].bars)?CHIPK[CHIP_SYM].bars[CHIPK[CHIP_SYM].bars.length-1][0]:null,
    fileN:(CHIPK[CHIP_SYM]&&CHIPK[CHIP_SYM].bars)?CHIPK[CHIP_SYM].bars.length:0,
    qqqLastFile:(()=>{let l='';for(const d in (QQQK||{}))if(d>l)l=d;return l;})(),qqqN:QQQK?Object.keys(QQQK).length:0,
    qqqLast20:qs.slice(-20).map(d=>d.slice(5)+':'+qc[d]),ck:window.__ck?Object.assign({},window.__ck):null};}"""


def load_snap(snap, fn):
    return json.load(open(os.path.join(snap, fn)))


def body(obj):
    return json.dumps(obj, separators=(",", ":")).encode()


class Router:
    """gist/raw 檔:錄一次、之後重播。overrides[fn] = {'old':(status,bytes), 'new':(status,bytes)};phase 決定給哪一份。"""
    def __init__(self, snap, overrides=None, phase="old"):
        self.snap, self.ov, self.phase = snap, overrides or {}, phase
        self.log, self.md = [], 0

    async def handle(self, route):
        url = route.request.url
        fn = url.split("?")[0].rsplit("/", 1)[-1]
        hdr = {"content-type": "application/json; charset=utf-8", "access-control-allow-origin": "*"}
        if fn.endswith(".gz64"):
            return await route.fulfill(status=404, body="", headers=hdr)
        if fn == "market_data.json":
            self.md += 1
        if fn in self.ov:
            spec = self.ov[fn][self.phase]; st, b = spec[0], spec[1]
            ph = self.phase
            if len(spec) > 2:                                 # 指定這個回應晚幾秒才到(模擬網路先後順序)
                await asyncio.sleep(spec[2])
            self.log.append({"t": time.time(), "fn": fn, "phase": ph, "status": st})
            return await route.fulfill(status=st, body=b if st == 200 else b"err", headers=hdr)
        p = os.path.join(self.snap, fn)
        if not os.path.exists(p):
            r = await route.fetch()
            b = await r.body()
            if r.status == 200:
                tmp = p + ".part"; open(tmp, "wb").write(b); os.replace(tmp, p)
            return await route.fulfill(status=r.status, body=b, headers=hdr)
        return await route.fulfill(status=200, body=open(p, "rb").read(), headers=hdr)


class Site:
    def __init__(self, page_file, port):
        self.www = tempfile.mkdtemp(prefix="t32_")
        shutil.copy(page_file, os.path.join(self.www, "index.html"))
        os.symlink(os.path.join(REPO, "data"), os.path.join(self.www, "data"))
        for js in ("astra-flow.js", "astra-dashboard-adapter.js"):   # 🧪Astra 研究層的兩個原檔(網站根目錄)
            if os.path.exists(os.path.join(REPO, js)):
                shutil.copy(os.path.join(REPO, js), os.path.join(self.www, js))
        self.port = port
        self.srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=self.www,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

    def close(self):
        self.srv.terminate(); shutil.rmtree(self.www, ignore_errors=True)


async def open_page(browser, site, router, offset_ms=0):
    ctx = await browser.new_context(viewport={"width": 1400, "height": 1000}, ignore_https_errors=True, service_workers="block")
    await ctx.add_init_script(INIT_JS + ("" if not offset_ms else f"window.__t32.setOff({int(offset_ms)});"))
    for h in GIST_HOSTS:
        await ctx.route(f"https://{h}/**", router.handle)
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(f"http://127.0.0.1:{site.port}/index.html", wait_until="domcontentloaded", timeout=120000)
    for _ in range(180):
        if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof FCL!=='undefined'&&!!FCL&&!!EXTDF&&Object.keys(chipDaily()).length>=250"):
            break
        await pg.wait_for_timeout(1000)
    for _ in range(60):
        if await pg.evaluate("()=>!!QQQK"):
            break
        await pg.wait_for_timeout(500)
    return ctx, pg, errs


async def select_sym(pg, sym):
    """像使用者一樣在輸入框打代號 ↵(只在放行回補「之前」做)。"""
    if await pg.evaluate("s=>CHIP_SYM===s", sym):
        return
    await pg.fill("#chipInput", sym); await pg.press("#chipInput", "Enter")
    for _ in range(80):
        await pg.wait_for_timeout(500)
        ok = await pg.evaluate("""s=>{const e=document.getElementById('cockpit');const u=TK_UL[s]||s;
          return CHIP_SYM===s&&!!(CHIPK[s]&&CHIPK[s].bars)&&!!(CHIPK[u]&&CHIPK[u].bars)&&!!e.querySelector('.plot-container')&&(e.dataset.sig||'').startsWith(s+':');}""", sym)
        if ok:
            break
    await pg.wait_for_timeout(4000)


async def astra_on(pg):
    """按 K 線疊加列的「Astra」鈕(使用者動作;只在放行回補之前做)。"""
    await pg.click(".cidxchipA")
    for _ in range(40):
        await pg.wait_for_timeout(500)
        if await pg.evaluate("()=>CHIP_ASTRA&&!!document.getElementById('astrastrip')&&document.getElementById('astrastrip').style.display!=='none'"):
            break
    await pg.wait_for_timeout(3000)


def trunc(bars, last, n=1250, drop=()):
    """日K檔照上游的樣子:只到 last、去掉 drop 那幾天、只留最後 n 根(上游固定 1250 根)。"""
    out = [b for b in bars if b[0] <= last and b[0] not in drop]
    return out[-n:]


def kfile(src, bars):
    o = copy.deepcopy(src); o["bars"] = bars; return o


def scenarios(snap, X):
    QQ, SP, KX = load_snap(snap, "kline_QQQ.json"), load_snap(snap, "kline_SPY.json"), load_snap(snap, f"kline_{X}.json")
    full = lambda F: kfile(F, trunc(F["bars"], D))
    qfq = lambda F, last: kfile(F, [b if b[0] >= "2026-09-21" else [b[0]] + [round(v * 0.995, 4) for v in b[1:5]] + list(b[5:])
                                    for b in trunc(F["bars"], last)])
    S = {}
    S["S1_QQQ缺中間一天"] = dict(
        desc=f"QQQ 日K檔停在 {D2}(少 {D1}),{D} 那根只在富途快照;回補檔到 {D}。個股檔一開始就完整。筆數都是 1250(上游固定)。",
        ov={"kline_QQQ.json": {"old": (200, body(kfile(QQ, trunc(QQ['bars'], D2)))), "new": (200, body(full(QQ)))},
            f"kline_{X}.json": {"old": (200, body(full(KX))), "new": (200, body(full(KX)))}}, expect=["kline_QQQ.json"])
    S["S2_個股缺中間一天"] = dict(
        desc=f"{X} 日K檔停在 {D2}(少 {D1}),{D} 那根只在快照;回補檔到 {D}(固定 1250 根 → 同筆數換日期)。QQQ 一開始就完整。",
        ov={f"kline_{X}.json": {"old": (200, body(kfile(KX, trunc(KX['bars'], D2)))), "new": (200, body(full(KX)))}},
        expect=[f"kline_{X}.json"])
    S["S3_同末日補中段"] = dict(
        desc=f"{X} 日K檔到 {D1} 但中間少 2026-10-01;回補檔同樣到 {D1}(末日相同)、補回 10-01;{D} 那根在快照。",
        ov={f"kline_{X}.json": {"old": (200, body(kfile(KX, trunc(KX['bars'], D1, drop=('2026-10-01',))))),
                                "new": (200, body(kfile(KX, trunc(KX['bars'], D1))))}}, expect=[f"kline_{X}.json"])
    if os.environ.get("T32_ASTRA", "1") == "1":
        S["S3A_同末日補中段_Astra開"] = dict(S["S3_同末日補中段"], astra=True,
            desc=S["S3_同末日補中段"]["desc"] + " 另把 🧪Astra 研究層打開(使用者按鈕),看 Astra 記號也跟著重算。")
    S["S4_兩者都缺一天"] = dict(
        desc=f"網頁開了兩天的實際樣子:QQQ 和 {X} 的日K檔都停在 {D2},{D} 在快照;回補兩個檔都到 {D}。",
        ov={"kline_QQQ.json": {"old": (200, body(kfile(QQ, trunc(QQ['bars'], D2)))), "new": (200, body(full(QQ)))},
            f"kline_{X}.json": {"old": (200, body(kfile(KX, trunc(KX['bars'], D2)))), "new": (200, body(full(KX)))}},
        expect=["kline_QQQ.json", f"kline_{X}.json"])
    S["S4b_兩者都缺_QQQ晚到"] = dict(
        desc=f"同 S4,但 QQQ 的回補檔晚 4 秒才到(個股的先到)—— 網路先後順序本來就不固定。",
        ov={"kline_QQQ.json": {"old": (200, body(kfile(QQ, trunc(QQ['bars'], D2)))), "new": (200, body(full(QQ)), 4)},
            f"kline_{X}.json": {"old": (200, body(kfile(KX, trunc(KX['bars'], D2)))), "new": (200, body(full(KX)))}},
        expect=["kline_QQQ.json", f"kline_{X}.json"])
    S["S5_只改舊價"] = dict(
        desc=f"模擬配息前復權:{X} 日K檔到 {D1},舊檔 2026-09-21 以前的開高低收 ×0.995(合成),新檔是原值;末日、末收、筆數都相同。",
        ov={f"kline_{X}.json": {"old": (200, body(qfq(KX, D1))), "new": (200, body(kfile(KX, trunc(KX['bars'], D1))))}},
        expect=[f"kline_{X}.json"])
    S["S6_來源失敗"] = dict(
        desc=f"QQQ 與 {X} 的日K檔停在 {D2};放行後重抓一律回 HTTP 500 → 舊圖要留著、不閃「載入中」。",
        ov={"kline_QQQ.json": {"old": (200, body(kfile(QQ, trunc(QQ['bars'], D2)))), "new": (500, b"")},
            f"kline_{X}.json": {"old": (200, body(kfile(KX, trunc(KX['bars'], D2)))), "new": (500, b"")}},
        expect=["kline_QQQ.json", f"kline_{X}.json"], fresh=False)
    S["S7_內容不變"] = dict(
        desc=f"QQQ 與 {X} 的日K檔停在 {D2};重抓回來的檔一模一樣(上游還沒更新)→ 不該重畫、不該一直重畫。",
        ov={"kline_QQQ.json": {"old": (200, body(kfile(QQ, trunc(QQ['bars'], D2)))), "new": (200, body(kfile(QQ, trunc(QQ['bars'], D2))))},
            f"kline_{X}.json": {"old": (200, body(kfile(KX, trunc(KX['bars'], D2)))), "new": (200, body(kfile(KX, trunc(KX['bars'], D2))))}},
        expect=["kline_QQQ.json", f"kline_{X}.json"], fresh=False)
    # 資料品質條(dqBanner)的「停更自癒」路徑:這檔沒有富途快照、日K檔落後一天 → 紅條;10 分鐘後自己重抓
    MD = load_snap(snap, "market_data.json"); MDx = copy.deepcopy(MD); (MDx.get("kline_today") or {}).pop(X, None)
    mdx = (200, body(MDx))
    S["S10_紅條重抓失敗"] = dict(
        desc=f"把 {X} 的富途快照拿掉、日K檔停在 {D1}(落後 1 天 → 紅條);放行後重抓回 HTTP 500 → 舊圖要留著。",
        ov={"market_data.json": {"old": mdx, "new": mdx},
            f"kline_{X}.json": {"old": (200, body(kfile(KX, trunc(KX['bars'], D1)))), "new": (500, b"")}},
        expect=[f"kline_{X}.json"], fresh=False)
    S["S11_紅條重抓成功"] = dict(
        desc=f"同 S10,但重抓回來是到 {D} 的完整檔 → 要更新成新開頁面的樣子,過程中不閃「載入中」。",
        ov={"market_data.json": {"old": mdx, "new": mdx},
            f"kline_{X}.json": {"old": (200, body(kfile(KX, trunc(KX['bars'], D1)))), "new": (200, body(full(KX)))}},
        expect=[f"kline_{X}.json"])
    return S


async def run_dynamic(browser, site, snap, X, name, sc, out):
    """舊資料畫一次 → 撥時鐘 + 換回應 → 只等自然輪詢 → 讀畫面。"""
    r = Router(snap, sc["ov"], "old")
    ctx, pg, errs = await open_page(browser, site, r)
    try:
        await select_sym(pg, X)
        if sc.get("astra"):
            await astra_on(pg)
        stale = await pg.evaluate(CAPTURE_JS)
        await pg.evaluate(COUNT_JS)
        r.phase = "new"; t0 = time.time()
        await pg.evaluate("ms=>window.__t32.setOff(ms)", OFFSET_JUMP)
        while time.time() - t0 < 330:                       # 等網頁自己去重抓(下一次 20/120 秒輪詢觸發的重繪)
            if all(any(l["fn"] == f and l["phase"] == "new" for l in r.log) for f in sc["expect"]):
                break
            await pg.wait_for_timeout(1000)
        t1 = time.time(); md1 = r.md
        fetched = {f: any(l["fn"] == f and l["phase"] == "new" for l in r.log) for f in sc["expect"]}
        while time.time() - t1 < 200 and r.md < md1 + 1:    # 回補之後,再等一次自然輪詢
            await pg.wait_for_timeout(1000)
        await pg.wait_for_timeout(5000)
        after = await pg.evaluate(CAPTURE_JS)
        out[name] = {"desc": sc["desc"], "stale": stale, "after": after, "fetched": fetched,
                     "secs_to_fetch": round(t1 - t0, 1), "polls_after_fetch": r.md - md1, "errors": errs[:5],
                     "requests": [(round(l["t"] - t0, 1), l["fn"], l["phase"], l["status"]) for l in r.log]}
    finally:
        await ctx.close()


async def run_fresh(browser, site, snap, X, name, sc, out):
    """參考:一開始就拿到「新」回應的新開頁面。"""
    r = Router(snap, sc["ov"], "new")
    ctx, pg, errs = await open_page(browser, site, r)
    try:
        await select_sym(pg, X)
        if sc.get("astra"):
            await astra_on(pg)
        out[name] = {"fresh": await pg.evaluate(CAPTURE_JS), "errors": errs[:5]}
    finally:
        await ctx.close()


async def run_intraday(browser, site, snap, X, out):
    """盤中不偷用未收盤棒:把時鐘撥到 2026-10-09(週五)14:00 ET;日K檔只到 10-08,10-09 那根只在快照(當盤中棒)。"""
    QQ, KX = load_snap(snap, "kline_QQQ.json"), load_snap(snap, f"kline_{X}.json")
    ov = {"kline_QQQ.json": {"old": (200, body(kfile(QQ, trunc(QQ['bars'], D1)))), "new": None},
          f"kline_{X}.json": {"old": (200, body(kfile(KX, trunc(KX['bars'], D1)))), "new": None}}
    target = datetime(2026, 10, 9, 18, 0, tzinfo=timezone.utc)   # 14:00 EDT
    off = int((target.timestamp() - time.time()) * 1000)
    r = Router(snap, ov, "old")
    ctx, pg, errs = await open_page(browser, site, r, offset_ms=off)
    try:
        await select_sym(pg, X)
        cap = await pg.evaluate(CAPTURE_JS)
        cap["snapDate"] = await pg.evaluate("()=>snapDate()")
        out["S8_盤中"] = {"cap": cap, "errors": errs[:5]}
    finally:
        await ctx.close()


async def run_13(browser, site, snap, out):
    """新開頁面 13 檔(t31 ① 的重播版):新舊版記號與狀態列要完全相同。"""
    r = Router(snap, {}, "old")
    ctx, pg, errs = await open_page(browser, site, r)
    res = {}
    try:
        await pg.evaluate("()=>{CHIP_WIN=250;}")
        for s in SYMS13:
            await select_sym(pg, s)
            c = await pg.evaluate(CAPTURE_JS)
            res[s] = {"marks": c["marks"], "qbar": c["qbar"], "qpop": c["qpop"]}
        out["S9_13檔"] = {"res": res, "errors": errs[:5]}
    finally:
        await ctx.close()


async def probe(page_file, snap):
    os.makedirs(snap, exist_ok=True)
    site = Site(page_file, 8799)
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""),
                                              "--proxy-bypass-list=127.0.0.1;localhost"])
            r = Router(snap, {}, "old")
            ctx, pg, errs = await open_page(b, site, r)
            for s in SYMS13:
                await select_sym(pg, s)
                c = await pg.evaluate(CAPTURE_JS)
                q = c["qpop"]; i = q.find("碼條件"); j = q.find("碼規則"); k = q.find("加 :")
                print(s, "| 狀態列:", c["qbar"][:60], "| 加碼:", (q[i - 1:i + 90] if i >= 0 else (q[j - 1:j + 40] if j >= 0 else "—")),
                      "| 最近記號:", [m for m in c["marks"] if m.split("|")[1] >= "09-20"][-6:])
            print("errors", errs[:3])
            await ctx.close(); await b.close()
    finally:
        site.close()
    print("snapshot files:", sorted(os.listdir(snap)))


def slim(o):
    """存檔前把整包 trace 換成雜湊(比對用 sha256;K線日期 kx、記號、狀態列、詳情原文照存)。"""
    if isinstance(o, dict):
        return {k: ({"sha256": hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True).encode()).hexdigest(), "n": len(v)}
                    if k == "traces" and isinstance(v, list) else slim(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [slim(v) for v in o]
    return o


def same(a, b, keys=("traces", "marks", "qbar", "qpop", "dq", "astra")):
    return {k: a.get(k) == b.get(k) for k in keys}


async def main_run(old_file, new_file, snap, X):
    out = {"X": X, "snap": {}, "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    for fn in sorted(os.listdir(snap)):
        if fn.endswith(".json"):
            out["snap"][fn] = hashlib.sha256(open(os.path.join(snap, fn), "rb").read()).hexdigest()[:16]
    S = scenarios(snap, X)
    only = os.environ.get("T32_ONLY")                     # 除錯用:只跑某幾個情境(逗號分隔的前綴,如 S2,S8)
    if only:
        S = {k: v for k, v in S.items() if any(k.startswith(o) for o in only.split(","))}
    sites = {"old": Site(old_file, 8801), "new": Site(new_file, 8802)}
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""),
                                              "--proxy-bypass-list=127.0.0.1;localhost"])
            sem = asyncio.Semaphore(int(os.environ.get("T32_PAR", "4")))
            res = {"old": {}, "new": {}}

            async def job(fn, *a):
                async with sem:
                    try:
                        await fn(*a)
                    except Exception as e:
                        print("job error", fn.__name__, a[-2] if len(a) > 2 else "", e)
            jobs = []
            for tag in ("old", "new"):
                for name, sc in S.items():
                    jobs.append(job(run_dynamic, b, sites[tag], snap, X, name, sc, res[tag]))
                    if sc.get("fresh", True):
                        jobs.append(job(run_fresh, b, sites[tag], snap, X, name + "_fresh", sc, res[tag]))
                if not only or "S8" in only:
                    jobs.append(job(run_intraday, b, sites[tag], snap, X, res[tag]))
                if not only or "S9" in only:
                    jobs.append(job(run_13, b, sites[tag], snap, res[tag]))
            await asyncio.gather(*jobs)
            await b.close()
    finally:
        for s in sites.values():
            s.close()
    if os.environ.get("T32_MERGE"):                       # 補跑部分情境:併進既有結果檔
        prev = json.load(open(os.path.join(HERE, os.environ.get("T32_OUT", "t32_refresh_test.json"))))
        for tag in ("old", "new"):
            prev["res"][tag].update(res[tag])
        prev.setdefault("merged_runs", []).append({"only": only, "run_utc": out["run_utc"]})
        out = prev
    else:
        out["res"] = res
    out = slim(out)
    json.dump(out, open(os.path.join(HERE, os.environ.get("T32_OUT", "t32_refresh_test.json")), "w"), ensure_ascii=False, indent=1)
    report(out)


def report(out):
    res, X = out["res"], out["X"]
    bld = {t: next((v[k]["build"] for v in res[t].values() if isinstance(v, dict) for k in ("after", "fresh", "cap") if isinstance(v.get(k), dict)), "?") for t in ("old", "new")}
    print(f"測試股票 {X};舊版 BUILD {bld['old']} / 新版 BUILD {bld['new']};快照 {len(out.get('snap', {}))} 個檔;跑的時間(UTC){out.get('run_utc')}")
    for name in [k for k in res["new"] if k.startswith("S") and not k.endswith("_fresh") and k.split("_")[0] in ("S1", "S2", "S3", "S3A", "S4", "S4b", "S5", "S6", "S7", "S10", "S11")]:
        for tag in ("old", "new"):
            r = res[tag].get(name)
            if not r:
                print(name, tag, "沒有結果"); continue
            st, af = r["stale"], r["after"]
            fr = (res[tag].get(name + "_fresh") or {}).get("fresh")
            cmp_f = same(af, fr) if fr else None
            ck = af.get("ck") or {}
            print(f"{name} {tag}: 重抓到={r['fetched']}(撥鐘後 {r['secs_to_fetch']}s)回補後輪詢 {r['polls_after_fetch']} 次 | "
                  f"跟新開頁面相同={cmp_f} | 跟舊畫面相同={same(af, st)['traces']} | 重畫 {ck.get('react')} 次、佔位 {ck.get('miss')}、無圖 {ck.get('noplot')} | "
                  f"K線有{D1[5:]}={D1[5:] in af['kx']} 有10-01={'10-01' in af['kx']} | 檔末 {af['fileLast']}/{af['fileN']} QQQ檔末 {af['qqqLastFile']}/{af['qqqN']} | 錯誤 {r['errors']}")
    for tag in ("old", "new"):
        c = (res[tag].get("S8_盤中") or {}).get("cap")
        if c:
            print(f"S8_盤中 {tag}: lastDone {c['lastDone']} snapDate {c['snapDate']} 10-09 確認記號={[m for m in c['marks'] if m.endswith('10-09')]} 狀態列:{c['qbar'][:50]}")
    o8, n8 = (res["old"].get("S8_盤中") or {}).get("cap"), (res["new"].get("S8_盤中") or {}).get("cap")
    if o8 and n8:
        print("S8_盤中 新舊版相同:", same(o8, n8))
    o9, n9 = (res["old"].get("S9_13檔") or {}).get("res"), (res["new"].get("S9_13檔") or {}).get("res")
    if o9 and n9:
        print("S9_13檔 新舊版相同:", sum(o9[s] == n9[s] for s in SYMS13), "/", len(SYMS13), [s for s in SYMS13 if o9[s] != n9[s]])


if __name__ == "__main__":
    if sys.argv[1] == "probe":
        asyncio.run(probe(sys.argv[2], sys.argv[3]))
    elif sys.argv[1] == "report":
        report(json.load(open(os.path.join(HERE, "t32_refresh_test.json"))))
    else:
        asyncio.run(main_run(sys.argv[2], sys.argv[3], sys.argv[4], os.environ.get("T32_SYM", "NVDA")))
