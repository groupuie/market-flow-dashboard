# 第 5 輪:兩倍 ETF 整套操作模擬 — 分批買(最多 3 批)、每個頂減 1/4 vs 一直抱著
# 規則:p4_prereg_2x_sim.md(commit da26bc5;§5 實作補充 commit 70cf72f,都在跑之前)
import os, sys, json, pickle, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4_lib import load, DT, EXT, CACHE, HERE, G
from swing_ref_v10 import sw_py_v10
T0_ = time.time()
PER5 = {"前段": ("2010-01-01", "2017-12-31"), "後段": ("2018-01-01", "2026-10-09"), "全期": ("2010-01-01", "2026-10-09")}
MGMT, SPREAD = 0.0095, 0.003          # 管理費 0.95%;借錢利息 = DTB3 + 0.3%(借 1 倍淨值)
KL = "/home/claude/work/kl"
STRAT = ["S0", "S1", "S2", "S3", "S4", "S5"]
NAME = {"S0": "一直抱兩倍", "S1": "分批規則(兩倍)", "S2": "分批+破底④不買(兩倍)", "S3": "一直抱一倍", "S4": "分批規則(一倍)", "S5": "固定比例兩倍(=S1 平均持股)"}

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
GS = {"IDX": set(G["IDX"]), "MAG7": set(G["MAG7"]), "NDX": set(G["NDX"]), "ALL": set(STK)}
VOTE = ["IDX", "MAG7", "NDX", "ALL"]

# 利率:FRED DTB3(%),缺值往前補;第 t 天用前一個交易日的值
_r = pd.read_csv(os.path.join(EXT, "DTB3.csv"))
_r = pd.Series(_r["DTB3"].to_numpy(float), index=pd.to_datetime(_r["observation_date"]))
_ci = pd.DatetimeIndex(cal).tz_localize(None) if getattr(cal, "tz", None) is not None else pd.DatetimeIndex(cal)
RATE = _r.reindex(_r.index.union(_ci)).ffill().reindex(_ci) / 100.0
RPREV = pd.Series(RATE.shift(1).bfill().to_numpy(), index=cal)

def rep_counter(buy, L, C):
    """破底計數(swing_ref_v10 / 網站 v1.0 連鎖定義)"""
    bi = np.flatnonzero(buy); k = np.zeros(len(C), int)
    for t in bi:
        best = 0
        for s in bi[(bi >= t - 20) & (bi < t)]:
            if C[t] < L[s] and k[s] > best: best = k[s]
        k[t] = best + 1
    return k

# ---------- 自我檢查:s4_signals = 網站同式(swing_ref_v10)----------
CHK = {}
for s in ["SPY", "QQQ", "NVDA", "NBIS"]:
    d = DATA[s]; S = SIG[s]
    O, H, L, C = (d[k].to_numpy(float) for k in "ohlc")
    D = [str(x.date()) for x in d.index]
    r = sw_py_v10([[D[i], O[i], H[i], L[i], C[i]] for i in range(len(D))])
    ix = {x: i for i, x in enumerate(D)}
    same = {k: sorted(ix[x] for x in r[rk]) == list(np.flatnonzero(S[k])) for k, rk in (("B0", "bot"), ("B2", "b2"), ("T0", "top"))}
    rp = rep_counter(S["B0"] | S["B2"], L, C)
    same["rep"] = all(int(rp[ix[x]]) == v for x, v in r["rep"].items()) and len(r["rep"]) == int((S["B0"] | S["B2"]).sum())
    CHK[s] = same
print("自我檢查", CHK, f"{time.time()-T0_:.0f}s")

def build_x2(O, C, fee, a, b):
    """兩倍 ETF:第 a 根收盤 = 1(期間前一天),算到第 b 根;一天跌到 ≤0 → 歸零"""
    m = b - a + 1; XC = np.zeros(m); XO = np.zeros(m); XC[0] = 1.0; XO[0] = np.nan; dead = None
    for j in range(1, m):
        t = a + j
        xo = XC[j - 1] * (1 + 2 * (O[t] / C[t - 1] - 1))
        xc = XC[j - 1] * (1 + 2 * (C[t] / C[t - 1] - 1) - fee[t])
        if xo <= 0:
            dead = t; break                      # 開盤就歸零:XO、XC 之後都是 0
        XO[j] = xo
        if xc <= 0:
            dead = t; break                      # 收盤歸零(開盤還能成交)
        XC[j] = xc
    return XO, XC, dead

def sim(XO, XC, y, buy, sell, mode, f=None):
    """XO/XC 第 0 個 = 期間前一天收盤;第 j 天收盤的訊號 → 第 j+1 天開盤動作(j ≥ 1)
    mode: hold(第一天開盤全買)/ rule(▲底或△回 → 買總資產 1/3,最多 100%;▼頂 → 賣持股 1/4)/ mix(固定比例 f,每天收盤調整)"""
    m = len(XC); E = np.empty(m); E[0] = 1.0; ex = np.zeros(m); cash = 1.0; sh = 0.0; nb = ns = both = 0
    for j in range(1, m):
        po, pc = XO[j], XC[j]
        if mode == "hold":
            if j == 1 and po > 0: sh = cash / po; cash = 0.0; nb = 1
        elif mode == "mix":
            if j == 1 and po > 0: sh = f * cash / po; cash = cash * (1 - f); nb = 1
        elif j >= 2:
            s_, b_ = sell[j - 1], buy[j - 1]
            if s_ and b_: both += 1
            if s_ and sh > 0 and po > 0:                      # 先賣
                q = sh / 4; cash += q * po; sh -= q; ns += 1
            if b_ and po > 0:                                 # 再買
                eo = cash + sh * po; amt = min(eo / 3, cash)
                if amt > 1e-9 * eo: sh += amt / po; cash -= amt; nb += 1
        cash *= (1 + y[j])                                    # 開盤交易後的現金,收盤記息
        E[j] = cash + sh * pc
        ex[j] = sh * pc / E[j] if E[j] > 0 else 0.0
        if mode == "mix" and pc > 0 and E[j] > 0:
            sh = f * E[j] / pc; cash = E[j] - sh * pc
    return E, ex[1:], nb, ns, both

def metrics(E, ex, d0, d1, nb, ns):
    yrs = (d1 - d0).days / 365.25; fin = float(E[-1])
    cagr = fin ** (1 / yrs) - 1 if fin > 0 else -1.0
    pk = np.maximum.accumulate(E); dd = 1 - E / pk; mdd = float(dd.max())
    uw = E < pk * (1 - 1e-12); run = best = 0
    for u in uw:
        run = run + 1 if u else 0
        if run > best: best = run
    return {"fin": fin, "cagr": float(cagr), "mdd": mdd, "calmar": float(cagr / mdd) if mdd > 0 else float("inf"),
            "expo": float(ex.mean()), "nb": nb, "ns": ns, "tpy": (nb + ns) / yrs, "uw": int(best), "yrs": yrs}

RES = {}; DEAD = {}; BOTH = {}; CURVE = {}
for jx, s in enumerate(DATA):
    d = DATA[s]; S = SIG[s]; n = len(d); dates = d.index; pos = {x: i for i, x in enumerate(dates)}
    O, L, C = (d[k].to_numpy(float) for k in "olc")
    buy = S["B0"] | S["B2"]; top = S["T0"]; rep = rep_counter(buy, L, C)
    rp = RPREV.reindex(dates).to_numpy()
    fee = (MGMT + rp + SPREAD) / 252; yd = rp / 252
    for pk, (a_, b_) in PER5.items():
        fd = cal[cal >= a_][0]
        if fd not in pos or pos[fd] < 1: continue            # 期間第一天沒資料 → 不算
        i0 = pos[fd]; i1 = int(dates.searchsorted(pd.Timestamp(b_), side="right")) - 1; a = i0 - 1
        if i1 - i0 < 250: continue
        XO, XC, dead = build_x2(O, C, fee, a, i1)
        if dead is not None: DEAD.setdefault(pk, []).append((s, str(dates[dead].date())))
        X1O = O[a:i1 + 1] / C[a]; X1C = C[a:i1 + 1] / C[a]
        y = yd[a:i1 + 1]; bs = buy[a:i1 + 1]; ts = top[a:i1 + 1]; bs2 = bs & (rep[a:i1 + 1] < 4)
        d0, d1 = dates[i0], dates[i1]; out = {}
        E, ex, nb, ns, _ = sim(XO, XC, y, bs, ts, "hold"); out["S0"] = metrics(E, ex, d0, d1, nb, ns); E0 = E
        E, ex, nb, ns, bo = sim(XO, XC, y, bs, ts, "rule"); out["S1"] = metrics(E, ex, d0, d1, nb, ns); E1 = E
        BOTH[(s, pk)] = bo
        E, ex, nb, ns, _ = sim(XO, XC, y, bs2, ts, "rule"); out["S2"] = metrics(E, ex, d0, d1, nb, ns); E2 = E
        E, ex, nb, ns, _ = sim(X1O, X1C, y, bs, ts, "hold"); out["S3"] = metrics(E, ex, d0, d1, nb, ns); E3 = E
        E, ex, nb, ns, _ = sim(X1O, X1C, y, bs, ts, "rule"); out["S4"] = metrics(E, ex, d0, d1, nb, ns)
        E, ex, nb, ns, _ = sim(XO, XC, y, bs, ts, "mix", f=out["S1"]["expo"]); out["S5"] = metrics(E, ex, d0, d1, nb, ns); E5 = E
        RES[(s, pk)] = out
        if s in ("SPY", "QQQ", "NVDA", "AAPL", "MSFT", "TSLA") :
            CURVE[f"{s}|{pk}"] = {"d": [str(x.date()) for x in dates[a:i1 + 1]], "S0": E0.round(5).tolist(), "S1": E1.round(5).tolist(),
                                  "S2": E2.round(5).tolist(), "S3": E3.round(5).tolist(), "S5": E5.round(5).tolist()}
    if jx % 60 == 0: print("  ", jx, s, f"{time.time()-T0_:.0f}s")

# ---------- 檢查:模擬 vs 真的兩倍 ETF ----------
VAL = {}
for und, etf in (("NVDA", "NVDL"), ("MU", "MUU")):
    b = json.load(open(os.path.join(KL, f"kline_{etf}.json")))["bars"]
    r = pd.DataFrame({"o": [x[1] for x in b], "c": [x[4] for x in b]}, index=pd.to_datetime([x[0] for x in b]))
    d = DATA[und]; di = pd.DatetimeIndex(d.index).tz_localize(None) if getattr(d.index, "tz", None) is not None else pd.DatetimeIndex(d.index)
    cm = r.index.intersection(di); a = int(np.flatnonzero(di == cm[0])[0]); b_ = int(np.flatnonzero(di == cm[-1])[0])
    rp = RPREV.reindex(d.index).to_numpy(); fee = (MGMT + rp + SPREAD) / 252
    XO, XC, dead = build_x2(d.o.to_numpy(float), d.c.to_numpy(float), fee, a, b_)
    syn = pd.DataFrame({"o": XO, "c": XC}, index=di[a:b_ + 1]).reindex(cm); rr = r.reindex(cm)
    rc_s = syn.c / syn.c.shift(1) - 1; rc_r = rr.c / rr.c.shift(1) - 1
    ro_s = syn.o / syn.c.shift(1) - 1; ro_r = rr.o / rr.c.shift(1) - 1
    yrs = (cm[-1] - cm[0]).days / 365.25; ms, mr = float(syn.c.iloc[-1] / syn.c.iloc[0]), float(rr.c.iloc[-1] / rr.c.iloc[0])
    diff = (rc_s - rc_r).dropna()
    VAL[f"{und}→{etf}"] = {"from": str(cm[0].date()), "to": str(cm[-1].date()), "days": int(len(cm)),
                          "收盤每天報酬相關": round(float(rc_s.corr(rc_r)), 4), "開盤跳空相關": round(float(ro_s.corr(ro_r)), 4),
                          "每天差距中位(百分點)": round(100 * float(diff.abs().median()), 3), "每天差距>2%的天數": int((diff.abs() > 0.02).sum()),
                          "模擬累積倍數": round(ms, 3), "真的累積倍數": round(mr, 3), "年化差距(模擬−真的)": round(100 * ((ms / mr) ** (1 / yrs) - 1), 2)}
print("檢查", VAL)

# ---------- 分組 ----------
def med(v): return float(np.median(v)) if len(v) else None
SUM = {}; log = []
for pk in PER5:
    for g in VOTE:
        syms = [s for s in sorted(GS[g]) if (s, pk) in RES]
        if not syms: continue
        R = {k: [RES[(s, pk)][k] for s in syms] for k in STRAT}
        row = {"n": len(syms)}
        for k in STRAT:
            row[k] = {"總倍數中位": med([x["fin"] for x in R[k]]), "年化中位": med([x["cagr"] for x in R[k]]), "最大跌幅中位": med([x["mdd"] for x in R[k]]),
                      "Calmar中位": med([x["calmar"] for x in R[k]]), "平均持股": float(np.mean([x["expo"] for x in R[k]])),
                      "每年交易次數": float(np.mean([x["tpy"] for x in R[k]])), "最長水下中位(交易日)": med([x["uw"] for x in R[k]]),
                      "最差總倍數": float(min(x["fin"] for x in R[k])), "最大跌幅最大": float(max(x["mdd"] for x in R[k]))}
        c10 = [R["S1"][i]["calmar"] > R["S0"][i]["calmar"] for i in range(len(syms))]
        row["S1vsS0"] = {"Calmar較好檔數": int(sum(c10)), "跌幅少的中位(百分點,配對)": 100 * med([R["S0"][i]["mdd"] - R["S1"][i]["mdd"] for i in range(len(syms))]),
                         "最後報酬較高檔數": int(sum(R["S1"][i]["fin"] > R["S0"][i]["fin"] for i in range(len(syms)))),
                         "總倍數比中位(S1÷S0)": med([R["S1"][i]["fin"] / R["S0"][i]["fin"] if R["S0"][i]["fin"] > 0 else float("inf") for i in range(len(syms))])}
        row["S2vsS1"] = {"Calmar較好檔數": int(sum(R["S2"][i]["calmar"] > R["S1"][i]["calmar"] for i in range(len(syms)))),
                         "跌幅較少檔數": int(sum(R["S2"][i]["mdd"] < R["S1"][i]["mdd"] for i in range(len(syms)))),
                         "最後報酬較高檔數": int(sum(R["S2"][i]["fin"] > R["S1"][i]["fin"] for i in range(len(syms))))}
        row["S1vsS5"] = {"Calmar較好檔數": int(sum(R["S1"][i]["calmar"] > R["S5"][i]["calmar"] for i in range(len(syms)))),
                         "跌幅較少檔數": int(sum(R["S1"][i]["mdd"] < R["S5"][i]["mdd"] for i in range(len(syms)))),
                         "最後報酬較高檔數": int(sum(R["S1"][i]["fin"] > R["S5"][i]["fin"] for i in range(len(syms))))}
        SUM[f"{g}|{pk}"] = row

# ---------- 決定 ----------
DEC = {}
for key, test in (("D16", lambda r: (r["S0"]["最大跌幅中位"] - r["S1"]["最大跌幅中位"] >= 0.10) and (r["S1vsS0"]["Calmar較好檔數"] >= r["n"] / 2)),
                  ("D17", lambda r: (r["S2"]["Calmar中位"] >= r["S1"]["Calmar中位"]) and (r["S2"]["最大跌幅中位"] < r["S1"]["最大跌幅中位"]))):
    cnt = {}
    for pk in ("前段", "後段"):
        c = 0
        for g in VOTE:
            r = SUM.get(f"{g}|{pk}")
            ok = bool(r and test(r)); c += ok
            if key == "D16":
                log.append(f"  D16 {g} {pk}(n={r['n']}):最大跌幅中位 S0 {100*r['S0']['最大跌幅中位']:.1f}% → S1 {100*r['S1']['最大跌幅中位']:.1f}%;Calmar 較好 {r['S1vsS0']['Calmar較好檔數']}/{r['n']} → {ok}")
            else:
                log.append(f"  D17 {g} {pk}(n={r['n']}):Calmar 中位 S1 {r['S1']['Calmar中位']:.3f} → S2 {r['S2']['Calmar中位']:.3f};最大跌幅中位 S1 {100*r['S1']['最大跌幅中位']:.1f}% → S2 {100*r['S2']['最大跌幅中位']:.1f}% → {ok}")
        cnt[pk] = c
    DEC[key] = all(v >= 3 for v in cnt.values())
    log.append(f"{key}:{'通過' if DEC[key] else '不通過'} {cnt}")
log.append(f"歸零:{ {k: len(v) for k, v in DEAD.items()} };同日先賣再買次數(全期合計):{sum(v for (s, pk), v in BOTH.items() if pk == '全期')}")

def rnd(x):
    if isinstance(x, float): return round(x, 4) if np.isfinite(x) else str(x)
    if isinstance(x, dict): return {k: rnd(v) for k, v in x.items()}
    if isinstance(x, list): return [rnd(v) for v in x]
    return x
OUT = {"self_check": CHK, "validation": VAL, "decision": DEC, "log": log, "summary": rnd(SUM), "dead": DEAD,
       "per": {f"{s}|{pk}": rnd(v) for (s, pk), v in RES.items()}, "names": NAME}
json.dump(OUT, open(os.path.join(HERE, "s8_result.json"), "w"), ensure_ascii=False, indent=1)
json.dump(CURVE, open(os.path.join(CACHE, "s8_curves.json"), "w"))
print("\n".join(log)); print(f"完成 {time.time()-T0_:.0f}s")
