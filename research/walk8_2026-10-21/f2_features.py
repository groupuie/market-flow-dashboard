#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk8 F2:財報 / 消息 / 資金流特徵 → out/X8.pkl(和 walk7 的 S7.pkl 同一個順序,只放新特徵)+ out/ea_events.pkl、out/ins_events.pkl
「決定日收盤時已經公開」的規則(保守,不靠 SEC 的時間戳):
- 8-K、Form 4:申報日的「下一個交易日」才算知道
- 財報日:每一份 10-Q / 10-K(報告期間 P、申報日 F)對到 (P, F] 之間最後一份 Item 2.02 的 8-K;對不到就用 F
  反應日 r = 申報日 t0 與 t0+1 之中「量 ÷ 前 20 天均量」比較大的那天;反應 EAR = r−1 收盤 → r+1 收盤(扣掉 SPY);r+1 收盤才算知道
- EPS(XBRL,每一季取「第一次申報」的數字,不用後來改過的):對到財報日的話和 EAR 同時知道;對不到就用申報日的下一個交易日
- FINRA 空單量:當天晚上才公布 → 下一個交易日才算知道(2018-08 以前沒有資料 = 缺值)
特徵(缺值 = 沒有資料;梯度提升可以直接處理缺值):
  E 財報:e_days(距上次財報反應日的交易日數)、e_ear(上次 EAR,%)、e_earz(EAR ÷ 波動)、e_gapz(反應日跳空 ÷ 波動)、e_vspk(反應日量比)、
         e_earz2(上上次 EAR ÷ 波動)、e_next(預估下次財報還有幾天)、e_in20(預估下次財報落在之後 20 天內)、e_sue(SUE)、e_sueage、e_epsup(EPS 比去年同季高)
  N 消息:n_8k20、n_8k60(8-K 件數,不含只有 2.02 / 9.01 / 5.07 的)、n_502、n_101、n_801、n_701、n_203(20 天內有沒有)、n_201、n_neg(60 天內;neg = 2.05 / 2.06 / 4.02 / 3.01 / 1.03 / 4.01 / 1.02)
  F 資金流:f_nbuy20、f_nbuy60(60 天內在公開市場買進的內部人數)、f_buyv60(買進金額 ÷ 60 天成交金額,萬分之)、f_nsell60、f_sellv60、
           f_sr5、f_sr20(場外放空量比例)、f_srz(5 天比例相對 60 天的 z)、f_ox5(場外成交量 ÷ 總量)、f_oxz
用法:python3 -I f2_features.py OUT_DIR W7_DIR"""
import glob, gzip, json, math, os, pickle, sys, zipfile, io
from datetime import datetime
import numpy as np, pandas as pd

OUT, W7 = sys.argv[1], sys.argv[2]
S = pd.read_pickle(os.path.join(W7, "out", "S7.pkl"))[["sym", "date", "i"]]
BARS = pickle.load(gzip.open(os.path.join(W7, "data", "daily.pkl.gz")))["bars"]
CIK = json.load(open(os.path.join(OUT, "data", "cik_map.json")))["map"]
FIN = pickle.load(gzip.open(os.path.join(OUT, "data", "finra_short.pkl.gz")))["short"]
spy = BARS["SPY"]; SPYC = dict(zip(spy["d"], spy["x"][:, 3]))
NEG = {"2.05", "2.06", "4.02", "3.01", "1.03", "4.01", "1.02"}; QUIET = {"2.02", "9.01", "5.07"}


def roll_sum(x, w):
    cs = np.concatenate([[0.0], np.cumsum(np.nan_to_num(x))]); out = np.empty(len(x)); k = np.arange(len(x))
    out[:] = cs[k + 1] - cs[np.maximum(k + 1 - w, 0)]; return out


def first_after(d, date):   # 第一個「日期 > date」的交易日索引
    return int(np.searchsorted(d, date, side="right"))


# ---------- 內部人(Form 4,公開市場買 P / 賣 S)
ins = []
for z in sorted(glob.glob(os.path.join(OUT, "raw", "f345", "*.zip"))):
    Z = zipfile.ZipFile(z)
    sub = pd.read_csv(io.BytesIO(Z.read("SUBMISSION.tsv")), sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK"])
    sub = sub[sub.DOCUMENT_TYPE == "4"]
    own = pd.read_csv(io.BytesIO(Z.read("REPORTINGOWNER.tsv")), sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "RPTOWNERCIK"]).drop_duplicates("ACCESSION_NUMBER")
    tr = pd.read_csv(io.BytesIO(Z.read("NONDERIV_TRANS.tsv")), sep="\t", dtype=str, usecols=["ACCESSION_NUMBER", "TRANS_CODE", "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
    tr = tr[tr.TRANS_CODE.isin(["P", "S"])]
    m = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER", how="left")
    m["v"] = pd.to_numeric(m.TRANS_SHARES, errors="coerce") * pd.to_numeric(m.TRANS_PRICEPERSHARE, errors="coerce")
    ins.append(m[["ACCESSION_NUMBER", "FILING_DATE", "ISSUERCIK", "RPTOWNERCIK", "TRANS_CODE", "TRANS_ACQUIRED_DISP_CD", "v"]])
INS = pd.concat(ins, ignore_index=True).drop_duplicates()
INS["fd"] = pd.to_datetime(INS.FILING_DATE, format="%d-%b-%Y", errors="coerce").dt.strftime("%Y-%m-%d")
INS["cik"] = pd.to_numeric(INS.ISSUERCIK, errors="coerce")
INS = INS[INS.fd.notna() & INS.cik.notna()]
INS["buy"] = (INS.TRANS_CODE == "P") & (INS.TRANS_ACQUIRED_DISP_CD == "A"); INS["sell"] = (INS.TRANS_CODE == "S") & (INS.TRANS_ACQUIRED_DISP_CD == "D")
INSG = {c: g for c, g in INS[INS.cik.isin(set(CIK.values()))].groupby("cik")}
print("Form 4 公開市場買賣筆數", len(INS), "名單內公司", len(INSG), flush=True)

# ---------- SEC 申報、EPS(每個 CIK 讀一次)
SUBS, EPS = {}, {}
for c in set(CIK.values()):
    p = os.path.join(OUT, "raw", "subs", f"{c}.json.gz"); SUBS[c] = json.load(gzip.open(p))["rows"] if os.path.exists(p) else []
    p = os.path.join(OUT, "raw", "eps", f"{c}.json.gz"); e = json.load(gzip.open(p))["eps"] if os.path.exists(p) else {}
    EPS[c] = next((v for t, v in e.items() if v), [])


def quarterly_eps(facts):
    """回傳 [(期末, EPS, 第一次申報日)];Q4 = 全年 − 前三季"""
    q, a = {}, {}
    for f in facts:
        if f.get("form") not in ("10-Q", "10-K", "10-Q/A", "10-K/A") or not f.get("start"):
            continue
        dur = (datetime.fromisoformat(f["end"]) - datetime.fromisoformat(f["start"])).days
        tgt = q if 75 <= dur <= 105 else (a if 350 <= dur <= 380 else None)
        if tgt is None:
            continue
        k = (f["start"], f["end"])
        if k not in tgt or f["filed"] < tgt[k][1]:
            tgt[k] = (float(f["val"]), f["filed"])
    out = {e: (v, fd) for (s, e), (v, fd) in q.items()}
    for (s, e), (v, fd) in a.items():
        if e in out:
            continue
        inside = [(qe, qv) for (qs, qe), (qv, qf) in q.items() if s <= qs and qe < e and (datetime.fromisoformat(e) - datetime.fromisoformat(qe)).days >= 45]
        if len(inside) == 3:
            out[e] = (v - sum(x for _, x in inside), fd)
    return sorted((e, v, fd) for e, (v, fd) in out.items())


EV, IEV, frames, cover = [], [], [], {"財報": 0, "EPS": 0, "空單": 0, "內部人": 0}
for s, g in S.groupby("sym", sort=False):
    b = BARS[s]; d = np.array(b["d"]); x = b["x"]; o, h, l, c, craw, v = (x[:, k] for k in range(6)); n = len(d); cik = CIK[s]
    pc = np.concatenate([[np.nan], c[:-1]]); trng = np.where(np.isnan(pc), h - l, np.maximum(h, pc) - np.minimum(l, pc))
    a = pd.Series(trng).rolling(20).mean().values / c; vm20 = pd.Series(v).rolling(20).mean().shift(1).values
    F = {}
    # ----- E:財報
    rows = SUBS[cik]; k8 = [r for r in rows if r["form"] == "8-K"]
    e202 = sorted(r["filingDate"] for r in k8 if "2.02" in (r["items"] or "").split(","))
    per = sorted({(r["reportDate"], r["filingDate"]) for r in rows if r["form"] in ("10-Q", "10-K") and r["reportDate"]})
    eas = []
    for pe, fd in per:
        cand = [e for e in e202 if pe < e <= fd]; eas.append((pe, cand[-1] if cand else fd, bool(cand)))
    ev = []
    for pe, fdate, matched in eas:
        t0 = int(np.searchsorted(d, fdate, side="left"))
        if t0 < 21 or t0 + 2 >= n:
            continue
        r = t0 if (v[t0] / vm20[t0] if vm20[t0] > 0 else 0) >= (v[t0 + 1] / vm20[t0] if vm20[t0] > 0 else 0) else t0 + 1
        if r + 1 >= n or d[r - 1] not in SPYC or d[r + 1] not in SPYC:
            continue
        ear = c[r + 1] / c[r - 1] - 1 - (SPYC[d[r + 1]] / SPYC[d[r - 1]] - 1); az = a[r - 1]
        ev.append({"sym": s, "cik": cik, "pe": pe, "fdate": fdate, "matched": matched, "t0": t0, "r": r, "kav": r + 1, "date_kav": d[r + 1], "ear": ear,
                   "earz": ear / (az * math.sqrt(2)) if az > 0 else np.nan, "gapz": (o[r] / c[r - 1] - 1) / az if az > 0 else np.nan,
                   "vspk": v[r] / vm20[t0] if vm20[t0] > 0 else np.nan})
    ev.sort(key=lambda z: z["kav"])
    # 同一個反應日只留一個
    ev = [z for k_, z in enumerate(ev) if k_ == 0 or z["r"] != ev[k_ - 1]["r"]]
    E = {k: np.full(n, np.nan) for k in ("e_days", "e_ear", "e_earz", "e_gapz", "e_vspk", "e_earz2", "e_next", "e_in20", "e_sue", "e_sueage", "e_epsup")}
    if ev:
        kav = np.array([z["kav"] for z in ev]); rr = np.array([z["r"] for z in ev]); idx = np.searchsorted(kav, np.arange(n), side="right") - 1; ok = idx >= 0
        for key, src in (("e_ear", "ear"), ("e_earz", "earz"), ("e_gapz", "gapz"), ("e_vspk", "vspk")):
            arr = np.array([z[src] for z in ev], float); E[key][ok] = arr[idx[ok]]
        E["e_days"][ok] = np.arange(n)[ok] - rr[idx[ok]]
        earz = np.array([z["earz"] for z in ev], float); ok2 = idx >= 1; E["e_earz2"][ok2] = earz[idx[ok2] - 1]
        sp = np.array([np.median(np.diff(rr[max(0, j - 4):j + 1])) if j >= 1 else np.nan for j in range(len(rr))]); ok1 = idx >= 1
        E["e_next"][ok1] = rr[idx[ok1]] + sp[idx[ok1]] - np.arange(n)[ok1]
        E["e_in20"] = np.where(np.isnan(E["e_next"]), np.nan, ((E["e_next"] >= 1) & (E["e_next"] <= 20)).astype(float))
        cover["財報"] += 1
    # SUE
    qe = quarterly_eps(EPS[cik])
    if len(qe) >= 9:
        ends = [datetime.fromisoformat(e) for e, _, _ in qe]; vals = np.array([v_ for _, v_, _ in qe]); diffs = {}
        for j in range(len(qe)):
            prev = [k_ for k_ in range(j) if 340 <= (ends[j] - ends[k_]).days <= 390]
            if prev:
                diffs[j] = vals[j] - vals[prev[-1]]
        kav_by_pe = {}
        for z in ev:
            if z["matched"]:
                kav_by_pe[z["pe"]] = z["kav"]
        sue_ev = []
        for j in sorted(diffs):
            past = [diffs[k_] for k_ in sorted(diffs) if k_ < j][-8:]
            if len(past) < 4 or np.std(past) <= 0:
                continue
            pe = qe[j][0]
            near = [kk for pp, kk in kav_by_pe.items() if abs((datetime.fromisoformat(pp) - ends[j]).days) <= 5]
            av = near[0] if near else first_after(d, qe[j][2])
            if av < n:
                sue_ev.append((av, diffs[j] / np.std(past), float(diffs[j] > 0)))
        if sue_ev:
            sue_ev.sort(); av = np.array([z[0] for z in sue_ev]); idx = np.searchsorted(av, np.arange(n), side="right") - 1; ok = idx >= 0
            E["e_sue"][ok] = np.array([z[1] for z in sue_ev])[idx[ok]]; E["e_sueage"][ok] = np.arange(n)[ok] - av[idx[ok]]
            E["e_epsup"][ok] = np.array([z[2] for z in sue_ev])[idx[ok]]; cover["EPS"] += 1
    F.update(E); EV.extend(ev)
    # ----- N:8-K 消息
    cnt = {k: np.zeros(n) for k in ("all", "502", "101", "801", "701", "203", "201", "neg")}
    for r_ in k8:
        its = set(x_ for x_ in (r_["items"] or "").split(",") if x_)
        t = first_after(d, r_["filingDate"])
        if t >= n or not its - QUIET:
            continue
        cnt["all"][t] += 1
        for key, it in (("502", "5.02"), ("101", "1.01"), ("801", "8.01"), ("701", "7.01"), ("203", "2.03"), ("201", "2.01")):
            cnt[key][t] += it in its
        cnt["neg"][t] += bool(its & NEG)
    F["n_8k20"], F["n_8k60"] = roll_sum(cnt["all"], 20), roll_sum(cnt["all"], 60)
    for key in ("502", "101", "801", "701", "203"):
        F["n_" + key] = (roll_sum(cnt[key], 20) > 0).astype(float)
    F["n_201"], F["n_neg"] = (roll_sum(cnt["201"], 60) > 0).astype(float), (roll_sum(cnt["neg"], 60) > 0).astype(float)
    pre = d < "2015-09-01"   # 申報資料從 2015-06 開始抓 → 60 天視窗之前不算
    for k in ("n_8k20", "n_8k60", "n_502", "n_101", "n_801", "n_701", "n_203", "n_201", "n_neg"):
        F[k][pre] = np.nan
    # ----- F:內部人
    dvol = craw * v; dv60 = roll_sum(dvol, 60)
    nb20, nb60, ns60 = np.zeros(n), np.zeros(n), np.zeros(n); bv, sv_ = np.zeros(n), np.zeros(n)
    G = INSG.get(cik)
    if G is not None and len(G):
        cover["內部人"] += 1
        G = G.assign(t=[first_after(d, f_) for f_ in G.fd]); G = G[G.t < n]
        for col, arr in (("buy", bv), ("sell", sv_)):
            gg = G[G[col]].groupby("t").v.sum()
            arr[gg.index.values] += np.nan_to_num(gg.values)
        for col, w, out in (("buy", 20, nb20), ("buy", 60, nb60), ("sell", 60, ns60)):
            diff = np.zeros(n + 1)
            for ow, gg in G[G[col]].groupby("RPTOWNERCIK"):
                ts = np.sort(gg.t.unique()); s0 = ts[0]; e0 = ts[0] + w
                for t in ts[1:]:
                    if t < e0:
                        e0 = t + w
                    else:
                        diff[s0] += 1; diff[min(e0, n)] -= 1; s0, e0 = t, t + w
                diff[s0] += 1; diff[min(e0, n)] -= 1
            out[:] = np.cumsum(diff)[:n]
        for t_, row in G[G.buy].groupby("t"):
            IEV.append({"sym": s, "t": int(t_), "date": d[int(t_)], "n_owner": int(row.RPTOWNERCIK.nunique()), "v": float(np.nansum(row.v))})
    F["f_nbuy20"], F["f_nbuy60"], F["f_nsell60"] = nb20, nb60, ns60
    F["f_buyv60"] = np.where(dv60 > 0, 1e4 * roll_sum(bv, 60) / dv60, np.nan); F["f_sellv60"] = np.where(dv60 > 0, 1e4 * roll_sum(sv_, 60) / dv60, np.nan)
    pre4 = d < "2015-09-01"
    for k in ("f_nbuy20", "f_nbuy60", "f_nsell60", "f_buyv60", "f_sellv60"):
        F[k][pre4] = np.nan
    # ----- F:FINRA 空單量(下一個交易日才知道 → 往後挪一天)
    shv, tov = np.full(n, np.nan), np.full(n, np.nan)
    if s in FIN:
        pos = {dd: k for k, dd in enumerate(d)}
        for dd, a_, b_ in FIN[s]:
            dd = f"{dd[:4]}-{dd[4:6]}-{dd[6:]}" if "-" not in dd else dd
            if dd in pos:
                shv[pos[dd]], tov[pos[dd]] = a_, b_
        cover["空單"] += 1
    shv = np.concatenate([[np.nan], shv[:-1]]); tov = np.concatenate([[np.nan], tov[:-1]]); vlag = np.concatenate([[np.nan], v[:-1]])
    S_, T_, V_ = pd.Series(shv), pd.Series(tov), pd.Series(vlag)
    r5 = S_.rolling(5, min_periods=4).sum() / T_.rolling(5, min_periods=4).sum(); r20 = S_.rolling(20, min_periods=15).sum() / T_.rolling(20, min_periods=15).sum()
    dr = S_ / T_; m60, s60 = dr.rolling(60, min_periods=40).mean(), dr.rolling(60, min_periods=40).std()
    ox = T_ / V_; ox5 = T_.rolling(5, min_periods=4).sum() / V_.rolling(5, min_periods=4).sum(); om, osd = ox.rolling(60, min_periods=40).mean(), ox.rolling(60, min_periods=40).std()
    F["f_sr5"], F["f_sr20"], F["f_srz"] = r5.values, r20.values, ((r5 - m60) / s60).values
    F["f_ox5"], F["f_oxz"] = ox5.values, ((ox5 - om) / osd).values
    ii = g.i.values
    frames.append(pd.DataFrame({k: np.asarray(val, float)[ii] for k, val in F.items()}, index=g.index))
X = pd.concat(frames).loc[S.index].replace([np.inf, -np.inf], np.nan).astype("float32")
X.to_pickle(os.path.join(OUT, "out", "X8.pkl"))
EVD = pd.DataFrame(EV); EVD.to_pickle(os.path.join(OUT, "out", "ea_events.pkl")); pd.DataFrame(IEV).to_pickle(os.path.join(OUT, "out", "ins_events.pkl"))
print("X8", X.shape, "有資料的公司數", cover)
print("各特徵有值的比例 %:", {k: round(100 * float(X[k].notna().mean()), 1) for k in X.columns})
print("財報事件", len(EVD), "對到 8-K 的比例 %", round(100 * float(EVD.matched.mean()), 1), "反應日 = 申報日當天 %", round(100 * float((EVD.r == EVD.t0).mean()), 1))
