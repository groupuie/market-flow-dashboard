# 指數事件(只描述):超跌事件、跟進日事件、三種進場比較、現況
import os, json, pickle, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); YM = "/home/claude/work/macro/yh"
P = pickle.load(open("/home/claude/work/o1.pkl", "rb")); cal = P["cal"]; MK = P["MK"]; N = len(cal)
def yraw(sym):
    df = pd.read_pickle(os.path.join(YM, sym.replace("^", "_") + ".pkl")); return df[~df.index.duplicated(keep="last")]
# 長日曆(1990 起,用 ^GSPC 的交易日)
gs = yraw("^GSPC"); gs = gs[gs.index >= "1989-01-01"]; LC = gs.index; LN = len(LC)
ix = yraw("^IXIC").reindex(LC); vx = yraw("^VIX").reindex(LC)
SP = gs.c.to_numpy(float); NQ = ix.c.to_numpy(float); NQV = ix.v.to_numpy(float); VH = vx.h.to_numpy(float); VC = vx.c.to_numpy(float)
D = np.array([str(x.date()) for x in LC])
def fwd(C, t, k): return (C[t + k] / C[t] - 1) * 100 if t + k < LN else None
def worst(C, t, k): return (np.nanmin(C[t + 1:t + k + 1]) / C[t] - 1) * 100 if t + k < LN else None
def first(mask, gap=20):
    out = []; last = -10**9
    for i in np.flatnonzero(mask):
        if i - last > gap: out.append(int(i))
        last = i
    return out
def summ(rows, keys):
    o = {"n": len(rows)}
    for k in keys:
        v = [r[k] for r in rows if r.get(k) is not None]
        if v: o[k] = {"n": len(v), "up_pct": round(100 * np.mean([x > 0 for x in v]), 0), "avg": round(float(np.mean(v)), 1), "med": round(float(np.median(v)), 1), "min": round(float(np.min(v)), 1)}
    return o
def per(d): return "1990-2009" if d < "2010-01-01" else ("2010-2017" if d < "2018-01-01" else "2018-2026")
# ---- 跟進日(長日曆)----
def ftd(C, V, corr=0.08, gain=0.015):
    pk = pd.Series(C).rolling(252, min_periods=252).max().to_numpy(); ev = []
    inc = False; low = np.nan; lowi = -1; day1 = -1; conf = -1; cur = None; hist = np.zeros(LN, int)   # hist:0 無、1 修正未確認、2 已確認
    for t in range(1, LN):
        if np.isnan(C[t]) or np.isnan(pk[t]): continue
        if not inc:
            if C[t] <= pk[t] * (1 - corr):
                inc = True; k0 = max(0, t - 251) + int(np.nanargmax(C[max(0, t - 251):t + 1])); lowi = k0 + int(np.nanargmin(C[k0:t + 1])); low = C[lowi]; day1 = -1; conf = -1; cur = None; pk0 = k0
            else: continue
        if C[t] >= pk[t] - 1e-9:
            if cur is not None and cur.get("end") is None: cur["end"] = "新高"; cur["end_t"] = t
            inc = False; conf = -1; cur = None; continue
        if C[t] < low:
            if cur is not None and cur.get("end") is None: cur["end"] = "破底"; cur["end_t"] = t
            low = C[t]; lowi = t; day1 = -1; conf = -1; cur = None
        elif day1 < 0 and t > lowi and C[t] > C[t - 1]: day1 = t
        if conf < 0 and day1 >= 0:
            nd = t - day1 + 1
            if nd >= 4 and C[t] / C[t - 1] - 1 >= gain and (np.isnan(V[t]) or np.isnan(V[t - 1]) or V[t] > V[t - 1]) and not (np.isnan(V[t]) or np.isnan(V[t - 1])):
                conf = t; cur = {"t": t, "d": D[t], "day": nd, "low_d": D[lowi], "lowi": lowi, "prem": round((C[t] / low - 1) * 100, 1), "dd_at_low": round((low / C[pk0] - 1) * 100, 1), "pk0": pk0, "end": None}
                ev.append(cur)
        hist[t] = 2 if conf >= 0 else 1
    return ev, hist
EV, HIST = ftd(NQ, NQV)
for e in EV:
    t = e["t"]; e["r20"] = fwd(NQ, t, 20); e["r60"] = fwd(NQ, t, 60); e["r120"] = fwd(NQ, t, 120); e["w60"] = worst(NQ, t, 60)
    e["fail"] = e["end"] == "破底"; e["fail60"] = bool(e["end"] == "破底" and e["end_t"] - t <= 60) if e["end"] else (False if t + 60 < LN else None)
    e["days_to_end"] = (e["end_t"] - t) if e["end"] else None
# ---- 超跌事件 ----
vh10 = pd.Series(VH).rolling(10, min_periods=1).max().to_numpy()
g = {k: pd.Series(MK[k], index=cal).reindex(LC).to_numpy() for k in ("G1", "G2", "G3", "G4", "G5", "G2c", "S")}
OE = {"VIX盤中≥40(G2)": first(vh10 >= 40), "VIX收盤≥30(G1)": first(VC >= 30), "PutCall最高5%(G3)": first(g["G3"] == 1), "G4=G2且G3": first(g["G4"] == 1), "G5=G1且G3": first(g["G5"] == 1), "現有強(S)": first(g["S"] == 1)}
OER = {}
for nm, ts in OE.items():
    rows = []
    for t in ts:
        r = {"d": D[t], "r5": fwd(SP, t, 5), "r20": fwd(SP, t, 20), "r60": fwd(SP, t, 60), "w60": worst(SP, t, 60), "q20": fwd(NQ, t, 20), "q60": fwd(NQ, t, 60), "qw60": worst(NQ, t, 60)}
        # 這次超跌之後第一個跟進日(120 天內)
        nx = next((e for e in EV if e["t"] >= t and e["t"] - t <= 120), None)
        if nx:
            r["ftd_d"] = nx["d"]; r["wait"] = nx["t"] - t; r["ftd_vs_event"] = round((NQ[nx["t"]] / NQ[t] - 1) * 100, 1); r["ftd_q60"] = nx["r60"]; r["ftd_fail"] = nx["fail"]
        rows.append(r)
    OER[nm] = rows
OUT = {"ftd": {"all": summ(EV, ["r20", "r60", "r120", "w60", "prem"])}, "ftd_events": [{k: v for k, v in e.items() if k not in ("t", "lowi", "pk0", "end_t")} for e in EV], "oversold": {}, "oversold_events": OER}
for p in ("1990-2009", "2010-2017", "2018-2026"):
    sub = [e for e in EV if per(e["d"]) == p]; s = summ(sub, ["r20", "r60", "r120", "w60", "prem"])
    done = [e for e in sub if e["end"]]; s["fail_pct"] = round(100 * np.mean([e["fail"] for e in done]), 0) if done else None; s["n_done"] = len(done)
    OUT["ftd"][p] = s
done = [e for e in EV if e["end"]]; OUT["ftd"]["all"]["fail_pct"] = round(100 * np.mean([e["fail"] for e in done]), 0); OUT["ftd"]["all"]["n_done"] = len(done)
for yrs, nm in ((("2000-03-01", "2002-12-31"), "2000-2002"), (("2007-10-01", "2009-06-30"), "2007-2009"), (("2022-01-01", "2022-12-31"), "2022")):
    sub = [e for e in EV if yrs[0] <= e["d"] <= yrs[1]]; OUT["ftd"][nm] = {"n": len(sub), "fail": sum(e["fail"] for e in sub), "dates": [(e["d"], "破底" if e["fail"] else (e["end"] or "進行中"), e["r60"] and round(e["r60"], 1)) for e in sub]}
for nm, rows in OER.items():
    OUT["oversold"][nm] = {"all": summ(rows, ["r5", "r20", "r60", "w60", "q20", "q60", "qw60", "wait", "ftd_vs_event", "ftd_q60"])}
    for p in ("1990-2009", "2010-2017", "2018-2026"):
        OUT["oversold"][nm][p] = summ([r for r in rows if per(r["d"]) == p], ["r5", "r20", "r60", "w60", "q60", "qw60", "ftd_q60"])
# 基準:任何一天
base = {}
for p, (a, b) in {"1990-2009": ("1990-01-01", "2009-12-31"), "2010-2017": ("2010-01-01", "2017-12-31"), "2018-2026": ("2018-01-01", "2026-07-31")}.items():
    ts = [t for t in range(LN) if a <= D[t] <= b]
    base[p] = summ([{"r20": fwd(SP, t, 20), "r60": fwd(SP, t, 60), "q20": fwd(NQ, t, 20), "q60": fwd(NQ, t, 60), "w60": worst(SP, t, 60)} for t in ts], ["r20", "r60", "q20", "q60", "w60"])
OUT["baseline_any_day"] = base
# 現況
t = LN - 1; pk = np.nanmax(NQ[t - 251:t + 1]); pct5 = P["pct5"]; pce5 = P["pce5"]
r = pct5.rolling(252).rank(pct=True)
OUT["now"] = {"date": D[t], "vix_close": VC[t], "vix_high_10d": float(vh10[t]), "vix_high_today": VH[t], "pc_total_5d": round(float(pct5.iloc[-1]), 3), "pc_total_5d_pctile_1y": round(float(r.iloc[-1]) * 100, 0), "pc_equity_5d": round(float(pce5.iloc[-1]), 3),
              "G": {k: (None if np.isnan(MK[k][-1]) else int(MK[k][-1])) for k in ("G1", "G2", "G3", "G4", "G5", "S")}, "S_parts": {"F6信用60日低": float(P["f6"].iloc[-1]), "F9寬度差": float(P["f9bad"].iloc[-1]), "F15負gamma(前一天)": float(P["f15"].iloc[-1]), "站上50日線比例": round(float(P["br"].iloc[-1]), 3)},
              "nasdaq_vs_1y_high_pct": round((NQ[t] / pk - 1) * 100, 1), "sp_vs_1y_high_pct": round((SP[t] / np.nanmax(SP[t - 251:t + 1]) - 1) * 100, 1), "ftd_state": {0: "不在修正", 1: "修正中、還沒確認", 2: "已確認"}[int(HIST[t])],
              "last10": [(D[i], round(NQ[i], 0), round((NQ[i] / NQ[i - 1] - 1) * 100, 2), round(VC[i], 1), round(VH[i], 1)) for i in range(t - 9, t + 1)]}
json.dump(OUT, open(os.path.join(HERE, "o2_events.json"), "w"), ensure_ascii=False, indent=1, default=lambda o: None if o is None else (float(o) if isinstance(o, (np.floating,)) else int(o) if isinstance(o, np.integer) else bool(o)))
print(json.dumps(OUT["now"], ensure_ascii=False)); print("FTD", json.dumps(OUT["ftd"], ensure_ascii=False)[:3000])
for nm in OUT["oversold"]: print(nm, json.dumps(OUT["oversold"][nm], ensure_ascii=False))
print("base", json.dumps(base, ensure_ascii=False))
for nm in ("G4=G2且G3", "G5=G1且G3"):
    for r_ in OER[nm]: print(nm, {k: (round(v, 1) if isinstance(v, float) else v) for k, v in r_.items()})
