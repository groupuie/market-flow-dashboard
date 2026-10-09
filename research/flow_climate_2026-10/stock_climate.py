import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT
L=pd.read_pickle(DT+"/long.pkl"); V=pd.read_pickle(DT+"/climate_variants.pkl")
d=L.index.get_level_values(0)
P=[("2007-07-01","2011-12-31"),("2012-01-01","2016-12-31"),("2017-01-01","2021-12-31"),("2022-01-01","2026-12-31")]
AI=set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI".split())
ai=L.index.get_level_values(1).isin(AI)
for vn in ("A yen+fin","E all5 bear|credit"):
    s=V[vn]
    # expanding-window quantile thresholds (no lookahead): rank of today's score vs trailing 3y distribution
    r=s.rolling(756,min_periods=252).rank(pct=True)
    L["clim"]=r.reindex(d).values
    print("=====",vn,"(stock-level pooled; bins by trailing-3y percentile of climate)")
    for a,b in P:
        m=(d>=a)&(d<=b)&L.clim.notna().values&L.f20.notna().values
        sub=L[m]; aim=ai[m]
        bins=pd.cut(sub.clim,[0,0.1,0.3,0.7,0.9,1.0],labels=["<10%","10-30","30-70","70-90",">90%"])
        g=sub.groupby(bins).agg(n=("f20","size"),hit=("f20",lambda x:(x>0).mean()*100),mu=("f20",lambda x:x.mean()*100),dd=("mae20",lambda x:(x<=np.log(0.85)).mean()*100))
        ga=sub[aim].groupby(bins[aim]).agg(hit=("f20",lambda x:(x>0).mean()*100),mu=("f20",lambda x:x.mean()*100))
        print(f" {a[:4]}-{b[:4]} base hit {(sub.f20>0).mean()*100:.0f}% mu {sub.f20.mean()*100:+.2f}")
        print("   all: "+" | ".join(f"{i}: {r.hit:.0f}% {r.mu:+.1f}% dd15 {r.dd:.0f}%" for i,r in g.iterrows()))
        print("   AI : "+" | ".join(f"{i}: {r.hit:.0f}% {r.mu:+.1f}%" for i,r in ga.iterrows()))
