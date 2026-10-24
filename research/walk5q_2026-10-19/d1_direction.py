#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk5-D:圖裡有沒有「往哪邊」的資訊(拿掉「會不會動」之後)— 規則見 PROTOCOL_d.md(跑之前寫好)
目標(都只用決定日收盤以前的特徵;特徵和 walk5-Q 的 M2 完全一樣,模型參數也一樣):
  D20(主要):20 個交易日內,先碰到 C×(1+3·atr) = 1、先碰到 C×(1−3·atr) = 0(上下對稱);同一天兩邊都碰到、或 20 天都沒碰到 → 不算(排除)
  D10:10 個交易日內、上下各 2·atr,同上
  R20 / R60:20 / 60 個交易日後的報酬 ÷(atr·√天數)
驗證:逐年往前 2021–2025(訓練 = 2018-01-02 起、答案最後一天 < Y 年 1 月 1 日)
用法:python3 -I d1_direction.py SCEN.pkl BARS.json.gz OUT.json [--control neg|pos]"""
import gzip, json, math, sys
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

SC, BZ, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
CTRL = sys.argv[sys.argv.index("--control") + 1] if "--control" in sys.argv else None   # neg:答案換亂數;pos:偷放未來 3 天報酬當特徵
SEED, BOOT, N_CH = 20261019, 2000, 126
FFULL = (["r1", "r2", "r3", "r5", "r10", "r20", "r40", "r60", "r120", "r250", "z5", "z20", "z60", "a", "atr5_20", "atr20_60", "rv20_a",
          "dma10", "dma20", "dma50", "dma100", "dma200", "sl20", "sl50", "sl200", "al20_50", "al50_200",
          "rw20", "rw60", "rw120", "rw250", "pos20", "pos60", "pos120", "pos250", "dsh60", "dsl60", "dsh250", "dsl250",
          "bo20", "bd20", "cs20", "bo60", "bd60", "cs60", "body", "cloc", "ush", "lsh", "rng_a", "gap", "streak", "rsi2", "rsi14",
          "vr1", "vr5", "vr20_60", "upv20"] + ["q_" + k for k in ("r1", "r5", "r20", "r60", "r120", "dma50", "dma200", "a", "atr5_20", "pos60", "streak", "rsi14")]
         + ["rs20", "rs60", "rs120"])
S = pd.read_pickle(SC); B = json.load(gzip.open(BZ))["bars"]


def liquid(c, v, i, H):
    lo, hi = i - N_CH + 1, i + H
    if lo < 0 or hi >= len(c):
        return False
    vv, cc = v[lo:hi + 1], c[lo:hi + 1]
    return bool((vv > 0).all()) and int((cc[1:] == cc[:-1]).sum()) <= 0.02 * len(cc)


def first_hit(h, l, C, i, k, H):
    for j in range(1, H + 1):
        up, dn = h[i + j] >= C * (1 + k), l[i + j] <= C * (1 - k)
        if up and dn:
            return np.nan
        if up:
            return 1.0
        if dn:
            return 0.0
    return np.nan


cols = {k: np.full(len(S), np.nan) for k in ("D10", "D20", "R20", "R60")}; ends = {k: [None] * len(S) for k in (10, 20, 60)}
pos = 0
for s, g in S.groupby("sym", sort=False):
    x = np.array([[float(b[k]) for k in range(1, 6)] for b in B[s]]).T; o, h, l, c, v = x; d = [b[0] for b in B[s]]
    for r, i, a in zip(g.index.values, g.i.values, g.a.values):
        if not np.isfinite(a) or a <= 0:
            continue
        C = c[i]
        if liquid(c, v, i, 10):
            cols["D10"][r] = first_hit(h, l, C, i, 2 * a, 10); ends[10][r] = d[i + 10]
        if liquid(c, v, i, 20):
            cols["D20"][r] = first_hit(h, l, C, i, 3 * a, 20); cols["R20"][r] = math.log(c[i + 20] / C) / (a * math.sqrt(20)); ends[20][r] = d[i + 20]
        if liquid(c, v, i, 60):
            cols["R60"][r] = math.log(c[i + 60] / C) / (a * math.sqrt(60)); ends[60][r] = d[i + 60]
for k, v_ in cols.items():
    S[k] = v_
for k, v_ in ends.items():
    S[f"e{k}"] = v_
if CTRL == "neg":
    rng0 = np.random.default_rng(SEED)
    for k in ("D10", "D20"):
        m = S[k].notna(); S.loc[m, k] = (rng0.random(int(m.sum())) < float(S.loc[m, k].mean())).astype(float)
    for k in ("R20", "R60"):
        m = S[k].notna(); S.loc[m, k] = rng0.standard_normal(int(m.sum()))
if CTRL == "pos":
    S["leak"] = S.groupby("sym")["r3"].shift(-3); FFULL = FFULL + ["leak"]
HZ = {"D20": 20, "D10": 10, "R20": 20, "R60": 60}; LBLK = {"D20": 20, "D10": 20, "R20": 20, "R60": 60}


def model(kind):
    kw = dict(learning_rate=0.05, max_iter=200, max_leaf_nodes=15, min_samples_leaf=1000, l2_regularization=1.0, early_stopping=False, random_state=SEED)
    return HistGradientBoostingClassifier(**kw) if kind == "D" else HistGradientBoostingRegressor(**kw)


def blocks(dates, L, seed=SEED):
    ud, di = np.unique(dates, return_inverse=True); T = len(ud); rng = np.random.default_rng(seed)
    for _ in range(BOOT):
        st = rng.integers(0, T, math.ceil(T / L)); cnt = np.bincount(((st[:, None] + np.arange(L)[None, :]) % T).ravel(), minlength=T)
        yield cnt, di


def wauc(y, p, w):
    o = np.argsort(p, kind="mergesort"); ps, yy, ww = p[o], y[o], w[o]
    gid = np.concatenate([[0], np.cumsum(ps[1:] != ps[:-1])]); ng = gid[-1] + 1
    P_ = np.bincount(gid, weights=ww * yy, minlength=ng); N_ = np.bincount(gid, weights=ww * (1 - yy), minlength=ng)
    return float((P_ * (np.cumsum(N_) - N_ + 0.5 * N_)).sum() / (P_.sum() * N_.sum()))


R = {"說明": "walk5-D(規則 PROTOCOL_d.md);D = 上下對稱的先碰哪邊(有動的情境才算);R = 之後報酬 ÷(atr·√天數)", "boot": BOOT, "seed": SEED}
for t, H in HZ.items():
    V = S[S[t].notna() & (S.date >= "2018-01-02")]; pr = []
    for Y in range(2021, 2026):
        tr, te = V[V[f"e{H}"] < f"{Y}-01-01"], V[V.date.str[:4] == str(Y)]
        if t[0] == "D":
            p = model("D").fit(tr[FFULL].values, tr[t].values.astype(int)).predict_proba(te[FFULL].values)[:, 1]
        else:
            p = model("R").fit(tr[FFULL].values, tr[t].clip(-5, 5).values).predict(te[FFULL].values)
        pr.append(pd.DataFrame({"sym": te.sym.values, "date": te.date.values, "y": te[t].values, "p": p, "yr": str(Y)}))
    g = pd.concat(pr, ignore_index=True); g["dec"] = pd.qcut(g.p.rank(method="first"), 10, labels=False)
    o = {"張數": len(g), "天數": int(g.date.nunique())}
    if t[0] == "D":
        y, p = g.y.values, g.p.values; pt = wauc(y, p, np.ones(len(y))); bs = [wauc(y, p, cnt[di].astype(float)) for cnt, di in blocks(g.date.values, LBLK[t])]
        ci = [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]
        o.update({"先往上比例%": round(100 * float(g.y.mean()), 1), "AUC": round(pt, 4), "95%": ci,
                  "判定": "有方向訊號(下界 > 0.5)" if ci[0] > 0.5 else ("反向(上界 < 0.5)" if ci[1] < 0.5 else "沒有證據(區間含 0.5)"),
                  "十分位 先往上%": [round(100 * float(g[g.dec == k].y.mean()), 1) for k in range(10)]})
        # 同一天內(橫向)的排序力
        dA = {d: wauc(h.y.values, h.p.values, np.ones(len(h))) for d, h in g.groupby("date") if len(h) >= 30 and 0 < h.y.sum() < len(h)}
        o["同一天內平均 AUC"] = round(float(np.mean(list(dA.values()))), 4)
    else:
        def daily_ic(h):
            return h[["y", "p"]].rank().corr().iloc[0, 1] if len(h) >= 30 else np.nan
        ic = g.groupby("date").apply(daily_ic).dropna(); ud = ic.index.values; a_ = ic.values; T = len(a_); rng = np.random.default_rng(SEED); bs = []
        for _ in range(BOOT):
            st = rng.integers(0, T, math.ceil(T / LBLK[t])); cnt = np.bincount(((st[:, None] + np.arange(LBLK[t])[None, :]) % T).ravel(), minlength=T); bs.append(float((a_ * cnt).sum() / cnt.sum()))
        ci = [round(float(np.percentile(bs, 2.5)), 4), round(float(np.percentile(bs, 97.5)), 4)]
        g["dm_y"] = g.y - g.groupby(["sym", "yr"]).y.transform("mean"); g["dm_p"] = g.p - g.groupby(["sym", "yr"]).p.transform("mean")
        o.update({"每天橫向排序相關(IC)平均": round(float(a_.mean()), 4), "95%": ci,
                  "判定": "有方向訊號(下界 > 0)" if ci[0] > 0 else ("反向(上界 < 0)" if ci[1] < 0 else "沒有證據(區間含 0)"),
                  "全部合併的排序相關": round(float(g[["y", "p"]].rank().corr().iloc[0, 1]), 4),
                  "同一檔同一年內(擇時)的排序相關": round(float(g[["dm_y", "dm_p"]].rank().corr().iloc[0, 1]), 4),
                  "十分位 實際報酬(atr·√天數 單位)": [round(float(g[g.dec == k].y.mean()), 3) for k in range(10)]})
    o["各年"] = {}
    for yr, h in g.groupby("yr"):
        o["各年"][yr] = round(wauc(h.y.values, h.p.values, np.ones(len(h))), 4) if t[0] == "D" else round(float(h.groupby("date").apply(daily_ic).dropna().mean()), 4)
    R[t] = o; print(t, json.dumps(o, ensure_ascii=False), flush=True)
json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1)
