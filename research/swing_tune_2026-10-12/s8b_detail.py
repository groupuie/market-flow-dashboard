# 第 5 輪的補充描述(不進決定):為什麼分批規則擋不住大跌、同一天「回」和「頂」的處理、NVDL 改 2 倍之後的檢查
import os, sys, json, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s8_2x_sim as M
from s4_lib import HERE
T0_ = time.time(); OUT = {}

# ---------- 1. NVDL:2024-01 以前是 1.5 倍(每月迴歸斜率 1.29–1.58),2024-02 起 2 倍 → 從 2024-02-01 再比一次 ----------
b = json.load(open(os.path.join(M.KL, "kline_NVDL.json")))["bars"]
r = pd.DataFrame({"o": [x[1] for x in b], "c": [x[4] for x in b]}, index=pd.to_datetime([x[0] for x in b]))
d = M.DATA["NVDA"]; di = pd.DatetimeIndex(d.index)
cm = r.index.intersection(di); cm = cm[cm >= "2024-02-01"]
a = int(np.flatnonzero(di == cm[0])[0]); b_ = int(np.flatnonzero(di == cm[-1])[0])
rp = M.RPREV.reindex(d.index).to_numpy(); fee = (M.MGMT + rp + M.SPREAD) / 252
XO, XC, _ = M.build_x2(d.o.to_numpy(float), d.c.to_numpy(float), fee, a, b_)
syn = pd.Series(XC, index=di[a:b_ + 1]).reindex(cm); rr = r.c.reindex(cm)
rs, rr_ = syn.pct_change(), rr.pct_change(); yrs = (cm[-1] - cm[0]).days / 365.25
ms, mr = float(syn.iloc[-1] / syn.iloc[0]), float(rr.iloc[-1] / rr.iloc[0])
OUT["NVDL_2x期間"] = {"from": str(cm[0].date()), "to": str(cm[-1].date()), "收盤每天報酬相關": round(float(rs.corr(rr_)), 4),
                     "模擬累積倍數": round(ms, 3), "真的累積倍數": round(mr, 3), "年化差距(模擬−真的)": round(100 * ((ms / mr) ** (1 / yrs) - 1), 2)}

# ---------- 共用:跑一檔一段,回傳 E、持股比例 ----------
def run(s, pk, conflict="sell_first", sig_override=None):
    d = M.DATA[s]; S = M.SIG[s]; dates = d.index; pos = {x: i for i, x in enumerate(dates)}
    O, L, C = (d[k].to_numpy(float) for k in "olc")
    buy = S["B0"] | S["B2"]; top = S["T0"]
    rp = M.RPREV.reindex(dates).to_numpy(); fee = (M.MGMT + rp + M.SPREAD) / 252; yd = rp / 252
    a_, b2 = M.PER5[pk]; fd = M.cal[M.cal >= a_][0]
    if fd not in pos or pos[fd] < 1: return None
    i0 = pos[fd]; i1 = int(dates.searchsorted(pd.Timestamp(b2), side="right")) - 1; a = i0 - 1
    XO, XC, dead = M.build_x2(O, C, fee, a, i1)
    y = yd[a:i1 + 1]; bs = buy[a:i1 + 1].copy(); ts = top[a:i1 + 1].copy()
    m = len(XC); E = np.empty(m); E[0] = 1.0; ex = np.zeros(m); cash = 1.0; sh = 0.0
    for j in range(1, m):
        po, pc = XO[j], XC[j]
        if j >= 2:
            s_, b_ = bool(ts[j - 1]), bool(bs[j - 1])
            if s_ and b_:
                if conflict == "none": s_ = b_ = False
                elif conflict == "top": b_ = False
                elif conflict == "buy": s_ = False
            order = ("b", "s") if conflict == "buy_first" else ("s", "b")
            for o in order:
                if o == "s" and s_ and sh > 0 and po > 0:
                    q = sh / 4; cash += q * po; sh -= q
                if o == "b" and b_ and po > 0:
                    eo = cash + sh * po; amt = min(eo / 3, cash)
                    if amt > 1e-9 * eo: sh += amt / po; cash -= amt
        cash *= (1 + y[j]); E[j] = cash + sh * pc; ex[j] = sh * pc / E[j] if E[j] > 0 else 0.0
    return {"E": E, "ex": ex, "d": dates[a:i1 + 1], "XC": XC}

# 自我檢查:run(預設 = 先賣再買)= s8 的 S1
for _s in ("QQQ", "NVDA", "SPY"):
    for _pk in ("前段", "後段", "全期"):
        assert abs(run(_s, _pk)["E"][-1] - M.RES[(_s, _pk)]["S1"]["fin"]) < 1e-9 * max(1, M.RES[(_s, _pk)]["S1"]["fin"]), (_s, _pk)
print("run() = s8 S1 OK")

# ---------- 2. 大跌的時候 S1 已經買到幾成 ----------
def episodes(s, pk="全期", min_dd=0.30):
    r1 = run(s, pk)
    if r1 is None: return []
    XC = r1["XC"]; E1, ex1, D = r1["E"], r1["ex"], r1["d"]
    pkv = np.maximum.accumulate(XC); dd = 1 - XC / pkv; out = []; j = 1
    while j < len(XC):
        if dd[j] >= min_dd:
            st = j
            while st > 0 and dd[st] > 0: st -= 1          # 前高那天
            en = j
            while en + 1 < len(XC) and dd[en + 1] > 0: en += 1   # 回到前高前一天
            tr = st + int(np.argmax(dd[st:en + 1]))
            pk1 = E1[:st + 1].max() if st > 0 else 1.0
            e1dd = 1 - E1[st:tr + 1].min() / max(E1[:st + 1].max(), 1e-12)
            out.append({"前高": str(D[st].date()), "谷底": str(D[tr].date()), "一直抱跌幅": round(100 * float(dd[tr]), 1),
                        "分批規則同期跌幅": round(100 * float(e1dd), 1), "前高那天持股": round(100 * float(ex1[st]), 0),
                        "谷底那天持股": round(100 * float(ex1[tr]), 0), "途中最低持股": round(100 * float(ex1[st:tr + 1].min()), 0)})
            j = en + 1
        else:
            j += 1
    return out
OUT["大跌"] = {s: episodes(s) for s in ["QQQ", "SPY", "NVDA", "AAPL", "MSFT", "TSLA", "META", "AMZN", "GOOGL"]}
# 全部檔:後段最大跌幅那段的谷底,S1 持股幾成
tr_ex = {g: [] for g in M.VOTE}
for s in M.DATA:
    r1 = run(s, "後段")
    if r1 is None: continue
    XC = r1["XC"]; dd = 1 - XC / np.maximum.accumulate(XC); tr = int(np.argmax(dd))
    for g in M.VOTE:
        if s in M.GS[g]: tr_ex[g].append(float(r1["ex"][tr]))
OUT["後段最大跌幅谷底的持股"] = {g: {"n": len(v), "中位": round(100 * float(np.median(v)), 1), "≥90%的比例": round(100 * float(np.mean(np.array(v) >= 0.9)), 1)} for g, v in tr_ex.items()}
print("2 done", f"{time.time()-T0_:.0f}s")

# ---------- 3. 七巨頭、指數逐檔 ----------
tab = {}
for pk in ("後段", "全期"):
    for s in ["SPY", "QQQ"] + M.G["MAG7"]:
        x = M.RES.get((s, pk))
        if not x: continue
        tab[f"{s}|{pk}"] = {k: {"倍數": round(x[k]["fin"], 2), "年化": round(100 * x[k]["cagr"], 1), "最大跌幅": round(100 * x[k]["mdd"], 1),
                                "平均持股": round(100 * x[k]["expo"], 0), "最長水下": x[k]["uw"]} for k in ("S0", "S1", "S2", "S5", "S3")}
OUT["逐檔"] = tab

# ---------- 4. 同一天又回又頂:別的處理方式(只描述)----------
SENS = {}
for c in ("sell_first", "buy_first", "none", "top", "buy"):
    for pk in ("前段", "後段"):
        for g in M.VOTE:
            v = []
            for s in sorted(M.GS[g]):
                if (s, pk) not in M.RES: continue
                r1 = run(s, pk, conflict=c); E = r1["E"]; d0, d1 = r1["d"][1], r1["d"][-1]
                mt = M.metrics(E, r1["ex"][1:], d0, d1, 0, 0); v.append(mt)
            SENS[f"{c}|{g}|{pk}"] = {"倍數中位": round(float(np.median([x["fin"] for x in v])), 3), "最大跌幅中位": round(100 * float(np.median([x["mdd"] for x in v])), 1),
                                     "Calmar中位": round(float(np.median([x["calmar"] for x in v])), 3), "平均持股": round(100 * float(np.mean([x["expo"] for x in v])), 1)}
OUT["同日回頂處理"] = SENS
print("4 done", f"{time.time()-T0_:.0f}s")

# 同一天又回又頂的那根,之後 10 天(隔天開盤 → 第 11 天開盤)
FW = {}
for s in M.DATA:
    d = M.DATA[s]; S = M.SIG[s]; O = d.o.to_numpy(float); n = len(O)
    ok = (d.index >= "2010-01-01") & (d.index <= "2026-07-31")
    for name, msk in (("只有回", S["B2"] & ~S["T0"]), ("只有頂", S["T0"] & ~S["B2"]), ("回+頂同一天", S["B2"] & S["T0"])):
        t = np.flatnonzero(msk & ok); t = t[t + 11 < n]
        r10 = O[t + 11] / O[t + 1] - 1
        for g in M.VOTE:
            if s in M.GS[g]: FW.setdefault(f"{g}|{name}", []).extend(r10.tolist())
OUT["之後10天"] = {k: {"n": len(v), "漲的比例": round(100 * float(np.mean(np.array(v) > 0)), 1), "中位": round(100 * float(np.median(v)), 2), "平均": round(100 * float(np.mean(v)), 2)} for k, v in FW.items()}
json.dump(OUT, open(os.path.join(HERE, "s8b_result.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: OUT[k] for k in ("NVDL_2x期間", "後段最大跌幅谷底的持股", "之後10天")}, ensure_ascii=False, indent=1))
print(f"完成 {time.time()-T0_:.0f}s")
