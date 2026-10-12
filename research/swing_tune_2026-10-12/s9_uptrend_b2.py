# 第 6 輪補充(2026-10-12 18:52 使用者):「△回 很多、都不是真正的底;下降通道不該叫買 → 只標下降通道的真底,上行通道的回可以標」
#   目的:挑一個白話、看得見的「上行」定義,△回 只在上行時標;▲底 不動。只描述 留下/濾掉 的 XT 勝率、平均、被套(同 s7:成本 0)
#   候選:U1 收盤 ≥ 50 日線 且 50 日線比 10 天前高;U2 20 日線 ≥ 50 日線;U3 收盤 ≥ 50 日線(= 第 3 輪 F3);U4 = U1 且 50 日線 ≥ 200 日線
import os, sys, json, pickle, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4_lib
from s4_lib import *
s4_lib.COST = 0.0
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
ACC = {}
def acc(key, net, mae, th):
    a = ACC.setdefault(key, [0, 0, 0.0, 0])
    if len(net): a[0] += len(net); a[1] += int((net > 0).sum()); a[2] += float(net.sum()); a[3] += int((mae <= -th).sum())
NB2 = {}
for s in DATA:
    d = DATA[s]; S = SIG[s]; p = np.array([CI[x] for x in d.index]); n = len(d)
    O, H, L, C = (d[k].to_numpy(dtype="float64") for k in "ohlc")
    m20 = d.c.rolling(20).mean().to_numpy(); m50 = d.c.rolling(50).mean().to_numpy(); m200 = d.c.rolling(200).mean().to_numpy()
    with np.errstate(invalid="ignore"):
        m50p = np.roll(m50, 10); m50p[:10] = np.nan
        U = {"U1": (C >= m50) & (m50 >= m50p), "U2": m20 >= m50, "U3": C >= m50, "U4": (C >= m50) & (m50 >= m50p) & (m50 >= m200)}
    grp = [g for g, m in GS.items() if s in m]; perm = {k: PER[k][p] for k in PER}; sigok = SIGP[p]
    th = 0.05 if s in GS["IDX"] else 0.10
    xe = exits(O, H, L, C, S["T0"])["XT"]; rmin = RMQ(L, np.minimum)
    tt = np.flatnonzero(S["B2"] & sigok); ok, net, hold, mae = trades(O, L, tt, xe, rmin); t2 = tt[ok]
    for pk in PER:
        m = perm[pk][t2]
        for g in grp:
            acc(("全部", g, pk), net[m], mae[m], th)
            for u, um in U.items():
                k = np.nan_to_num(um[t2], nan=False)
                acc((u + "留", g, pk), net[m & k], mae[m & k], th); acc((u + "濾", g, pk), net[m & ~k], mae[m & ~k], th)
    # 每檔每年 △回 個數(後段)
    m = perm["後段"][t2]
    for u, um in U.items():
        k = np.nan_to_num(um[t2], nan=False)
        NB2.setdefault(u, []).append(int((m & k).sum()))
    NB2.setdefault("全部", []).append(int(m.sum()))
def A(k):
    a = ACC.get(k)
    return None if not a or not a[0] else {"n": a[0], "win": round(100 * a[1] / a[0], 1), "avg": round(100 * a[2] / a[0], 2), "trap": round(100 * a[3] / a[0], 1)}
RES = {"b": {"|".join(k): A(k) for k in ACC}, "b2_per_stock_post": {u: float(np.mean(v)) for u, v in NB2.items()}}
json.dump(RES, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "s9_result.json"), "w"), ensure_ascii=False, indent=1)
for u in ("U1", "U2", "U3", "U4"):
    print("==", u, "後段每檔△回", round(RES["b2_per_stock_post"][u], 1), "/ 全部", round(RES["b2_per_stock_post"]["全部"], 1))
    for pk in ("前段", "後段"):
        for g in ("IDX", "MAG7", "NDX", "ALL"):
            a, f, t = A((u + "留", g, pk)), A((u + "濾", g, pk)), A(("全部", g, pk))
            if a and f: print(f"  {g:5s}{pk} 留 勝{a['win']} 均{a['avg']} 套{a['trap']} n{a['n']} | 濾 勝{f['win']} 均{f['avg']} 套{f['trap']} n{f['n']} | 全 勝{t['win']} 套{t['trap']}")
