#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk8 G1:價格 + 財報 / 消息 / 資金流 的梯度提升(逐年往前;參數和 walk7 的 M2 完全一樣)
模型:M2 = walk7 的價格特徵(82 個);M2E = + 財報;M2N = + 消息(8-K);M2F = + 資金流(內部人、空單量);M2A = 全部加;A0 = 只有財報 + 消息 + 資金流(沒有價格特徵)
目標:y_buy(買方先漲一段)、y_sell(賣方先跌一段)、y_dir(上下對稱 ±2 個波動先碰哪邊)
測試年 2019–2026;訓練只用「答案在測試年 1 月 1 日之前就結束」的日子;HistGradientBoosting:lr 0.05、200 輪、15 葉、每葉 ≥ 1000、L2 1、不提早停、seed 20261021
訓練期整欄缺值的特徵在那一折不用(只會發生在 2018 年以前的空單量)
不用 f_ox5(場外量 ÷ Yahoo 量;Yahoo 的量會用「之後的分割」回頭調整,水準值可能藏未來資訊),只用它的 z 值 f_oxz
用法:python3 -I g1_models.py OUT_DIR W7_DIR [--dev]   (--dev:只跑「訓練 ≤ 2017、測試 2018」檢查程式)"""
import os, sys, time
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

OUT, W7 = sys.argv[1], sys.argv[2]; DEV = "--dev" in sys.argv; SEED = 20261021
S = pd.read_pickle(os.path.join(W7, "out", "S7.pkl")); X = pd.read_pickle(os.path.join(OUT, "out", "X8.pkl"))
assert (X.index == S.index).all()
S["y_buy"] = (S.buy == 1).astype(np.int8); S["y_sell"] = (S.sell == 1).astype(np.int8); S["y_dir"] = S.d20
NOT = {"sym", "date", "year", "i", "in_sp", "dv_rank", "end20", "buy", "sell", "buy_day", "sell_day", "d20", "d20_day", "r20", "r60", "y_buy", "y_sell", "y_dir"}
FALL = [k for k in S.columns if k not in NOT]
E = [k for k in X.columns if k.startswith("e_")]; N = [k for k in X.columns if k.startswith("n_")]; F = [k for k in X.columns if k.startswith("f_") and k != "f_ox5"]
D = pd.concat([S[FALL + ["y_buy", "y_sell", "y_dir", "year", "end20", "date"]], X[E + N + F]], axis=1)
MODELS = {"M2": FALL, "M2E": FALL + E, "M2N": FALL + N, "M2F": FALL + F, "M2A": FALL + E + N + F, "A0": E + N + F}
TGT = ["y_buy", "y_sell", "y_dir"]
folds = [(2018, "2018-01-01")] if DEV else [(y, f"{y}-01-01") for y in range(2019, 2027)]
print("特徵數", {m: len(c) for m, c in MODELS.items()}, flush=True)


def hgb():
    return HistGradientBoostingClassifier(learning_rate=0.05, max_iter=200, max_leaf_nodes=15, min_samples_leaf=1000, l2_regularization=1.0, early_stopping=False, random_state=SEED)


preds = {m: [] for m in MODELS}
for ty, t0 in folds:
    tic = time.time(); tr = D.index[D.end20 < t0].values; te = D.index[D.year == ty].values
    has = D.loc[tr].notna().any()   # 訓練期整欄都是缺值的特徵(例如 2018 年以前的空單量)這一折先不用
    for m, cols0 in MODELS.items():
        cols = [c for c in cols0 if has[c]]; out = pd.DataFrame(index=te)
        for t in TGT:
            ok = tr[~np.isnan(D[t].values[tr].astype(float))]
            mdl = hgb().fit(D.loc[ok, cols].values, D.loc[ok, t].values.astype(int)); out["p_" + t[2:]] = mdl.predict_proba(D.loc[te, cols].values)[:, 1]
        preds[m].append(out.assign(year=ty))
    print(ty, "訓練", len(tr), "測試", len(te), round(time.time() - tic), "秒", flush=True)
    if DEV:
        sys.path.insert(0, W7); from w5_stats import wd_auc  # noqa: E402
        for m, L in preds.items():
            o = L[-1]; y = D.loc[o.index]
            print("  dev", m, {t: round(wd_auc(o["p_" + t[2:]].values[y[t].notna().values], y[t].dropna().values.astype(int), y.date.values[y[t].notna().values]), 4) for t in TGT}, flush=True)
tag = "dev" if DEV else "real"
for m, L in preds.items():
    pd.concat(L).astype("float32").to_pickle(os.path.join(OUT, "out", f"pred8_{m}_{tag}.pkl"))
print("完成", tag)
