#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk6 L2b:長線盤感的成績 —「跳著試驗」版(規則 PROTOCOL_L.md,跑之前寫好)
決定點彼此不重疊:看 h 個月,就每 h 個月才判一次(1 個月 = 每月底;3 個月 = 3/6/9/12 月底;6 個月 = 6/12 月底;12 個月 = 12 月底;24 個月 = 偶數年 12 月底)
→ 每一期的答案不會重疊,期和期之間大致獨立,用「期數 − 1」當自由度的 t 檢定就站得住
- 規則(不用學):順勢 12 個月 r12m > 0、順勢 12-1 r12_1 > 0、站上 200 日線 vs200 > 0、靠近 52 週高 hi52 > −5%、短線反轉(上個月跌)r1m < 0
- ETF 擇時(主要 H1 = 12 個月、順勢 12 個月):之後報酬 = 每檔自己的平均 + β ×(+1 / −1);每檔扣掉自己的平均、同一期的誤差算在一起(以期為群)
- 個股挑股(主要 H2 = 12 個月、順勢 12-1):每一期橫向排序相關(Spearman),取平均,t 檢定(Fama-MacBeth)
- 個股擇時:同 ETF 擇時的做法;個股 M2(逐年往前)只做次要
用法:python3 -I l2b_eval.py SCEN.pkl OUT.json [--placebo N]   (--placebo:用 N 條沒有資訊的假分數校準 H1 / H2 的誤報率)"""
import json, math, sys
import numpy as np, pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor

SC, OUT = sys.argv[1], sys.argv[2]
NPL = int(sys.argv[sys.argv.index("--placebo") + 1]) if "--placebo" in sys.argv else 0
SEED, START = 20261020, "2005-12-01"
HZ = {"m1": (21, None), "m3": (63, ("03", "06", "09", "12")), "m6": (126, ("06", "12")), "m12": (252, ("12",)), "m24": (504, ("12",))}
RULE = {"順勢12個月": ("r12m", 0.0), "順勢12-1": ("r12_1", 0.0), "站上200日線": ("vs200", 0.0), "靠近52週高": ("hi52", -0.05), "短線反轉": ("neg_r1m", 0.0)}
FL = ["r1m", "r3m", "r6m", "r12m", "r24m", "r36m", "r12_1", "vs200", "vs50", "ma50_200", "sl200", "hi52", "lo52", "ath_dd", "vol3m", "vol12m", "volr", "mdd12m", "vr",
      "q_r12m", "q_r6m", "q_vs200", "q_vol3m", "q_hi52", "rs12m", "rs6m"]
S = pd.read_pickle(SC); S["neg_r1m"] = -S.r1m


def pick(h):
    hd, mons = HZ[h]; V = S[S["f_" + h].notna() & (S.date >= START)].copy()
    if mons:
        V = V[V.date.str[5:7].isin(mons)]
    if h == "m24":
        V = V[V.date.str[:4].astype(int) % 2 == 0]
    return V


def panel_timing(g, x, y):
    """y = a_i + β x + e(每檔自己的平均先扣掉),以期為群的穩健標準誤;回傳 β、t、p(單邊 β > 0)、群數"""
    d = g[["sym", "date"]].copy(); d["x"] = x; d["y"] = y; d = d.dropna()
    d = d[d.groupby("sym").x.transform("std") > 0]
    if d.empty:
        return None
    d["xt"] = d.x - d.groupby("sym").x.transform("mean"); d["yt"] = d.y - d.groupby("sym").y.transform("mean")
    sxx = float((d.xt ** 2).sum()); b = float((d.xt * d.yt).sum() / sxx); d["u"] = d.xt * (d.yt - b * d.xt)
    G = d.date.nunique(); su = d.groupby("date").u.sum().values; V = (su ** 2).sum() / sxx ** 2 * G / (G - 1)
    t = b / math.sqrt(V); p = float(stats.t.sf(t, G - 1))
    return {"β": round(b, 4), "t": round(t, 2), "p(β > 0)": round(p, 4), "p(β < 0)": round(1 - p, 4), "期數": G, "標的數": int(d.sym.nunique()), "張數": len(d)}


def fm_ic(g, s, y):
    ic = []
    for _, h in g.assign(s=s, y=y).groupby("date"):
        h = h[["s", "y"]].dropna()
        if len(h) >= 30:
            ic.append(stats.spearmanr(h.s, h.y)[0])
    ic = np.array(ic); G = len(ic)
    if G < 3:
        return None
    t = ic.mean() / (ic.std(ddof=1) / math.sqrt(G)); p = float(stats.t.sf(t, G - 1))
    return {"平均 IC": round(float(ic.mean()), 4), "t": round(float(t), 2), "p(> 0)": round(p, 4), "p(< 0)": round(1 - p, 4), "期數": G, "IC 為正的期數": int((ic > 0).sum())}


def verdict(r, key_hi, key_lo):
    if r is None:
        return "資料不夠"
    return "有方向(p < 0.025)" if r[key_hi] < 0.025 else ("反向(p < 0.025)" if r[key_lo] < 0.025 else "沒有證據")


if NPL:   # 校準:假分數(月 AR(1) ρ = 0.92,一半共同、一半各自)→ H1(符號)與 H2(連續)的誤報率
    M = np.array(sorted(S.date.unique())); mi = {m: k for k, m in enumerate(M)}; syms = sorted(S.sym.unique()); si = {s: k for k, s in enumerate(syms)}
    rI, cI = np.array([si[s] for s in S.sym]), np.array([mi[m] for m in S.date]); rng = np.random.default_rng(SEED + 7)
    V = pick("m12"); E, K = V[V.etf], V[~V.etf]; h1 = []; h2 = []
    for p_ in range(NPL):
        T = len(M); e = math.sqrt(0.5) * rng.standard_normal(T)[None, :] + math.sqrt(0.5) * rng.standard_normal((len(syms), T)); x = np.zeros_like(e); x[:, 0] = e[:, 0]
        for t_ in range(1, T):
            x[:, t_] = 0.92 * x[:, t_ - 1] + math.sqrt(1 - 0.92 ** 2) * e[:, t_]
        z = pd.Series(x[rI, cI], index=S.index)
        r1 = panel_timing(E, np.sign(z.loc[E.index].values), E["f_m12"].values); r2 = fm_ic(K, z.loc[K.index].values, K["f_m12"].values)
        h1.append([r1["p(β > 0)"], r1["p(β < 0)"]]); h2.append([r2["p(> 0)"], r2["p(< 0)"]])
    h1, h2 = np.array(h1), np.array(h2)
    R = {"假分數條數": NPL, "H1 誤報%(有方向 / 反向)": [round(100 * float((h1[:, 0] < 0.025).mean()), 1), round(100 * float((h1[:, 1] < 0.025).mean()), 1)],
         "H2 誤報%(有方向 / 反向)": [round(100 * float((h2[:, 0] < 0.025).mean()), 1), round(100 * float((h2[:, 1] < 0.025).mean()), 1)]}
    json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1); print(json.dumps(R, ensure_ascii=False)); sys.exit(0)

R = {"seed": SEED, "評估起": START, "說明": "跳著試驗:決定點每 h 個月一次、答案不重疊;ETF / 個股擇時 = 固定效果 + 以期為群;個股挑股 = 每期排序相關的 t 檢定"}
for h, (hd, _) in HZ.items():
    V = pick(h); E, K = V[V.etf], V[~V.etf]; y = "f_" + h; o = {"ETF 張數": len(E), "個股張數": len(K), "決定點": f"{V.date.min()} ~ {V.date.max()}"}
    for nm, (sc, th) in RULE.items():
        xe = np.where(E[sc] > th, 1.0, np.where(E[sc].notna(), -1.0, np.nan)); xk = np.where(K[sc] > th, 1.0, np.where(K[sc].notna(), -1.0, np.nan))
        e = panel_timing(E, xe, E[y].values); c = fm_ic(K, K[sc].values, K[y].values); t = panel_timing(K, xk, K[y].values)
        up, dn = E[xe > 0], E[xe < 0]
        o[nm] = {"ETF 擇時": e, "ETF 擇時判定": verdict(e, "p(β > 0)", "p(β < 0)"), "個股挑股": c, "個股挑股判定": verdict(c, "p(> 0)", "p(< 0)"),
                 "個股擇時": t, "個股擇時判定": verdict(t, "p(β > 0)", "p(β < 0)"),
                 "ETF:訊號成立 / 不成立時,之後平均報酬%(張數)": [round(100 * float(np.expm1(up[y]).mean()), 2), len(up), round(100 * float(np.expm1(dn[y]).mean()), 2), len(dn)]}
        if sc == "r12_1":
            K2 = K.assign(q=K.groupby("date")[sc].transform(lambda s_: pd.qcut(s_.rank(method="first"), 5, labels=False) if s_.notna().sum() >= 30 else np.nan))
            per = K2.groupby("date").apply(lambda d_: np.expm1(d_[d_.q == 4][y]).mean() - np.expm1(d_[d_.q == 0][y]).mean()).dropna()
            o[nm]["個股:每期前 1/5 − 後 1/5 平均報酬%(期數、為正的期數)"] = [round(100 * float(per.mean()), 2), len(per), int((per > 0).sum())]
    # 個股 M2(逐年往前;訓練用所有月份,測試只用這個期間的決定點)
    Kall = S[~S.etf & S[y].notna()].copy(); Kall["yy"] = (Kall[y] / (Kall.vol12m * math.sqrt(hd / 252))).clip(-5, 5); P = []
    for Y_ in range(2011, 2026):
        tr = Kall[(Kall["end_" + h] < f"{Y_}-01-01") & Kall.yy.notna()]; te = K[K.date.str[:4] == str(Y_)]
        if te.empty or len(tr) < 2000:
            continue
        m = HistGradientBoostingRegressor(learning_rate=0.05, max_iter=200, max_leaf_nodes=15, min_samples_leaf=200, l2_regularization=1.0, early_stopping=False,
                                          random_state=SEED).fit(tr[FL].values, tr.yy.values)
        P.append(te.assign(m2=m.predict(te[FL].values)))
    if P:
        G_ = pd.concat(P); c = fm_ic(G_, G_.m2.values, G_[y].values); t = panel_timing(G_, np.sign(G_.m2.values), G_[y].values)
        cb = fm_ic(G_, G_.r12_1.values, G_[y].values)
        o["M2(個股,2011 起)"] = {"個股挑股": c, "個股挑股判定": verdict(c, "p(> 0)", "p(< 0)"), "個股擇時": t, "個股擇時判定": verdict(t, "p(β > 0)", "p(β < 0)"), "同一段順勢12-1 挑股": cb}
    R[h] = o
    print(h, " | ".join(f"{nm}:{v.get('ETF 擇時判定', '')[:2]}/{v.get('個股挑股判定', '')[:2]}/{v.get('個股擇時判定', '')[:2]}" for nm, v in o.items() if isinstance(v, dict)), flush=True)
json.dump(R, open(OUT, "w"), ensure_ascii=False, indent=1)
