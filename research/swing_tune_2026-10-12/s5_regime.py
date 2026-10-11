# 第 2 輪:短線記號 × 走勢(規則:p1_prereg_regime.md,commit 719ed65 之後才跑)→ s5_result.json + s5_decision.json + 印表
import os, sys, json, pickle, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4_lib
from s4_lib import *
from regime_ref import regime
import flow_climate as FCx
s4_lib.COST = 0.0          # Firstrade 免手續費(使用者 2026-10-12)
T0_ = time.time()
meta = json.load(open(os.path.join(DT, "meta.json")))
eq = sorted(s for s, v in meta.items() if v.get("type") == "EQUITY")
spy = load("SPY"); cal = spy.index; CI = {d: i for i, d in enumerate(cal)}; ND = len(cal)
DATA = {}
for s in ["SPY", "QQQ"] + eq:
    d = load(s)
    if d is None or len(d) < 260: continue
    DATA[s] = d[d.index.isin(CI)]
STK = [s for s in DATA if s not in ("SPY", "QQQ")]
SIG = pickle.load(open(os.path.join(CACHE, "s4_signals.pkl"), "rb"))
pos = {s: np.array([CI[x] for x in DATA[s].index]) for s in DATA}
# 流量明星(同 s4)
DV = np.full((ND, len(STK)), np.nan)
for j, s in enumerate(STK): d = DATA[s]; DV[pos[s], j] = (d.c * d.v).to_numpy()
DVd = pd.DataFrame(DV); dv20 = DVd.rolling(20, min_periods=20).mean(); base = DVd.rolling(120, min_periods=100).mean().shift(21)
FLOW = ((dv20 >= 2.0 * base) & (dv20.rank(axis=1, ascending=False, method="first") <= 30)).to_numpy()
q = DATA["QQQ"].c.reindex(cal).to_numpy()
CTA = np.array(FCx.cta_pos([float(v) if np.isfinite(v) else float("nan") for v in q]), dtype=float)
PER = {k: ((cal >= a) & (cal <= b)) for k, (a, b) in PERIODS.items()}; SIGP = (cal >= S0) & (cal <= S1)
GS = {"IDX": set(G["IDX"]), "MAG7": set(G["MAG7"]), "NDX": set(G["NDX"]), "ALL": set(STK)}
RN = {1: "上升", -1: "下降", 0: "盤整"}
print("資料", len(DATA), f"{time.time()-T0_:.0f}s")

ACC = {}; TOPS = {}; MTN = {}; SHARE = {}; CNT = {}
def acc(key, net, hold, mae, th):
    a = ACC.setdefault(key, [0, 0, 0.0, 0])
    if len(net): a[0] += len(net); a[1] += int((net > 0).sum()); a[2] += float(net.sum()); a[3] += int((mae <= -th).sum())
def tacc(key, s10, s20, dd, up):
    a = TOPS.setdefault(key, [0, 0, 0, 0.0, 0.0])
    a[0] += len(s10); a[1] += int(s10.sum()); a[2] += int(s20.sum()); a[3] += float(dd.sum()); a[4] += float(up.sum())
REGCACHE = {}
for jx, s in enumerate(DATA):
    d = DATA[s]; S = SIG[s]; p = pos[s]; n = len(d)
    O, H, L, C = (d[k].to_numpy(dtype="float64") for k in "ohlc")
    R = regime(list(H), list(L), list(C)); reg = np.array(R["reg"]); REGCACHE[s] = R
    m50 = d.c.rolling(50).mean().to_numpy(); m200 = d.c.rolling(200).mean().to_numpy()
    with np.errstate(invalid="ignore"):
        ma = np.where((m50 > m200) & (m50 > np.roll(m50, 20)), 1, np.where((m50 < m200) & (m50 < np.roll(m50, 20)), -1, 0)); ma[:220] = 0
    brk_dn = np.array(R["brk_dn"]); brk_up = np.array(R["brk_up"])
    grp = [g for g, m in GS.items() if s in m]
    jj = STK.index(s) if s in STK else None
    flow_t = FLOW[p, jj] if jj is not None else np.zeros(n, bool)
    perm = {k: PER[k][p] for k in PER}; sigok = SIGP[p]
    th = 0.05 if s in GS["IDX"] else 0.10
    cta_t = CTA[p]
    EX = exits(O, H, L, C, S["T0"]); rmin = RMQ(L, np.minimum); rmax = RMQ(H, np.maximum)
    def buckets(t_idx):
        out = []
        for pk in PER:
            m = perm[pk][t_idx]
            for g in grp: out.append((g, pk, m))
            out.append(("FLOW", pk, m & flow_t[t_idx]))
        return out
    for pk in PER:   # 走勢天數比例
        for g in grp + ["FLOW"]:
            m = perm[pk] & sigok & (flow_t if g == "FLOW" else True)
            for rv in (1, -1, 0): SHARE[(g, pk, rv)] = SHARE.get((g, pk, rv), 0) + int((m & (reg == rv)).sum())
    every = np.flatnonzero(sigok)
    for xk in ("XT", "X10"):
        xe = EX[xk]
        ok, net, hold, mae = trades(O, L, every, xe, rmin); t_ok = every[ok]
        for g, pk, m in buckets(t_ok):
            acc(("BASE", "全部", xk, g, pk), net[m], hold[m], mae[m], th)
            for rv in (1, -1, 0):
                mm = m & (reg[t_ok] == rv); acc(("BASE", RN[rv], xk, g, pk), net[mm], hold[mm], mae[mm], th)
        sigs = {"B0": S["B0"], "B2": S["B2"], "突破": brk_up}
        for b, sg in sigs.items():
            tt = np.flatnonzero(sg & sigok); ok, net, hold, mae = trades(O, L, tt, xe, rmin); t2 = tt[ok]
            r2 = reg[t2 - 1] if b == "突破" else reg[t2]      # 突破當天走勢已經改了 → 用前一天(都是下降)
            rm = ma[t2]
            for g, pk, m in buckets(t2):
                acc((b, "全部", xk, g, pk), net[m], hold[m], mae[m], th)
                for rv in (1, -1, 0):
                    mm = m & (r2 == rv); acc((b, RN[rv], xk, g, pk), net[mm], hold[mm], mae[mm], th)
                    mm = m & (rm == rv); acc((b, "均線" + RN[rv], xk, g, pk), net[mm], hold[mm], mae[mm], th)
                if b == "B0":
                    cs = np.nan_to_num(cta_t[t2], nan=1) <= 0
                    for rv in (1, -1, 0):
                        for cv, cm in (("強", cs), ("弱", ~cs)):
                            mm = m & (r2 == rv) & cm; acc(("B0", RN[rv] + cv, xk, g, pk), net[mm], hold[mm], mae[mm], th)
                    mm = m & cs; acc(("B0", "全部強", xk, g, pk), net[mm], hold[mm], mae[mm], th)
                    mm = m & ~cs; acc(("B0", "全部弱", xk, g, pk), net[mm], hold[mm], mae[mm], th)
    # 頂(賣對了)
    def tstats(tt):
        tt = tt[tt + 21 < n]; e = O[tt + 1]
        return tt, O[tt + 11] < e, O[tt + 21] < e, 1 - rmin.q(tt + 1, tt + 20) / e, rmax.q(tt + 1, tt + 20) / e - 1
    for name, mk in (("BASE", sigok.copy()), ("T0", S["T0"] & sigok), ("T4", S["T4"] & sigok), ("跌破", brk_dn & sigok)):
        tt, s10, s20, dd, up = tstats(np.flatnonzero(mk))
        rr = reg[tt - 1] if name == "跌破" else reg[tt]; rm = ma[tt]
        for g, pk, m in buckets(tt):
            tacc((name, "全部", g, pk), s10[m], s20[m], dd[m], up[m])
            for rv in (1, -1, 0):
                mm = m & (rr == rv); tacc((name, RN[rv], g, pk), s10[mm], s20[mm], dd[mm], up[mm])
                mm = m & (rm == rv); tacc((name, "均線" + RN[rv], g, pk), s10[mm], s20[mm], dd[mm], up[mm])
    # 記號數(每檔每年;各走勢)
    for name, mk in (("B0", S["B0"]), ("B2", S["B2"]), ("T0", S["T0"]), ("跌破", brk_dn), ("突破", brk_up)):
        for g, pk, m in buckets(np.flatnonzero(mk & sigok)): CNT[(name, g, pk)] = CNT.get((name, g, pk), 0) + int(m.sum())
    # 山:上升跌破 vs T0
    isidx = s in GS["IDX"]; ru, dn_ = (0.15, 0.10) if isidx else (0.30, 0.20)
    for P in range(120, n - 1):
        if not sigok[P]: continue
        if H[P] < H[max(0, P - 60):P + 61].max() or (P > 0 and H[P] <= H[max(0, P - 60):P].max()): continue
        lo0 = L[P - 120:P + 1].min(); tr = P + int(np.argmin(L[P:min(n, P + 121)])); lt = L[tr]
        if H[P] / lo0 - 1 < ru or 1 - lt / H[P] < dn_ or tr <= P: continue
        for name, mk in (("T0", S["T0"]), ("跌破", brk_dn)):
            ks = np.flatnonzero(mk[max(0, P - 10):tr]) + max(0, P - 10); av = 0.0
            if len(ks) and ks[0] + 1 < n: av = float(np.clip((O[ks[0] + 1] - lt) / (H[P] - lt), 0, 1))
            for g, pk, m in buckets(np.array([P])):
                if m[0]: MTN.setdefault((name, g, pk), []).append(av)
    if jx % 60 == 0: print("  ", jx, s, f"{time.time()-T0_:.0f}s")
pickle.dump(REGCACHE, open(os.path.join(CACHE, "s5_regime.pkl"), "wb"))

def A(key):
    a = ACC.get(key)
    if not a or a[0] == 0: return None
    return {"n": a[0], "win": round(100 * a[1] / a[0], 1), "avg": round(100 * a[2] / a[0], 2), "trap": round(100 * a[3] / a[0], 1)}
def TT(key):
    a = TOPS.get(key)
    if not a or a[0] == 0: return None
    return {"n": a[0], "s10": round(100 * a[1] / a[0], 1), "s20": round(100 * a[2] / a[0], 1), "dd20": round(100 * a[3] / a[0], 2), "up20": round(100 * a[4] / a[0], 2)}
RES = {"bottoms": {"|".join(k): A(k) for k in ACC}, "tops": {"|".join(k): TT(k) for k in TOPS},
       "mountains": {"|".join(k): {"n": len(v), "median": round(100 * float(np.median(v)), 1), "ge50": round(100 * float((np.array(v) >= 0.5).mean()), 1), "none": round(100 * float((np.array(v) == 0).mean()), 1)} for k, v in MTN.items()},
       "share": {f"{g}|{pk}|{RN[rv]}": v for (g, pk, rv), v in SHARE.items()}, "count": {"|".join(k): v for k, v in CNT.items()}}
json.dump(RES, open(os.path.join(HERE, "s5_result.json"), "w"), ensure_ascii=False, indent=1)
print("完成", f"{time.time()-T0_:.0f}s")
