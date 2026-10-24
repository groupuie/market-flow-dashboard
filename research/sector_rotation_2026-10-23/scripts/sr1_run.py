#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SR1 板塊輪動(協定 PROTOCOL_SR1.md v1.0):高手規則 × 量化 × 融合;French 12 / 49 產業月報酬;持有月 1975-01 ~ 2026-06。
程式 v1.2(2026-10-23,回應 Codex R8;協定規則不變,更正前的程式凍結在 sr1_run_v1.1.py):
  ① E7「前一半」= S0 前 ⌊n/2⌋ 名(v1.1 用百分位 ≥ 0.5,12 產業選了 7 個);
  ② F1 的複合百分位改用精確分數(v1.1 用浮點平均,數學上同分時會被浮點誤差排出先後,沒有照「同分照欄位順序」)。
用法:python3 -I sr1_run.py SCRATCH [--synthetic]
  SCRATCH/sr/unz/  = French 三個 CSV(解壓後);SCRATCH/sr/raw/ = FRED 四個 CSV
  --synthetic:報酬換成亂數(同樣的日期與欄位),只用來除錯;輸出檔名加 _synthetic
輸出:SCRATCH/sr/out/sr1_results{_synthetic}.json、sr1_monthly{_synthetic}.csv"""
import json, os, sys, warnings
import numpy as np, pandas as pd

ROOT = sys.argv[1]; SYN = "--synthetic" in sys.argv; TAG = "_synthetic" if SYN else ""
UNZ, RAW, OUT = (os.path.join(ROOT, "sr", x) for x in ("unz", "raw", "out")); os.makedirs(OUT, exist_ok=True)
LAST = pd.Period("2026-06", "M"); EVAL0 = pd.Period("1975-01", "M"); SIM0 = pd.Period("1960-01", "M"); TRAIN0 = pd.Period("1955-01", "M")
COST = {"0bp": 0.0, "10bp": 0.001, "25bp": 0.0025}; SEED = 20261023


# ---------------- 資料 ----------------
def french_section(fn, title, annual=False):
    lines = open(os.path.join(UNZ, fn), encoding="latin-1").read().splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip().startswith(title))
    hdr = None; rows = []
    for l in lines[i + 1:]:
        s = l.strip()
        if not s:
            if rows:
                break
            continue
        if s.startswith(","):
            hdr = [c.strip() for c in s.split(",")[1:]]; continue
        parts = [p.strip() for p in l.split(",")]
        if not parts[0].isdigit():
            break
        rows.append([parts[0]] + [float(x) for x in parts[1:]])
    df = pd.DataFrame([r[1:] for r in rows], columns=hdr, index=[r[0] for r in rows])
    df = df.mask(df <= -99.99)
    if annual:
        df.index = df.index.astype(int)
    else:
        df.index = pd.PeriodIndex([f"{x[:4]}-{x[4:]}" for x in df.index], freq="M")
    return df


def fred(sid):
    d = pd.read_csv(os.path.join(RAW, f"fred_{sid}.csv"))
    d.columns = ["date", "v"]; d["v"] = pd.to_numeric(d["v"], errors="coerce")
    return pd.Series(d["v"].values, index=pd.PeriodIndex(pd.to_datetime(d["date"]), freq="M"))


FF = french_section("F-F_Research_Data_Factors.csv", "The annual TBill return")  # 第一段(月)
FF = FF[FF.index <= LAST] / 100
RF, MKT = FF["RF"], FF["Mkt-RF"] + FF["RF"]
MAC = pd.DataFrame({k: fred(k) for k in ("GS10", "TB3MS", "BAA", "AAA")})
MAC = MAC[MAC.index <= LAST]
S_ = MAC["GS10"] - MAC["TB3MS"]; CS_ = MAC["BAA"] - MAC["AAA"]


def load(nind):
    fn = f"{nind}_Industry_Portfolios.csv"
    R = french_section(fn, "Average Value Weighted Returns -- Monthly") / 100
    R = R[R.index <= LAST]
    BM = french_section(fn, "Sum of BE / Sum of ME", annual=True)
    if SYN:
        rng = np.random.default_rng(7 + nind)
        R = pd.DataFrame(rng.normal(0.009, 0.055, R.shape), index=R.index, columns=R.columns).where(R.notna())
    return R, BM


# ---------------- 訊號 ----------------
def cum(R, a, b):
    """月 t−a ~ t−b 的累計報酬(全部有值才算)"""
    L = np.log1p(R); w = a - b + 1
    return np.expm1(L.rolling(w, min_periods=w).sum().shift(b))


def signals(R, BM, nind):
    sig = {}
    sig["S0"] = cum(R, 11, 1)
    sig["E1"] = cum(R, 5, 0)
    L = np.log1p(R); cl = L.fillna(0).cumsum(); ok = R.notna().rolling(12, min_periods=12).sum() == 12
    sig["E4"] = np.exp(cl - cl.rolling(12, min_periods=12).max()).where(ok)
    sig["E5"] = -cum(R, 59, 12)
    sig["E6"] = -cum(R, 2, 0)
    S0v = sig["S0"].values; keep = np.zeros(S0v.shape, bool)       # v1.2:S0 前 ⌊n/2⌋ 名(n = 當月有 S0 的產業數;同分照欄位順序)
    for ti in range(S0v.shape[0]):
        ok = np.where(~np.isnan(S0v[ti]))[0]
        for j in sorted(ok, key=lambda j: (-S0v[ti, j], j))[:len(ok) // 2]:
            keep[ti, j] = True
    sig["E7"] = (-R).where(keep)
    sig["E8"] = cum(R, 5, 0) - cum(R, 11, 6)
    se = pd.DataFrame(np.nan, index=R.index, columns=R.columns)
    for k in range(len(R)):
        lag = [k + 1 - 12 * j for j in range(1, 21) if k + 1 - 12 * j >= 0]
        if len(lag) >= 10:
            v = R.iloc[lag]; n = v.notna().sum()
            se.iloc[k] = v.mean().where(n >= 10)
    sig["E9"] = se
    bm = pd.DataFrame(np.nan, index=R.index, columns=R.columns)
    for t in R.index:
        y = t.year if t.month >= 6 else t.year - 1
        if y in BM.index:
            bm.loc[t] = BM.loc[y].reindex(R.columns).values
    sig["E10"] = bm
    sig["VOL12"] = R.rolling(12, min_periods=12).std()
    sig["R1"] = R; sig["R3"] = cum(R, 2, 0)
    return sig


def regime_sets():
    """E11:用月 t−1 的總經;回傳每個決定月 t 的產業組"""
    S1, C1 = S_.shift(1), CS_.shift(1)
    dS, dC = S1 - S1.shift(6), C1 - C1.shift(6)
    out = {}
    for t in S1.index:
        s, ds, dc = S1.get(t), dS.get(t), dC.get(t)
        if any(pd.isna(x) for x in (s, ds, dc)):
            continue
        if s < 0.5 or dc > 0.5:
            out[t] = ("放緩", ["NoDur", "Utils", "Hlth", "Telcm"])
        elif s >= 1.5 and ds > 0 and dc <= 0:
            out[t] = ("初升", ["Durbl", "Shops", "Money", "BusEq"])
        elif ds < 0:
            out[t] = ("末升", ["Enrgy", "Chems", "Manuf", "NoDur"])
        else:
            out[t] = ("中段", ["BusEq", "Manuf", "Chems", "Money"])
    return out


# ---------------- Ridge / MLP ----------------
def ml_scores(R, sig):
    from sklearn.linear_model import Ridge
    from sklearn.neural_network import MLPRegressor
    from sklearn.exceptions import ConvergenceWarning
    feats = ["R1", "R3", "E1", "S0", "E4", "E5", "E9", "VOL12", "E10"]
    Z = {}
    for f in feats:
        x = sig[f]; Z[f] = x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0)
    S1, C1 = S_.shift(1), CS_.shift(1); dC = C1 - C1.shift(6)
    Sz = (S1 - S1.expanding(24).mean()) / S1.expanding(24).std(); dCz = (dC - dC.expanding(24).mean()) / dC.expanding(24).std()
    months = R.index
    X = {}
    for t in months:
        cols = [Z[f].loc[t].values for f in feats]
        sz = Sz.get(t, np.nan); dz = dCz.get(t, np.nan)
        cols.append(Z["S0"].loc[t].values * (0 if pd.isna(sz) else sz)); cols.append(Z["S0"].loc[t].values * (0 if pd.isna(dz) else dz))
        X[t] = np.nan_to_num(np.column_stack(cols), nan=0.0)
    nxt = R.shift(-1); Y = nxt.sub(nxt.mean(axis=1), axis=0)
    avail = R.notna() & sig["S0"].notna()
    out = {"Q1": pd.DataFrame(np.nan, index=months, columns=R.columns), "Q2": pd.DataFrame(np.nan, index=months, columns=R.columns)}
    nconv = 0; nfit = 0
    for Yr in range(EVAL0.year, LAST.year + 1):
        fit_t = pd.Period(f"{Yr - 1}-12", "M")
        tr = [t for t in months if TRAIN0 <= t <= fit_t - 1]
        Xs, ys = [], []
        for t in tr:
            m = avail.loc[t].values & Y.loc[t].notna().values
            if m.any():
                Xs.append(X[t][m]); ys.append(Y.loc[t].values[m])
        Xs, ys = np.vstack(Xs), np.concatenate(ys)
        rid = Ridge(alpha=10.0).fit(Xs, ys)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", ConvergenceWarning)
            mlp = MLPRegressor(hidden_layer_sizes=(32, 16), alpha=1e-3, learning_rate_init=1e-3, max_iter=500, random_state=622).fit(Xs, ys)
            nconv += sum(1 for x in w if issubclass(x.category, ConvergenceWarning))
        nfit += 1
        for t in [t for t in months if fit_t <= t <= fit_t + 11 and t <= LAST - 1]:
            m = avail.loc[t].values
            if m.any():
                out["Q1"].loc[t, R.columns[m]] = rid.predict(X[t][m]); out["Q2"].loc[t, R.columns[m]] = mlp.predict(X[t][m])
    return out, {"年度訓練次數": nfit, "MLP 沒收斂次數": nconv}


# ---------------- 組合 ----------------
def simulate(R, weights_fn, cost, months):
    """weights_fn(t) → dict 產業 → 權重(總和 ≤ 1,其餘 RF);回傳持有月 t+1 的淨報酬"""
    w_prev = {}; rets = {}; turn = {}
    for t in months:
        w = weights_fn(t)
        if w is None:
            continue
        h = t + 1
        tc = cost * sum(abs(w.get(i, 0) - w_prev.get(i, 0)) for i in set(w) | set(w_prev))
        r_i = {i: (R.at[h, i] if pd.notna(R.at[h, i]) else RF[h]) for i in w}
        cash = 1 - sum(w.values())
        gross = sum(w[i] * r_i[i] for i in w) + cash * RF[h]
        rets[h] = gross - tc; turn[h] = tc / cost if cost else sum(abs(w.get(i, 0) - w_prev.get(i, 0)) for i in set(w) | set(w_prev))
        tot = 1 + gross
        w_prev = {i: w[i] * (1 + r_i[i]) / tot for i in w}
    return pd.Series(rets), pd.Series(turn)


def topk(score_row, avail_row, k):
    s = score_row[avail_row & score_row.notna()]
    if len(s) < k:
        return None
    order = sorted(range(len(s)), key=lambda j: (-s.values[j], j))   # 同分照欄位順序
    return {s.index[j]: 1 / k for j in order[:k]}


def exact_rank_topk(parts, avail_row, k):
    """v1.2:多個分數的橫斷面百分位平均,用精確分數(Fraction)算;平均名次是 0.5 的倍數,百分位 = 名次 / 有值的個數。
    任何一個成分缺值 → 那個產業不能選(同 v1.1 的 skipna=False);同分照欄位順序。排序只看總和(除以成分數不改變順序)。"""
    from fractions import Fraction
    ex = []
    for p in parts:
        v = p.dropna(); rk = v.rank(method="average"); n = len(v)
        ex.append({c: Fraction(int(round(2 * rk[c])), 2 * n) for c in v.index})
    cols = list(avail_row.index)
    sc = {c: sum((e[c] for e in ex), Fraction(0)) for c in cols if avail_row[c] and all(c in e for e in ex)}
    if len(sc) < k:
        return None
    order = sorted(sc, key=lambda c: (-sc[c], cols.index(c)))
    return {c: 1 / k for c in order[:k]}


def run_universe(nind, cost_key="10bp", ml=None, sig=None, R=None):
    k = 3 if nind == 12 else 10; c = COST[cost_key]
    months = [t for t in R.index if SIM0 - 1 <= t <= LAST - 1]
    avail = R.notna()
    reg = regime_sets() if nind == 12 else {}
    res = {}

    def from_score(name):
        sc = sig[name] if name in sig else ml[name]
        return lambda t: topk(sc.loc[t], avail.loc[t], k)
    for name in ("S0", "E1", "E4", "E5", "E6", "E7", "E8", "E9", "E10"):
        res[name] = simulate(R, from_score(name), c, months)
    for name in ("Q1", "Q2"):
        res[name] = simulate(R, from_score(name), c, [t for t in months if t >= EVAL0 - 1])

    rf12 = np.expm1(np.log1p(RF).rolling(12, min_periods=12).sum())
    c12 = cum(R, 11, 0)

    def e2(t):
        w = topk(sig["S0"].loc[t], avail.loc[t], k)
        return None if w is None else {i: v for i, v in w.items() if c12.at[t, i] >= rf12[t]}
    res["E2"] = simulate(R, e2, c, months)
    s0r = res["S0"][0]

    def e3(t):
        w = topk(sig["S0"].loc[t], avail.loc[t], k)
        if w is None:
            return None
        hist = s0r[(s0r.index <= t) & (s0r.index >= t - 5)]
        sc = 1.0 if len(hist) < 6 else min(1.0, 0.12 / (hist.std(ddof=1) * np.sqrt(12)))
        return {i: v * sc for i, v in w.items()}
    res["E3"] = simulate(R, e3, c, months)
    if nind == 12:
        res["E11"] = simulate(R, lambda t: ({i: 0.25 for i in reg[t][1]} if t in reg else None), c, months)

    def f1(t):
        if t < EVAL0 - 1 or pd.isna(ml["Q1"].loc[t]).all():
            return None
        parts = [sig["S0"].loc[t], sig["E4"].loc[t], ml["Q1"].loc[t]]
        if nind == 12:
            if t not in reg:
                return None
            parts.append(pd.Series([1.0 if i in reg[t][1] else 0.0 for i in R.columns], index=R.columns))
        return exact_rank_topk(parts, avail.loc[t], k)                  # v1.2:精確分數(v1.1 是浮點平均)
    res["F1"] = simulate(R, f1, c, [t for t in months if t >= EVAL0 - 1])
    res["B1"] = simulate(R, lambda t: (lambda a: {i: 1 / len(a) for i in a})(list(R.columns[avail.loc[t].values])), c, months)
    return res


# ---------------- 統計 ----------------
def stats(r):
    r = r[(r.index >= EVAL0) & (r.index <= LAST)]
    w = (1 + r).cumprod()
    return {"月數": int(len(r)), "年化%": round(100 * (w.iloc[-1] ** (12 / len(r)) - 1), 2), "年化波動%": round(100 * r.std() * np.sqrt(12), 2),
            "最大回撤%": round(100 * (w / w.cummax() - 1).min(), 2), "月平均%": round(100 * r.mean(), 3)}


def nw_se(d, lags):
    """平均數的 Newey–West 標準誤(Bartlett 權重)"""
    d = np.asarray(d, float) - np.mean(d); n = len(d); s = np.dot(d, d) / n
    for L in range(1, lags + 1):
        s += 2 * (1 - L / (lags + 1)) * np.dot(d[L:], d[:-L]) / n
    return float(np.sqrt(s / n))


def diff_test(a, b, block=12, reps=10000, seed=SEED):
    idx = a.index.intersection(b.index); idx = idx[(idx >= EVAL0) & (idx <= LAST)]
    d = (a[idx] - b[idx]).values; n = len(d); m = d.mean()
    rng = np.random.default_rng(seed); nb = int(np.ceil(n / block)); bs = np.empty(reps)
    for r in range(reps):
        st = rng.integers(0, n, nb); ix = (st[:, None] + np.arange(block)[None, :]).ravel()[:n] % n
        bs[r] = d[ix].mean()
    p = float(np.mean(np.abs(bs - m) >= abs(m)))
    se = nw_se(d, 12)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {"月平均差(百分點)": round(100 * m, 4), "95%區間(百分點)": [round(100 * lo, 4), round(100 * hi, 4)], "雙尾 p(區塊自助)": round(p, 4),
            "Newey–West t": round(m / se, 2) if se > 0 else None, "月數": int(n)}


def holm(ps):
    k = sorted(ps, key=lambda x: ps[x]); m = len(k); adj = {}; run = 0
    for j, key in enumerate(k):
        run = max(run, min(1.0, (m - j) * ps[key])); adj[key] = round(run, 4)
    return adj


def ic(score, R, h):
    fut = np.expm1(np.log1p(R).rolling(h, min_periods=h).sum().shift(-h))
    vals = []
    for t in score.index:
        if t < EVAL0 - 1 or t + h > LAST:
            continue
        s, f = score.loc[t], fut.loc[t]; m = s.notna() & f.notna()
        if m.sum() >= 5:
            vals.append(s[m].rank().corr(f[m].rank()))
    v = np.array(vals); nan = int(np.isnan(v).sum()); v = v[~np.isnan(v)]; se = nw_se(v, h)   # v1.1 更正:分數全部同分的月份相關係數是 NaN,跳過並計數
    return {"平均 IC": round(float(v.mean()), 4), "NW t": round(float(v.mean() / se), 2) if se > 0 else None, "月數": int(len(v)), "全部同分跳過的月數": nan}


def ac1(R, sig):
    k = 3; rows = []; plan = []
    # 先算 A3 實際延後的比例(第二批在 t+1 不是下跌就延後),再用同樣比例做隨機延後 A3r
    for t in R.index:
        if t < EVAL0 or t + 6 > LAST or t > pd.Period("2025-12", "M"):
            continue
        w = topk(sig["S0"].loc[t], R.notna().loc[t], k)
        if w is not None:
            plan.extend(R.at[t + 1, i] >= 0 for i in w)
    p_delay = float(np.mean(plan)); rng = np.random.default_rng(SEED)
    for t in R.index:
        if t < EVAL0 or t + 6 > LAST or t > pd.Period("2025-12", "M"):       # 開始月 1975-01 ~ 2025-12,且 t+6 ≤ 2026-06
            continue
        w = topk(sig["S0"].loc[t], R.notna().loc[t], k)
        if w is None:
            continue
        a1 = a2 = a3 = a3r = 0.0
        for i in w:
            r = [R.at[t + j, i] for j in range(1, 7)]; rf = [RF[t + j] for j in range(1, 7)]
            g = lambda s: float(np.prod([1 + x for x in r[s:]]))                  # 從 t+s 月底買進到 t+6
            cash = lambda s: float(np.prod([1 + x for x in rf[:s]]))             # 等待期間賺 RF
            a1 += g(0) / k
            a2 += (g(0) + cash(1) * g(1) + cash(2) * g(2)) / 3 / k
            second = 1 if r[0] < 0 else 2
            a3 += (g(0) + cash(second) * g(second) + cash(2) * g(2)) / 3 / k
            sr_ = 2 if rng.random() < p_delay else 1
            a3r += (g(0) + cash(sr_) * g(sr_) + cash(2) * g(2)) / 3 / k
        rows.append((t, a1 - 1, a2 - 1, a3 - 1, a3r - 1))
    D = pd.DataFrame(rows, columns=["t", "A1", "A2", "A3", "A3r"]).set_index("t")
    out = {"組數": int(len(D)), "A3 延後比例": round(p_delay, 4), "平均 6 個月報酬%": {c: round(100 * D[c].mean(), 3) for c in ("A1", "A2", "A3", "A3r")}}
    D.index = pd.PeriodIndex(D.index, freq="M")
    for c in ("A2", "A3"):
        out[f"{c} − A1"] = diff_test(D[c], D["A1"])
    out["Holm"] = holm({k_: out[f"{k_} − A1"]["雙尾 p(區塊自助)"] for k_ in ("A2", "A3")})
    out["A3 − A2(只報告)"] = diff_test(D["A3"], D["A2"])
    out["A3 − A3r(只報告)"] = diff_test(D["A3"], D["A3r"])
    return out


# ---------------- 主程式 ----------------
result = {"協定": "PROTOCOL_SR1.md v1.0", "程式": "sr1_run.py v1.2(E7 候選數、F1 精確分數)", "合成資料": SYN, "評分期": [str(EVAL0), str(LAST)]}
monthly = {}
for nind in (12, 49):
    R, BM = load(nind)
    sig = signals(R, BM, nind)
    ml, mlinfo = ml_scores(R, sig)
    U = {"ML": mlinfo}
    by_cost = {ck: run_universe(nind, ck, ml, sig, R) for ck in COST}
    main = by_cost["10bp"]
    U["10bp 每個規則"] = {n: {**stats(v[0]), "月均換手": round(float(v[1][v[1].index >= EVAL0].mean()), 3)} for n, v in main.items()}
    U["市場 B2"] = stats(MKT); U["成本敏感度 年化%"] = {ck: {n: stats(v[0])["年化%"] for n, v in res.items()} for ck, res in by_cost.items()}
    base = main["S0"][0]
    U["主要 H1:F1 − S0"] = diff_test(main["F1"][0], base)
    sec = [n for n in ("E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", "E11", "Q1", "Q2") if n in main]
    U["次要:各規則 − S0"] = {n: diff_test(main[n][0], base) for n in sec}
    U["次要 Holm"] = holm({n: U["次要:各規則 − S0"][n]["雙尾 p(區塊自助)"] for n in sec})
    U["對市場(只報告)"] = {n: diff_test(v[0], MKT, reps=2000) for n, v in main.items()}
    per = {"1975–1984": ("1975-01", "1984-12"), "1985–1994": ("1985-01", "1994-12"), "1995–2004": ("1995-01", "2004-12"),
           "2005–2014": ("2005-01", "2014-12"), "2015–2026-06": ("2015-01", "2026-06"), "2016–2025(對照 Codex R7)": ("2016-01", "2025-12")}
    sub = {}
    for lab, (a, b) in per.items():
        a, b = pd.Period(a, "M"), pd.Period(b, "M"); row = {}
        for n, v in list(main.items()) + [("B2", (MKT, None))]:
            r = v[0]; r = r[(r.index >= a) & (r.index <= b)]
            if len(r):
                row[n] = round(100 * (float((1 + r).prod()) ** (12 / len(r)) - 1), 2)
        sub[lab] = row
    U["分段 年化%"] = sub
    scores = {n: sig[n] for n in ("S0", "E1", "E4", "E5", "E6", "E7", "E8", "E9", "E10")} | {"Q1": ml["Q1"], "Q2": ml["Q2"]}
    U["預測力 IC(Spearman,只報告)"] = {n: {f"{h} 個月": ic(s, R, h) for h in (1, 3, 6)} for n, s in scores.items()}
    if nind == 12:
        reg = regime_sets()
        from collections import Counter
        U["E11 景氣狀態次數(評分期)"] = dict(Counter(v[0] for t, v in reg.items() if EVAL0 - 1 <= t <= LAST - 1))
        U["AC1 分批逢低"] = ac1(R, sig)
    result[f"{nind} 產業"] = U
    for n, v in main.items():
        monthly[f"{nind}|{n}"] = v[0]
monthly["MKT"] = MKT; monthly["RF"] = RF
M = pd.DataFrame(monthly); M = M[(M.index >= EVAL0) & (M.index <= LAST)]
M.to_csv(os.path.join(OUT, f"sr1_monthly{TAG}.csv"))
json.dump(result, open(os.path.join(OUT, f"sr1_results{TAG}.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: (v if k != "12 產業" and k != "49 產業" else {kk: vv for kk, vv in v.items() if kk in ("ML", "主要 H1:F1 − S0", "次要 Holm")}) for k, v in result.items()}, ensure_ascii=False, indent=1, default=str)[:4000])
