# s10(2026-10-13,只描述):△回 加上行條件之後(10/12 18:52 上線),網站上的成績數字要不要跟著改?
#   網站規則 = 先過濾(收盤 ≥ 50 日線、50 日線比 10 天前高)再冷卻 5 根(index.html swSeriesJS、scripts/astra_data.py sw_series)
#   s9 算的是「舊的回(先冷卻)再過濾」= 留下的子集合 → 和網站差一點點(被舊回冷卻擋掉、但符合上行的日子,網站會標)
#   A. 追蹤股(s4/s9 同一批、SW_GRP 的來源):回 的 全期 / 前段 / 後段 勝率、平均、被套 —— 舊規則、s9 子集合、網站規則
#   B. 第 6 輪 600 檔(AX_STR 的來源):底+回 合併的「強 / 一般」勝率 —— 舊規則 vs 網站規則;另列只有回的強/一般
#   出場同 s4/r6:隔天開盤買 → 下一個頂的隔天開盤賣(40 根內沒頂就第 41 根);成本 0
import os, sys, json, pickle, math
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import s4_lib
from s4_lib import load, swing, cooldown, exits, trades, RMQ, DT, G, PERIODS, CACHE
s4_lib.COST = 0.0

def b2_rules(C):
    cs = pd.Series(C); m50 = cs.rolling(50).mean(); m200 = cs.rolling(200).mean(); mn7 = cs.rolling(7).min()
    with np.errstate(invalid="ignore"):
        e7 = ((cs > m200) & (cs <= mn7)).to_numpy()
        up = ((cs >= m50) & (m50 >= m50.shift(10))).to_numpy()
    old = cooldown(e7)
    return {"舊": old, "s9子集合": old & up, "網站": cooldown(e7 & up)}

def stat(net, mae, th):
    if not len(net): return None
    return {"n": int(len(net)), "win": round(100 * float((net > 0).mean()), 1), "avg": round(100 * float(net.mean()), 2),
            "trap": round(100 * float((mae <= -th).mean()), 1)}

OUT = {"A": {}, "B": {}}
# ---------------- A. 追蹤股(s4 同一批)----------------
meta = json.load(open(os.path.join(DT, "meta.json")))
eq = sorted(s for s, v in meta.items() if v.get("type") == "EQUITY")
spy = load("SPY"); cal = spy.index; CI = {d: i for i, d in enumerate(cal)}
DATA = {}
for s in ["SPY", "QQQ"] + eq:
    d = load(s)
    if d is None or len(d) < 260: continue
    DATA[s] = d[d.index.isin(CI)]
STK = [s for s in DATA if s not in ("SPY", "QQQ")]
GS = {"IDX": set(G["IDX"]), "MAG7": set(G["MAG7"]), "NDX": set(G["NDX"]), "ALL": set(STK)}
PK = ("全期", "前段", "後段")
ACC = {}
for s, d in DATA.items():
    O, H, L, C = (d[k].to_numpy(dtype="float64") for k in "ohlc")
    b0, t0, _ = swing(O, H, L, C)
    xe = exits(O, H, L, C, t0)["XT"]; rmin = RMQ(L, np.minimum)
    dates = d.index; th = 0.05 if s in GS["IDX"] else 0.10
    grp = [g for g, m in GS.items() if s in m]
    for rule, b2 in b2_rules(C).items():
        tt = np.flatnonzero(b2); ok, net, hold, mae = trades(O, L, tt, xe, rmin); t2 = tt[ok]
        for pk in PK:
            a, b = PERIODS[pk]; m = np.array([a <= str(dates[t].date()) <= b for t in t2], bool)
            for g in grp:
                A = ACC.setdefault((rule, g, pk), [[], []]); A[0].append(net[m]); A[1].append(mae[m])
for (rule, g, pk), (n_, m_) in ACC.items():
    net = np.concatenate(n_) if n_ else np.array([]); mae = np.concatenate(m_) if m_ else np.array([])
    OUT["A"][f"{rule}|{g}|{pk}"] = stat(net, mae, 0.05 if g == "IDX" else 0.10)

# ---------------- B. 第 6 輪 600 檔:底+回 的強 / 一般 ----------------
MAC = "/home/claude/work/macro"
uni = json.load(open(os.path.join(MAC, "universe.json")))
MAG7 = {"AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"}
NDXS = set(uni["ndx"]) - MAG7 - {"GOOG"}
STK6 = sorted((set(uni["sp500"]) | set(uni["ndx"]) | set(uni["top100_dv_last_session"]) | set(eq)) - {"SPY", "QQQ", "GOOG"})
D6 = {}
for s in ["SPY", "QQQ"] + STK6:
    d = DATA.get(s)
    if d is None:
        d = load(s)
        if d is None or len(d) < 260: continue
        d = d[d.index.isin(CI)]
    D6[s] = d
STK6 = [s for s in D6 if s not in ("SPY", "QQQ")]
AIG = {"半導體": "NVDA AMD AVGO QCOM MRVL ARM INTC TXN ADI MCHP NXPI ON MPWR TSM ASML AMAT LRCX KLAC TER ENTG AMKR GFS SWKS QRVO MTSI SNPS CDNS",
       "記憶體": "MU WDC STX SNDK PSTG NTAP", "網通光": "ANET CSCO CIEN COHR LITE AAOI GLW CRDO ALAB", "伺服器": "DELL SMCI HPE",
       "電力": "VRT ETN GEV CEG VST NRG TLN OKLO PWR", "雲端巨頭": "MSFT GOOGL AMZN META ORCL",
       "AI軟體": "PLTR NOW CRM SNOW DDOG MDB CRWD PANW ZS NET APP ADBE INTU WDAY TEAM AI SOUN PATH U IOT GTLB ESTC OKTA S TWLO HUBS",
       "新雲": "CRWV NBIS IREN CIFR APLD CORZ WULF"}
AIG = {k: v.split() for k, v in AIG.items()}
GS6 = {"IDX": {"SPY", "QQQ"}, "MAG7": MAG7 & set(D6), "NDX": NDXS & set(D6), "ALL": set(STK6),
       "AI_HW": {s for g in ("半導體", "記憶體", "網通光", "伺服器", "電力") for s in AIG[g]} & set(D6),
       "AI_SW": {s for g in ("雲端巨頭", "AI軟體", "新雲") for s in AIG[g]} & set(D6)}
R6 = pickle.load(open(os.path.join(CACHE, "r6_sig.pkl"), "rb")); MK = R6["MK"]
assert len(R6["cal"]) == len(cal)
FAV = {"F6": 1, "F9": 0, "F15": 1}   # r6_result.json D18_pass
PER6 = {"前段": ("2010-01-01", "2017-12-31"), "後段": ("2018-01-01", "2026-07-31")}
DSTR = np.array([str(x.date()) for x in cal])
def strong(q):
    sc = 0
    for k, fav in FAV.items():
        v = MK[k][q]
        if not (isinstance(v, float) and math.isnan(v)) and int(v) == fav: sc += 1
    return sc >= 2
CNT = {}
for s, d in D6.items():
    O, H, L, C = (d[k].to_numpy(dtype=float) for k in "ohlc"); n = len(C)
    p = np.array([CI[x] for x in d.index])
    b0, t0, _ = swing(O, H, L, C)
    xe = exits(O, H, L, C, t0)["XT"]
    grp = [g for g, m in GS6.items() if s in m]
    R = b2_rules(C)
    for rule in ("舊", "網站"):
        b2 = R[rule]
        for t in np.flatnonzero(b0 | b2):
            if t + 1 >= n: continue
            e = xe[t]
            if e >= n or e <= t + 1: continue
            win = int(O[e] / O[t + 1] - 1 > 0); dd = DSTR[p[t]]; st = "強" if strong(p[t]) else "一般"
            kind = "底" if b0[t] else "回"
            for pk, (a, b) in PER6.items():
                if not (a <= dd <= b): continue
                for g in grp:
                    for kk in ("底+回", kind):
                        c = CNT.setdefault((rule, kk, g, pk, st), [0, 0]); c[0] += 1; c[1] += win
for (rule, kk, g, pk, st), (n_, w_) in CNT.items():
    OUT["B"][f"{rule}|{kk}|{g}|{pk}|{st}"] = {"n": n_, "win": round(100 * w_ / n_, 1) if n_ else None}
json.dump(OUT, open(os.path.join(HERE, "s10_result.json"), "w"), ensure_ascii=False, indent=1)

# ---------------- 印出 ----------------
print("A. 追蹤股 △回(全期 2010-01~2026-07;勝率 / 平均 / 被套 / 次數)")
for g in ("IDX", "MAG7", "NDX", "ALL"):
    row = []
    for rule in ("舊", "s9子集合", "網站"):
        x = OUT["A"].get(f"{rule}|{g}|全期")
        row.append(f"{rule} {x['win']}/{x['avg']}/{x['trap']} n{x['n']}" if x else f"{rule} —")
    print(f"  {g:5s} " + " | ".join(row))
for pk in ("前段", "後段"):
    print(f"  {pk}:", " ".join(f"{g} 舊{OUT['A'][f'舊|{g}|{pk}']['win']}→網站{OUT['A'][f'網站|{g}|{pk}']['win']}" for g in ("IDX", "MAG7", "NDX", "ALL")))
print("\nB. 第 6 輪 600 檔:強 / 一般 勝率(前段 / 後段;括號 = 強的次數)")
for kk in ("底+回", "回"):
    print(f"  [{kk}]")
    for g in ("IDX", "MAG7", "AI_HW", "AI_SW", "NDX", "ALL"):
        row = []
        for rule in ("舊", "網站"):
            f = lambda pk, st: OUT["B"].get(f"{rule}|{kk}|{g}|{pk}|{st}") or {"n": 0, "win": None}
            row.append(f"{rule} 強 {f('前段','強')['win']}({f('前段','強')['n']})/{f('後段','強')['win']}({f('後段','強')['n']}) 一般 {f('前段','一般')['win']}/{f('後段','一般')['win']}")
        print(f"    {g:6s} " + " | ".join(row))
