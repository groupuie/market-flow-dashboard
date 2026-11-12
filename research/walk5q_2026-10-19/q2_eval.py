#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q2:成績(規則寫在 PROTOCOL_q.md,跑之前就固定)
- AUC 的 95% 區間:以「交易日」為單位的環狀區塊重抽(相鄰幾天的答案會重疊,所以整段一起抽);逐年往前 L = 20 天、考試期 L = 10 天;4,000 次
- E1(主要):逐年往前 2021–2025 合併的 AUC;下界 > 0.5 → 圖裡有可學的訊號
- E2:2026-07~09 考試期 AUC
- E3:和 walk4 判讀者比(同一批圖、同一組重抽、算差)
- E4:前一成 vs 同檔前後 10 天基準、每天橫向挑前一成、同一天內的排序力、校準、各型態、各年、特徵重要性
用法:python3 -I q2_eval.py OUT_PREFIX WALK4_DIR RESULT.json"""
import json, math, os, sys
import numpy as np, pandas as pd

PFX, W4, RES = sys.argv[1], sys.argv[2], sys.argv[3]
P = pd.read_pickle(PFX + "_preds.pkl"); META = json.load(open(PFX + "_meta.json")); CTRL = META.get("control")
B, SEED = 4000, 20261019


class Boot:
    """同一組日期重抽,套到好幾個分數上(可以算差)"""
    def __init__(self, dates, y, scores, L, seed=SEED):
        self.ud, self.di = np.unique(np.asarray(dates), return_inverse=True); self.y = np.asarray(y, float); self.L = L; self.seed = seed
        self.S = {}
        for k, s in scores.items():
            s = np.asarray(s, float); o = np.argsort(s, kind="mergesort"); ss = s[o]
            g = np.concatenate([[0], np.cumsum(ss[1:] != ss[:-1])]); self.S[k] = (o, g, int(g[-1]) + 1)

    def auc(self, k, w=None):
        o, g, ng = self.S[k]; yy = self.y[o]; ww = np.ones(len(o)) if w is None else w[o]
        pos = np.bincount(g, weights=ww * yy, minlength=ng); neg = np.bincount(g, weights=ww * (1 - yy), minlength=ng)
        Pn, Nn = pos.sum(), neg.sum()
        return float("nan") if Pn == 0 or Nn == 0 else float((pos * (np.cumsum(neg) - neg + 0.5 * neg)).sum() / (Pn * Nn))

    def weights(self):
        T = len(self.ud); nb = math.ceil(T / self.L); rng = np.random.default_rng(self.seed)
        for _ in range(B):
            st = rng.integers(0, T, nb); cnt = np.bincount(((st[:, None] + np.arange(self.L)[None, :]) % T).ravel(), minlength=T)
            yield cnt[self.di].astype(float)

    def run(self, pairs=()):
        pt = {k: self.auc(k) for k in self.S}; draws = {k: [] for k in self.S}; dd = {p: [] for p in pairs}
        for w in self.weights():
            a = {k: self.auc(k, w) for k in self.S}
            for k in self.S:
                draws[k].append(a[k])
            for p in pairs:
                dd[p].append(a[p[0]] - a[p[1]])
        ci = lambda v: [round(float(np.nanpercentile(v, 2.5)), 4), round(float(np.nanpercentile(v, 97.5)), 4)]
        return {k: {"AUC": round(pt[k], 4), "95%": ci(draws[k])} for k in self.S}, {f"{a}−{b}": {"差": round(pt[a] - pt[b], 4), "95%": ci(dd[(a, b)])} for a, b in pairs}


def verdict(ci):
    return "有可學的訊號(下界 > 0.5)" if ci[0] > 0.5 else ("反向(上界 < 0.5)" if ci[1] < 0.5 else "沒有證據(區間含 0.5)")


def top_decile(g, score="p_m2"):
    q = g[score].quantile(0.9); top = g[g[score] >= q]; bot = g[g[score] <= g[score].quantile(0.1)]
    daily = g.assign(rk=g.groupby("date")[score].rank(pct=True)); dtop = daily[daily.rk >= 0.9]
    pc = lambda x: round(100 * float(x), 1)
    return {"全部": [len(g), pc(g.y.mean()), pc(g.base.mean())], "最高一成(張數、成功%、同檔前後10天基準%)": [len(top), pc(top.y.mean()), pc(top.base.mean())],
            "最低一成": [len(bot), pc(bot.y.mean()), pc(bot.base.mean())], "每天挑最高一成(去掉大盤時機)": [len(dtop), pc(dtop.y.mean()), pc(dtop.base.mean())],
            "最高一成 − 基準(百分點)": round(100 * float(top.y.mean() - top.base.mean()), 1)}


def within_date(g, L, score="p_m2"):
    ds = sorted(g.date.unique()); A = {}
    for d, h in g.groupby("date"):
        if len(h) >= 30 and 0 < h.y.sum() < len(h):
            b = Boot(np.zeros(len(h)), h.y.values, {"s": h[score].values}, L=1); A[d] = b.auc("s")
    a = np.array([A.get(d, np.nan) for d in ds]); ok = ~np.isnan(a); T = len(ds); rng = np.random.default_rng(SEED); v = []
    for _ in range(B):
        st = rng.integers(0, T, math.ceil(T / L)); cnt = np.bincount(((st[:, None] + np.arange(L)[None, :]) % T).ravel(), minlength=T)
        v.append(float((a[ok] * cnt[ok]).sum() / cnt[ok].sum()))
    return {"天數": int(ok.sum()), "平均每天的 AUC": round(float(np.nanmean(a)), 4), "95%": [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]}


R = {"control": CTRL, "B": B, "seed": SEED}
for t in ("T1b", "T1s", "T2b", "T2s"):
    o = {}
    for split, L in (("wf", 20), ("q3", 10)):
        g = P[(P.target == t) & (P.split == split)]
        auc, diff = Boot(g.date.values, g.y.values, {"M1": g.p_m1.values, "M2": g.p_m2.values}, L=L).run(pairs=(("M2", "M1"),))
        o[split] = {"張數": len(g), "天數": int(g.date.nunique()), "成功率%": round(100 * float(g.y.mean()), 1), "AUC": auc, "M2−M1": diff["M2−M1"],
                    "判定(M2)": verdict(auc["M2"]["95%"]), "判定(M1)": verdict(auc["M1"]["95%"]), "前一成": top_decile(g)}
        if split == "wf":
            o[split]["同一天內的排序力(M2)"] = within_date(g, L)
            o[split]["各年(M2 AUC、95%)"] = {}
            for y_, h in g.groupby("fold"):
                a_, _ = Boot(h.date.values, h.y.values, {"M2": h.p_m2.values}, L=L).run(); o[split]["各年(M2 AUC、95%)"][y_] = [a_["M2"]["AUC"], a_["M2"]["95%"]]
            dec = pd.qcut(g.p_m2.rank(method="first"), 10, labels=False)
            o[split]["校準(M2 十分位:平均預測%、實際%)"] = [[round(100 * float(g.p_m2[dec == k].mean()), 1), round(100 * float(g.y[dec == k].mean()), 1)] for k in range(10)]
            o[split]["各型態(張數、M2 AUC)"] = {k: [len(h), round(Boot(np.zeros(len(h)), h.y.values, {"s": h.p_m2.values}, L=1).auc("s"), 4)] for k, h in g.groupby("kind") if len(h) >= 200}
    R[t] = o
if CTRL is None:
    R["特徵重要性(打亂後 AUC 掉多少;前 15)"] = {t: dict(list(d.items())[:15]) for t, d in META["perm_importance_mean_auc_drop"].items()}
    # E3:walk4 判讀者(Fable 5.1,第 1–118 回合)和模型在同一批圖上比
    S4 = json.load(open(os.path.join(W4, "data", "sample.json"))); IT = {r["id"]: r for r in S4["items"]}
    LAB = [f"{g + 1}{chr(65 + j)}" for g in range(3) for j in range(8)]; rows = []
    for k, ids in enumerate(S4["rounds"]):
        p = os.path.join(W4, "preds", f"r{k + 1:04d}.json")
        if not os.path.exists(p):
            continue
        A = json.load(open(p))["ans"]
        for lab, i in zip(LAB, ids):
            it = IT[i]; a = A[lab]
            rows.append({"sym": it["sym"], "i": it["idx"], "date": it["date"], "phase": it["phase"], "pb": a["pb"], "ps": a["ps"],
                         "yb4": 1.0 if it["buy"]["r"] == "對" else 0.0, "ys4": 1.0 if it["sell"]["r"] == "對" else 0.0})
    J = pd.DataFrame(rows); e3 = {}
    for t, js, jy in (("T1b", "pb", "yb4"), ("T1s", "ps", "ys4")):
        for name, split, ph, L in (("考試期(2026-07~09)", "q3", "test", 10), ("訓練期裡 2021–2025 的圖(模型用逐年往前的預測)", "wf", "train", 20)):
            g = P[(P.target == t) & (P.split == split)][["sym", "i", "y", "p_m1", "p_m2"]]
            m = J[J.phase == ph].merge(g, on=["sym", "i"], how="inner")
            agree = float((m.y == m[jy]).mean()) if len(m) else float("nan")
            auc, diff = Boot(m.date.values, m.y.values, {"判讀者": m[js].values, "M1": m.p_m1.values, "M2": m.p_m2.values}, L=L).run(
                pairs=(("判讀者", "M2"), ("判讀者", "M1"), ("M2", "M1")))
            e3[f"{t} {name}"] = {"張數": len(m), "答案和 walk4 一致%": round(100 * agree, 2), "AUC": auc, "差": diff}
    R["E3 判讀者 vs 模型(同一批圖)"] = e3
json.dump(R, open(RES, "w"), ensure_ascii=False, indent=1)
print(json.dumps({t: {s: {"AUC": R[t][s]["AUC"], "判定": R[t][s]["判定(M2)"]} for s in ("wf", "q3")} for t in ("T1b", "T1s", "T2b", "T2s")}, ensure_ascii=False, indent=1))
