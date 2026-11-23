# 第 7 輪:超跌條件(VIX、Put/Call)與跟進日 × Astra 底/回(規則:PREREG.md,commit 1c2c911,跑之前)
import os, sys, json, math, time, glob, pickle
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "swing_tune_2026-10-12"))
import s4_lib
from s4_lib import load, swing, cooldown, exits
T0_ = time.time(); MAC = "/home/claude/work/macro"; YM = MAC + "/yh"
PER = {"前段": ("2010-01-01", "2017-12-31"), "後段": ("2018-01-01", "2026-07-31"), "海嘯": ("2007-07-01", "2009-06-30")}
VP = ["前段", "後段"]; VOTE = ["IDX", "MAG7", "NDX", "ALL"]; DESC = ["AI_HW", "AI_SW"]
NMIN = {"IDX": 20, "MAG7": 30, "NDX": 50, "ALL": 100, "AI_HW": 30, "AI_SW": 30}
MAG7 = {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"}
HW = "NVDA AMD AVGO QCOM MRVL ARM INTC TXN ADI MCHP NXPI ON MPWR TSM ASML AMAT LRCX KLAC TER ENTG AMKR GFS SWKS QRVO MTSI SNPS CDNS MU WDC STX SNDK PSTG NTAP ANET CSCO CIEN COHR LITE AAOI GLW CRDO ALAB DELL SMCI HPE VRT ETN GEV CEG VST NRG TLN OKLO PWR".split()
SW = "MSFT GOOGL AMZN META ORCL PLTR NOW CRM SNOW DDOG MDB CRWD PANW ZS NET APP ADBE INTU WDAY TEAM AI SOUN PATH U IOT GTLB ESTC OKTA S TWLO HUBS CRWV NBIS IREN CIFR APLD CORZ WULF".split()
L604 = json.load(open(os.path.join(HERE, "..", "expectancy_2026-10-14", "x3_r6_overlap.json")))["r6_executed_list"]
GJ = json.load(open(os.path.join(REPO, "research", "swing_tune_2026-10-12", "groups.json")))
NDXS = (set(GJ.get("NDX", [])) | set(GJ.get("NDX_missing_in_data", []))) - MAG7 - {"GOOG"}
spy = load("SPY"); cal = spy.index; CI = {d: i for i, d in enumerate(cal)}; N = len(cal)
DATA = {}
for s in L604:
    d = load(s)
    if d is None or len(d) < 260: continue
    DATA[s] = d[d.index.isin(CI)]
STK = [s for s in DATA if s not in ("SPY", "QQQ")]
GS = {"IDX": {"SPY", "QQQ"}, "MAG7": MAG7 & set(DATA), "NDX": NDXS & set(DATA), "ALL": set(STK), "AI_HW": set(HW) & set(DATA), "AI_SW": set(SW) & set(DATA)}
print("檔數", len(DATA), {k: len(v) for k, v in GS.items()}, "日曆到", cal[-1].date(), flush=True)

def yraw(sym):
    df = pd.read_pickle(os.path.join(YM, sym.replace("^", "_") + ".pkl")); return df[~df.index.duplicated(keep="last")]
def al(s): return s.reindex(s.index.union(cal)).ffill(limit=5).reindex(cal)
# ---------- 市場背景值 ----------
vx = yraw("^VIX"); vixc = al(vx.c); vixh = al(vx.h)
def pcser(old_csv, name):
    o = pd.read_csv(os.path.join(MAC, old_csv), skiprows=2); o.columns = [c.strip() for c in o.columns]
    a = pd.Series(pd.to_numeric(o["P/C Ratio"], errors="coerce").to_numpy(), index=pd.to_datetime(o["DATE"].str.strip(), format="mixed"))
    rows = {}
    for f in sorted(glob.glob(MAC + "/pcd/*.json")):
        j = json.load(open(f)); v = j.get(name)
        try: rows[pd.Timestamp(os.path.basename(f)[:10])] = float(v)
        except Exception: pass
    b = pd.Series(rows); s = pd.concat([a[a.index < b.index.min()], b]).sort_index(); s = s[~s.index.duplicated(keep="last")]
    return s[(s > 0.2) & (s < 3)]
pct_raw = pcser("totalpc.csv", "TOTAL PUT/CALL RATIO"); pce_raw = pcser("equitypc.csv", "EQUITY PUT/CALL RATIO")
pct5 = al(pct_raw.rolling(5).mean()); pce5 = al(pce_raw.rolling(5).mean())
def top(s, q, w=252): return (s.rolling(w, min_periods=w).rank(pct=True) >= 1 - q).where(s.notna() & s.shift(w - 1).notna())
F = {}
F["G1"] = (vixc >= 30).where(vixc.notna())
vh10 = vixh.rolling(10, min_periods=10).max(); F["G2"] = (vh10 >= 40).where(vh10.notna())
F["G3"] = top(pct5, 0.05)
F["G4"] = ((F["G2"] == 1) & (F["G3"] == 1)).astype(float).where(F["G2"].notna() & F["G3"].notna())
F["G5"] = ((F["G1"] == 1) & (F["G3"] == 1)).astype(float).where(F["G1"].notna() & F["G3"].notna())
# 敏感度
F["G2c"] = (vixc >= 40).where(vixc.notna())
F["G3_3"] = top(pct5, 0.03); F["G3_10"] = top(pct5, 0.10); F["G3e"] = top(pce5, 0.05)
F["G3fix"] = (pce5 >= 0.90).where(pce5.notna())

# ---------- 跟進日 ----------
def ftd(sym, corr=0.08, gain=0.015, life=40, last_day=10**9):
    d = yraw(sym).reindex(cal); C = d.c.to_numpy(float); V = d.v.to_numpy(float)
    pk = pd.Series(C).rolling(252, min_periods=252).max().to_numpy()
    state = np.full(N, np.nan); ev = []; fails = []
    inc = False; low = np.nan; lowi = -1; day1 = -1; conf = -1; cl = np.nan
    for t in range(1, N):
        if np.isnan(C[t]) or np.isnan(pk[t]): continue
        if not inc:
            if C[t] <= pk[t] * (1 - corr):
                inc = True; k0 = int(np.nanargmax(C[max(0, t - 251):t + 1])) + max(0, t - 251)
                seg = C[k0:t + 1]; lowi = k0 + int(np.nanargmin(seg)); low = C[lowi]; day1 = -1; conf = -1
            else: continue
        if C[t] >= pk[t] - 1e-9: inc = False; conf = -1; continue          # 創 252 天新高 → 修正結束
        if C[t] < low:                                                     # 破底
            if conf >= 0: fails.append((conf, t))
            low = C[t]; lowi = t; day1 = -1; conf = -1
        elif day1 < 0 and t > lowi and C[t] > C[t - 1]: day1 = t
        if conf < 0 and day1 >= 0:
            nday = t - day1 + 1
            if nday >= 4 and nday <= last_day and C[t] / C[t - 1] - 1 >= gain and V[t] > V[t - 1]:
                conf = t; cl = low; ev.append({"t": t, "low": low, "lowi": lowi, "day": nday})
        if conf >= 0 and t - conf > life: conf = -2                        # 過期(不再算已確認,也不回到「未確認」→ 空值)
        state[t] = 1.0 if conf >= 0 else (0.0 if conf == -1 else np.nan)
    return state, ev, fails, C
ST, EV, FL, IXC = ftd("^IXIC"); F["H1"] = pd.Series(ST, index=cal)
for nm, kw in {"H1_125": dict(gain=0.0125), "H1_17": dict(gain=0.017), "H1_20": dict(gain=0.02), "H1_c5": dict(corr=0.05), "H1_c10": dict(corr=0.10)}.items():
    F[nm] = pd.Series(ftd("^IXIC", **kw)[0], index=cal)
F["H1_sp"] = pd.Series(ftd("^GSPC")[0], index=cal)
# ---------- 現有「強」----------
hi = al(yraw("HYG").ac) / al(yraw("IEF").ac); f6 = (hi <= hi.rolling(60, min_periods=60).min() + 1e-12).where(hi.notna())
above = np.zeros(N); cnt = np.zeros(N)
for s in STK:
    c = DATA[s].c.reindex(cal); m = c.rolling(50).mean(); ok = (c.notna() & m.notna()).to_numpy(); above += ((c > m).to_numpy() & ok); cnt += ok
br = pd.Series(np.where(cnt > 50, above / np.maximum(cnt, 1), np.nan), index=cal)
f9bad = (~((br >= 0.40) | (br > br.shift(5)))).where(br.notna())
dix = pd.read_csv(os.path.join(MAC, "DIX.csv")); gex = pd.Series(dix.gex.to_numpy(float), index=pd.to_datetime(dix.date))
gex = gex.reindex(gex.index.union(cal)).ffill(limit=5).reindex(cal).shift(1); f15 = (gex < 0).where(gex.notna())
sc = f6.fillna(0) + f9bad.fillna(0) + f15.fillna(0); F["S"] = (sc >= 2).astype(float).where(f15.notna())
MK = {k: v.to_numpy(dtype=float) for k, v in F.items()}
print("成立比例", {k: round(float(np.nanmean(v[CI[pd.Timestamp('2010-01-04')]:])), 3) for k, v in MK.items()}, flush=True)

# ---------- 交易 ----------
BUY = []
for s, d in DATA.items():
    O, H, L, C = (d[k].to_numpy(dtype=float) for k in "ohlc"); n = len(C); p = np.array([CI[x] for x in d.index])
    b0, t0, _ = swing(O, H, L, C); cs = pd.Series(C)
    b2 = cooldown(((cs > cs.rolling(200).mean()) & (cs <= cs.rolling(7).min())).to_numpy()); xe = exits(O, H, L, C, t0)["XT"]
    for t in np.flatnonzero(b0 | b2):
        if t + 1 >= n: continue
        e = xe[t]
        if e >= n or e <= t + 1: continue
        net = O[e] / O[t + 1] - 1; BUY.append((s, p[t], int(net > 0), net))
DSTR = np.array([str(x.date()) for x in cal]); print("買點筆數", len(BUY), f"{time.time()-T0_:.0f}s", flush=True)
B = pd.DataFrame(BUY, columns=["s", "q", "win", "net"]); B["d"] = DSTR[B.q.to_numpy()]
for k, v in MK.items(): B[k] = v[B.q.to_numpy()]
FAC = [k for k in MK if k != "S"]
def cell(sub, k):
    out = {}
    for side in (1, 0):
        x = sub[sub[k] == side]; out[side] = {"n": int(len(x)), "win": round(100 * x.win.mean(), 1) if len(x) else None, "avg": round(100 * x.net.mean(), 2) if len(x) else None}
    return out
TB = {}
for g in VOTE + DESC:
    bg = B[B.s.isin(GS[g])]
    for pk, (a, b) in PER.items():
        sub = bg[(bg.d >= a) & (bg.d <= b)]
        TB[f"ALLSIG|{g}|{pk}"] = {"n": int(len(sub)), "win": round(100 * sub.win.mean(), 1) if len(sub) else None}
        for k in FAC + ["S"]:
            TB[f"{k}|{g}|{pk}"] = cell(sub, k)
            ns = sub[sub.S == 0]; TB[f"{k}|{g}|{pk}|非強"] = cell(ns, k) if k != "S" else None
def decide(k):
    res = {}
    for sgn in (1, -1):
        cnt = {}
        for pk in VP:
            c = 0
            for g in VOTE:
                x = TB[f"{k}|{g}|{pk}"]
                if x[1]["n"] >= NMIN[g] and x[0]["n"] >= NMIN[g] and sgn * (x[1]["win"] - x[0]["win"]) >= 5: c += 1
            cnt[pk] = c
        res["+" if sgn > 0 else "-"] = cnt
    ok = [d for d, c in res.items() if all(v >= 3 for v in c.values())]
    return {"votes": res, "pass": ok[0] if ok else None}
DEC = {k: decide(k) for k in FAC + ["S"]}
for k, v in DEC.items(): print(k, v)
# 重疊:成立的交易日裡有多少是「強」(2011-05 起 GEX 有資料)
OV = {}
for k in FAC:
    a = MK[k]; s_ = MK["S"]; m = (a == 1) & ~np.isnan(s_) & (DSTR >= "2010-01-01")
    OV[k] = {"days": int(m.sum()), "strong_pct": round(100 * float((s_[m] == 1).mean()), 1) if m.sum() else None}
print("重疊", OV)
pickle.dump({"B": B, "MK": MK, "cal": cal, "EV": EV, "FL": FL, "IXC": IXC, "pct5": pct5, "pce5": pce5, "vixc": vixc, "vixh": vixh, "br": br, "gex": gex, "f6": f6, "f9bad": f9bad, "f15": f15},
            open("/home/claude/work/o1.pkl", "wb"))
json.dump({"n_stocks": len(DATA), "groups": {k: len(v) for k, v in GS.items()}, "cal_last": str(cal[-1].date()), "table": TB, "decide": DEC, "overlap": OV,
           "rate_2010on": {k: round(float(np.nanmean(v[CI[pd.Timestamp('2010-01-04')]:])), 4) for k, v in MK.items()}}, open(os.path.join(HERE, "o1_result.json"), "w"), ensure_ascii=False, indent=1)
print(f"完成 {time.time()-T0_:.0f}s")
