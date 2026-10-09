# Cross-sectional (selection) model: stock features only, target = beats same-day universe average over 20d
import numpy as np, pandas as pd, time, warnings, sys; warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from lib import DT
t0=time.time()
L=pd.read_pickle(DT+"/long.pkl")
SF=["r1","r2","r3","r5","r10","r20","r60","r120","r250","z1","z5","z10","z20","d10","d20","d50","d200","p20","p50","p200","pctB","rsi2","rsi14","ibs","dd252","pos252","pos20","dd60","up60","volr","volr5","rvpos","sc","tds","tdb","ndown","nup","gap","beta","res5","res20","zres5","atrp","sd20","sd60"]
d=L.index.get_level_values(0)
X=L[SF].astype("float32").copy()
for c in ["r5","r20","r60","r250","z5","d50","dd252","rvpos","volr5","sd60","beta","gap","res20"]:
    X["cs_"+c]=L[c].groupby(level=0).rank(pct=True).astype("float32").values
ex=L.f20-L.f20.groupby(level=0).transform("mean")
y=(ex>0).astype(float).where(L.f20.notna())
dates=d.unique().sort_values(); di=pd.Series(np.arange(len(dates)),index=dates); dix=di.reindex(d).values
pred=pd.Series(np.nan,index=L.index)
for Y in range(2011,2027):
    test=(d.year==Y); emb=dates[dates<pd.Timestamp(f"{Y}-01-01")][-25]
    tr=(d<emb)&y.notna().values&(dix%3==0)
    Xt=X[tr]; cols=[c for c in X.columns if Xt[c].nunique()>1]
    clf=HistGradientBoostingClassifier(max_iter=200,learning_rate=0.05,max_depth=4,min_samples_leaf=1500,l2_regularization=2.0,max_features=0.5,random_state=0).fit(Xt[cols],y[tr])
    tm=test&y.notna().values
    pred[tm]=clf.predict_proba(X.loc[tm,cols])[:,1]
    print(Y,"AUC %.3f"%roc_auc_score(y[tm],pred[tm]),"%.0fs"%(time.time()-t0)); sys.stdout.flush()
    if Y==2026: pd.to_pickle((clf,cols),DT+"/cs_model_2026.pkl")
pred.to_pickle(DT+"/cs_pred.pkl")
df=pd.DataFrame({"p":pred,"ex":ex,"f20":L.f20,"yr":d.year}).dropna()
df["dec"]=df.groupby(level=0).p.transform(lambda s: pd.qcut(s.rank(method="first"),10,labels=False))
for a,b in ((2011,2016),(2017,2021),(2022,2026)):
    s=df[(df.yr>=a)&(df.yr<=b)]
    t=s.groupby("dec").agg(ex=("ex","mean"),hit=("f20",lambda x:(x>0).mean()))
    print(a,b,"excess by CS decile (%):",(t.ex*100).round(2).tolist()," hit:",(t.hit*100).round(1).tolist())
