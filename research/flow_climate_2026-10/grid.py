import numpy as np, pandas as pd, warnings, itertools; warnings.filterwarnings("ignore")
from lib import DT
L=pd.read_pickle(DT+"/long.pkl"); cr=pd.read_pickle(DT+"/climA_rank.pkl")
d=L.index.get_level_values(0); clim=cr.reindex(d).values; ok=~np.isnan(clim)
AI=set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI".split())
ai=L.index.get_level_values(1).isin(AI)
P=[("2009-01-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
f=L.f20.values
def row(mask,side):
    res=[]; aires=[]
    for a,b in P:
        per=(d>=a)&(d<=b)&~np.isnan(f)
        base=((f[per]>0) if side=="bot" else (f[per]<0)).mean()*100
        m=per&mask
        h=((f[m]>0) if side=="bot" else (f[m]<0)).mean()*100 if m.sum() else np.nan
        res.append(h-base)
        ma=m&ai; pa=per&ai
        ba=((f[pa]>0) if side=="bot" else (f[pa]<0)).mean()*100
        aires.append((((f[ma]>0) if side=="bot" else (f[ma]<0)).mean()*100-ba) if ma.sum()>30 else np.nan)
    return res,aires,int((mask&~np.isnan(f)).sum())
print("減碼 grid: edge = P(f20<0) - base (pts) per period [09-13,14-18,19-22,23-26]; AI subgroup")
ext={"p20>=10%":L.p20.values>=0.10,"p20>=15%":L.p20.values>=0.15,"d20>=2ATR":L.d20.values>=2,"rsi14>=70":L.rsi14.values>=70,"p50>=20%":L.p50.values>=0.20}
for ct,(en,em) in itertools.product([0.2,0.3],ext.items()):
    r,ra,n=row(ok&(clim<=ct)&em,"top")
    print(f" clim<={ct:.0%} & {en:10s} n={n:6d} edge "+" ".join(f"{x:+5.1f}" for x in r)+" | AI "+" ".join(f"{x:+5.1f}" for x in ra)+f" | min {min(r):+.1f}")
print("抄底 grid: edge = P(f20>0) - base")
dip={"z5<=-1":L.z5.values<=-1,"z5<=-1.5":L.z5.values<=-1.5,"p20<=-5%":L.p20.values<=-0.05,"rsi14<=40":L.rsi14.values<=40,"pos20<=0.2":L.pos20.values<=0.2}
for ct,(dn,dm) in itertools.product([0.7,0.8,0.9],dip.items()):
    r,ra,n=row(ok&(clim>=ct)&dm,"bot")
    print(f" clim>={ct:.0%} & {dn:10s} n={n:6d} edge "+" ".join(f"{x:+5.1f}" for x in r)+" | AI "+" ".join(f"{x:+5.1f}" for x in ra)+f" | min {min(r):+.1f}")
for ct in (0.7,0.8,0.9):
    r,ra,n=row(ok&(clim>=ct),"bot"); print(f" clim>={ct:.0%} (no dip)   n={n:6d} edge "+" ".join(f"{x:+5.1f}" for x in r)+" | AI "+" ".join(f"{x:+5.1f}" for x in ra))
for ct in (0.2,0.3):
    r,ra,n=row(ok&(clim<=ct),"top"); print(f" clim<={ct:.0%} (no ext)   n={n:6d} edge "+" ".join(f"{x:+5.1f}" for x in r)+" | AI "+" ".join(f"{x:+5.1f}" for x in ra))
