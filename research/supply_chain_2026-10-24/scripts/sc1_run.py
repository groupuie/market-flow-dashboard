#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SC1(協定 PROTOCOL_SC1.md v1.0):供應鏈傳導 —— 客戶產業這個月漲,供應商產業下個月會不會跟著漲?和 S0 融合有沒有加分?
輸入:SCRATCH/sr/raw/49_Industry_Portfolios_CSV.zip(同 SR1 / FL1,202608 CRSP)、SCRATCH/sc/out/sc1_flows.npz(sc_map.py 的 49 產業流量表)
用法:python3 -I sc1_run.py SCRATCH [--synthetic]   → SCRATCH/sc/out/sc1_results{_synthetic}.json、sc1_monthly{_synthetic}.csv
--synthetic:產業報酬換成亂數(同樣的日期與欄位;同 SR1 的 49 產業假資料),只用來除錯。"""
import os, sys, json, math, zipfile
import numpy as np, pandas as pd

S = sys.argv[1]; SYN = "--synthetic" in sys.argv; TAG = "_synthetic" if SYN else ""
OUT = os.path.join(S, "sc", "out")
LAST = pd.Period("2026-06", "M")                    # 持有月最晚 2026-06
P0 = pd.Period("2009-01", "M")                      # 主要樣本第一個決定月(2007 細項表 + 2 年)
L0 = pd.Period("1999-01", "M")                      # 長樣本第一個決定月(1997 摘要表 + 2 年)
SEED = 20261023; NWL = 4; BLOCK = 12; REPS = 10000; NPERM = 1000; MIN_SHARE = 0.05; MIN_N = 30; MIN_SUB = 15; TOPK = 10
FF = ("Agric Food Soda Beer Smoke Toys Fun Books Hshld Clths Hlth MedEq Drugs Chems Rubbr Txtls BldMt Cnstr Steel FabPr Mach ElcEq "
      "Autos Aero Ships Guns Gold Mines Coal Oil Util Telcm PerSv BusSv Hardw Softw Chips LabEq Paper Boxes Trans Whlsl Rtail Meals "
      "Banks Insur RlEst Fin Other").split()
D_TABLES = (2007, 2012, 2017)


# ---------- French ----------
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
    """月 t−a ~ t−b 的累計報酬(全部有值才算)"""
    L = np.log1p(Rm); w = a - b + 1
    return np.expm1(L.rolling(w, min_periods=w).sum().shift(b))


S0 = cum(R, 11, 1)                                  # 同 SR1:t−11 ~ t−1
C3 = cum(R, 2, 0)                                   # t−2 ~ t(S4 用)
FUT1 = R.shift(-1)                                  # t+1
FUT3 = np.expm1(np.log1p(R).rolling(3, min_periods=3).sum().shift(-3))   # t+1 ~ t+3

# ---------- 權重 ----------
Z = np.load(os.path.join(OUT, "sc1_flows.npz"))


def weights(key, kind):
    F = Z[key].copy(); out = Z[key + "_out"]; np.fill_diagonal(F, 0.0)
    M = F if kind == "c" else F.T                   # c:k 賣給 l;s:k 向 l 買
    tot = M.sum(1)
    share = np.divide(tot, out, out=np.zeros(49), where=out > 0)
    W = np.divide(M, tot[:, None], out=np.zeros_like(M), where=tot[:, None] > 0)
    valid = (tot > 0) & (out > 0) & (share >= MIN_SHARE)
    return W, valid, share


WT = {}
for y in D_TABLES:
    WT[("D", y, "c")] = weights(f"D{y}", "c"); WT[("D", y, "s")] = weights(f"D{y}", "s")
for y in range(1997, 2024):
    WT[("S", y, "c")] = weights(f"S{y}", "c"); WT[("S", y, "s")] = weights(f"S{y}", "s")


def table(t, level):
    if level == "D":
        ys = [y for y in D_TABLES if y <= t.year - 2]
        return max(ys) if ys else None
    y = min(t.year - 2, 2023)
    return y if y >= 1997 else None


def link_signal(W, valid, x):
    """Σ_l W[k,l] x_l,權重只在 x 有值的 l 之間重新正規化;valid 以外 = NaN"""
    x = np.asarray(x, float); ok = ~np.isnan(x); Wm = W[:, ok]; den = Wm.sum(1)
    sig = np.divide(Wm @ x[ok], den, out=np.full(49, np.nan), where=den > 0)
    sig[~valid] = np.nan
    return sig


# ---------- 統計 ----------
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
    return pd.Series(x).rank().values                 # 平均名次(同分取平均)


def sp(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.nanstd(a) == 0 or np.nanstd(b) == 0:
        return np.nan
    return float(np.corrcoef(rk(a), rk(b))[0, 1])


# ---------- 每月 ----------
rows = []
months = [t for t in R.index if L0 <= t and t + 1 <= LAST]
for t in months:
    r_t = R.loc[t].values; f1 = FUT1.loc[t].values; s0 = S0.loc[t].values
    f3 = FUT3.loc[t].values if t + 3 <= LAST else np.full(49, np.nan)
    rec = {"t": str(t)}
    yd, ys = table(t, "D"), table(t, "S"); rec["表_細項"] = yd; rec["表_摘要"] = ys
    if yd is not None:
        Wc, vc, shc = WT[("D", yd, "c")]; Ws, vs, _ = WT[("D", yd, "s")]
        cm = link_signal(Wc, vc, r_t); sm = link_signal(Ws, vs, r_t); cm3 = link_signal(Wc, vc, C3.loc[t].values)
        m = ~np.isnan(cm) & ~np.isnan(f1); rec["n_CM"] = int(m.sum())
        if m.sum() >= MIN_N:
            rec["IC1_CM"] = sp(cm[m], f1[m]); rec["IC1_own_onCM"] = sp(r_t[m], f1[m]); rec["corr_CM_own"] = sp(cm[m], r_t[m])
            # 融合:同一批產業(CM、S0、t+1 都有)
            mf = m & ~np.isnan(s0)
            if mf.sum() >= MIN_N:
                fused = rk(s0[mf]) + rk(cm[mf])        # 名次和(半整數,精確)= 百分位平均的排序
                rec["IC1_F"] = sp(fused, f1[mf]); rec["IC1_S0_onF"] = sp(s0[mf], f1[mf]); rec["n_F"] = int(mf.sum())
                rec["H2_diff"] = rec["IC1_F"] - rec["IC1_S0_onF"]          # 同一個月兩者都有才有值(NaN 會傳下去)
            # CM ⊥ 自己這個月的報酬(橫斷面 OLS 殘差)
            X = np.column_stack([np.ones(m.sum()), r_t[m]]); beta = np.linalg.lstsq(X, cm[m], rcond=None)[0]
            rec["IC1_CMperp"] = sp(cm[m] - X @ beta, f1[m])
            # 前 10 名等權 − 同一批產業等權;前 10 − 後 10(只報告)
            idx = np.where(m)[0]; order = idx[np.argsort(-cm[idx], kind="stable")]
            rec["top10_ex"] = float(f1[order[:TOPK]].mean() - f1[idx].mean())
            rec["ls10"] = float(f1[order[:TOPK]].mean() - f1[order[-TOPK:]].mean())
            # Fama–MacBeth(只報告):t+1 報酬 ~ 1 + z(名次 CM) + z(名次 自己)
            z1 = rk(cm[m]); z1 = (z1 - z1.mean()) / z1.std(); z2 = rk(r_t[m]); z2 = (z2 - z2.mean()) / z2.std()
            b = np.linalg.lstsq(np.column_stack([np.ones(m.sum()), z1, z2]), f1[m], rcond=None)[0]
            rec["FMB_CM"] = float(b[1]); rec["FMB_own"] = float(b[2])
            # 上游一半(只報告):跨產業中間銷售占產出 ≥ 中位數
            med = np.median(shc[vc]); mu_ = m & (shc >= med)
            if mu_.sum() >= MIN_SUB:
                rec["IC1_CM_upstream"] = sp(cm[mu_], f1[mu_])
        ms = ~np.isnan(sm) & ~np.isnan(f1)
        if ms.sum() >= MIN_N:
            rec["IC1_SM"] = sp(sm[ms], f1[ms])
        m3 = ~np.isnan(cm3) & ~np.isnan(f3)
        if m3.sum() >= MIN_N:
            rec["IC3_CM3"] = sp(cm3[m3], f3[m3])
    if ys is not None:
        Wc, vc, _ = WT[("S", ys, "c")]; Ws, vs, _ = WT[("S", ys, "s")]
        cmS = link_signal(Wc, vc, r_t); smS = link_signal(Ws, vs, r_t)
        m = ~np.isnan(cmS) & ~np.isnan(f1)
        if m.sum() >= MIN_N:
            rec["IC1_CM_S"] = sp(cmS[m], f1[m]); rec["n_CM_S"] = int(m.sum())
        m = ~np.isnan(smS) & ~np.isnan(f1)
        if m.sum() >= MIN_N:
            rec["IC1_SM_S"] = sp(smS[m], f1[m])
    rows.append(rec)
MON = pd.DataFrame(rows)
MON.to_csv(os.path.join(OUT, f"sc1_monthly{TAG}.csv"), index=False)


def col(name, a=None, b=None, df=MON):
    d = df.copy(); tt = pd.PeriodIndex(d["t"], freq="M")
    keep = np.ones(len(d), bool)
    if a is not None:
        keep &= tt >= pd.Period(a, "M")
    if b is not None:
        keep &= tt <= pd.Period(b, "M")
    v = d.loc[keep, name] if name in d else pd.Series(dtype=float)
    return v.dropna().values.astype(float)


def test(v):
    return nw(v) | boot(v)


PRI = (str(P0), "2026-05")
res = {"協定": "PROTOCOL_SC1.md v1.0", "程式": "sc1_run.py v1.0", "假資料": SYN,
       "設定": {"主要決定月": PRI, "長樣本決定月": [str(L0), "2026-05"], "持有月最晚": str(LAST), "NW 落後": NWL, "區塊": BLOCK,
              "自助次數": REPS, "種子": SEED, "CM 門檻(跨產業中間銷售 ÷ 產出)": MIN_SHARE, "最少產業數": MIN_N}}
pri = {"H1 IC_1m(CM)": test(col("IC1_CM", *PRI)), "H2 IC_1m(S0 + CM) − IC_1m(S0)": test(col("H2_diff", *PRI))}
pri["Holm(NW 雙尾 p)"] = holm({k: v["雙尾 p"] for k, v in pri.items()})
res["主要"] = pri
sec = {"S1 IC_1m(SM 供應商)": test(col("IC1_SM", *PRI)),
       "S2 IC_1m(CM ⊥ 自己當月報酬)": test(col("IC1_CMperp", *PRI)),
       "S3 CM 前 10 名 − 同批等權(下月,小數)": test(col("top10_ex", *PRI)),
       "S4 IC_3m(CM 3 個月)": test(col("IC3_CM3", str(P0), "2026-03")),
       "S5 IC_1m(CM,摘要表長樣本 1999–2026)": test(col("IC1_CM_S", str(L0), "2026-05"))}
sec["Holm(NW 雙尾 p)"] = holm({k: v["雙尾 p"] for k, v in sec.items()})
res["次要"] = sec

rep = {}
rep["IC_1m(S0)(同 H2 那批)"] = nw(col("IC1_S0_onF", *PRI)); rep["IC_1m(融合)"] = nw(col("IC1_F", *PRI))
rep["IC_1m(自己當月報酬)(CM 那批)"] = nw(col("IC1_own_onCM", *PRI))
rep["CM 和自己當月報酬的橫斷面相關(平均)"] = round(float(np.mean(col("corr_CM_own", *PRI))), 4)
rep["Fama–MacBeth:CM 係數(小數 / 月)"] = nw(col("FMB_CM", *PRI)); rep["Fama–MacBeth:自己當月係數"] = nw(col("FMB_own", *PRI))
rep["CM 前 10 − 後 10(下月,小數)"] = nw(col("ls10", *PRI))
rep["IC_1m(CM)> 0 的月份比例"] = round(float(np.mean(col("IC1_CM", *PRI) > 0)), 4)
rep["分段 IC_1m(CM)"] = {"2009–2016": nw(col("IC1_CM", "2009-01", "2016-12")), "2017–2026": nw(col("IC1_CM", "2017-01", "2026-05"))}
rep["各細項表期間 IC_1m(CM)"] = {"2007 表(2009–2013)": nw(col("IC1_CM", "2009-01", "2013-12")), "2012 表(2014–2018)": nw(col("IC1_CM", "2014-01", "2018-12")),
                              "2017 表(2019–2026)": nw(col("IC1_CM", "2019-01", "2026-05"))}
rep["上游一半 IC_1m(CM)"] = nw(col("IC1_CM_upstream", *PRI))
rep["摘要表長樣本"] = {"IC_1m(CM)1999–2008": nw(col("IC1_CM_S", "1999-01", "2008-12")), "IC_1m(CM)2009–2026": nw(col("IC1_CM_S", "2009-01", "2026-05")),
                   "IC_1m(SM)1999–2026": nw(col("IC1_SM_S", "1999-01", "2026-05"))}
rep["每月 CM 產業數(主要)"] = [int(MON["n_CM"].dropna().min()), int(MON["n_CM"].dropna().max())]
rep["CM 有訊號的產業(各細項表)"] = {str(y): [FF[i] for i in range(49) if WT[("D", y, "c")][1][i]] for y in D_TABLES}
rep["CM 沒有訊號的產業(各細項表)"] = {str(y): [FF[i] for i in range(49) if not WT[("D", y, "c")][1][i]] for y in D_TABLES}

# 安慰劑:每個產業的客戶權重在「其他產業」之間隨機重排(保留集中度、不含自己),1,000 次
rngp = np.random.default_rng(SEED)
blocks = []
for y in D_TABLES:
    ts = [t for t in months if P0 <= t <= pd.Period("2026-05", "M") and table(t, "D") == y]
    Rt = R.loc[ts].values.T; F1 = FUT1.loc[ts].values.T
    blocks.append((y, ts, Rt, F1))
actual = col("IC1_CM", *PRI).mean()
perm_means = np.empty(NPERM)
for d in range(NPERM):
    vals = []
    for y, ts, Rt, F1 in blocks:
        W, valid, _ = WT[("D", y, "c")]; Wp = np.zeros_like(W)
        for k in range(49):
            if valid[k]:
                idx = np.array([l for l in range(49) if l != k]); Wp[k, idx] = W[k, idx][rngp.permutation(len(idx))]
        for j in range(len(ts)):
            s_ = link_signal(Wp, valid, Rt[:, j]); m = ~np.isnan(s_) & ~np.isnan(F1[:, j])
            vals.append(sp(s_[m], F1[m, j]) if m.sum() >= MIN_N else np.nan)
    perm_means[d] = np.nanmean(vals)
rep["安慰劑(客戶權重隨機重排 1,000 次)"] = {"實際平均 IC": round(float(actual), 4), "安慰劑平均": round(float(perm_means.mean()), 4),
                                      "安慰劑 2.5% / 50% / 97.5%": [round(float(x), 4) for x in np.percentile(perm_means, [2.5, 50, 97.5])],
                                      "安慰劑 ≥ 實際的比例": round(float(np.mean(perm_means >= actual)), 4)}
res["只報告"] = rep
json.dump(res, open(os.path.join(OUT, f"sc1_results{TAG}.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: res[k] for k in ("主要", "次要")}, ensure_ascii=False, indent=1)[:6000])
