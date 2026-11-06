#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk6 L0:長歷史日K(同 walk4 的 127 檔;2000-01-01 起,截到 2026-10-16;還原權值,Yahoo)
用法:python3 l0_data.py WALK4_BARS.json.gz OUT_DIR"""
import concurrent.futures as cf, datetime as dt, gzip, hashlib, json, os, sys, time
sys.path.insert(0, "/home/claude/market-flow-dashboard/scripts")
import astra_data as AD
W4, OUT = sys.argv[1], sys.argv[2]
syms = sorted(json.load(gzip.open(W4))["bars"])
ETF = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC", "SMH", "SOXX", "GLD", "SLV", "USO", "TLT", "HYG", "UUP"]
p1 = int(dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc).timestamp()); now = int(time.time()); LAST = "2026-10-16"
def job(s):
    for k in range(3):
        try:
            return s, AD.yahoo(s, p1, now + 86400), None
        except Exception as e:
            err = str(e)[:100]; time.sleep(3)
    return s, None, err
B, F = {}, {}
with cf.ThreadPoolExecutor(6) as ex:
    for s, b, err in ex.map(job, syms):
        if err or not b:
            F[s] = err or "沒有資料"
        else:
            B[s] = [[x[0], x[1], x[2], x[3], x[4], x[5]] for x in b if x[0] <= LAST]
raw = json.dumps({"bars": B, "etf": [s for s in ETF if s in B]}, separators=(",", ":")).encode()
with gzip.open(os.path.join(OUT, "data", "bars_long.json.gz"), "wb") as fh:
    fh.write(raw)
man = {"fetched_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sha256_json": hashlib.sha256(raw).hexdigest(), "n": len(B), "fail": F, "last": LAST,
       "first": {s: B[s][0][0] for s in B}, "n_bars": {s: len(B[s]) for s in B}}
json.dump(man, open(os.path.join(OUT, "data", "manifest.json"), "w"), ensure_ascii=False, indent=1)
print("symbols", len(B), "fail", F)
print("ETF first:", {s: B[s][0][0] for s in ETF if s in B})
print("first before 2006:", sum(1 for s in B if B[s][0][0] < "2006-01-01"), "last:", {s: B[s][-1][0] for s in ("SPY", "NVDA")})
