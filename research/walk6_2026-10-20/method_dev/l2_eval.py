#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk6 L2:長線盤感的成績(規則 PROTOCOL_L.md,跑之前寫好)
- 不用學的規則(分數越高 = 越看好):順勢 12 個月 r12m、順勢 12-1 r12_1、站上 200 日線 vs200、靠近 52 週高 hi52、短線反轉 −r1m
- 個股另外有 M2(梯度提升回歸樹,逐年往前 2011–2025,答案 = h 期報酬 ÷(一年波動 × √(h/252)),截 ±5)
- ETF(23 檔)擇時:每一檔自己的「分數 vs 之後報酬」排序相關,再平均;個股:每個月橫向排序相關(挑股)取平均,以及每一檔自己的擇時
- 顯著性:**錯開檢定**。把所有標的的答案序列一起往後錯開 k 個月(k = 36 ~ T−36,繞回來接),每個 k 算一次同樣的統計量 = 「對不上時會長怎樣」;
  真的那一次要比全部錯開的 97.5% 還高(單邊 p < 0.025)才算有方向。這樣保留了分數和答案各自的自我相關(長期報酬重疊、動能很黏),
  區塊重抽在這裡會太樂觀(對照檢查時亂數答案也一直「顯著」)
- 評估期:決定日 2006-01 起(M2 只有 2011 起的測試年)
用法:python3 -I l2_eval.py SCEN.pkl OUT.json [--control neg|pos]"""
import json, math, sys
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

SC, OUT = sys.argv[1], sys.argv[2]
CTRL = sys.argv[sys.argv.index("--control") + 1] if "--control" in sys.argv else None
SEED, START, MINSHIFT = 20261020, "2006-01-01", 36
HZ = {"m1": 21, "m3": 63, "m6": 126, "m12": 252, "m24": 504}
BASE = {"順勢12個月": "r12m", "順勢12-1": "r12_1", "站上200日線": "vs200", "靠近52週高": "hi52", "短線反轉": "neg_r1m"}
FL = ["r1m", "r3m", "r6m", "r12m", "r24m", "r36m", "r12_1", "vs200", "vs50", "ma50_200", "sl200", "hi52", "lo52", "ath_dd", "vol3m", "vol12m", "volr", "mdd12m", "vr",
      "q_r12m", "q_r6m", "q_vs200", "q_vol3m", "q_hi52", "rs12m", "rs6m"]
S = pd.read_pickle(SC); S["neg_r1m"] = -S.r1m
rng0 = np.random.default_rng(SEED)
if CTRL == "neg":   # 每一檔自己的答案序列整段錯開(至少 36 個月):兩邊各自的自我相關都保留,但對不上
    for h in HZ:
        for s, g in S.groupby("sym"):
            ix = g.index.values; k = int(rng0.integers(36, max(37, len(ix) - 36))) if len(ix) > 80 else 0
            S.loc[ix, "f_" + h] = np.roll(g["f_" + h].values, k)
if CTRL == "pos":
    S["leak"] = S["f_m12"] + rng0.normal(0, 0.3, len(S)); BASE = {"偷看": "leak"}


def mats(g, score, tgt):
    M = np.array(sorted(g.date.unique())); mi = {m: k for k, m in enumerate(M)}; syms = sorted(g.sym.unique()); si = {s: k for k, s in enumerate(syms)}
    X = np.full((len(syms), len(M)), np.nan); Y = np.full((len(syms), len(M)), np.nan)
    r = [si[s] for s in g.sym]; c = [mi[m] for m in g.date]; X[r, c] = g[score].values; Y[r, c] = g[tgt].values
    return X, Y


def rowwise_ic(Xs, Ys, min_n):
    """每一列各自的 Spearman(平均名次、兩邊都有值的才算、少於 min_n 對不算),再平均"""
    m = np.isfinite(Xs) & np.isfinite(Ys); Xs = np.where(m, Xs, np.nan); Ys = np.where(m, Ys, np.nan)
    rx = pd.DataFrame(Xs).rank(axis=1).values; ry = pd.DataFrame(Ys).rank(axis=1).values
    dx = rx - np.nanmean(rx, 1, keepdims=True); dy = ry - np.nanmean(ry, 1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        ic = np.nansum(dx * dy, 1) / np.sqrt(np.nansum(dx * dx, 1) * np.nansum(dy * dy, 1))
    ic[m.sum(1) < min_n] = np.nan
    return float(np.nanmean(ic)) if np.isfinite(ic).any() else np.nan


def ts_stat(X, Y):
    return rowwise_ic(X, Y, 24)      # 擇時:每一檔跨月份


def cs_stat(X, Y):
    return rowwise_ic(X.T, Y.T, 30)  # 挑股:每個月跨標的


def shift_test(X, Y, stat):
    T = X.shape[1]; real = stat(X, Y)
    null = np.array([stat(X, np.roll(Y, k, axis=1)) for k in range(MINSHIFT, T - MINSHIFT + 1)]); null = null[np.isfinite(null)]
    hi = (1 + int((null >= real).sum())) / (1 + len(null)); lo = (1 + int((null <= real).sum())) / (1 + len(null))
    return {"IC": round(real, 4), "錯開後(2.5%–97.5%)": [round(float(np.percentile(null, 2.5)), 4), round(float(np.percentile(null, 97.5)), 4)], "錯開次數": len(null),
            "p(往上)": round(hi, 4), "p(往下)": round(lo, 4), "判定": "有方向(p < 0.025)" if hi < 0.025 else ("反向(p < 0.025)" if lo < 0.025 else "沒有證據")}


R = {"control": CTRL, "seed": SEED, "評估起": START, "最少錯開月數": MINSHIFT}
for h, hd in HZ.items():
    V = S[S["f_" + h].notna() & (S.date >= START)].copy(); V["ex"] = V["f_" + h] - V["qf_" + h]
    E, K = V[V.etf], V[~V.etf]; o = {"ETF 情境": len(E), "個股情境": len(K), "最後決定日": V.date.max()}
    for nm, sc in BASE.items():
        X, Y = mats(E, sc, "f_" + h); e = shift_test(X, Y, ts_stat)
        X, Y = mats(K, sc, "f_" + h); c = shift_test(X, Y, cs_stat); t = shift_test(X, Y, ts_stat)
        o[nm] = {"ETF 擇時": e, "個股挑股": c, "個股擇時": t}
        if sc in ("r12m", "leak"):
            pos, neg = E[E[sc] > 0], E[E[sc] <= 0]
            o[nm]["ETF:分數 > 0 vs ≤ 0 的平均報酬%(張數)"] = [round(100 * float(np.expm1(pos["f_" + h]).mean()), 2), len(pos), round(100 * float(np.expm1(neg["f_" + h]).mean()), 2), len(neg)]
        if sc in ("r12_1", "leak"):
            K2 = K.assign(q=K.groupby("date")[sc].transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=False) if x.notna().sum() >= 30 else np.nan))
            top, bot = K2[K2.q == 4], K2[K2.q == 0]
            o[nm]["個股:每月前 1/5 − 後 1/5 平均報酬%(相對 QQQ)"] = [round(100 * float(np.expm1(top["f_" + h]).mean() - np.expm1(bot["f_" + h]).mean()), 2),
                                                              round(100 * float(top.ex.mean() - bot.ex.mean()), 2)]
    if CTRL != "pos":   # 個股 M2(逐年往前)
        P = []
        Kall = S[~S.etf & S["f_" + h].notna()].copy(); Kall["y"] = (Kall["f_" + h] / (Kall.vol12m * math.sqrt(hd / 252))).clip(-5, 5)
        for Y_ in range(2011, 2026):
            tr = Kall[(Kall["end_" + h] < f"{Y_}-01-01") & (Kall.date >= "2001-01-01") & Kall.y.notna()]; te = Kall[Kall.date.str[:4] == str(Y_)]
            if te.empty or len(tr) < 2000:
                continue
            m = HistGradientBoostingRegressor(learning_rate=0.05, max_iter=200, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0, early_stopping=False,
                                              random_state=SEED).fit(tr[FL].values, tr.y.values)
            P.append(te.assign(m2=m.predict(te[FL].values)))
        if P:
            G = pd.concat(P); X, Y = mats(G, "m2", "f_" + h)
            o["M2(個股,2011 起)"] = {"個股挑股": shift_test(X, Y, cs_stat), "個股擇時": shift_test(X, Y, ts_stat)}
            X, Y = mats(G, "r12_1", "f_" + h); o["同一段(2011 起)順勢12-1"] = {"個股挑股": shift_test(X, Y, cs_stat), "個股擇時": shift_test(X, Y, ts_stat)}
    R[h] = o
    print(h, " | ".join(f"{nm}/{k2}:{v2['IC']}{'↑' if v2['判定'].startswith('有') else ('↓' if v2['判定'].startswith('反') else '')}"
                         for nm, v in o.items() if isinstance(v, dict) for k2, v2 in v.items() if isinstance(v2, dict) and "IC" in v2), flush=True)
json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1)
