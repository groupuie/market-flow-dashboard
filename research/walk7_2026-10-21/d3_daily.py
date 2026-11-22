#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 D3:候選股的日 K(2014-06 起,截到 LAST;還原權值的開高低收 + 只還原分割的收盤(算成交金額)+ 成交量)
候選 = 每年 1 月 S&P 500 成分股(2016–2026 全部)∪ 月 K 掃描裡任一年成交金額前 250 的個股 ∪ SPY、QQQ
用法:python3 d3_daily.py OUT_DIR   → OUT_DIR/data/daily.pkl.gz、data/daily_manifest.json"""
import concurrent.futures as cf, datetime as dt, gzip, hashlib, json, os, pickle, sys, time, urllib.parse, urllib.error
from zoneinfo import ZoneInfo
import numpy as np
sys.path.insert(0, "/home/claude/market-flow-dashboard/scripts")
import astra_data as AD

OUT = sys.argv[1]; LAST = "2026-10-20"
SP = json.load(open(os.path.join(OUT, "data", "sp500_jan1.json")))
M = json.load(gzip.open(os.path.join(OUT, "data", "monthly.json.gz")))
mon, typ = M["m"], M["type"]
cand = {"SPY": "市場", "QQQ": "市場"}
# 舊代號(改名)→ 用同一個 CIK 最新一年的代號去抓(例:ANTM → ELV、ABC → COR、BLL → BALL)
cik_last = {}
for Y in sorted(SP, key=int):
    for m in SP[Y]:
        if m.get("cik"):
            cik_last[m["cik"]] = m["sym"]
ymap = {}
for Y, mem in SP.items():
    for m in mem:
        ymap[m["sym"]] = cik_last.get(m.get("cik"), m["sym"]) if m.get("cik") else m["sym"]
        cand.setdefault(ymap[m["sym"]], "S&P 500")
top_any = {}
for Y in range(2015, 2027):
    dv = []
    for s, rows in mon.items():
        if typ.get(s) not in (None, "EQUITY"):
            continue
        v = sum((c or 0) * (q or 0) for d, c, q in rows if d.startswith(str(Y)))
        if v > 0:
            dv.append((v, s))
    dv.sort(reverse=True)
    for r, (v, s) in enumerate(dv[:250]):
        cand.setdefault(s, "成交金額"); top_any[s] = min(top_any.get(s, 999), r + 1)
syms = sorted(cand)
print("候選", len(syms), "(S&P 500 名單", sum(1 for s in cand.values() if s == "S&P 500"), "、成交金額", sum(1 for s in cand.values() if s == "成交金額"), ")", flush=True)
p1 = int(dt.datetime(2014, 6, 1, tzinfo=dt.timezone.utc).timestamp()); p2 = int(time.time()) + 86400


def job(s):
    q = f"?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit&includeAdjustedClose=true"
    for k in range(4):
        try:
            raw = AD.http_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(s)}{q}", 40, 1, AD.YH_H)
            r = json.loads(raw)["chart"]["result"][0]; ts = r.get("timestamp") or []
            if not ts:
                return s, None, "空的"
            qd = r["indicators"]["quote"][0]; adj = ((r["indicators"].get("adjclose") or [{}])[0]).get("adjclose")
            tz = ZoneInfo(r["meta"].get("exchangeTimezoneName") or "America/New_York"); rows = {}
            for i, t in enumerate(ts):
                c = qd["close"][i]
                if c is None or not (c > 0):
                    continue
                ac = adj[i] if (adj and i < len(adj) and adj[i] is not None) else c; f = ac / c
                o, h, l = (qd[k_][i] for k_ in ("open", "high", "low"))
                o = o * f if (o and o > 0) else ac; h = h * f if (h and h > 0) else ac; l = l * f if (l and l > 0) else ac
                d = dt.datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d")
                if d <= LAST:
                    rows[d] = (o, max(h, o, ac), min(l, o, ac), ac, c, float(qd["volume"][i] or 0))
            ds = sorted(rows)
            return s, {"d": ds, "x": np.array([rows[d] for d in ds], dtype=np.float64), "type": r["meta"].get("instrumentType"),
                       "name": r["meta"].get("longName") or r["meta"].get("shortName") or ""}, None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return s, None, "404"
            time.sleep(5 * (k + 1))
        except Exception as e:
            time.sleep(3 * (k + 1))
    return s, None, "失敗"


t0 = time.time(); B, F = {}, {}
with cf.ThreadPoolExecutor(6) as ex:
    for n, (s, b, err) in enumerate(ex.map(job, syms)):
        if err or b is None or len(b["d"]) < 30:
            F[s] = err or "太短"
        else:
            B[s] = b
        if (n + 1) % 200 == 0:
            print(n + 1, "/", len(syms), "失敗", len(F), round(time.time() - t0), "秒", flush=True)
raw = pickle.dumps({"bars": B, "cand": cand, "top_any": top_any, "ymap": ymap, "last": LAST}, protocol=4)
with gzip.open(os.path.join(OUT, "data", "daily.pkl.gz"), "wb") as fh:
    fh.write(raw)
man = {"fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "sha256_pickle": hashlib.sha256(raw).hexdigest(), "n": len(B), "fail": F, "last": LAST,
       "欄位": "d = 日期;x = [還原開, 還原高, 還原低, 還原收, 只還原分割的收盤, 成交量]"}
json.dump(man, open(os.path.join(OUT, "data", "daily_manifest.json"), "w"), ensure_ascii=False, indent=1)
print("完成", len(B), "失敗", len(F), round(time.time() - t0), "秒")
