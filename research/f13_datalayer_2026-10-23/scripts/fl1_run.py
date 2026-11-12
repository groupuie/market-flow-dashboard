#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FL1(協定 PROTOCOL_FL1.md v1.0):13F 產業淨買進(FLOW)能不能預測產業之後的報酬;和 S0 融合有沒有加分。
輸入:SCRATCH/f13/series/flow__{P}.parquet(DL1)、SCRATCH/cm/cusip_map.parquet(CM1)、SCRATCH/sr/raw/ 的 French 49 產業與 F-F 因子 zip(同 SR1)。
用法:python3 -I fl1_run.py SCRATCH [--synthetic]   → SCRATCH/f13/out/fl1_results{_synthetic}.json、fl1_decisions{_synthetic}.csv
--synthetic:產業報酬換成亂數(同樣的日期與欄位),只用來除錯。"""
import os, sys, io, re, json, math, glob, zipfile, datetime as dt
from fractions import Fraction
import numpy as np, pandas as pd

S = sys.argv[1]; SYN = "--synthetic" in sys.argv; TAG = "_synthetic" if SYN else ""
F = os.path.join(S, "f13"); SE, OUT = os.path.join(F, "series"), os.path.join(F, "out")
LAST = pd.Period("2026-06", "M"); SEED = 20261023


# ---------- French ----------
def french(zpath, anchor):
    z = zipfile.ZipFile(zpath); text = z.read(z.namelist()[0]).decode("latin-1"); lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip().startswith(anchor)); hdr = None; rows = []
    for l in lines[i + 1:]:
        s = l.strip()
        if not s:
            if rows:
                break
            continue
        if s.startswith(","):
            if rows:
                break
            hdr = [c.strip() for c in s.split(",")[1:]]; continue
        p = [x.strip() for x in l.split(",")]
        if not (p[0].isdigit() and len(p[0]) == 6):
            break
        rows.append([p[0]] + [float(x) for x in p[1:]])
    df = pd.DataFrame([r[1:] for r in rows], columns=hdr, index=pd.PeriodIndex([f"{r[0][:4]}-{r[0][4:]}" for r in rows], freq="M"))
    return df.mask(df <= -99.99) / 100


R = french(os.path.join(S, "sr", "raw", "49_Industry_Portfolios_CSV.zip"), "Average Value Weighted Returns -- Monthly")
FF = french(os.path.join(S, "sr", "raw", "F-F_Research_Data_Factors_CSV.zip"), "The annual TBill return")
R, FF = R[R.index <= LAST], FF[FF.index <= LAST]; MKT = FF["Mkt-RF"] + FF["RF"]
CODES = list(R.columns)
if SYN:
    rng = np.random.default_rng(49); R = pd.DataFrame(rng.normal(0.009, 0.055, R.shape), index=R.index, columns=R.columns).where(R.notna())
LR = np.log1p(R)
S0 = np.expm1(LR.rolling(11, min_periods=11).sum().shift(1))          # 決定月 t:t−11 ~ t−1


def fwd(t, h):
    if t + h > LAST:
        return None
    w = LR.loc[t + 1:t + h]
    return np.expm1(w.sum(min_count=h)).where(w.notna().all())


def mkt_fwd(t, h):
    return float(np.prod([1 + MKT[t + k] for k in range(1, h + 1)]) - 1)


# ---------- 法定期限(同 c_snapshots.py)----------
def fed_holidays(y):
    def nth(m, wd, n):
        d = dt.date(y, m, 1); k = 0
        while True:
            if d.weekday() == wd:
                k += 1
                if k == n:
                    return d
            d += dt.timedelta(days=1)
    def last(m, wd):
        d = (dt.date(y, m + 1, 1) - dt.timedelta(days=1)) if m < 12 else dt.date(y, 12, 31)
        while d.weekday() != wd:
            d -= dt.timedelta(days=1)
        return d
    obs = lambda d: d - dt.timedelta(days=1) if d.weekday() == 5 else d + dt.timedelta(days=1) if d.weekday() == 6 else d
    h = {obs(dt.date(y, 1, 1)), nth(1, 0, 3), nth(2, 0, 3), last(5, 0), obs(dt.date(y, 7, 4)), nth(9, 0, 1), nth(10, 0, 2), obs(dt.date(y, 11, 11)), nth(11, 3, 4), obs(dt.date(y, 12, 25))}
    if y >= 2021:
        h.add(obs(dt.date(y, 6, 19)))
    return h


def deadline(P):
    d = P + dt.timedelta(days=45)
    while d.weekday() >= 5 or d in fed_holidays(d.year):
        d += dt.timedelta(days=1)
    return d


# ---------- 產業對照 ----------
rng_ = []; cur = None
for l in zipfile.ZipFile(os.path.join(S, "fs", "raw", "Siccodes49.zip")).read("Siccodes49.txt").decode("latin-1").splitlines():
    m = re.match(r"^\s*(\d{1,2})\s+([A-Za-z]+)\s+\S", l); r = re.match(r"^\s+(\d{4})-(\d{4})", l)
    if m and not r:
        cur = m.group(2)
    elif r and cur:
        rng_.append((int(r.group(1)), int(r.group(2)), cur))


def ff49(sic):
    try:
        s = int(sic)
    except Exception:                                           # noqa: BLE001
        return None
    for lo, hi, c in rng_:
        if lo <= s <= hi:
            return c
    return "Other"


MAP = pd.read_parquet(os.path.join(S, "cm", "cusip_map.parquet")).set_index("cusip")


def industry_at(cusip, pend):
    if cusip not in MAP.index:
        return None
    m = MAP.loc[cusip]
    if m["etf"] or m["cik"] is None or (isinstance(m["cik"], float) and math.isnan(m["cik"])):
        return None
    hist = json.loads(m["sic_hist"]) if isinstance(m["sic_hist"], str) else []
    sic = None
    if hist:
        before = [s for d, s in hist if d and d <= str(pend)]
        sic = before[-1] if before else hist[0][1]
    if sic is None:
        sic = m.get("sic_current")
    return ff49(sic) if sic not in (None, "", "0000") else None


# ---------- 統計 ----------
def t_two_sided_p(t, df):
    try:
        from scipy.stats import t as T
        return float(2 * T.sf(abs(t), df))
    except Exception:                                           # noqa: BLE001
        return float(math.erfc(abs(t) / math.sqrt(2)))


def nw(d, lag):
    d = np.asarray(d, float); n = len(d); mu = d.mean(); e = d - mu; s = np.dot(e, e) / n
    for L in range(1, lag + 1):
        s += 2 * (1 - L / (lag + 1)) * np.dot(e[L:], e[:-L]) / n
    se = math.sqrt(s / n); t = mu / se if se > 0 else float("nan")
    return {"n": n, "平均": round(mu, 4), "NW 標準誤": round(se, 4), "t": round(t, 2), "雙尾 p": round(t_two_sided_p(t, n - 1), 4), "落後": lag}


def boot(d, block=4, reps=10000, seed=SEED):
    d = np.asarray(d, float); n = len(d); m = d.mean(); rng = np.random.default_rng(seed); nb = int(np.ceil(n / block)); bs = np.empty(reps)
    for r in range(reps):
        st = rng.integers(0, n, nb); ix = (st[:, None] + np.arange(block)[None, :]).ravel()[:n] % n; bs[r] = d[ix].mean()
    return {"雙尾 p(區塊自助)": round(float(np.mean(np.abs(bs - m) >= abs(m))), 4), "95% 區間": [round(float(x), 4) for x in np.percentile(bs, [2.5, 97.5])]}


def holm(ps):
    k = sorted(ps, key=lambda x: ps[x]); m = len(k); out = {}; run = 0
    for j, key in enumerate(k):
        run = max(run, min(1.0, (m - j) * ps[key])); out[key] = round(run, 4)
    return out


def spearman(a, b):
    a, b = pd.Series(a, dtype=float), pd.Series(b, dtype=float); m = a.notna() & b.notna()
    if m.sum() < 10 or a[m].nunique() < 2 or b[m].nunique() < 2:
        return None
    return float(a[m].rank().corr(b[m].rank()))


def exact_mean_rank(parts):
    ex = []
    for p in parts:
        v = p.dropna(); rk = v.rank(method="average"); n = len(v)
        ex.append({c: Fraction(int(round(2 * rk[c])), 2 * n) for c in v.index})
    keys = [c for c in CODES if all(c in e for e in ex)]
    return pd.Series({c: float(sum((e[c] for e in ex), Fraction(0))) for c in keys})   # 先用 Fraction 精確加總再轉浮點:相等的和轉出來一定相等,不相等的差距遠大於浮點誤差


def topk_mean(score, ret, k=10):
    s = score.dropna(); s = s[s.index.isin(ret.dropna().index)]
    pos = {c: j for j, c in enumerate(CODES)}
    order = sorted(s.index, key=lambda c: (-s[c], pos[c]))[:k]
    return float(ret[order].mean()) if len(order) == k else None


# ---------- 產業訊號 ----------
dec = []
for fp in sorted(glob.glob(os.path.join(SE, "flow__*.parquet"))):
    P = dt.date.fromisoformat(os.path.basename(fp)[len("flow__"):-len(".parquet")])
    if P < dt.date(2013, 9, 30):
        continue
    A = deadline(P) + dt.timedelta(days=1); t = pd.Period(f"{A.year}-{A.month:02d}", "M")
    df = pd.read_parquet(fp)
    df = df[df["p0"].notna() & ~df["unresolved"].fillna(False) & ~df["thin_jump"].fillna(False)].copy()
    df["ind"] = [industry_at(c, P) for c in df["cusip"]]
    tot_val = float(df["value_prev"].sum()); mapped = df[df["ind"].notna()]
    g = mapped.groupby("ind")
    agg = pd.DataFrame({"flow": g["flow_fixed_usd"].sum(), "alloc": g["dalloc_usd"].sum(), "v0": g["value_prev"].sum(), "n": g.size(),
                        "bw": g.apply(lambda x: float((x["breadth"].fillna(0) * x["value_prev"]).sum()))})
    ok = (agg["v0"] >= 1e9) & (agg["n"] >= 3)
    sig = pd.DataFrame({"FLOW": agg["flow"] / agg["v0"], "ALLOC": agg["alloc"] / agg["v0"], "BREADTH": agg["bw"] / agg["v0"]}).where(ok).reindex(CODES)
    s0 = S0.loc[t] if t in S0.index else pd.Series(np.nan, index=CODES)
    pc = {"P": str(P), "可用日": str(A), "決定月": str(t), "對到產業的市值占比%": round(100 * float(mapped["value_prev"].sum()) / tot_val, 2) if tot_val else None,
          "有訊號的產業": int(sig["FLOW"].notna().sum())}
    Fu = exact_mean_rank([s0.reindex(CODES), sig["FLOW"]])
    for h in (1, 3, 6):
        r = fwd(t, h)
        if r is None:
            continue
        pc[f"IC_{h}m_FLOW"] = spearman(sig["FLOW"], r); pc[f"IC_{h}m_S0"] = spearman(s0, r); pc[f"IC_{h}m_F"] = spearman(Fu, r)
        pc[f"IC_{h}m_ALLOC"] = spearman(sig["ALLOC"], r); pc[f"IC_{h}m_BREADTH"] = spearman(sig["BREADTH"], r)
        # 同一批產業(F 與 S0 都要有)的 S0 IC,給 H2 的配對差
        common = Fu.index; pc[f"IC_{h}m_S0_common"] = spearman(s0.reindex(common), r.reindex(common))
        if h == 3:
            mk = mkt_fwd(t, 3); tf = topk_mean(sig["FLOW"], r); tF = topk_mean(Fu, r); tS = topk_mean(s0, r)
            pc["top10_FLOW_minus_mkt_3m"] = None if tf is None else tf - mk
            pc["top10_F_minus_S0_3m"] = None if (tF is None or tS is None) else tF - tS
    # 同期 IC(只報告):FLOW 和 P−1 → P 那一季的產業報酬
    qe = pd.Period(f"{P.year}-{P.month:02d}", "M"); same = np.expm1(LR.loc[qe - 2:qe].sum(min_count=3)).where(LR.loc[qe - 2:qe].notna().all())
    pc["同期 IC(FLOW vs 這一季報酬)"] = spearman(sig["FLOW"], same)
    pc["FLOW 與 S0 的橫斷面相關"] = spearman(sig["FLOW"], s0)
    dec.append(pc)
D = pd.DataFrame(dec)
D.to_csv(os.path.join(OUT, f"fl1_decisions{TAG}.csv"), index=False)


def series(col):
    x = D[["P", col]].dropna(); return x[col].values, list(x["P"])


res = {"協定": "PROTOCOL_FL1.md v1.0", "合成資料": SYN, "持有月最後": str(LAST), "決定數": len(D),
       "對到產業的市值占比%(中位 / 最低)": [float(D["對到產業的市值占比%"].median()), float(D["對到產業的市值占比%"].min())],
       "對到產業低於 85% 的季": list(D.loc[D["對到產業的市值占比%"] < 85, "P"])}
h1, _ = series("IC_3m_FLOW")
x = D[["IC_3m_F", "IC_3m_S0_common"]].dropna(); h2 = (x["IC_3m_F"] - x["IC_3m_S0_common"]).values
res["主要 H1:IC_3m(FLOW)"] = {**nw(h1, 1), **boot(h1)}
res["主要 H2:IC_3m(F) − IC_3m(S0)"] = {**nw(h2, 1), **boot(h2)}
res["主要 Holm"] = holm({"H1": res["主要 H1:IC_3m(FLOW)"]["雙尾 p"], "H2": res["主要 H2:IC_3m(F) − IC_3m(S0)"]["雙尾 p"]})
sec = {}
for name, col, lag in (("IC_1m(FLOW)", "IC_1m_FLOW", 1), ("IC_6m(FLOW)", "IC_6m_FLOW", 2), ("IC_3m(ALLOC)", "IC_3m_ALLOC", 1), ("IC_3m(BREADTH)", "IC_3m_BREADTH", 1),
                       ("FLOW 前 10 名 − 市場(3m)", "top10_FLOW_minus_mkt_3m", 1), ("F 前 10 名 − S0 前 10 名(3m)", "top10_F_minus_S0_3m", 1)):
    v, _ = series(col); sec[name] = nw(v, lag)
res["次要"] = sec; res["次要 Holm"] = holm({k: v["雙尾 p"] for k, v in sec.items()})
rep = {"IC_3m(S0)(同一批決定)": nw(series("IC_3m_S0")[0], 1)}
for lab, lo, hi in (("2013–2019", "2013-01-01", "2019-12-31"), ("2020–2026", "2020-01-01", "2026-12-31")):
    m = (D["P"] >= lo) & (D["P"] <= hi); v = D.loc[m, "IC_3m_FLOW"].dropna().values
    rep[f"IC_3m(FLOW) {lab}"] = nw(v, 1) if len(v) > 2 else None
rep["同期 IC(機構是不是追漲)"] = nw(series("同期 IC(FLOW vs 這一季報酬)")[0], 1)
rep["FLOW 與 S0 的橫斷面相關(平均)"] = round(float(D["FLOW 與 S0 的橫斷面相關"].mean()), 4)
res["只報告"] = rep
json.dump(res, open(os.path.join(OUT, f"fl1_results{TAG}.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
