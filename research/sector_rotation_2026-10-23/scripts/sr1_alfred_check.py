#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SR1 利率資料修訂的事後檢查(回應 Codex R8 §6):ALFRED 歷史版本 vs SR1 用的現行版(2026-10-23 抓)。
每兩年 1 月 15 日一個版本(ALFRED 最早約 1996 年才有);比較同一月份的數值,並把 E11 景氣狀態用舊版數值重算,數有幾個決定月改變。
用法:python3 -I sr1_alfred_check.py SCRATCH   (SCRATCH/alfred/raw/{代號}_{版本日}.csv;SCRATCH/sr/raw/fred_{代號}.csv)
下載:https://alfred.stlouisfed.org/graph/alfredgraph.csv?id={代號}&vintage_date={版本日}(1998-01-15 起每兩年;1996 以前 404)
輸出:SCRATCH/sr/out/sr1_alfred_check.json"""
import os, sys, json, glob, hashlib
import numpy as np, pandas as pd
S = sys.argv[1]; SIDS = ("GS10", "TB3MS", "BAA", "AAA")
EV0, EV1 = pd.Period("1974-12", "M"), pd.Period("2026-05", "M")      # 評分期的決定月


def load_csv(fn):
    d = pd.read_csv(fn); d.columns = ["date", "v"]; d["v"] = pd.to_numeric(d["v"], errors="coerce")
    return pd.Series(d["v"].values, index=pd.PeriodIndex(pd.to_datetime(d["date"]), freq="M")).dropna()


cur = {s: load_csv(os.path.join(S, "sr", "raw", f"fred_{s}.csv")) for s in SIDS}


def regimes(M):
    """同 sr1_run.py 的 regime_sets():決定月 t 用 t−1 的月平均"""
    S_ = M["GS10"] - M["TB3MS"]; C_ = M["BAA"] - M["AAA"]
    S1, C1 = S_.shift(1), C_.shift(1); dS, dC = S1 - S1.shift(6), C1 - C1.shift(6)
    out = {}
    for t in S1.index:
        s, ds, dc = S1.get(t), dS.get(t), dC.get(t)
        if any(pd.isna(x) for x in (s, ds, dc)):
            continue
        out[t] = "放緩" if (s < 0.5 or dc > 0.5) else "初升" if (s >= 1.5 and ds > 0 and dc <= 0) else "末升" if ds < 0 else "中段"
    return out


Mc = pd.DataFrame(cur); reg_c = regimes(Mc)
vint = sorted({os.path.basename(f).split("_")[1][:-4] for f in glob.glob(os.path.join(S, "alfred", "raw", "*_*.csv"))})
res = {"現行版": "SR1 用的 FRED 檔(2026-10-23 抓)", "版本數": len(vint), "每個版本": {}, "全部版本合計": {}}
allcells = {s: set() for s in SIDS}; maxd = {s: 0.0 for s in SIDS}
for vd in vint:
    row = {}; Mv = Mc.copy(); last = None; ok = True
    for s in SIDS:
        fn = os.path.join(S, "alfred", "raw", f"{s}_{vd}.csv")
        if not os.path.exists(fn):
            ok = False; break
        v = load_csv(fn); idx = v.index.intersection(cur[s].index)
        d = (v[idx] - cur[s][idx]).abs(); bad = d[d > 1e-9]
        row[s] = {"共同月數": int(len(idx)), "不同的月數": int(len(bad)), "最大差": round(float(d.max()), 4) if len(d) else None,
                  "不同的月份(前 5)": [f"{p}:{v[p]:.2f}→{cur[s][p]:.2f}" for p in bad.index[:5]]}
        allcells[s] |= set(bad.index); maxd[s] = max(maxd[s], float(d.max()) if len(d) else 0.0)
        Mv.loc[idx, s] = v[idx].values; last = idx.max() if last is None else min(last, idx.max())
    if not ok:
        continue
    reg_v = regimes(Mv)
    ts = [t for t in reg_c if EV0 <= t <= EV1 and t - 1 <= last]
    flips = [str(t) for t in ts if reg_v.get(t) != reg_c[t]]
    row["E11 決定月(用這個版本涵蓋的月份)"] = len(ts); row["E11 狀態改變的決定月"] = flips[:10]; row["E11 改變月數"] = len(flips)
    res["每個版本"][vd] = row
res["全部版本合計"] = {s: {"曾經和現行版不同的月份數": len(allcells[s]), "最大差": round(maxd[s], 4)} for s in SIDS}
man = sorted(glob.glob(os.path.join(S, "alfred", "raw", "*_*.csv")))
res["原檔指紋(前 16 碼)"] = {os.path.basename(f): hashlib.sha256(open(f, "rb").read()).hexdigest()[:16] for f in man}
json.dump(res, open(os.path.join(S, "sr", "out", "sr1_alfred_check.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "原檔指紋(前 16 碼)"}, ensure_ascii=False, indent=1)[:6000])
