#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 W3:每個「某檔某天」最近 64 天的形狀(給相似線型比對 K1 與序列模型 N1)
P64[n, 64, 5]:t = i−63 … i;前 4 欄 = log(開 / 今收)、log(高 / 今收)、log(低 / 今收)、log(收 / 今收),都除以 atr(日均波動);第 5 欄 = log(量 / 最近 60 天均量)
只用決定日收盤(含)以前的資料。float16,存成 out/P64.npy(和 S7.pkl 同一個順序)
用法:python3 -I w3_paths.py OUT_DIR"""
import gzip, os, pickle, sys
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

OUT = sys.argv[1]; L = 64
S = pd.read_pickle(os.path.join(OUT, "out", "S7.pkl"))[["sym", "i", "a"]]
BARS = pickle.load(gzip.open(os.path.join(OUT, "data", "daily.pkl.gz")))["bars"]
P = np.lib.format.open_memmap(os.path.join(OUT, "out", "P64.npy"), mode="w+", dtype=np.float16, shape=(len(S), L, 5))
for s, g in S.groupby("sym", sort=False):
    x = BARS[s]["x"]; o, h, l, c, v = x[:, 0], x[:, 1], x[:, 2], x[:, 3], x[:, 5]
    idx = g.i.values; a = g.a.values.astype(np.float64)
    W = lambda arr: swv(arr, L)[idx - L + 1]          # 每一列:arr[i−63 … i]
    ci = c[idx][:, None]
    for k, arr in enumerate((o, h, l, c)):
        P[g.index.values, :, k] = np.clip(np.log(W(arr) / ci) / a[:, None], -60, 60).astype(np.float16)
    vm = swv(v, 60)[idx - 59].mean(axis=1)[:, None]
    P[g.index.values, :, 4] = np.clip(np.log(np.maximum(W(v), 1) / np.maximum(vm, 1)), -8, 8).astype(np.float16)
P.flush()
print("P64", P.shape, "非有限值", int((~np.isfinite(P[:5000].astype(np.float32))).sum()))
