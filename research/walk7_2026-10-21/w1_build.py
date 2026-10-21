#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 W1:名單(每年)+ 每個「某檔某天」的答案與特徵
名單(每年 1 月 1 日定一次,用前一年的資料,沒有偷看):
  - 市值前 500(近似)= 當年 1 月 1 日的 S&P 500 成分股(Wikipedia 當時版本;舊代號用 CIK 對到後來的代號)
  - 成交金額前 100 = 1 月 1 日之前 252 個交易日的「只還原分割的收盤 × 成交量」加總,個股(不含 ETF;同公司多種股只留一種)
決定日:2016-10-21 起,到最後一個還有 20 個交易日答案的日子;每一檔要有 ≥ 252 根歷史、[i−125, i+20] 沒有零成交量、收盤不變的天數 ≤ 2%
答案(之後 20 個交易日;尺 = atr = 前 20 天平均真實區間 ÷ 收盤,同 x10):
  buy  = 1 先碰 +2·atr(先漲一段)/ 0 先碰 −1.5·atr(先跌;同一天兩邊都碰 = 先跌)/ 2 都沒碰
  sell = 1 先碰 −2·atr(先跌一段)/ 0 先碰 +1.5·atr(被軋;同一天兩邊都碰 = 被軋)/ 2 都沒碰
  d20  = 1 先碰 +2·atr / 0 先碰 −2·atr / 缺值 = 都沒碰或同一天兩邊都碰(上下對稱,只看方向)
  r20、r60 = 之後 20 / 60 個交易日的報酬(還原權值);r60 沒有資料就是缺值
特徵:walk5 的 feats()(約 70 個)+ QQQ 大盤特徵 + 相對強弱
用法:python3 -I w1_build.py OUT_DIR   → OUT_DIR/out/S7.pkl、out/universe.json"""
import gzip, json, math, os, pickle, sys
import numpy as np, pandas as pd

OUT = sys.argv[1]; HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "..", "walk5q", "q0_features.py")).read()
src = src.split("def barrier(")[0].replace("BARS, OUT = sys.argv[1], sys.argv[2]\nB = json.load(gzip.open(BARS))[\"bars\"]", "")
ns = {}; exec(src, ns); feats, shift, sma = ns["feats"], ns["shift"], ns["sma"]

D = pickle.load(gzip.open(os.path.join(OUT, "data", "daily.pkl.gz"))); BARS, ymap = D["bars"], D["ymap"]
SP = json.load(open(os.path.join(OUT, "data", "sp500_jan1.json")))
DROP = {"GOOG", "BRK-A", "FOX", "NWS", "UA", "DISCK", "LEN-B", "BF-A", "HEI-A", "ZG", "LBRDA", "FWONA", "BATRA", "LSXMA", "LSXMB", "QRTEB"}
START, H, H2 = "2016-10-21", 20, 60
CAL = BARS["SPY"]["d"]; LASTDEC = CAL[-1 - H]
ETF = {s for s, b in BARS.items() if b["type"] != "EQUITY"}

# 1) 每年名單
uni = {}
for Y in range(2016, 2027):
    anchor = max(d for d in CAL if d < f"{Y}-01-01"); k = CAL.index(anchor); win0 = CAL[k - 251]
    dv = []
    for s, b in BARS.items():
        if s in ETF or s in DROP:
            continue
        d = b["d"]; lo, hi = np.searchsorted(d, win0), np.searchsorted(d, anchor, side="right")
        if hi - lo < 200:
            continue
        x = b["x"][lo:hi]; dv.append((float((x[:, 4] * x[:, 5]).sum()), s))
    dv.sort(reverse=True); top = {s: r + 1 for r, (v, s) in enumerate(dv[:100])}
    sp = {}
    for m in SP[str(Y)]:
        s = ymap.get(m["sym"], m["sym"])
        if s in BARS and s not in DROP:
            sp[s] = m["sym"]
    uni[Y] = {"sp": sorted(sp), "dv": top, "dv_n": len(dv), "sp_missing": sorted(m["sym"] for m in SP[str(Y)] if ymap.get(m["sym"], m["sym"]) not in BARS)}
    print(Y, "anchor", anchor, "S&P 有資料", len(sp), "/", len(SP[str(Y)]), "成交金額前 100(候選", len(dv), ")", "兩者都在", len(set(sp) & set(top)), "合計", len(set(sp) | set(top)), flush=True)
json.dump({str(Y): v for Y, v in uni.items()}, open(os.path.join(OUT, "out", "universe.json"), "w"), ensure_ascii=False, indent=0)

# 2) 大盤
q = BARS["QQQ"]; qd = q["d"]; qx = q["x"]
QF, _ = feats(qx[:, 0], qx[:, 1], qx[:, 2], qx[:, 3], qx[:, 5]); QI = {d: k for k, d in enumerate(qd)}
QK = ["r1", "r5", "r20", "r60", "r120", "dma50", "dma200", "a", "atr5_20", "pos60", "streak", "rsi14"]


def outcomes(h, l, c, i, a):
    C = c[i]; U2, D15, U15, D2 = C * (1 + 2 * a), C * (1 - 1.5 * a), C * (1 + 1.5 * a), C * (1 - 2 * a)
    buy = sell = d20 = None; bd = sd = dd = H
    for j in range(1, H + 1):
        hi, lo = h[i + j], l[i + j]
        if buy is None:
            if lo <= D15:
                buy, bd = 0, j
            elif hi >= U2:
                buy, bd = 1, j
        if sell is None:
            if hi >= U15:
                sell, sd = 0, j
            elif lo <= D2:
                sell, sd = 1, j
        if d20 is None:
            u, dn = hi >= U2, lo <= D2
            if u and dn:
                d20, dd = -1, j
            elif u:
                d20, dd = 1, j
            elif dn:
                d20, dd = 0, j
        if buy is not None and sell is not None and d20 is not None:
            break
    return (2 if buy is None else buy), bd, (2 if sell is None else sell), sd, (np.nan if d20 in (None, -1) else d20), dd


# 3) 每一檔:特徵算一次,挑名單年份裡的日子
SPSET = {Y: set(u["sp"]) for Y, u in uni.items()}
yrs_of = {}
for Y, u in uni.items():
    for s in set(u["sp"]) | set(u["dv"]):
        yrs_of.setdefault(s, set()).add(Y)
frames = []
for n_, s in enumerate(sorted(yrs_of)):
    b = BARS[s]; d = np.array(b["d"]); x = b["x"]; o, h, l, c, v = x[:, 0], x[:, 1], x[:, 2], x[:, 3], x[:, 5]; n = len(c)
    if n < 300:
        continue
    F, a = feats(o, h, l, c, v)
    yr = np.array([int(t[:4]) for t in d]); keep = np.zeros(n, bool)
    for Y in yrs_of[s]:
        keep |= yr == Y
    keep &= (d >= START) & (d <= LASTDEC); keep[:252] = False
    idx = [i for i in np.nonzero(keep)[0] if i + H < n and d[i] in QI]
    good = []
    for i in idx:
        vv, cc = v[i - 125:i + H + 1], c[i - 125:i + H + 1]
        if (vv > 0).all() and int((cc[1:] == cc[:-1]).sum()) <= 0.02 * len(cc) and a[i] == a[i] and a[i] > 0:
            good.append(i)
    if not good:
        continue
    good = np.array(good)
    df = pd.DataFrame({k: F[k][good] for k in F}); df.insert(0, "i", good); df.insert(0, "date", d[good]); df.insert(0, "sym", s)
    Y_ = np.array([int(t[:4]) for t in d[good]]); df.insert(3, "year", Y_)
    df["in_sp"] = [s in SPSET[Y] for Y in Y_]; df["dv_rank"] = [uni[Y]["dv"].get(s, 0) for Y in Y_]
    qi = [QI[t] for t in d[good]]
    for k in QK:
        df["q_" + k] = QF[k][qi]
    for k in (20, 60, 120):
        df[f"rs{k}"] = df[f"r{k}"] - QF[f"r{k}"][qi]
    res = [outcomes(h, l, c, i, a[i]) for i in good]
    df["buy"], df["buy_day"], df["sell"], df["sell_day"], df["d20"], df["d20_day"] = map(np.array, zip(*res))
    df["r20"] = c[good + H] / c[good] - 1
    df["r60"] = [c[i + H2] / c[i] - 1 if i + H2 < n else np.nan for i in good]
    df["end20"] = d[good + H]
    frames.append(df)
    if (n_ + 1) % 100 == 0:
        print(n_ + 1, "/", len(yrs_of), flush=True)
S = pd.concat(frames, ignore_index=True)
fc = [k for k in S.columns if k not in ("sym", "date", "year", "i", "in_sp", "dv_rank", "end20", "buy", "sell", "buy_day", "sell_day")]
S[fc] = S[fc].replace([np.inf, -np.inf], np.nan).astype("float32")
for k in ("buy", "sell", "buy_day", "sell_day", "i", "year", "dv_rank"):
    S[k] = S[k].astype("int32")
S.to_pickle(os.path.join(OUT, "out", "S7.pkl"))
print("列數", len(S), "檔數", S.sym.nunique(), "日期", S.date.min(), "~", S.date.max(), "最後決定日", LASTDEC)
print("買方 先漲/先跌/都沒到 %:", [round(100 * float((S.buy == k).mean()), 1) for k in (1, 0, 2)])
print("賣方 先跌/被軋/都沒到 %:", [round(100 * float((S.sell == k).mean()), 1) for k in (1, 0, 2)])
print("D20 先漲比例 %:", round(100 * float(S.d20.mean()), 1), "有效", int(S.d20.notna().sum()))
print("每年列數:", S.groupby("year").size().to_dict())
