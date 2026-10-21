#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""walk7 W4:電腦方法(逐年往前;訓練只用「答案在測試年之前就結束」的日子)
目標:y_buy = 買方先漲一段;y_sell = 賣方先跌一段;y_dir = D20 先漲(上下對稱,只看方向;缺值不算)
方法(參數事先固定,不調):
  M1 = 梯度提升,只用 11 個「人看圖看得到」的數字(w_*)
  M2 = 梯度提升,全部約 90 個特徵(walk5 的 feats + 大盤 + 相對強弱)
       HistGradientBoosting:lr 0.05、200 輪、15 葉、每葉 ≥ 1000、L2 1、不提早停、seed 20261021;每個目標各一個模型
  K1 = 相似線型:最近 60 天收盤形狀(每 3 天一點、以日均波動為單位,20 點)+ 4 段量比(×3)→ PCA 10 維 → 訓練期隨機 30 萬個找最近 200 個,看它們的結果
  N1 = 序列模型(1D 卷積):最近 64 天的開高低收(÷ 日均波動)+ 量比 + log(日均波動);3 層卷積;訓練期隨機 40 萬個、3 輪、Adam 1e-3、seed 20261021
測試年:M1 / M2 = 2019–2026;K1 / N1 = 2021–2026(省時間);K1 每個測試年隨機 3 萬個 + 全部考題列;N1 全部
用法:python3 -I w4_cpu.py OUT_DIR [--dev]   (--dev:只跑「訓練 ≤ 2017、測試 2018」檢查程式;正式結果不看 2018)"""
import json, os, sys, time
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.decomposition import PCA
from sklearn.neighbors import NearestNeighbors

OUT = sys.argv[1]; DEV = "--dev" in sys.argv; SEED = 20261021; rng = np.random.default_rng(SEED)
S = pd.read_pickle(os.path.join(OUT, "out", "S7.pkl")); P = np.load(os.path.join(OUT, "out", "P64.npy"), mmap_mode="r")
S["y_buy"] = (S.buy == 1).astype(np.int8); S["y_sell"] = (S.sell == 1).astype(np.int8); S["y_dir"] = S.d20
W11 = ["w_atr20", "w_rsi14", "w_d1", "w_d5", "w_d20", "w_vs20", "w_vs50", "w_vs200", "w_vr", "w_rng60", "w_pos60"]
NOT = {"sym", "date", "year", "i", "in_sp", "dv_rank", "end20", "buy", "sell", "buy_day", "sell_day", "d20", "d20_day", "r20", "r60", "y_buy", "y_sell", "y_dir"}
FALL = [k for k in S.columns if k not in NOT]
judged = set()
hp = os.path.join(OUT, "_sealed", "hidden_w7.json")
if os.path.exists(hp):   # 考題列(只拿列號,不看答案)
    H_ = json.load(open(hp)); key = {(r["sym"], int(r["i"])): None for r in H_["items"]}
    judged = set(S.index[[(s, int(i)) in key for s, i in zip(S.sym.values, S.i.values)]])
folds = [(2018, "2018-01-01")] if DEV else [(y, f"{y}-01-01") for y in range(2019, 2027)]
TGT = ["y_buy", "y_sell", "y_dir"]


def hgb():
    return HistGradientBoostingClassifier(learning_rate=0.05, max_iter=200, max_leaf_nodes=15, min_samples_leaf=1000, l2_regularization=1.0, early_stopping=False, random_state=SEED)


def kvec(rows):
    p = P[rows].astype(np.float32); cl = p[:, 3:61:3, 3]
    vb = np.stack([p[:, a:b, 4].mean(1) for a, b in ((4, 19), (19, 34), (34, 49), (49, 64))], 1)
    return np.concatenate([cl, 3 * vb], 1)


def run_cnn(tr_rows, te_rows, seed):
    import torch, torch.nn as nn
    torch.manual_seed(seed); torch.set_num_threads(2)

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.c = nn.Sequential(nn.Conv1d(5, 16, 5, padding=2), nn.ReLU(), nn.Conv1d(16, 32, 5, stride=2, padding=2), nn.ReLU(),
                                   nn.Conv1d(32, 32, 5, stride=2, padding=2), nn.ReLU(), nn.AdaptiveAvgPool1d(1))
            self.h = nn.Sequential(nn.Linear(33, 32), nn.ReLU(), nn.Linear(32, 3))

        def forward(self, x, la):
            return self.h(torch.cat([self.c(x).squeeze(-1), la], 1))

    def batch(rows):
        x = torch.from_numpy(np.ascontiguousarray(P[rows].astype(np.float32).transpose(0, 2, 1)))
        la = torch.from_numpy(np.log(S.a.values[rows].astype(np.float32))[:, None]); return x, la

    net = Net(); opt = torch.optim.Adam(net.parameters(), lr=1e-3); bce = nn.BCEWithLogitsLoss(reduction="none")
    Y = torch.from_numpy(np.stack([S.y_buy.values, S.y_sell.values, np.nan_to_num(S.y_dir.values, nan=0.0)], 1).astype(np.float32))
    M = torch.from_numpy(np.stack([np.ones(len(S)), np.ones(len(S)), (~np.isnan(S.y_dir.values)).astype(float)], 1).astype(np.float32))
    r = np.random.default_rng(seed)
    for ep in range(3):
        order = r.permutation(tr_rows)
        for k in range(0, len(order), 1024):
            b = np.sort(order[k:k + 1024]); x, la = batch(b); out = net(x, la)
            loss = (bce(out, Y[b]) * M[b]).sum() / M[b].sum(); opt.zero_grad(); loss.backward(); opt.step()
    net.eval(); res = []
    with torch.no_grad():
        for k in range(0, len(te_rows), 8192):
            b = te_rows[k:k + 8192]; x, la = batch(b); res.append(torch.sigmoid(net(x, la)).numpy())
    return np.concatenate(res)


preds = {m: [] for m in ("M1", "M2", "K1", "N1")}
for ty, t0 in folds:
    tic = time.time(); tr = S.index[S.end20 < t0].values; te = S.index[S.year == ty].values
    if len(te) == 0:
        continue
    for m, cols in (("M1", W11), ("M2", FALL)):
        out = pd.DataFrame(index=te)
        for t in TGT:
            ok = tr[~np.isnan(S[t].values[tr].astype(float))]
            mdl = hgb().fit(S.loc[ok, cols].values, S.loc[ok, t].values.astype(int)); out["p_" + t[2:]] = mdl.predict_proba(S.loc[te, cols].values)[:, 1]
        preds[m].append(out.assign(year=ty))
    if ty >= 2021 or DEV:
        ref = rng.choice(tr, min(300000, len(tr)), replace=False); ref.sort()
        tsub = np.union1d(rng.choice(te, min(30000, len(te)), replace=False), np.array(sorted(judged & set(te)), dtype=int))
        Kr, Kt = kvec(ref), kvec(tsub); pca = PCA(10, random_state=SEED).fit(Kr)
        nn_ = NearestNeighbors(n_neighbors=200, algorithm="kd_tree").fit(pca.transform(Kr)); _, I = nn_.kneighbors(pca.transform(Kt))
        out = pd.DataFrame(index=tsub)
        for t in TGT:
            yv = S[t].values[ref].astype(float); out["p_" + t[2:]] = np.nanmean(yv[I], axis=1)
        preds["K1"].append(out.assign(year=ty))
        trn = rng.choice(tr, min(400000, len(tr)), replace=False)
        pr = run_cnn(trn, te, SEED + ty); preds["N1"].append(pd.DataFrame(pr, index=te, columns=["p_buy", "p_sell", "p_dir"]).assign(year=ty))
    print(ty, "訓練", len(tr), "測試", len(te), round(time.time() - tic), "秒", flush=True)
    if DEV:
        from sklearn.metrics import roc_auc_score
        for m, L in preds.items():
            if L:
                o = L[-1]; y = S.loc[o.index]
                print("  dev", m, {t: round(roc_auc_score(y[t].values[~np.isnan(y[t].values.astype(float))].astype(int), o["p_" + t[2:]].values[~np.isnan(y[t].values.astype(float))]), 3) for t in TGT})
tag = "dev" if DEV else "real"
for m, L in preds.items():
    if L:
        pd.concat(L).astype("float32").to_pickle(os.path.join(OUT, "out", f"pred_{m}_{tag}.pkl"))
print("完成", tag)
