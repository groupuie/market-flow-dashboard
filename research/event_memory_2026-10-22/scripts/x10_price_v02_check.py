#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""資料稽核 + 開發描述(不看保留季;回應 Codex 2026-10-23 02:39:18 第 5.1 點與複核意見):用價格層 v0.2(p4_price_v02.py,原始回應、缺值不補)
  1. 原始開 / 高 / 低 / 收的缺值**實數**(只算 2026-07-01 以前;這是 2026-10-23 重抓的 Yahoo 版本,不一定等於 walk7 當時抓到的版本)
  2. 對照 walk7 的上界旗標:F_O(開 = 收)、F_H(高 = max(開, 收))、F_L(低 = min(開, 收))裡,幾列在 v0.2 原始資料真的是缺值
  3. E9 / E9b 選股的進出場、FL3 事件窗列,實際碰到原始缺值幾次
  4. FL3_A60 v0.2(契約 v0.2 §3;准入 §2b)重算事件窗基準率:**不用** walk7 W1 的未來 20 天篩選;只換價格層與准入,反應日仍用 walk8 的(正式版要改);
     只收答案在 2026-07-01 以前成熟的列(t+3 < 2026-07-01);名單 = walk7 當年名單扣掉 E10 的身份接錯
用法:python3 -I x10_price_v02_check.py SCRATCH   → SCRATCH/em/out/x10_price_v02_check.json"""
import gzip, json, os, pickle, sys
from collections import Counter
import numpy as np, pandas as pd

ROOT = sys.argv[1]; OUT = os.path.join(ROOT, "em", "out"); HOLD_FROM = "2026-07-01"
W7 = pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz")))["bars"]
V2 = pickle.load(gzip.open(os.path.join(ROOT, "pv2", "bars_v02.pkl.gz")))["bars"]
U = json.load(open(os.path.join(ROOT, "wt", "research", "walk7_2026-10-21", "out", "universe.json")))
EA = pd.read_pickle(os.path.join(ROOT, "w8", "out", "ea_events.pkl"))[["sym", "r"]]
BAD = {("PARA", str(y)) for y in range(2021, 2026)} | {("IR", str(y)) for y in range(2017, 2021)} | {("SE", "2017")}
res = {"說明": __doc__.split("\n")[0]}

# ---------- 1. 原始缺值實數 ----------
N = {}
for s, b in V2.items():
    raw = b["raw"]; d = np.array(b["d"]); pre = d < HOLD_FROM
    nul = np.isnan(raw[:, :4]); vz = np.isnan(raw[:, 4]) | (raw[:, 4] == 0)
    flat = (raw[:, 0] == raw[:, 1]) & (raw[:, 1] == raw[:, 2]) & (raw[:, 2] == raw[:, 3])
    N[s] = {"d": d, "pre": pre, "o": nul[:, 0], "h": nul[:, 1], "l": nul[:, 2], "c": nul[:, 3], "notrade": flat & vz, "idx": {x: i for i, x in enumerate(d)}}
tot = int(sum(N[s]["pre"].sum() for s in N))
c1 = {k: int(sum((N[s][k] & N[s]["pre"]).sum() for s in N)) for k in ("o", "h", "l", "c", "notrade")}
res["1 原始缺值(2026-07-01 以前)"] = {"列數": tot, "開缺": c1["o"], "高缺": c1["h"], "低缺": c1["l"], "收缺": c1["c"], "沒有交易(四價相同且量 0 或缺)": c1["notrade"],
                                    "開缺最多的 10 檔": Counter({s: int((N[s]["o"] & N[s]["pre"]).sum()) for s in N}).most_common(10)}

# ---------- 2. walk7 上界旗標 vs v0.2 原始缺值 ----------
cmp = Counter()
for s, b in W7.items():
    if s not in N:
        cmp["walk7 有、v0.2 沒有的代號"] += 1; continue
    o, h, l, ac = b["x"][:, 0], b["x"][:, 1], b["x"][:, 2], b["x"][:, 3]
    FO, FH, FL_ = o == ac, h == np.maximum(o, ac), l == np.minimum(o, ac)
    ix = N[s]["idx"]
    for k, dd in enumerate(b["d"]):
        if dd >= HOLD_FROM:
            break
        j = ix.get(dd)
        if j is None:
            cmp["walk7 有、v0.2 沒有的列"] += 1; continue
        on, hn, ln = N[s]["o"][j], N[s]["h"][j], N[s]["l"][j]
        cmp["對到的列"] += 1
        if FO[k]:
            cmp["F_O 列"] += 1; cmp["F_O 且 v0.2 開缺(確定是補的)"] += int(on)
        elif on:
            cmp["不是 F_O 但 v0.2 開缺(版本不同)"] += 1
        if FH[k]:
            cmp["F_H 列"] += 1; cmp["F_H 且 v0.2 高缺"] += int(hn)
        elif hn:
            cmp["不是 F_H 但 v0.2 高缺(版本不同)"] += 1
        if FL_[k]:
            cmp["F_L 列"] += 1; cmp["F_L 且 v0.2 低缺"] += int(ln)
        elif ln:
            cmp["不是 F_L 但 v0.2 低缺(版本不同)"] += 1
res["2 walk7 旗標 vs v0.2 原始缺值(2026-07-01 以前)"] = dict(cmp)


def nul_at(s, date, key):
    j = N.get(s, {}).get("idx", {}).get(date) if s in N else None
    return None if j is None else bool(N[s][key][j])


# ---------- 3. E9 / E9b 選股、FL3 事件窗列 ----------
P = pd.read_csv(os.path.join(OUT, "x9_flag_usage_e9.csv"))
main = P[P["期間"].isin(["2024-01-02~2026-06-30", "2017-01-03~2023-12-29"])].copy()
main["進場開缺"] = [nul_at(s, a, "o") for s, a in zip(main["代號"], main["a"])]
main["出場開缺"] = [nul_at(s, b, "o") if ex == "開盤" else False for s, b, ex in zip(main["代號"], main["b"], main["出場價"])]
summ = {}
for (rule, kind, per), g in main.groupby(["規則", "名單", "期間"]):
    if kind in ("PIT", "END"):
        summ[f"{rule}|{kind}|{per}"] = {"選股": len(g), "進場開缺": int(g["進場開缺"].fillna(False).sum()), "出場開缺": int(g["出場開缺"].fillna(False).sum()),
                                       "進場 F_O(上界)": int(g["進場F_O"].sum()), "出場 F_O(上界)": int(g["出場F_O"].sum()),
                                       "v0.2 找不到那天": int(g["進場開缺"].isna().sum() + g["出場開缺"].isna().sum())}
res["3a E9 / E9b 選股碰到原始開缺"] = summ
FL3 = pd.read_pickle(os.path.join(OUT, "fl3_rows.pkl"))
FL3 = FL3[(FL3.ev_lag >= 0) & FL3.FL3_A60.notna() & (pd.to_datetime(FL3["date"]) < HOLD_FROM)]
cnt3 = Counter()
for s, g in FL3.groupby("sym", sort=False):
    d7 = W7[s]["d"]
    for i in g["i"].values.astype(int):
        e_d = d7[i + 1] if i + 1 < len(d7) else None
        if e_d is None:
            continue
        cnt3["列"] += 1
        on = nul_at(s, e_d, "o")
        if on is None:
            cnt3["v0.2 找不到進場日"] += 1
        elif on:
            cnt3["進場開缺"] += 1
        win = [d7[i + k] for k in (1, 2, 3) if i + k < len(d7)]
        if any(nul_at(s, x, "l") or nul_at(s, x, "c") for x in win):
            cnt3["答案窗低或收缺"] += 1
        atr = [d7[k] for k in range(max(i - 59, 0), i + 1)]
        if any(nul_at(s, x, "h") or nul_at(s, x, "l") for x in atr):
            cnt3["ATR60 窗高或低缺"] += 1
res["3b FL3 事件窗列(walk7 W1 篩過;2026-07-01 以前)碰到原始缺值"] = dict(cnt3)


# ---------- 4. FL3_A60 v0.2 重算(不用 W1 未來篩選) ----------
def series(s):
    b = V2[s]; raw = b["raw"]; f = b["adjclose"] / raw[:, 3]
    o, h, l, c = (raw[:, k] * f for k in range(4))
    return np.array(b["d"]), o, h, l, c, N[s]


CALPOS = {x: i for i, x in enumerate(V2["SPY"]["d"])}                    # 交易日曆 = SPY 有 K 棒的日子(正式版改用 NYSE 官方日曆)
rows = []
for s, g in EA.groupby("sym"):
    if s not in V2 or s not in W7:
        continue
    d, o, h, l, c, nn = series(s); idx = nn["idx"]; d7 = W7[s]["d"]
    bad_bar = nn["notrade"] | nn["h"] | nn["l"] | nn["c"]
    for r7 in g["r"].values.astype(int):
        if r7 >= len(d7):
            continue
        for k in range(5):
            if r7 + k >= len(d7):
                break
            t_date = d7[r7 + k]; y = t_date[:4]
            if y not in U or s not in (set(U[y]["sp"]) | set(U[y]["dv"].keys())) or (s, y) in BAD:
                continue
            t = idx.get(t_date)
            if t is None:
                rows.append((s, t_date, k, "v0.2 沒有這天", None)); continue
            if t + 3 >= len(d) or d[t + 3] >= HOLD_FROM:
                continue                                                  # 答案在保留季或之後才成熟 → 不收
            if t < 60 or bad_bar[t - 60: t + 1].any() or np.isnan(c[t - 60]):
                rows.append((s, t_date, k, "feature_missing", None)); continue
            p0, p3 = CALPOS.get(d[t - 60]), CALPOS.get(d[t + 3])
            if p0 is None or p3 is None or p3 - p0 != 63:                  # 中間少了交易日(停牌整天沒有 K 棒)
                rows.append((s, t_date, k, "calendar_gap", None)); continue
            pc = c[t - 60: t]; hh, ll = h[t - 59: t + 1], l[t - 59: t + 1]
            A = float(np.mean(np.maximum(hh, pc) - np.minimum(ll, pc)))
            if nn["o"][t + 1] or nn["notrade"][t + 1]:
                rows.append((s, t_date, k, "entry_missing", None)); continue
            if (nn["notrade"][t + 1: t + 4] | nn["l"][t + 1: t + 4] | nn["c"][t + 1: t + 4]).any():
                rows.append((s, t_date, k, "label_unresolved", None)); continue
            e = o[t + 1]; y_ = 0
            for j in (1, 2, 3):
                if l[t + j] <= e - A:
                    break
                if c[t + j] >= e + A:
                    y_ = 1; break
            rows.append((s, t_date, k, "scored", y_))
R = pd.DataFrame(rows, columns=["sym", "date", "k", "status", "y"])
sc = R[R.status == "scored"]
unres = int((R.status == "label_unresolved").sum())
res["4 FL3_A60 v0.2 重算(事件窗;答案 2026-07-01 以前成熟)"] = {
    "列": len(R), "狀態": dict(Counter(R.status)), "計分列基準率%": round(100 * sc.y.mean(), 2),
    "依天(d0..d4)%": {int(k): round(100 * g.y.mean(), 2) for k, g in sc.groupby("k")},
    "界線:label_unresolved 全當 0 / 全當 1 時的基準率%": [round(100 * sc.y.sum() / (len(sc) + unres), 2), round(100 * (sc.y.sum() + unres) / (len(sc) + unres), 2)],
    "對照 E10(walk7 價格、W1 篩過、同期)": 23.56}
# 共同列:walk7 W1 列與 v0.2 計分列的答案是否一致
FL3k = FL3.assign(dd=[W7[s]["d"][int(i)] for s, i in zip(FL3.sym, FL3.i)])[["sym", "dd", "FL3_A60"]].rename(columns={"dd": "date"})
mm = FL3k.merge(sc[["sym", "date", "y"]], on=["sym", "date"], how="inner")
res["4b 共同列(walk7 W1 列 ∩ v0.2 計分列)"] = {"列": len(mm), "答案不同": int((mm.FL3_A60 != mm.y).sum()),
                                           "walk7 = 1、v0.2 = 0": int(((mm.FL3_A60 == 1) & (mm.y == 0)).sum()), "walk7 = 0、v0.2 = 1": int(((mm.FL3_A60 == 0) & (mm.y == 1)).sum()),
                                           "walk7 基準率%": round(100 * mm.FL3_A60.mean(), 2), "v0.2 基準率%": round(100 * mm.y.mean(), 2)}
# 多出來的列(v0.2 計分、但不在 walk7 W1 列)為什麼被 W1 拿掉:W1 起點 2016-10-21、整檔 ≥ 300 根、歷史 ≥ 252 根、之後 ≥ 20 根、[i−125, i+20] 量 > 0 且收盤不變 ≤ 2%
extra = sc.merge(FL3k[["sym", "date"]], on=["sym", "date"], how="left", indicator=True)
extra = extra[extra["_merge"] == "left_only"]
why = Counter()
for s_, d_ in zip(extra.sym, extra.date):
    i7 = {x: i for i, x in enumerate(W7[s_]["d"])}.get(d_) if s_ in W7 else None
    if i7 is None:
        why["walk7 沒有這天"] += 1; continue
    x = W7[s_]["x"]; v = x[:, 5]; cc = x[:, 3]
    if d_ < "2016-10-21":
        why["決定日早於 2016-10-21(W1 起點)"] += 1
    elif len(cc) < 300:
        why["整檔不到 300 根"] += 1
    elif i7 < 252:
        why["歷史不到 252 根"] += 1
    elif i7 + 20 >= len(cc):
        why["之後不到 20 根"] += 1
    else:
        vv, c2 = v[i7 - 125: i7 + 21], cc[i7 - 125: i7 + 21]
        why["[i−125, i+20] 有量 0" if (vv <= 0).any() else ("收盤不變 > 2%" if (np.diff(c2) == 0).mean() > 0.02 else "其他(名單 / 事件對應不同)")] += 1
res["4c v0.2 多出的計分列(不在 W1 列)"] = {"列": len(extra), "W1 拿掉的原因": dict(why), "這些列的基準率%": round(100 * extra.y.mean(), 2) if len(extra) else None}
json.dump(res, open(os.path.join(OUT, "x10_price_v02_check.json"), "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
