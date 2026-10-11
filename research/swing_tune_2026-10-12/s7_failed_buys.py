# 第 4 輪:連續破底的買點、買點附停損、灰色頂的代價(規則:p3_prereg_failed_buys.md,commit 266217e)
import os, sys, json, pickle, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4_lib
from s4_lib import *
from regime_ref import atr_wilder
s4_lib.COST = 0.0
T0_ = time.time()
meta = json.load(open(os.path.join(DT, "meta.json")))
eq = sorted(s for s, v in meta.items() if v.get("type") == "EQUITY")
spy = load("SPY"); cal = spy.index; CI = {d: i for i, d in enumerate(cal)}
DATA = {}
for s in ["SPY", "QQQ"] + eq:
    d = load(s)
    if d is None or len(d) < 260: continue
    DATA[s] = d[d.index.isin(CI)]
STK = [s for s in DATA if s not in ("SPY", "QQQ")]
SIG = pickle.load(open(os.path.join(CACHE, "s4_signals.pkl"), "rb"))
PER = {k: ((cal >= a) & (cal <= b)) for k, (a, b) in PERIODS.items()}; SIGP = (cal >= S0) & (cal <= S1)
GS = {"IDX": set(G["IDX"]), "MAG7": set(G["MAG7"]), "NDX": set(G["NDX"]), "ALL": set(STK)}
VOTE = ["IDX", "MAG7", "NDX", "ALL"]; NMIN = {"IDX": 30, "MAG7": 50, "NDX": 50, "ALL": 50}
ACC = {}; MT = {}
def acc(key, net, mae, th):
    a = ACC.setdefault(key, [0, 0, 0.0, 0, 0])
    if len(net): a[0] += len(net); a[1] += int((net > 0).sum()); a[2] += float(net.sum()); a[3] += int((mae <= -th).sum()); a[4] += int((net <= -th).sum())
for jx, s in enumerate(DATA):
    d = DATA[s]; S = SIG[s]; p = np.array([CI[x] for x in d.index]); n = len(d)
    O, H, L, C = (d[k].to_numpy(dtype="float64") for k in "ohlc")
    atr = np.array(atr_wilder(list(H), list(L), list(C)))
    m50 = d.c.rolling(50).mean().to_numpy(); m200 = d.c.rolling(200).mean().to_numpy()
    with np.errstate(invalid="ignore"):
        upt = (m50 > m200) & (m50 > np.roll(m50, 20)); upt[:220] = False
    grp = [g for g, m in GS.items() if s in m]
    perm = {k: PER[k][p] for k in PER}; sigok = SIGP[p]
    th = 0.05 if s in GS["IDX"] else 0.10
    xe = exits(O, H, L, C, S["T0"])["XT"]; rmin = RMQ(L, np.minimum)
    buy = S["B0"] | S["B2"]; bi = np.flatnonzero(buy)
    # 連續破底:往前 20 根內的買點 s,之後到 t 有收盤 < L[s]
    rep = np.zeros(n, bool)
    for t in bi:
        for s_ in bi[(bi >= t - 20) & (bi < t)]:
            if C[s_ + 1:t + 1].min() < L[s_]: rep[t] = True; break
    def buckets(t_idx):
        out = []
        for pk in PER:
            m = perm[pk][t_idx]
            for g in grp: out.append((g, pk, m))
        return out
    for name, sg in (("買點", buy), ("B0", S["B0"]), ("B2", S["B2"])):
        tt = np.flatnonzero(sg & sigok); ok, net, hold, mae = trades(O, L, tt, xe, rmin); t2 = tt[ok]
        # 停損版
        net_s = net.copy(); mae_s = mae.copy()
        for k, t in enumerate(t2):
            stop = L[t] - atr[t]; e = xe[t]
            hit = np.flatnonzero(C[t + 1:e] < stop)
            if len(hit):
                j = t + 1 + hit[0]
                if j + 1 < n:
                    net_s[k] = O[j + 1] / O[t + 1] - 1
                    mae_s[k] = min(L[t + 1:j + 1].min() / O[t + 1] - 1, 0) if j + 1 > t + 1 else 0
        r2 = rep[t2]
        for g, pk, m in buckets(t2):
            acc((name, "全部", g, pk), net[m], mae[m], th)
            acc((name, "連續破底", g, pk), net[m & r2], mae[m & r2], th)
            acc((name, "第一個", g, pk), net[m & ~r2], mae[m & ~r2], th)
            acc((name, "停損", g, pk), net_s[m], mae_s[m], th)
    # 山:山頂附近第一個頂是不是灰;下跌途中有幾個買點、幾個是連續破底
    isidx = s in GS["IDX"]; ru, dn_ = (0.15, 0.10) if isidx else (0.30, 0.20)
    for P in range(120, n - 1):
        if not sigok[P]: continue
        if H[P] < H[max(0, P - 60):P + 61].max() or (P > 0 and H[P] <= H[max(0, P - 60):P].max()): continue
        lo0 = L[P - 120:P + 1].min(); tr = P + int(np.argmin(L[P:min(n, P + 121)])); lt = L[tr]
        if H[P] / lo0 - 1 < ru or 1 - lt / H[P] < dn_ or tr <= P: continue
        ks = np.flatnonzero(S["T0"][max(0, P - 10):tr]) + max(0, P - 10)
        rec = {"gray": None, "av": 0.0, "nbuy": int(buy[P:tr].sum()), "nrep": int((buy & rep)[P:tr].sum())}
        if len(ks) and ks[0] + 1 < n:
            rec["gray"] = bool(upt[ks[0]]); rec["av"] = float(np.clip((O[ks[0] + 1] - lt) / (H[P] - lt), 0, 1))
        for g, pk, m in buckets(np.array([P])):
            if m[0]: MT.setdefault((g, pk), []).append(rec)
    if jx % 60 == 0: print("  ", jx, s, f"{time.time()-T0_:.0f}s")

def A(k):
    a = ACC.get(k)
    return None if not a or not a[0] else {"n": a[0], "win": round(100 * a[1] / a[0], 1), "avg": round(100 * a[2] / a[0], 2), "trap": round(100 * a[3] / a[0], 1), "bigloss": round(100 * a[4] / a[0], 1)}
RES = {"b": {"|".join(k): A(k) for k in ACC}, "mtn": {}}
for (g, pk), v in MT.items():
    gr = [r for r in v if r["gray"] is True]; co = [r for r in v if r["gray"] is False]; no = [r for r in v if r["gray"] is None]
    RES["mtn"][f"{g}|{pk}"] = {"n": len(v), "灰色頂比例": round(100 * len(gr) / len(v), 1), "原色頂比例": round(100 * len(co) / len(v), 1), "沒頂": round(100 * len(no) / len(v), 1),
                              "灰色頂躲掉中位": round(100 * float(np.median([r["av"] for r in gr])), 1) if gr else None,
                              "原色頂躲掉中位": round(100 * float(np.median([r["av"] for r in co])), 1) if co else None,
                              "下跌途中買點中位": float(np.median([r["nbuy"] for r in v])), "其中連續破底中位": float(np.median([r["nrep"] for r in v]))}
def b(k, sub, g, pk): return RES["b"].get(f"{k}|{sub}|{g}|{pk}")
log = []
# D13
cnt = {}
for pk in ("前段", "後段"):
    c = 0
    for g in VOTE:
        r, f = b("買點", "連續破底", g, pk), b("買點", "第一個", g, pk)
        ok = bool(r and f and r["n"] >= NMIN[g] and r["win"] <= f["win"] - 5 and r["trap"] >= f["trap"] + 5); c += ok
        log.append(f"  D13 {g} {pk}:連續破底 {r and (r['win'], r['trap'], r['n'])} vs 第一個 {f and (f['win'], f['trap'], f['n'])} → {ok}")
    cnt[pk] = c
d13 = all(v >= 3 for v in cnt.values()); log.append(f"D13 連續破底的買點變灰:{'通過' if d13 else '不通過'} {cnt}")
# D14
cnt = {}
for pk in ("前段", "後段"):
    c = 0
    for g in VOTE:
        a_, s_ = b("買點", "全部", g, pk), b("買點", "停損", g, pk)
        ok = bool(a_ and s_ and a_["n"] >= NMIN[g] and s_["avg"] >= a_["avg"] - 0.5 and s_["bigloss"] <= a_["bigloss"] - 5); c += ok
        log.append(f"  D14 {g} {pk}:停損 {s_ and (s_['win'], s_['avg'], s_['bigloss'])} vs 不停損 {a_ and (a_['win'], a_['avg'], a_['bigloss'])} → {ok}")
    cnt[pk] = c
d14 = all(v >= 3 for v in cnt.values()); log.append(f"D14 買點附停損:{'通過' if d14 else '不通過'} {cnt}")
for g in ("IDX", "MAG7", "NDX", "ALL"):
    log.append(f"D15 {g} 全期:{RES['mtn'].get(g + '|全期')}")
RES["decision"] = {"D13": d13, "D14": d14}; RES["log"] = log
json.dump(RES, open(os.path.join(HERE, "s7_result.json"), "w"), ensure_ascii=False, indent=1)
print("\n".join(log)); print(f"完成 {time.time()-T0_:.0f}s")
