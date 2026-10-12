# 第 5 輪補充(只描述,不進決定):照真的槓桿 ETF 校正成本後,再跑 S0 / S1 / S3 / S5
#   s8 的模擬比真的貴不夠:個股兩倍(NVDL 改 2 倍後、MUU、TSLL 改 2 倍後)每年多賺 7.3–7.6%;指數三倍(TQQQ、UPRO)每年多賺 0.9–1.2%
#   → 校正:個股兩倍每年再扣 x_s、指數兩倍每年再扣 x_i(用 ln(1+年化差距) 平均;指數三倍借 2 倍,兩倍借 1 倍 → 除以 2)
import os, sys, json, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s8_2x_sim as M
from s4_lib import HERE, load
T0_ = time.time()

def gap(und, etf, path, lev, start=None, extra=0.0):
    b = json.load(open(os.path.join(path, f"kline_{etf}.json")))["bars"]
    r = pd.Series([x[4] for x in b], index=pd.to_datetime([x[0] for x in b]))
    d = M.DATA[und] if und in M.DATA else load(und)
    cm = r.index.intersection(d.index)
    if start: cm = cm[cm >= start]
    rp = M.RPREV.reindex(cm).to_numpy(); u = d.c.reindex(cm).pct_change().fillna(0).to_numpy()
    fee = (M.MGMT + (lev - 1) * (rp + M.SPREAD) + extra) / 252; fee[0] = 0
    x = np.cumprod(1 + lev * u - fee); yrs = (cm[-1] - cm[0]).days / 365.25
    rr = r.reindex(cm)
    return (x[-1] / x[0] / (rr.iloc[-1] / rr.iloc[0])) ** (1 / yrs) - 1
REAL = [("NVDA", "NVDL", M.KL, 2, "2024-02-01"), ("MU", "MUU", M.KL, 2, None), ("TSLA", "TSLL", M.KL, 2, "2024-04-01"),
        ("QQQ", "TQQQ", "/home/claude/work/kl_extra", 3, None), ("SPY", "UPRO", "/home/claude/work/kl_extra", 3, None)]
G0 = {e: gap(u, e, p, l, s) for u, e, p, l, s in REAL}
X_S = float(np.mean([np.log1p(G0[e]) for e in ("NVDL", "MUU", "TSLL")]))
X_I = float(np.mean([np.log1p(G0[e]) for e in ("TQQQ", "UPRO")])) / 2
G1 = {e: gap(u, e, p, l, s, extra=(X_S if l == 2 else 2 * X_I)) for u, e, p, l, s in REAL}
CAL = {"校正前年化差距(模擬−真的,%)": {k: round(100 * float(v), 2) for k, v in G0.items()}, "個股兩倍每年再扣(%)": round(100 * X_S, 2),
       "指數兩倍每年再扣(%)": round(100 * X_I, 2), "校正後年化差距(%)": {k: round(100 * float(v), 2) for k, v in G1.items()}}
print(CAL)

RES = {}
for s in M.DATA:
    d = M.DATA[s]; S = M.SIG[s]; dates = d.index; pos = {x: i for i, x in enumerate(dates)}
    O, C = d.o.to_numpy(float), d.c.to_numpy(float)
    buy = S["B0"] | S["B2"]; top = S["T0"]
    rp = M.RPREV.reindex(dates).to_numpy(); xt = X_I if s in M.GS["IDX"] else X_S
    fee = (M.MGMT + rp + M.SPREAD + xt) / 252; yd = rp / 252
    for pk, (a_, b_) in M.PER5.items():
        if (s, pk) not in M.RES: continue
        fd = M.cal[M.cal >= a_][0]; i0 = pos[fd]; i1 = int(dates.searchsorted(pd.Timestamp(b_), side="right")) - 1; a = i0 - 1
        XO, XC, dead = M.build_x2(O, C, fee, a, i1)
        y = yd[a:i1 + 1]; bs = buy[a:i1 + 1]; ts = top[a:i1 + 1]; d0, d1 = dates[i0], dates[i1]; out = {}
        E, ex, nb, ns, _ = M.sim(XO, XC, y, bs, ts, "hold"); out["S0"] = M.metrics(E, ex, d0, d1, nb, ns)
        E, ex, nb, ns, _ = M.sim(XO, XC, y, bs, ts, "rule"); out["S1"] = M.metrics(E, ex, d0, d1, nb, ns)
        E, ex, nb, ns, _ = M.sim(XO, XC, y, bs, ts, "mix", f=out["S1"]["expo"]); out["S5"] = M.metrics(E, ex, d0, d1, nb, ns)
        out["S3"] = M.RES[(s, pk)]["S3"]
        RES[(s, pk)] = out
SUM = {}
for pk in M.PER5:
    for g in M.VOTE:
        syms = [s for s in sorted(M.GS[g]) if (s, pk) in RES]
        row = {"n": len(syms)}
        for k in ("S0", "S1", "S5", "S3"):
            v = [RES[(s, pk)][k] for s in syms]
            row[k] = {"倍數中位": round(float(np.median([x["fin"] for x in v])), 2), "年化中位": round(100 * float(np.median([x["cagr"] for x in v])), 1),
                      "最大跌幅中位": round(100 * float(np.median([x["mdd"] for x in v])), 1), "Calmar中位": round(float(np.median([x["calmar"] for x in v])), 3)}
        row["兩倍(S0)贏一倍(S3)的檔數"] = int(sum(RES[(s, pk)]["S0"]["fin"] > RES[(s, pk)]["S3"]["fin"] for s in syms))
        row["S1贏S0的檔數(最後報酬)"] = int(sum(RES[(s, pk)]["S1"]["fin"] > RES[(s, pk)]["S0"]["fin"] for s in syms))
        SUM[f"{g}|{pk}"] = row
PER = {f"{s}|{pk}": {k: {"倍數": round(RES[(s, pk)][k]["fin"], 3), "最大跌幅": round(100 * RES[(s, pk)][k]["mdd"], 1)} for k in ("S0", "S1", "S5", "S3")}
       for s in ["SPY", "QQQ"] + M.G["MAG7"] for pk in M.PER5 if (s, pk) in RES}
json.dump({"calibration": CAL, "summary": SUM, "per": PER}, open(os.path.join(HERE, "s8c_result.json"), "w"), ensure_ascii=False, indent=1)
for k, v in SUM.items(): print(k, v)
print(f"完成 {time.time()-T0_:.0f}s")
