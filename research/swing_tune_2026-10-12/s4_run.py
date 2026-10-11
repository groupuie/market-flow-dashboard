# 短線 底/頂 調整第 1 輪 — 跑全部候選(規則:p0_prereg.md,commit 72e3e1f 之後才跑)
#   用法:python3 s4_run.py            → s4_result.json + 印出表格
import os, sys, json, math, pickle, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4_lib import *
import flow_climate as FCx   # scripts/flow_climate.py 的 cta_pos
sys.path.insert(0, os.path.join(REPO, "research", "swing_marks_2026-10-11"))
from swing_ref import sw_py
T0 = time.time()

# ---------- 名單與日曆 ----------
meta = json.load(open(os.path.join(DT, "meta.json")))
eq = sorted(s for s, v in meta.items() if v.get("type") == "EQUITY")
spy = load("SPY"); cal = spy.index; CI = {d: i for i, d in enumerate(cal)}; ND = len(cal)
SYMS = ["SPY", "QQQ"] + eq
DATA = {}
for s in SYMS:
    d = load(s)
    if d is None or len(d) < 260: continue
    d = d[d.index.isin(CI)]
    DATA[s] = d
STK = [s for s in DATA if s not in ("SPY", "QQQ")]
print("檔數", len(DATA), "個股", len(STK), f"{time.time()-T0:.0f}s")

# ---------- 每檔訊號(快取)----------
cp = os.path.join(CACHE, "s4_signals.pkl")
if os.path.exists(cp): SIG = pickle.load(open(cp, "rb"))
else:
    SIG = {}
    for k, s in enumerate(DATA):
        SIG[s] = stock_signals(DATA[s])
        if k % 40 == 0: print("  訊號", k, s, f"{time.time()-T0:.0f}s")
    pickle.dump(SIG, open(cp, "wb"))
print("訊號完成", f"{time.time()-T0:.0f}s")

# ---------- 自我檢查:numpy 版 B0/T0 = 網站參考實作 ----------
chk = {}
for s in ("SPY", "QQQ", "MU", "NVDA", "AAPL", "TSLA"):
    if s not in DATA: continue
    d = DATA[s]; B = [[str(x.date()), o, h, l, c] for x, o, h, l, c in zip(d.index, d.o, d.h, d.l, d.c)]
    r = sw_py(B); ds = [str(x.date()) for x in d.index]
    chk[s] = (r["bot"] == [ds[i] for i in np.flatnonzero(SIG[s]["B0"])]) and (r["top"] == [ds[i] for i in np.flatnonzero(SIG[s]["T0"])])
print("B0/T0 = swing_ref:", chk)
assert all(chk.values())

# ---------- 市場層:流量明星、寬度、VIX、DIX/GEX、CTA ----------
pos = {s: np.array([CI[x] for x in DATA[s].index]) for s in DATA}
DV = np.full((ND, len(STK)), np.nan)
for j, s in enumerate(STK):
    d = DATA[s]; DV[pos[s], j] = (d.c * d.v).to_numpy()
DVd = pd.DataFrame(DV)
dv20 = DVd.rolling(20, min_periods=20).mean(); base = DVd.rolling(120, min_periods=100).mean().shift(21)
rk = dv20.rank(axis=1, ascending=False, method="first")
FLOW = ((dv20 >= 2.0 * base) & (rk <= 30)).to_numpy()
OSm = np.full((ND, len(STK)), np.nan)
for j, s in enumerate(STK):
    S = SIG[s]; d = DATA[s]; C = d.c.to_numpy()
    r2 = rsi2_wilder(C); lo, _ = bb_pop(C)
    with np.errstate(invalid="ignore"): o = ((np.nan_to_num(r2, nan=50) <= 10) | (C <= np.where(np.isnan(lo), -np.inf, lo))).astype(float)
    o[:20] = np.nan; OSm[pos[s], j] = o
BRd = np.nanmean(OSm, axis=1); BR3 = pd.Series(BRd).rolling(3, min_periods=1).max().to_numpy()

def cboe(fn):
    x = pd.read_csv(os.path.join(EXT, fn)); x["DATE"] = pd.to_datetime(x["DATE"], format="%m/%d/%Y")
    return x.set_index("DATE")["CLOSE"].reindex(cal).to_numpy()
VIX = cboe("VIX_History.csv"); VXN = cboe("VXN_History.csv")
dx = pd.read_csv(os.path.join(EXT, "DIX.csv"), parse_dates=["date"]).set_index("date").reindex(cal)
DIX, GEX = dx["dix"], dx["gex"]
dixq = DIX.rolling(252, min_periods=200).quantile(0.80); gexq = GEX.rolling(252, min_periods=200).quantile(0.20)
F_DIX = pd.Series((DIX >= dixq).astype(float)).rolling(3, min_periods=1).max().to_numpy() > 0
F_GEX = pd.Series((GEX <= gexq).astype(float)).rolling(3, min_periods=1).max().to_numpy() > 0
DIXOK = (dixq.notna() & gexq.notna()).to_numpy()
q = DATA["QQQ"].c.reindex(cal).to_numpy()
CTA = np.array(FCx.cta_pos([float(v) if np.isfinite(v) else float("nan") for v in q]), dtype=float)
qmx = pd.Series(q).rolling(252, min_periods=60).max().to_numpy()
COR = q <= qmx * 0.9
print("市場層完成", f"{time.time()-T0:.0f}s", "FLOW 檔日", int(FLOW.sum()), "DIX 有效日", int(DIXOK.sum()))

# ---------- 期間 ----------
PER = {k: ((cal >= a) & (cal <= b)) for k, (a, b) in PERIODS.items()}
SIGP = (cal >= S0) & (cal <= S1)
GROUP_STATIC = {"IDX": set(G["IDX"]), "MAG7": set(G["MAG7"]), "NDX": set(G["NDX"]), "ALL": set(STK)}
GROUPS = ["IDX", "MAG7", "NDX", "FLOW", "ALL"]
FILTERS = ["F_VIX", "F_BR", "F_CTA", "F_DIX", "F_GEX", "F_COR"]

class Acc:
    def __init__(self): self.d = {}
    def add(self, key, net, hold, mae, trap_th):
        a = self.d.setdefault(key, {"n": 0, "w": 0, "s": 0.0, "trap": 0, "hh": np.zeros(42, int)})
        if len(net) == 0: return
        a["n"] += len(net); a["w"] += int((net > 0).sum()); a["s"] += float(net.sum()); a["trap"] += int((mae <= -trap_th).sum())
        a["hh"] += np.bincount(np.clip(hold, 0, 41), minlength=42)
    def get(self, key):
        a = self.d.get(key)
        if not a or a["n"] == 0: return None
        cs = np.cumsum(a["hh"]); med = int(np.searchsorted(cs, a["n"] / 2))
        return {"n": a["n"], "win": round(100 * a["w"] / a["n"], 1), "avg": round(100 * a["s"] / a["n"], 2),
                "trap": round(100 * a["trap"] / a["n"], 1), "hold": med}
ACC = Acc(); PIV = {}; TOPS = {}; MTN = {}; SY = {}

BOTS = ["B0", "B1r", "B1c", "B2", "B2n", "B3", "B4", "B6"]
TOPC = ["T0", "T4", "T5", "T2", "T3", "T6"]
def piv_add(key, hit, tot):
    a = PIV.setdefault(key, [0, 0]); a[0] += int(hit); a[1] += int(tot)
def top_add(key, arr):
    a = TOPS.setdefault(key, {"n": 0, "s10": 0, "s20": 0, "dd": 0.0, "up": 0.0, "r10": 0.0})
    a["n"] += arr["n"]; a["s10"] += arr["s10"]; a["s20"] += arr["s20"]; a["dd"] += arr["dd"]; a["up"] += arr["up"]; a["r10"] += arr["r10"]

for j, s in enumerate(DATA):
    d = DATA[s]; S = SIG[s]; p = pos[s]; n = len(d)
    O, H, L, C = (d[k].to_numpy(dtype="float64") for k in "ohlc")
    grp_static = [g for g, m in GROUP_STATIC.items() if s in m]
    jj = STK.index(s) if s in STK else None
    flow_t = FLOW[p, jj] if jj is not None else np.zeros(n, bool)
    perm = {k: PER[k][p] for k in PER}; sigok = SIGP[p]
    trap_th = 0.05 if s in GROUP_STATIC["IDX"] else 0.10
    EX = exits(O, H, L, C, S["T0"]); rmin = RMQ(L, np.minimum); rmax = RMQ(H, np.maximum)
    for g in grp_static + ["FLOW"]:
        for pk in PER: SY[(g, pk)] = SY.get((g, pk), 0) + int((perm[pk] & (flow_t if g == "FLOW" else True)).sum())
    def bucket(t_idx):
        """回傳 [(組, 期間, 子集 mask)]"""
        out = []
        for pk in PER:
            m = perm[pk][t_idx]
            for g in grp_static: out.append((g, pk, m))
            out.append(("FLOW", pk, m & flow_t[t_idx]))
        return out
    # 底:候選 + 基準
    cr = S["_crsi"]
    bsig = {k: S[k] for k in BOTS if k != "B4"}
    with np.errstate(invalid="ignore"): bsig["B4"] = cooldown(np.nan_to_num(cr, nan=50) < (10 if s in GROUP_STATIC["IDX"] else 5))
    every = np.arange(n)[sigok]
    for xk, xe in EX.items():
        ok, net, hold, mae = trades(O, L, every, xe, rmin); t_ok = every[ok]
        for g, pk, m in bucket(t_ok): ACC.add(("BASE", xk, g, pk), net[m], hold[m], mae[m], trap_th)
        for b, sg in bsig.items():
            tt = np.flatnonzero(sg & sigok)
            ok, net, hold, mae = trades(O, L, tt, xe, rmin); t2 = tt[ok]
            for g, pk, m in bucket(t2): ACC.add((b, xk, g, pk), net[m], hold[m], mae[m], trap_th)
            if b == "B0" and xk == "XT":   # 濾網:強/弱
                cpos = p[t2]
                fl = {"F_VIX": np.nan_to_num(VIX[cpos], nan=0) >= 20, "F_BR": BR3[cpos] >= 0.40, "F_CTA": np.nan_to_num(CTA[cpos], nan=1) <= 0,
                      "F_DIX": F_DIX[cpos], "F_GEX": F_GEX[cpos], "F_COR": COR[cpos]}
                for f, fm in fl.items():
                    valid = DIXOK[cpos] if f in ("F_DIX", "F_GEX") else np.ones(len(t2), bool)
                    for g, pk, m in bucket(t2):
                        ACC.add((f + "+", xk, g, pk), net[m & fm & valid], hold[m & fm & valid], mae[m & fm & valid], trap_th)
                        ACC.add((f + "-", xk, g, pk), net[m & ~fm & valid], hold[m & ~fm & valid], mae[m & ~fm & valid], trap_th)
    # 轉折命中率 / 準確率
    pl, ph = pivots(H, L, S["atr14"])
    for b, sg in list(bsig.items()) + [(t, S[t]) for t in TOPC]:
        pv = pl if b.startswith("B") else ph
        ia, hit = near(pv & sigok, sg, 3)        # 命中率:轉折旁有訊號
        ib, pre = near(sg & sigok, pv, 3)        # 準確率:訊號旁有轉折
        for g, pk, m in bucket(ia): piv_add((b, "recall", g, pk), hit[m].sum(), m.sum())
        for g, pk, m in bucket(ib): piv_add((b, "prec", g, pk), pre[m].sum(), m.sum())
        for g, pk, m in bucket(ib): piv_add((b, "count", g, pk), m.sum(), 0)
    # 頂:賣對了(10/20 天)、之後 20 根最多再跌/再漲
    def top_stats(tt):
        ok = tt + 21 < n; tt = tt[ok]
        e = O[tt + 1]; o11 = O[tt + 11]; o21 = O[tt + 21]
        dd = 1 - rmin.q(tt + 1, tt + 20) / e; up = rmax.q(tt + 1, tt + 20) / e - 1
        return tt, (o11 < e), (o21 < e), dd, up, (e - o11) / e
    for t_name, tm in [("BASE", sigok.copy())] + [(t, S[t] & sigok) for t in TOPC]:
        tt, s10, s20, dd, up, r10 = top_stats(np.flatnonzero(tm))
        for g, pk, m in bucket(tt):
            top_add((t_name, g, pk), {"n": int(m.sum()), "s10": int(s10[m].sum()), "s20": int(s20[m].sum()), "dd": float(dd[m].sum()), "up": float(up[m].sum()), "r10": float(r10[m].sum())})
    # 山
    isidx = s in GROUP_STATIC["IDX"]; ru, dn_ = (0.15, 0.10) if isidx else (0.30, 0.20)
    for P in range(120, n - 1):
        if not sigok[P]: continue
        if H[P] < H[max(0, P - 60):P + 61].max() or (P > 0 and H[P] <= H[max(0, P - 60):P].max()): continue
        lo0 = L[P - 120:P + 1].min(); tr = P + int(np.argmin(L[P:min(n, P + 121)])); lt = L[tr]
        if H[P] / lo0 - 1 < ru or 1 - lt / H[P] < dn_ or tr <= P: continue
        for t_name in TOPC:
            ks = np.flatnonzero(S[t_name][max(0, P - 10):tr]) + max(0, P - 10)
            av = 0.0
            if len(ks) and ks[0] + 1 < n: av = float(np.clip((O[ks[0] + 1] - lt) / (H[P] - lt), 0, 1))
            for g, pk, m in bucket(np.array([P])):
                if m[0]: MTN.setdefault((t_name, g, pk), []).append(av)
    if j % 40 == 0: print("  評估", j, s, f"{time.time()-T0:.0f}s")

# ---------- 輸出 ----------
R = {"meta": {"n_stocks": len(STK), "periods": PERIODS, "cost_roundtrip": COST, "check_B0T0": chk,
              "stock_years": {f"{g}|{pk}": round(v / 252, 1) for (g, pk), v in SY.items()}},
     "bottoms": {}, "filters": {}, "pivots": {}, "tops": {}, "mountains": {}}
for (k, xk, g, pk), _ in ACC.d.items():
    R["bottoms" if not k.startswith("F_") else "filters"][f"{k}|{xk}|{g}|{pk}"] = ACC.get((k, xk, g, pk))
for (b, kind, g, pk), (h_, t_) in PIV.items():
    R["pivots"][f"{b}|{kind}|{g}|{pk}"] = (round(100 * h_ / t_, 1) if t_ else None, t_) if kind != "count" else h_
for (t, g, pk), a in TOPS.items():
    if a["n"]: R["tops"][f"{t}|{g}|{pk}"] = {"n": a["n"], "s10": round(100 * a["s10"] / a["n"], 1), "s20": round(100 * a["s20"] / a["n"], 1),
                                             "dd20": round(100 * a["dd"] / a["n"], 2), "up20": round(100 * a["up"] / a["n"], 2), "avoid10": round(100 * a["r10"] / a["n"], 2)}
for (t, g, pk), v in MTN.items():
    v = np.array(v); R["mountains"][f"{t}|{g}|{pk}"] = {"n": len(v), "median": round(100 * float(np.median(v)), 1), "ge50": round(100 * float((v >= 0.5).mean()), 1), "none": round(100 * float((v == 0).mean()), 1)}
json.dump(R, open(os.path.join(HERE, "s4_result.json"), "w"), ensure_ascii=False, indent=1)
print("完成", f"{time.time()-T0:.0f}s")
