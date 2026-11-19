#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 共用統計:AUC、同一天內的 AUC(分層 Mann–Whitney)、以月為區塊的重抽、同一天內打亂的置換檢定"""
import numpy as np, pandas as pd
from scipy.stats import rankdata


def auc(score, y):
    y = np.asarray(y).astype(int); s = np.asarray(score, float); n1 = y.sum(); n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(s); return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def date_stats(score, y, dates):
    """每一天的 U 與 n1·n0(同一天內的排名;平手算一半)"""
    d = pd.DataFrame({"s": np.asarray(score, float), "y": np.asarray(y).astype(int), "d": np.asarray(dates)})
    d["r"] = d.groupby("d").s.rank(method="average")
    g = d.groupby("d").agg(n=("y", "size"), n1=("y", "sum"), r1=("r", lambda r: 0.0))
    g["r1"] = d[d.y == 1].groupby("d").r.sum().reindex(g.index).fillna(0.0)
    g["n0"] = g.n - g.n1; g["U"] = g.r1 - g.n1 * (g.n1 + 1) / 2; g["w"] = g.n1 * g.n0
    return g[g.w > 0]


def wd_auc(score, y, dates):
    g = date_stats(score, y, dates); return float(g.U.sum() / g.w.sum()) if len(g) else np.nan


def boot_month(g, reps=2000, seed=1):
    """g = date_stats 的結果;以「月」為區塊重抽 → 同一天內 AUC 的分布"""
    m = pd.Series(g.index.astype(str).str[:7], index=g.index); M = m.unique(); rng = np.random.default_rng(seed)
    U = g.U.groupby(m).sum().reindex(M).values; Wt = g.w.groupby(m).sum().reindex(M).values; out = np.empty(reps)
    for k in range(reps):
        idx = rng.integers(0, len(M), len(M)); out[k] = U[idx].sum() / Wt[idx].sum()
    return out


def boot_month_pooled(score, y, dates, reps=2000, seed=1):
    """一般 AUC(不分天)的月區塊重抽"""
    d = pd.DataFrame({"s": np.asarray(score, float), "y": np.asarray(y).astype(int), "m": pd.Series(np.asarray(dates)).astype(str).str[:7].values})
    groups = [g for _, g in d.groupby("m")]; rng = np.random.default_rng(seed); out = np.empty(reps)
    for k in range(reps):
        b = pd.concat([groups[j] for j in rng.integers(0, len(groups), len(groups))]); out[k] = auc(b.s.values, b.y.values)
    return out


def perm_within_date(score, y, dates, reps=10000, seed=7):
    """同一天內把分數打亂 → 同一天內 AUC 的虛無分布;回傳(實際值, 單邊 p(> 實際))"""
    d = pd.DataFrame({"s": np.asarray(score, float), "y": np.asarray(y).astype(int), "d": np.asarray(dates)}).sort_values("d")
    obs = wd_auc(d.s.values, d.y.values, d.d.values); rng = np.random.default_rng(seed)
    grp = [np.nonzero((d.d == k).values)[0] for k in d.d.unique()]; s = d.s.values.copy(); cnt = 0
    g0 = date_stats(d.s.values, d.y.values, d.d.values); W = g0.w.sum()
    yv = d.y.values; keys = list(d.d.unique())
    # 分數在每一天內的排名固定,只打亂「誰拿到哪個排名」= 打亂 y
    rk = d.groupby("d").s.rank(method="average").values
    for _ in range(reps):
        U = 0.0
        for ix in grp:
            yy = rng.permutation(yv[ix]); n1 = yy.sum(); U += rk[ix][yy == 1].sum() - n1 * (n1 + 1) / 2
        cnt += (U / W) >= obs - 1e-12
    return obs, (cnt + 1) / (reps + 1)
