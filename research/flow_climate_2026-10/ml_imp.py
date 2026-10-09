import numpy as np, pandas as pd, warnings, time; warnings.filterwarnings("ignore")
from sklearn.metrics import roc_auc_score
from lib import DT
exec(open("ml_wf.py").read().split("y_up=")[0].split("t0=time.time()")[1].replace("L=pd.read_pickle","L=pd.read_pickle",1)) if False else None
import importlib.util
src=open("ml_wf.py").read()
pre=src.split("y_up=")[0]   # reuse feature construction
exec(pre)
y=(L["f20"]>0).astype(float).where(L["f20"].notna())
clf,cols=pd.read_pickle(DT+"/ml_model_pup_2018.pkl")
dates=d.unique().sort_values(); di=pd.Series(np.arange(len(dates)),index=dates)
m=(d>="2018-01-01")&y.notna().values&((di.reindex(d).values%5)==0)
Xo=X.loc[m,cols].copy(); yo=y[m].values; do=d[m]; f20=L["f20"][m].values
def score(Xe):
    p=clf.predict_proba(Xe)[:,1]
    auc=roc_auc_score(yo,p)
    g=pd.DataFrame({"d":do,"p":p,"f":f20}).groupby("d").mean()
    tic=g.p.rank().corr(g.f.rank())
    cs=pd.DataFrame({"d":do,"p":p,"f":f20}); cs["pr"]=cs.groupby("d").p.rank(pct=True); cs["fx"]=cs.f-cs.groupby("d").f.transform("mean")
    csic=cs.pr.corr(cs.fx.rank(pct=True))
    return auc,tic,csic
base=score(Xo); print("base AUC %.4f timingIC %.3f csIC %.3f"%base, "rows",len(Xo))
G={"stock_tech":[c for c in cols if c in SF],"cs_rank_rel":[c for c in cols if c.startswith("cs_") or c.startswith("rel")],
"cta_volctl":[c for c in cols if c.startswith(("cta_","flip","volctl","rv21","rv63","sb_corr"))],
"vix":[c for c in cols if c.startswith(("vix","vrp","vvix","skew"))],"gex_dix":[c for c in cols if c.startswith(("gex","dix"))],
"credit":[c for c in cols if c.startswith(("hy_","ig_"))],"rates":[c for c in cols if c.startswith(("tnx","curve","move"))],
"fx":[c for c in cols if c.startswith(("dxy","jpy","krw"))],"commod":[c for c in cols if c.startswith(("oil","gold","silver","agau","cuau","auspx"))],
"index_state":[c for c in cols if c.startswith(("spx_","ndx_","sox_"))],"breadth":[c for c in cols if c.startswith("br")],
"cot":[c for c in cols if c.startswith("cot_")],"misc":[c for c in cols if c in ("btc_chg20","kospi_r5","kospi_r20","twii_r20","tom","hb_lv20","rsp_spy20")]}
rng=np.random.default_rng(0)
for g,cs in G.items():
    if not cs: continue
    Xp=Xo.copy()
    # permute by DATE blocks for market features (keep cross-sectional structure), by row for stock features
    if g in ("stock_tech","cs_rank_rel"):
        for c in cs: Xp[c]=rng.permutation(Xp[c].values)
    else:
        ud=np.unique(do); perm=dict(zip(ud,rng.permutation(ud)))
        tmp=Xo[cs].groupby(do).first()
        Xp[cs]=tmp.loc[[perm[x] for x in do]].values
    s=score(Xp)
    print(f"{g:12s} n={len(cs):3d}  dAUC={base[0]-s[0]:+.4f}  dTimingIC={base[1]-s[1]:+.3f}  dCSIC={base[2]-s[2]:+.3f}")
