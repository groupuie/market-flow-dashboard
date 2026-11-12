#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk6 L3:錯開檢定準不準?用「沒有任何資訊的假分數」測(跑真正的分數之前)
- 假分數 = 每一檔一條 AR(1) 亂數序列(月),ρ = 0(像短線反轉那種不黏的分數)或 0.92(像 12 個月動能那麼黏),
  一半是大家共同的、一半是各自的;和真的答案(之後報酬)完全無關
- 每種 40 條假分數 × 5 個期間 × 3 種比法(ETF 擇時、個股挑股、個股擇時),用 l2_eval.py 一模一樣的錯開檢定
- 準的話:「有方向」和「反向」各應該約 2.5%
用法:python3 -I l3_placebo.py SCEN.pkl L2_EVAL.py OUT.json"""
import json, sys
import numpy as np, pandas as pd

SC, L2, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
src = open(L2).read().split('R = {"control"')[0]
src = src.replace("SC, OUT = sys.argv[1], sys.argv[2]", "SC, OUT = None, None").replace('S = pd.read_pickle(SC); S["neg_r1m"] = -S.r1m', "S = None").replace('CTRL = sys.argv[sys.argv.index("--control") + 1] if "--control" in sys.argv else None', "CTRL = None")
ns = {}; exec(src, ns)
mats, shift_test, ts_stat, cs_stat, START, HZ = ns["mats"], ns["shift_test"], ns["ts_stat"], ns["cs_stat"], ns["START"], ns["HZ"]
S = pd.read_pickle(SC)
M = np.array(sorted(S.date.unique())); mi = {m: k for k, m in enumerate(M)}; syms = sorted(S.sym.unique()); si = {s: k for k, s in enumerate(syms)}
rI, cI = np.array([si[s] for s in S.sym]), np.array([mi[m] for m in S.date])
rng = np.random.default_rng(20261020)
NP = 40; res = {}
for rho in (0.0, 0.92):
    cnt = {}
    for p in range(NP):
        T = len(M); com = rng.standard_normal(T); idi = rng.standard_normal((len(syms), T)); e = np.sqrt(0.5) * com[None, :] + np.sqrt(0.5) * idi
        x = np.zeros_like(e); x[:, 0] = e[:, 0]
        for t in range(1, T):
            x[:, t] = rho * x[:, t - 1] + np.sqrt(1 - rho ** 2) * e[:, t]
        S["plc"] = x[rI, cI]
        for h in HZ:
            V = S[S["f_" + h].notna() & (S.date >= START)]; E, K = V[V.etf], V[~V.etf]
            for nm, (g, stat) in {"ETF 擇時": (E, ts_stat), "個股挑股": (K, cs_stat), "個股擇時": (K, ts_stat)}.items():
                X, Y = mats(g, "plc", "f_" + h); r = shift_test(X, Y, stat)
                c = cnt.setdefault(f"{h}/{nm}", [0, 0, 0]); c[0] += 1; c[1] += r["判定"].startswith("有"); c[2] += r["判定"].startswith("反")
        print("rho", rho, "placebo", p + 1, flush=True)
    res[f"ρ={rho}"] = {k: {"次數": v[0], "誤報「有方向」%": round(100 * v[1] / v[0], 1), "誤報「反向」%": round(100 * v[2] / v[0], 1)} for k, v in cnt.items()}
    tot = np.array(list(cnt.values())); res[f"ρ={rho}"]["全部"] = {"次數": int(tot[:, 0].sum()), "誤報「有方向」%": round(100 * tot[:, 1].sum() / tot[:, 0].sum(), 1), "誤報「反向」%": round(100 * tot[:, 2].sum() / tot[:, 0].sum(), 1)}
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1); print(json.dumps(res, ensure_ascii=False, indent=1))
