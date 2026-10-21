#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""開發資料的功效錨點(沒有預先登記;只為估「要多少季才看得出 Brier 差」,不是任何方法的成績):
財報事件窗(反應日 r ~ r+4)的 FL3_A20 答案上,比三個簡單預測:
  P0 = 訓練期基準率(一個常數);P1 = 只用「事件窗第幾天」的基準率;R = 邏輯迴歸(波動、報酬、均線、RSI、大盤、第幾天)
訓練 = 答案在 2021-01-01 前結束;測試 = 2021-01-01 ~ 2025-12-31(開發用,之後不再當保留組)。
報:Brier、R − P0 的配對差、以「日期」為群的標準誤(每天的事件互相相關)、事件間 / 日期間的變異占比,
    再把標準誤換算成「一季約 446 件事件」時要幾季才能在 95% 信心下看出同樣大小的差(80% 功效,雙尾)。
用法:python3 -I x3_power_anchor.py SCRATCH"""
import json, os, sys
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = sys.argv[1]; OUT = os.path.join(ROOT, "em", "out")
FL = pd.read_pickle(os.path.join(OUT, "fl3_rows.pkl"))
S = pd.read_pickle(os.path.join(ROOT, "w7", "out", "S7.pkl"))[["a", "atr5_20", "atr20_60", "q_a", "r5", "r20", "dma50", "rsi14", "q_r20", "end20"]]
D = FL.join(S); D = D[D.ev_lag >= 0].copy()
D["y"] = D.FL3_A20.astype(int)
for k in range(5):
    D[f"lag{k}"] = (D.ev_lag == k).astype(float)
X = np.c_[np.log(D.a), D.atr5_20, D.atr20_60, np.log(D.q_a), D.r5, D.r20, D.dma50, D.rsi14 / 100, D.q_r20, D[[f"lag{k}" for k in range(1, 5)]].values]
ok = np.isfinite(X).all(1)
tr = ok & (D.end20 < "2021-01-01").values; te = ok & (D.date >= "2021-01-01").values & (D.date <= "2025-12-31").values
y = D.y.values
p0 = np.full(te.sum(), y[tr].mean())
lagrate = D[tr].groupby("ev_lag").y.mean(); p1 = D.ev_lag[te].map(lagrate).values
mdl = LogisticRegression(max_iter=2000).fit(X[tr], y[tr]); pr = mdl.predict_proba(X[te])[:, 1]
yt = y[te]; dt = D.date.values[te]; ev = (D.sym + "_" + D.ev_r.astype(str)).values[te]
bs = {k: (p - yt) ** 2 for k, p in (("P0", p0), ("P1", p1), ("R", pr))}


def clustered_se(d, groups):
    g = pd.Series(d).groupby(groups).sum(); n = len(d)
    return float(np.sqrt((g ** 2).sum() - (g.sum() ** 2) / len(g)) / n) if len(g) > 1 else np.nan


res = {"說明": __doc__.split("\n")[0], "測試列數": int(te.sum()), "測試事件數": int(len(set(ev))), "測試日期數": int(len(set(dt))),
       "基準率(訓練)": round(float(y[tr].mean()), 4), "測試實際比例": round(float(yt.mean()), 4),
       "Brier": {k: round(float(v.mean()), 5) for k, v in bs.items()}}
from scipy.stats import rankdata  # noqa: E402
r_ = rankdata(pr); n1 = yt.sum(); n0 = len(yt) - n1
res["R 的 AUC(不分日)"] = round(float((r_[yt == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)), 4)
for a_, b_ in (("P0", "R"), ("P0", "P1"), ("P1", "R")):
    d = bs[a_] - bs[b_]
    se_iid = float(d.std(ddof=1) / np.sqrt(len(d)))
    se_ev = clustered_se(d, ev); se_dt = clustered_se(d, dt)
    q_events = 446; n_events_test = len(set(ev))
    # 以日期群標準誤換算到「每季 446 件事件」:標準誤 ∝ 1/√(事件數)
    se_per_q = se_dt * np.sqrt(n_events_test / q_events)
    need = (2.8 * se_per_q / abs(d.mean())) ** 2 if d.mean() != 0 else np.inf
    res[f"{a_} − {b_}(正 = {b_} 較好)"] = {"平均差": round(float(d.mean()), 5), "標準誤_獨立": round(se_iid, 5), "標準誤_事件群": round(se_ev, 5),
                                       "標準誤_日期群": round(se_dt, 5), "換算一季的標準誤": round(float(se_per_q), 5),
                                       "要幾季才看得出這麼大的差(80% 功效)": round(float(need), 1)}
# 變異拆解:日期間、事件間
yy = pd.Series(yt.astype(float)); tot = float(((yy - yy.mean()) ** 2).mean())
for nm, gk in (("日期", dt), ("事件", ev)):
    m = yy.groupby(gk).transform("mean"); res[f"答案變異:{nm}間佔 %"] = round((tot - float(((yy - m) ** 2).mean())) / tot * 100, 1)
# 若真效果是 Brier 改善 δ,每季標準誤用 R − P0 那組的,幾季看得出(80% 功效)
se_q = res["P0 − R(正 = R 較好)"]["換算一季的標準誤"]
res["假設的真效果 δ(Brier 改善)→ 要幾季"] = {str(dl): round((2.8 * se_q / dl) ** 2, 1) for dl in (0.001, 0.002, 0.003, 0.005, 0.01)}
res["註"] = "B 對 C 的配對差,變異會和 R 對 P0 不同(看兩組預測差多少);這裡只給量級。正式功效要用 one_day_example 量到的判讀分布再模擬。"
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open(os.path.join(OUT, "x3_power_anchor.json"), "w"), ensure_ascii=False, indent=1)
