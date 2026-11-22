#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感訓練 I3:只對指定期間的練習題算結果(而且只用到 CUTOFF 那天為止的 K 線)

用法:python3 i3_outcomes.py SCRATCH_DIR FROM TO CUTOFF TAG
  例:P1 的錯題本 → FROM=2026-07-01 TO=2026-07-24 CUTOFF=2026-08-24(寫筆記的人看到的價格都早於 P2 第一天 08-25)
  最後總評 → FROM=2026-07-01 TO=2026-09-15 CUTOFF=2026-10-14
買點題 = 網站賣法(乙 / 丙,= astra_trades.exit_of),每邊扣 0.1%;頂點題 = 隔天開盤 → 第 11 天開盤。
結果要用到 CUTOFF 之後的 K 線 → status = open(不算)。
"""
import gzip, json, os, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import astra_data as AD, astra_trades as AT

S, FROM, TO, CUT, TAG = sys.argv[1:6]
COST = 0.001
BARS = json.load(gzip.open(os.path.join(S, "data", "bars.json.gz")))
IDX = [m for m in json.load(open(os.path.join(S, "sealed", "index.json"))) if FROM <= m["date"] <= TO]
out = {}
for s in sorted({m["sym"] for m in IDX}):
    B = [b for b in BARS[s] if b[0] <= CUT]; W = AD.sw_series(B); D = W["D"]; O = [x[1] for x in B]; n = W["n"]
    for m in [x for x in IDX if x["sym"] == s]:
        i = D.index(m["date"]); r = {"id": m["id"], "sym": s, "date": m["date"], "q": m["q"], "type": m["type"], "style": m["style"]}
        if m["q"] == "buy":
            r["sig_ok"] = i in dict(AT.buy_points(W))
            d, why = AT.exit_of(W, O, i, AT.STY[m["style"]])
            if d is not None and d + 1 < n:
                r.update(status="closed", exit_why=why, entry=D[i + 1], exit=D[d + 1], hold=d + 1 - (i + 1),
                         ret=AT.ret(O, i + 1, d + 1, COST), ret0=AT.ret(O, i + 1, d + 1, 0.0))
                r["win"] = r["ret"] > 0
            else:
                r["status"] = "open"
        else:
            r["sig_ok"] = i in set(W["top"])
            if i + 11 < n:
                r.update(status="closed", entry=D[i + 1], exit=D[i + 11], fr10=O[i + 11] / O[i + 1] - 1)
                r["win"] = r["fr10"] < 0
            else:
                r["status"] = "open"
        out[m["id"]] = r
json.dump({"from": FROM, "to": TO, "cutoff": CUT, "cost_per_side": COST, "marks": out}, open(os.path.join(S, "sealed", f"outcomes_{TAG}.json"), "w"), ensure_ascii=False)
c = {}
for r in out.values():
    k = (r["q"], r["status"]); c[k] = c.get(k, 0) + 1
print(TAG, {f"{a}/{b}": v for (a, b), v in sorted(c.items())}, "latest exit used:", max((r.get("exit") or "") for r in out.values()))
