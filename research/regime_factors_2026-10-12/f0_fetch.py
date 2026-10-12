# 第 6 輪資料:背景值(總經、跨資產、期權、部位、板塊)+ 擴大股票範圍的試跑(只抓資料,不在 repo 存資料)
#   資料放 /home/claude/work/macro(背景值)與 /home/claude/work/t30/yh(個股日K,沿用 s4_lib 的格式)
import json, os, sys, time, re, io, urllib.request, urllib.parse, concurrent.futures as cf
import pandas as pd, numpy as np
UA = {"User-Agent": "Mozilla/5.0"}
MAC = "/home/claude/work/macro"; YM = os.path.join(MAC, "yh"); YS = "/home/claude/work/t30/yh"
os.makedirs(YM, exist_ok=True)
T0 = time.time(); LOG = {}

def get(u, timeout=60, hdr=None):
    r = urllib.request.Request(u, headers=dict(UA, **(hdr or {})))
    return urllib.request.urlopen(r, timeout=timeout).read()

def yahoo(sym, out_dir):
    fn = os.path.join(out_dir, sym.replace("^", "_").replace("=", "_").replace("/", "-") + ".pkl")
    if os.path.exists(fn) and time.time() - os.path.getmtime(fn) < 6 * 3600: return sym, "cached"
    err = ""
    for a in range(3):
        try:
            u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?period1=0&period2={int(time.time())}&interval=1d&events=div%2Csplit"
            d = json.loads(get(u))
            r = d["chart"]["result"][0]; ts = r.get("timestamp") or []
            if not ts: return sym, "empty"
            q = r["indicators"]["quote"][0]; adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose")
            tz = r["meta"].get("exchangeTimezoneName", "America/New_York")
            idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert(tz).tz_localize(None).normalize()
            df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"], "v": q["volume"]}, index=idx, dtype="float64")
            df["ac"] = np.array(adj, dtype="float64") if adj else df["c"]
            df = df[~df.index.duplicated(keep="last")].dropna(subset=["c"])
            df.to_pickle(fn); return sym, len(df)
        except Exception as e:
            err = str(e)[:80]; time.sleep(2 + 3 * a)
    return sym, "ERR " + err

# ---------- 1. 背景值(Yahoo)----------
MACRO = ["^VIX", "^VIX3M", "^VIX9D", "^VVIX", "^MOVE", "^SKEW", "^TNX", "^FVX", "^IRX", "^TYX", "CL=F", "BZ=F", "NG=F", "GC=F", "SI=F", "HG=F",
         "DX-Y.NYB", "JPY=X", "EURUSD=X", "HYG", "JNK", "LQD", "IEF", "TLT", "SHY", "TIP", "BWX", "XLY", "XLP", "XLK", "XLF", "XLE", "XLV", "XLU", "XLI",
         "XLB", "XLC", "XLRE", "SMH", "SOXX", "IGV", "SKYY", "ARKK", "IWM", "RSP", "MTUM", "SPHB", "SPLV", "EEM", "EWJ", "FXI", "KRE", "XBI", "BTC-USD",
         "^GSPC", "^NDX", "^SOX", "GLD", "SLV", "USO", "UUP", "XRT", "QQQ", "SPY"]
with cf.ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda s: yahoo(s, YM), MACRO))
LOG["macro"] = {s: r for s, r in res}
print("macro", sum(isinstance(r, int) or r == "cached" for s, r in res), "/", len(res), [x for x in res if not (isinstance(x[1], int) or x[1] == "cached")], f"{time.time()-T0:.0f}s", flush=True)

# ---------- 2. 名單:S&P 500、Nasdaq-100(Wikipedia)、全美股當日成交金額(Nasdaq 篩選器)----------
def wiki_table(url, col_pat):
    html = get(url).decode("utf-8", "ignore")
    for t in pd.read_html(io.StringIO(html)):
        cols = [str(c) for c in t.columns]
        k = next((c for c in cols if re.search(col_pat, c, re.I)), None)
        if k is not None and len(t) >= 90: return t, k
    raise RuntimeError("table not found " + url)
t, k = wiki_table("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies", r"^Symbol$")
sp = [str(x).replace(".", "-").strip() for x in t[k]]
sub = next((c for c in t.columns if "Sub-Industry" in str(c)), None); sec = next((c for c in t.columns if "Sector" in str(c)), None)
SPM = {str(r[k]).replace(".", "-").strip(): {"sector": str(r[sec]) if sec else "", "sub": str(r[sub]) if sub else ""} for _, r in t.iterrows()}
try:
    t2, k2 = wiki_table("https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies", r"^(Ticker|Symbol)")
    ndx = [str(x).replace(".", "-").strip() for x in t2[k2]]
except Exception as e:   # Wikipedia 改版找不到表 → 用 groups.json(2026-06-05 名單)
    G_ = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "swing_tune_2026-10-12", "groups.json")))
    ndx = sorted(set(G_["NDX"]) | set(G_["NDX_missing_in_data"]) | set(G_["MAG7"])); print("NDX fallback groups.json", len(ndx), str(e)[:80])
scr = json.loads(get("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&download=true", hdr={"Accept": "application/json"}))["data"]["rows"]
def num(s):
    try: return float(str(s).replace("$", "").replace(",", ""))
    except Exception: return float("nan")
rows = []
for r in scr:
    sym = str(r["symbol"]).strip().replace("/", "-").replace("^", "-")
    if not re.fullmatch(r"[A-Z][A-Z0-9\-\.]{0,6}", sym): continue
    px, vol, mc = num(r["lastsale"]), num(r["volume"]), num(r["marketCap"])
    rows.append({"sym": sym, "px": px, "vol": vol, "dv": px * vol, "mc": mc, "sector": r.get("sector", ""), "industry": r.get("industry", ""), "name": r.get("name", "")})
scr_df = pd.DataFrame(rows).dropna(subset=["dv"]).sort_values("dv", ascending=False)
top100 = list(scr_df.head(100).sym)
json.dump({"date": time.strftime("%Y-%m-%d"), "sp500": sp, "sp500_meta": SPM, "ndx": ndx, "top100_dv_last_session": top100,
           "screener_n": len(scr_df), "screener_top300": scr_df.head(300).to_dict("records")}, open(os.path.join(MAC, "universe.json"), "w"), ensure_ascii=False)
print("名單 S&P500", len(sp), "NDX", len(ndx), "top100", top100[:12], f"{time.time()-T0:.0f}s", flush=True)

# ---------- 3. 擴大範圍試跑:這些股票的日K(全史)----------
U = sorted(set(sp) | set(ndx) | set(top100))
have = {f[:-4] for f in os.listdir(YS) if f.endswith(".pkl")}
need = [s for s in U if s not in have]
t1 = time.time()
with cf.ThreadPoolExecutor(6) as ex:
    res = list(ex.map(lambda s: yahoo(s, YS), need))
bad = [x for x in res if not isinstance(x[1], int)]
LOG["universe"] = {"union": len(U), "already": len(U) - len(need), "fetched": len(need) - len(bad), "bad": bad, "seconds": round(time.time() - t1)}
print("擴大範圍:", LOG["universe"], flush=True)

# ---------- 4. 部位:CFTC 期貨(ES、NQ;TFF 週報)、NAAIM 經理人持股 ----------
def cftc(code):
    f = ["open_interest_all", "dealer_positions_long_all", "dealer_positions_short_all", "asset_mgr_positions_long", "asset_mgr_positions_short",
         "lev_money_positions_long", "lev_money_positions_short"]
    u = "https://publicreporting.cftc.gov/resource/gpe5-46if.json?" + urllib.parse.urlencode({"$where": f"cftc_contract_market_code='{code}'",
        "$select": ",".join(["report_date_as_yyyy_mm_dd"] + f), "$order": "report_date_as_yyyy_mm_dd", "$limit": 50000})
    df = pd.DataFrame(json.loads(get(u, 120))); df["date"] = pd.to_datetime(df.pop("report_date_as_yyyy_mm_dd")).dt.normalize()
    for c in f: df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.groupby("date").sum().sort_index()
try:
    cot = {"ES": cftc("13874A"), "NQ": cftc("209742")}
    pd.to_pickle(cot, os.path.join(MAC, "cot.pkl")); LOG["cot"] = {k: [str(v.index[0].date()), str(v.index[-1].date()), len(v)] for k, v in cot.items()}
except Exception as e: LOG["cot"] = "ERR " + str(e)[:120]
try:
    html = get("https://naaim.org/programs/naaim-exposure-index/").decode("utf-8", "ignore")
    m = re.findall(r'href="([^"]+\.xlsx?)"', html)
    LOG["naaim_links"] = m[:3]
    if m:
        x = get(m[0] if m[0].startswith("http") else "https://naaim.org" + m[0], 120)
        open(os.path.join(MAC, "naaim.xlsx"), "wb").write(x)
        nd = pd.read_excel(os.path.join(MAC, "naaim.xlsx")); LOG["naaim"] = [list(map(str, nd.columns[:4])), len(nd)]
except Exception as e: LOG["naaim"] = "ERR " + str(e)[:120]
# ---------- 5. 期權:Cboe 認沽/認購比(歷史檔)、DIX/GEX ----------
for nm in ("totalpc", "equitypc", "indexpc"):
    try:
        b = get(f"https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/{nm}.csv", 120); open(os.path.join(MAC, nm + ".csv"), "wb").write(b)
        LOG[nm] = len(b)
    except Exception as e: LOG[nm] = "ERR " + str(e)[:80]
try:
    b = get("https://squeezemetrics.com/monitor/static/DIX.csv", 120); open(os.path.join(MAC, "DIX.csv"), "wb").write(b); LOG["dix"] = len(b)
except Exception as e: LOG["dix"] = "ERR " + str(e)[:80]
# ---------- 6. 通膨:BLS CPI(月)----------
try:
    out = []
    for a, b_ in ((2004, 2013), (2014, 2023), (2024, 2026)):
        body = json.dumps({"seriesid": ["CUSR0000SA0", "CUSR0000SA0L1E"], "startyear": str(a), "endyear": str(b_)}).encode()
        r = urllib.request.Request("https://api.bls.gov/publicAPI/v2/timeseries/data/", data=body, headers=dict(UA, **{"Content-Type": "application/json"}))
        d = json.loads(urllib.request.urlopen(r, timeout=60).read())
        for s in d["Results"]["series"]:
            for o in s["data"]:
                if o["period"].startswith("M") and o["period"] != "M13": out.append((s["seriesID"], int(o["year"]), int(o["period"][1:]), float(o["value"])))
    pd.DataFrame(out, columns=["sid", "y", "m", "v"]).to_csv(os.path.join(MAC, "cpi.csv"), index=False); LOG["cpi"] = len(out)
except Exception as e: LOG["cpi"] = "ERR " + str(e)[:120]
json.dump(LOG, open(os.path.join(MAC, "fetch_log.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: v for k, v in LOG.items() if k != "macro"}, ensure_ascii=False, default=str)[:3000]); print(f"完成 {time.time()-T0:.0f}s")
