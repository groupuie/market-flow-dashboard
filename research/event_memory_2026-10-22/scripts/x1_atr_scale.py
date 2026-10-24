#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事後診斷(沒有預先登記;回應 Astra 盤感路線 v1.0 第 3 點):
「波動收縮之後比較常大動」會不會只是 ATR20 變小、門檻跟著變近?
做法:walk7 名單的每個某檔某天(2016-10 ~ 2026-09;重點看 2021-01 ~ 2025-12,和 v3.7 x4_quiet 同期),
同一批日子,用四把尺量「之後 10 / 20 天有沒有大動」:
  A20 = 2 × ATR20 / 收盤(原本的尺)、A60 = 2 × ATR60 / 收盤、A250 = 2 × ATR250 / 收盤、FIX = 固定 ±6%
另報之後 10 / 20 天每日報酬標準差(%)與 |10 天報酬|(%),以及「有動的裡面先往上」的比例(A20)。
分組:安靜(ATR20 / ATR60 ≤ 0.96,同 x4_quiet)/ 其他;量縮(20 日均量 ÷ 前 60 天 ≤ 0.85);
      波動高(近 20 天實現波動在自身近 504 天的百分位 ≥ 80,同網站 RVPOS 的意思)/ 低(≤ 20)。
另外:只看波動的邏輯迴歸(log a、ATR5/20、ATR20/60、大盤 log a)預測 walk7 的買方答案,
      訓練 = 答案在 2021-01-01 前結束的日子,測試 2021 ~ 2026 同一天內 AUC,和 walk7 的 M2(0.516)比。
用法:python3 -I x1_atr_scale.py SCRATCH   (讀 SCRATCH/w7,寫 SCRATCH/em/out/x1_atr_scale.json)"""
import gzip, json, os, pickle, sys
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as swv

ROOT = sys.argv[1]; W7 = os.path.join(ROOT, "w7"); OUT = os.path.join(ROOT, "em", "out"); os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, W7)
from w5_stats import wd_auc  # noqa: E402

S = pd.read_pickle(os.path.join(W7, "out", "S7.pkl"))[["sym", "date", "i", "a", "atr5_20", "atr20_60", "vr20_60", "q_a", "buy", "d20", "end20"]]
B = pickle.load(gzip.open(os.path.join(W7, "data", "daily.pkl.gz")))["bars"]


def sma(x, w):
    cs = np.cumsum(np.insert(np.nan_to_num(x), 0, 0.0)); o = np.full(len(x), np.nan); o[w - 1:] = (cs[w:] - cs[:-w]) / w; return o


parts = []
for s, g in S.groupby("sym", sort=False):
    x = B[s]["x"]; o, h, l, c = x[:, 0], x[:, 1], x[:, 2], x[:, 3]; n = len(c)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), h - l, np.maximum(h, pc) - np.minimum(l, pc))
    a20, a60, a250 = sma(tr, 20) / c, sma(tr, 60) / c, sma(tr, 250) / c
    lr = np.r_[np.nan, np.diff(np.log(c))]
    rv20 = pd.Series(lr).rolling(20).std().values
    rvpos = pd.Series(rv20).rolling(504, min_periods=252).rank(pct=True).values * 100
    I = g["i"].values
    d = {"row": g.index.values}
    for H in (10, 20):
        hmax = swv(h, H).max(1); lmin = swv(l, H).min(1)   # 第 k 列 = [k, k+H)
        up = hmax[I + 1] / c[I] - 1; dn = lmin[I + 1] / c[I] - 1
        sd = swv(lr, H).std(1)[I + 1] * 100
        d[f"up{H}"], d[f"dn{H}"], d[f"sd{H}"] = up, dn, sd
        for nm, sc in (("A20", 2 * a20[I]), ("A60", 2 * a60[I]), ("A250", 2 * a250[I]), ("FIX", np.full(len(I), 0.06))):
            d[f"big{H}_{nm}"] = ((up >= sc) | (dn <= -sc)).astype(float)
    d["absr10"] = np.abs(c[I + 10] / c[I] - 1) * 100
    d["rvpos"] = rvpos[I]; d["a250"] = a250[I]; d["a20chk"] = a20[I]
    parts.append(pd.DataFrame(d))
F = pd.concat(parts).set_index("row"); S = S.join(F)
print("a 一致性(S7 的 a vs 重算 ATR20 / 收盤,最大差)", float(np.nanmax(np.abs(S.a - S.a20chk))), flush=True)


def first_up_A20(g, H=20):
    """walk7 的 buy 答案:有動(先漲或先跌)的裡面先漲的比例"""
    m = g.buy != 2
    return round(float((g.buy[m] == 1).mean()) * 100, 1)


def row(g):
    r = {"n": int(len(g))}
    for H in (10, 20):
        for nm in ("A20", "A60", "A250", "FIX"):
            r[f"大動{H}天_{nm}%"] = round(float(g[f"big{H}_{nm}"].mean()) * 100, 1)
        r[f"之後{H}天日報酬標準差%"] = round(float(g[f"sd{H}"].mean()), 3)
    r["|10天報酬|%"] = round(float(g.absr10.mean()), 2)
    r["2ATR20 門檻%(中位)"] = round(float((2 * g.a).median()) * 100, 2)
    r["有動的裡面先漲%(walk7 buy 答案)"] = first_up_A20(g)
    return r


res = {"說明": __doc__.split("\n")[0], "期間": {}}
for nm, m in (("2021-2025", (S.date >= "2021-01-01") & (S.date <= "2025-12-31")), ("全期 2016-10 ~ 2026-09", S.date.notna())):
    g = S[m]
    res["期間"][nm] = {
        "全部": row(g),
        "安靜(ATR20/ATR60 ≤ 0.96)": row(g[g.atr20_60 <= 0.96]), "其他(> 0.96)": row(g[g.atr20_60 > 0.96]),
        "量縮(20 日均量 / 前 60 天 ≤ 0.85)": row(g[g.vr20_60 <= 0.85]), "量不縮(> 0.85)": row(g[g.vr20_60 > 0.85]),
        "波動高(RVPOS ≥ 80)": row(g[g.rvpos >= 80]), "波動低(RVPOS ≤ 20)": row(g[g.rvpos <= 20]),
    }
    print(nm, json.dumps(res["期間"][nm], ensure_ascii=False, indent=1), flush=True)

# 只看波動的簡單模型 vs walk7 M2(買方同一天內 AUC 2021–2026 = 0.516)
from sklearn.linear_model import LogisticRegression  # noqa: E402
X = np.c_[np.log(S.a), S.atr5_20, S.atr20_60, np.log(S.q_a)]
ok = np.isfinite(X).all(1)
tr_ = ok & (S.end20 < "2021-01-01").values; te_ = ok & (S.date >= "2021-01-01").values
out_m = {}
for lab, y in (("買方先漲一段(buy==1)", (S.buy == 1).astype(int).values), ("有動(buy!=2)", (S.buy != 2).astype(int).values),
               ("方向 d20", S.d20.values)):
    yy = np.asarray(y, float); m_tr = tr_ & np.isfinite(yy); m_te = te_ & np.isfinite(yy)
    lr_ = LogisticRegression(max_iter=1000).fit(X[m_tr], yy[m_tr].astype(int))
    p = lr_.predict_proba(X[m_te])[:, 1]
    out_m[lab] = {"同一天內AUC_2021-2026": round(wd_auc(p, yy[m_te].astype(int), S.date.values[m_te]), 4), "係數": [round(float(v), 3) for v in lr_.coef_[0]]}
# 同一個簡單模型,改成「固定 6% 的大動」當答案(看會不會動的訊號換尺後還在不在)
for lab, col in (("20 天大動(A20 尺)", "big20_A20"), ("20 天大動(固定 6%)", "big20_FIX"), ("20 天大動(A250 尺)", "big20_A250")):
    yy = S[col].values; m_tr = tr_ & np.isfinite(yy); m_te = te_ & np.isfinite(yy)
    lr_ = LogisticRegression(max_iter=1000).fit(X[m_tr], yy[m_tr].astype(int))
    p = lr_.predict_proba(X[m_te])[:, 1]
    out_m[lab] = {"同一天內AUC_2021-2026": round(wd_auc(p, yy[m_te].astype(int), S.date.values[m_te]), 4), "係數": [round(float(v), 3) for v in lr_.coef_[0]]}
res["只看波動的邏輯迴歸(特徵:log a、ATR5/20、ATR20/60、大盤 log a)"] = out_m
res["對照:walk7 M2 2021-2026 同一天內 AUC"] = {"買方": 0.516, "方向": 0.506}
print(json.dumps(out_m, ensure_ascii=False, indent=1))
json.dump(res, open(os.path.join(OUT, "x1_atr_scale.json"), "w"), ensure_ascii=False, indent=1)
print("寫入", os.path.join(OUT, "x1_atr_scale.json"))
