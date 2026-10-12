# 第 6 輪:背景值 × Astra 底/回/頂(規則:p6_prereg.md,commit 5810a76,跑之前)
import os, sys, json, math, time, pickle
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "swing_tune_2026-10-12")); sys.path.insert(0, os.path.join(REPO, "scripts"))
import s4_lib
from s4_lib import load, swing, cooldown, exits, DT
import flow_climate as FCE
s4_lib.COST = 0.0
T0_ = time.time()
MAC = "/home/claude/work/macro"; YM = os.path.join(MAC, "yh"); CACHE = "/home/claude/work/swing_tune"
PER = {"前段": ("2010-01-01", "2017-12-31"), "後段": ("2018-01-01", "2026-07-31")}
VOTE = ["IDX", "MAG7", "NDX", "ALL"]; DESC = ["AI_HW", "AI_SW"]
NMIN = {"IDX": 20, "MAG7": 30, "NDX": 50, "ALL": 100, "AI_HW": 30, "AI_SW": 30}
MAG7 = {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"}
AIG = {   # p6 §4
    "半導體": "NVDA AMD AVGO QCOM MRVL ARM INTC TXN ADI MCHP NXPI ON MPWR TSM ASML AMAT LRCX KLAC TER ENTG AMKR GFS SWKS QRVO MTSI SNPS CDNS",
    "記憶體": "MU WDC STX SNDK PSTG NTAP", "網通光": "ANET CSCO CIEN COHR LITE AAOI GLW CRDO ALAB", "伺服器": "DELL SMCI HPE",
    "電力": "VRT ETN GEV CEG VST NRG TLN OKLO PWR", "雲端巨頭": "MSFT GOOGL AMZN META ORCL",
    "AI軟體": "PLTR NOW CRM SNOW DDOG MDB CRWD PANW ZS NET APP ADBE INTU WDAY TEAM AI SOUN PATH U IOT GTLB ESTC OKTA S TWLO HUBS",
    "新雲": "CRWV NBIS IREN CIFR APLD CORZ WULF"}
AIG = {k: v.split() for k, v in AIG.items()}
HWG = ["半導體", "記憶體", "網通光", "伺服器", "電力"]; SWG = ["雲端巨頭", "AI軟體", "新雲"]
SEC_ETF = {"Information Technology": "XLK", "Financials": "XLF", "Energy": "XLE", "Health Care": "XLV", "Consumer Discretionary": "XLY",
           "Consumer Staples": "XLP", "Industrials": "XLI", "Materials": "XLB", "Utilities": "XLU", "Real Estate": "XLRE", "Communication Services": "XLC"}

# ---------- 股票 ----------
uni = json.load(open(os.path.join(MAC, "universe.json")))
meta = json.load(open(os.path.join(DT, "meta.json")))
old = [s for s, v in meta.items() if v.get("type") == "EQUITY"]
NDXS = set(uni["ndx"]) - MAG7 - {"GOOG"}
STK = sorted((set(uni["sp500"]) | set(uni["ndx"]) | set(uni["top100_dv_last_session"]) | set(old)) - {"SPY", "QQQ", "GOOG"})
spy = load("SPY"); cal = spy.index; CI = {d: i for i, d in enumerate(cal)}; N = len(cal)
DATA = {}
for s in ["SPY", "QQQ"] + STK:
    d = load(s)
    if d is None or len(d) < 260: continue
    DATA[s] = d[d.index.isin(CI)]
STK = [s for s in DATA if s not in ("SPY", "QQQ")]
GS = {"IDX": {"SPY", "QQQ"}, "MAG7": MAG7 & set(DATA), "NDX": NDXS & set(DATA), "ALL": set(STK),
      "AI_HW": {s for g in HWG for s in AIG[g]} & set(DATA), "AI_SW": {s for g in SWG for s in AIG[g]} & set(DATA)}
print("檔數", len(DATA), {k: len(v) for k, v in GS.items()}, f"{time.time()-T0_:.0f}s", flush=True)

def ycl(sym, col="ac"):   # 背景值的 Yahoo 收盤,對齊 SPY 日曆(往前補最多 5 天)
    p = os.path.join(YM, sym.replace("^", "_").replace("=", "_") + ".pkl")
    df = pd.read_pickle(p); s = df[col].astype(float)
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(s.index.union(cal)).ffill(limit=5).reindex(cal)
def cboe(name, col="CLOSE"):
    df = pd.read_csv(os.path.join(MAC, f"cboe_{name}.csv")); df.columns = [c.upper() for c in df.columns]
    s = pd.Series(pd.to_numeric(df[col if col in df.columns else df.columns[-1]], errors="coerce").to_numpy(), index=pd.to_datetime(df["DATE"], format="%m/%d/%Y"))
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(s.index.union(cal)).ffill(limit=5).reindex(cal)
def rank_pct(s, w, mp): return s.rolling(w, min_periods=mp).rank(pct=True)

# ---------- 市場層背景值(第 t 天收盤就知道)----------
F = {}
vix, v3 = ycl("^VIX", "c"), ycl("^VIX3M", "c")
F["F1"] = (vix / v3 >= 1.0).where(v3.notna())
F["F2"] = (vix >= 30).where(vix.notna())
qq = DATA["QQQ"].c.reindex(cal)
cq = pd.Series(FCE.cta_pos(list(qq.ffill().fillna(0).to_numpy())), index=cal).astype(float)
F["F3"] = (cq <= 0).where(cq.notna())
gs = ycl("^GSPC", "c"); lr = np.log(gs / gs.shift(1))
s21, s63 = lr.rolling(21).std() * math.sqrt(252), lr.rolling(63).std() * math.sqrt(252)
E = np.minimum(1.5, 0.10 / np.maximum(s21, s63))
F["F4"] = (rank_pct(E, 1260, 252) <= 0.20).where(E.notna())
tnx = ycl("^TNX", "c"); d20 = tnx - tnx.shift(20)
F["F5"] = (d20 > d20.rolling(756, min_periods=252).mean() + 2 * d20.rolling(756, min_periods=252).std()).where(d20.notna())
hi = ycl("HYG") / ycl("IEF")
F["F6"] = (hi <= hi.rolling(60, min_periods=60).min() + 1e-12).where(hi.notna())
bz = ycl("BZ=F", "c")
F["F7"] = (bz / bz.shift(20) - 1 >= 0.20).where(bz.notna() & bz.shift(20).notna())
yp = ycl("XLY") / ycl("XLP")
F["F8"] = (yp / yp.shift(60) - 1 < -0.05).where(yp.notna() & yp.shift(60).notna())
# 寬度
above = np.zeros(N); cnt = np.zeros(N)
for s in STK:
    c = DATA[s].c.reindex(cal); m = c.rolling(50).mean(); ok = (c.notna() & m.notna()).to_numpy()
    above += ((c > m).to_numpy() & ok); cnt += ok
br = pd.Series(np.where(cnt > 50, above / np.maximum(cnt, 1), np.nan), index=cal)
F["F9"] = ((br >= 0.40) | (br > br.shift(5))).where(br.notna())
def ddays(sym):
    d = DATA[sym].reindex(cal); C = d.c.to_numpy(); V = d.v.to_numpy(); out = np.full(N, np.nan); act = []
    for t in range(1, N):
        if np.isnan(C[t]) or np.isnan(C[t - 1]): continue
        if C[t] / C[t - 1] - 1 <= -0.002 and V[t] > V[t - 1]: act.append(t)
        act = [k for k in act if t - k < 25 and C[t] < C[k] * 1.05 and max(C[k:t + 1]) < C[k] * 1.05]
        out[t] = len(act)
    return pd.Series(out, index=cal)
dq, dsp = ddays("QQQ"), ddays("SPY")
F["F11q"] = (dq >= 5).where(dq.notna()); F["F11s"] = (dsp >= 5).where(dsp.notna())
c1 = cboe("COR1M")
F["F14"] = (rank_pct(c1, 252, 126) <= 0.10).where(c1.notna())
dix = pd.read_csv(os.path.join(MAC, "DIX.csv")); gex = pd.Series(dix.gex.to_numpy(float), index=pd.to_datetime(dix.date))
gex = gex.reindex(gex.index.union(cal)).ffill(limit=5).reindex(cal).shift(1)
F["F15"] = (gex < 0).where(gex.notna())
cot = pd.read_pickle(os.path.join(MAC, "cot.pkl"))["ES"]
amn = (cot.asset_mgr_positions_long - cot.asset_mgr_positions_short) / cot.open_interest_all
amr = rank_pct(amn, 156, 104); amr.index = amr.index + pd.Timedelta(days=3)    # 週二部位 → 週五發布後才算
amr = amr.reindex(amr.index.union(cal)).ffill(limit=10).reindex(cal)
F["F16"] = (amr <= 0.20).where(amr.notna())
sk = ycl("^SKEW", "c")
F["F17"] = (rank_pct(sk, 252, 126) >= 0.90).where(sk.notna())
fs = json.load(open("/home/claude/work/fc/fc_series.json"))
cl = pd.Series([np.nan if (x is None or (isinstance(x, float) and math.isnan(x))) else x for x in fs["clim"]], index=pd.to_datetime(fs["d"])).reindex(cal)
F["F19"] = (cl >= 0.35).where(cl.notna())
dx = ycl("DX-Y.NYB", "c"); dx20 = dx / dx.shift(20) - 1
F["F20"] = (rank_pct(dx20, 756, 252) >= 0.90).where(dx20.notna())
MK = {k: v.to_numpy(dtype=float) for k, v in F.items()}
print("市場背景值好了", {k: round(float(np.nanmean(v)), 3) for k, v in MK.items()}, f"{time.time()-T0_:.0f}s", flush=True)

# ---------- 族群(F10、F18)----------
spyc = DATA["SPY"].c.reindex(cal)
def eqw(members):
    R = []
    for s in members:
        if s in DATA: R.append(DATA[s].c.reindex(cal).pct_change())
    if not R: return None
    r = pd.concat(R, axis=1).mean(axis=1, skipna=True)
    return (1 + r.fillna(0)).cumprod().where(pd.concat(R, axis=1).notna().any(axis=1))
GRP = {g: eqw(m) for g, m in AIG.items()}
for sec, etf in SEC_ETF.items(): GRP[etf] = ycl(etf)
GOF = {}
for g, m in AIG.items():
    for s in m: GOF.setdefault(s, g)
for s, mm in uni["sp500_meta"].items():
    if s not in GOF and mm.get("sector") in SEC_ETF: GOF[s] = SEC_ETF[mm["sector"]]
def gser(g):
    x = GRP.get(g)
    return None if x is None else x
G21, G504 = {}, {}
spy21, spy504 = spyc / spyc.shift(21) - 1, spyc / spyc.shift(504) - 1
for g, x in GRP.items():
    if x is None: continue
    G21[g] = ((x / x.shift(21) - 1) > spy21).where(x.notna() & x.shift(21).notna()).to_numpy(dtype=float)
    G504[g] = ((x / x.shift(504) - 1) - spy504 >= 1.0).where(x.notna() & x.shift(504).notna()).to_numpy(dtype=float)

# ---------- 每檔:訊號、出場、結果、個股背景值 ----------
BUY = []; TOP = []   # (sym, cal index, win/ok, net, trap, {factor: 0/1/nan})
FAC_BUY = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12", "F13", "F14", "F15", "F16", "F17", "F18", "F19", "F20"]
SIG = {}
for jx, (s, d) in enumerate(DATA.items()):
    O, H, L, C = (d[k].to_numpy(dtype=float) for k in "ohlc"); n = len(C)
    p = np.array([CI[x] for x in d.index])
    b0, t0, _ = swing(O, H, L, C)
    cs = pd.Series(C); e7 = ((cs > cs.rolling(200).mean()) & (cs <= cs.rolling(7).min())).to_numpy(); b2 = cooldown(e7)
    SIG[s] = {"B0": b0, "B2": b2, "T0": t0, "p": p}
    xe = exits(O, H, L, C, t0)["XT"]
    m50, m150, m200 = (cs.rolling(k).mean().to_numpy() for k in (50, 150, 200))
    mx252 = cs.rolling(252).max().to_numpy(); hx252 = pd.Series(H).rolling(252).max().to_numpy()
    with np.errstate(invalid="ignore"):
        f12 = np.where(np.isnan(m200) | np.isnan(np.roll(m200, 21)), np.nan,
                       ((C > m50) & (m50 > m150) & (m150 > m200) & (m200 > np.roll(m200, 21)) & (C >= 0.75 * mx252)).astype(float))
        f13 = np.where(np.isnan(hx252), np.nan, (C >= 0.85 * hx252).astype(float))
    f12[:221] = np.nan
    g = GOF.get(s); g21 = G21.get(g); g504 = G504.get(g)
    isidx = s in ("SPY", "QQQ"); th = 0.05 if isidx else 0.10
    f11 = MK["F11s"] if s == "SPY" else MK["F11q"]
    def facs(t):
        q = p[t]
        r = {k: MK[k][q] for k in ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F14", "F15", "F16", "F17", "F19", "F20")}
        r["F11"] = f11[q]; r["F12"] = f12[t]; r["F13"] = f13[t]
        r["F10"] = g21[q] if (g21 is not None and not isidx) else np.nan
        r["F18"] = g504[q] if (g504 is not None and not isidx) else np.nan
        return r
    for t in np.flatnonzero(b0 | b2):
        if t + 1 >= n: continue
        e = xe[t]
        if e >= n or e <= t + 1: continue
        net = O[e] / O[t + 1] - 1; mae = L[t + 1:e].min() / O[t + 1] - 1
        BUY.append((s, p[t], int(net > 0), net, int(mae <= -th), facs(t), "B0" if b0[t] else "B2"))
    for t in np.flatnonzero(t0):
        if t + 11 >= n: continue
        TOP.append((s, p[t], int(O[t + 11] < O[t + 1]), O[t + 11] / O[t + 1] - 1, 0, facs(t), "T0"))
    if jx % 100 == 0: print("  ", jx, s, f"{time.time()-T0_:.0f}s", flush=True)
pickle.dump({"BUY": BUY, "TOP": TOP}, open(os.path.join(CACHE, "r6_trades.pkl"), "wb"))
DSTR = np.array([str(x.date()) for x in cal])
print("交易筆數", len(BUY), len(TOP), f"{time.time()-T0_:.0f}s", flush=True)

def table(rows, groups):
    out = {}
    for g in groups:
        mem = GS[g]
        for pk, (a, b) in PER.items():
            sub = [r for r in rows if r[0] in mem and a <= DSTR[r[1]] <= b]
            for k in FAC_BUY:
                c = {1: [0, 0, 0.0], 0: [0, 0, 0.0]}
                for r in sub:
                    v = r[5][k]
                    if v is None or (isinstance(v, float) and math.isnan(v)): continue
                    v = int(v); c[v][0] += 1; c[v][1] += r[2]; c[v][2] += r[3]
                out[(k, g, pk)] = {side: {"n": c[side][0], "win": round(100 * c[side][1] / c[side][0], 1) if c[side][0] else None,
                                          "avg": round(100 * c[side][2] / c[side][0], 2) if c[side][0] else None} for side in (1, 0)}
            base = {"n": len(sub), "win": round(100 * sum(r[2] for r in sub) / len(sub), 1) if sub else None}
            out[("ALLSIG", g, pk)] = base
    return out
TB = table(BUY, VOTE + DESC); TT = table(TOP, VOTE + DESC)

def decide(T, label):
    passed = {}; log = []
    for k in FAC_BUY:
        best = None
        for sgn in (1, -1):
            cnt = {}
            for pk in PER:
                c = 0
                for g in VOTE:
                    x = T[(k, g, pk)]
                    if x[1]["n"] >= NMIN[g] and x[0]["n"] >= NMIN[g] and sgn * (x[1]["win"] - x[0]["win"]) >= 5: c += 1
                cnt[pk] = c
            if all(v >= 3 for v in cnt.values()): best = (sgn, cnt)
            log.append(f"  {label} {k} 方向{'+' if sgn > 0 else '−'}:{cnt}")
        if best: passed[k] = 1 if best[0] > 0 else 0   # 有利的那一邊(1 = 成立那邊勝率高)
    return passed, log
PB, LB = decide(TB, "買點"); PT, LT = decide(TT, "頂")
print("D18 通過:", PB, " D19 通過:", PT, flush=True)

def combo(rows, passed, groups):
    m = len(passed); res = {}
    if m == 0: return res
    need = (m - 1) if m >= 2 else 1
    for g in groups:
        for pk, (a, b) in PER.items():
            sub = [r for r in rows if r[0] in GS[g] and a <= DSTR[r[1]] <= b]
            st, ot = [0, 0], [0, 0]
            for r in sub:
                sc = sum(1 for k, fav in passed.items() if not (isinstance(r[5][k], float) and math.isnan(r[5][k])) and int(r[5][k]) == fav)
                tgt = st if sc >= need else ot; tgt[0] += 1; tgt[1] += r[2]
            res[f"{g}|{pk}"] = {"強": {"n": st[0], "win": round(100 * st[1] / st[0], 1) if st[0] else None},
                                "其他": {"n": ot[0], "win": round(100 * ot[1] / ot[0], 1) if ot[0] else None}}
    return res
CB = combo(BUY, PB, VOTE + DESC); CT = combo(TOP, PT, VOTE + DESC)
R = {"n_stocks": len(DATA), "groups": {k: len(v) for k, v in GS.items()}, "rate": {k: round(float(np.nanmean(v)), 3) for k, v in MK.items()},
     "buy": {"|".join(map(str, k)): v for k, v in TB.items()}, "top": {"|".join(map(str, k)): v for k, v in TT.items()},
     "D18_pass": PB, "D19_pass": PT, "combo_buy": CB, "combo_top": CT, "log": LB + LT}
json.dump(R, open(os.path.join(HERE, "r6_result.json"), "w"), ensure_ascii=False, indent=1)
pickle.dump({"SIG": SIG, "MK": MK, "cal": cal}, open(os.path.join(CACHE, "r6_sig.pkl"), "wb"))
print("\n".join(LB + LT)); print("合併(買):", json.dumps(CB, ensure_ascii=False)); print("合併(頂):", json.dumps(CT, ensure_ascii=False))
print(f"完成 {time.time()-T0_:.0f}s")
