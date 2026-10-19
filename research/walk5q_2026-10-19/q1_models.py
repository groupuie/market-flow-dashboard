#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q1:用「圖」能不能學到東西 — 兩個事先固定的模型,逐年往前驗證 + 2026-07~09 考試期
- M1 = 邏輯迴歸,只用 walk4 判讀者看得到的 11 個數字(訓練期 0.5% / 99.5% 截尾、缺值補中位數、標準化)
- M2 = 梯度提升樹(參數事先固定,不調):約 70 個圖形特徵(這檔 + QQQ),只用決定日收盤以前的資料
- 逐年往前:Y = 2021..2025,訓練 = 2018-01-02 起、而且答案的最後一天 < Y 年 1 月 1 日;測試 = Y 年那一年
- 考試期:訓練 = 答案的最後一天 ≤ 2026-06-30;測試 = 2026-07-01 ~ 2026-09-30(T2 要 15 天,只到資料夠的那天)
- --control neg:答案換成亂數(檢查會不會誤報);--control pos:偷放「未來 3 天報酬」當特徵(檢查抓不抓得到)
用法:python3 -I q1_models.py SCEN.pkl OUT_PREFIX [--control neg|pos]"""
import json, sys, time
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression

SC, PFX = sys.argv[1], sys.argv[2]
CTRL = sys.argv[sys.argv.index("--control") + 1] if "--control" in sys.argv else None
SEED = 20261019
F11 = ["w_atr20", "w_rsi14", "w_d1", "w_d5", "w_d20", "w_vs20", "w_vs50", "w_vs200", "w_vr", "w_rng60", "w_pos60"]
FFULL = (["r1", "r2", "r3", "r5", "r10", "r20", "r40", "r60", "r120", "r250", "z5", "z20", "z60", "a", "atr5_20", "atr20_60", "rv20_a",
          "dma10", "dma20", "dma50", "dma100", "dma200", "sl20", "sl50", "sl200", "al20_50", "al50_200",
          "rw20", "rw60", "rw120", "rw250", "pos20", "pos60", "pos120", "pos250", "dsh60", "dsl60", "dsh250", "dsl250",
          "bo20", "bd20", "cs20", "bo60", "bd60", "cs60", "body", "cloc", "ush", "lsh", "rng_a", "gap", "streak", "rsi2", "rsi14",
          "vr1", "vr5", "vr20_60", "upv20"] + ["q_" + k for k in ("r1", "r5", "r20", "r60", "r120", "dma50", "dma200", "a", "atr5_20", "pos60", "streak", "rsi14")]
         + ["rs20", "rs60", "rs120"])
TG = {"T1b": "end10", "T1s": "end10", "T2b": "end15", "T2s": "end15"}
S = pd.read_pickle(SC)
rng = np.random.default_rng(SEED)
if CTRL == "neg":
    for t in TG:
        m = S[t].notna(); S.loc[m, t] = (rng.random(int(m.sum())) < float(S.loc[m, t].mean())).astype("float32")
        g = S.groupby("sym")[t]   # 基準也用亂數答案重算(和 q0 同樣:前後 10 個交易日、只算有答案的日子)
        S["base_" + t] = (g.transform(lambda x: x.rolling(21, center=True, min_periods=1).sum()) / g.transform(lambda x: x.notna().astype(float).rolling(21, center=True, min_periods=1).sum())).astype("float32")
if CTRL == "pos":
    S["leak_fwd3"] = S.groupby("sym")["r3"].shift(-3); F11 = F11 + ["leak_fwd3"]; FFULL = FFULL + ["leak_fwd3"]


def m1_fit_predict(Xtr, ytr, Xte):
    lo, hi = np.nanpercentile(Xtr, 0.5, axis=0), np.nanpercentile(Xtr, 99.5, axis=0); med = np.nanmedian(Xtr, axis=0)
    def prep(X):
        X = np.clip(X, lo, hi); miss = np.isnan(X[:, [F11.index("w_vs200")]]).astype(float); X = np.where(np.isnan(X), med, X)
        return np.hstack([X, miss])
    A, T_ = prep(Xtr), prep(Xte); mu, sd = A.mean(0), A.std(0) + 1e-9
    lr = LogisticRegression(C=1.0, max_iter=2000).fit((A - mu) / sd, ytr)
    return lr.predict_proba((T_ - mu) / sd)[:, 1], dict(zip(F11 + ["vs200_missing"], np.round(lr.coef_[0], 4).tolist()))


def m2():
    return HistGradientBoostingClassifier(learning_rate=0.05, max_iter=200, max_leaf_nodes=15, min_samples_leaf=1000, l2_regularization=1.0,
                                          early_stopping=False, random_state=SEED)


out, imp, coefs, t0 = [], {}, {}, time.time()
for t, endc in TG.items():
    V = S[S[t].notna() & (S.date >= "2018-01-02")]
    splits = [(str(Y), (V[endc] < f"{Y}-01-01"), (V.date.str[:4] == str(Y))) for Y in range(2021, 2026)]
    splits.append(("q3", (V[endc] <= "2026-06-30"), (V.date >= "2026-07-01") & (V.date <= "2026-09-30")))
    for name, mtr, mte in splits:
        tr, te = V[mtr], V[mte]
        ytr, yte = tr[t].values.astype(int), te[t].values.astype(int)
        p1, cf = m1_fit_predict(tr[F11].values.astype(float), ytr, te[F11].values.astype(float)); coefs[f"{t}/{name}"] = cf
        mod = m2().fit(tr[FFULL].values, ytr); p2 = mod.predict_proba(te[FFULL].values)[:, 1]
        o = te[["sym", "date", "i", "kind", "base_" + t]].copy(); o.columns = ["sym", "date", "i", "kind", "base"]
        o["target"], o["split"], o["y"], o["p_m1"], o["p_m2"] = t, ("wf" if name != "q3" else "q3"), yte, p1, p2; o["fold"] = name
        out.append(o)
        if name != "q3" and CTRL is None:
            pi = permutation_importance(mod, te[FFULL].values, yte, scoring="roc_auc", n_repeats=3, random_state=SEED, max_samples=min(20000, len(te)))
            for f, mval in zip(FFULL, pi.importances_mean):
                imp.setdefault(t, {}).setdefault(f, []).append(float(mval))
        print(t, name, "訓練", len(tr), "測試", len(te), "秒", round(time.time() - t0), flush=True)
P = pd.concat(out, ignore_index=True)
P.to_pickle(PFX + "_preds.pkl")
json.dump({"control": CTRL, "features_m2": FFULL, "features_m1": F11, "m1_coef": coefs,
           "perm_importance_mean_auc_drop": {t: dict(sorted(((f, round(float(np.mean(v)), 5)) for f, v in d.items()), key=lambda x: -x[1])) for t, d in imp.items()}},
          open(PFX + "_meta.json", "w"), ensure_ascii=False, indent=1)
print("完成,共", len(P), "筆預測")
