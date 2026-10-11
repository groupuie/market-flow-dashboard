# 第 3 輪:通道尺度走勢 + 回檔破位過濾 + 上升中的頂變灰(規則:p2_prereg_channel.md,commit 595ad1b;程式修正 8da73e6)
import os, sys, json, pickle, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4_lib
from s4_lib import *
from regime_ref import regime, atr_wilder
s4_lib.COST = 0.0
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
DV = np.full((ND, len(STK)), np.nan)
for j, s in enumerate(STK): d = DATA[s]; DV[pos[s], j] = (d.c * d.v).to_numpy()
DVd = pd.DataFrame(DV); dv20 = DVd.rolling(20, min_periods=20).mean(); base = DVd.rolling(120, min_periods=100).mean().shift(21)
FLOW = ((dv20 >= 2.0 * base) & (dv20.rank(axis=1, ascending=False, method="first") <= 30)).to_numpy()
PER = {k: ((cal >= a) & (cal <= b)) for k, (a, b) in PERIODS.items()}; SIGP = (cal >= S0) & (cal <= S1)
GS = {"IDX": set(G["IDX"]), "MAG7": set(G["MAG7"]), "NDX": set(G["NDX"]), "ALL": set(STK)}
VOTE = ["IDX", "MAG7", "NDX", "ALL"]; NMIN = {"IDX": 30, "MAG7": 50, "NDX": 50, "ALL": 50}
RN = {1: "上升", -1: "下降", 0: "盤整"}

ACC = {}; TOPS = {}; MTN = {}; RUNS = []; SHARE = {}; R3C = {}
def acc(key, net, mae, th):
    a = ACC.setdefault(key, [0, 0, 0.0, 0])
    if len(net): a[0] += len(net); a[1] += int((net > 0).sum()); a[2] += float(net.sum()); a[3] += int((mae <= -th).sum())
def tacc(key, s10, s20):
    a = TOPS.setdefault(key, [0, 0, 0]); a[0] += len(s10); a[1] += int(s10.sum()); a[2] += int(s20.sum())
for jx, s in enumerate(DATA):
    d = DATA[s]; S = SIG[s]; p = pos[s]; n = len(d)
    O, H, L, C = (d[k].to_numpy(dtype="float64") for k in "ohlc")
    R = regime(list(H), list(L), list(C), 3.0, 0.03, 0.30); reg = np.array(R["reg"]); R3C[s] = R
    atr = np.array(atr_wilder(list(H), list(L), list(C)))
    hh20 = pd.Series(H).rolling(20, min_periods=1).max().to_numpy()
    m50 = d.c.rolling(50).mean().to_numpy(); m200 = d.c.rolling(200).mean().to_numpy()
    with np.errstate(invalid="ignore"):
        mareg = np.where((m50 > m200) & (m50 > np.roll(m50, 20)), 1, np.where((m50 < m200) & (m50 < np.roll(m50, 20)), -1, 0)); mareg[:220] = 0
        F = {"F1": reg == 1, "F2": (hh20 - C) / atr <= 3, "F3": C >= np.nan_to_num(m50, nan=np.inf)}
    Gm = {"G1": reg == 1, "G2": mareg == 1}
    brk_dn = np.array(R["brk_dn"]); brk_up = np.array(R["brk_up"])
    grp = [g for g, m in GS.items() if s in m]
    jj = STK.index(s) if s in STK else None
    flow_t = FLOW[p, jj] if jj is not None else np.zeros(n, bool)
    perm = {k: PER[k][p] for k in PER}; sigok = SIGP[p]
    th = 0.05 if s in GS["IDX"] else 0.10
    EX = exits(O, H, L, C, S["T0"]); rmin = RMQ(L, np.minimum); rmax = RMQ(H, np.maximum)
    def buckets(t_idx):
        out = []
        for pk in PER:
            m = perm[pk][t_idx]
            for g in grp: out.append((g, pk, m))
            out.append(("FLOW", pk, m & flow_t[t_idx]))
        return out
    # 有效性:走勢連續天數(訊號期間)、比例
    if s in GS["ALL"]:
        rr = reg[sigok]
        if len(rr):
            cut = np.flatnonzero(np.diff(rr) != 0) + 1; seg = np.split(rr, cut)
            RUNS += [len(x) for x in seg]
    for pk in PER:
        for g in grp + ["FLOW"]:
            m = perm[pk] & sigok & (flow_t if g == "FLOW" else True)
            for rv in (1, -1, 0): SHARE[(g, pk, rv)] = SHARE.get((g, pk, rv), 0) + int((m & (reg == rv)).sum())
    every = np.flatnonzero(sigok); xe = EX["XT"]
    ok, net, hold, mae = trades(O, L, every, xe, rmin); t_ok = every[ok]
    for g, pk, m in buckets(t_ok): acc(("BASE", "全部", g, pk), net[m], mae[m], th)
    # 回檔(B2)過濾
    tt = np.flatnonzero(S["B2"] & sigok); ok, net, hold, mae = trades(O, L, tt, xe, rmin); t2 = tt[ok]
    for g, pk, m in buckets(t2):
        acc(("B2", "全部", g, pk), net[m], mae[m], th)
        for f, fm in F.items():
            k_ = fm[t2]; acc(("B2", f + "留", g, pk), net[m & k_], mae[m & k_], th); acc(("B2", f + "濾", g, pk), net[m & ~k_], mae[m & ~k_], th)
        for rv in (1, -1, 0):
            mm = m & (reg[t2] == rv); acc(("B2", "R3" + RN[rv], g, pk), net[mm], mae[mm], th)
    # 底(只描述)
    tt = np.flatnonzero(S["B0"] & sigok); ok, net, hold, mae = trades(O, L, tt, xe, rmin); t2 = tt[ok]
    for g, pk, m in buckets(t2):
        acc(("B0", "全部", g, pk), net[m], mae[m], th)
        for rv in (1, -1, 0):
            mm = m & (reg[t2] == rv); acc(("B0", "R3" + RN[rv], g, pk), net[mm], mae[mm], th)
    # 下降突破當買
    tt = np.flatnonzero(brk_up & sigok); ok, net, hold, mae = trades(O, L, tt, xe, rmin); t2 = tt[ok]
    for g, pk, m in buckets(t2): acc(("突破", "全部", g, pk), net[m], mae[m], th)
    # 頂:原色 / 灰色;跌破當賣
    def ts(tt):
        tt = tt[tt + 21 < n]; e = O[tt + 1]; return tt, O[tt + 11] < e, O[tt + 21] < e
    tt, s10, s20 = ts(np.flatnonzero(sigok))
    for g, pk, m in buckets(tt): tacc(("BASE", "全部", g, pk), s10[m], s20[m])
    tt, s10, s20 = ts(np.flatnonzero(S["T0"] & sigok))
    for g, pk, m in buckets(tt):
        tacc(("T0", "全部", g, pk), s10[m], s20[m])
        for gk, gm in Gm.items():
            k_ = gm[tt]; tacc(("T0", gk + "灰", g, pk), s10[m & k_], s20[m & k_]); tacc(("T0", gk + "原", g, pk), s10[m & ~k_], s20[m & ~k_])
        for rv in (1, -1, 0):
            mm = m & (reg[tt] == rv); tacc(("T0", "R3" + RN[rv], g, pk), s10[mm], s20[mm])
    tt, s10, s20 = ts(np.flatnonzero(brk_dn & sigok))
    for g, pk, m in buckets(tt): tacc(("跌破", "全部", g, pk), s10[m], s20[m])
    # 山
    isidx = s in GS["IDX"]; ru, dn_ = (0.15, 0.10) if isidx else (0.30, 0.20)
    for P in range(120, n - 1):
        if not sigok[P]: continue
        if H[P] < H[max(0, P - 60):P + 61].max() or (P > 0 and H[P] <= H[max(0, P - 60):P].max()): continue
        lo0 = L[P - 120:P + 1].min(); tr = P + int(np.argmin(L[P:min(n, P + 121)])); lt = L[tr]
        if H[P] / lo0 - 1 < ru or 1 - lt / H[P] < dn_ or tr <= P: continue
        ks = np.flatnonzero(brk_dn[max(0, P - 10):tr]) + max(0, P - 10); av = 0.0
        if len(ks) and ks[0] + 1 < n: av = float(np.clip((O[ks[0] + 1] - lt) / (H[P] - lt), 0, 1))
        for g, pk, m in buckets(np.array([P])):
            if m[0]: MTN.setdefault((g, pk), []).append(av)
    if jx % 60 == 0: print("  ", jx, s, f"{time.time()-T0_:.0f}s")
pickle.dump(R3C, open(os.path.join(CACHE, "s6_r3.pkl"), "wb"))

def A(k):
    a = ACC.get(k)
    return None if not a or not a[0] else {"n": a[0], "win": round(100 * a[1] / a[0], 1), "avg": round(100 * a[2] / a[0], 2), "trap": round(100 * a[3] / a[0], 1)}
def TT(k):
    a = TOPS.get(k)
    return None if not a or not a[0] else {"n": a[0], "s10": round(100 * a[1] / a[0], 1), "s20": round(100 * a[2] / a[0], 1)}
runs = np.array(RUNS)
tot = {pk: sum(SHARE.get(("ALL", pk, rv), 0) for rv in (1, -1, 0)) for pk in PER}
share = {pk: {RN[rv]: round(100 * SHARE.get(("ALL", pk, rv), 0) / max(1, tot[pk]), 1) for rv in (1, -1, 0)} for pk in PER}
valid = bool(np.median(runs) >= 15 and all(10 <= v <= 70 for v in share["全期"].values()))
RES = {"validity": {"median_run": float(np.median(runs)), "mean_run": round(float(runs.mean()), 1), "share_ALL": share, "pass": valid},
       "b": {"|".join(k): A(k) for k in ACC}, "t": {"|".join(k): TT(k) for k in TOPS},
       "mtn": {f"{g}|{pk}": {"n": len(v), "median": round(100 * float(np.median(v)), 1)} for (g, pk), v in MTN.items()},
       "share": {f"{g}|{pk}|{RN[rv]}": v for (g, pk, rv), v in SHARE.items()}}
# ---- 決定 ----
log = [f"有效性:連續天數中位 {np.median(runs):.0f} 天(平均 {runs.mean():.1f})、ALL 全期比例 {share['全期']} → {'通過' if valid else '不通過'}"]
dec = {"validity": valid}
def b(k, sub, g, pk): return RES["b"].get(f"{k}|{sub}|{g}|{pk}")
d10 = {}
for f in ("F1", "F2", "F3"):
    ok_all = True; det = {}
    for pk in ("前段", "後段"):
        cnt = 0
        for g in VOTE:
            al, kp, rm = b("B2", "全部", g, pk), b("B2", f + "留", g, pk), b("B2", f + "濾", g, pk)
            c = bool(al and kp and rm and kp["n"] >= NMIN[g] and kp["trap"] <= al["trap"] - 2 and kp["win"] >= al["win"] - 1 and rm["win"] <= al["win"] - 3)
            det[f"{g}|{pk}"] = (kp and (kp["win"], kp["trap"], kp["n"]), rm and (rm["win"], rm["trap"], rm["n"]), al and (al["win"], al["trap"]), c); cnt += c
        ok_all &= cnt >= 3
    if f == "F1" and not valid: ok_all = False
    red = np.mean([b("B2", "全部", g, "後段")["trap"] - b("B2", f + "留", g, "後段")["trap"] for g in VOTE])
    d10[f] = {"pass": bool(ok_all), "trap_cut_post": round(float(red), 2), "detail": det}
    log.append(f"D10 {f}:{'通過' if ok_all else '不通過'}(後段被套平均少 {red:.1f} 點)")
pas = [f for f in d10 if d10[f]["pass"]]; dec["D10"] = {"detail": d10, "chosen": max(pas, key=lambda f: d10[f]["trap_cut_post"]) if pas else None}
log.append(f"D10 採用:{dec['D10']['chosen']}")
def t(k, sub, g, pk): return RES["t"].get(f"{k}|{sub}|{g}|{pk}")
d11 = {}
for gk in ("G1", "G2"):
    ok_all = True; det = {}; gaps = []
    for pk in ("前段", "後段"):
        cnt = 0
        for g in VOTE:
            bs, sh, gr = t("BASE", "全部", g, pk), t("T0", gk + "原", g, pk), t("T0", gk + "灰", g, pk)
            c = bool(bs and sh and gr and sh["n"] >= NMIN[g] and sh["s10"] - bs["s10"] >= 2 and gr["s10"] <= sh["s10"] - 3)
            det[f"{g}|{pk}"] = (sh and (sh["s10"], sh["n"]), gr and (gr["s10"], gr["n"]), bs and bs["s10"], c); cnt += c
            if pk == "後段" and sh and gr: gaps.append(sh["s10"] - gr["s10"])
        ok_all &= cnt >= 3
    if gk == "G1" and not valid: ok_all = False
    d11[gk] = {"pass": bool(ok_all), "gap_post": round(float(np.mean(gaps)), 2) if gaps else None, "detail": det}
    log.append(f"D11 {gk}:{'通過' if ok_all else '不通過'}(後段原色−灰色平均 {d11[gk]['gap_post']} 點)")
pas = [g for g in d11 if d11[g]["pass"]]; dec["D11"] = {"detail": d11, "chosen": max(pas, key=lambda g: d11[g]["gap_post"]) if pas else None}
log.append(f"D11 採用:{dec['D11']['chosen']}")
# D12 字樣
cnt_dn = {pk: sum(1 for g in VOTE if t("跌破", "全部", g, pk) and t("BASE", "全部", g, pk) and t("跌破", "全部", g, pk)["n"] >= NMIN[g]
                  and t("跌破", "全部", g, pk)["s20"] >= t("BASE", "全部", g, pk)["s20"]) for pk in ("前段", "後段")}
mt_ok = all((RES["mtn"].get(f"{g}|{pk}") or {"median": 0})["median"] >= 40 for g in ("MAG7", "NDX", "ALL") for pk in ("前段", "後段"))
exit_label = valid and all(v >= 3 for v in cnt_dn.values()) and mt_ok
cnt_up = {pk: sum(1 for g in VOTE if b("突破", "全部", g, pk) and b("BASE", "全部", g, pk) and b("突破", "全部", g, pk)["n"] >= NMIN[g]
                  and b("突破", "全部", g, pk)["win"] >= b("BASE", "全部", g, pk)["win"] + 3) for pk in ("前段", "後段")}
up_label = valid and all(v >= 3 for v in cnt_up.values())
dec["D12"] = {"show": valid, "exit_label": bool(exit_label), "cnt_dn": cnt_dn, "mtn_ok": mt_ok, "up_label": bool(up_label), "cnt_up": cnt_up}
log.append(f"D12 走勢與價位線:{'上' if valid else '不上'};跌破字樣「出場」:{exit_label}(賣對了組數 {cnt_dn}、山 {mt_ok});突破字樣「轉強」:{up_label}(組數 {cnt_up})")
RES["decision"] = dec; RES["log"] = log
json.dump(RES, open(os.path.join(HERE, "s6_result.json"), "w"), ensure_ascii=False, indent=1, default=str)
print("\n".join(log)); print(f"完成 {time.time()-T0_:.0f}s")
