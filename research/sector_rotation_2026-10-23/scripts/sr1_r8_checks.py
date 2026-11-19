#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SR1 程式 v1.2 更正 + 回應 Codex R8(2026-10-23 18:30:12)的事後核對。協定規則不變;全部是看過 SR1 / SR2 報告之後的診斷。
1) 滾動 120 個月窗口:S0 vs 市場(R8 §3)
2) 2016–2025 對帳:SR1 能定義的列 + R7 式變體(R8 §2)
3) E7「前一半」改成 S0 前 ⌊n/2⌋ 名(v1.1 用百分位 ≥ 0.5,12 產業選了 7 個;R8 §4)
4) F1 / F2 的複合百分位改用精確分數(避免數學上同分、浮點卻不同分;R8 §4)
5) AC1 解析對照:全樣本延後比例的期望、同一期延後數量匹配的期望(R8 §4)
資料、成本、評分期、組合規則都和更正前的 sr1_run_v1.1.py / sr2_run_v1.0.py 相同(函式直接載入);更正後的正式程式是 sr1_run.py v1.2 / sr2_run.py v1.1。
用法:python3 -I sr1_r8_checks.py SCRATCH  → SCRATCH/sr/out/sr1_r8_checks.json"""
import json, os, sys, warnings
from fractions import Fraction
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "sr1_run_v1.1.py"), encoding="utf-8").read().split("# ---------------- 主程式 ----------------")[0]
G = {"__name__": "sr1_lib"}
exec(compile(src, "sr1_run_v1.1.py", "exec"), G)                 # 凍結的 v1.1 程式(更正前)
src2 = open(os.path.join(HERE, "sr2_run_v1.0.py"), encoding="utf-8").read()
exec(compile(src2[src2.index("TRAIN_START ="):src2.index("result = {")], "sr2_run_v1.0.py", "exec"), G)   # SR2 的 leadlag()
EVAL0, LAST, COST, MKT, RF, OUT, SIM0 = (G[k] for k in ("EVAL0", "LAST", "COST", "MKT", "RF", "OUT", "SIM0"))
simulate, topk, stats, diff_test, holm, cum = (G[k] for k in ("simulate", "topk", "stats", "diff_test", "holm", "cum"))
C10 = COST["10bp"]
P = lambda s: pd.Period(s, "M")


class _NoMLP:                     # F1 只需要 Ridge(Q1);MLP 換成空殼省時間,Ridge 是確定性的,結果和原本相同(下面會比對)
    def __init__(self, **kw): pass
    def fit(self, X, y): return self
    def predict(self, X): return np.zeros(len(X))


import sklearn.neural_network as _nn
_nn.MLPRegressor = _NoMLP

orig = pd.read_csv(os.path.join(HERE, "..", "out", "sr1_monthly_v1.1.csv"), index_col=0)
orig.index = pd.PeriodIndex(orig.index, freq="M")
orig_res = json.load(open(os.path.join(HERE, "..", "out", "sr1_results_v1.1.json"), encoding="utf-8"))
orig_sr2 = json.load(open(os.path.join(HERE, "..", "out", "sr2_results_v1.0.json"), encoding="utf-8"))


def ann(r):
    return float((1 + r).prod() ** (12 / len(r)) - 1)


def per(r, a, b):
    return r[(r.index >= P(a)) & (r.index <= P(b))]


def maxdiff(a, b):
    idx = a.index.intersection(b.index); idx = idx[(idx >= EVAL0) & (idx <= LAST)]
    return float(np.max(np.abs(a[idx].values - b[idx].values)))


def picks(wfn, months):
    out = {}
    for t in months:
        w = wfn(t)
        out[t] = None if w is None else tuple(sorted(w))
    return out


def n_changed(pa, pb):
    ev = [t for t in pa if EVAL0 - 1 <= t <= LAST - 1]
    return int(sum(pa[t] != pb.get(t) for t in ev)), len(ev)


# ---------- 精確百分位 ----------
def exact_pct(row):
    v = row.dropna(); n = len(v)
    if n == 0:
        return {}
    rk = v.rank(method="average")                      # 平均名次 = 0.5 的倍數
    return {c: Fraction(int(round(2 * rk[c])), 2 * n) for c in v.index}


def exact_topk(parts, avail_row, cols, k):
    """parts:每個成分一個 pd.Series(同一月);任何成分缺值 → 不能選(同原本 skipna=False);同分照欄位順序"""
    ex = [exact_pct(p) for p in parts]
    sc = {}
    for c in cols:
        if avail_row[c] and all(c in e for e in ex):
            sc[c] = sum((e[c] for e in ex), Fraction(0))
    if len(sc) < k:
        return None, False
    pos = {c: j for j, c in enumerate(cols)}
    order = sorted(sc, key=lambda c: (-sc[c], pos[c]))
    tie_at_cut = len(order) > k and sc[order[k - 1]] == sc[order[k]]
    return {c: 1 / k for c in order[:k]}, tie_at_cut


result = {"說明": "SR1 程式 v1.2 更正 + Codex R8 事後核對;協定規則不變", "評分期": [str(EVAL0), str(LAST)]}

# ---------- 1) 滾動 120 個月 ----------
roll = {}
for nind in (12, 49):
    s, m = orig[f"{nind}|S0"], orig["MKT"]; W = 120; rows = []
    for a in range(len(s) - W + 1):
        rows.append((str(s.index[a]), str(s.index[a + W - 1]), 100 * (ann(s.iloc[a:a + W]) - ann(m.iloc[a:a + W]))))
    d = np.array([r[2] for r in rows]); j = int(np.argmin(d)); jb = int(np.argmax(d))
    roll[f"{nind} 產業"] = {"窗口數": len(rows), "S0 贏市場的窗口": int((d > 0).sum()), "平均年化差(百分點)": round(float(d.mean()), 3),
                          "中位數(百分點)": round(float(np.median(d)), 3), "最差窗口": [rows[j][0], rows[j][1]], "最差年化差(百分點)": round(rows[j][2], 3),
                          "最好窗口": [rows[jb][0], rows[jb][1]], "最好年化差(百分點)": round(rows[jb][2], 3)}
fixed = {}
for nind in (12, 49):
    row = {}
    for lab, (a, b) in {"1975–1984": ("1975-01", "1984-12"), "1985–1994": ("1985-01", "1994-12"), "1995–2004": ("1995-01", "2004-12"),
                        "2005–2014": ("2005-01", "2014-12"), "2015–2024": ("2015-01", "2024-12"), "2025-01 ~ 2026-06(18 個月)": ("2025-01", "2026-06")}.items():
        row[lab] = round(100 * (ann(per(orig[f"{nind}|S0"], a, b)) - ann(per(orig["MKT"], a, b))), 2)
    fixed[f"{nind} 產業 S0 − 市場 年化差(百分點)"] = row
result["1 滾動 120 個月窗口(用 SR1 已報告的 10bp 月報酬;窗口高度重疊,不是獨立次數)"] = roll
result["1b 完整十年分段(原表最後一段 2015–2026-06 是 11.5 年)"] = fixed

# ---------- 2)~4) 每個名單 ----------
bridge, e7out, f1out, f2out = {}, {}, {}, {}
for nind in (12, 49):
    R, BM = G["load"](nind)
    sig = G["signals"](R, BM, nind)
    k = 3 if nind == 12 else 10
    avail = R.notna(); cols = list(R.columns)
    months = [t for t in R.index if SIM0 - 1 <= t <= LAST - 1]

    # S0 重算 = 原本
    s0 = simulate(R, lambda t: topk(sig["S0"].loc[t], avail.loc[t], k), C10, months)[0]
    chk = {"S0 重算和原本的最大月差": maxdiff(s0, orig[f"{nind}|S0"])}

    # ---- 2) 2016–2025 對帳 ----
    def run_window(score, kk, c, mode="direct", terminal=False, a="2016-01", b="2025-12"):
        ms = [t for t in R.index if P(a) - 1 <= t <= P(b) - 1]
        base = lambda t: topk(score.loc[t], avail.loc[t], kk)
        if mode == "direct":
            r = simulate(R, base, c, ms)[0]
        elif mode == "overlap3":                         # 三個重疊組合(t、t−1、t−2 的選擇各 1/3)
            def wf(t):
                ws = [base(t - j) for j in range(3)]
                if any(w is None for w in ws):
                    return None
                out = {}
                for w in ws:
                    for i, v in w.items():
                        out[i] = out.get(i, 0) + v / 3
                return out
            r = simulate(R, wf, c, ms)[0]
        elif mode in ("quarterly", "partial3"):          # 每 3 個月才換一次 / 每月只往目標調三分之一
            w_prev = {}; rets = {}
            for j, t in enumerate(ms):
                tgt = base(t)
                if mode == "quarterly":
                    w = tgt if j % 3 == 0 else dict(w_prev)
                else:
                    w = {i: w_prev.get(i, 0) + (tgt.get(i, 0) - w_prev.get(i, 0)) / 3 for i in set(tgt) | set(w_prev)} if w_prev else tgt
                    w = {i: v for i, v in w.items() if v > 1e-15}
                h = t + 1
                tc = c * sum(abs(w.get(i, 0) - w_prev.get(i, 0)) for i in set(w) | set(w_prev))
                r_i = {i: (R.at[h, i] if pd.notna(R.at[h, i]) else RF[h]) for i in w}
                cash = 1 - sum(w.values()); gross = sum(w[i] * r_i[i] for i in w) + cash * RF[h]
                rets[h] = gross - tc; tot = 1 + gross
                w_prev = {i: w[i] * (1 + r_i[i]) / tot for i in w}
            r = pd.Series(rets)
        Wv = float((1 + r).prod())
        if terminal:
            Wv *= (1 - c)                                   # 結束時全部賣掉:全額投資 → 成本 c × 1
        return round(100 * (Wv ** (12 / len(r)) - 1), 4)

    s0_r7 = cum(R, 12, 2)            # R7:持有月 j 用 j−13 ~ j−3
    k_r7 = 3 if nind == 12 else 12
    rows = {}
    rows["R7 式:j−13~j−3、前 %d 名、三個重疊組合、新開始、末端清算(SR1 成本)" % k_r7] = run_window(s0_r7, k_r7, C10, "overlap3", True)
    rows["R7 式:同上但每 3 個月換一次"] = run_window(s0_r7, k_r7, C10, "quarterly", True)
    rows["R7 式:同上但每月只往目標調 1/3"] = run_window(s0_r7, k_r7, C10, "partial3", True)
    rows["R7 式:直接調整、j−13~j−3、前 %d 名、新開始、末端清算(SR1 成本)" % k_r7] = run_window(s0_r7, k_r7, C10, "direct", True)
    rows["改 SR1 形成月份 j−12~j−2(前 %d 名)、新開始、末端清算" % k_r7] = run_window(sig["S0"], k_r7, C10, "direct", True)
    rows["前 %d 名、新開始、末端清算(R8 的「改SR1近似費用」列)" % k] = run_window(sig["S0"], k, C10, "direct", True)
    rows["前 %d 名、新開始、不扣末端清算(R8 的「取消末端清算費」列)" % k] = run_window(sig["S0"], k, C10, "direct", False)
    rows["SR1 原本(承接 2015-12 的持倉)"] = round(100 * ann(per(orig[f"{nind}|S0"], "2016-01", "2025-12")), 4)
    bridge[f"{nind} 產業"] = rows

    # ---- 3) E7 ----
    def e7_score(mode):
        sc = pd.DataFrame(np.nan, index=R.index, columns=R.columns)
        S0v = sig["S0"].values; Rv = R.values
        for ti in range(len(R.index)):
            ok = ~np.isnan(S0v[ti]); n = int(ok.sum())
            if n == 0:
                continue
            m = n // 2 if mode == "floor" else -(-n // 2)
            order = sorted(np.where(ok)[0], key=lambda j: (-S0v[ti, j], j))[:m]
            for j in order:
                sc.iat[ti, j] = -Rv[ti, j]
        return sc
    e7_old = sig["E7"]
    fn_old = lambda t: topk(e7_old.loc[t], avail.loc[t], k)
    r_old = simulate(R, fn_old, C10, months)[0]
    chk["E7 原本重算和原本的最大月差"] = maxdiff(r_old, orig[f"{nind}|E7"])
    cand_old = int((sig["S0"].rank(axis=1, pct=True) >= 0.5).loc[P("2000-01")].sum())
    E = {"v1.1 候選數(2000-01 例)": cand_old}
    p_old = picks(fn_old, months)
    for mode in (("floor",) if nind == 12 else ("floor", "ceil")):
        scm = e7_score(mode)
        fn = lambda t, scm=scm: topk(scm.loc[t], avail.loc[t], k)
        rr = simulate(R, fn, C10, months)[0]
        ch, nev = n_changed(p_old, picks(fn, months))
        n_c = int(scm.loc[P("2000-01")].notna().sum())
        E[f"v1.2 前 {'⌊n/2⌋' if mode == 'floor' else '⌈n/2⌉'} 名(2000-01 候選 {n_c} 個)"] = {
            "選擇改變的月數": f"{ch} / {nev}", "年化%(原本 → 更正)": [round(100 * ann(per(r_old, '1975-01', '2026-06')), 3), round(100 * ann(per(rr, '1975-01', '2026-06')), 3)],
            "統計": stats(rr), "E7 − S0": diff_test(rr, s0)}
        if mode == "floor":
            e7_fix = rr
    e7out[f"{nind} 產業"] = E
    if nind == 12:   # 次要家族重做 Holm(只換 E7 的 p)
        ps = {n_: v["雙尾 p(區塊自助)"] for n_, v in orig_res["12 產業"]["次要:各規則 − S0"].items()}
        ps_new = dict(ps); ps_new["E7"] = E[[x for x in E if x.startswith("v1.2 前 ⌊n/2⌋")][0]]["E7 − S0"]["雙尾 p(區塊自助)"]
        e7out["12 產業 次要 Holm(E7 換成更正版)"] = holm(ps_new)

    # ---- 4) F1 精確 ----
    ml, _ = G["ml_scores"](R, sig)
    reg = G["regime_sets"]() if nind == 12 else {}
    pct = {n_: sig[n_].rank(axis=1, pct=True) for n_ in ("S0", "E4")}
    mlmonths = [t for t in months if t >= EVAL0 - 1]

    def f1_parts(t):
        if t < EVAL0 - 1 or pd.isna(ml["Q1"].loc[t]).all():
            return None
        parts_raw = [sig["S0"].loc[t], sig["E4"].loc[t], ml["Q1"].loc[t]]
        if nind == 12:
            if t not in reg:
                return None
            parts_raw.append(pd.Series([1.0 if i in reg[t][1] else 0.0 for i in R.columns], index=R.columns))
        return parts_raw

    def f1_float(t):
        pr = f1_parts(t)
        if pr is None:
            return None
        parts = [pct["S0"].loc[t], pct["E4"].loc[t], ml["Q1"].loc[t].rank(pct=True)] + ([pr[3].rank(pct=True)] if nind == 12 else [])
        return topk(pd.concat(parts, axis=1).mean(axis=1, skipna=False), avail.loc[t], k)

    ties = {"n": 0}

    def f1_exact(t):
        pr = f1_parts(t)
        if pr is None:
            return None
        w, tie = exact_topk(pr, avail.loc[t], cols, k)
        if tie and EVAL0 - 1 <= t <= LAST - 1:
            ties["n"] += 1
        return w
    rf_float = simulate(R, f1_float, C10, mlmonths)[0]
    chk["F1 浮點版重算和原本的最大月差(確認 Ridge 重現)"] = maxdiff(rf_float, orig[f"{nind}|F1"])
    ties["n"] = 0; rf_exact = simulate(R, f1_exact, C10, mlmonths)[0]; n_tie1 = ties["n"]
    pf, pe = picks(f1_float, mlmonths), picks(f1_exact, mlmonths)
    ch, nev = n_changed(pf, pe)
    F = {"精確分數在第 k 名剛好同分的月數": n_tie1, "精確 vs 浮點 選擇不同的月數": f"{ch} / {nev}",
         "年化%(浮點 → 精確)": [round(100 * ann(per(rf_float, '1975-01', '2026-06')), 3), round(100 * ann(per(rf_exact, '1975-01', '2026-06')), 3)],
         "統計(精確)": stats(rf_exact), "F1 − S0(精確)": diff_test(rf_exact, s0),
         "F1 − S0(原本報告)": orig_res[f"{nind} 產業"]["主要 H1:F1 − S0"]}
    f1out[f"{nind} 產業" + ("(主要 H1)" if nind == 12 else "(只報告)")] = F

    # ---- 4b) SR2 F2 精確 ----
    q3, _ = G["leadlag"](R, nind)
    m2 = [t for t in R.index if EVAL0 - 1 <= t <= LAST - 1]
    s0b = simulate(R, lambda t: topk(sig["S0"].loc[t], avail.loc[t], k), C10, m2)[0]
    f2f = lambda t: topk(pd.concat([pct["S0"].loc[t], q3.loc[t].rank(pct=True)], axis=1).mean(axis=1, skipna=False), avail.loc[t], k)
    ties["n"] = 0

    def f2e(t):
        w, tie = exact_topk([sig["S0"].loc[t], q3.loc[t]], avail.loc[t], cols, k)
        if tie:
            ties["n"] += 1
        return w
    r2f = simulate(R, f2f, C10, m2)[0]
    q3r = simulate(R, lambda t: topk(q3.loc[t], avail.loc[t], k), C10, m2)[0]
    ties["n"] = 0; r2e = simulate(R, f2e, C10, m2)[0]; n_tie2 = ties["n"]
    ch2, nev2 = n_changed(picks(f2f, m2), picks(f2e, m2))
    F2 = {"精確分數在第 k 名剛好同分的月數": n_tie2, "精確 vs 浮點 選擇不同的月數": f"{ch2} / {nev2}",
          "年化%(浮點 → 精確)": [round(100 * ann(per(r2f, '1975-01', '2026-06')), 3), round(100 * ann(per(r2e, '1975-01', '2026-06')), 3)],
          "F2 − S0(浮點重算)": diff_test(r2f, s0b), "F2 − S0(精確)": diff_test(r2e, s0b),
          "F2 − S0(原本報告)": orig_sr2[f"{nind} 產業"]["F2 − S0"]}
    if nind == 49:
        F2["主要家族 Holm(精確 F2)"] = holm({"Q3": orig_sr2["49 產業"]["Q3 − S0"]["雙尾 p(區塊自助)"], "F2": F2["F2 − S0(精確)"]["雙尾 p(區塊自助)"]})
    F2["Q3 重算年化%(確認 LASSO 重現)"] = round(100 * ann(per(q3r, '1975-01', '2026-06')), 3)
    f2out[f"{nind} 產業" + ("(SR2 主要)" if nind == 49 else "(只報告)")] = F2
    result[f"檢查 {nind} 產業"] = chk

    # ---- 5) AC1 解析對照(只做 12 產業,同原本) ----
    if nind == 12:
        rows = []; plan = []
        starts = [t for t in R.index if EVAL0 <= t and t + 6 <= LAST and t <= P("2025-12")]
        for t in starts:
            w = topk(sig["S0"].loc[t], avail.loc[t], k)
            if w is not None:
                plan.extend(R.at[t + 1, i] >= 0 for i in w)
        p = float(np.mean(plan))
        for t in starts:
            w = topk(sig["S0"].loc[t], avail.loc[t], k)
            if w is None:
                continue
            m_t = sum(R.at[t + 1, i] >= 0 for i in w)     # 這一期 A3 實際延後的產業數
            a1 = a2 = a3 = cp = cm = 0.0
            for i in w:
                r = [R.at[t + j, i] for j in range(1, 7)]; rf = [RF[t + j] for j in range(1, 7)]
                g = lambda s: float(np.prod([1 + x for x in r[s:]]))
                cash = lambda s: float(np.prod([1 + x for x in rf[:s]]))
                a1 += g(0) / k
                a2 += (g(0) + cash(1) * g(1) + cash(2) * g(2)) / 3 / k
                second = 1 if r[0] < 0 else 2
                a3 += (g(0) + cash(second) * g(second) + cash(2) * g(2)) / 3 / k
                cp += (g(0) + (1 - p) * cash(1) * g(1) + p * cash(2) * g(2) + cash(2) * g(2)) / 3 / k
                q = m_t / k
                cm += (g(0) + (1 - q) * cash(1) * g(1) + q * cash(2) * g(2) + cash(2) * g(2)) / 3 / k
            rows.append((t, a1 - 1, a2 - 1, a3 - 1, cp - 1, cm - 1))
        D = pd.DataFrame(rows, columns=["t", "A1", "A2", "A3", "A3p", "A3m"]).set_index("t")
        D.index = pd.PeriodIndex(D.index, freq="M")
        result["5 AC1 解析對照(事後診斷,不是新的確認性檢定)"] = {
            "組數": int(len(D)), "全樣本延後比例 p": round(p, 4),
            "平均 6 個月報酬%": {c: round(100 * D[c].mean(), 4) for c in D.columns},
            "A3 − A3p(全樣本比例的期望;事後匹配)": diff_test(D["A3"], D["A3p"]),
            "A3 − A3m(同一期延後數量匹配的期望)": diff_test(D["A3"], D["A3m"]),
            "A3 − A3m(4,000 次,對照 R8)": diff_test(D["A3"], D["A3m"], reps=4000),
            "原本 A3 − A3r(單一亂數)": orig_res["12 產業"]["AC1 分批逢低"]["A3 − A3r(只報告)"]}

result["2 2016–2025 對帳(年化%,4 位小數;SR1 成本 10bp)"] = bridge
result["3 E7 更正"] = e7out
result["4 F1 精確分數"] = f1out
result["4b SR2 F2 精確分數"] = f2out
json.dump(result, open(os.path.join(OUT, "sr1_r8_checks.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(result, ensure_ascii=False, indent=1, default=str)[:12000])
