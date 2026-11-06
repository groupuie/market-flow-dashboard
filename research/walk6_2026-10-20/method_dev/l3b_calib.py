#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk6 L3b:兩個主要假設那兩格(12 個月 ETF 擇時、12 個月個股挑股),用 200 條假分數(ρ = 0.92、0.95)校準錯開檢定的門檻
- 輸出每條假分數的 p(往上)/ p(往下),算出在各個門檻下的誤報率;選「誤報 ≤ 2.5%」最寬的門檻當正式判定門檻(跑真的分數之前)
用法:python3 -I l3b_calib.py SCEN.pkl L2_EVAL.py OUT.json"""
import json, sys
import numpy as np, pandas as pd
SC, L2, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(L2).read().split('R = {"control"')[0]
src = src.replace("SC, OUT = sys.argv[1], sys.argv[2]", "SC, OUT = None, None").replace('S = pd.read_pickle(SC); S["neg_r1m"] = -S.r1m', "S = None").replace('CTRL = sys.argv[sys.argv.index("--control") + 1] if "--control" in sys.argv else None', "CTRL = None")
ns = {}; exec(src, ns); mats, shift_test, ts_stat, cs_stat, START = ns["mats"], ns["shift_test"], ns["ts_stat"], ns["cs_stat"], ns["START"]
S = pd.read_pickle(SC); M = np.array(sorted(S.date.unique())); mi = {m: k for k, m in enumerate(M)}; syms = sorted(S.sym.unique()); si = {s: k for k, s in enumerate(syms)}
rI, cI = np.array([si[s] for s in S.sym]), np.array([mi[m] for m in S.date]); rng = np.random.default_rng(20261021)
V = S[S["f_m12"].notna() & (S.date >= START)]; E, K = V[V.etf], V[~V.etf]
out = {}
for rho in (0.92, 0.95):
    P = {"ETF 擇時": [], "個股挑股": []}
    for p in range(200):
        T = len(M); e = np.sqrt(0.5) * rng.standard_normal(T)[None, :] + np.sqrt(0.5) * rng.standard_normal((len(syms), T)); x = np.zeros_like(e); x[:, 0] = e[:, 0]
        for t in range(1, T):
            x[:, t] = rho * x[:, t - 1] + np.sqrt(1 - rho ** 2) * e[:, t]
        val = x[rI, cI]; Ev = pd.Series(val, index=S.index).loc[E.index].values; Kv = pd.Series(val, index=S.index).loc[K.index].values
        X, Y = mats(E.assign(plc=Ev), "plc", "f_m12"); r = shift_test(X, Y, ts_stat); P["ETF 擇時"].append([r["p(往上)"], r["p(往下)"]])
        X, Y = mats(K.assign(plc=Kv), "plc", "f_m12"); r = shift_test(X, Y, cs_stat); P["個股挑股"].append([r["p(往上)"], r["p(往下)"]])
        if (p + 1) % 20 == 0:
            print("rho", rho, p + 1, flush=True)
    o = {}
    for k, v in P.items():
        a = np.array(v); pmin = float(a.min())
        o[k] = {"p 最小可能值": pmin, **{f"p < {th}": [round(100 * float((a[:, 0] < th).mean()), 1), round(100 * float((a[:, 1] < th).mean()), 1)] for th in (0.025, 0.0167, 0.0112, 0.0075)},
                "p = 最小值(比全部錯開都高 / 都低)": [round(100 * float((a[:, 0] <= pmin + 1e-9).mean()), 1), round(100 * float((a[:, 1] <= pmin + 1e-9).mean()), 1)]}
    out[f"ρ={rho}"] = o
json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
