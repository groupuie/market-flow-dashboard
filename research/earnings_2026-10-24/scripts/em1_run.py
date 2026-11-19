#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EM1(協定 PROTOCOL_EM1.md v1.0):產業盈餘動能 —— 盈餘轉強的產業,之後 3 個月會不會比較強?和 S0 融合有沒有加分?
輸入:SCRATCH/sr/raw/49_Industry_Portfolios_CSV.zip(同 SR1 / SC1,202608 CRSP)、SCRATCH/ern/out/em1_signals.csv(em_c_industry.py)
用法:python3 -I em1_run.py SCRATCH [--synthetic]   → SCRATCH/ern/out/em1_results{_synthetic}.json、em1_monthly{_synthetic}.csv
--synthetic:產業報酬換成亂數(同樣的日期與欄位;同 SR1 的 49 產業假資料),只用來除錯。"""
import os, sys, json, math, zipfile
import numpy as np, pandas as pd

S = sys.argv[1]; SYN = "--synthetic" in sys.argv; TAG = "_synthetic" if SYN else ""
OUT = os.path.join(S, "ern", "out")
LAST = pd.Period("2026-06", "M"); P0 = pd.Period("2010-07", "M")
SEED = 20261023; NWL = 4; BLOCK = 12; REPS = 10000; MIN_N = 30; TOPK = 10
FF = ("Agric Food Soda Beer Smoke Toys Fun Books Hshld Clths Hlth MedEq Drugs Chems Rubbr Txtls BldMt Cnstr Steel FabPr Mach ElcEq "
      "Autos Aero Ships Guns Gold Mines Coal Oil Util Telcm PerSv BusSv Hardw Softw Chips LabEq Paper Boxes Trans Whlsl Rtail Meals "
      "Banks Insur RlEst Fin Other").split()


def french(zpath, anchor):
    z = zipfile.ZipFile(zpath); lines = z.read(z.namelist()[0]).decode("latin-1").splitlines()
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
R = R[R.index <= LAST]
assert list(R.columns) == FF, list(R.columns)
if SYN:
    rng0 = np.random.default_rng(7 + 49)
    R = pd.DataFrame(rng0.normal(0.009, 0.055, R.shape), index=R.index, columns=R.columns).where(R.notna())


def cum(Rm, a, b):
    L = np.log1p(Rm); w = a - b + 1
    return np.expm1(L.rolling(w, min_periods=w).sum().shift(b))


def fut(Rm, h):
    return np.expm1(np.log1p(Rm).rolling(h, min_periods=h).sum().shift(-h))


S0 = cum(R, 11, 1); PAST3 = cum(R, 2, 0); F1, F3, F6 = fut(R, 1), fut(R, 3), fut(R, 6)

sig = pd.read_csv(os.path.join(OUT, "em1_signals.csv"))
sig["t"] = pd.PeriodIndex(sig["t"], freq="M")
G = sig.pivot(index="t", columns="ff", values="G").reindex(columns=FF)
B = sig.pivot(index="t", columns="ff", values="B").reindex(columns=FF)
NF = sig.pivot(index="t", columns="ff", values="n").reindex(columns=FF)
A = G - G.shift(3, freq="M").reindex(G.index)                  # 加速 = G(t) − G(t−3)


# ---------- 統計(同 SC1)----------
def t_two_sided_p(t, df):
    try:
        from scipy.stats import t as T
        return float(2 * T.sf(abs(t), df))
    except Exception:                                           # noqa: BLE001
        return float(math.erfc(abs(t) / math.sqrt(2)))


def nw(d, lag=NWL):
    d = np.asarray(d, float); d = d[~np.isnan(d)]; n = len(d); mu = d.mean(); e = d - mu; s = np.dot(e, e) / n
    for L in range(1, lag + 1):
        s += 2 * (1 - L / (lag + 1)) * np.dot(e[L:], e[:-L]) / n
    se = math.sqrt(s / n); t = mu / se if se > 0 else float("nan")
    return {"n": n, "平均": round(mu, 4), "NW 標準誤": round(se, 4), "t": round(t, 2), "雙尾 p": round(t_two_sided_p(t, n - 1), 4), "落後": lag}


def boot(d, block=BLOCK, reps=REPS, seed=SEED):
    d = np.asarray(d, float); d = d[~np.isnan(d)]; n = len(d); m = d.mean(); rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block)); bs = np.empty(reps)
    for r in range(reps):
        st = rng.integers(0, n, nb); ix = (st[:, None] + np.arange(block)[None, :]).ravel()[:n] % n; bs[r] = d[ix].mean()
    return {"雙尾 p(區塊自助)": round(float(np.mean(np.abs(bs - m) >= abs(m))), 4), "95% 區間": [round(float(x), 4) for x in np.percentile(bs, [2.5, 97.5])]}


def holm(ps):
    k = sorted(ps, key=lambda x: ps[x]); m = len(k); out = {}; run = 0
    for j, key in enumerate(k):
        run = max(run, min(1.0, (m - j) * ps[key])); out[key] = round(run, 4)
    return out


def rk(x):
    return pd.Series(x).rank().values


def sp(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.nanstd(a) == 0 or np.nanstd(b) == 0:
        return np.nan
    return float(np.corrcoef(rk(a), rk(b))[0, 1])


def row(df, t):
    return df.loc[t].values.astype(float) if t in df.index else np.full(49, np.nan)


# ---------- 每月 ----------
rows = []
for t in [t for t in R.index if P0 <= t and t + 1 <= LAST]:
    g, b, a = row(G, t), row(B, t), row(A, t); s0 = S0.loc[t].values; p3 = PAST3.loc[t].values
    f1 = F1.loc[t].values; f3 = F3.loc[t].values if t + 3 <= LAST else np.full(49, np.nan); f6 = F6.loc[t].values if t + 6 <= LAST else np.full(49, np.nan)
    rec = {"t": str(t), "n_ind": int((~np.isnan(g)).sum()), "n_firms": float(np.nansum(row(NF, t)))}
    m = ~np.isnan(g) & ~np.isnan(f3)
    if m.sum() >= MIN_N:
        rec["IC3_G"] = sp(g[m], f3[m])
        mf = m & ~np.isnan(s0)
        if mf.sum() >= MIN_N:
            fused = rk(s0[mf]) + rk(g[mf])
            rec["IC3_F"] = sp(fused, f3[mf]); rec["IC3_S0_onF"] = sp(s0[mf], f3[mf]); rec["H2_diff"] = rec["IC3_F"] - rec["IC3_S0_onF"]
            X = np.column_stack([np.ones(mf.sum()), rk(s0[mf])]); y = rk(g[mf]); beta = np.linalg.lstsq(X, y, rcond=None)[0]
            rec["IC3_Gperp"] = sp(y - X @ beta, f3[mf])
        idx = np.where(m)[0]; order = idx[np.argsort(-g[idx], kind="stable")]
        rec["top10_ex3"] = float(f3[order[:TOPK]].mean() - f3[idx].mean()); rec["ls10_3"] = float(f3[order[:TOPK]].mean() - f3[order[-TOPK:]].mean())
    mb = ~np.isnan(b) & ~np.isnan(f3)
    if mb.sum() >= MIN_N:
        rec["IC3_B"] = sp(b[mb], f3[mb])
    ma = ~np.isnan(a) & ~np.isnan(f3)
    if ma.sum() >= MIN_N:
        rec["IC3_A"] = sp(a[ma], f3[ma])
    m1 = ~np.isnan(g) & ~np.isnan(f1)
    if m1.sum() >= MIN_N:
        rec["IC1_G"] = sp(g[m1], f1[m1])
    m6 = ~np.isnan(g) & ~np.isnan(f6)
    if m6.sum() >= MIN_N:
        rec["IC6_G"] = sp(g[m6], f6[m6])
    mc = ~np.isnan(g) & ~np.isnan(p3)
    if mc.sum() >= MIN_N:
        rec["IC_same_G"] = sp(g[mc], p3[mc])                      # 和 t−2 ~ t 的報酬(同期)
    ms = ~np.isnan(g) & ~np.isnan(s0)
    if ms.sum() >= MIN_N:
        rec["corr_G_S0"] = sp(g[ms], s0[ms])
    rows.append(rec)
MON = pd.DataFrame(rows)
MON.to_csv(os.path.join(OUT, f"em1_monthly{TAG}.csv"), index=False)


def col(name, a=None, b=None, months=None, df=MON):
    d = df.copy(); tt = pd.PeriodIndex(d["t"], freq="M"); keep = np.ones(len(d), bool)
    if a is not None:
        keep &= tt >= pd.Period(a, "M")
    if b is not None:
        keep &= tt <= pd.Period(b, "M")
    if months is not None:
        keep &= np.isin(tt.month, months)
    v = d.loc[keep, name] if name in d else pd.Series(dtype=float)
    return v.dropna().values.astype(float)


def test(v):
    return nw(v) | boot(v)


P3 = (str(P0), "2026-03"); P1 = (str(P0), "2026-05")
res = {"協定": "PROTOCOL_EM1.md v1.0", "程式": "em1_run.py v1.0", "假資料": SYN,
       "設定": {"主要決定月(3 個月)": P3, "1 個月": P1, "持有月最晚": str(LAST), "NW 落後": NWL, "區塊": BLOCK, "自助次數": REPS, "種子": SEED, "最少產業數": MIN_N}}
pri = {"H1 IC_3m(G)": test(col("IC3_G", *P3)), "H2 IC_3m(S0 + G) − IC_3m(S0)": test(col("H2_diff", *P3))}
pri["Holm(NW 雙尾 p)"] = holm({k: v["雙尾 p"] for k, v in pri.items()})
res["主要"] = pri
sec = {"S1 IC_1m(G)": test(col("IC1_G", *P1)), "S2 IC_3m(B 變好的公司比例)": test(col("IC3_B", *P3)), "S3 IC_3m(A 加速)": test(col("IC3_A", *P3)),
       "S4 IC_3m(G ⊥ S0)": test(col("IC3_Gperp", *P3)), "S5 G 前 10 名 − 同批等權(3 個月,小數)": test(col("top10_ex3", *P3))}
sec["Holm(NW 雙尾 p)"] = holm({k: v["雙尾 p"] for k, v in sec.items()})
res["次要"] = sec
rep = {"IC_3m(S0)(同 H2 那批)": nw(col("IC3_S0_onF", *P3)), "IC_3m(融合)": nw(col("IC3_F", *P3)),
       "G 和 S0 的橫斷面相關(平均)": round(float(np.mean(col("corr_G_S0", *P1))), 4),
       "同期:G 和 t−2 ~ t 報酬的 IC": nw(col("IC_same_G", *P1)),
       "IC_6m(G)(落後 6)": nw(col("IC6_G", str(P0), "2025-12"), lag=6),
       "G 前 10 − 後 10(3 個月,小數)": nw(col("ls10_3", *P3)),
       "IC_3m(G)> 0 的月份比例": round(float(np.mean(col("IC3_G", *P3) > 0)), 4),
       "分段 IC_3m(G)": {"2010-07 ~ 2017-12": nw(col("IC3_G", "2010-07", "2017-12")), "2018-01 ~ 2026-03": nw(col("IC3_G", "2018-01", "2026-03")),
                       "2012-01 ~ 2026-03(XBRL 全面上路後)": nw(col("IC3_G", "2012-01", "2026-03"))},
       "財報季剛過的決定月(2、5、8、11 月)IC_3m(G)": nw(col("IC3_G", *P3, months=[2, 5, 8, 11])),
       "其他決定月 IC_3m(G)": nw(col("IC3_G", *P3, months=[1, 3, 4, 6, 7, 9, 10, 12])),
       "每月有訊號的產業數(最少 / 中位 / 最多)": [int(MON["n_ind"].min()), int(MON["n_ind"].median()), int(MON["n_ind"].max())],
       "每月公司數(最少 / 中位 / 最多)": [int(MON["n_firms"].min()), int(MON["n_firms"].median()), int(MON["n_firms"].max())]}
res["只報告"] = rep
json.dump(res, open(os.path.join(OUT, f"em1_results{TAG}.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: res[k] for k in ("主要", "次要")}, ensure_ascii=False, indent=1)[:6000])
