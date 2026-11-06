#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感訓練 I7:總評(判讀檔已鎖指紋之後才跑)

用法:python3 i7_final.py SCRATCH_DIR
各組:A 盲判(P1、P2)、B 訓練後(P2)、M 純經驗庫(P1、P2:最像的過去比平常好就同意,p = 那 k 個對的比例)
另報:盲判按月份;P2 上 A 和 B 判得不一樣的題目,後來誰對;P1 錯題本用的結果和最後結果是否一致
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from i6_eval import evaluate, fmt, mean

S = sys.argv[1]
R = json.load(open(os.path.join(S, "registry.json")))
OC = json.load(open(os.path.join(S, "sealed", "outcomes_ALL.json")))["marks"]
O1 = json.load(open(os.path.join(S, "sealed", "outcomes_P1.json")))["marks"]
AN = json.load(open(os.path.join(S, "analogs.json")))
BASE = {("buy", "stock"): 0.55, ("buy", "idx"): 0.75, ("top", "stock"): 0.45, ("top", "idx"): 0.33}
DAYS = sorted(R["days"]); P1 = [d for d in DAYS if d <= "2026-07-24"]; P2 = [d for d in DAYS if d >= "2026-08-25"]
PK = {}
for d in DAYS:
    for m in json.load(open(R["days"][d]["pack"]))["marks"]:
        PK[m["id"]] = m


def rows(arm, days):
    out = []
    for d in days:
        if arm == "M":
            V = {i: {"v": "agree" if AN[i]["hit"] > AN[i]["base"] else "disagree", "p": AN[i]["hit"]} for i, m in PK.items() if m["date"] == d}
        else:
            p = os.path.join(S, f"verdicts_{arm}", d + ".json")
            if not os.path.exists(p):
                continue
            V = {m["id"]: m for m in json.load(open(p))["marks"]}
        for i, v in V.items():
            o = OC[i]
            if o["status"] != "closed":
                continue
            out.append({"id": i, "date": d, "q": o["q"], "type": o["type"], "v": v["v"], "p": float(v["p"]), "win": o["win"],
                        "ret": o.get("ret"), "fr10": o.get("fr10"), "sym": o["sym"], "month": d[:7]})
    return out


res = {}
for name, arm, days in (("A_blind_P1", "blind", P1), ("A_blind_P2", "blind", P2), ("A_blind_P1P2", "blind", P1 + P2),
                        ("B_trained_P2", "trained", P2), ("M_knn_P1", "M", P1), ("M_knn_P2", "M", P2)):
    rr = rows(arm, days); res[name] = evaluate(rr, days, BASE)
    for q in ("buy", "top"):
        if q in res[name]:
            print(f"{name:14s} {q}: " + fmt(res[name][q], q))
# 按月份(盲判)
res["A_blind_by_month"] = {}
for mo in ("2026-07", "2026-08", "2026-09"):
    days = [d for d in P1 + P2 if d.startswith(mo)]
    if days:
        res["A_blind_by_month"][mo] = evaluate(rows("blind", days), days, BASE)
        for q in ("buy", "top"):
            if q in res["A_blind_by_month"][mo]:
                print(f"blind {mo} {q}: " + fmt(res["A_blind_by_month"][mo][q], q))
# P2:A vs B 判得不一樣的題
A2 = {r["id"]: r for r in rows("blind", P2)}; B2 = {r["id"]: r for r in rows("trained", P2)}
flip = {}
for q in ("buy", "top"):
    val = (lambda r: r["ret"]) if q == "buy" else (lambda r: r["fr10"])
    ids = [i for i in A2 if i in B2 and A2[i]["q"] == q]
    for a, b in (("agree", "disagree"), ("disagree", "agree"), ("agree", "agree"), ("disagree", "disagree")):
        g = [A2[i] for i in ids if A2[i]["v"] == a and B2[i]["v"] == b]
        flip[f"{q}: 盲判 {a} / 訓練後 {b}"] = {"n": len(g), "hit": mean([1.0 if r["win"] else 0 for r in g]), "mean": mean([val(r) for r in g])}
    pa = [A2[i]["p"] for i in ids]; pb = [B2[i]["p"] for i in ids]
    ma, mb = mean(pa), mean(pb)
    cv = sum((x - ma) * (y - mb) for x, y in zip(pa, pb)); va = sum((x - ma) ** 2 for x in pa); vb = sum((y - mb) ** 2 for y in pb)
    flip[f"{q}: p 相關係數(盲判 vs 訓練後)"] = cv / (va * vb) ** 0.5 if va > 0 and vb > 0 else None
res["P2_flips"] = flip
for k, v in flip.items():
    print(k, v if not isinstance(v, dict) else {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()})
# P1 錯題本用的結果 vs 最後結果
diff = [i for i, o in O1.items() if o["status"] == "closed" and (OC[i].get("ret"), OC[i].get("fr10")) != (o.get("ret"), o.get("fr10"))]
res["P1_outcome_consistency"] = {"n_p1": len(O1), "n_diff": len(diff)}
print("P1 錯題本結果 vs 最後結果 不一致:", len(diff), "/", len(O1))
# 全部題目的平常(這段期間)
allr = [o for o in OC.values() if o["status"] == "closed"]
res["period_base"] = {f"{q}/{t}": {"n": len([o for o in allr if o["q"] == q and o["type"] == t]),
                                     "hit": mean([1.0 if o["win"] else 0 for o in allr if o["q"] == q and o["type"] == t]),
                                     "mean": mean([(o["ret"] if q == "buy" else o["fr10"]) for o in allr if o["q"] == q and o["type"] == t])}
                      for q in ("buy", "top") for t in ("stock", "idx")}
for seg, days in (("P1", P1), ("P2", P2)):
    rr = [o for o in allr if o["date"] in set(days)]
    res["period_base"][seg] = {q: {"n": len([o for o in rr if o["q"] == q]), "hit": mean([1.0 if o["win"] else 0 for o in rr if o["q"] == q])} for q in ("buy", "top")}
print(json.dumps(res["period_base"], ensure_ascii=False))
json.dump(res, open(os.path.join(S, "final_results.json"), "w"), ensure_ascii=False, indent=1)
