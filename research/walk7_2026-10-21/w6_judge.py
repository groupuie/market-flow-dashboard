#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 W6:Claude 看圖(2,000 張)的成績 —— 答案鎖定之後才跑
主要(H1):POST(2026-07-01 起,Claude 訓練資料之後)1,000 張,B1 + B2 合併:p_up 對「買方先漲一段」的同一天內 AUC > 0.5
          → 同一天內打亂的置換檢定(10,000 次),單邊 p < 0.025 才算成立
次要:H1s = 同樣做法看 p_dn 對「賣方先跌一段」;H2 = PRE 1,000 張的 AUC(月區塊重抽);H3 = B2 − B1;H4 = 和電腦方法(同一批列)比
另外:「買點 / 再等」「賣點 / 再等」的實際比例;認得出時期的張數;只看方向(D20)
用法:python3 -I w6_judge.py OUT_DIR → out/judge_result.json"""
import glob, hashlib, json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from w5_stats import auc, wd_auc, date_stats, boot_month, boot_month_pooled, perm_within_date  # noqa: E402

OUT = sys.argv[1]
H = json.load(open(os.path.join(OUT, "_sealed", "hidden_w7.json"))); items = pd.DataFrame(H["items"])
A = []
for f in sorted(glob.glob(os.path.join(OUT, "judge", "b*", "answers.json"))):
    j = json.load(open(f))
    for it in j["items"]:
        A.append({"id": str(it["id"]).zfill(4), "buy_call": it["buy"], "p_up": float(it["p_up"]), "sell_call": it["sell"], "p_dn": float(it["p_dn"]), "rec": it.get("rec", ""), "why": it.get("why", "")})
A = pd.DataFrame(A).drop_duplicates("id"); J = items.merge(A, on="id", how="left")
S = pd.read_pickle(os.path.join(OUT, "out", "S7.pkl"))[["sym", "i", "date", "buy", "sell", "d20", "r20", "a", "in_sp", "dv_rank"]]
J = J.merge(S.reset_index().rename(columns={"index": "row"}), on=["sym", "i", "date"], how="left")
J["y_buy"] = (J.buy == 1).astype(int); J["y_sell"] = (J.sell == 1).astype(int)
R = {"答案數": int(J.p_up.notna().sum()), "缺": sorted(J.id[J.p_up.isna()].tolist())}
J = J[J.p_up.notna()]


def summ(D, score, tgt, within):
    y = D[tgt].values.astype(float); ok = ~np.isnan(y); s = D[score].values[ok]; y = y[ok].astype(int); d = D.date.values[ok]
    o = {"n": int(len(y)), "AUC": round(auc(s, y), 4)}
    if within:
        obs, p = perm_within_date(s, y, d); g = date_stats(s, y, d); b = boot_month(g, 2000) if g.index.str[:7].nunique() > 2 else None
        o.update({"同一天內 AUC": round(obs, 4), "置換檢定 單邊 p": round(p, 4), "天數": int(len(g))})
        # 以「天」為單位的重抽區間
        rng = np.random.default_rng(5); U, W = g.U.values, g.w.values; bs = []
        for _ in range(2000):
            k = rng.integers(0, len(g), len(g)); bs.append(U[k].sum() / W[k].sum())
        o["同一天內 95%(以天重抽)"] = [round(float(np.quantile(bs, 0.025)), 4), round(float(np.quantile(bs, 0.975)), 4)]
    else:
        b = boot_month_pooled(s, y, d, 2000); o.update({"95%(月區塊)": [round(float(np.quantile(b, 0.025)), 4), round(float(np.quantile(b, 0.975)), 4)], "單邊 p(≤ 0.5)": round(float((b <= 0.5).mean()), 4)})
    return o


def calls(D):
    o = {}
    for side, call, yv, lab in (("買方", "buy_call", "y_buy", "買點"), ("賣方", "sell_call", "y_sell", "賣點")):
        k = D[call] == lab
        o[side] = {f"說{lab}": int(k.sum()), f"{lab}時實際 %": round(100 * float(D.loc[k, yv].mean()), 1) if k.any() else None,
                   "說再等": int((~k).sum()), "再等時實際 %": round(100 * float(D.loc[~k, yv].mean()), 1) if (~k).any() else None}
    return o


for pool in ("POST", "PRE"):
    D = J[J.pool == pool]; within = pool == "POST"; R[pool] = {}
    for var in ("全部", "B1", "B2"):
        E = D if var == "全部" else D[D.variant == var]
        R[pool][var] = {"買方 p_up → 先漲一段": summ(E, "p_up", "y_buy", within), "賣方 p_dn → 先跌一段": summ(E, "p_dn", "y_sell", within),
                        "只看方向 p_up → D20": summ(E, "p_up", "d20", within), "判斷": calls(E), "平均 p_up": round(float(E.p_up.mean()), 1), "平均 p_dn": round(float(E.p_dn.mean()), 1)}
    R[pool]["認得時期(rec 不是空的)"] = int((D.rec.fillna("").str.strip() != "").sum())
    nr = D[D.rec.fillna("").str.strip() == ""]
    R[pool]["不算認得的"] = {"買方": summ(nr, "p_up", "y_buy", within), "賣方": summ(nr, "p_dn", "y_sell", within)}
# B2 − B1(合併 PRE + POST;以天為單位重抽)
rng = np.random.default_rng(11); d1, d2 = J[J.variant == "B1"], J[J.variant == "B2"]; diff = []
for _ in range(2000):
    a1 = d1.sample(len(d1), replace=True, random_state=int(rng.integers(1e9))); a2 = d2.sample(len(d2), replace=True, random_state=int(rng.integers(1e9)))
    diff.append(auc(a2.p_up, a2.y_buy) - auc(a1.p_up, a1.y_buy))
R["H3 B2 − B1 買方 AUC"] = {"差": round(auc(d2.p_up, d2.y_buy) - auc(d1.p_up, d1.y_buy), 4), "95%": [round(float(np.quantile(diff, 0.025)), 4), round(float(np.quantile(diff, 0.975)), 4)]}
# 和電腦方法比(同一批列)
R["H4 電腦方法(同一批列)"] = {}
for m in ("M1", "M2", "K1", "N1"):
    p = os.path.join(OUT, "out", f"pred_{m}_real.pkl")
    if not os.path.exists(p):
        continue
    P = pd.read_pickle(p); E = J[J.row.isin(P.index)].copy(); E["m_buy"] = P.loc[E.row, "p_buy"].values; E["m_sell"] = P.loc[E.row, "p_sell"].values
    o = {}
    for pool in ("POST", "PRE"):
        F = E[E.pool == pool]
        if len(F) < 100:
            continue
        o[pool] = {"列數": int(len(F)), "電腦 買方": summ(F, "m_buy", "y_buy", pool == "POST"), "電腦 賣方": summ(F, "m_sell", "y_sell", pool == "POST"),
                   "Claude 買方(同一批)": round(auc(F.p_up, F.y_buy), 4)}
    R["H4 電腦方法(同一批列)"][m] = o
R["答案檔 SHA-256"] = {os.path.basename(os.path.dirname(f)): hashlib.sha256(open(f, "rb").read()).hexdigest()[:16] for f in sorted(glob.glob(os.path.join(OUT, "judge", "b*", "answers.json")))}
json.dump(R, open(os.path.join(OUT, "out", "judge_result.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: R[k] for k in ("答案數",)}, ensure_ascii=False))
for pool in ("POST", "PRE"):
    print(pool, json.dumps(R[pool]["全部"]["買方 p_up → 先漲一段"], ensure_ascii=False), json.dumps(R[pool]["全部"]["賣方 p_dn → 先跌一段"], ensure_ascii=False))
