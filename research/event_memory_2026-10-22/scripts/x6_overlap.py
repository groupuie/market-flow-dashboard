#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E0 的補充(事後、沒有預先登記;回應複核):walk7 M2 的買方機率,和「只看 4 個波動數字」的邏輯迴歸,是不是同一個訊號?
- 同 x1:波動模型訓練 = 答案在 2021-01-01 前結束的日子,特徵 log a、ATR5/20、ATR20/60、大盤 log a
- M2 = walk7 逐年往前的預測(out/pred_M2_real.pkl 的 p_buy)
- 2021-01 ~ 2026-09:兩者各自的同一天內 AUC、相關、M2 扣掉波動模型後的殘差 AUC(OLS:logit M2 ~ logit 波動,只有 2 個參數)
用法:python3 -I x6_overlap.py SCRATCH   → SCRATCH/em/out/x6_overlap.json"""
import json, os, sys
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
ROOT = sys.argv[1]; W7 = os.path.join(ROOT, "w7"); OUT = os.path.join(ROOT, "em", "out")
sys.path.insert(0, W7)
from w5_stats import wd_auc  # noqa: E402
S = pd.read_pickle(os.path.join(W7, "out", "S7.pkl"))[["date", "a", "atr5_20", "atr20_60", "q_a", "buy", "end20"]]
P = pd.read_pickle(os.path.join(W7, "out", "pred_M2_real.pkl"))[["p_buy"]]
X = np.c_[np.log(S.a), S.atr5_20, S.atr20_60, np.log(S.q_a)]; ok = np.isfinite(X).all(1)
y = (S.buy == 1).astype(int).values
tr = ok & (S.end20 < "2021-01-01").values
mdl = LogisticRegression(max_iter=1000).fit(X[tr], y[tr])
S["p_vol"] = np.nan; S.loc[ok, "p_vol"] = mdl.predict_proba(X[ok])[:, 1]
D = S.join(P, how="inner"); D = D[(D.date >= "2021-01-01") & D.p_vol.notna() & D.p_buy.notna()]
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
lm, lv = lg(D.p_buy.values), lg(D.p_vol.values)
b, a = np.polyfit(lv, lm, 1); resid = lm - (a + b * lv)
yy = (D.buy == 1).astype(int).values; dd = D.date.values
rk = lambda v: pd.Series(v).groupby(dd).rank(pct=True).values
res = {"說明": __doc__.split("\n")[0], "列數": int(len(D)), "期間": [str(D.date.min()), str(D.date.max())],
       "同一天內 AUC": {"M2": round(wd_auc(D.p_buy.values, yy, dd), 4), "波動模型": round(wd_auc(D.p_vol.values, yy, dd), 4),
                     "M2 扣掉波動模型的殘差": round(wd_auc(resid, yy, dd), 4), "兩者同一天內排名平均": round(wd_auc(rk(D.p_buy.values) + rk(D.p_vol.values), yy, dd), 4)},
       "相關": {"Spearman(全部)": round(float(spearmanr(D.p_buy, D.p_vol).correlation), 3),
              "同一天內排名的相關(平均)": round(float(pd.DataFrame({"m": rk(D.p_buy.values), "v": rk(D.p_vol.values), "d": dd}).groupby("d").apply(lambda g: g.m.corr(g.v)).mean()), 3)},
       "殘差回歸": {"斜率": round(float(b), 3), "截距": round(float(a), 3)}}
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open(os.path.join(OUT, "x6_overlap.json"), "w"), ensure_ascii=False, indent=1)
