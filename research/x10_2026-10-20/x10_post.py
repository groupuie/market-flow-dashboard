#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""x10 揭曉之後的補充(事後才寫;不改對錯 —— 對錯照 x10.py 與 result.json)
用法:python3 -I x10_post.py BARS_LONG.json.gz judge/answers.json
輸出:
  show.json  每張:之前 60 根 + 之後 60 根(今收 = 100)、四條線、先碰到哪條線、20 / 60 天內最高最低在第幾天(給網頁畫圖)
  null.json  「圖沒有資訊」時的成績分布:答案照我鎖定的,結果從 2 萬個候選日子(和 base.json 同一批)裡隨機抽 → 20 句會對幾句
"""
import gzip, json, os, random, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from x10 import atr, ok, outcome, H, AFTER, LO_DATE  # noqa: E402

D = json.load(gzip.open(sys.argv[1])); B, ETF = D["bars"], set(D["etf"]); A = json.load(open(sys.argv[2]))["ans"]
hid = json.load(open(os.path.join(HERE, "hidden.json")))["items"]; R = {r["n"]: r for r in json.load(open(os.path.join(HERE, "result.json")))["items"]}
NAME = {"LIN": "Linde", "ADP": "Automatic Data Processing", "TER": "Teradyne", "AMAT": "Applied Materials", "HON": "Honeywell", "ROP": "Roper Technologies",
        "MAR": "Marriott", "FTNT": "Fortinet", "XEL": "Xcel Energy", "LRCX": "Lam Research"}
LEV = {("buy", "先漲一段"): 2.0, ("buy", "先跌一段"): -1.5, ("sell", "先跌一段"): -2.0, ("sell", "先漲一段"): 1.5}


def grade(call, side, res):
    if side == "buy":
        return {"先漲一段": "對", "先跌一段": "錯", "都沒到": "平"}[res] if call == "買點" else {"先漲一段": "錯", "先跌一段": "對", "都沒到": "平"}[res]
    return {"先跌一段": "對", "先漲一段": "錯", "都沒到": "平"}[res] if call == "賣點" else {"先跌一段": "錯", "先漲一段": "對", "都沒到": "平"}[res]


# 1) 網頁用的每張資料
show = []
for it in hid:
    b = B[it["sym"]]; i = it["i"]; C = b[i][4]; a = atr(b, i); res, st = outcome(b, i); r = R[it["n"]]; ans = A[str(it["n"])]
    assert res["buy"] == r["買方結果"] and res["sell"] == r["賣方結果"], it
    assert grade(ans["買方"], "buy", res["buy"][0]) == r["買方對錯"] and grade(ans["賣方"], "sell", res["sell"][0]) == r["賣方對錯"], it
    W = b[i - 59:i + AFTER + 1]
    ohlc = [[round(v / C * 100, 2) for v in x[1:5]] for x in W]
    post20 = b[i + 1:i + H + 1]; post60 = b[i + 1:i + AFTER + 1]
    hi20 = max(range(H), key=lambda k: post20[k][2]); lo20 = min(range(H), key=lambda k: post20[k][3])
    hi60 = max(range(AFTER), key=lambda k: post60[k][2]); lo60 = min(range(AFTER), key=lambda k: post60[k][3])
    hit = {s: ({"day": res[s][1], "lev": round(100 * (1 + LEV[(s, res[s][0])] * a), 2)} if res[s][0] != "都沒到" else None) for s in ("buy", "sell")}
    show.append({"n": it["n"], "sym": it["sym"], "name": NAME[it["sym"]], "date": it["date"], "end20": b[i + H][0], "end60": b[i + AFTER][0],
                 "atr": round(100 * a, 2), "close": round(C, 2), "ohlc": ohlc, "dates": [x[0] for x in W], "x0": -59,
                 "lines": {"buy_up": round(100 * (1 + 2 * a), 2), "buy_dn": round(100 * (1 - 1.5 * a), 2), "sell_dn": round(100 * (1 - 2 * a), 2), "sell_up": round(100 * (1 + 1.5 * a), 2)},
                 "res": res, "hit": hit, "grade": {"buy": r["買方對錯"], "sell": r["賣方對錯"]},
                 "ret20": st["20天後"], "ret60": st["60天後"],
                 "hi20": [hi20 + 1, round(100 * (post20[hi20][2] / C - 1), 1)], "lo20": [lo20 + 1, round(100 * (post20[lo20][3] / C - 1), 1)],
                 "hi60": [hi60 + 1, round(100 * (post60[hi60][2] / C - 1), 1)], "lo60": [lo60 + 1, round(100 * (post60[lo60][3] / C - 1), 1)],
                 "call": ans})
json.dump(show, open(os.path.join(HERE, "show.json"), "w"), ensure_ascii=False, separators=(",", ":"))
for s in show:
    print(s["n"], s["sym"], s["date"], "買", s["res"]["buy"], s["grade"]["buy"], "賣", s["res"]["sell"], s["grade"]["sell"], "20天高低", s["hi20"], s["lo20"], "60天高低", s["hi60"], s["lo60"], s["ret20"], s["ret60"])

# 2) 「圖沒有資訊」時的成績分布(和 base.json 同一批 2 萬個候選日子)
pool = [(s, i) for s in sorted(B) if s not in ETF for i in range(len(B[s])) if B[s][i][0] >= LO_DATE and ok(B[s], i)]
assert len(pool) == 218073, len(pool)
random.Random(json.load(open(os.path.join(HERE, "hidden.json")))["seed"]).shuffle(pool)   # x10.py sample 先洗牌、再抽 2 萬個算基準 → 照同樣順序
J = {}
for s, i in random.Random(1).sample(pool, 20000):
    res, _ = outcome(B[s], i); k = (res["buy"][0], res["sell"][0]); J[k] = J.get(k, 0) + 1
tot = sum(J.values()); base_chk = {}
for (rb, rs), v in J.items():
    base_chk.setdefault("buy", {}).setdefault(rb, 0); base_chk["buy"][rb] += v; base_chk.setdefault("sell", {}).setdefault(rs, 0); base_chk["sell"][rs] += v
base_chk = {side: {k: round(100 * v / tot, 1) for k, v in d.items()} for side, d in base_chk.items()}
assert base_chk == json.load(open(os.path.join(HERE, "base.json"))), base_chk


def dist(calls):
    """calls = [(買方判斷, 賣方判斷)] × 張數 → 每一邊、合計「對」的句數分布"""
    out = {}
    for which in ("買方", "賣方", "合計"):
        P = np.array([1.0])
        for cb, cs in calls:
            p = np.zeros(3)
            for (rb, rs), v in J.items():
                c = (which != "賣方") * (grade(cb, "buy", rb) == "對") + (which != "買方") * (grade(cs, "sell", rs) == "對"); p[c] += v / tot
            P = np.convolve(P, p)
        P = P[:len(P)] if which == "合計" else P[:len(calls) + 1]
        cdf = np.cumsum(P); mean = float((np.arange(len(P)) * P).sum())
        out[which] = {"平均": round(mean, 2), "90% 範圍": [int(np.searchsorted(cdf, 0.05)), int(np.searchsorted(cdf, 0.95))], "分布%": [round(100 * float(x), 2) for x in P]}
    return out


calls = [(A[str(k)]["買方"], A[str(k)]["賣方"]) for k in range(1, 11)]
obs = {"買方": sum(1 for s in show if s["grade"]["buy"] == "對"), "賣方": sum(1 for s in show if s["grade"]["sell"] == "對")}; obs["合計"] = obs["買方"] + obs["賣方"]
N0 = dist(calls)
for k in obs:
    P = N0[k]["分布%"]; N0[k]["實際"] = obs[k]; N0[k]["P(≤ 實際)%"] = round(sum(P[:obs[k] + 1]), 1); N0[k]["P(≥ 實際)%"] = round(sum(P[obs[k]:]), 1)
lazy = [("還要再等,低點還沒到", "還要再等,高點還沒到")] * 10
lazy_obs = sum(grade(c[0], "buy", s["res"]["buy"][0]) == "對" for c, s in zip(lazy, show)) + sum(grade(c[1], "sell", s["res"]["sell"][0]) == "對" for c, s in zip(lazy, show))
coin = {"買方": 0.0, "賣方": 0.0}
for s in show:   # 每一句都丟銅板(一半說買點 / 賣點、一半說還要再等),結果照實際
    coin["買方"] += 0.5 * (s["res"]["buy"][0] != "都沒到"); coin["賣方"] += 0.5 * (s["res"]["sell"][0] != "都沒到")
NUL = {"說明": "答案照鎖定的;每張的結果從 2 萬個候選日子(與 base.json 同一批)隨機抽,張與張獨立;同一張的買方、賣方結果一起抽(兩邊高度相關)",
       "候選日子": len(pool), "抽樣": tot, "聯合分布(買方結果, 賣方結果)%": {f"{k[0]} / {k[1]}": round(100 * v / tot, 2) for k, v in sorted(J.items(), key=lambda x: -x[1])},
       "我的答案": N0, "每張都說「兩邊都還要再等」在這 10 張的成績": lazy_obs, "每句丟銅板、結果照實際的平均": round(coin["買方"] + coin["賣方"], 2)}
json.dump(NUL, open(os.path.join(HERE, "null.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in NUL.items() if k != "我的答案"}, ensure_ascii=False))
for k, v in N0.items():
    print(k, {kk: vv for kk, vv in v.items() if kk != "分布%"})
