#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk5 型態書:只用「答案在 2026-06-30 以前揭曉」的情境(2018-01-02 起,約 23 萬個),把買點規律濃縮成一棵淺樹(深度 3、每條至少 5,000 例)
- 深度 3 是在 2021–2025 逐年往前(只用訓練年份)比較深度 2 / 3 / 4 後選的(x1_book_dev.py:0.512 / 0.530 / 0.517;M2 0.533)
- 輸出:book.json(規則、各年、2026 上半年驗證)+ book.md(給判讀者看的白話版)+ exam.json(考題:walk4 第 119–210 回合裡從來沒有人看過的 600 張考試期圖)
用法:python3 -I w5_book.py SCEN.pkl WALK4_DIR OUT_DIR"""
import json, os, sys
import numpy as np, pandas as pd
from sklearn.tree import DecisionTreeClassifier

SC, W4, OD = sys.argv[1], sys.argv[2], sys.argv[3]; os.makedirs(OD, exist_ok=True)
S = pd.read_pickle(SC)
S["volc"] = S.atr20_60; S["atr"] = 100 * S.a; S["q_atr"] = 100 * S.q_a; S["q_vs50"] = S.q_dma50 * S.q_a * 100; S["q_vs200"] = S.q_dma200 * S.q_a * 100
S["q_pos60"] = 100 * S.q_pos60; S["hi_days"] = S.dsh250 * 250; S["rng250"] = S.rw250 * S.a * 100; S["vtrend"] = S.vr20_60
S["d5"] = 100 * (np.exp(S.r5) - 1); S["d20"] = 100 * (np.exp(S.r20) - 1); S["vs20"] = S.w_vs20; S["vs50"] = S.w_vs50; S["rs20p"] = 100 * S.rs20
FB = ["volc", "atr", "q_atr", "q_vs50", "q_vs200", "q_pos60", "hi_days", "rng250", "vtrend", "d5", "d20", "vs20", "vs50", "rs20p"]
NAME = {"volc": "波動收縮比(近 20 天平均波動 ÷ 近 60 天;< 1 = 最近變安靜)", "atr": "這檔日均波動 %", "q_atr": "大盤(QQQ)日均波動 %",
        "q_vs50": "大盤離 50 日線 %", "q_vs200": "大盤離 200 日線 %", "q_pos60": "大盤在近 60 天高低區間的位置(0 最低、100 最高)",
        "hi_days": "離近一年最高點幾個交易日(0 = 今天創一年新高)", "rng250": "近一年最高 ÷ 最低 − 1(%)", "vtrend": "量的趨勢(近 20 天均量 ÷ 再前 60 天均量)",
        "d5": "近 5 天漲跌 %", "d20": "近 20 天漲跌 %", "vs20": "離 20 日線 %", "vs50": "離 50 日線 %", "rs20p": "近 20 天比大盤強多少(百分點)"}
DIG = {"volc": 2, "atr": 2, "q_atr": 2, "q_vs50": 1, "q_vs200": 1, "q_pos60": 0, "hi_days": 0, "rng250": 0, "vtrend": 2, "d5": 1, "d20": 1, "vs20": 1, "vs50": 1, "rs20p": 1}
TR = S[S.T1b.notna() & (S.date >= "2018-01-02") & (S.end10 <= "2026-06-30")].copy()
X = TR[FB].fillna(-999).values
tree = DecisionTreeClassifier(max_depth=3, min_samples_leaf=5000, random_state=1).fit(X, TR.T1b.values)
T = tree.tree_


def paths(node=0, cond=()):
    if T.children_left[node] == -1:
        return [(node, cond)]
    f, th = FB[T.feature[node]], float(T.threshold[node])
    return paths(T.children_left[node], cond + ((f, "≤", th),)) + paths(T.children_right[node], cond + ((f, ">", th),))


def fmt(f, op, th):
    if th < -900:
        return f"{NAME[f]}{'沒有資料' if op == '≤' else '有資料'}"
    return f"{NAME[f]} {op} {round(th, DIG[f]) if DIG[f] else int(round(th))}"


leaf_of = tree.apply(X); TR["leaf"] = leaf_of
P = paths(); order = sorted(P, key=lambda p: -TR.T1b[TR.leaf == p[0]].mean())
book, ids = [], {}
for k, (node, cond) in enumerate(order):
    g = TR[TR.leaf == node]; rid = f"B{k + 1}"; ids[node] = rid
    yr = {y: round(100 * float(h.T1b.mean()), 1) for y, h in g.groupby(g.date.str[:4])}
    h26 = g[g.date >= "2026-01-01"]
    book.append({"id": rid, "條件": [fmt(*c) for c in cond], "raw": [[c[0], c[1], c[2]] for c in cond], "例數": len(g), "買對%": round(100 * float(g.T1b.mean()), 1),
                 "漲一段%(T2b)": round(100 * float(g.T2b.mean()), 1), "賣對%": round(100 * float(g.T1s.mean()), 1), "各年買對%": yr,
                 "2026 上半年": [len(h26), round(100 * float(h26.T1b.mean()), 1) if len(h26) else None]})
base = round(100 * float(TR.T1b.mean()), 1)
# 一維摘要:每個特徵分五等分的買對%
one = {}
for f in FB:
    v = TR[f]; ok = v.notna()
    q = pd.qcut(v[ok], 5, duplicates="drop")
    one[f] = [[f"{iv.left:.{DIG[f]}f} ~ {iv.right:.{DIG[f]}f}", int(n), round(100 * float(m), 1)] for iv, (n, m) in TR[ok].groupby(q, observed=True).T1b.agg(["size", "mean"]).iterrows()]
json.dump({"訓練例數": len(TR), "整體買對%": base, "規則": book, "一維(五等分:區間、例數、買對%)": one, "特徵": FB, "名稱": NAME}, open(os.path.join(OD, "book.json"), "w"), ensure_ascii=False, indent=1)
# 白話版
L = [f"# 型態書(買點)", "", f"來源:2018-01 ~ 2026-06 的 {len(TR):,} 個「某檔某天」(Nasdaq-100 + 主要 ETF,127 檔),答案都在 2026-06-30 以前揭曉。整體隨便買,10 天內「買對」(先漲 2×atr20、沒先跌 1.5×atr20)= **{base}%**。",
     "電腦用約 70 個圖形特徵學到的規律,主要來自:**這檔最近的波動是變大還是變小、大盤自己的波動和位置、離一年高點多久** — 不是經典型態的名字。下面是把它濃縮成 8 條規則(每條至少 5,000 例);每一張圖一定剛好落在其中一條。", "",
     "| 規則 | 條件(全部都要成立) | 例數 | 買對% | 各年範圍 | 2026 上半年 |", "|---|---|---:|---:|---|---|"]
for b in book:
    ys = list(b["各年買對%"].values())
    L.append(f"| {b['id']} | {';'.join(b['條件'])} | {b['例數']:,} | **{b['買對%']}** | {min(ys)}–{max(ys)} | {b['2026 上半年'][1]}%({b['2026 上半年'][0]} 例) |")
L += ["", "**單一特徵的規律**(五等分,每格約 4.7 萬例;數字是買對%):", ""]
for f in ("volc", "q_atr", "q_pos60", "q_vs50", "hi_days", "atr", "vtrend", "d5", "vs20", "rs20p"):
    L.append(f"- {NAME[f]}:" + ";".join(f"{a}→{r}%" for a, n, r in one[f]))
L += ["", "**賣點**:用同樣的方法,逐年往前驗證找不到穩定的賣點規律(AUC 0.51,區間含 0.5),所以沒有賣點規則;ps 請照圖給你自己的判斷,隨便賣約 28% 會賣對。"]
open(os.path.join(OD, "book.md"), "w").write("\n".join(L) + "\n")
# 考題:walk4 第 119–210 回合裡的考試期圖(沒有任何判讀者看過)
S4 = json.load(open(os.path.join(W4, "data", "sample.json"))); IT = {r["id"]: r for r in S4["items"]}
ex = [IT[i] for k in range(118, len(S4["rounds"])) for i in S4["rounds"][k] if IT[i]["phase"] == "test"]
idx = S.set_index(["sym", "i"])
rows = []
for it in ex:
    r = idx.loc[(it["sym"], it["idx"])]
    x = np.array([[(-999 if pd.isna(r[f]) else float(r[f])) for f in FB]])
    lf = ids[int(tree.apply(x)[0])]
    rows.append({"id": it["id"], "sym": it["sym"], "i": it["idx"], "date": it["date"], "kind": it["kind"], "rule": lf, "rule_rate": next(b["買對%"] for b in book if b["id"] == lf),
                 "nums": {f: (None if pd.isna(r[f]) else round(float(r[f]), DIG[f])) for f in FB}, "atr20": it["feat"]["atr20"],
                 "y_b": 1 if it["buy"]["r"] == "對" else 0, "y_s": 1 if it["sell"]["r"] == "對" else 0})
json.dump(rows, open(os.path.join(OD, "exam.json"), "w"), ensure_ascii=False)
print("訓練例數", len(TR), "整體買對%", base)
for b in book:
    print(b["id"], b["例數"], b["買對%"], b["2026 上半年"], " ; ".join(b["條件"]))
import collections
print("考題", len(rows), collections.Counter(r["rule"] for r in rows))
