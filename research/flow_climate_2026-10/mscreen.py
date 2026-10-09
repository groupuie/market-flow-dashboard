import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT
M = pd.read_pickle(DT+"/market.pkl"); I = pd.read_pickle(DT+"/idx_targets.pkl")
IS = (M.index>="2007-07-01")&(M.index<"2018-01-01"); OOS = (M.index>="2018-01-01")
def ic(x,y,mask,step=5):
    d=pd.concat([x,y],axis=1)[mask].dropna().iloc[::step]
    if len(d)<60: return np.nan,0
    return d.iloc[:,0].rank().corr(d.iloc[:,1].rank()), len(d)
def tails(x,y,mask,q=0.1):
    d=pd.concat([x,y],axis=1)[mask].dropna()
    if len(d)<200: return (np.nan,)*3
    lo,hi=d.iloc[:,0].quantile([q,1-q])
    return d[d.iloc[:,0]<=lo].iloc[:,1].mean()*100, d.iloc[:,1].mean()*100, d[d.iloc[:,0]>=hi].iloc[:,1].mean()*100
rows=[]
for tgt in ["SPY_f10","SPY_f20","SMH_f20"]:
    y=I[tgt]
    for c in M.columns:
        if c in ("month",): continue
        a,na=ic(M[c],y,IS); b,nb=ic(M[c],y,OOS)
        lo_i,mu_i,hi_i=tails(M[c],y,IS); lo_o,mu_o,hi_o=tails(M[c],y,OOS)
        rows.append(dict(tgt=tgt,feat=c,ic_is=a,ic_oos=b,n_is=na,n_oos=nb,lo_is=lo_i,hi_is=hi_i,mu_is=mu_i,lo_oos=lo_o,hi_oos=hi_o,mu_oos=mu_o))
R=pd.DataFrame(rows)
R["same"]=np.sign(R.ic_is)==np.sign(R.ic_oos)
R["minabs"]=np.where(R.same,np.minimum(R.ic_is.abs(),R.ic_oos.abs()),0)
pd.set_option("display.width",250); pd.set_option("display.max_rows",400)
for tgt in ["SPY_f10","SPY_f20","SMH_f20"]:
    r=R[R.tgt==tgt].sort_values("minabs",ascending=False).head(28)
    print("=== ",tgt," (IC on 5-day-spaced samples; tails = bottom/top decile mean fwd %, vs all)")
    print(r[["feat","ic_is","ic_oos","n_is","n_oos","lo_is","mu_is","hi_is","lo_oos","mu_oos","hi_oos"]].round(3).to_string(index=False))
R.to_pickle(DT+"/mscreen.pkl")
