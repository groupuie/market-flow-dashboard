# 📊量化 抄底:資金氣候門檻放寬(規則:p5_prereg.md,commit 82b5129(rebase 前 255b11e),跑之前)
import os, sys, json, math, time
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "swing_tune_2026-10-12")); sys.path.insert(0, os.path.join(REPO, "scripts"))
from s4_lib import load, DT, G
import flow_climate as FCE
T0 = time.time()
CAND = [0.80, 0.65, 0.50, 0.35, 0.20, None]          # None = 不看氣候(只描述)
PER = {"前段": ("2010-01-01", "2017-12-31"), "後段": ("2018-01-01", "2026-07-31"), "全期": ("2010-01-01", "2026-07-31")}
LASTY = ("2025-10-10", "2026-10-09")
FC = "/home/claude/work/fc/fc_series.json"
AI = set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI".split())   # research/flow_climate_2026-10/rules.py

fs = json.load(open(FC)); CL = {d: c for d, c in zip(fs["d"], fs["clim"]) if c is not None and not (isinstance(c, float) and math.isnan(c))}
mk = json.load(open(FC + ".mkt.json")); MB = dict(zip(mk["d"], mk["m"]))
meta = json.load(open(os.path.join(DT, "meta.json")))
eq = sorted(s for s, v in meta.items() if v.get("type") == "EQUITY")
spy = load("SPY"); cal = spy.index; CI = set(cal)
DATA = {}
for s in ["SPY", "QQQ"] + eq:
    d = load(s)
    if d is None or len(d) < 260: continue
    DATA[s] = d[d.index.isin(CI)]
STK = [s for s in DATA if s not in ("SPY", "QQQ")]
GS = {"IDX": {"SPY", "QQQ"}, "MAG7": set(G["MAG7"]), "NDX": set(G["NDX"]), "ALL": set(STK), "AI": AI & set(STK)}
VOTE = ["IDX", "MAG7", "NDX", "ALL"]; GALL = VOTE + ["AI"]
print("檔數", len(DATA), "氣候", min(CL), "~", max(CL), f"{time.time()-T0:.0f}s")

def key(x): return "none" if x is None else f"{x:.2f}"
EV = {}      # (key, group, period) -> list of (r20, r40, dd40, bits, sym, date)
BASE = {}    # (group, period) -> [n, up20, up40, dd40, sum r20, sum r40]
LY = {key(x): 0 for x in CAND}; LYS = {key(x): [] for x in CAND}
for s, d in DATA.items():
    D = [str(x.date()) for x in d.index]; O = d.o.to_numpy(float); L = d.l.to_numpy(float); C = d.c.to_numpy(float); n = len(C)
    grp = [g for g in GALL if s in GS[g]]
    # 結果(隔天開盤買)
    r20 = np.full(n, np.nan); r40 = np.full(n, np.nan); dd = np.full(n, np.nan)
    for t in range(n - 41):
        o1 = O[t + 1]
        if not (o1 > 0): continue
        r20[t] = math.log(C[t + 20] / o1); r40[t] = math.log(C[t + 40] / o1); dd[t] = L[t + 1:t + 41].min() / o1 - 1
    for pk, (a, b) in PER.items():
        m = np.array([(a <= x <= b) for x in D]) & ~np.isnan(r40)
        for g in grp:
            B = BASE.setdefault((g, pk), [0, 0, 0, 0, 0.0, 0.0])
            B[0] += int(m.sum()); B[1] += int((r20[m] > 0).sum()); B[2] += int((r40[m] > 0).sum()); B[3] += int((dd[m] <= -0.10).sum())
            B[4] += float(r20[m].sum()); B[5] += float(r40[m].sum())
    for x in CAND:
        th = dict(FCE.TH); th["buy"] = -1.0 if x is None else x
        clim_of = (lambda dd_: CL.get(dd_, 0.5)) if x is None else (lambda dd_: CL.get(dd_))
        ev, _ = FCE.fc_events(D, list(C), clim_of, th=th)
        for e in ev:
            if e["k"] != "buy": continue
            i = e["i"]
            if LASTY[0] <= D[i] <= LASTY[1]: LY[key(x)] += 1; LYS[key(x)].append((s, D[i]))
            if np.isnan(r40[i]): continue
            for pk, (a, b) in PER.items():
                if not (a <= D[i] <= b): continue
                for g in grp: EV.setdefault((key(x), g, pk), []).append((r20[i], r40[i], dd[i], MB.get(D[i]), s, D[i]))
print("events done", f"{time.time()-T0:.0f}s")

def summ(L_):
    if not L_: return {"n": 0}
    a = np.array([(r2, r4, d4) for r2, r4, d4, *_ in L_], float)
    return {"n": len(L_), "up20": round(100 * float((a[:, 0] > 0).mean()), 1), "up40": round(100 * float((a[:, 1] > 0).mean()), 1),
            "dd40": round(100 * float((a[:, 2] <= -0.10).mean()), 1), "mu20": round(100 * float(a[:, 0].mean()), 1), "mu40": round(100 * float(a[:, 1].mean()), 1)}
def bsum(g, pk):
    B = BASE[(g, pk)]
    return {"n": B[0], "up20": round(100 * B[1] / B[0], 1), "up40": round(100 * B[2] / B[0], 1), "dd40": round(100 * B[3] / B[0], 1),
            "mu20": round(100 * B[4] / B[0], 1), "mu40": round(100 * B[5] / B[0], 1)}
RES = {"base": {f"{g}|{pk}": bsum(g, pk) for g in GALL for pk in PER}, "ev": {}, "last_year": LY}
for x in CAND:
    for g in GALL:
        for pk in PER: RES["ev"][f"{key(x)}|{g}|{pk}"] = summ(EV.get((key(x), g, pk), []))
log = []
def passes(x):
    ok = True
    for pk in ("前段", "後段"):
        e, b = RES["ev"][f"{key(x)}|ALL|{pk}"], RES["base"][f"ALL|{pk}"]
        a_ok = e["n"] >= 50 and e["up40"] >= b["up40"] + 3 and e["up20"] >= b["up20"]
        e2, b2 = RES["ev"][f"{key(x)}|NDX|{pk}"], RES["base"][f"NDX|{pk}"]
        n_ok = (e2["n"] < 30) or (e2["up40"] >= b2["up40"])
        log.append(f"  X={key(x)} {pk}:ALL n={e['n']} 40天 {e.get('up40')}%(平常 {b['up40']})、20天 {e.get('up20')}%(平常 {b['up20']}) → {a_ok};"
                   f"NDX n={e2['n']} 40天 {e2.get('up40')}%(平常 {b2['up40']}) → {n_ok}")
        ok = ok and a_ok and n_ok
    return ok
chosen = 0.80
for x in (0.65, 0.50, 0.35, 0.20):
    p = passes(x); log.append(f"X={x:.2f} {'通過' if p else '沒過'}")
    if not p: break
    chosen = x
log.append(f"新門檻 = {chosen:.2f}" + ("(不放寬)" if chosen == 0.80 else ""))
RES["decision"] = {"chosen": chosen}
# 只描述:選定門檻的分級(後段、ALL)與 STATS.buy
def grade(L_):
    out = {}
    for nm, f in (("strong", lambda b: b is not None and (b & FCE.MK["cor"]) != 0), ("normal", lambda b: b is not None and not (b & FCE.MK["cor"]) and (b & FCE.MK["vix"]) != 0),
                  ("weak", lambda b: b is not None and not (b & (FCE.MK["cor"] | FCE.MK["vix"])))):
        sub = [e for e in L_ if f(e[3])]; out[nm] = summ(sub)
    return out
RES["grade_chosen"] = {pk: grade(EV.get((key(chosen), "ALL", pk), [])) for pk in PER}
RES["grade_all_x"] = {key(x): {f"{g}|{pk}": grade(EV.get((key(x), g, pk), [])) for g in ("ALL", "NDX", "MAG7") for pk in PER} for x in CAND}   # 只描述:每個門檻的強/照舊/弱
RES["ai_chosen"] = {"ev": RES["ev"][f"{key(chosen)}|AI|全期"], "base": RES["base"]["AI|全期"]}
RES["last_year_list"] = {k: v[:80] for k, v in LYS.items()}
RES["log"] = log
json.dump(RES, open(os.path.join(HERE, "s1_result.json"), "w"), ensure_ascii=False, indent=1)
print("\n".join(log))
print("最近一年抄底數(全部追蹤股 + SPY/QQQ):", LY)
for x in CAND:
    row = [f"{g}:" + "/".join(f"{RES['ev'][f'{key(x)}|{g}|{pk}'].get('n')} {RES['ev'][f'{key(x)}|{g}|{pk}'].get('up40')}" for pk in ("前段", "後段")) for g in VOTE]
    print("X", key(x), " | ".join(row))
print("平常 40 天:", {k: v["up40"] for k, v in RES["base"].items()})
print("選定門檻分級(後段 ALL):", RES["grade_chosen"]["後段"]); print("AI 子集(全期):", RES["ai_chosen"])
print(f"完成 {time.time()-T0:.0f}s")
