import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT
M=pd.read_pickle(DT+"/market.pkl"); I=pd.read_pickle(DT+"/idx_targets.pkl"); L=pd.read_pickle(DT+"/long.pkl")
ew=L.f20.groupby(level=0).mean().reindex(M.index)
ewx=L.x20.groupby(level=0).mean().reindex(M.index)
T={"EW_f20":ew,"SPY_f20":I.SPY_f20,"SMH_f20":I.SMH_f20,"QQQ_f20":I.QQQ_f20}
P=[("2007-07-01","2011-12-31"),("2012-01-01","2016-12-31"),("2017-01-01","2021-12-31"),("2022-01-01","2026-12-31")]
rows=[]
for tn,y in T.items():
    for c in M.columns:
        ics=[]
        for a,b in P:
            dd=pd.concat([M[c],y],axis=1)[a:b].dropna()
            if len(dd)<300: ics.append(np.nan); continue
            vals=[]
            for off in range(0,20,4):   # average over 5 offsets of 20d-spaced samples
                s=dd.iloc[off::20]; vals.append(s.iloc[:,0].rank().corr(s.iloc[:,1].rank()))
            ics.append(np.nanmean(vals))
        ics=np.array(ics); v=ics[~np.isnan(ics)]
        if len(v)<3: continue
        rows.append(dict(t=tn,f=c,p1=ics[0],p2=ics[1],p3=ics[2],p4=ics[3],mean=v.mean(),cons=max((v>0).sum(),(v<0).sum()),nper=len(v)))
R=pd.DataFrame(rows)
R["score"]=R["mean"].abs()*(R.cons==R.nper)
pd.set_option("display.width",200); pd.set_option("display.max_rows",300)
for tn in T:
    r=R[(R.t==tn)&(R.cons==R.nper)].sort_values("score",ascending=False).head(22)
    print("===",tn,"(features with same-sign IC in every sub-period; IC on 20d-spaced samples)")
    print(r[["f","p1","p2","p3","p4","mean","nper"]].round(3).to_string(index=False))
R.to_pickle(DT+"/stab.pkl")
