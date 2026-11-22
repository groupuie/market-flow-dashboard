#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事後檢查(沒有預先登記;回應 Codex R6 2026-10-22 23:44:00):趨勢 / 動能帳戶的好成績,有多少來自「用現在的名單回頭選股」?
同一套規則、同一段時間,只換股票名單:
  PIT = 當年 1 月 1 日的名單(walk7:當年 S&P 500 成分 ∪ 前一年成交金額前 100),逐年換
  END = 2026 年的名單(固定;近似 Codex「現在的 341 檔」那種事後名單)
  PIT_SP / END_SP = 同上但只用 S&P 500 成分(不含成交金額前 100)
規則(照 R6 的定義,盡量簡化):每 21 個交易日調整一次;用前一天收盤以前的資料,當天開盤成交;前 20 名等權;單邊 10bp。
  TSMOM_LONG:過去 252 日報酬 > 0,依「252 日報酬 ÷ 63 日年化波動」排序
  MOM12_1:C(t−21)/C(t−252) − 1 排序(跳過最近一個月)
  EW:名單內全部等權;另列 SPY 買進持有
期間:2024-01-02 ~ 2026-06-30(**不碰保留季 2026-07 ~ 09**,所以和 R6 的 2026-10-09 終點不同)。
期間中下市 / 沒有價格:用最後一個收盤價變現金。日 K 是 walk7 的還原價(scripts/astra_data.py),不是 R6 的 Alpaca 資料。
用法:python3 -I x8_pit_trend.py SCRATCH   → SCRATCH/em/out/x8_pit_trend.json"""
import gzip, json, os, pickle, sys
import numpy as np

ROOT = sys.argv[1]; OUT = os.path.join(ROOT, "em", "out")
B = pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz")))["bars"]
U = json.load(open(os.path.join(ROOT, "wt", "research", "walk7_2026-10-21", "out", "universe.json")))
CAL = list(B["SPY"]["d"]); START, END_D = "2024-01-02", "2026-06-30"
days = [d for d in CAL if START <= d <= END_D]
reb = days[::21]
if reb[-1] != days[-1]:
    reb.append(days[-1])   # 最後一天只用來結算
IDX = {s: {d: k for k, d in enumerate(B[s]["d"])} for s in B}


def names(year, sp_only=False):
    u = U[str(year)]; return sorted(set(u["sp"]) if sp_only else set(u["sp"]) | set(u["dv"].keys()))


END_LIST = names(2026); END_SP = names(2026, True)


def price(s, d, col):          # col 0 = 開盤、3 = 收盤(還原)
    k = IDX[s].get(d)
    return None if k is None else float(B[s]["x"][k, col])


def last_close_upto(s, d):
    dd = B[s]["d"]; k = np.searchsorted(dd, d, side="right") - 1
    return (float(B[s]["x"][k, 3]), dd[k]) if k >= 0 else (None, None)


def features(s, d):
    """d 的前一個交易日收盤以前的資料"""
    k = IDX[s].get(d)
    if k is None or k < 253:
        return None
    c = B[s]["x"][:k, 3]          # 不含 d 當天
    if np.any(~np.isfinite(c[-253:])) or np.any(c[-253:] <= 0):
        return None
    r252 = c[-1] / c[-253] - 1; m121 = c[-22] / c[-253] - 1
    lr = np.diff(np.log(c[-64:])); vol = lr.std(ddof=1) * np.sqrt(252)
    return {"r252": r252, "m121": m121, "vol": vol}


def run(rule, uni_kind):
    eq = 1.0; curve = [1.0]; w_prev = {}; turn = 0.0; picks_log = []
    for a, b in zip(reb[:-1], reb[1:]):
        lst = {"PIT": lambda: names(int(a[:4])), "END": lambda: END_LIST, "PIT_SP": lambda: names(int(a[:4]), True), "END_SP": lambda: END_SP}[uni_kind]()
        cand = {}
        for s in lst:
            if s not in B or price(s, a, 0) is None:
                continue
            f = features(s, a)
            if f:
                cand[s] = f
        if rule == "EW":
            pick = sorted(cand)
        elif rule == "TSMOM_LONG":
            pick = sorted([s for s in cand if cand[s]["r252"] > 0 and cand[s]["vol"] > 0], key=lambda s: -cand[s]["r252"] / cand[s]["vol"])[:20]
        elif rule == "MOM12_1":
            pick = sorted(cand, key=lambda s: -cand[s]["m121"])[:20]
        w = {s: 1 / len(pick) for s in pick} if pick else {}
        cost = 0.001 * sum(abs(w.get(s, 0) - w_prev.get(s, 0)) for s in set(w) | set(w_prev))
        eq *= (1 - cost); turn += sum(abs(w.get(s, 0) - w_prev.get(s, 0)) for s in set(w) | set(w_prev))
        rets = {}
        for s in pick:
            o0 = price(s, a, 0); o1 = price(s, b, 0) if b != reb[-1] else price(s, b, 3)
            if o1 is None:
                lc, _ = last_close_upto(s, b); o1 = lc
            rets[s] = o1 / o0 - 1
        pr = sum(w[s] * rets[s] for s in pick)
        eq *= (1 + pr); curve.append(eq)
        tot = sum(w[s] * (1 + rets[s]) for s in pick) or 1.0
        w_prev = {s: w[s] * (1 + rets[s]) / tot for s in pick}
        picks_log.append({"date": a, "n_cand": len(cand), "picks": pick[:20] if rule != "EW" else len(pick), "rets": ({s: round(rets[s] * 100, 1) for s in pick} if rule != "EW" else None)})
    eq *= (1 - 0.001 * sum(w_prev.values()))   # 最後清倉
    curve[-1] = eq
    yrs = (len(days) - 1) / 252
    cv = np.array(curve); mdd = float((cv / np.maximum.accumulate(cv) - 1).min())
    return {"累計%": round((eq - 1) * 100, 2), "CAGR%": round((eq ** (1 / yrs) - 1) * 100, 2), "調整日最大回撤%": round(mdd * 100, 2),
            "總換手(單邊和)": round(turn, 1), "picks": picks_log}


res = {"說明": __doc__.split("\n")[0], "期間": [days[0], days[-1]], "交易日": len(days), "調整次數": len(reb) - 1,
       "名單大小": {"PIT 2024 / 2025 / 2026": [len(names(y)) for y in (2024, 2025, 2026)], "END(2026)": len(END_LIST)}}
spy0 = price("SPY", days[0], 0); spy1 = price("SPY", days[-1], 3)
yrs = (len(days) - 1) / 252
res["SPY 買進持有"] = {"累計%": round((spy1 / spy0 * (1 - 0.001) ** 2 - 1) * 100, 2), "CAGR%": round(((spy1 / spy0 * (1 - 0.001) ** 2) ** (1 / yrs) - 1) * 100, 2)}
out = {}
for rule in ("TSMOM_LONG", "MOM12_1", "EW"):
    for kind in ("PIT", "END", "PIT_SP", "END_SP"):
        r = run(rule, kind); out[f"{rule}|{kind}"] = r
        print(rule, kind, {k: v for k, v in r.items() if k != "picks"}, flush=True)
res["結果"] = {k: {kk: vv for kk, vv in v.items() if kk != "picks"} for k, v in out.items()}
# 只在 END 名單、不在當年 PIT 名單的股票被選中的次數(TSMOM_LONG|END)
extra = {}
for p in out["TSMOM_LONG|END"]["picks"]:
    pit = set(names(int(p["date"][:4])))
    for s in p["picks"]:
        if s not in pit:
            extra[s] = extra.get(s, 0) + 1
res["TSMOM_LONG|END 選到「當年還不在名單」的股票(次數)"] = dict(sorted(extra.items(), key=lambda kv: -kv[1]))
res["TSMOM_LONG|END 選股中「當年還不在名單」的比例%"] = round(100 * sum(extra.values()) / sum(len(p["picks"]) for p in out["TSMOM_LONG|END"]["picks"]), 1)
# 貢獻:TSMOM_LONG|PIT 單期報酬最大的 10 筆(等權 1/20,所以單期貢獻 ≈ 報酬 ÷ 20)
top = sorted(((p["date"], s, r) for p in out["TSMOM_LONG|PIT"]["picks"] for s, r in (p["rets"] or {}).items()), key=lambda x: -x[2])[:10]
res["TSMOM_LONG|PIT 單期報酬最大的 10 筆(日期, 代號, 該期報酬%)"] = top
json.dump(res, open(os.path.join(OUT, "x8_pit_trend.json"), "w"), ensure_ascii=False, indent=1)
print(top)
print(json.dumps({k: res[k] for k in ("SPY 買進持有", "名單大小", "TSMOM_LONG|END 選股中「當年還不在名單」的比例%")}, ensure_ascii=False))
print(list(res["TSMOM_LONG|END 選到「當年還不在名單」的股票(次數)"].items())[:15])
