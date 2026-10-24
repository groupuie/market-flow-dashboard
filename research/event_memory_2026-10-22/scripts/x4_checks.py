#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兩個開發檢查(沒有預先登記;不判斷任何方法的好壞,只檢查「答案算得對不對」與「主檢定會不會亂報顯著」):
1) 答案重算(replay):從原始日K用另一種寫法(逐列迴圈、ATR 逐根加總)重算 FL3_A20 / FL3_A60 / FL3_FIX2,
   抽 5,000 列(種子 20261022)和 x2 的向量版比,並核對「第 i 根 K 的日期 = 決定日」、e = 第 i+1 根開盤。
2) 虛無模擬(null simulation):2021–2025 財報事件窗,R(邏輯迴歸)當底,做兩組「同分布」的假 Claude 預測 B、C
   (在 logit 上各自加:日期共用雜訊 + 事件共用雜訊 + 單列雜訊,B、C 各抽一次),真實差距 = 0。
   每一季、每一年各做一次檢定,看 5% 門檻下多常誤報:獨立 t、事件群 t、日期群 t(自由度 G−1)、日期層級正負號翻轉(999 次)。
   同時量「B、C 預測差多少(RMS)」對應的一季標準誤,換算看出 Brier 差 0.002 / 0.005 要幾季(80% 功效)。
用法:python3 -I x4_checks.py SCRATCH   → SCRATCH/em/out/x4_checks.json"""
import gzip, json, os, pickle, sys
import numpy as np, pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression

ROOT = sys.argv[1]; OUT = os.path.join(ROOT, "em", "out")
FL = pd.read_pickle(os.path.join(OUT, "fl3_rows.pkl"))
B = pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz")))["bars"]
res = {"說明": "開發檢查,不是檢定;不看任何 Claude 判讀"}

# ---------- 1) 答案重算 ----------
rng = np.random.default_rng(20261022)
samp = FL.iloc[rng.choice(len(FL), 5000, replace=False)]
bad = {"日期不符": 0, "FL3_A20": 0, "FL3_A60": 0, "FL3_FIX2": 0, "A 是空值(跳過)": 0}


def atr_loop(h, l, c, i, w):
    s = 0.0
    for j in range(i - w + 1, i + 1):
        tr = (h[j] - l[j]) if j == 0 else max(h[j], c[j - 1]) - min(l[j], c[j - 1])
        s += tr
    return s / w


def fl3_loop(o, h, l, c, i, A):
    e = o[i + 1]
    for k in (1, 2, 3):
        j = i + k
        if l[j] <= e - A:
            return 0
        if c[j] >= e + A:
            return 1
    return 0


for r in samp.itertuples():
    b = B[r.sym]; x = b["x"]; o, h, l, c = x[:, 0], x[:, 1], x[:, 2], x[:, 3]; i = int(r.i)
    if b["d"][i] != r.date:
        bad["日期不符"] += 1; continue
    if i < 59:
        bad["A 是空值(跳過)"] += 1; continue
    for nm, A in (("FL3_A20", atr_loop(h, l, c, i, 20)), ("FL3_A60", atr_loop(h, l, c, i, 60)), ("FL3_FIX2", 0.02 * o[i + 1])):
        if fl3_loop(o, h, l, c, i, A) != int(getattr(r, nm)):
            bad[nm] += 1
res["1 答案重算(抽 5,000 列)"] = {"不符筆數": bad, "說明": "ATR 用逐根迴圈重算;決定日 = 第 i 根 K 的日期;e = 第 i+1 根開盤;同一天先看最低再看收盤"}
print(res["1 答案重算(抽 5,000 列)"], flush=True)

# ---------- 2) 虛無模擬 ----------
S = pd.read_pickle(os.path.join(ROOT, "w7", "out", "S7.pkl"))[["a", "atr5_20", "atr20_60", "q_a", "r5", "r20", "dma50", "rsi14", "q_r20", "end20"]]
D = FL.join(S); D = D[D.ev_lag >= 0].copy()
for k in range(5):
    D[f"lag{k}"] = (D.ev_lag == k).astype(float)
X = np.c_[np.log(D.a), D.atr5_20, D.atr20_60, np.log(D.q_a), D.r5, D.r20, D.dma50, D.rsi14 / 100, D.q_r20, D[[f"lag{k}" for k in range(1, 5)]].values]
ok = np.isfinite(X).all(1)
tr = ok & (D.end20 < "2021-01-01").values; te = ok & (D.date >= "2021-01-01").values & (D.date <= "2025-12-31").values
ev_key = (D.sym + "_" + D.ev_r.astype(str)).values
ev_date = pd.Series(D.date.values).groupby(ev_key).transform("min").values   # 事件的第一個決定日 ≈ 反應日
qtr = pd.PeriodIndex(pd.to_datetime(ev_date), freq="Q").astype(str)
yr = pd.Series(ev_date).str[:4].values


def logit(p):
    return np.log(p / (1 - p))


def tstats(d, dates, evs):
    n = len(d); m = d.mean()
    se_iid = d.std(ddof=1) / np.sqrt(n)
    out = {"iid": (m / se_iid, np.inf)}
    for nm, g in (("event", evs), ("date", dates)):
        codes, inv = np.unique(g, return_inverse=True); G = len(codes)
        sg = np.bincount(inv, weights=d - m)
        se = np.sqrt(G / (G - 1) * (sg ** 2).sum()) / n
        out[nm] = (m / se, G - 1)
    return out, m


def signflip_p(d, dates, flips):
    codes, inv = np.unique(dates, return_inverse=True)
    sg = np.bincount(inv, weights=d); G = len(sg)
    obs = abs(sg.sum()); sim = np.abs(flips[:, :G] @ sg)
    return (1 + (sim >= obs - 1e-12).sum()) / (1 + len(sim))


flips = rng.choice([-1.0, 1.0], size=(999, 400))
out_all = {}
for lab in ("FL3_A60", "FL3_A20"):
    y = D[lab].values.astype(int)
    mdl = LogisticRegression(max_iter=2000).fit(X[tr], y[tr]); pR = np.clip(mdl.predict_proba(X[te])[:, 1], 1e-4, 1 - 1e-4)
    yt = y[te]; dt = D.date.values[te]; ev = ev_key[te]; qq = qtr[te]; yy = yr[te]
    _, inv_d = np.unique(dt, return_inverse=True); _, inv_e = np.unique(ev, return_inverse=True)
    units = {u: [np.where(keys == k)[0] for k in np.unique(keys)] for u, keys in (("一季", qq), ("一年", yy))}
    lab_out = {"R 的 Brier(測試)": round(float(((pR - yt) ** 2).mean()), 5), "測試列數": int(te.sum())}
    for tau in (0.08, 0.2, 0.4):
        rej = {u: {"iid": 0, "event": 0, "date": 0, "signflip": 0, "n": 0} for u in ("一季", "一年")}
        dbar_q = []; rms = []; se_date_q = []
        for rep in range(200):
            def draw():
                z = 0.5 * tau * rng.standard_normal(inv_d.max() + 1)[inv_d] + 0.5 * tau * rng.standard_normal(inv_e.max() + 1)[inv_e] + 0.7071 * tau * rng.standard_normal(len(pR))
                return 1 / (1 + np.exp(-(logit(pR) + z)))
            pB, pC = draw(), draw()
            d = (pB - yt) ** 2 - (pC - yt) ** 2
            rms.append(float(np.sqrt(((pB - pC) ** 2).mean())))
            for unit, idxs in units.items():
                for m_ in idxs:
                    ts, mean_ = tstats(d[m_], inv_d[m_], inv_e[m_])
                    r_ = rej[unit]; r_["n"] += 1
                    r_["iid"] += abs(ts["iid"][0]) > 1.96
                    r_["event"] += abs(ts["event"][0]) > stats.t.ppf(0.975, ts["event"][1])
                    r_["date"] += abs(ts["date"][0]) > stats.t.ppf(0.975, ts["date"][1])
                    if rep < 50:   # 翻轉檢定比較慢,只做前 50 次
                        r_.setdefault("sf_n", 0); r_["sf_n"] += 1
                        r_["signflip"] += signflip_p(d[m_], inv_d[m_], flips) < 0.05
                    if unit == "一季":
                        dbar_q.append(mean_); se_date_q.append(abs(mean_ / ts["date"][0]) if ts["date"][0] != 0 else np.nan)
        sd_q = float(np.std(dbar_q, ddof=1))
        lab_out[f"雜訊 τ={tau}"] = {
            "B、C 預測差(RMS)": round(float(np.mean(rms)), 4),
            "誤報率 %(一季;5% 門檻)": {k: round(100 * rej["一季"][k] / rej["一季"]["n"], 1) for k in ("iid", "event", "date")} | {"signflip": round(100 * rej["一季"]["signflip"] / rej["一季"]["sf_n"], 1)},
            "誤報率 %(一年;5% 門檻)": {k: round(100 * rej["一年"][k] / rej["一年"]["n"], 1) for k in ("iid", "event", "date")} | {"signflip": round(100 * rej["一年"]["signflip"] / rej["一年"]["sf_n"], 1)},
            "一季的配對差標準差(實際散布)": round(sd_q, 5),
            "日期群標準誤估計(一季,平均)": round(float(np.nanmean(se_date_q)), 5),
            "看出 Brier 差要幾季(80% 功效)": {str(dl): round((2.8 * sd_q / dl) ** 2, 1) for dl in (0.002, 0.005, 0.01)},
            "次數": {"一季檢定": rej["一季"]["n"], "一年檢定": rej["一年"]["n"], "翻轉檢定(一季)": rej["一季"]["sf_n"]}}
        print(lab, tau, json.dumps(lab_out[f"雜訊 τ={tau}"], ensure_ascii=False), flush=True)
    out_all[lab] = lab_out
res["2 虛無模擬(B、C 同分布,真差 = 0)"] = out_all
res["註"] = ("雜訊 = logit 上加 0.5τ 日期共用 + 0.5τ 事件共用 + 0.71τ 單列;B、C 各抽一次。"
            "「實際散布」= 200 次 × 20 季的季平均差的標準差(含季與季之間答案不同)。真實 Claude 的 B、C 差多少,要等試做一天量過。")
json.dump(res, open(os.path.join(OUT, "x4_checks.json"), "w"), ensure_ascii=False, indent=1)
print("寫入 x4_checks.json")
