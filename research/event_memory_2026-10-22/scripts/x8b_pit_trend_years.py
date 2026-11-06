#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事後檢查(沒有預先登記;接 E9):同一套趨勢 / 動能規則,用「當年名單」逐年跑 2017 ~ 2026 上半年,看 2024–2026 的好成績是不是只在這一段。
規則、成本、成交方式和 x8_pit_trend.py 完全一樣(每 21 個交易日調整、前一天收盤以前的資料、當天開盤成交、前 20 名等權、單邊 10bp)。
  逐年:每年第一個交易日開始、最後一個交易日收盤清倉(2026 只到 06-30,不碰保留季 2026-07 ~ 09);名單 = 當年 1 月 1 日(walk7 universe.json)
  連續:2017-01-03 ~ 2023-12-29 一口氣跑(名單在年初換),和 E9 的 2024-01-02 ~ 2026-06-30 對照
名單限制:universe.json 只收「抓得到價格」的股票;後來下市 / 被併購的抓不到(2017 年 S&P 500 只有 415 檔、2024 年 476 檔),所以「當年名單」也有倖存者偏差,越早越大。
用法:python3 -I x8b_pit_trend_years.py SCRATCH   → SCRATCH/em/out/x8b_pit_trend_years.json"""
import gzip, json, os, pickle, sys
import numpy as np

ROOT = sys.argv[1]; OUT = os.path.join(ROOT, "em", "out")
B = pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz")))["bars"]
U = json.load(open(os.path.join(ROOT, "wt", "research", "walk7_2026-10-21", "out", "universe.json")))
CAL = list(B["SPY"]["d"])
IDX = {s: {d: k for k, d in enumerate(B[s]["d"])} for s in B}
HOLD_FROM = "2026-07-01"   # 保留季開始;任何結果都不能用到這天以後的價格


def names(year, sp_only=False):
    u = U[str(year)]; return sorted(set(u["sp"]) if sp_only else set(u["sp"]) | set(u["dv"].keys()))


def price(s, d, col):
    k = IDX[s].get(d)
    return None if k is None else float(B[s]["x"][k, col])


def last_close_upto(s, d):
    dd = B[s]["d"]; k = np.searchsorted(dd, d, side="right") - 1
    return float(B[s]["x"][k, 3]) if k >= 0 else None


def features(s, d):
    k = IDX[s].get(d)
    if k is None or k < 253:
        return None
    c = B[s]["x"][:k, 3]
    if np.any(~np.isfinite(c[-253:])) or np.any(c[-253:] <= 0):
        return None
    lr = np.diff(np.log(c[-64:]))
    return {"r252": c[-1] / c[-253] - 1, "m121": c[-22] / c[-253] - 1, "vol": lr.std(ddof=1) * np.sqrt(252)}


def run(rule, sp_only, start, end):
    assert end < HOLD_FROM
    days = [d for d in CAL if start <= d <= end]
    reb = days[::21]
    if reb[-1] != days[-1]:
        reb.append(days[-1])
    eq = 1.0; w_prev = {}; n_pick = []
    for a, b in zip(reb[:-1], reb[1:]):
        cand = {}
        for s in names(int(a[:4]), sp_only):
            if s not in B or price(s, a, 0) is None:
                continue
            f = features(s, a)
            if f:
                cand[s] = f
        if rule == "EW":
            pick = sorted(cand)
        elif rule == "TSMOM_LONG":
            pick = sorted([s for s in cand if cand[s]["r252"] > 0 and cand[s]["vol"] > 0], key=lambda s: -cand[s]["r252"] / cand[s]["vol"])[:20]
        else:  # MOM12_1
            pick = sorted(cand, key=lambda s: -cand[s]["m121"])[:20]
        w = {s: 1 / len(pick) for s in pick} if pick else {}
        eq *= 1 - 0.001 * sum(abs(w.get(s, 0) - w_prev.get(s, 0)) for s in set(w) | set(w_prev))
        rets = {}
        for s in pick:
            o0 = price(s, a, 0); o1 = price(s, b, 0) if b != reb[-1] else price(s, b, 3)
            rets[s] = (o1 if o1 is not None else last_close_upto(s, b)) / o0 - 1
        eq *= 1 + sum(w[s] * rets[s] for s in pick)
        tot = sum(w[s] * (1 + rets[s]) for s in pick) or 1.0
        w_prev = {s: w[s] * (1 + rets[s]) / tot for s in pick}
        n_pick.append(len(pick))
    eq *= 1 - 0.001 * sum(w_prev.values())
    return round((eq - 1) * 100, 2), min(n_pick)


def spy(start, end):
    days = [d for d in CAL if start <= d <= end]
    return round((price("SPY", days[-1], 3) / price("SPY", days[0], 0) * 0.999 ** 2 - 1) * 100, 2)


res = {"說明": __doc__.split("\n")[0], "逐年": {}, "連續": {}}
for y in range(2017, 2027):
    ys = [d for d in CAL if d[:4] == str(y) and d < HOLD_FROM]
    st, en = ys[0], (ys[-1] if y < 2026 else "2026-06-30")
    row = {"期間": [st, en], "SPY": spy(st, en)}
    for rule in ("TSMOM_LONG", "MOM12_1", "EW"):
        for sp_only in (False, True):
            r, mn = run(rule, sp_only, st, en)
            row[f"{rule}|{'PIT_SP' if sp_only else 'PIT'}"] = r
            if rule != "EW" and mn < 20:
                row[f"{rule}|{'PIT_SP' if sp_only else 'PIT'} 最少持股"] = mn
    res["逐年"][str(y)] = row
    print(y, row, flush=True)
for st, en in (("2017-01-03", "2023-12-29"), ("2024-01-02", "2026-06-30")):
    row = {"SPY": spy(st, en)}
    for rule in ("TSMOM_LONG", "MOM12_1", "EW"):
        for sp_only in (False, True):
            row[f"{rule}|{'PIT_SP' if sp_only else 'PIT'}"] = run(rule, sp_only, st, en)[0]
    res["連續"][f"{st}~{en}"] = row
    print(st, en, row, flush=True)
# 摘要:逐年贏 SPY 的年數(2017–2023 / 2024–2026H1 分開)
summ = {}
for k in ("TSMOM_LONG|PIT", "TSMOM_LONG|PIT_SP", "MOM12_1|PIT", "MOM12_1|PIT_SP", "EW|PIT", "EW|PIT_SP"):
    a = [y for y in range(2017, 2024) if res["逐年"][str(y)][k] > res["逐年"][str(y)]["SPY"]]
    b = [y for y in range(2024, 2027) if res["逐年"][str(y)][k] > res["逐年"][str(y)]["SPY"]]
    summ[k] = {"2017–2023 贏 SPY 的年": a, "2024–2026H1 贏 SPY 的年": b}
res["逐年贏 SPY"] = summ
json.dump(res, open(os.path.join(OUT, "x8b_pit_trend_years.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(summ, ensure_ascii=False))
