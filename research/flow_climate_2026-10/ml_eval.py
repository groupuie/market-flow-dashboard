import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from sklearn.metrics import roc_auc_score
from lib import DT
L=pd.read_pickle(DT+"/long.pkl"); P=pd.read_pickle(DT+"/ml_preds.pkl")
d=L.index.get_level_values(0); yr=d.year
df=pd.DataFrame({"pup":P.pup.values,"pdd":P.pdd.values,"f20":L.f20.values,"f10":L.f10.values,"mae20":L.mae20.values,"sd20":L.sd20.values,"x20":L.x20.values,"yr":yr,"date":d,"sym":L.index.get_level_values(1)})
df=df.dropna(subset=["pup","f20"])
df["up"]=(df.f20>0).astype(int); df["dd"]=(df.mae20<=np.log(0.85)).astype(int)
print("trivial AUC dd (sd20):", round(roc_auc_score(df.dd,df.sd20),3), " model:", round(roc_auc_score(df.dd,df.pdd),3))
print("pooled AUC up:", round(roc_auc_score(df.up,df.pup),3))
# cross-sectional AUC (within-date ranks) to separate selection from timing
df["pup_cs"]=df.groupby("date").pup.rank(pct=True); df["f20_cs"]=df.f20-df.groupby("date").f20.transform("mean")
print("cross-sectional AUC (beat same-day avg):", round(roc_auc_score((df.f20_cs>0).astype(int),df.pup_cs),3))
# date-level timing: mean pup per date vs EW mean f20
g=df.groupby("date").agg(pup=("pup","mean"),f20=("f20","mean"))
print("timing IC (date mean pup vs EW f20, 5d spaced):", round(g.iloc[::5].pup.rank().corr(g.iloc[::5].f20.rank()),3))
# deciles by year
df["dec"]=df.groupby("yr").pup.transform(lambda s: pd.qcut(s,10,labels=False,duplicates="drop"))
t=df.groupby(["yr","dec"]).agg(hit=("up","mean"),mu=("f20","mean")).unstack("dec")
base=df.groupby("yr").agg(hit=("up","mean"),mu=("f20","mean"))
out=pd.DataFrame({"base_hit":base.hit*100,"top_hit":t["hit"][9]*100,"bot_hit":t["hit"][0]*100,"base_mu":base.mu*100,"top_mu":t["mu"][9]*100,"bot_mu":t["mu"][0]*100})
print(out.round(1).to_string())
for per,(a,b) in (("2011-17",(2011,2017)),("2018-26",(2018,2026))):
    s=df[(df.yr>=a)&(df.yr<=b)]
    dd=s.groupby("yr").pup.transform(lambda x: pd.qcut(x,10,labels=False,duplicates="drop"))
    print(per,"top10pct hit %.1f mu %.2f | bottom10pct hit %.1f mu %.2f | base hit %.1f mu %.2f"%(s[dd==9].up.mean()*100,s[dd==9].f20.mean()*100,s[dd==0].up.mean()*100,s[dd==0].f20.mean()*100,s.up.mean()*100,s.f20.mean()*100))
df.to_pickle(DT+"/ml_df.pkl")
