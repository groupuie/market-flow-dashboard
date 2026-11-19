#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 補算:POST(2026-07~09,58 天)電腦方法的同一天內 AUC —— 原本登記的「月區塊重抽」只有 3 個月,不可靠,改以「天」重抽(2,000 次)
用法:python3 -I x3_post_cpu.py OUT_DIR → out/x3_post_cpu.json"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from w5_stats import date_stats  # noqa: E402
OUT = sys.argv[1]; S = pd.read_pickle(os.path.join(OUT, "out", "S7.pkl"))[["date", "buy", "sell", "d20"]]
S["y_buy"] = (S.buy == 1).astype(int); S["y_sell"] = (S.sell == 1).astype(int); S["y_dir"] = S.d20; R = {}
for m in ("M1", "M2", "K1", "N1"):
    P = pd.read_pickle(os.path.join(OUT, "out", f"pred_{m}_real.pkl")); P = P[S.loc[P.index, "date"].values >= "2026-07-01"]; R[m] = {}
    for t, c in (("y_buy", "p_buy"), ("y_sell", "p_sell"), ("y_dir", "p_dir")):
        y = S.loc[P.index, t].values.astype(float); ok = ~np.isnan(y); g = date_stats(P[c].values[ok], y[ok].astype(int), S.loc[P.index, "date"].values[ok])
        U, W = g.U.values, g.w.values; rng = np.random.default_rng(9); bs = []
        for _ in range(2000):
            k = rng.integers(0, len(g), len(g)); bs.append(U[k].sum() / W[k].sum())
        R[m][t] = {"n": int(ok.sum()), "同一天內 AUC": round(float(U.sum() / W.sum()), 4), "95%(以天重抽)": [round(float(np.quantile(bs, 0.025)), 4), round(float(np.quantile(bs, 0.975)), 4)], "天數": int(len(g)),
                   "AUC > 0.5 的天數": int((g.U / g.w > 0.5).sum())}
json.dump(R, open(os.path.join(OUT, "out", "x3_post_cpu.json"), "w"), ensure_ascii=False, indent=1)
for m, v in R.items():
    print(m, {t: (x["同一天內 AUC"], x["95%(以天重抽)"], f'{x["AUC > 0.5 的天數"]}/{x["天數"]}') for t, x in v.items()})
