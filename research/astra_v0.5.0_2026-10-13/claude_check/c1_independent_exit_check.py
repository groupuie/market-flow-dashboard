# Claude 端獨立核對(2026-10-14,只描述):Astra v0.5.0 的 B0 / R1 / E1 / C50
#   不 import Astra 的 experiment.py / data_tools.py;照 MD 附錄一(事前規格)自己寫一份。
#   資料 = Claude 自己的 Yahoo 還原日K 快取(research/swing_tune_2026-10-12/s4_lib.load,抓到 2026-10-09,比 Astra 少一天)
#   訊號 = s4_lib.swing(底、頂)+ 現行回(Double 7s + 收盤 ≥ 50 日線、50 日線 ≥ 10 天前,先過濾再冷卻 5 根)
#   名單 = research/inst_flow_2026-10-11/universe_266.txt + SPY、QQQ;MAG7 / NDX = groups.json ∩ 名單
#   和 Astra 不同的地方(會讓數字差一點):少一天資料、s4_lib 遇到壞的開高低價會用收盤補(Astra 是拒收、切段)
import os, sys, json, math
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "swing_tune_2026-10-12"))
import s4_lib
from s4_lib import load, swing, cooldown

UNI = [s.strip() for s in open(os.path.join(REPO, "research/inst_flow_2026-10-11/universe_266.txt")) if s.strip() and not s.startswith("#")]
G = json.load(open(os.path.join(REPO, "research/swing_tune_2026-10-12/groups.json")))
GS = {"IDX": {"SPY", "QQQ"}, "MAG7": set(G["MAG7"]) & set(UNI), "NDX": set(G["NDX"]) & set(UNI), "ALL": set(UNI)}
PER = {"A": ("2010-01-01", "2017-12-31"), "B": ("2018-01-01", "2026-07-31")}
# 資料來源:預設 Claude 快取;SRC=astra 改讀 Astra 下載工具抓的 adjusted/*.json(用來分辨差異是資料還是程式)
SRC = os.environ.get("SRC", "claude"); ADIR = os.environ.get("ADIR", "/home/claude/work/astra_v050_data/adjusted")
if SRC == "astra":
    def load(s):
        f = os.path.join(ADIR, s + ".json")
        if not os.path.exists(f): return None
        b = json.load(open(f))["bars"]
        return pd.DataFrame({"o": [x[1] for x in b], "h": [x[2] for x in b], "l": [x[3] for x in b], "c": [x[4] for x in b]},
                            index=pd.to_datetime([x[0] for x in b]))
spy = load("SPY"); cal = [str(x.date()) for x in spy.index]; CI = {d: i for i, d in enumerate(cal)}

def atr_wilder(H, L, C):
    n = len(C); a = [None] * n; tr = []
    for i in range(n):
        pc = C[i - 1] if i else C[i]
        tr.append(max(H[i] - L[i], abs(H[i] - pc), abs(L[i] - pc)))
        if i == 13: a[i] = sum(tr) / 14
        elif i > 13: a[i] = (a[i - 1] * 13 + tr[i]) / 14
    return a

def window(O, C, t, top, atr, pol):
    """回傳 (報酬, 窗口最大回撤, R1 有沒有觸發)。e = t+1 開盤買;觀察到 t+64 開盤;賣出都在觸發的下一開盤。"""
    e, end = t + 1, t + 64
    ft = next((j for j in range(t + 1, t + 41) if top[j]), None)
    x = ft + 1 if ft is not None else t + 41
    sells = {}                                    # 第幾根開盤 → 賣掉原始股數的比例
    trig = False
    if pol in ("B0", "C50"): sells[x] = 1.0
    elif pol == "R1":
        hc = -math.inf; armed = False
        for j in range(e, x):
            hc = max(hc, C[j]); armed = armed or hc >= O[e] + 2 * atr
            if armed and C[j] <= hc - atr and j + 1 < x:
                sells[j + 1] = 0.5; trig = True; break
        sells[x] = sells.get(x, 0) + (0.5 if trig else 1.0)
    elif pol == "E1":
        if ft is None: sells[x] = 1.0
        else:
            sells[x] = 0.5; out = end
            for j in range(x, end):
                if C[j] < min(C[j - 10:j]): out = j + 1; break
            sells[out] = sells.get(out, 0) + 0.5
    alloc = 0.5 if pol == "C50" else 1.0
    q0 = alloc / O[e]; q = q0; cash = 1 - alloc; nav = [1.0]
    for j in range(e, end + 1):
        if j in sells: cash += q0 * sells[j] * O[j]; q -= q0 * sells[j]
        nav.append(cash + q * (O[j] if j == end else C[j]))
    peak = nav[0]; dd = 0.0
    for v in nav: peak = max(peak, v); dd = max(dd, 1 - v / peak)
    assert abs(q) < 1e-12
    return nav[-1] - 1, dd, trig

ROWS = []
for s in ["SPY", "QQQ"] + UNI:
    d = load(s)
    if d is None: continue
    d = d[d.index.isin(spy.index)]
    pos = np.array([CI[str(x.date())] for x in d.index])
    cuts = np.flatnonzero(np.diff(pos) != 1) + 1                       # 和共同日曆不連續 → 切段(不壓縮交易日)
    for seg in np.split(np.arange(len(d)), cuts):
        if len(seg) < 201: continue
        sd = d.iloc[seg]; O, H, L, C = (sd[k].to_numpy(dtype=float) for k in "ohlc"); n = len(C)
        b0, t0, _ = swing(O, H, L, C)
        cs = pd.Series(C); m50 = cs.rolling(50).mean()
        with np.errstate(invalid="ignore"):
            e7 = ((cs > cs.rolling(200).mean()) & (cs <= cs.rolling(7).min()) & (cs >= m50) & (m50 >= m50.shift(10))).to_numpy()
        b2 = cooldown(e7); atr = atr_wilder(H, L, C)
        for t in np.flatnonzero(b0 | b2):
            day = str(sd.index[t].date()); per = next((p for p, (a, b) in PER.items() if a <= day <= b), None)
            if per is None or t < 199 or t + 64 >= n or not atr[t] or atr[t] <= 0: continue
            r = {pol: window(O, C, t, t0, atr[t], pol) for pol in ("B0", "R1", "E1", "C50")}
            ROWS.append((s, day, per, r))

def summ(rows, pol):
    ret = np.array([r[3][pol][0] for r in rows]); dd = np.array([r[3][pol][1] for r in rows])
    return {"n": len(ret), "win": round(100 * float((ret > 0).mean()), 2), "mean": round(100 * float(ret.mean()), 2),
            "median": round(100 * float(np.median(ret)), 2), "mdd": round(100 * float(dd.mean()), 2)}
OUT = {"data_last": cal[-1], "n_windows": len(ROWS), "groups": {g: len(v) for g, v in GS.items()}, "sum": {}, "paired": {}}
for g, mem in GS.items():
    for per in PER:
        rows = [r for r in ROWS if r[0] in mem and r[2] == per]
        if not rows: continue
        OUT["sum"][f"{g}|{per}"] = {pol: summ(rows, pol) for pol in ("B0", "R1", "E1", "C50")}
        for pol in ("R1", "E1", "C50"):
            dd = np.array([r[3]["B0"][1] - r[3][pol][1] for r in rows]); dr = np.array([r[3][pol][0] - r[3]["B0"][0] for r in rows])
            p = {"dDD": round(100 * float(dd.mean()), 3), "dR": round(100 * float(dr.mean()), 3)}
            if pol == "R1":
                tg = np.array([r[3]["R1"][2] for r in rows]); p["trig"] = round(100 * float(tg.mean()), 2)
                p["dDD_if_trig"] = round(100 * float(dd[tg].mean()), 2); p["dR_if_trig"] = round(100 * float(dr[tg].mean()), 2)
            OUT["paired"][f"{g}|{per}|{pol}"] = p
json.dump(OUT, open(os.path.join(HERE, "c1_result.json" if SRC == "claude" else "c1_result_astra_data.json"), "w"), ensure_ascii=False, indent=1)
print("資料到", OUT["data_last"], "窗口", OUT["n_windows"], OUT["groups"])
for per in PER:
    print(f"[ALL {per}]", " | ".join(f"{pol} n{v['n']} 勝{v['win']} 均{v['mean']} 中{v['median']} 回撤{v['mdd']}" for pol, v in OUT["sum"][f"ALL|{per}"].items()))
for k, v in OUT["paired"].items():
    if k.endswith("|R1"): print("  ", k, v)
for per in PER:
    print(f"  ALL {per} E1", OUT["paired"][f"ALL|{per}|E1"], "C50", OUT["paired"][f"ALL|{per}|C50"])
