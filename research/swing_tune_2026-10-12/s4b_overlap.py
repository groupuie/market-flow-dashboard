# s4b(描述,不改決定):D1 通過的 B2(Double 7s)和現行 B0 重疊多少?怎麼放上網站(取代 / 另一種記號)
#   重疊 = 前後 3 根內有另一種訊號;分「只有 B2」「只有 B0」「兩個都有」看 XT 成績
import os, sys, json, pickle
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4_lib import *
meta = json.load(open(os.path.join(DT, "meta.json")))
eq = sorted(s for s, v in meta.items() if v.get("type") == "EQUITY")
SIG = pickle.load(open(os.path.join(CACHE, "s4_signals.pkl"), "rb"))
spy = load("SPY"); cal = spy.index; CI = {d: i for i, d in enumerate(cal)}
GS = {"IDX": set(G["IDX"]), "MAG7": set(G["MAG7"]), "NDX": set(G["NDX"])}
out = {}
acc = {}
def add(k, net):
    a = acc.setdefault(k, [0, 0, 0.0]); a[0] += len(net); a[1] += int((net > 0).sum()); a[2] += float(net.sum())
for s in SIG:
    d = load(s)
    if d is None or len(d) < 260: continue
    d = d[d.index.isin(CI)]; S = SIG[s]
    O, H, L, C = (d[k].to_numpy(dtype="float64") for k in "ohlc"); n = len(C)
    idx = d.index; sigok = (idx >= S0) & (idx <= S1)
    per = {"前段": (idx >= "2010-01-01") & (idx <= "2017-12-31"), "後段": (idx >= "2018-01-01") & (idx <= "2026-07-31")}
    b0, b2 = S["B0"], S["B2"]
    _, b2_near_b0 = near(b2, b0, 3); _, b0_near_b2 = near(b0, b2, 3)
    i2 = np.flatnonzero(b2); i0 = np.flatnonzero(b0)
    EX = exits(O, H, L, C, S["T0"]); rmin = RMQ(L, np.minimum)
    grp = [g for g, m in GS.items() if s in m] + (["ALL"] if s not in ("SPY", "QQQ") else [])
    for name, ii, m in (("B2_有B0", i2, b2_near_b0), ("B2_沒B0", i2, ~b2_near_b0), ("B0_有B2", i0, b0_near_b2), ("B0_沒B2", i0, ~b0_near_b2)):
        tt = ii[m]; tt = tt[sigok[tt]]
        ok, net, hold, mae = trades(O, L, tt, EX["XT"], rmin); t2 = tt[ok]
        for pk, pm in per.items():
            for g in grp: add((name, g, pk), net[pm[t2]])
for (name, g, pk), (nn, w, s_) in sorted(acc.items()):
    out[f"{name}|{g}|{pk}"] = {"n": nn, "win": round(100 * w / nn, 1) if nn else None, "avg": round(100 * s_ / nn, 2) if nn else None}
json.dump(out, open(os.path.join(HERE, "s4b_overlap.json"), "w"), ensure_ascii=False, indent=1)
for g in ("IDX", "MAG7", "NDX", "ALL"):
    print("==", g)
    for name in ("B2_有B0", "B2_沒B0", "B0_有B2", "B0_沒B2"):
        print("  ", name, " | ".join(f"{pk} n{out[f'{name}|{g}|{pk}']['n']:>6} {out[f'{name}|{g}|{pk}']['win']}/{out[f'{name}|{g}|{pk}']['avg']}" for pk in ("前段", "後段")))
