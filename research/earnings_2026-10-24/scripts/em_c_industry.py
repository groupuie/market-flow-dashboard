#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EM1 資料層 C(v1.0):每個月底、每個 French 49 產業的盈餘訊號(只用財報與申報時間;不碰報酬)。
用法:python3 -I em_c_industry.py SCRATCH   → SCRATCH/ern/out/em1_signals.csv、em1_signals_qa.json
規則(PROTOCOL_EM1 §3):
  ① 公司:申報人身分(afs)是大型加速、加速或小型加速申報人(公開流通市值 ≥ 7,500 萬美元,代表股票有在交易);
     SIC 對到 Siccodes49;REIT(SIC 6798)不算
  ② 決定月 t 的截止 = 月 t 最後一個平日 16:00(美東);只用 accepted 早於截止的紀錄;每家公司用最新的一季,
     而且那一季的 period 不早於月 t 月底前 200 天
  ③ G = Σ(當季 − 去年同季)÷ Σ(|當季| + |去年同季|)/ 2(產業加總的對稱年增率,介於 −2 與 2);
     B = 當季 > 去年同季的公司比例;產業至少 5 家公司才有訊號"""
import os, re, sys, json, datetime as dt
import numpy as np, pandas as pd

S = sys.argv[1]; OUT = os.path.join(S, "ern", "out")
FF = ("Agric Food Soda Beer Smoke Toys Fun Books Hshld Clths Hlth MedEq Drugs Chems Rubbr Txtls BldMt Cnstr Steel FabPr Mach ElcEq "
      "Autos Aero Ships Guns Gold Mines Coal Oil Util Telcm PerSv BusSv Hardw Softw Chips LabEq Paper Boxes Trans Whlsl Rtail Meals "
      "Banks Insur RlEst Fin Other").split()
ACC = {"1-LAF", "2-ACC", "3-SRA"}; MIN_FIRMS = 5; MAX_AGE = 200
ranges = []
for line in open(os.path.join(S, "sc", "x", "Siccodes49.txt"), encoding="latin-1").read().splitlines():
    m = re.match(r"^\s*(\d{4})-(\d{4})", line)
    if m:
        ranges.append((int(m.group(1)), int(m.group(2)), cur)); continue
    m = re.match(r"^\s*(\d+)\s+(\S+)", line)
    if m:
        cur = int(m.group(1))


def ff49(sic):
    try:
        s = int(sic)
    except (TypeError, ValueError):
        return None
    if s == 6798:
        return None
    hit = [k for a, b, k in ranges if a <= s <= b]
    return hit[0] if hit else None


d = pd.read_parquet(os.path.join(OUT, "firmq.parquet"))
qa = {"公司季紀錄": int(len(d))}
d["ff"] = d["sic"].map(ff49)
qa["SIC 對不到或 REIT"] = int(d["ff"].isna().sum()); qa["非加速申報人"] = int((~d["afs"].isin(ACC)).sum())
d = d[d["ff"].notna() & d["afs"].isin(ACC)].copy(); d["ff"] = d["ff"].astype(int)
d["period"] = pd.to_datetime(d["period"]); d["accepted"] = pd.to_datetime(d["accepted"])
qa["可用紀錄"] = int(len(d)); qa["可用公司"] = int(d["cik"].nunique())


def last_weekday_1600(p):
    day = p.to_timestamp(how="end").normalize()
    while day.weekday() >= 5:
        day -= pd.Timedelta(days=1)
    return day + pd.Timedelta(hours=16)


rows = []; mkt = []
for t in pd.period_range("2009-12", "2026-05", freq="M"):
    cut = last_weekday_1600(t); mend = t.to_timestamp(how="end").normalize()
    x = d[(d["accepted"] < cut) & (d["period"] >= mend - pd.Timedelta(days=MAX_AGE))]
    if x.empty:
        continue
    x = x.sort_values(["cik", "period", "accepted"]).groupby("cik").tail(1)
    x = x.assign(diff=x["cur"] - x["prev"], scale=(x["cur"].abs() + x["prev"].abs()) / 2, up=(x["cur"] > x["prev"]).astype(float))
    g = x.groupby("ff").agg(n=("cik", "size"), sd=("diff", "sum"), ss=("scale", "sum"), B=("up", "mean"))
    for k, r in g.iterrows():
        ok = r.n >= MIN_FIRMS and r.ss > 0
        rows.append({"t": str(t), "ff": FF[k - 1], "n": int(r.n), "G": r.sd / r.ss if ok else np.nan, "B": r.B if ok else np.nan, "scale_musd": r.ss / 1e6})
    mkt.append({"t": str(t), "公司數": int(len(x)), "全體 G": float(x["diff"].sum() / x["scale"].sum()), "有訊號的產業": int(((g.n >= MIN_FIRMS) & (g.ss > 0)).sum())})
sig = pd.DataFrame(rows)
sig.to_csv(os.path.join(OUT, "em1_signals.csv"), index=False)
M = pd.DataFrame(mkt)
qa["每月(節錄)"] = M[M["t"].str.endswith(("-03", "-06", "-09", "-12"))].to_dict("records")
qa["有訊號產業數 < 30 的月份"] = M.loc[M["有訊號的產業"] < 30, "t"].tolist()
# 抽查(已知的公開數字:Apple FY2019 Q4 淨利 136.86 億、FY2018 Q4 141.25 億;Microsoft FY2019 Q4 131.87 億、FY2018 Q4 88.73 億;
#       Exxon 2019 Q4 56.9 億、2018 Q4 60.0 億;JPMorgan 2019 Q4 85.2 億、2018 Q4 70.7 億)
chk = {}
for name, cik, per in (("Apple", 320193, "2019-09-30"), ("Microsoft", 789019, "2019-06-30"), ("Exxon", 34088, "2019-12-31"), ("JPMorgan", 19617, "2019-12-31")):
    r = d[(d["cik"] == cik) & (d["period"] == pd.Timestamp(per))]
    chk[name] = r[["kind", "tag", "cur", "prev", "accepted", "ff"]].assign(ff=lambda z: z["ff"].map(lambda k: FF[k - 1]), accepted=lambda z: z["accepted"].astype(str)).to_dict("records")
qa["抽查"] = chk
json.dump(qa, open(os.path.join(OUT, "em1_signals_qa.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: v for k, v in qa.items() if k != "每月(節錄)"}, ensure_ascii=False, indent=1, default=str)[:4000])
print(M.iloc[::12].to_string())
