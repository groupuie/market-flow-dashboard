import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT
M=pd.read_pickle(DT+"/market.pkl"); I=pd.read_pickle(DT+"/idx_targets.pkl"); L=pd.read_pickle(DT+"/long.pkl")
ew=L.f20.groupby(level=0).mean().reindex(M.index); ew10=L.f10.groupby(level=0).mean().reindex(M.index); ew5=L.f5.groupby(level=0).mean().reindex(M.index)
def rk(x,n=756,mp=252): return x.rolling(n,min_periods=mp).rank(pct=True)
C=pd.DataFrame({
 "yen": 1-rk(M.cot_jy_dlr_z),                         # carry unwound (dealers short yen) → bullish
 "sys": 1-(rk(M.cta_ndx)+rk(M.volctl))/2,             # systematic exposure low → bullish
 "fear": (rk(M.vix,252,126)+rk(M.vix9_ratio,252,126).fillna(rk(M.vix_ratio,252,126)))/2,
 "gexdix": ((1-rk(M.gex,504,126))+rk(M.dix5,504,126))/2,
 "fincond": ((1-rk(M.fvx_chg20))+(1-rk(M.cta_dxy)))/2,
})
C.to_pickle(DT+"/climate_c2.pkl")
print(C.dropna().corr().round(2))
sc=C.mean(axis=1,skipna=True).where(C.notna().sum(axis=1)>=3)
T={"EW5":ew5,"EW10":ew10,"EW20":ew,"SPY20":I.SPY_f20,"QQQ20":I.QQQ_f20,"SMH20":I.SMH_f20,"SPYmae20":I.SPY_mae20}
for a,b in (("2007-07-01","2021-12-31"),("2022-01-01","2026-12-31"),("2007-07-01","2011-12-31"),("2012-01-01","2016-12-31"),("2017-01-01","2021-12-31")):
    d=pd.concat([sc.rename("s")]+[v.rename(k) for k,v in T.items()],axis=1)[a:b].dropna()
    d["q"]=pd.qcut(d.s,5,labels=False)
    t=d.groupby("q").mean()
    hit=d.groupby("q").apply(lambda g:(g[["EW20","SPY20","SMH20"]]>0).mean())
    print(f"--- {a[:4]}-{b[:4]} n={len(d)}  (Q1=bearish climate … Q5=bullish)")
    for k in T: print(f"  {k:8s} "+"  ".join(f"{v*100:+.2f}" for v in t[k].values))
    for k in ("EW20","SPY20","SMH20"): print(f"  hit {k:5s} "+"  ".join(f"{v*100:.0f}%" for v in hit[k].values))
# per-component IC by period (20d spaced avg over offsets)
P=[("2007-07-01","2011-12-31"),("2012-01-01","2016-12-31"),("2017-01-01","2021-12-31"),("2022-01-01","2026-12-31")]
def ic(x,y,a,b):
    dd=pd.concat([x,y],axis=1)[a:b].dropna(); v=[]
    for off in range(0,20,4):
        s=dd.iloc[off::20]; v.append(s.iloc[:,0].rank().corr(s.iloc[:,1].rank()))
    return np.mean(v)
for c in list(C.columns)+["SCORE"]:
    x=sc if c=="SCORE" else C[c]
    print(f"{c:8s} IC EW20 by period: "+"  ".join(f"{ic(x,ew,a,b):+.3f}" for a,b in P)+"  | SMH20: "+"  ".join(f"{ic(x,I.SMH_f20,a,b):+.3f}" for a,b in P))
sc.to_pickle(DT+"/climate_score.pkl")
