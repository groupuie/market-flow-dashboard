#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SR2 產業領先落後(協定 PROTOCOL_SR2.md v1.0):LASSO(BIC)用所有產業的當月報酬預測每個產業的下月報酬;和 S0 簡單動能比。
資料、組合、成本、評分期同 SR1(sr1_run.py 的函式直接載入,不重寫)。
程式 v1.1(2026-10-23,回應 Codex R8;協定規則不變,更正前凍結在 sr2_run_v1.0.py):F2 的複合百分位改用精確分數(sr1_run.py 的 exact_rank_topk)。
用法:python3 -I sr2_run.py SCRATCH [--synthetic]   → SCRATCH/sr/out/sr2_results{_synthetic}.json"""
import json, os, sys, warnings
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "sr1_run.py"), encoding="utf-8").read().split("# ---------------- 主程式 ----------------")[0]
G = {"__name__": "sr1_lib"}
exec(compile(src, "sr1_run.py", "exec"), G)                     # 同一份資料讀取、模擬、統計函式
EVAL0, LAST, COST, MKT, RF, SYN, OUT = (G[k] for k in ("EVAL0", "LAST", "COST", "MKT", "RF", "SYN", "OUT"))
TAG = "_synthetic" if SYN else ""
TRAIN_START = {12: pd.Period("1930-01", "M"), 49: pd.Period("1970-01", "M")}


def leadlag(R, nind):
    from sklearn.linear_model import LassoLarsIC
    months = R.index; X = R.values; Y = R.shift(-1).values; cols = list(R.columns)
    pred = pd.DataFrame(np.nan, index=months, columns=cols); nsel = []; r2 = {c: [] for c in cols}
    pos = {t: k for k, t in enumerate(months)}
    for Yr in range(EVAL0.year, LAST.year + 1):
        fit_t = pd.Period(f"{Yr - 1}-12", "M")
        tr = [pos[t] for t in months if TRAIN_START[nind] <= t <= fit_t - 1]
        Xtr, Ytr = X[tr], Y[tr]
        ok = ~np.isnan(Xtr).any(axis=1)
        mu, sd = Xtr[ok].mean(0), Xtr[ok].std(0); sd[sd == 0] = 1
        te = [pos[t] for t in months if fit_t <= t <= fit_t + 11 and t <= LAST - 1]
        Xte = (X[te] - mu) / sd
        for j, c in enumerate(cols):
            m = ok & ~np.isnan(Ytr[:, j])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                mod = LassoLarsIC(criterion="bic").fit((Xtr[m] - mu) / sd, Ytr[m, j])
            nsel.append(int((mod.coef_ != 0).sum()))
            good = ~np.isnan(Xte).any(axis=1)
            p = np.full(len(te), np.nan); p[good] = mod.predict(Xte[good]); pred.iloc[te, j] = p
            hist_mean = float(np.nanmean(Ytr[m, j]))
            for k_, row in enumerate(te):
                y = Y[row, j]
                if not np.isnan(y) and not np.isnan(p[k_]):
                    r2[c].append(((y - p[k_]) ** 2, (y - hist_mean) ** 2))
    r2os = {c: 1 - sum(a for a, b in v) / sum(b for a, b in v) for c, v in r2.items() if v}
    return pred, {"LASSO 平均選了幾個變數": round(float(np.mean(nsel)), 2), "樣本外 R²(相對訓練期平均)平均%": round(100 * float(np.mean(list(r2os.values()))), 3),
                  "樣本外 R² 中位數%": round(100 * float(np.median(list(r2os.values()))), 3), "樣本外 R² > 0 的產業數": int(sum(v > 0 for v in r2os.values())), "產業數": len(r2os)}


result = {"協定": "PROTOCOL_SR2.md v1.0", "程式": "sr2_run.py v1.1(F2 精確分數)", "合成資料": SYN, "評分期": [str(EVAL0), str(LAST)]}
for nind in (49, 12):
    R, BM = G["load"](nind)
    sig = G["signals"](R, BM, nind)
    q3, info = leadlag(R, nind)
    k = 3 if nind == 12 else 10; avail = R.notna(); months = [t for t in R.index if EVAL0 - 1 <= t <= LAST - 1]
    pct_s0 = sig["S0"].rank(axis=1, pct=True)
    U = {"Q3 資訊": info}
    for ck, c in COST.items():
        res = {"S0": G["simulate"](R, lambda t: G["topk"](sig["S0"].loc[t], avail.loc[t], k), c, months),
               "Q3": G["simulate"](R, lambda t: G["topk"](q3.loc[t], avail.loc[t], k), c, months),
               "F2": G["simulate"](R, lambda t: G["exact_rank_topk"]([sig["S0"].loc[t], q3.loc[t]], avail.loc[t], k), c, months),   # v1.1:精確分數
               "B1": G["simulate"](R, lambda t: (lambda a: {i: 1 / len(a) for i in a})(list(R.columns[avail.loc[t].values])), c, months)}
        U[f"{ck} 每個規則"] = {n: G["stats"](v[0]) for n, v in res.items()}
        if ck == "10bp":
            main = res
    U["市場"] = G["stats"](MKT)
    U["Q3 − S0"] = G["diff_test"](main["Q3"][0], main["S0"][0]); U["F2 − S0"] = G["diff_test"](main["F2"][0], main["S0"][0])
    U["Holm(" + ("主要" if nind == 49 else "只報告") + ")"] = G["holm"]({"Q3": U["Q3 − S0"]["雙尾 p(區塊自助)"], "F2": U["F2 − S0"]["雙尾 p(區塊自助)"]})
    U["對市場(只報告)"] = {n: G["diff_test"](v[0], MKT, reps=2000) for n, v in main.items()}
    sub = {}
    for lab, (a, b) in {"1985-01 ~ 2026-06": ("1985-01", "2026-06"), "2016–2025": ("2016-01", "2025-12")}.items():
        a, b = pd.Period(a, "M"), pd.Period(b, "M"); row = {}
        for n, v in list(main.items()) + [("市場", (MKT, None))]:
            r = v[0]; r = r[(r.index >= a) & (r.index <= b)]
            row[n] = round(100 * (float((1 + r).prod()) ** (12 / len(r)) - 1), 2)
        sub[lab] = row
    sub["1985 起 Q3 − S0"] = G["diff_test"](main["Q3"][0][main["Q3"][0].index >= pd.Period("1985-01", "M")], main["S0"][0])
    U["分段 年化%"] = sub
    U["下月 IC"] = {"S0": G["ic"](sig["S0"], R, 1), "Q3": G["ic"](q3, R, 1)}
    result[f"{nind} 產業"] = U
json.dump(result, open(os.path.join(OUT, f"sr2_results{TAG}.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk in ("Q3 資訊", "Q3 − S0", "F2 − S0")}) for k, v in result.items()}, ensure_ascii=False, indent=1)[:3000])
