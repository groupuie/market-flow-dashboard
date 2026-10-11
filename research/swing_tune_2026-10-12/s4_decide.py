# 照 p0_prereg.md §6 的 D1–D4 機械判定(讀 s4_result.json)→ s4_decision.json + 給網站的數字 site_numbers.json
import os, json
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "s4_result.json")))
B, F, T, P, M = R["bottoms"], R["filters"], R["tops"], R["pivots"], R["mountains"]
FOCUS = ["IDX", "MAG7", "NDX", "FLOW"]
NMIN = {"IDX": 50, "MAG7": 150, "NDX": 150, "FLOW": 150}
log = []; dec = {}
def b(k, g, pk, x="XT"): return B.get(f"{k}|{x}|{g}|{pk}")

# ---- D1 ----
d1 = {}
for k in ["B1r", "B1c", "B2", "B2n", "B3", "B4", "B6"]:
    post = []; pre = []
    for g in FOCUS:
        c, z = b(k, g, "後段"), b("B0", g, "後段")
        post.append(bool(c and z and c["n"] >= NMIN[g] and c["win"] >= z["win"] and c["avg"] >= z["avg"]))
        c, z = b(k, g, "前段"), b("B0", g, "前段")
        pre.append(bool(c and z and c["win"] >= z["win"] and c["avg"] >= z["avg"]))
    ok = sum(post) >= 3 and sum(pre) >= 2
    d1[k] = {"後段": dict(zip(FOCUS, post)), "前段": dict(zip(FOCUS, pre)), "pass": ok}
    log.append(f"D1 {k}: 後段 {sum(post)}/4 {dict(zip(FOCUS, post))} 前段 {sum(pre)}/4 → {'通過' if ok else '不通過'}")
dec["D1"] = d1

# ---- D2 ----
d2 = {}
NS = {"IDX": 30, "MAG7": 100, "NDX": 100, "FLOW": 100, "ALL": 100}
for f in ["F_VIX", "F_BR", "F_CTA", "F_DIX", "F_GEX", "F_COR"]:
    for g in ["IDX", "MAG7", "NDX", "FLOW", "ALL"]:
        r = {}
        for pk in ("前段", "後段"):
            s_, w_ = F.get(f"{f}+|XT|{g}|{pk}"), F.get(f"{f}-|XT|{g}|{pk}")
            r[pk] = (s_["win"] - w_["win"], s_["n"]) if s_ and w_ else (None, 0)
        ok = all(r[pk][0] is not None and r[pk][0] >= 5 and r[pk][1] >= NS[g] for pk in r)
        d2[f"{f}|{g}"] = {"前段差": r["前段"][0], "前段強n": r["前段"][1], "後段差": r["後段"][0], "後段強n": r["後段"][1], "pass": ok}
passed = {k: v for k, v in d2.items() if v["pass"]}
best = max(passed.items(), key=lambda kv: kv[1]["後段差"])[0] if passed else None
dec["D2"] = {"all": d2, "passed": list(passed), "chosen": best}
log.append(f"D2 通過:{list(passed)} → 只用後段差最大:{best}")

# ---- D3 ----
def s10(k, g, pk): v = T.get(f"{k}|{g}|{pk}"); return v and v["s10"]
w3 = 0; det = {}
for g in FOCUS:
    ok = all((s10("T4", g, pk) or 0) - (s10("BASE", g, pk) or 0) > (s10("T0", g, pk) or 0) - (s10("BASE", g, pk) or 0) for pk in ("前段", "後段"))
    det[g] = ok; w3 += ok
r4 = P.get("T4|recall|ALL|全期"); r0 = P.get("T0|recall|ALL|全期")
keep = r4[0] / r0[0] if r4 and r0 and r0[0] else 0
dec["D3"] = {"groups": det, "recall_ratio": round(keep, 2), "pass": w3 >= 3 and keep >= 0.4}
log.append(f"D3 T4 比 T0 好的組:{det} 命中率保留 {keep:.0%} → {'通過' if dec['D3']['pass'] else '不通過'}")

# ---- D4 ----
d4 = {}
for k in ("T2", "T3"):
    ok = True; det = {}
    for g in ("MAG7", "NDX", "FLOW"):
        for pk in ("前段", "後段"):
            m = M.get(f"{k}|{g}|{pk}"); t = T.get(f"{k}|{g}|{pk}"); bs = T.get(f"BASE|{g}|{pk}")
            c = bool(m and t and bs and m["median"] >= 40 and t["s20"] - bs["s20"] > 0)
            det[f"{g}|{pk}"] = (m and m["median"], t and bs and round(t["s20"] - bs["s20"], 1), c); ok &= c
    d4[k] = {"detail": det, "pass": ok}
    log.append(f"D4 {k}:{'通過' if ok else '不通過'} {det}")
dec["D4"] = d4
json.dump(dec, open(os.path.join(HERE, "s4_decision.json"), "w"), ensure_ascii=False, indent=1)
print("\n".join(log))

# ---- 給網站的數字(全期 2010–2026-07;XT = 底買、下一個頂賣、40 根內沒頂就第 40 根賣)----
def r(k, g, x="XT", sec=B): v = sec.get(f"{k}|{x}|{g}|全期"); return v
site = {"note": "全期 2010-01~2026-07;隔天開盤成交;來回成本 0.2%;XT=底買→下一個頂賣(40 根內沒頂就第 40 根賣);trap=中途跌 ≥10%(IDX ≥5%)"}
for g in ("IDX", "MAG7", "NDX", "ALL"):
    z, bs, b2 = r("B0", g), r("BASE", g), r("B2", g)
    site[g] = {"b0": [z["win"], z["avg"], z["trap"]], "base": [bs["win"], bs["avg"]], "b2": [b2["win"], b2["avg"], b2["trap"]],
               "t0_s10": T[f"T0|{g}|全期"]["s10"], "base_s10": T[f"BASE|{g}|全期"]["s10"], "mtn": M.get(f"T0|{g}|全期")}
    if g != "IDX":
        sp, wk = F.get(f"F_CTA+|XT|{g}|全期"), F.get(f"F_CTA-|XT|{g}|全期")
        site[g]["cta"] = [sp["win"], sp["avg"], sp["n"], wk["win"], wk["avg"], wk["n"]]
json.dump(site, open(os.path.join(HERE, "site_numbers.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(site, ensure_ascii=False, indent=1))
