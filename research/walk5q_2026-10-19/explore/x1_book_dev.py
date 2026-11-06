# 開發用(只用訓練資料;不碰考試期):淺樹「型態書」能抓到 M2 多少訊號
import numpy as np, pandas as pd, json
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import roc_auc_score
S = pd.read_pickle("out/scen.pkl")
S["d5"] = 100*(np.exp(S.r5)-1); S["d20"] = 100*(np.exp(S.r20)-1); S["vs20"] = S.w_vs20; S["vs50"] = S.w_vs50
S["atr"] = 100*S.a; S["q_atr"] = 100*S.q_a; S["q_vs50"] = S.q_dma50*S.q_a*100; S["q_vs200"] = S.q_dma200*S.q_a*100; S["q_pos60"] = 100*S.q_pos60
S["hi_days"] = S.dsh250*250; S["rng250"] = S.rw250*S.a*100; S["vtrend"] = S.vr20_60; S["rs20p"] = 100*S.rs20; S["volc"] = S.atr20_60
FB = ["volc","atr","q_atr","q_vs50","q_vs200","q_pos60","hi_days","rng250","vtrend","d5","d20","vs20","vs50","rs20p"]
P = pd.read_pickle("out/real_preds.pkl")
for t, endc in (("T1b","end10"),("T2b","end15"),("T1s","end10")):
    V = S[S[t].notna() & (S.date >= "2018-01-02")]
    res = {}
    for depth in (2,3,4):
        sc = []
        for Y in range(2021,2026):
            tr = V[V[endc] < f"{Y}-01-01"]; te = V[V.date.str[:4]==str(Y)]
            m = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=5000, random_state=1).fit(tr[FB].fillna(-999).values, tr[t].values)
            sc.append(pd.DataFrame({"y": te[t].values, "p": m.predict_proba(te[FB].fillna(-999).values)[:,1]}))
        sc = pd.concat(sc); res[depth] = round(roc_auc_score(sc.y, sc.p),4)
    g = P[(P.target==t)&(P.split=="wf")]
    print(t, "淺樹 WF AUC(深度:AUC)", res, "| M2", round(roc_auc_score(g.y,g.p_m2),4), "M1", round(roc_auc_score(g.y,g.p_m1),4))
