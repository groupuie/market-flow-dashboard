#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""x5 的補充(事後、沒有預先登記):R8 5 天急跌,逐年拆開看(之後 10 天超額報酬 = 減同日全名單平均;中位數;為正比例;日期數)。
用法:python3 -I x5b_r8_years.py SCRATCH"""
import gzip, json, os, pickle, sys
import numpy as np, pandas as pd
ROOT = sys.argv[1]; W7 = os.path.join(ROOT, "w7"); OUT = os.path.join(ROOT, "em", "out")
S = pd.read_pickle(os.path.join(W7, "out", "S7.pkl"))[["sym", "date", "i", "a", "r5"]]
B = pickle.load(gzip.open(os.path.join(W7, "data", "daily.pkl.gz")))["bars"]
f = np.empty(len(S))
for s, g in S.groupby("sym", sort=False):
    c = B[s]["x"][:, 3]; I = g["i"].values; f[S.index.get_indexer(g.index)] = (c[I + 10] / c[I] - 1) * 100
S["f10"] = f; S["x10"] = S.f10 - S.groupby("date").f10.transform("mean")
S["r5s"] = np.expm1(S.r5)   # S7 的 r5 是對數報酬;網站用簡單報酬
out = {}
for nm, col in (("S7 r5(對數)", "r5"), ("網站算法(簡單報酬)", "r5s")):
    m = S[col] / (S.a * np.sqrt(5)) <= -2; g = S[m].copy(); g["y"] = g.date.str[:4]
    t = g.groupby("y").agg(n=("x10", "size"), 日期數=("date", "nunique"), 超額平均=("x10", "mean"), 超額中位=("x10", "median"), 報酬平均=("f10", "mean"), 為正比例=("f10", lambda v: (v > 0).mean() * 100)).round(2)
    out[nm] = {"全部": {"n": int(m.sum()), "日期數": int(g.date.nunique()), "超額平均": round(float(g.x10.mean()), 2), "超額中位": round(float(g.x10.median()), 2)},
               "逐年": t.reset_index().to_dict("records"),
               "最多的 5 天": g.groupby("date").size().sort_values(ascending=False).head(5).to_dict()}
print(json.dumps(out, ensure_ascii=False, indent=0))
json.dump(out, open(os.path.join(OUT, "x5b_r8_years.json"), "w"), ensure_ascii=False, indent=1)
