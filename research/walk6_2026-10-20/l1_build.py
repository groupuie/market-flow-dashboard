#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk6 L1:每個月「跳」一次的長線情境(決定點 = QQQ 每個月最後一個交易日的收盤)
- 特徵只用決定日收盤(含)以前的日K;答案 = 之後 h 個交易日的報酬(h = 21 / 63 / 126 / 252 / 504 ≈ 1 / 3 / 6 / 12 / 24 個月)
- 流動性:決定日以前至少 260 根;前 63 天沒有零成交量;收盤 > 0
用法:python3 -I l1_build.py BARS_LONG.json.gz OUT.pkl"""
import gzip, json, math, sys
import numpy as np, pandas as pd

BZ, OUT = sys.argv[1], sys.argv[2]
D = json.load(gzip.open(BZ)); B, ETF = D["bars"], set(D["etf"])
H = {"m1": 21, "m3": 63, "m6": 126, "m12": 252, "m24": 504}


def arr(b):
    return [x[0] for x in b], np.array([[float(x[k]) for k in range(1, 6)] for x in b]).T


def sma(x, w):
    out = np.full(len(x), np.nan); cs = np.concatenate([[0.0], np.cumsum(x)])
    if len(x) >= w:
        out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


def feats(o, h, l, c, v):
    n = len(c); lc = np.log(c); F = {}
    sh = lambda x, k: np.concatenate([np.full(k, np.nan), x[:-k]]) if k < len(x) else np.full(len(x), np.nan)
    for k, nm in ((21, "r1m"), (63, "r3m"), (126, "r6m"), (252, "r12m"), (504, "r24m"), (756, "r36m")):
        F[nm] = lc - sh(lc, k)
    F["r12_1"] = sh(lc, 21) - sh(lc, 252)
    m50, m200 = sma(c, 50), sma(c, 200)
    F["vs200"] = c / m200 - 1; F["vs50"] = c / m50 - 1; F["ma50_200"] = m50 / m200 - 1; F["sl200"] = m200 / sh(m200, 21) - 1
    Hs, Ls, Cs = pd.Series(h), pd.Series(l), pd.Series(c)
    F["hi52"] = c / Hs.rolling(252).max().values - 1; F["lo52"] = c / Ls.rolling(252).min().values - 1
    F["ath_dd"] = c / Cs.cummax().values - 1
    lr = np.concatenate([[np.nan], np.diff(lc)]); S = pd.Series(lr)
    F["vol3m"] = S.rolling(63).std().values * math.sqrt(252); F["vol12m"] = S.rolling(252).std().values * math.sqrt(252); F["volr"] = F["vol3m"] / F["vol12m"]
    F["mdd12m"] = (Cs / Cs.rolling(252).max() - 1).rolling(252).min().values
    F["vr"] = sma(v, 21) / sma(v, 252)
    return F


qd, qx = arr(B["QQQ"]); QF = feats(*qx); QI = {d: k for k, d in enumerate(qd)}
ME = sorted(d for d, nx in zip(qd[:-1], qd[1:]) if d[:7] != nx[:7])   # QQQ 每個月最後一個交易日(最後一個還沒結束的月份不算)
qc = qx[3]
rows = []
for s in sorted(B):
    d, x = arr(B[s]); o, h, l, c, v = x; n = len(c); idx = {t: k for k, t in enumerate(d)}; F = feats(o, h, l, c, v)
    for t in ME:
        i = idx.get(t)
        if i is None or i < 260 or not (v[max(0, i - 62):i + 1] > 0).all():
            continue
        qi = QI[t]
        r = {"sym": s, "date": t, "etf": s in ETF, "i": i}
        for k, a in F.items():
            r[k] = float(a[i]) if np.isfinite(a[i]) else np.nan
        for k in ("r12m", "r6m", "vs200", "vol3m", "hi52"):
            r["q_" + k] = float(QF[k][qi]) if np.isfinite(QF[k][qi]) else np.nan
        r["rs12m"] = r["r12m"] - r["q_r12m"]; r["rs6m"] = r["r6m"] - r["q_r6m"]
        for nm, hh in H.items():
            if i + hh < n and qi + hh < len(qc):
                r["f_" + nm] = math.log(c[i + hh] / c[i]); r["qf_" + nm] = math.log(qc[qi + hh] / qc[qi]); r["end_" + nm] = d[i + hh]
            else:
                r["f_" + nm] = np.nan; r["qf_" + nm] = np.nan; r["end_" + nm] = None
        rows.append(r)
S = pd.DataFrame(rows)
S.to_pickle(OUT)
print("情境", len(S), "檔", S.sym.nunique(), "ETF 情境", int(S.etf.sum()), "月份", S.date.nunique(), S.date.min(), S.date.max())
for nm in H:
    print(nm, "有答案", int(S["f_" + nm].notna().sum()), "最後決定日", S.loc[S["f_" + nm].notna(), "date"].max())
