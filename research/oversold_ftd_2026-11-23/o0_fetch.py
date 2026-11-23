# 資料:個股日K(第 6 輪同一份 604 檔名單)、指數(含成交量)、VIX、HYG/IEF、Cboe 認沽認購比(舊檔 2006-11~2019-10 + 每日統計 2019-10 起)
# 資料放 /home/claude/work(不進 repo)
import json, os, sys, time, urllib.request, urllib.parse, concurrent.futures as cf
import pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0"}; MAC = "/home/claude/work/macro"; YM = MAC + "/yh"; YS = "/home/claude/work/t30/yh"; PCD = MAC + "/pcd"
for d in (YM, YS, PCD): os.makedirs(d, exist_ok=True)
def get(u, timeout=60): return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=timeout).read()
def yahoo(sym, out_dir):
    fn = os.path.join(out_dir, sym.replace("^", "_").replace("=", "_").replace("/", "-") + ".pkl")
    if os.path.exists(fn): return sym, "cached"
    err = ""
    for a in range(4):
        try:
            u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?period1=0&period2={int(time.time())}&interval=1d&events=div%2Csplit"
            r = json.loads(get(u))["chart"]["result"][0]; ts = r.get("timestamp") or []
            if not ts: return sym, "empty"
            q = r["indicators"]["quote"][0]; adj = (r["indicators"].get("adjclose") or [{}])[0].get("adjclose")
            tz = r["meta"].get("exchangeTimezoneName", "America/New_York")
            idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert(tz).tz_localize(None).normalize()
            df = pd.DataFrame({"o": q["open"], "h": q["high"], "l": q["low"], "c": q["close"], "v": q["volume"]}, index=idx, dtype="float64")
            df["ac"] = np.array(adj, dtype="float64") if adj else df["c"]
            df = df[~df.index.duplicated(keep="last")].dropna(subset=["c"]); df.to_pickle(fn); return sym, len(df)
        except Exception as e: err = str(e)[:80]; time.sleep(2 + 3 * a)
    return sym, "ERR " + err
L = json.load(open(os.path.join(HERE, "..", "expectancy_2026-10-14", "x3_r6_overlap.json")))["r6_executed_list"]
MACRO = ["^VIX", "^VIX3M", "^GSPC", "^IXIC", "^NDX", "^DJI", "HYG", "IEF", "SPY", "QQQ"]
with cf.ThreadPoolExecutor(6) as ex:
    r1 = list(ex.map(lambda s: yahoo(s, YM), MACRO)); r2 = list(ex.map(lambda s: yahoo(s, YS), L))
print("macro", r1); bad = [x for x in r2 if not (isinstance(x[1], int) or x[1] == "cached")]; print("stocks", len(r2), "bad", bad, flush=True)
# Cboe 每日統計
days = [d for d in pd.read_pickle(YM + "/_GSPC.pkl").index if d >= pd.Timestamp("2019-10-07")]
def pc(d):
    fn = os.path.join(PCD, d.strftime("%Y-%m-%d") + ".json")
    if os.path.exists(fn): return 1
    for a in range(3):
        try:
            b = get(f"https://cdn.cboe.com/data/us/options/market_statistics/daily/{d.strftime('%Y-%m-%d')}_daily_options", 30)
            j = json.loads(b); open(fn, "w").write(json.dumps({x["name"]: x["value"] for x in j["ratios"]})); return 1
        except Exception as e:
            if "404" in str(e) or "403" in str(e): return 0
            time.sleep(1 + 2 * a)
    return 0
with cf.ThreadPoolExecutor(8) as ex: ok = list(ex.map(pc, days))
print("pc daily", sum(ok), "/", len(days), "缺", [str(d.date()) for d, o in zip(days, ok) if not o][:30])
