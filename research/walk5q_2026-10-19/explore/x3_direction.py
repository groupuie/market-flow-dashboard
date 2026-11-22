# 事後探索(沒有預先登記):拿掉「會不會動」之後,圖裡還有沒有「往哪邊」的資訊?
# D 目標 = 只看「10 天內有碰到其中一邊」的情境:先碰 +2×atr = 1、先碰 −1.5×atr = 0(買點的對 vs 洗)
# 同樣的 M2 參數、同樣的逐年往前切法;另外看 10 天後報酬(以 atr 為單位)的排序相關
import gzip, json, sys, numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import roc_auc_score
sys.argv = ["x", "out/scen.pkl", "out/tmp"]; exec(open("q1_models.py").read().split("out, imp, coefs")[0])   # 載入同一組特徵清單與 M2 參數
Bz = json.load(gzip.open("../walk4/data/bars.json.gz"))["bars"]
three, fwd = [], []
for s, i in zip(S.sym.values, S.i.values):
    b = Bz[s]; C = b[i][4]
    if i + 10 >= len(b): three.append(np.nan); fwd.append(np.nan); continue
    tr = [max(b[k][2], b[k-1][4]) - min(b[k][3], b[k-1][4]) for k in range(i-19, i+1)]; a = sum(tr)/20/C
    r = 0.5
    for j in range(1, 11):
        if b[i+j][3] <= C*(1-1.5*a): r = 0.0; break
        if b[i+j][2] >= C*(1+2*a): r = 1.0; break
    three.append(r); fwd.append(np.log(b[i+10][4]/C)/(a*np.sqrt(10)))
S["D"] = np.where(np.array(three) == 0.5, np.nan, three); S["F10"] = fwd
S.loc[S.T1b.isna(), ["D", "F10"]] = np.nan
res = {}
def boot_auc(y, p, d, L=20, B=1000, seed=1):
    ud, di = np.unique(d, return_inverse=True); T = len(ud); rng = np.random.default_rng(seed); v = []
    for _ in range(B):
        st = rng.integers(0, T, -(-T//L)); cnt = np.bincount(((st[:, None]+np.arange(L))%T).ravel(), minlength=T); w = cnt[di]
        m = w > 0; v.append(roc_auc_score(y[m], p[m], sample_weight=w[m]))
    return [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
for tgt in ("D", "F10"):
    V = S[S[tgt].notna() & (S.date >= "2018-01-02")]; preds = []
    for Y in range(2021, 2026):
        tr = V[V.end10 < f"{Y}-01-01"]; te = V[V.date.str[:4] == str(Y)]
        if tgt == "D":
            m = m2().fit(tr[FFULL].values, tr.D.values.astype(int)); p = m.predict_proba(te[FFULL].values)[:, 1]
        else:
            m = HistGradientBoostingRegressor(learning_rate=0.05, max_iter=200, max_leaf_nodes=15, min_samples_leaf=1000, l2_regularization=1.0, early_stopping=False, random_state=SEED).fit(tr[FFULL].values, tr.F10.clip(-4, 4).values)
            p = m.predict(te[FFULL].values)
        preds.append(pd.DataFrame({"date": te.date.values, "y": te[tgt].values, "p": p}))
    g = pd.concat(preds)
    if tgt == "D":
        res["D:有動的情境裡先漲 2atr(1)vs 先跌 1.5atr(0)"] = {"張數": len(g), "先漲比例%": round(100*float(g.y.mean()), 1), "AUC": round(roc_auc_score(g.y, g.p), 4), "95%(20 天區塊、1000 次)": boot_auc(g.y.values, g.p.values, g.date.values)}
        g["dec"] = pd.qcut(g.p.rank(method="first"), 10, labels=False); res["D 十分位 先漲%"] = [round(100*float(g[g.dec == k].y.mean()), 1) for k in range(10)]
    else:
        ic = g[["y", "p"]].rank().corr().iloc[0, 1]; daily = g.groupby("date").apply(lambda h: h[["y", "p"]].rank().corr().iloc[0, 1]).dropna()
        g["dec"] = pd.qcut(g.p.rank(method="first"), 10, labels=False)
        res["F10:10 天後報酬(atr 單位)"] = {"張數": len(g), "排序相關(全部)": round(float(ic), 4), "每天橫向排序相關平均": round(float(daily.mean()), 4), "每天的 t 值(粗估)": round(float(daily.mean()/daily.std()*np.sqrt(len(daily))), 2),
                                       "十分位 實際 10 天報酬(atr 單位)": [round(float(g[g.dec == k].y.mean()), 3) for k in range(10)]}
json.dump(res, open("out/x3_direction.json", "w"), ensure_ascii=False, indent=1); print(json.dumps(res, ensure_ascii=False, indent=1))
