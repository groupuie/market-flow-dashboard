#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 D1:全部上市個股的月 K(2014 起;只留未還原收盤 × 成交量,用來找每年成交金額大的候選)
用法:python3 d1_monthly.py OUT_DIR [N]   (讀 OUT_DIR/raw/nasdaq_screener.json;寫 OUT_DIR/data/monthly.json.gz)"""
import concurrent.futures as cf, datetime as dt, gzip, json, os, re, sys, time, urllib.parse, urllib.error
sys.path.insert(0, "/home/claude/market-flow-dashboard/scripts")
import astra_data as AD

OUT = sys.argv[1]; NMAX = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9
rows = json.load(open(os.path.join(OUT, "raw", "nasdaq_screener.json")))["data"]["rows"]
BAD = re.compile(r"warrant|\bunits?\b|\brights?\b|preferred|% |notes due|debenture|subordinated|perpetual|trust preferred", re.I)


def num(x):
    try:
        return float(str(x).replace("$", "").replace(",", ""))
    except Exception:
        return float("nan")


syms = []
for r in rows:
    s = AD.ysym(r["symbol"]); mc = num(r.get("marketCap"))
    if not AD.SYM_RE.fullmatch(s) or BAD.search(r.get("name", "")):
        continue
    if mc == mc and mc >= 5e7:
        syms.append(s)
syms = sorted(set(syms))[:NMAX]
p1 = int(dt.datetime(2014, 1, 1, tzinfo=dt.timezone.utc).timestamp()); p2 = int(time.time()) + 86400


def job(s):
    q = f"?period1={p1}&period2={p2}&interval=1mo"
    for k in range(4):
        try:
            raw = AD.http_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}{q}", 30, 1, AD.YH_H)
            r = json.loads(raw)["chart"]["result"][0]; ts = r.get("timestamp") or []; qd = r["indicators"]["quote"][0]
            out = [[dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m"), qd["close"][i], qd["volume"][i]] for i, t in enumerate(ts)
                   if qd["close"][i] is not None and qd["volume"][i] is not None]
            return s, out, r["meta"].get("instrumentType"), None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return s, None, None, "404"
            time.sleep(5 * (k + 1))
        except Exception as e:
            err = str(e)[:80]; time.sleep(3 * (k + 1))
    return s, None, None, "fail"


t0 = time.time(); M, TY, F = {}, {}, {}
with cf.ThreadPoolExecutor(6) as ex:
    for n, (s, out, ty, err) in enumerate(ex.map(job, syms)):
        if err:
            F[s] = err
        else:
            M[s] = out; TY[s] = ty
        if (n + 1) % 250 == 0:
            print(n + 1, "/", len(syms), "失敗", len(F), round(time.time() - t0), "秒", flush=True)
os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
with gzip.open(os.path.join(OUT, "data", "monthly.json.gz"), "wt") as fh:
    json.dump({"m": M, "type": TY, "fail": F, "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat()}, fh)
print("完成", len(M), "失敗", len(F), round(time.time() - t0), "秒")
