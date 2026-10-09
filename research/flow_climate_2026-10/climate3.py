import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT, series, calendar
M=pd.read_pickle(DT+"/market.pkl"); I=pd.read_pickle(DT+"/idx_targets.pkl"); L=pd.read_pickle(DT+"/long.pkl")
C=pd.read_pickle(DT+"/climate_c2.pkl")
ew=L.f20.groupby(level=0).mean().reindex(M.index)
spx=series("^GSPC",M.index); s200=spx.rolling(200).mean()
bear=(spx<s200)&(s200<s200.shift(20))
credit_stress=(M.hy_dd60<=-0.03)&(M.hy_chg20<0)
print("bear days share %.1f%%, credit stress %.1f%%"%(bear.mean()*100,credit_stress.mean()*100))
def comp(cols,brake=None):
    X=C[cols].copy()
    if brake is not None:
        for c in ("sys","fear","gexdix"):
            if c in X: X.loc[brake,c]=0.5
    return X.mean(axis=1,skipna=True).where(X.notna().sum(axis=1)>=2)
V={"A yen+fin":comp(["yen","fincond"]),"B all5":comp(["yen","fincond","sys","fear","gexdix"]),
   "C all5 bear-brake":comp(["yen","fincond","sys","fear","gexdix"],bear),
   "D all5 credit-brake":comp(["yen","fincond","sys","fear","gexdix"],credit_stress),
   "E all5 bear|credit":comp(["yen","fincond","sys","fear","gexdix"],bear|credit_stress)}
P=[("2007-07-01","2011-12-31"),("2012-01-01","2016-12-31"),("2017-01-01","2021-12-31"),("2022-01-01","2026-12-31")]
for nm,sc in V.items():
    line=[]
    for a,b in P:
        d=pd.concat([sc.rename("s"),ew.rename("ew"),I.SMH_f20.rename("smh"),I.SPY_f20.rename("spy")],axis=1)[a:b].dropna()
        d["q"]=pd.qcut(d.s,5,labels=False,duplicates="drop")
        t=d.groupby("q").mean()*100
        h=d.groupby("q").ew.apply(lambda x:(x>0).mean()*100)
        line.append(f"{a[:4]}: Q1 {t.ew.iloc[0]:+.1f}/{h.iloc[0]:.0f}% Q5 {t.ew.iloc[-1]:+.1f}/{h.iloc[-1]:.0f}% (SMH Q1 {t.smh.iloc[0]:+.1f} Q5 {t.smh.iloc[-1]:+.1f})")
    print(f"{nm:20s} | "+" | ".join(line))
pd.DataFrame({k:v for k,v in V.items()}).to_pickle(DT+"/climate_variants.pkl")
