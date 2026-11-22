#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk5-A:「會調整」的學法 — 每個月重學一次、越新的例子越重要,能不能抓到「往哪邊」(D20)?(規則 PROTOCOL_a.md,跑之前寫好)
- D20 和 walk5-D 一樣:20 個交易日內先碰 +3·atr = 1、先碰 −3·atr = 0;同一天都碰或都沒碰 → 排除
- A1(主要):每個月月初重學;訓練 = 2018-01-02 起、答案最後一天早於該月第一個交易日;權重 = 0.5 ^(距今年數 ÷ 1 年)
- A0(對照):每個月重學、不加權
- 期間:2021-01 ~ 2025-12(和 walk5-D 同一段,逐月);2026-01 ~ 2026-09(D20 答案到 2026-10-14 都揭曉的部分)= 沒用過的新資料
用法:python3 -I a5_adaptive.py SCEN.pkl BARS.json.gz OUT.json"""
import datetime as dt, gzip, json, math, sys
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

SC, BZ, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SEED, BOOT, N_CH, L = 20261019, 2000, 126, 20
FFULL = (["r1", "r2", "r3", "r5", "r10", "r20", "r40", "r60", "r120", "r250", "z5", "z20", "z60", "a", "atr5_20", "atr20_60", "rv20_a",
          "dma10", "dma20", "dma50", "dma100", "dma200", "sl20", "sl50", "sl200", "al20_50", "al50_200",
          "rw20", "rw60", "rw120", "rw250", "pos20", "pos60", "pos120", "pos250", "dsh60", "dsl60", "dsh250", "dsl250",
          "bo20", "bd20", "cs20", "bo60", "bd60", "cs60", "body", "cloc", "ush", "lsh", "rng_a", "gap", "streak", "rsi2", "rsi14",
          "vr1", "vr5", "vr20_60", "upv20"] + ["q_" + k for k in ("r1", "r5", "r20", "r60", "r120", "dma50", "dma200", "a", "atr5_20", "pos60", "streak", "rsi14")]
         + ["rs20", "rs60", "rs120"])
S = pd.read_pickle(SC); B = json.load(gzip.open(BZ))["bars"]
D20, E20 = np.full(len(S), np.nan), [None] * len(S)
for s, g in S.groupby("sym", sort=False):
    x = np.array([[float(b[k]) for k in range(1, 6)] for b in B[s]]).T; o, h, l, c, v = x; d = [b[0] for b in B[s]]
    for r, i, a in zip(g.index.values, g.i.values, g.a.values):
        lo, hi = i - N_CH + 1, i + 20
        if not np.isfinite(a) or a <= 0 or lo < 0 or hi >= len(c):
            continue
        vv, cc = v[lo:hi + 1], c[lo:hi + 1]
        if not ((vv > 0).all() and int((cc[1:] == cc[:-1]).sum()) <= 0.02 * len(cc)):
            continue
        C = c[i]; res = np.nan
        for j in range(1, 21):
            up, dn = h[i + j] >= C * (1 + 3 * a), l[i + j] <= C * (1 - 3 * a)
            if up and dn:
                break
            if up:
                res = 1.0; break
            if dn:
                res = 0.0; break
        D20[r] = res; E20[r] = d[i + 20]
S["D20"], S["e20"] = D20, E20
V = S[S.D20.notna() & (S.date >= "2018-01-02")].copy(); V["ym"] = V.date.str[:7]
DT = pd.to_datetime(V.date).values


def mdl():
    return HistGradientBoostingClassifier(learning_rate=0.05, max_iter=200, max_leaf_nodes=15, min_samples_leaf=1000, l2_regularization=1.0, early_stopping=False, random_state=SEED)


months = sorted(m for m in V.ym.unique() if "2021-01" <= m <= "2026-09")
pr = []
for m in months:
    te = V[V.ym == m]
    if te.empty:
        continue
    t0 = te.date.min(); trm = (V.e20 < t0).values; tr = V[trm]
    assert tr.e20.max() < t0 <= te.date.min() and tr.date.max() < t0   # 不偷看:訓練的答案都在這個月開始前揭曉
    age = (np.datetime64(t0) - DT[trm]).astype("timedelta64[D]").astype(float) / 365.25
    out = {"date": te.date.values, "sym": te.sym.values, "y": te.D20.values, "ym": m}
    out["A1"] = mdl().fit(tr[FFULL].values, tr.D20.values.astype(int), sample_weight=0.5 ** age).predict_proba(te[FFULL].values)[:, 1]
    out["A0"] = mdl().fit(tr[FFULL].values, tr.D20.values.astype(int)).predict_proba(te[FFULL].values)[:, 1]
    pr.append(pd.DataFrame(out)); print(m, len(tr), len(te), flush=True)
P = pd.concat(pr, ignore_index=True); P.to_pickle(OUT.replace(".json", "_preds.pkl"))


def wauc(y, p, w):
    o = np.argsort(p, kind="mergesort"); ps, yy, ww = p[o], y[o], w[o]
    gid = np.concatenate([[0], np.cumsum(ps[1:] != ps[:-1])]); ng = gid[-1] + 1
    P_ = np.bincount(gid, weights=ww * yy, minlength=ng); N_ = np.bincount(gid, weights=ww * (1 - yy), minlength=ng)
    return float((P_ * (np.cumsum(N_) - N_ + 0.5 * N_)).sum() / (P_.sum() * N_.sum()))


def ev(g, k):
    y, p = g.y.values, g[k].values; ud, di = np.unique(g.date.values, return_inverse=True); T = len(ud); rng = np.random.default_rng(SEED); bs = []
    for _ in range(BOOT):
        st = rng.integers(0, T, math.ceil(T / L)); cnt = np.bincount(((st[:, None] + np.arange(L)[None, :]) % T).ravel(), minlength=T); bs.append(wauc(y, p, cnt[di].astype(float)))
    ci = [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]; pt = wauc(y, p, np.ones(len(y)))
    dec = pd.qcut(g[k].rank(method="first"), 10, labels=False)
    return {"張數": len(g), "天數": T, "先往上%": round(100 * float(g.y.mean()), 1), "AUC": round(pt, 4), "95%": ci,
            "判定": "有方向訊號(下界 > 0.5)" if ci[0] > 0.5 else ("反向(上界 < 0.5)" if ci[1] < 0.5 else "沒有證據(區間含 0.5)"),
            "十分位 先往上%": [round(100 * float(g.y[dec == q].mean()), 1) for q in range(10)],
            "各年": {yr: round(wauc(h.y.values, h[k].values, np.ones(len(h))), 4) for yr, h in g.groupby(g.date.str[:4])}}


R = {"說明": "walk5-A(PROTOCOL_a.md);A1 = 每月重學 + 越新越重(半衰期 1 年),A0 = 每月重學不加權"}
for k in ("A1", "A0"):
    R[k] = {"2021–2025(主要)": ev(P[P.date < "2026-01-01"], k), "2026-01~09(新資料)": ev(P[P.date >= "2026-01-01"], k)}
    print(k, json.dumps({s: {kk: v for kk, v in o.items() if kk in ("AUC", "95%", "判定", "各年")} for s, o in R[k].items()}, ensure_ascii=False), flush=True)
json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1)
