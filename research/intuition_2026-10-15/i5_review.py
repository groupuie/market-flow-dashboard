#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盤感訓練 I5:給「教練」的錯題本材料(只有 P1 = 2026-07-01 ~ 07-24;結果只用到 2026-08-24 的 K 線)

用法:python3 i5_review.py SCRATCH_DIR → SCRATCH_DIR/coach/review_P1.md
內容:P1 盲判成績、校準、偏差(各特徵區間:判讀說同意的比例 vs 實際)、經驗庫在 P1 的表現、
      歷史經驗(2010 ~ 2026-06,池子 = 2026-07-01 前已結束)的分區勝率、判錯最多的題、P1 全部題目表
"""
import gzip, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from i6_eval import evaluate, fmt, mean, auc

S = sys.argv[1]; os.makedirs(os.path.join(S, "coach"), exist_ok=True)
R = json.load(open(os.path.join(S, "registry.json")))
OC = json.load(open(os.path.join(S, "sealed", "outcomes_P1.json")))["marks"]
AN = json.load(open(os.path.join(S, "analogs.json")))
bank = [r for r in json.load(gzip.open(os.path.join(S, "bank.json.gz"), "rt", encoding="utf-8")) if r["exit_date"] < "2026-07-01"]
KV = json.load(open(os.path.join(S, "knn_validate.json")))
P1 = [d for d in sorted(R["days"]) if d <= "2026-07-24"]
BASE = {("buy", "stock"): 0.55, ("buy", "idx"): 0.75, ("top", "stock"): 0.45, ("top", "idx"): 0.33}

rows = []
for d in P1:
    P = json.load(open(R["days"][d]["pack"])); V = {m["id"]: m for m in json.load(open(os.path.join(S, "verdicts_blind", d + ".json")))["marks"]}
    for m in P["marks"]:
        o = OC.get(m["id"])
        if not o or o["status"] != "closed":
            continue
        v = V[m["id"]]; a = AN[m["id"]]
        rows.append({**{k: m.get(k) for k in ("id", "sym", "date", "q", "kind", "type", "why", "chg1", "gap", "r5", "r20", "r60", "vs50", "vs200", "pos52", "dd52", "vol20_daily", "vr", "days_since_top", "buys_20d")},
                     "spy_r20": m["market"]["SPY"]["r20"], "qqq_r5": m["market"]["QQQ"]["r5"], "v": v["v"], "p": float(v["p"]), "jwhy": v["why"],
                     "win": o["win"], "ret": o.get("ret"), "fr10": o.get("fr10"), "exit_why": o.get("exit_why"), "knn": a["hit"], "knn_base": a["base"], "knn_mean": a["mean"]})
sessions = P1
E = evaluate(rows, sessions, BASE)
L = ["# 錯題本材料:P1(2026-07-01 ~ 07-24,17 個交易日)", "",
     "- 這是給「教練」看的。題目 = 那天收盤後網站的買點 / 頂點;判讀 = 一個全新的 Claude 盲判(只看資料包)",
     "- 結果:買點題 = 照網站賣法、每邊扣 0.1% 後有沒有賺;頂點題 = 頂點隔天開盤 → 第 11 天開盤有沒有比較低(「對」= 有跌)",
     "- 結果只用到 2026-08-24 的 K 線(之後的價格,你和下一批判讀都不會知道)", ""]
for q, name in (("buy", "買點題"), ("top", "頂點題")):
    if q in E:
        o = E[q]
        L += [f"## P1 盲判成績:{name}", "", "- " + fmt(o, q), "", "| 判讀給的 p | 題數 | 平均 p | 實際對的比例 |", "|---|---:|---:|---:|"]
        L += [f"| {c['p_bin']} | {c['n']} | {100 * c['mean_p']:.0f}% | {100 * c['actual']:.0f}% |" for c in o["calibration"]]
        L += [""]

# 經驗庫在 P1
def corr(a, b):
    ma, mb = mean(a), mean(b); va = sum((x - ma) ** 2 for x in a); vb = sum((y - mb) ** 2 for y in b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) ** 0.5 if va > 0 and vb > 0 else float("nan")


L += ["## 經驗庫(最像的過去 k 個)在 P1 的表現(機械,沒有判讀)", ""]
for q in ("buy", "top"):
    Rq = [r for r in rows if r["q"] == q]
    if Rq:
        ag = [r for r in Rq if r["knn"] > r["knn_base"]]; dg = [r for r in Rq if r["knn"] <= r["knn_base"]]
        L.append(f"- {q}:AUC {auc([r['knn'] for r in Rq], [r['win'] for r in Rq]):.3f};經驗庫說「比平常好」{len(ag)} 題 → 實際對 {100 * mean([1.0 if r['win'] else 0 for r in ag]):.1f}%;"
                 f"「比平常差」{len(dg)} 題 → {100 * mean([1.0 if r['win'] else 0 for r in dg]):.1f}%;判讀的 p 和經驗庫的相關係數 {corr([r['p'] for r in Rq], [r['knn'] for r in Rq]):+.2f}")
L += ["- 經驗庫的歷史驗證(池子 = 2021 前結束的點,題目 = 2021-01 ~ 2026-06):" + ";".join(f"{k} AUC {v['auc']:.3f}(前 10% 對 {v['top10%_hit%']:.0f}% / 後 10% 對 {v['bottom10%_hit%']:.0f}%)" for k, v in KV.items()), ""]


def bucket_table(title, data, q, specs):
    L.append(f"### {title}")
    L.append("")
    L.append("| 特徵 | 區間 | 題數 | 判讀同意 | 判讀平均 p | 實際對 |" if data is rows else ("| 特徵 | 區間 | 筆數 | 對的比例 | 平均報酬 |" if q == "buy" else "| 特徵 | 區間 | 筆數 | 對的比例(10 天後有跌) | 10 天後平均漲跌 |"))
    L.append("|---|---|---:|---:|---:|---:|" if data is rows else "|---|---|---:|---:|---:|")
    for f, cuts in specs:
        for lo, hi in zip(cuts[:-1], cuts[1:]):
            g = [r for r in data if r["q"] == q and r.get(f) is not None and lo <= r[f] < hi]
            if f == "days_since_top":
                g = [r for r in data if r["q"] == q and ((r.get(f) if r.get(f) is not None else 999) >= lo) and ((r.get(f) if r.get(f) is not None else 999) < hi)]
            if len(g) < (10 if data is rows else 200):
                continue
            lab = f"{lo:g} ~ {hi:g}".replace("-1e+09", "−∞").replace("1e+09", "+∞")
            if data is rows:
                L.append(f"| {f} | {lab} | {len(g)} | {100 * mean([1.0 if r['v'] == 'agree' else 0 for r in g]):.0f}% | {100 * mean([r['p'] for r in g]):.0f}% | {100 * mean([1.0 if r['win'] else 0 for r in g]):.0f}% |")
            else:
                vv = [r["ret"] if q == "buy" else r["fr10"] for r in g]
                L.append(f"| {f} | {lab} | {len(g)} | {100 * mean([1.0 if r['win'] else 0 for r in g]):.1f}% | {100 * mean(vv):+.2f}% |")
    L.append("")


INF = 1e9
SPEC = [("vs200", [-INF, 0, 10, 25, 50, INF]), ("vs50", [-INF, -10, 0, 5, 15, INF]), ("pos52", [-INF, 20, 50, 80, INF]),
        ("r5", [-INF, -10, -5, 0, INF]), ("r20", [-INF, -15, 0, 15, INF]), ("chg1", [-INF, -5, -2, 0, INF]),
        ("vol20_daily", [-INF, 1.5, 2.5, 4, INF]), ("vr", [-INF, 0.8, 1.2, 2, INF]), ("days_since_top", [0, 4, 11, 31, INF]),
        ("spy_r20", [-INF, -5, 0, 3, INF]), ("qqq_r5", [-INF, -3, 0, 3, INF])]
for r in bank:
    r["spy_r20"] = r["SPY_r20"]; r["qqq_r5"] = r["QQQ_r5"]
L += ["## 判讀的偏差:P1 各區間「判讀說同意的比例」vs「實際對的比例」(10 題以上才列)", ""]
bucket_table("買點題(個股 + 指數)", rows, "buy", SPEC)
bucket_table("頂點題", rows, "top", SPEC)
L += ["## 歷史經驗:2010-01 ~ 2026-06(池子 = 2026-07-01 前已結束;個股;200 筆以上才列)", ""]
bucket_table("買點題(個股):對 = 扣成本後賺", [r for r in bank if r["type"] == "stock"], "buy", SPEC + [("buys_20d", [0, 1, 2, 3, INF])])
bucket_table("頂點題(個股):對 = 10 天後比較低", [r for r in bank if r["type"] == "stock"], "top", SPEC)
for kd in ("底", "回"):
    g = [r for r in bank if r["q"] == "buy" and r["type"] == "stock" and r["kind"] == kd]
    L.append(f"- 個股買點 {kd}:{len(g)} 筆,對 {100 * mean([1.0 if r['win'] else 0 for r in g]):.1f}%,平均 {100 * mean([r['ret'] for r in g]):+.2f}%,碰停損 {100 * mean([1.0 if r.get('exit_why') == '停損' else 0 for r in g]):.1f}%")
g = [r for r in bank if r["q"] == "buy" and r["type"] == "idx"]
L.append(f"- 指數買點(SPY/QQQ):{len(g)} 筆,對 {100 * mean([1.0 if r['win'] else 0 for r in g]):.1f}%,平均 {100 * mean([r['ret'] for r in g]):+.2f}%")
L.append("")

# 判錯最多的
def line(r):
    out = f"{r['date']} {r['sym']} {r['q']}/{r['kind']} p={r['p']:.2f} {r['v']} → {'對' if r['win'] else '錯'}"
    out += f"({'報酬' if r['q'] == 'buy' else '10天'} {100 * (r['ret'] if r['q'] == 'buy' else r['fr10']):+.1f}%{(' ' + r['exit_why']) if r.get('exit_why') else ''})"
    out += f" | vs50 {r['vs50']} vs200 {r['vs200']} pos52 {r['pos52']} r5 {r['r5']} r20 {r['r20']} vol {r['vol20_daily']} vr {r['vr']} dst {r['days_since_top']} SPYr20 {r['spy_r20']} | 經驗庫 {100 * r['knn']:.0f}%(平常 {100 * r['knn_base']:.0f}%) | 判讀理由:{r['jwhy']}"
    return out


for q in ("buy", "top"):
    Rq = [r for r in rows if r["q"] == q]
    L += [f"## 最有信心卻錯的({q},p 最高的錯題 12 個)", ""] + ["- " + line(r) for r in sorted([r for r in Rq if not r["win"]], key=lambda r: -r["p"])[:12]] + [""]
    L += [f"## 最沒信心卻對的({q},p 最低的對題 12 個)", ""] + ["- " + line(r) for r in sorted([r for r in Rq if r["win"]], key=lambda r: r["p"])[:12]] + [""]
L += ["## P1 全部題目(日期 股票 題型/種類 判讀 → 結果 | 特徵 | 經驗庫 | 判讀理由)", ""] + ["- " + line(r) for r in sorted(rows, key=lambda r: (r["date"], r["q"], r["sym"]))]
open(os.path.join(S, "coach", "review_P1.md"), "w").write("\n".join(L) + "\n")
json.dump({q: E[q] for q in E}, open(os.path.join(S, "coach", "p1_eval.json"), "w"), ensure_ascii=False, indent=1)
print("\n".join(L[:40]))
