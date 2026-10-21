#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 事後描述:Claude 的 p_up / p_dn 分組 → 實際比例;和電腦 M2 的相關。用法:python3 -I x2_calib.py OUT_DIR → out/x2_calib.json"""
import glob, json, os, sys
import numpy as np, pandas as pd
from scipy.stats import spearmanr
OUT = sys.argv[1]
H = pd.DataFrame(json.load(open(os.path.join(OUT, "_sealed", "hidden_w7.json")))["items"])
A = pd.DataFrame([dict(it, id=str(it["id"]).zfill(4)) for f in glob.glob(os.path.join(OUT, "judge", "b*", "answers.json")) for it in json.load(open(f))["items"]])
S = pd.read_pickle(os.path.join(OUT, "out", "S7.pkl"))[["sym", "i", "date", "buy", "sell", "d20", "r20"]]
J = H.merge(A[["id", "p_up", "p_dn"]], on="id").merge(S.reset_index().rename(columns={"index": "row"}), on=["sym", "i", "date"])
R = {}
for pool in ("POST", "PRE", "全部"):
    D = J if pool == "全部" else J[J.pool == pool]
    out = {}
    for lab, lo, hi in (("p_up ≤ 40", 0, 40), ("41–43", 41, 43), ("44–46", 44, 46), ("47–49", 47, 49), ("≥ 50", 50, 100)):
        k = D[(D.p_up >= lo) & (D.p_up <= hi)]
        out[lab] = {"張數": int(len(k)), "實際先漲一段 %": round(100 * float((k.buy == 1).mean()), 1) if len(k) else None, "20 天平均報酬 %": round(100 * float(k.r20.mean()), 2) if len(k) else None}
    R[pool + " 買方"] = out
P = pd.read_pickle(os.path.join(OUT, "out", "pred_M2_real.pkl")); E = J[J.row.isin(P.index)]
R["Claude p_up 和 M2 p_buy 的相關(Spearman)"] = round(float(spearmanr(E.p_up, P.loc[E.row, "p_buy"].values)[0]), 3)
R["Claude p_up 和 M2 p_dir 的相關(Spearman)"] = round(float(spearmanr(E.p_up, P.loc[E.row, "p_dir"].values)[0]), 3)
R["p_up 的分布"] = {"平均": round(float(J.p_up.mean()), 1), "標準差": round(float(J.p_up.std()), 1), "最小": float(J.p_up.min()), "最大": float(J.p_up.max())}
json.dump(R, open(os.path.join(OUT, "out", "x2_calib.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(R, ensure_ascii=False, indent=0))
