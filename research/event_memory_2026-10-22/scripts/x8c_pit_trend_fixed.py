#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事後檢查(沒有預先登記;E9 / E9b 的更正版,原版保留;回應 Codex 2026-10-23 02:39:18 第 5.4 點:先報同名單的資料修正影響,再報換名單)。
修正規則(在跑這支程式之前寫定;旗標定義見 x9_price_audit.py):
  R0 身份錯接的(年, 代號)不列入「當年名單」類(PIT、PIT_SP、L341∩PIT):PARA 2021–2025(價格是 Banzai)、IR 2017–2020(價格是 Gardner Denver)、SE 2017(價格是 Sea Ltd)
     ——固定的 2026 名單(END、END_SP、L341)裡的 IR 就是現在的 Ingersoll Rand Inc.,價格是對的,不排除(v2 改正:v1 對所有名單都排除)
  R1 特徵窗(決定日前 253 根)裡 F_SYN(四價相同且量 0)超過 5 列 → 不合格(擋「假歷史」,容忍零星一兩天)
  R2 進場那根是 F_SYN → 那天買不到,不選(下一名遞補)
  R3 出場那根是 F_SYN → 改用之後第一根不是 F_SYN 的開盤(最後一期也一樣,所以可能用到期末之後的價格;全部記錄);找不到 → 最後收盤(列入清單)
  R4 F_O(開盤 = 收盤,可能是補值):補上的開盤就是當天收盤,E9 等於「收盤成交」,這是買得到的價格 → 主版不改;
     敏感度版 R4s:F_O 進場也不選(F_O 出場仍用當天收盤)
第二部分(E9d,換名單,用同一套修正規則):Codex R6 的 341 檔(2026-10-11 封存,SHA-256 0b4c23ee…4448;對到我們的 K 棒 330 檔)
  L341 = 330 檔固定用到底;L341∩PIT = 每年只留「當年也在我們的 walk7 名單(S&P 500 ∪ 前一年成交金額前 100)裡」的
     (同公司別名 = Yahoo 公司名稱相同的代號;實際只找到 BRK-B/BRK-A;MMC/MRSH 在 walk7 名單裡本來就缺,見 E10)
  這只是「交集敏感度」,不是修好的當時名單:341 本身已扣掉 R6 之前研究過的 266 檔,也找不回下市股。
期間與成交照 E9 / E9b;不碰保留季 2026-07 ~ 09。
用法:python3 -I x8c_pit_trend_fixed.py SCRATCH   → SCRATCH/em/out/x8c_pit_trend_fixed.json"""
import gzip, json, os, pickle, sys
from collections import defaultdict
import numpy as np

ROOT = sys.argv[1]; OUT = os.path.join(ROOT, "em", "out")
D = pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz"))); B = D["bars"]
U = json.load(open(os.path.join(ROOT, "wt", "research", "walk7_2026-10-21", "out", "universe.json")))
L341_RAW = open(os.path.join(ROOT, "em", "codex_341", "symbols_341.txt")).read().split()
CAL = list(B["SPY"]["d"]); HOLD_FROM = "2026-07-01"
IDX = {s: {d: k for k, d in enumerate(B[s]["d"])} for s in B}
FO, SYN = {}, {}
for s, b in B.items():
    o, h, l, ac, c, v = b["x"].T
    FO[s] = o == ac; SYN[s] = (o == h) & (h == l) & (l == ac) & (v == 0)
CS_SYN = {s: np.r_[0, np.cumsum(SYN[s])] for s in B}
BAD = {("PARA", str(y)) for y in range(2021, 2026)} | {("IR", str(y)) for y in range(2017, 2021)} | {("SE", "2017")}
L341 = sorted({s.replace(".", "-") for s in L341_RAW if s.replace(".", "-") in B})
byname = defaultdict(set)
for s, b in B.items():
    byname[(b.get("name") or "").strip().lower()].add(s)
ALIAS = {s: byname[(B[s].get("name") or "").strip().lower()] for s in L341}     # 同一個 Yahoo 公司名稱的其他代號


def names(year, sp_only=False):
    u = U[str(year)]; return sorted(set(u["sp"]) if sp_only else set(u["sp"]) | set(u["dv"].keys()))


def lst_for(kind, y):
    if kind == "PIT":
        return names(y)
    if kind == "PIT_SP":
        return names(y, True)
    if kind == "END":
        return names(2026)
    if kind == "END_SP":
        return names(2026, True)
    if kind == "L341":
        return L341
    if kind == "L341∩PIT":
        pit = set(names(y)); return [s for s in L341 if ALIAS[s] & pit]
    raise ValueError(kind)


def features(s, d):
    k = IDX[s].get(d)
    if k is None or k < 253:
        return None
    c = B[s]["x"][:k, 3]
    if np.any(~np.isfinite(c[-253:])) or np.any(c[-253:] <= 0):
        return None
    lr = np.diff(np.log(c[-64:]))
    return {"r252": c[-1] / c[-253] - 1, "m121": c[-22] / c[-253] - 1, "vol": lr.std(ddof=1) * np.sqrt(252), "k": k}


def run(rule, kind, start, end, fix=True, r4s=False, log=None):
    assert end < HOLD_FROM
    days = [d for d in CAL if start <= d <= end]; reb = days[::21]
    if reb[-1] != days[-1]:
        reb.append(days[-1])
    eq = 1.0; w_prev = {}
    for a, b in zip(reb[:-1], reb[1:]):
        y = int(a[:4]); cand = {}
        for s in lst_for(kind, y):
            if s not in B or IDX[s].get(a) is None:
                continue
            f = features(s, a)
            if not f:
                continue
            k = f["k"]
            if fix:
                if kind in ("PIT", "PIT_SP", "L341∩PIT") and (s, str(y)) in BAD:   # R0(只對當年名單類)
                    continue
                if CS_SYN[s][k] - CS_SYN[s][k - 253] > 5:               # R1
                    continue
                if SYN[s][k]:                                            # R2
                    continue
                if r4s and FO[s][k]:                                     # R4s
                    continue
            cand[s] = f
        if rule == "EW":
            pick = sorted(cand)
        elif rule == "TSMOM_LONG":
            pick = sorted([s for s in cand if cand[s]["r252"] > 0 and cand[s]["vol"] > 0], key=lambda s: -cand[s]["r252"] / cand[s]["vol"])[:20]
        else:
            pick = sorted(cand, key=lambda s: -cand[s]["m121"])[:20]
        w = {s: 1 / len(pick) for s in pick} if pick else {}
        eq *= 1 - 0.001 * sum(abs(w.get(s, 0) - w_prev.get(s, 0)) for s in set(w) | set(w_prev))
        rets = {}; last = b == reb[-1]
        for s in pick:
            x = B[s]["x"]; o0 = float(x[IDX[s][a], 0]); kb = IDX[s].get(b); note = None
            if kb is None:                                               # 缺價:最後收盤(E9 / E9b 實際 0 次)
                kk = int(np.searchsorted(B[s]["d"], b, side="right") - 1); o1 = float(x[kk, 3]); note = "缺價→最後收盤"
            elif fix and SYN[s][kb]:                                     # R3
                nxt = np.where(~SYN[s][kb:])[0]
                if len(nxt):
                    kk = kb + int(nxt[0]); o1 = float(x[kk, 0]); note = f"R3→{B[s]['d'][kk]} 開盤"
                else:
                    kk = len(B[s]["d"]) - 1; o1 = float(x[kk, 3]); note = "R3→最後收盤"
            else:
                o1 = float(x[kb, 3] if last else x[kb, 0])
            rets[s] = o1 / o0 - 1
            if log is not None and note:
                log.append((rule, kind, start, a, b, s, note, round(rets[s] * 100, 2)))
        eq *= 1 + sum(w[s] * rets[s] for s in pick)
        tot = sum(w[s] * (1 + rets[s]) for s in pick) or 1.0
        w_prev = {s: w[s] * (1 + rets[s]) / tot for s in pick}
    eq *= 1 - 0.001 * sum(w_prev.values())
    return round((eq - 1) * 100, 2)


def spy(start, end):
    days = [d for d in CAL if start <= d <= end]; x = B["SPY"]["x"]
    return round((x[IDX["SPY"][days[-1]], 3] / x[IDX["SPY"][days[0]], 0] * 0.999 ** 2 - 1) * 100, 2)


E9 = json.load(open(os.path.join(OUT, "x8_pit_trend.json")))["結果"]
E9b = json.load(open(os.path.join(OUT, "x8b_pit_trend_years.json")))
res = {"說明": __doc__.split("\n")[0], "341": {"清單檔 SHA-256": "0b4c23eec9dbbba86cc67d5b4c1c07ff26d8f130b6591df1ea5ec726102b4448",
                                             "對到 K 棒": len(L341), "沒有 K 棒": sorted(s for s in L341_RAW if s.replace(".", "-") not in B),
                                             "別名(和 341 代號同公司、不同代號)": {s: sorted(ALIAS[s] - {s}) for s in L341 if len(ALIAS[s]) > 1},
                                             "L341∩PIT 每年檔數": {y: len(lst_for("L341∩PIT", y)) for y in range(2017, 2027)}}}
rep = {}                                                                 # 重現檢查:不套修正時要和原版完全一樣
for rule in ("TSMOM_LONG", "MOM12_1", "EW"):
    for kind in ("PIT", "END", "PIT_SP", "END_SP"):
        rep[f"{rule}|{kind}|2024-01~2026-06"] = run(rule, kind, "2024-01-02", "2026-06-30", fix=False) == E9[f"{rule}|{kind}"]["累計%"]
    for kind in ("PIT", "PIT_SP"):
        rep[f"{rule}|{kind}|2017~2023"] = run(rule, kind, "2017-01-03", "2023-12-29", fix=False) == E9b["連續"]["2017-01-03~2023-12-29"][f"{rule}|{kind}"]
res["重現檢查(不套修正 = 原版)"] = {"全部相同": all(rep.values()), "明細": rep}
print("reproduce", all(rep.values()), {k: v for k, v in rep.items() if not v}, flush=True)
log = []
part1 = {}
for rule in ("TSMOM_LONG", "MOM12_1", "EW"):
    for kind in ("PIT", "END", "PIT_SP", "END_SP"):
        orig = E9[f"{rule}|{kind}"]["累計%"]
        fx = run(rule, kind, "2024-01-02", "2026-06-30", log=log); fs = run(rule, kind, "2024-01-02", "2026-06-30", r4s=True)
        part1[f"{rule}|{kind}|2024-01~2026-06"] = {"原版": orig, "修正": fx, "修正+R4s": fs, "差(修正−原版)": round(fx - orig, 2)}
    for kind in ("PIT", "PIT_SP"):
        orig = E9b["連續"]["2017-01-03~2023-12-29"][f"{rule}|{kind}"]
        fx = run(rule, kind, "2017-01-03", "2023-12-29", log=log); fs = run(rule, kind, "2017-01-03", "2023-12-29", r4s=True)
        part1[f"{rule}|{kind}|2017~2023"] = {"原版": orig, "修正": fx, "修正+R4s": fs, "差(修正−原版)": round(fx - orig, 2)}
    print(rule, {k: v for k, v in part1.items() if k.startswith(rule)}, flush=True)
years = {}
for y in range(2017, 2027):
    ys = [d for d in CAL if d[:4] == str(y) and d < HOLD_FROM]; st, en = ys[0], (ys[-1] if y < 2026 else "2026-06-30")
    row = {"SPY": spy(st, en)}
    for rule in ("TSMOM_LONG", "MOM12_1", "EW"):
        for kind in ("PIT", "PIT_SP"):
            row[f"{rule}|{kind}"] = {"原版": E9b["逐年"][str(y)][f"{rule}|{kind}"], "修正": run(rule, kind, st, en, log=log)}
    years[str(y)] = row
res["第一部分:資料修正(同名單)"] = {"E9 / E9b 連續段": part1, "逐年": years}
part2 = {}
for st, en in (("2024-01-02", "2026-06-30"), ("2017-01-03", "2023-12-29")):
    row = {"SPY": spy(st, en)}
    for rule in ("TSMOM_LONG", "MOM12_1", "EW"):
        for kind in ("L341", "L341∩PIT", "PIT", "END"):
            row[f"{rule}|{kind}"] = run(rule, kind, st, en, log=log)
    part2[f"{st}~{en}"] = row
    print(st, en, row, flush=True)
res["第二部分:換名單(341;修正規則)"] = part2
res["R3 / 缺價 出場紀錄(修正版全部執行、去重)"] = sorted(set(log))
json.dump(res, open(os.path.join(OUT, "x8c_pit_trend_fixed.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(res["341"], ensure_ascii=False)[:1500])
print(res["R3 / 缺價 出場紀錄(修正版全部執行、去重)"][:20])
