#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感訓練 I8(事後探索,不是預先登記的檢定;給第 2 輪設計用)

問題:第 1 輪的判讀其實是在押「風格」(喜歡低波動、避開高波動)。如果判讀當天就知道「最近是高波動股強還是低波動股強」,
     能不能分辨押對 / 押錯?
做法(只用當天以前的資料):每個交易日,把 268 檔依近 20 天日波動分三組,算「高波動組近 20 天平均漲跌 − 低波動組」= 風格溫度。
     看經驗庫(2010 ~ 2026-06)和練習期間(2026-07 ~ 09)的個股買點:按「自己的波動」×「當天風格溫度」分組的勝率 / 平均報酬。
用法:python3 i8_style_probe.py SCRATCH_DIR
"""
import gzip, json, os, sys
import numpy as np

S = sys.argv[1]
BARS = json.load(gzip.open(os.path.join(S, "data", "bars.json.gz")))
bank = json.load(gzip.open(os.path.join(S, "bank.json.gz"), "rt", encoding="utf-8"))
OC = json.load(open(os.path.join(S, "sealed", "outcomes_ALL.json")))["marks"]
R = json.load(open(os.path.join(S, "registry.json")))
cal = [b[0] for b in BARS["SPY"] if b[0] >= "2009-06-01"]; ci = {d: k for k, d in enumerate(cal)}
V = np.full((len(BARS), len(cal)), np.nan); R20 = np.full((len(BARS), len(cal)), np.nan)
for a, (s, B) in enumerate(sorted(BARS.items())):
    C = {b[0]: b[4] for b in B}; arr = np.array([C.get(d, np.nan) for d in cal])
    lr = np.diff(np.log(arr), prepend=np.nan)
    for k in range(21, len(cal)):
        w = lr[k - 19:k + 1]
        if np.isfinite(w).sum() >= 18:
            V[a, k] = np.nanstd(w, ddof=1)
        if np.isfinite(arr[k]) and np.isfinite(arr[k - 20]):
            R20[a, k] = arr[k] / arr[k - 20] - 1
temp = {}
for k in range(21, len(cal)):
    v = V[:, k]; r = R20[:, k]; m = np.isfinite(v) & np.isfinite(r)
    if m.sum() < 60:
        continue
    q1, q2 = np.nanpercentile(v[m], [33.3, 66.7])
    temp[cal[k]] = float(np.mean(r[m & (v >= q2)]) - np.mean(r[m & (v <= q1)]))


def tab(rows, label):
    out = []
    for vl, vf in (("自己低波動 <2.5", lambda x: x < 2.5), ("自己高波動 ≥4", lambda x: x >= 4)):
        for tl, tf in (("風格溫度 < −3%(低波動股強)", lambda t: t < -0.03), ("−3% ~ +3%", lambda t: -0.03 <= t <= 0.03), ("> +3%(高波動股強)", lambda t: t > 0.03)):
            g = [r for r in rows if r["vol"] is not None and vf(r["vol"]) and r["temp"] is not None and tf(r["temp"])]
            if len(g) >= 20:
                out.append(f"| {label} | {vl} | {tl} | {len(g)} | {100 * np.mean([x['win'] for x in g]):.1f}% | {100 * np.mean([x['ret'] for x in g]):+.2f}% |")
    return out


H = [{"vol": r["vol20_daily"], "temp": temp.get(r["date"]), "win": r["win"], "ret": r["ret"]} for r in bank
     if r["q"] == "buy" and r["type"] == "stock" and r["exit_date"] < "2026-07-01"]
P = []
for d in R["days"]:
    for m in json.load(open(R["days"][d]["pack"]))["marks"]:
        if m["q"] == "buy" and m["type"] == "stock":
            o = OC[m["id"]]; P.append({"vol": m["vol20_daily"], "temp": temp.get(d), "win": o["win"], "ret": o["ret"], "date": d})
L = ["| 資料 | 這檔的波動 | 當天風格溫度 | 筆數 | 賺的比例 | 平均報酬 |", "|---|---|---|---:|---:|---:|"] + tab(H, "2010~2026-06") + tab(P, "2026-07~09 練習題")
print("\n".join(L))
ts = {d: round(100 * temp[d], 1) for d in sorted(temp) if "2026-06-15" <= d <= "2026-09-15"}
print("風格溫度(%)每週一次:", {d: v for k, (d, v) in enumerate(ts.items()) if k % 5 == 0})
json.dump({"table_md": L, "temp_2026": ts}, open(os.path.join(S, "style_probe.json"), "w"), ensure_ascii=False, indent=1)
