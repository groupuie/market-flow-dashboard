# Nested check: train 2006-07..2012-11 (embargo), permutation importance on 2013-2017 validation (no peeking at 2018+)
import numpy as np, pandas as pd, warnings, time; warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from lib import DT
src=open("ml_wf.py").read(); exec(src.split("y_up=")[0])
y=(L["f20"]>0).astype(float).where(L["f20"].notna())
dates=d.unique().sort_values(); di=pd.Series(np.arange(len(dates)),index=dates); dix=di.reindex(d).values
tr=(d<"2012-12-01")&y.notna().values&(dix%3==0)
Xt=X[tr]; cols=[c for c in X.columns if Xt[c].nunique()>1]
clf=HistGradientBoostingClassifier(max_iter=250,learning_rate=0.05,max_depth=5,min_samples_leaf=800,l2_regularization=1.0,max_features=0.5,random_state=0).fit(Xt[cols],y[tr])
m=(d>="2013-01-01")&(d<"2018-01-01")&y.notna().values&(dix%5==0)
Xo=X.loc[m,cols].copy(); yo=y[m].values; do=d[m]; f20=L["f20"][m].values
def score(Xe):
    p=clf.predict_proba(Xe)[:,1]
    g=pd.DataFrame({"d":do,"p":p,"f":f20}).groupby("d").mean()
    cs=pd.DataFrame({"d":do,"p":p,"f":f20}); cs["pr"]=cs.groupby("d").p.rank(pct=True); cs["fx"]=cs.f-cs.groupby("d").f.transform("mean")
    return roc_auc_score(yo,p), g.p.rank().corr(g.f.rank()), cs.pr.corr(cs.fx.rank(pct=True))
base=score(Xo); print("VALID 2013-17 base AUC %.4f timingIC %.3f csIC %.3f"%base)
G={"stock_tech":[c for c in cols if c in SF],"cs_rank_rel":[c for c in cols if c.startswith("cs_") or c.startswith("rel")],
"cta_volctl":[c for c in cols if c.startswith(("cta_","flip","volctl","rv21","rv63","sb_corr"))],
"vix":[c for c in cols if c.startswith(("vix","vrp","vvix","skew"))],"gex_dix":[c for c in cols if c.startswith(("gex","dix"))],
"credit":[c for c in cols if c.startswith(("hy_","ig_"))],"rates":[c for c in cols if c.startswith(("tnx","curve","move"))],
"fx":[c for c in cols if c.startswith(("dxy","jpy","krw"))],"commod":[c for c in cols if c.startswith(("oil","gold","silver","agau","cuau","auspx"))],
"index_state":[c for c in cols if c.startswith(("spx_","ndx_","sox_"))],"breadth":[c for c in cols if c.startswith("br")],
"cot":[c for c in cols if c.startswith("cot_")],"misc":[c for c in cols if c in ("btc_chg20","kospi_r5","kospi_r20","twii_r20","tom","hb_lv20","rsp_spy20")]}
rng=np.random.default_rng(1)
for g,cs in G.items():
    if not cs: continue
    res=[]
    for rep in range(2):
        Xp=Xo.copy()
        if g in ("stock_tech","cs_rank_rel"):
            for c in cs: Xp[c]=rng.permutation(Xp[c].values)
        else:
            ud=np.unique(do); perm=dict(zip(ud,rng.permutation(ud)))
            tmp=Xo[cs].groupby(do).first(); Xp[cs]=tmp.loc[[perm[x] for x in do]].values
        res.append(score(Xp))
    s=np.mean(res,axis=0)
    print(f"{g:12s} n={len(cs):3d}  dAUC={base[0]-s[0]:+.4f}  dTimingIC={base[1]-s[1]:+.3f}  dCSIC={base[2]-s[2]:+.3f}")
