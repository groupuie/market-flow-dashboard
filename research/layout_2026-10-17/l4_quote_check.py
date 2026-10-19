# l4:自選清單的「最新價 / 漲跌」逐檔對帳(2026-10-17 複核後的修正版)——用 gist 真實歷史檔重播三個時段
#   A 盤前(gist 1e0498b,10/16 12:02Z = 美東 08:02):快照日期夾到 10-15;昨收要是 10-14(不是更早)
#   B 盤中(gist add6036,10/16 15:44Z):Mac 快輪只更新 SPY 的 last、走勢/chg1d 停在全量輪 → 舊寫法 SPY 漲跌會錯;
#      新寫法:最新價=當日K快照、昨收=scan.json(這裡把 scan 的日期/收盤改成 10-15 模擬當時的夜間檔)
#   C 盤中、但 scan 還停在 10-14(夜間引擎沒跑)→ 走「抓該檔日K」那條路,數字要跟 B 一樣
#   預期值用 Python 從同一份資料獨立算:最新價=kline_today 收盤;昨收=日K檔裡「前一個交易日」那根的收盤
#   用法:python3 l4_quote_check.py <新版 index.html> <快照資料夾(含 kline_*.json)> <gist 歷史資料夾(git repo)>
import asyncio, json, os, sys, shutil, subprocess, tempfile, time, importlib.util, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
T32 = os.path.join(os.path.dirname(HERE), "requant_2026-10-10", "t32_refresh_test.py")
spec = importlib.util.spec_from_file_location("t32", T32); t32 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t32)
from playwright.async_api import async_playwright
WL = ["SPY", "NVDA", "MU", "QQQ", "SMH", "ALAB", "TQQQ", "BTC-USD"]
CASES = {"A": ("1e0498b", "2026-10-16T12:03:00Z", None), "B": ("add6036", "2026-10-16T15:45:00Z", "2026-10-15"), "C": ("add6036", "2026-10-16T15:45:00Z", "2026-10-14")}
ROWS = r"""()=>[...document.querySelectorAll('#wlBody .wlRow')].map(r=>({s:r.getAttribute('data-wl'),
  px:((r.querySelector('.wlPx')||{}).childNodes[0]||{}).textContent,tg:(r.querySelector('.wlPx .tg')||{}).textContent||'',
  ch:(r.querySelector('.wlCh')||{}).textContent,pc:(r.querySelector('.wlPc .pill')||{}).textContent,title:r.title||''}))"""


def kbars(snap, s):
    p = os.path.join(snap, f"kline_{s}.json")
    return json.load(open(p))["bars"] if os.path.exists(p) else None


def prev_td(d, hol):
    x = dt.date.fromisoformat(d)
    for _ in range(12):
        x -= dt.timedelta(days=1)
        if x.weekday() < 5 and x.isoformat() not in hol: return x.isoformat()


def expect(md, snap, s, D, hol):
    q = None
    for k in ("stocks", "market", "leveraged", "crypto"):
        if s in (md.get(k) or {}): q = md[k][s]
    kt = (md.get("kline_today") or {}).get(s)
    if kt:
        d = min(kt[0], D); last = kt[4]; P = prev_td(d, hol)
        b = kbars(snap, s); prev = None
        if b:
            m = {x[0]: x[4] for x in b}; prev = m.get(P)
        return last, prev
    if q:
        sp = q["spark"]; return q["last"], (sp[-2] if abs(sp[-1] - q["last"]) < 1e-6 * max(1, q["last"]) else None)
    return None, None


def fmt(v, ref):
    a = abs(v); n = 2 if abs(ref) >= 1 else (3 if abs(ref) >= .1 else 4)
    return f"{a:,.2f}" if a >= 1000 else f"{a:.{n}f}"


class Site2:
    """同 t32.Site,但 data/ 用一份可改的複本(這裡只改 scan.json 的日期/收盤)"""
    def __init__(self, page_file, port, scan_patch):
        self.www = tempfile.mkdtemp(prefix="l4_")
        shutil.copy(page_file, os.path.join(self.www, "index.html"))
        shutil.copytree(os.path.join(REPO, "data"), os.path.join(self.www, "data"))
        for js in ("astra-flow.js", "astra-dashboard-adapter.js"):
            if os.path.exists(os.path.join(REPO, js)): shutil.copy(os.path.join(REPO, js), os.path.join(self.www, js))
        if scan_patch:
            p = os.path.join(self.www, "data", "scan.json"); j = json.load(open(p))
            for r in j["rows"]:
                if r["sym"] in scan_patch: r["d"], r["px"] = scan_patch[r["sym"]]
                else: r["d"] = "2000-01-01"
            json.dump(j, open(p, "w"))
        self.port = port
        self.srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=self.www, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

    def close(self):
        self.srv.terminate(); shutil.rmtree(self.www, ignore_errors=True)


async def run_case(b, page, snap, gist, case, port, out):
    commit, when, scan_d = CASES[case]
    md = json.loads(subprocess.check_output(["git", "-C", gist, "show", f"{commit}:market_data.json"]))
    sd = tempfile.mkdtemp(prefix="l4snap_")
    for f in os.listdir(snap): shutil.copy(os.path.join(snap, f), sd)
    json.dump(md, open(os.path.join(sd, "market_data.json"), "w"))
    pub = dict(md); t = dt.datetime.fromisoformat(md["ts_utc"].replace(" ", "T")) - dt.timedelta(hours=5)
    pub["ts_utc"] = t.strftime("%Y-%m-%d %H:%M:%S"); pub["source"] = "public-collector"
    json.dump(pub, open(os.path.join(sd, "market_public.json"), "w"))
    patch = None
    if scan_d:
        patch = {}
        for s in WL:
            bb = kbars(snap, s)
            if bb:
                m = {x[0]: x[4] for x in bb}
                if scan_d in m: patch[s] = (scan_d, m[scan_d])
    site = Site2(page, port, patch)
    r = t32.Router(sd, {}, "old")
    try:
        off = int((dt.datetime.fromisoformat(when.replace("Z", "+00:00")).timestamp() - time.time()) * 1000)
        ctx = await b.new_context(ignore_https_errors=True, service_workers="block", viewport={"width": 1920, "height": 1080})
        await ctx.add_init_script(t32.INIT_JS); await ctx.add_init_script("window.__t32.setOff(%d);" % off)
        await ctx.add_init_script("try{localStorage.setItem('mfd_wl',JSON.stringify(%s));}catch(_){}" % json.dumps(WL))
        for h in t32.GIST_HOSTS: await ctx.route(f"https://{h}/**", r.handle)
        pg = await ctx.new_page(); errs = []; kreq = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.on("request", lambda q: kreq.append(q.url.split("?")[0].rsplit("/", 1)[-1]) if "kline_" in q.url or "/k/" in q.url else None)
        await pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="domcontentloaded", timeout=120000)
        for _ in range(120):
            if await pg.evaluate("()=>!!document.querySelector('#cockpit .plot-container')&&typeof DATA!=='undefined'&&!!DATA&&!DATA._partial"): break
            await pg.wait_for_timeout(1000)
        await pg.wait_for_timeout(12000)
        rows = await pg.evaluate(ROWS)
        D = await pg.evaluate("()=>snapDate()")
        hol = await pg.evaluate("()=>Object.keys(TJ_HOL)")
        res = {"D": D, "rows": rows, "errors": errs[:5], "k_fetch": sorted(set(kreq)), "bad": []}
        for row in rows:
            last, prev = expect(md, snap, row["s"], D, set(hol))
            want_px = fmt(last, last) if last is not None else "—"
            if row["px"].lstrip("-") != want_px: res["bad"].append((row["s"], "價", row["px"], want_px))
            if last is not None and prev:
                ch, pc = last - prev, (last / prev - 1) * 100
                if row["pc"].lstrip("+-") != f"{abs(pc):.2f}%": res["bad"].append((row["s"], "幅", row["pc"], f"{pc:+.2f}%"))
                if row["ch"].lstrip("+-") != fmt(ch, last): res["bad"].append((row["s"], "額", row["ch"], f"{ch:+.4f}"))
            elif row["pc"] != "—": res["bad"].append((row["s"], "應為 —", row["pc"]))
        out[case] = res
        await ctx.close()
    finally:
        site.close(); shutil.rmtree(sd, ignore_errors=True)


async def main(page, snap, gist):
    out = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--ignore-certificate-errors", "--proxy-server=" + os.environ.get("HTTPS_PROXY", ""), "--proxy-bypass-list=127.0.0.1;localhost"])
        port = 8971
        for c in CASES:
            await run_case(b, page, snap, gist, c, port, out); port += 1
        await b.close()
    L = []
    for c, (commit, when, scan_d) in CASES.items():
        R = out[c]
        L.append(f"=== {c}:gist {commit} 時鐘 {when} scan 日期 {scan_d or '(原檔)'} → snapDate {R['D']} | 錯誤 {R['errors']}")
        L.append("   " + " | ".join(f"{x['s']} {x['px']}{('(' + x['tg'] + ')') if x['tg'] else ''} {x['ch']} {x['pc']}" for x in R["rows"]))
        L.append(f"   不符 = {R['bad'] or '無'} | 這次抓的日K檔 = {R['k_fetch']}")
    txt = "\n".join(L)
    open(os.path.join(HERE, "l4_quote_check.log"), "w").write(txt + "\n")
    json.dump(out, open(os.path.join(HERE, "l4_quote_check.json"), "w"), ensure_ascii=False, indent=1)
    print(txt)


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:4]))
