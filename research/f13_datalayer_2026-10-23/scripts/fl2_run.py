#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FL2(協定 PROTOCOL_FL2.md v1.0):主動型、過去 8 季選得準(前 10%)的機構,產業淨買進(FLOW_SK)能不能預測產業之後的報酬。
共用 fl1_run.py 的 French、S0、法定期限、產業對照與統計函式(只載入定義,不跑 FL1)。
用法:python3 -I fl2_run.py SCRATCH [--synthetic]   → SCRATCH/f13/out/fl2_results{_synthetic}.json、fl2_decisions{_synthetic}.csv"""
import os, sys, json, glob, datetime as dt
import numpy as np, pandas as pd, duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "fl1_run.py"), encoding="utf-8").read().split("# ---------- 產業訊號 ----------")[0]
G = {"__name__": "fl1_lib"}
exec(compile(src, "fl1_run.py", "exec"), G)
S, SYN, TAG, F, SE, OUT, LAST = (G[k] for k in ("S", "SYN", "TAG", "F", "SE", "OUT", "LAST"))
CODES, S0, LR, fwd, mkt_fwd, deadline, industry_at = (G[k] for k in ("CODES", "S0", "LR", "fwd", "mkt_fwd", "deadline", "industry_at"))
spearman, exact_mean_rank, topk_mean, nw, boot, holm = (G[k] for k in ("spearman", "exact_mean_rank", "topk_mean", "nw", "boot", "holm"))
SN = os.path.join(F, "snap")
CLEAN = "typ = 'SH' AND putcall = '' AND shares > 0 AND value_fixed > 0 AND NOT coalesce(price_outlier, false) AND NOT unit_undetermined"
AS_MIN, N_MIN, TOP, SKILL_Q, SKILL_MIN = 0.6, 10, 0.10, 8, 6

quarters = sorted(os.path.basename(p)[len("snap_D46__"):-len(".parquet")] for p in glob.glob(os.path.join(SN, "snap_D46__*.parquet")))
qi = {q: k for k, q in enumerate(quarters)}
con = duckdb.connect(); con.execute("SET memory_limit='5GB'; SET threads=2; SET preserve_insertion_order=false")


def hold(q):
    return f"(SELECT cik, cusip, sum(shares) sh, sum(value_fixed) v FROM '{SN}/snap_D46__{q}.parquet' WHERE {CLEAN} GROUP BY 1, 2)"


def rets(q1):
    """flow__{q1}:季 q1−1 → q1 的 CUSIP 報酬(參考價、拆股調整;判斷不了的不算)"""
    return (f"(SELECT cusip, p1 / (p0 / split_k) - 1 r, p0, split_k FROM '{SE}/flow__{q1}.parquet' "
            f"WHERE p0 IS NOT NULL AND p1 IS NOT NULL AND NOT coalesce(unresolved, false) AND NOT coalesce(thin_jump, false))")


# ---------- 第 1 輪:每季的主動比例、持股數、下一季超額報酬 ----------
rows = []
for q in quarters:
    con.execute(f"CREATE OR REPLACE TEMP TABLE h AS SELECT * FROM {hold(q)}")
    con.execute("CREATE OR REPLACE TEMP TABLE w AS SELECT cusip, sum(v) / (SELECT sum(v) FROM h) W FROM h GROUP BY 1")
    con.execute("""CREATE OR REPLACE TEMP TABLE m AS SELECT h.cik, count(*) n, 0.5 * (sum(abs(h.v / t.tv - w.W)) + 1 - sum(w.W)) asv
                   FROM h JOIN (SELECT cik, sum(v) tv FROM h GROUP BY 1) t USING (cik) JOIN w USING (cusip) GROUP BY 1""")
    k = qi[q]
    if k + 1 < len(quarters) and os.path.exists(os.path.join(SE, f"flow__{quarters[k + 1]}.parquet")):
        con.execute(f"CREATE OR REPLACE TEMP TABLE r AS SELECT * FROM {rets(quarters[k + 1])}")
        con.execute("""CREATE OR REPLACE TEMP TABLE agg AS SELECT sum(w.W * r.r) / sum(w.W) ragg FROM w JOIN r USING (cusip)""")
        con.execute("""CREATE OR REPLACE TEMP TABLE e AS SELECT h.cik, sum(h.v * r.r) / sum(h.v) - (SELECT ragg FROM agg) ex, count(*) nr
                       FROM h JOIN r USING (cusip) GROUP BY 1""")
        df = con.execute("SELECT m.cik, m.n, m.asv, CASE WHEN e.nr >= 10 THEN e.ex END ex FROM m LEFT JOIN e USING (cik)").fetchdf()
    else:
        df = con.execute("SELECT cik, n, asv, NULL::DOUBLE ex FROM m").fetchdf()
    df["q"] = q; rows.append(df)
MQ = pd.concat(rows, ignore_index=True)
MQ["k"] = MQ["q"].map(qi)

# ---------- 第 2 輪:每個季配對 P−1 → P ----------
dec = []
for P in quarters:
    kP = qi[P]
    Pd = dt.date.fromisoformat(P)
    if Pd < dt.date(2015, 6, 30) or kP == 0:
        continue
    A = deadline(Pd) + dt.timedelta(days=1); t = pd.Period(f"{A.year}-{A.month:02d}", "M")
    past = MQ[(MQ["k"] >= kP - SKILL_Q) & (MQ["k"] <= kP - 1) & MQ["ex"].notna()]
    sk = past.groupby("cik")["ex"].agg(["mean", "count"]); sk = sk[sk["count"] >= SKILL_MIN]["mean"]
    cur = MQ[(MQ["k"] == kP)].set_index("cik")
    act = cur[(cur["asv"] >= AS_MIN) & (cur["n"] >= N_MIN)].index
    cand = sk[sk.index.isin(act)].sort_values(ascending=False)
    n_top = int(np.ceil(TOP * len(cand))); SK = list(cand.index[:n_top]); ACT = list(act)
    a = quarters[kP - 1]
    con.execute(f"CREATE OR REPLACE TEMP TABLE s0 AS SELECT * FROM {hold(a)}"); con.execute(f"CREATE OR REPLACE TEMP TABLE s1 AS SELECT * FROM {hold(P)}")
    con.execute(f"CREATE OR REPLACE TEMP TABLE c AS SELECT DISTINCT cik FROM '{SN}/snap_D46__{a}.parquet' INTERSECT SELECT DISTINCT cik FROM '{SN}/snap_D46__{P}.parquet'")
    con.execute(f"CREATE OR REPLACE TEMP TABLE rr AS SELECT * FROM {rets(P)}")
    con.execute("""CREATE OR REPLACE TEMP TABLE pos AS SELECT coalesce(s1.cik, s0.cik) cik, coalesce(s1.cusip, s0.cusip) cusip, coalesce(s0.sh, 0) sh0, coalesce(s1.sh, 0) sh1, coalesce(s0.v, 0) v0
                   FROM s0 FULL OUTER JOIN s1 USING (cik, cusip) WHERE coalesce(s1.cik, s0.cik) IN (SELECT cik FROM c)""")
    con.execute("""CREATE OR REPLACE TEMP TABLE pf AS SELECT pos.cik, pos.cusip, pos.v0, (pos.sh1 - pos.sh0 * rr.split_k) * (rr.p0 / rr.split_k) flow
                   FROM pos JOIN rr USING (cusip)""")
    con.register("sk_df", pd.DataFrame({"cik": SK})); con.register("act_df", pd.DataFrame({"cik": ACT}))
    out = {}
    for lab, tab, vmin in (("SK", "sk_df", 2e8), ("ACT", "act_df", 1e9)):
        g = con.execute(f"SELECT cusip, sum(flow) flow, sum(v0) v0 FROM pf WHERE cik IN (SELECT cik FROM {tab}) GROUP BY 1").fetchdf()
        g["ind"] = [industry_at(cc, Pd) for cc in g["cusip"]]; g = g[g["ind"].notna()]
        agg = g.groupby("ind").agg(flow=("flow", "sum"), v0=("v0", "sum"), n=("cusip", "size"))
        ok = (agg["v0"] >= vmin) & (agg["n"] >= 3)
        out[lab] = (agg["flow"] / agg["v0"]).where(ok).reindex(CODES)
        out[lab + "_v0"] = float(g["v0"].sum())
    tot_v0 = float(con.execute("SELECT sum(v0) FROM pf").fetchone()[0] or 0)
    s0v = S0.loc[t] if t in S0.index else pd.Series(np.nan, index=CODES)
    Fu = exact_mean_rank([s0v.reindex(CODES), out["SK"]])
    pc = {"P": P, "決定月": str(t), "高手家數": len(SK), "主動型家數": len(ACT), "有技能分數的主動型": len(cand),
          "高手前一季市值占比%": round(100 * out["SK_v0"] / tot_v0, 2) if tot_v0 else None, "有訊號的產業(SK)": int(out["SK"].notna().sum())}
    for h in (1, 3, 6):
        r = fwd(t, h)
        if r is None:
            continue
        pc[f"IC_{h}m_SK"] = spearman(out["SK"], r)
        if h == 3:
            pc["IC_3m_ACT"] = spearman(out["ACT"], r); pc["IC_3m_F"] = spearman(Fu, r); pc["IC_3m_S0_common"] = spearman(s0v.reindex(Fu.index), r.reindex(Fu.index))
            mk = mkt_fwd(t, 3); tf = topk_mean(out["SK"], r); pc["top10_SK_minus_mkt_3m"] = None if tf is None else tf - mk
    qe = pd.Period(P[:7], "M"); same = np.expm1(LR.loc[qe - 2:qe].sum(min_count=3)).where(LR.loc[qe - 2:qe].notna().all())
    pc["同期 IC(SK)"] = spearman(out["SK"], same)
    # FL1 的全體 FLOW(同 fl1_run.py 的算法),只為了算和 FLOW_SK 的橫斷面相關(只報告)
    fa = pd.read_parquet(os.path.join(SE, f"flow__{P}.parquet"))
    fa = fa[fa["p0"].notna() & ~fa["unresolved"].fillna(False) & ~fa["thin_jump"].fillna(False)].copy()
    fa["ind"] = [industry_at(cc, Pd) for cc in fa["cusip"]]; fa = fa[fa["ind"].notna()]
    ga = fa.groupby("ind").agg(flow=("flow_fixed_usd", "sum"), v0=("value_prev", "sum"), n=("cusip", "size"))
    flow_all = (ga["flow"] / ga["v0"]).where((ga["v0"] >= 1e9) & (ga["n"] >= 3)).reindex(CODES)
    pc["SK 與全體 FLOW 的橫斷面相關"] = spearman(out["SK"], flow_all)
    # 技能延續(只報告):高手在季 P 的持股、P → P+1 的超額報酬
    nxt = MQ[(MQ["k"] == kP) & MQ["ex"].notna()].set_index("cik")["ex"]
    pc["高手下一季超額%"] = None if not len(nxt[nxt.index.isin(SK)]) else round(100 * float(nxt[nxt.index.isin(SK)].mean()), 3)
    pc["主動型下一季超額%"] = None if not len(nxt[nxt.index.isin(ACT)]) else round(100 * float(nxt[nxt.index.isin(ACT)].mean()), 3)
    dec.append(pc)
    print(P, t, len(SK), len(ACT), pc.get("IC_3m_SK") is not None, flush=True)
D = pd.DataFrame(dec); D.to_csv(os.path.join(OUT, f"fl2_decisions{TAG}.csv"), index=False)


def col(c):
    return D[c].dropna().values


h1 = col("IC_3m_SK"); x = D[["IC_3m_F", "IC_3m_S0_common"]].dropna(); h2 = (x["IC_3m_F"] - x["IC_3m_S0_common"]).values
res = {"協定": "PROTOCOL_FL2.md v1.0", "合成資料": SYN, "決定數": len(D), "持有月最後": str(LAST),
       "高手家數(中位 / 最少)": [float(D["高手家數"].median()), int(D["高手家數"].min())], "高手前一季市值占比%(中位)": float(D["高手前一季市值占比%"].median()),
       "主要 H1:IC_3m(FLOW_SK)": {**nw(h1, 1), **boot(h1)}, "主要 H2:IC_3m(F_SK) − IC_3m(S0)": {**nw(h2, 1), **boot(h2)}}
res["主要 Holm"] = holm({"H1": res["主要 H1:IC_3m(FLOW_SK)"]["雙尾 p"], "H2": res["主要 H2:IC_3m(F_SK) − IC_3m(S0)"]["雙尾 p"]})
sec = {"IC_1m(FLOW_SK)": nw(col("IC_1m_SK"), 1), "IC_6m(FLOW_SK)": nw(col("IC_6m_SK"), 2), "IC_3m(FLOW_ACT)": nw(col("IC_3m_ACT"), 1),
       "FLOW_SK 前 10 名 − 市場(3m)": nw(col("top10_SK_minus_mkt_3m"), 1)}
res["次要"] = sec; res["次要 Holm"] = holm({k: v["雙尾 p"] for k, v in sec.items()})
rep = {"技能延續:高手下一季超額%(平均)": round(float(np.nanmean(D["高手下一季超額%"].astype(float))), 3),
       "主動型下一季超額%(平均)": round(float(np.nanmean(D["主動型下一季超額%"].astype(float))), 3),
       "高手 − 主動型 下一季超額(NW)": nw((D["高手下一季超額%"].astype(float) - D["主動型下一季超額%"].astype(float)).dropna().values, 1),
       "同期 IC(SK)": nw(col("同期 IC(SK)"), 1)}
for lab, lo, hi in (("2015–2019", "2015-01-01", "2019-12-31"), ("2020–2026", "2020-01-01", "2026-12-31")):
    v = D.loc[(D["P"] >= lo) & (D["P"] <= hi), "IC_3m_SK"].dropna().values
    rep[f"IC_3m(FLOW_SK) {lab}"] = nw(v, 1) if len(v) > 2 else None
rep["FLOW_SK 和全體 FLOW 的橫斷面相關(平均)"] = round(float(D["SK 與全體 FLOW 的橫斷面相關"].mean()), 4)
res["只報告"] = rep
json.dump(res, open(os.path.join(OUT, f"fl2_results{TAG}.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
