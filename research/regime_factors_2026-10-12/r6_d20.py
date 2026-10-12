# 第 6 輪 D20:兩倍 ETF 趨勢上限(規則:p6_prereg.md §3,commit 5810a76,跑之前;模擬同第 5 輪 s8_2x_sim.py)
import os, sys, json, math, time, pickle
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "swing_tune_2026-10-12"))
from s4_lib import load, EXT
T0_ = time.time()
CACHE = "/home/claude/work/swing_tune"
PER5 = {"前段": ("2010-01-01", "2017-12-31"), "後段": ("2018-01-01", "2026-10-09")}
MGMT, SPREAD = 0.0095, 0.003
VOTE = ["IDX", "MAG7", "NDX", "ALL"]
S = pickle.load(open(os.path.join(CACHE, "r6_sig.pkl"), "rb")); SIG, cal = S["SIG"], S["cal"]
R6 = json.load(open(os.path.join(HERE, "r6_result.json")))
uni = json.load(open("/home/claude/work/macro/universe.json"))
MAG7 = {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"}
DATA = {s: load(s) for s in SIG}
DATA = {s: d[d.index.isin(set(cal))] for s, d in DATA.items() if d is not None}
STK = [s for s in DATA if s not in ("SPY", "QQQ")]
GS = {"IDX": {"SPY", "QQQ"}, "MAG7": MAG7 & set(DATA), "NDX": (set(uni["ndx"]) - MAG7 - {"GOOG"}) & set(DATA), "ALL": set(STK)}
_r = pd.read_csv(os.path.join(EXT, "DTB3.csv")); _r = pd.Series(_r["DTB3"].to_numpy(float), index=pd.to_datetime(_r["observation_date"]))
RPREV = pd.Series((_r.reindex(_r.index.union(cal)).ffill().reindex(cal) / 100.0).shift(1).bfill().to_numpy(), index=cal)
IDXC = {k: DATA[k].c.reindex(cal) for k in ("SPY", "QQQ")}
IDXOFF = {k: (v < v.rolling(200).mean()).where(v.rolling(200).mean().notna()).to_numpy(dtype=float) for k, v in IDXC.items()}

def build_x2(O, C, fee, a, b):
    m = b - a + 1; XC = np.zeros(m); XO = np.zeros(m); XC[0] = 1.0; XO[0] = np.nan
    for j in range(1, m):
        t = a + j
        xo = XC[j - 1] * (1 + 2 * (O[t] / C[t - 1] - 1)); xc = XC[j - 1] * (1 + 2 * (C[t] / C[t - 1] - 1) - fee[t])
        if xo <= 0: break
        XO[j] = xo
        if xc <= 0: break
        XC[j] = xc
    return XO, XC

def sim(XO, XC, y, buy, sell, mode, off=None):
    """mode: hold / rule(S1)/ cap(S6、S7:前一天收盤 off=1 → 持股最多 1/3,超過就開盤賣到 1/3、不再加)"""
    m = len(XC); E = np.empty(m); E[0] = 1.0; ex = np.zeros(m); cash = 1.0; sh = 0.0; nb = ns = 0
    for j in range(1, m):
        po, pc = XO[j], XC[j]
        if mode == "hold":
            if j == 1 and po > 0: sh = cash / po; cash = 0.0; nb = 1
        elif j >= 2 and po > 0:
            cap = 1 / 3 if (mode == "cap" and off is not None and off[j - 1] == 1) else 1.0
            if sell[j - 1] and sh > 0: q = sh / 4; cash += q * po; sh -= q; ns += 1
            eo = cash + sh * po
            if sh * po > cap * eo * (1 + 1e-9): q = sh - cap * eo / po; cash += q * po; sh -= q; ns += 1
            if buy[j - 1]:
                amt = min(eo / 3, cash, max(0.0, cap * eo - sh * po))
                if amt > 1e-9 * eo: sh += amt / po; cash -= amt; nb += 1
        cash *= (1 + y[j]); E[j] = cash + sh * pc; ex[j] = sh * pc / E[j] if E[j] > 0 else 0.0
    return E, ex[1:], nb, ns

def metrics(E, ex, d0, d1):
    yrs = (d1 - d0).days / 365.25; fin = float(E[-1]); cagr = fin ** (1 / yrs) - 1 if fin > 0 else -1.0
    pk = np.maximum.accumulate(E); mdd = float((1 - E / pk).max())
    return {"fin": fin, "cagr": cagr, "mdd": mdd, "calmar": cagr / mdd if mdd > 0 else float("inf"), "expo": float(ex.mean())}

RES = {}
for jx, (s, d) in enumerate(DATA.items()):
    dates = d.index; pos = {x: i for i, x in enumerate(dates)}
    O, C = d.o.to_numpy(float), d.c.to_numpy(float)
    Sg = SIG[s]; buy = Sg["B0"] | Sg["B2"]; top = Sg["T0"]; p = Sg["p"]
    rp = RPREV.reindex(dates).to_numpy(); fee = (MGMT + rp + SPREAD) / 252; yd = rp / 252
    own = pd.Series(C); m200 = own.rolling(200).mean().to_numpy()
    own_off = np.where(np.isnan(m200), np.nan, (C < m200).astype(float))
    ix_off = IDXOFF["SPY" if s == "SPY" else "QQQ"][p]
    for pk, (a_, b_) in PER5.items():
        fd = cal[cal >= a_][0]
        if fd not in pos or pos[fd] < 1: continue
        i0 = pos[fd]; i1 = int(dates.searchsorted(pd.Timestamp(b_), side="right")) - 1; a = i0 - 1
        if i1 - i0 < 250: continue
        XO, XC = build_x2(O, C, fee, a, i1)
        y = yd[a:i1 + 1]; bs = buy[a:i1 + 1]; ts = top[a:i1 + 1]; d0, d1 = dates[i0], dates[i1]; out = {}
        E, ex, *_ = sim(XO, XC, y, bs, ts, "hold"); out["S0"] = metrics(E, ex, d0, d1)
        E, ex, *_ = sim(XO, XC, y, bs, ts, "rule"); out["S1"] = metrics(E, ex, d0, d1)
        E, ex, *_ = sim(XO, XC, y, bs, ts, "cap", ix_off[a:i1 + 1]); out["S6"] = metrics(E, ex, d0, d1)
        E, ex, *_ = sim(XO, XC, y, bs, ts, "cap", own_off[a:i1 + 1]); out["S7"] = metrics(E, ex, d0, d1)
        RES[(s, pk)] = out
    if jx % 150 == 0: print("  ", jx, s, f"{time.time()-T0_:.0f}s", flush=True)

SUM = {}; log = []; DEC = {}
for st in ("S6", "S7"):
    cnt = {}
    for pk in PER5:
        c = 0
        for g in VOTE:
            syms = [s for s in sorted(GS[g]) if (s, pk) in RES]
            if not syms: continue
            md0 = float(np.median([RES[(s, pk)]["S0"]["mdd"] for s in syms])); mdx = float(np.median([RES[(s, pk)][st]["mdd"] for s in syms]))
            better = sum(RES[(s, pk)][st]["calmar"] > RES[(s, pk)]["S0"]["calmar"] for s in syms)
            ok = (md0 - mdx >= 0.10) and better >= len(syms) / 2; c += ok
            row = {k: {"倍數中位": round(float(np.median([RES[(s, pk)][k]["fin"] for s in syms])), 2), "年化中位": round(100 * float(np.median([RES[(s, pk)][k]["cagr"] for s in syms])), 1),
                       "最大跌幅中位": round(100 * float(np.median([RES[(s, pk)][k]["mdd"] for s in syms])), 1), "平均持股": round(100 * float(np.mean([RES[(s, pk)][k]["expo"] for s in syms])), 1)}
                   for k in ("S0", "S1", "S6", "S7")}
            row["n"] = len(syms); row[f"{st} Calmar較好"] = int(better); SUM[f"{g}|{pk}"] = {**SUM.get(f"{g}|{pk}", {}), **row}
            log.append(f"  D20 {st} {g} {pk}(n={len(syms)}):最大跌幅中位 S0 {100*md0:.1f}% → {st} {100*mdx:.1f}%;Calmar 較好 {better}/{len(syms)} → {ok}")
        cnt[pk] = c
    DEC[st] = all(v >= 3 for v in cnt.values()); log.append(f"D20 {st}:{'通過' if DEC[st] else '不通過'} {cnt}")
per = {f"{s}|{pk}": {k: {kk: round(vv, 4) for kk, vv in v.items()} for k, v in out.items()} for (s, pk), out in RES.items() if s in ("SPY", "QQQ") or s in MAG7}
json.dump({"decision": DEC, "summary": SUM, "per_idx_mag7": per, "log": log}, open(os.path.join(HERE, "r6_d20_result.json"), "w"), ensure_ascii=False, indent=1)
print("\n".join(log))
for k, v in SUM.items(): print(k, {kk: vv for kk, vv in v.items()})
print(f"完成 {time.time()-T0_:.0f}s")
