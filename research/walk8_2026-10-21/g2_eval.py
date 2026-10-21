#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk8 G2:成績(規則在 PROTOCOL_W8.md,跑之前寫好)
A. 模型(g1_models.py 的預測):同一天內 AUC、和 M2 的差(同一批列、以月為區塊成對重抽 2,000 次)
   主要 H1:2021–2026、y_dir(只看方向),M2A − M2 的 95% 區間下限 > 0
B. 事件研究(不用學;2016-10 ~ 2026-09 全部):
   主要 H2:財報反應延續 —— 財報反應知道的那天(反應日的下一個交易日收盤),EAR ÷ 波動 和「之後 20 天超額報酬」的排序相關;
           每個月一組 → 月 IC 的 t 檢定(Fama-MacBeth),單邊 p(> 0) < 0.025
   次要:SUE 延續、反應日跳空、內部人群買(60 天內 ≥ 2 人在公開市場買進,第一次成立那天)、8-K 各類消息、空單量比例、預估財報落在之後 20 天內
   超額報酬 = 之後 20 天報酬 − 同一天名單內全部股票的平均
用法:python3 -I g2_eval.py OUT_DIR W7_DIR TAG(real / dev / check;check = 答案換成亂數,只檢查事件研究的程式)"""
import gzip, json, os, sys
import numpy as np, pandas as pd
from scipy import stats

OUT, W7, TAG = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, W7); from w5_stats import auc, date_stats  # noqa: E402
S = pd.read_pickle(os.path.join(W7, "out", "S7.pkl"))[["sym", "date", "year", "buy", "sell", "d20", "r20"]]
X = pd.read_pickle(os.path.join(OUT, "out", "X8.pkl"))
S["y_buy"] = (S.buy == 1).astype(int); S["y_sell"] = (S.sell == 1).astype(int); S["y_dir"] = S.d20
S["ex20"] = S.r20 - S.groupby("date").r20.transform("mean"); S["month"] = S.date.str[:7]
if TAG == "check":   # 只檢查事件研究的程式能不能跑:答案換成亂數(不看真的結果)
    rng0 = np.random.default_rng(0); S["ex20"] = rng0.normal(0, 0.05, len(S)); S["r20"] = S.ex20
    S["y_dir"] = np.where(S.d20.isna(), np.nan, rng0.integers(0, 2, len(S))); S["y_buy"] = rng0.integers(0, 2, len(S))
TGT = {"y_buy": "p_buy", "y_sell": "p_sell", "y_dir": "p_dir"}; R = {"tag": TAG}


def month_sums(score, y, dates):
    g = date_stats(score, y, dates); m = g.index.astype(str).str[:7]
    return g.U.groupby(m).sum(), g.w.groupby(m).sum()


def paired(scA, scB, y, dates, reps=2000, seed=11):
    UA, W = month_sums(scA, y, dates); UB, _ = month_sums(scB, y, dates); M = UA.index.values; UB = UB.reindex(M).values; UA = UA.values; W = W.reindex(M).values
    rng = np.random.default_rng(seed); a, b, dlt = [], [], []
    for _ in range(reps):
        k = rng.integers(0, len(M), len(M)); w = W[k].sum(); a.append(UA[k].sum() / w); b.append(UB[k].sum() / w); dlt.append(a[-1] - b[-1])
    q = lambda v: [round(float(np.quantile(v, 0.025)), 4), round(float(np.quantile(v, 0.975)), 4)]
    return {"A": round(float(UA.sum() / W.sum()), 4), "A 95%": q(a), "B": round(float(UB.sum() / W.sum()), 4), "差": round(float((UA.sum() - UB.sum()) / W.sum()), 4), "差 95%": q(dlt),
            "差 p(≤ 0)": round(float((np.array(dlt) <= 0).mean()), 4), "月數": int(len(M))}


# ---------- A. 模型
P = {}
for m in ("M2", "M2E", "M2N", "M2F", "M2A", "A0"):
    p = os.path.join(OUT, "out", f"pred8_{m}_{TAG}.pkl")
    if os.path.exists(p):
        P[m] = pd.read_pickle(p)
if P:
    R["模型"] = {}
    base = P["M2"]
    for per, yrs in (("2021–2026", range(2021, 2027)), ("2019–2020", range(2019, 2021)), ("POST 2026-07~09", None), ("dev 2018", [2018])):
        rows = base.index[base.year.isin(list(yrs))] if yrs is not None else base.index[S.loc[base.index, "date"].values >= "2026-07-01"]
        if len(rows) < 1000:
            continue
        o = {}
        for m in P:
            if m == "M2":
                continue
            o[m] = {}
            for t, c in TGT.items():
                yv = S.loc[rows, t].values.astype(float); ok = ~np.isnan(yv); rr = rows[ok]
                o[m][t] = paired(P[m].loc[rr, c].values, base.loc[rr, c].values, yv[ok].astype(int), S.loc[rr, "date"].values)
        R["模型"][per] = o
        print(per, {m: {t: (v["A"], v["B"], v["差"], v["差 95%"]) for t, v in d_.items()} for m, d_ in o.items()}, flush=True)
    R["模型 各年(y_dir 同一天內 AUC)"] = {}
    for m in P:
        R["模型 各年(y_dir 同一天內 AUC)"][m] = {}
        for yv_ in sorted(P[m].year.unique()):
            rows = P[m].index[P[m].year == yv_]; yy = S.loc[rows, "y_dir"].values.astype(float); ok = ~np.isnan(yy)
            g = date_stats(P[m].loc[rows, "p_dir"].values[ok], yy[ok].astype(int), S.loc[rows, "date"].values[ok])
            R["模型 各年(y_dir 同一天內 AUC)"][m][int(yv_)] = round(float(g.U.sum() / g.w.sum()), 4)

if TAG in ("real", "check"):
    # ---------- B. 事件研究
    def fm_ic(df, x, y, mincount=30):
        ics = []
        for mth, g in df.groupby("month"):
            g = g[[x, y]].dropna()
            if len(g) >= mincount:
                ics.append(stats.spearmanr(g[x], g[y])[0])
        ics = np.array(ics); G = len(ics)
        if G < 6:
            return None
        t = ics.mean() / (ics.std(ddof=1) / np.sqrt(G)); p = float(stats.t.sf(t, G - 1))
        e = ics - ics.mean(); g0 = (e @ e) / G; g1 = (e[1:] @ e[:-1]) / G; nw = ics.mean() / np.sqrt(max(g0 + 2 * 0.5 * g1, 1e-12) / G)   # Newey-West(落後 1 期)
        return {"平均 IC": round(float(ics.mean()), 4), "t": round(float(t), 2), "p(> 0)": round(p, 4), "p(< 0)": round(1 - p, 4), "月數": G, "IC > 0 的月": int((ics > 0).sum()),
                "t(Newey-West 1 期)": round(float(nw), 2), "相鄰月 IC 相關": round(float(np.corrcoef(ics[1:], ics[:-1])[0, 1]), 3)}

    def wm_auc(df, x, y):
        """每個月內的 AUC(合併 U / W)"""
        g = df[[x, y, "month"]].dropna(); g = g[g[y].isin([0, 1])]
        U = W = 0.0
        for _, h in g.groupby("month"):
            n1 = h[y].sum(); n0 = len(h) - n1
            if n1 and n0:
                r = stats.rankdata(h[x]); U += r[h[y].values == 1].sum() - n1 * (n1 + 1) / 2; W += n1 * n0
        return round(U / W, 4) if W else None

    def quint(df, x, y="ex20"):
        g = df[[x, y, "month"]].dropna(); g["q"] = g.groupby("month")[x].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) if len(s) >= 10 else np.nan)
        m = g.groupby("q")[y].mean(); return {int(k): round(100 * float(v), 2) for k, v in m.items()}

    def boot_mean(v, months, reps=2000, seed=3):
        d = pd.DataFrame({"v": v, "m": months}).dropna(); gs = d.groupby("m").v.agg(["sum", "count"]); s_, c_ = gs["sum"].values, gs["count"].values
        rng = np.random.default_rng(seed); bs = []
        for _ in range(reps):
            k = rng.integers(0, len(gs), len(gs)); bs.append(s_[k].sum() / c_[k].sum())
        return {"平均 %": round(100 * float(s_.sum() / c_.sum()), 2), "95%": [round(100 * float(np.quantile(bs, 0.025)), 2), round(100 * float(np.quantile(bs, 0.975)), 2)], "件數": int(c_.sum()), "月數": int(len(gs))}

    EV = pd.read_pickle(os.path.join(OUT, "out", "ea_events.pkl"))
    key = S.reset_index().set_index(["sym", "date"])["index"]
    EV["row"] = [key.get((s, d), np.nan) for s, d in zip(EV.sym, EV.date_kav)]; EV = EV[EV.row.notna()].copy(); EV["row"] = EV.row.astype(int)
    EV = EV.join(S[["y_dir", "y_buy", "ex20", "r20", "month"]], on="row"); EV = EV.join(X[["e_sue"]], on="row")
    R["事件"] = {"H2 財報反應延續(EAR ÷ 波動 → 之後 20 天超額報酬)": {"IC": fm_ic(EV, "earz", "ex20"), "月內 AUC(只看方向)": wm_auc(EV, "earz", "y_dir"),
                                                       "五等分(低 → 高)之後 20 天超額報酬 %": quint(EV, "earz"), "事件數": int(len(EV))},
               "SUE 延續": {"IC": fm_ic(EV, "e_sue", "ex20"), "月內 AUC": wm_auc(EV, "e_sue", "y_dir"), "五等分 %": quint(EV, "e_sue")},
               "反應日跳空": {"IC": fm_ic(EV, "gapz", "ex20"), "五等分 %": quint(EV, "gapz")}}
    # 內部人群買:第一次成立那天
    D = pd.concat([S[["sym", "date", "y_dir", "ex20", "month"]], X[["f_nbuy60", "e_in20", "f_srz", "f_sr5", "n_502", "n_101", "n_201", "n_203", "n_801", "n_701", "n_neg"]]], axis=1)
    D["prev_nb"] = D.groupby("sym").f_nbuy60.shift(1)
    cl = D[(D.f_nbuy60 >= 2) & (D.prev_nb < 2)]
    R["事件"]["內部人群買(60 天內 ≥ 2 人買進,第一次成立)"] = {"之後 20 天超額報酬": boot_mean(cl.ex20.values, cl.month.values), "先漲 2 個波動的比例 %(同一天全體 → 事件)":
                                                     [round(100 * float(D.y_dir.mean()), 1), round(100 * float(cl.y_dir.mean()), 1)]}
    # 8-K:消息知道的那天(前一天沒有、今天有)
    R["事件"]["8-K 消息(第一次知道那天)"] = {}
    for k_, nm in (("n_502", "高層異動 5.02"), ("n_101", "重大合約 1.01"), ("n_201", "完成併購 / 處分 2.01"), ("n_203", "舉債 2.03"), ("n_801", "其他重大事件 8.01"), ("n_701", "Reg FD 7.01"), ("n_neg", "負面(重組、減損、重編、下市通知…)")):
        D["_p"] = D.groupby("sym")[k_].shift(1); ev = D[(D[k_] == 1) & (D._p == 0)]
        R["事件"]["8-K 消息(第一次知道那天)"][nm] = boot_mean(ev.ex20.values, ev.month.values)
    # 空單量比例、財報前
    R["事件"]["空單量 z(5 天 vs 60 天)→ 超額報酬"] = fm_ic(D, "f_srz", "ex20", 200)
    R["事件"]["空單量比例(5 天)→ 超額報酬"] = fm_ic(D, "f_sr5", "ex20", 200)
    g = D.dropna(subset=["e_in20", "y_dir"]); a_ = g.groupby(["date", "e_in20"]).y_dir.mean().unstack()
    diff = (a_[1.0] - a_[0.0]).dropna(); mm = diff.groupby(diff.index.str[:7]).mean()
    R["事件"]["財報落在之後 20 天內:先漲比例差(百分點,同一天比較)"] = {"平均": round(100 * float(diff.mean()), 2), "t(以月)": round(float(mm.mean() / (mm.std(ddof=1) / np.sqrt(len(mm)))), 2), "月數": int(len(mm))}
json.dump(R, open(os.path.join(OUT, "out", f"w8_{TAG}.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(R.get("事件", {}), ensure_ascii=False)[:3000])
