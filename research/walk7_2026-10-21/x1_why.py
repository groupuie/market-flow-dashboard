#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 事後探索(沒有預先登記):為什麼 Claude 看圖會「反著準」?
1) Claude 的 p_up、p_dn 和圖上幾個數字的相關(Spearman):5 天、20 天漲跌、離 20 / 50 日線、RSI14、60 天位置、日均波動
2) 同樣這幾個數字,單獨拿來排序時的同一天內 AUC(考題 2,000 張,以及 2021–2026 全部)
用法:python3 -I x1_why.py OUT_DIR → out/x1_why.json"""
import glob, json, os, sys
import numpy as np, pandas as pd
from scipy.stats import spearmanr
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from w5_stats import wd_auc, date_stats  # noqa: E402

OUT = sys.argv[1]
H = pd.DataFrame(json.load(open(os.path.join(OUT, "_sealed", "hidden_w7.json")))["items"])
A = pd.DataFrame([dict(it, id=str(it["id"]).zfill(4)) for f in glob.glob(os.path.join(OUT, "judge", "b*", "answers.json")) for it in json.load(open(f))["items"]])
S = pd.read_pickle(os.path.join(OUT, "out", "S7.pkl"))
S["y_buy"] = (S.buy == 1).astype(int); S["y_sell"] = (S.sell == 1).astype(int); S["y_dir"] = S.d20
J = H.merge(A[["id", "p_up", "p_dn", "buy", "sell"]].rename(columns={"buy": "buy_call", "sell": "sell_call"}), on="id").merge(S, on=["sym", "i", "date"])
F = {"5 天漲跌(z5)": "z5", "過去 20 天漲跌(w_d20)": "w_d20", "離 20 日線": "dma20", "離 50 日線": "dma50", "RSI14": "rsi14", "60 天位置": "pos60", "日均波動": "a", "過去 60 天漲跌(z60)": "r60_past"}
# 注意:S7 的 r20 / r60 欄是「之後」的報酬(答案),不是過去的;過去 60 天用 z60(÷ 波動)
J["r60_past"] = J["z60"]; S["r60_past"] = S["z60"]
R = {"Claude 機率和圖上數字的相關(Spearman,2,000 張)": {}}
for nm, c in F.items():
    R["Claude 機率和圖上數字的相關(Spearman,2,000 張)"][nm] = {"p_up": round(float(spearmanr(J.p_up, J[c], nan_policy="omit")[0]), 3), "p_dn": round(float(spearmanr(J.p_dn, J[c], nan_policy="omit")[0]), 3)}
def wd(df, score, t):
    ok = df[t].notna() & df[score].notna(); d = df[ok]; return round(wd_auc(d[score].values, d[t].values.astype(int), d.date.values), 4)
R["單一數字的同一天內 AUC(只看方向 D20;數字越大越看漲)"] = {}
T = S[(S.year >= 2021)]
for nm, c in F.items():
    R["單一數字的同一天內 AUC(只看方向 D20;數字越大越看漲)"][nm] = {"POST 考題 1,000": wd(J[J.pool == "POST"], c, "y_dir"), "2021–2026 全部": wd(T, c, "y_dir"), "POST 全部(2026-07~09)": wd(S[S.date >= "2026-07-01"], c, "y_dir")}
json.dump(R, open(os.path.join(OUT, "out", "x1_why.json"), "w"), ensure_ascii=False, indent=1)
for k, v in R.items():
    print(k)
    for a, b in v.items():
        print("  ", a, b)
