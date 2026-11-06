#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q0:「圖裡到底有沒有東西可學」— 每一檔、每一天的情境 + 特徵 + 答案
- 特徵只用「決定日收盤(含)以前」的這檔日K與 QQQ 日K
- 答案:
  T1b / T1s = walk4 的買對 / 賣對(10 天內先 +2×ATR20 / 先 −1.5×ATR20;同一天兩邊都碰到算錯)
  T2b / T2s = 比較像使用者說的「買了幾天內開始漲一段,就算洗盤也不會套太久」:
     15 天內碰到 +3×ATR20(漲一段);在那之前收盤跌破買價的天數 ≤ 3(不會套太久);
     那之前(含當天)最低價沒有碰到 −2.5×ATR20(洗盤可以,但不能洗到停損)。賣點反過來
- 基準(同檔前後 10 個交易日、任何日期、只算有效的日子)= 和 walk4 一樣的「同一檔隨便哪天」對照
用法:python3 -I q0_features.py BARS.json.gz OUT.pkl"""
import gzip, json, math, sys
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

BARS, OUT = sys.argv[1], sys.argv[2]
B = json.load(gzip.open(BARS))["bars"]
MK, NEED, N_CH = "QQQ", 130, 126


def shift(x, k):
    out = np.full(len(x), np.nan)
    if k < len(x):
        out[k:] = x[:len(x) - k]
    return out


def sma(x, w):
    out = np.full(len(x), np.nan)
    if len(x) >= w:
        cs = np.concatenate([[0.0], np.cumsum(x)]); out[w - 1:] = (cs[w:] - cs[:-w]) / w
    return out


def flag(cond, *src):
    bad = np.zeros(len(cond), bool)
    for s in src:
        bad |= np.isnan(s)
    return np.where(bad, np.nan, cond.astype(float))


def feats(o, h, l, c, v):
    n = len(c); pc = shift(c, 1)
    tr = np.where(np.isnan(pc), h - l, np.maximum(h, pc) - np.minimum(l, pc))
    atr20, atr5, atr60 = sma(tr, 20), sma(tr, 5), sma(tr, 60); a = atr20 / c
    F = {}; lc = np.log(c)
    for k in (1, 2, 3, 5, 10, 20, 40, 60, 120, 250):
        F[f"r{k}"] = lc - shift(lc, k)
    for k in (5, 20, 60):
        F[f"z{k}"] = F[f"r{k}"] / (a * math.sqrt(k))
    F["a"] = a; F["atr5_20"] = atr5 / atr20; F["atr20_60"] = atr20 / atr60
    lr = lc - shift(lc, 1); F["rv20_a"] = pd.Series(lr).rolling(20).std().values / a
    M = {k: sma(c, k) for k in (10, 20, 50, 100, 200)}
    for k, m in M.items():
        F[f"dma{k}"] = (c / m - 1) / a
    F["sl20"] = (M[20] - shift(M[20], 5)) / (a * c); F["sl50"] = (M[50] - shift(M[50], 10)) / (a * c); F["sl200"] = (M[200] - shift(M[200], 20)) / (a * c)
    F["al20_50"] = flag(M[20] > M[50], M[20], M[50]); F["al50_200"] = flag(M[50] > M[200], M[50], M[200])
    Hs, Ls = pd.Series(h), pd.Series(l); HL = {}
    for w in (20, 60, 120, 250):
        hh, ll = Hs.rolling(w).max().values, Ls.rolling(w).min().values; HL[w] = (hh, ll)
        F[f"rw{w}"] = (hh / ll - 1) / a; F[f"pos{w}"] = (c - ll) / (hh - ll)
    for w in (60, 250):
        dsh, dsl = np.full(n, np.nan), np.full(n, np.nan)
        if n >= w:
            dsh[w - 1:] = np.argmax(swv(h, w)[:, ::-1], axis=1) / w; dsl[w - 1:] = np.argmin(swv(l, w)[:, ::-1], axis=1) / w
        F[f"dsh{w}"], F[f"dsl{w}"] = dsh, dsl
    for w in (20, 60):
        F[f"bo{w}"] = (c / Hs.shift(1).rolling(w).max().values - 1) / a
        F[f"bd{w}"] = (c / Ls.shift(1).rolling(w).min().values - 1) / a
        F[f"cs{w}"] = pd.Series(c).rolling(w).std().values / (a * c)
    rng = h - l; rz = np.where(rng > 0, rng, np.nan)
    F["body"] = (c - o) / rz; F["cloc"] = (c - l) / rz; F["ush"] = (h - np.maximum(o, c)) / rz; F["lsh"] = (np.minimum(o, c) - l) / rz
    F["rng_a"] = rng / (a * c); F["gap"] = (o / pc - 1) / a
    st = np.zeros(n)
    for i in range(1, n):
        st[i] = (st[i - 1] + 1 if st[i - 1] > 0 else 1) if c[i] > c[i - 1] else ((st[i - 1] - 1 if st[i - 1] < 0 else -1) if c[i] < c[i - 1] else 0)
    F["streak"] = st
    ch = c - pc; g = np.nan_to_num(np.where(ch > 0, ch, 0.0)); dn = np.nan_to_num(np.where(ch < 0, -ch, 0.0))
    for k in (2, 14):
        ag, al = sma(g, k), sma(dn, k)
        F[f"rsi{k}"] = np.where(al == 0, 100.0, 100 - 100 / (1 + ag / np.where(al == 0, 1, al)))
    v20 = sma(v, 20); v20p = shift(v20, 1)
    F["vr1"] = v / v20p; F["vr5"] = sma(v, 5) / shift(v20, 5); F["vr20_60"] = v20 / shift(sma(v, 60), 20)
    F["upv20"] = sma(np.where(ch > 0, v, 0.0), 20) / v20
    # walk4 判讀者看得到的 11 個數字(同樣的定義)
    F["w_atr20"] = 100 * a; F["w_rsi14"] = F["rsi14"]; F["w_d1"] = 100 * (c / pc - 1); F["w_d5"] = 100 * (c / shift(c, 5) - 1); F["w_d20"] = 100 * (c / shift(c, 20) - 1)
    F["w_vs20"] = 100 * (c / M[20] - 1); F["w_vs50"] = 100 * (c / M[50] - 1); F["w_vs200"] = 100 * (c / M[200] - 1); F["w_vr"] = F["vr1"]
    hh, ll = HL[60]; F["w_rng60"] = 100 * (hh / ll - 1); F["w_pos60"] = 100 * (c - ll) / (hh - ll)
    return F, a


def barrier(h, l, c, i, a, side, H=10, up=2.0, dn=1.5):
    C = c[i]
    U, D = (C * (1 + up * a), C * (1 - dn * a)) if side == "b" else (C * (1 + dn * a), C * (1 - up * a))
    for j in range(1, H + 1):
        hi, lo = h[i + j], l[i + j]
        if side == "b":
            if lo <= D:
                return 0.0
            if hi >= U:
                return 1.0
        else:
            if hi >= U:
                return 0.0
            if lo <= D:
                return 1.0
    return 0.0


def leg(h, l, c, i, a, side, H=15, k=3.0, stop=2.5, maxu=3):
    C = c[i]; under = 0
    for j in range(1, H + 1):
        if side == "b":
            if l[i + j] <= C * (1 - stop * a):
                return 0.0
            if h[i + j] >= C * (1 + k * a):
                return 1.0 if under <= maxu else 0.0
            under += c[i + j] < C
        else:
            if h[i + j] >= C * (1 + stop * a):
                return 0.0
            if l[i + j] <= C * (1 - k * a):
                return 1.0 if under <= maxu else 0.0
            under += c[i + j] > C
    return 0.0


def liquid(c, v, i, H):
    lo, hi = i - N_CH + 1, i + H
    if lo < 0 or hi >= len(c):
        return False
    vv, cc = v[lo:hi + 1], c[lo:hi + 1]
    return bool((vv > 0).all()) and int((cc[1:] == cc[:-1]).sum()) <= 0.02 * len(cc)


def kind(f):
    mvol = f["w_atr20"] * math.sqrt(20)
    if not np.isnan(f["w_pos60"]) and f["w_rng60"] <= 1.5 * mvol and f["w_pos60"] >= 50:
        return "整理"
    if f["w_d20"] > 0 and abs(f["w_vs20"]) <= 2:
        return "拉回"
    if f["w_d5"] <= -2 * f["w_atr20"]:
        return "急跌"
    return "其他"


def arrays(bars):
    d = np.array([b[0] for b in bars]); x = np.array([[float(b[k]) for k in range(1, 6)] for b in bars]).T
    return d, x[0], x[1], x[2], x[3], x[4]


qd, qo, qh, ql, qc, qv = arrays(B[MK]); QF, _ = feats(qo, qh, ql, qc, qv); QI = {d: k for k, d in enumerate(qd)}
QK = ["r1", "r5", "r20", "r60", "r120", "dma50", "dma200", "a", "atr5_20", "pos60", "streak", "rsi14"]
frames = []
for s in sorted(B):
    d, o, h, l, c, v = arrays(B[s]); n = len(c)
    if n < NEED + 11:
        continue
    F, a = feats(o, h, l, c, v)
    rows = [i for i in range(NEED, n) if d[i] in QI]
    df = pd.DataFrame({k: F[k][rows] for k in F}); df.insert(0, "i", rows); df.insert(0, "date", d[rows]); df.insert(0, "sym", s)
    qi = [QI[d[i]] for i in rows]
    for k in QK:
        df["q_" + k] = QF[k][qi]
    for k in (20, 60, 120):
        df[f"rs{k}"] = df[f"r{k}"] - QF[f"r{k}"][qi]
    lab = {t: np.full(len(rows), np.nan) for t in ("T1b", "T1s", "T2b", "T2s")}; end10, end15 = [None] * len(rows), [None] * len(rows)
    for r, i in enumerate(rows):
        if liquid(c, v, i, 10):
            lab["T1b"][r] = barrier(h, l, c, i, a[i], "b"); lab["T1s"][r] = barrier(h, l, c, i, a[i], "s"); end10[r] = d[i + 10]
        if liquid(c, v, i, 15):
            lab["T2b"][r] = leg(h, l, c, i, a[i], "b"); lab["T2s"][r] = leg(h, l, c, i, a[i], "s"); end15[r] = d[i + 15]
    for t, y in lab.items():
        df[t] = y
        s_ = pd.Series(y); df["base_" + t] = (s_.rolling(21, center=True, min_periods=1).sum() / s_.notna().astype(float).rolling(21, center=True, min_periods=1).sum()).values
    df["end10"], df["end15"] = end10, end15
    df["kind"] = [kind({k: F[k][i] for k in ("w_atr20", "w_pos60", "w_rng60", "w_d20", "w_vs20", "w_d5")}) for i in rows]
    frames.append(df)
S = pd.concat(frames, ignore_index=True)
fc = [c_ for c_ in S.columns if c_ not in ("sym", "date", "i", "kind", "end10", "end15")]
print("inf 欄位(改成缺值):", [c_ for c_ in fc if np.isinf(S[c_].values.astype(float)).any()])
S[fc] = S[fc].replace([np.inf, -np.inf], np.nan).astype("float32")
S.to_pickle(OUT)
print("rows", len(S), "syms", S.sym.nunique(), "dates", S.date.min(), S.date.max())
for t in ("T1b", "T1s", "T2b", "T2s"):
    y = S[t]; print(t, "有效", int(y.notna().sum()), "成功率%", round(100 * float(y.mean()), 1))
