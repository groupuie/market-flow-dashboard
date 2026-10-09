import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from evalx import *
L=load_long()
d=L.index.get_level_values(0)
feats=["r1","r2","r3","r5","r10","r20","r60","r120","r250","z1","z5","z10","z20","d10","d20","d50","d200","p20","p50","p200","pctB","rsi2","rsi14","ibs","dd252","pos252","pos20","dd60","up60","volr","volr5","rvpos","sc","tds","tdb","ndown","nup","gap","beta","res5","res20","zres5","atrp","sd20"]
out=[]
for per,(a,b) in PERIODS.items():
    sub=L[(d>=a)&(d<=b)]
    sm=sub.groupby(level=1)["f20"].transform("mean")
    ex=sub["f20"]-sm
    for f in feats:
        x=sub[f]
        q=x.groupby(level=0).transform(lambda s: s.rank(pct=True)) if False else x.rank(pct=True)
        dec=(q*10).clip(upper=9.999).astype("float").floordiv(1)
        g=pd.DataFrame({"dec":dec,"f20":sub["f20"],"ex":ex,"up":(sub["f20"]>0).astype(float)}).dropna()
        t=g.groupby("dec").agg(mu=("f20","mean"),ex=("ex","mean"),hit=("up","mean"))
        out.append(dict(per=per,feat=f,lo_mu=t.mu.iloc[0]*100,hi_mu=t.mu.iloc[-1]*100,lo_ex=t.ex.iloc[0]*100,hi_ex=t.ex.iloc[-1]*100,lo_hit=t.hit.iloc[0]*100,hi_hit=t.hit.iloc[-1]*100,base_hit=g.up.mean()*100))
R=pd.DataFrame(out).set_index(["feat","per"]).unstack("per")
pd.set_option("display.width",250); pd.set_option("display.max_rows",200)
cols=[(c,p) for c in ["lo_hit","hi_hit","base_hit","lo_ex","hi_ex"] for p in ("IS","OOS")]
print(R[cols].round(1).to_string())
