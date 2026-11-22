#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 W5:電腦方法的成績
- 每個方法 × 目標(買方先漲 y_buy、賣方先跌 y_sell、只看方向 y_dir):
  一般 AUC、同一天內 AUC(只比同一天的股票,扣掉大盤當天的漲跌)、月區塊重抽 95% 區間、單邊 p(> 0.5)
  主要測試期 = 2021–2026(K1、N1 只有這段);另外報 2019–2020、各年、POST(2026-07-01 起)
- 最高 1/10 的實際比例 vs 全體
- 技術規則 R1–R9(不用學):訊號成立 vs 不成立的實際比例差,以月為群的重抽區間
用法:python3 -I w5_cpu_eval.py OUT_DIR TAG(real / dev)"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from w5_stats import auc, wd_auc, date_stats, boot_month, boot_month_pooled  # noqa: E402

OUT, TAG = sys.argv[1], sys.argv[2]
S = pd.read_pickle(os.path.join(OUT, "out", "S7.pkl"))
S["y_buy"] = (S.buy == 1).astype(int); S["y_sell"] = (S.sell == 1).astype(int); S["y_dir"] = S.d20
TGT = {"y_buy": "p_buy", "y_sell": "p_sell", "y_dir": "p_dir"}; R = {"tag": TAG}


def block(rows, P, tgt, reps=1000):
    y = S.loc[rows, tgt].values.astype(float); ok = ~np.isnan(y); rows = np.asarray(rows)[ok]; y = y[ok].astype(int); s = P.loc[rows, TGT[tgt]].values; d = S.loc[rows, "date"].values
    g = date_stats(s, y, d); wd = float(g.U.sum() / g.w.sum()); bw = boot_month(g, reps); a = auc(s, y)
    top = s >= np.quantile(s, 0.9)
    return {"n": int(len(y)), "AUC": round(a, 4), "同一天內 AUC": round(wd, 4), "同一天內 95%": [round(float(np.quantile(bw, 0.025)), 4), round(float(np.quantile(bw, 0.975)), 4)],
            "同一天內 p(≤ 0.5)": round(float((bw <= 0.5).mean()), 4), "最高 1/10 實際 %": round(100 * float(y[top].mean()), 1), "全體 %": round(100 * float(y.mean()), 1)}


for m in ("M1", "M2", "K1", "N1"):
    p = os.path.join(OUT, "out", f"pred_{m}_{TAG}.pkl")
    if not os.path.exists(p):
        continue
    P = pd.read_pickle(p); R[m] = {}
    for per, cond in (("2021–2026", P.year >= 2021), ("2019–2020", P.year <= 2020), ("POST 2026-07~09", S.loc[P.index, "date"].values >= "2026-07-01"), ("dev 2018", P.year == 2018)):
        rows = P.index[cond]
        if len(rows) < 1000:
            continue
        R[m][per] = {t: block(rows, P, t) for t in TGT}
    R[m]["各年同一天內 AUC"] = {int(y): {t: round(wd_auc(P.loc[P.year == y, TGT[t]].values[~S.loc[P.index[P.year == y], t].isna().values],
                                                     S.loc[P.index[P.year == y], t].dropna().values.astype(int), S.loc[P.index[P.year == y], "date"].values[~S.loc[P.index[P.year == y], t].isna().values]), 4)
                                         for t in TGT} for y in sorted(P.year.unique())}
    print(m, json.dumps({k: {t: (v[t]["同一天內 AUC"], v[t]["同一天內 95%"]) for t in TGT} for k, v in R[m].items() if k != "各年同一天內 AUC"}, ensure_ascii=False), flush=True)

# 技術規則
yr = S.year >= (2018 if TAG == "dev" else 2021); X = S[yr if TAG != "dev" else (S.year == 2018)]
RULES = {"R1 多頭排列(收 > 20 > 50 > 200 日線)": (X.dma20 > 0) & (X.al20_50 == 1) & (X.al50_200 == 1),
         "R2 20 日新高 + 量 ≥ 1.5 倍": (X.bo20 >= 0) & (X.vr1 >= 1.5),
         "R3 靠近 52 週高(位置 ≥ 95%)": X.pos250 >= 0.95,
         "R4 RSI14 < 30(超賣)": X.rsi14 < 30,
         "R5 RSI14 > 70(超買)": X.rsi14 > 70,
         "R6 多頭裡拉回 20 日線(±0.5 個波動)": (X.dma50 > 0) & (X.sl50 > 0) & (X.dma20.abs() <= 0.5),
         "R7 跳空上漲 ≥ 1 個波動": X.gap >= 1,
         "R8 5 天急跌(≤ −2 個波動 × √5)": X.z5 <= -2,
         "R9 窄幅整理(20 天高低差 ≤ 4 個波動)": X.rw20 <= 4}
R["規則"] = {}; rng = np.random.default_rng(3); mon = X.date.str[:7].values; M = np.unique(mon)
for nm, on in RULES.items():
    on = on.values.astype(bool); out = {"成立比例 %": round(100 * float(on.mean()), 1)}
    for t in ("y_buy", "y_sell", "y_dir"):
        y = X[t].values.astype(float); ok = ~np.isnan(y)
        g = pd.DataFrame({"m": mon[ok], "on": on[ok], "y": y[ok]}).groupby(["m", "on"]).y.agg(["sum", "count"]).unstack(fill_value=0)
        s1, c1, s0, c0 = g[("sum", True)].values, g[("count", True)].values, g[("sum", False)].values, g[("count", False)].values
        diff = s1.sum() / c1.sum() - s0.sum() / c0.sum(); bs = []
        for _ in range(1000):
            k = rng.integers(0, len(g), len(g)); bs.append(s1[k].sum() / c1[k].sum() - s0[k].sum() / c0[k].sum())
        out[t] = {"成立時 %": round(100 * s1.sum() / c1.sum(), 1), "不成立時 %": round(100 * s0.sum() / c0.sum(), 1), "差(百分點)": round(100 * diff, 1),
                  "95%": [round(100 * float(np.quantile(bs, 0.025)), 1), round(100 * float(np.quantile(bs, 0.975)), 1)]}
    R["規則"][nm] = out; print(nm, {t: out[t]["差(百分點)"] for t in ("y_buy", "y_sell", "y_dir")}, flush=True)
json.dump(R, open(os.path.join(OUT, "out", f"cpu_{TAG}.json"), "w"), ensure_ascii=False, indent=1)
