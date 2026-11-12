#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事後檢查(沒有預先登記;只檢查網站已上線的兩句話會不會也是「尺」造成的):
網站 10/21 上線:R8「5 天急跌(5 天報酬 ≤ −2 ×(ATR20 ÷ 收盤)× √5)→ 之後短線反彈機會高一些」、R4「RSI14 < 30 → 偏反彈一點點」。
walk7 的答案 buy 用 ATR20 當尺(先碰 +2·a 或 −1.5·a,a = ATR20 ÷ 收盤,20 天;同一天兩邊都碰算先跌)。急跌後 ATR20 被撐大,尺跟著變。
這裡同一批日子換尺:A20(原尺,先核對和 walk7 的 buy 一模一樣)、A60、固定(a = 2.4%,約全體中位),
再加完全不用尺的:之後 5 / 10 / 20 天收盤報酬,和「減掉同一天全名單平均」的超額報酬。
用法:python3 -I x5_rule_ruler.py SCRATCH   → SCRATCH/em/out/x5_rule_ruler.json"""
import gzip, json, os, pickle, sys
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

ROOT = sys.argv[1]; W7 = os.path.join(ROOT, "w7"); OUT = os.path.join(ROOT, "em", "out")
S = pd.read_pickle(os.path.join(W7, "out", "S7.pkl"))[["sym", "date", "i", "a", "r5", "rsi14", "buy"]]
B = pickle.load(gzip.open(os.path.join(W7, "data", "daily.pkl.gz")))["bars"]
H = 20


def sma(x, w):
    cs = np.cumsum(np.insert(np.nan_to_num(x), 0, 0.0)); o = np.full(len(x), np.nan); o[w - 1:] = (cs[w:] - cs[:-w]) / w; return o


def first_touch(h, l, c, I, a):
    """buy:1 先碰 +2a、0 先碰 −1.5a(同一天都碰算 0)、2 都沒碰;回傳 0/1/2"""
    C = c[I]; up = C * (1 + 2 * a); dn = C * (1 - 1.5 * a)
    hw = swv(h, H)[I + 1]; lw = swv(l, H)[I + 1]          # 第 k 列 = [I+1, I+H]
    hu = hw >= up[:, None]; ld = lw <= dn[:, None]
    ku = np.where(hu.any(1), hu.argmax(1), H); kd = np.where(ld.any(1), ld.argmax(1), H)
    out = np.full(len(I), 2); out[(kd <= ku) & (kd < H)] = 0; out[(ku < kd)] = 1
    return out


parts = []
for s, g in S.groupby("sym", sort=False):
    x = B[s]["x"]; o, h, l, c = x[:, 0], x[:, 1], x[:, 2], x[:, 3]
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), h - l, np.maximum(h, pc) - np.minimum(l, pc))
    I = g["i"].values
    d = {"row": g.index.values}
    d["b_A20"] = first_touch(h, l, c, I, sma(tr, 20)[I] / c[I])
    d["b_A60"] = first_touch(h, l, c, I, sma(tr, 60)[I] / c[I])
    d["b_FIX"] = first_touch(h, l, c, I, np.full(len(I), 0.024))
    for k in (5, 10, 20):
        d[f"f{k}"] = (c[I + k] / c[I] - 1) * 100
    parts.append(pd.DataFrame(d))
F = pd.concat(parts).set_index("row"); S = S.join(F)
chk = int((S.b_A20 != S.buy).sum())
print("A20 重算和 walk7 buy 不同的筆數:", chk, flush=True)
for k in (5, 10, 20):
    S[f"x{k}"] = S[f"f{k}"] - S.groupby("date")[f"f{k}"].transform("mean")
S["z5"] = (S.r5) / (S.a * np.sqrt(5))


def row(g):
    r = {"n": int(len(g))}
    for nm in ("A20", "A60", "FIX"):
        b = g[f"b_{nm}"]
        r[f"先漲一段%({nm})"] = round(float((b == 1).mean()) * 100, 1)
        r[f"有動裡先漲%({nm})"] = round(float((b[b != 2] == 1).mean()) * 100, 1)
    for k in (5, 10, 20):
        r[f"之後{k}天報酬%(平均/中位)"] = [round(float(g[f"f{k}"].mean()), 2), round(float(g[f"f{k}"].median()), 2)]
        r[f"之後{k}天超額%(減同日平均)"] = round(float(g[f"x{k}"].mean()), 2)
    r["之後10天為正%"] = round(float((g.f10 > 0).mean()) * 100, 1)
    return r


res = {"說明": __doc__.split("\n")[0], "A20 重算和 walk7 buy 不同筆數": chk, "期間": {}}
for nm, m in (("2021-2025", (S.date >= "2021-01-01") & (S.date <= "2025-12-31")), ("全期 2016-10 ~ 2026-09", S.date.notna())):
    g = S[m]
    res["期間"][nm] = {"全部": row(g), "R8 5天急跌(z5 ≤ −2)": row(g[g.z5 <= -2]), "R4 RSI14 < 30": row(g[g.rsi14 < 30])}
    print(nm, json.dumps(res["期間"][nm], ensure_ascii=False, indent=0), flush=True)
json.dump(res, open(os.path.join(OUT, "x5_rule_ruler.json"), "w"), ensure_ascii=False, indent=1)
print("寫入 x5_rule_ruler.json")
