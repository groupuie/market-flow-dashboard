import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT, series
M=pd.read_pickle(DT+"/market.pkl"); L=pd.read_pickle(DT+"/long.pkl"); C=pd.read_pickle(DT+"/climate_c2.pkl")
A=C[["yen","fincond"]].mean(axis=1); A=A.where(C[["yen","fincond"]].notna().all(axis=1))
cr=A.rolling(756,min_periods=252).rank(pct=True); cr.to_pickle(DT+"/climA_rank.pkl")
d=L.index.get_level_values(0)
clim=cr.reindex(d).values
spx=series("^GSPC",M.index); spx200=(spx>spx.rolling(200).mean()).reindex(d).values
sox=series("^SOX",M.index); sox200=(sox>sox.rolling(200).mean()).reindex(d).values
spxz5=M.spx_z5.reindex(d).values; soxz5=M.sox_z5.reindex(d).values
dchg=(cr-cr.shift(20)).reindex(d).values
P=[("2009-01-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
def rep(nm,mask):
    out=[]
    for a,b in P:
        per=(d>=a)&(d<=b)&L.f20.notna().values
        for h in ("f5","f10","f20"):
            pass
        f=L.f20.values; f10=L.f10.values
        base=(f[per]>0).mean()*100; mm=per&mask
        nd=len(np.unique(d[mm]))
        out.append(f"{a[2:4]}-{b[2:4]} n={mm.sum():5d}/{nd:3d}d hit20 {((f[mm]>0).mean()*100) if mm.sum() else np.nan:.0f}%({base:.0f}) mu {np.nanmean(f[mm])*100 if mm.sum() else np.nan:+.1f} hit10 {((f10[mm]>0).mean()*100) if mm.sum() else np.nan:.0f}%")
    print(f"{nm:44s} "+" | ".join(out))
ok=~np.isnan(clim)
rep("climate>=90%",ok&(clim>=0.9))
rep("climate>=80%",ok&(clim>=0.8))
rep("climate<=10%",ok&(clim<=0.1))
rep("climate<=20%",ok&(clim<=0.2))
rep("clim>=50% & SPX z5<=-1.5 & SPX>200d",ok&(clim>=0.5)&(spxz5<=-1.5)&spx200)
rep("clim>=50% & SOX z5<=-1.5 & SOX>200d",ok&(clim>=0.5)&(soxz5<=-1.5)&sox200)
rep("clim>=50% & stock z5<=-1.5",ok&(clim>=0.5)&(L.z5.values<=-1.5))
rep("clim>=80% & stock z5<=-1",ok&(clim>=0.8)&(L.z5.values<=-1))
rep("clim<50% & SPX z5<=-1.5 (no support)",ok&(clim<0.5)&(spxz5<=-1.5))
rep("clim drop >=40pt in 20d",ok&(dchg<=-0.4))
rep("clim<=20% & stock p20>=+10% (extended)",ok&(clim<=0.2)&(L.p20.values>=0.10))
rep("clim<=20% & stock below SMA50",ok&(clim<=0.2)&(L.p50.values<0))
