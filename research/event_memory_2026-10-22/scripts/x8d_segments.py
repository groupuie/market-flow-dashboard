#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""事後描述(沒有預先登記;回應 Codex 2026-10-23 02:39:18 第 2.4 點):E9 的 TSMOM_LONG|PIT 連續帳戶(2024-01-02 ~ 2026-06-30;x8c 已確認資料修正後選股不變)
同一個帳戶的分段淨值(兩種半年切法)與 2026-01-06 起各股的金額貢獻(淨與正);回答「+193.2% 有多少來自 2026 上半年 / 記憶體與儲存股」。
規則、成本、成交和 x8_pit_trend.py 完全一樣(本程式先重現 +193.2% 再拆)。
用法:python3 -I x8d_segments.py SCRATCH   → SCRATCH/em/out/x8d_segments.json"""
import gzip, json, math, os, pickle, sys
from collections import defaultdict
import numpy as np

ROOT = sys.argv[1]; OUT = os.path.join(ROOT, "em", "out")
B = pickle.load(gzip.open(os.path.join(ROOT, "w7", "data", "daily.pkl.gz")))["bars"]
U = json.load(open(os.path.join(ROOT, "wt", "research", "walk7_2026-10-21", "out", "universe.json")))
CAL = list(B["SPY"]["d"]); IDX = {s: {d: k for k, d in enumerate(B[s]["d"])} for s in B}
MEM = {"SNDK", "MU", "STX", "WDC"}                       # 記憶體與儲存四檔(Codex 在看過 E9b 之後點名的,不是預先登記)


def names(y):
    u = U[str(y)]; return sorted(set(u["sp"]) | set(u["dv"].keys()))


def feat(s, d):
    k = IDX[s].get(d)
    if k is None or k < 253:
        return None
    c = B[s]["x"][:k, 3]
    if np.any(~np.isfinite(c[-253:])) or np.any(c[-253:] <= 0):
        return None
    lr = np.diff(np.log(c[-64:])); return c[-1] / c[-253] - 1, lr.std(ddof=1) * np.sqrt(252)


days = [d for d in CAL if "2024-01-02" <= d <= "2026-06-30"]; reb = days[::21]
if reb[-1] != days[-1]:
    reb.append(days[-1])
eq = 1.0; w_prev = {}; nav = [(reb[0], 1.0)]; contrib = defaultdict(float); per = []
for a, b in zip(reb[:-1], reb[1:]):
    cand = {}
    for s in names(int(a[:4])):
        if s in B and IDX[s].get(a) is not None:
            f = feat(s, a)
            if f and f[0] > 0 and f[1] > 0:
                cand[s] = f[0] / f[1]
    pick = sorted(cand, key=lambda s: -cand[s])[:20]
    w = {s: 1 / len(pick) for s in pick}
    eq *= 1 - 0.001 * sum(abs(w.get(s, 0) - w_prev.get(s, 0)) for s in set(w) | set(w_prev))
    last = b == reb[-1]; rets = {}
    for s in pick:
        x = B[s]["x"]; kb = IDX[s].get(b)
        o1 = x[kb, 3] if last else x[kb, 0]
        rets[s] = float(o1 / x[IDX[s][a], 0] - 1)
    gain = {s: eq * w[s] * rets[s] for s in pick}          # 這一期每檔賺賠的金額(起始帳戶 = 1)
    if a >= "2026-01-01":
        for s, g in gain.items():
            contrib[s] += g
    per.append({"a": a, "b": b, "期報酬%": round(100 * sum(w[s] * rets[s] for s in pick), 2), "記憶體儲存檔數": sum(s in MEM for s in pick)})
    eq *= 1 + sum(w[s] * rets[s] for s in pick)
    tot = sum(w[s] * (1 + rets[s]) for s in pick); w_prev = {s: w[s] * (1 + rets[s]) / tot for s in pick}
    nav.append((b, eq))
eq *= 1 - 0.001 * sum(w_prev.values()); nav[-1] = (nav[-1][0], eq)
assert round((eq - 1) * 100, 2) == 193.2, eq
segs = {}
for lab, lo, hi in (("2024 上半年", "2024-01-01", "2024-07-01"), ("2024 下半年", "2024-07-01", "2025-01-01"), ("2025 上半年", "2025-01-01", "2025-07-01"),
                    ("2025 下半年", "2025-07-01", "2026-01-01"), ("2026 上半年", "2026-01-01", "2026-07-01")):
    pts = [v for d, v in nav if d < hi]; start = [v for d, v in nav if d < lo]
    v0 = start[-1] if start else 1.0; v1 = pts[-1]
    segs[lab] = {"起點調整日": max([d for d, v in nav if d < lo], default=nav[0][0]), "倍數": round(v1 / v0, 4)}
tot_log = math.log(eq)
for k in segs:
    segs[k]["佔全期對數成長%"] = round(100 * math.log(segs[k]["倍數"]) / tot_log, 1)
# 第二種切法:從界線後第一個調整日起算(不含跨界那一期)
nav_d = [d for d, v in nav]; segs2 = {}
for lab, lo, hi in (("2024 上半年", "2024-01-01", "2024-07-01"), ("2024 下半年", "2024-07-01", "2025-01-01"), ("2025 上半年", "2025-01-01", "2025-07-01"),
                    ("2025 下半年", "2025-07-01", "2026-01-01"), ("2026 上半年", "2026-01-01", "2026-07-01")):
    i0 = min(i for i, d in enumerate(nav_d) if d >= lo); i1 = min([i for i, d in enumerate(nav_d) if d >= hi], default=len(nav) - 1)
    m = nav[i1][1] / nav[i0][1]
    segs2[lab] = {"起點調整日": nav_d[i0], "終點": nav_d[i1], "期數": i1 - i0, "倍數": round(m, 4), "佔全期對數成長%": round(100 * math.log(m) / tot_log, 1)}
segs2["註"] = "每段的起點都是界線之後第一個調整日;跨界那一期算在前一段(分段 A 算在後一段);兩種切法各段倍數相乘都 = 全期"
g26 = sum(contrib.values()); gm = sum(v for s, v in contrib.items() if s in MEM)
gpos = sum(v for v in contrib.values() if v > 0); gmpos = sum(v for s, v in contrib.items() if s in MEM and v > 0)
res = {"說明": __doc__.split("\n")[0], "全期累計%": round((eq - 1) * 100, 2), "分段 A(跨界那一期算在後一段;各段相乘 = 全期)": segs,
       "分段 B(從界線後第一個調整日起)": segs2,
       "2026 上半年各期": [p for p in per if p["a"] >= "2026-01-01"],
       "2026 上半年金額貢獻(起始帳戶 = 1;前 12 檔)": sorted(((s, round(v, 4)) for s, v in contrib.items()), key=lambda t: -t[1])[:12],
       "2026-01-06 起:四檔佔淨獲利%": round(100 * gm / g26, 1) if g26 else None,
       "2026-01-06 起:四檔佔正獲利(只加賺錢的部位)%": round(100 * gmpos / gpos, 1) if gpos else None,
       "註": "分段倍數相乘 = 全期(含成本);2026 上半年第一個調整日是 " + min(d for d, v in nav if d >= "2026-01-01")}
json.dump(res, open(os.path.join(OUT, "x8d_segments.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
