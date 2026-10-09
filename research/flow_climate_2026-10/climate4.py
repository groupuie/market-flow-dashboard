import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT, series
M=pd.read_pickle(DT+"/market.pkl"); L=pd.read_pickle(DT+"/long.pkl"); C=pd.read_pickle(DT+"/climate_c2.pkl")
spx=series("^GSPC",M.index); s200=spx.rolling(200).mean()
brake=((spx<s200)&(s200<s200.shift(20)))|((M.hy_dd60<=-0.03)&(M.hy_chg20<0))
stress=C[["sys","fear","gexdix"]].mean(axis=1,skipna=True); stress[brake]=0.5
V={"A":C[["yen","fincond"]].mean(axis=1),
   "F (A+stress 1/3)":pd.concat([C.yen,C.fincond,stress],axis=1).mean(axis=1),
   "G (A 1/2 + stress 1/2)":(C[["yen","fincond"]].mean(axis=1)+stress)/2,
   "yen only":C.yen,"fincond only":C.fincond,"stress(braked) only":stress}
d=L.index.get_level_values(0)
P=[("2007-07-01","2011-12-31"),("2012-01-01","2016-12-31"),("2017-01-01","2021-12-31"),("2022-01-01","2026-12-31")]
for vn,s in V.items():
    r=s.rolling(756,min_periods=252).rank(pct=True).reindex(d).values
    out=[]
    for a,b in P:
        m=(d>=a)&(d<=b)&~np.isnan(r)&L.f20.notna().values
        f=L.f20.values[m]; rr=r[m]; base=(f>0).mean()*100
        hi=f[rr>0.9]; lo=f[rr<=0.1]
        out.append(f"{a[:4]} base {base:.0f} | top10 {(hi>0).mean()*100:.0f}% {hi.mean()*100:+.1f} | bot10 {(lo>0).mean()*100:.0f}% {lo.mean()*100:+.1f}")
    print(f"{vn:24s} "+" || ".join(out))
