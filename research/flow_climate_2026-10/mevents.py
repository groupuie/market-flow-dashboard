import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import DT
M=pd.read_pickle(DT+"/market.pkl"); I=pd.read_pickle(DT+"/idx_targets.pkl")
idx=M.index
def ep(sig,gap=20):
    sig=sig.fillna(False).astype(bool); out=pd.Series(False,index=sig.index); last=-10**9
    for i,(d,v) in enumerate(sig.items()):
        if v and i-last>gap: out.iloc[i]=True
        if v: last=i
    return out
def rep(name,sig,gap=20):
    e=ep(sig,gap)
    for per,(a,b) in (("IS","2007-07-01","2017-12-31"),("OOS","2018-01-01","2026-12-31")) if False else (("IS",("2007-07-01","2017-12-31")),("OOS",("2018-01-01","2026-12-31"))):
        m=e&(idx>=a)&(idx<=b); base=(idx>=a)&(idx<=b)
        s=[]
        for t in ("SPY_f10","SPY_f20","QQQ_f20","SMH_f20"):
            y=I[t][m].dropna(); yb=I[t][base].dropna()
            s.append(f"{t.split('_')[0]}{t[-3:]} {y.mean()*100:+.1f}%/{(y>0).mean()*100:.0f}% (base {yb.mean()*100:+.1f}/{(yb>0).mean()*100:.0f})")
        mae=I["SPY_mae20"][m].mean()*100
        print(f"{name:44s} {per:3s} n={m.sum():3d} | "+" | ".join(s)+f" | SPYmae20 {mae:.1f}")
    return e
vr=M.vix_ratio; vix=M.vix
print("--- 抄底 market-level events ---")
rep("VIX/VIX3M back <1 after >1 within 10d", (vr<1)&(vr.shift(1)>=1))
rep("VIX/VIX3M back <0.95 after >1.0 w/in 10d", (vr<0.95)&(M.vix_ratio_max10>=1.0))
rep("VIX >1y P80 & VIX -20% from 10d peak", (M.vix_pct.rolling(10).max()>=0.8)&(vix<=0.8*vix.rolling(10).max()))
rep("VIX >1y P90 (in panic)", M.vix_pct>=0.9)
rep("VIX/VIX3M >1.0 (backwardation)", vr>=1.0)
rep("CTA_ndx bottom 10% (3y)", M.cta_ndx_pct<=0.1)
rep("GEX <0", M.gex<0)
rep("GEX<0 & VIX ratio back <1", (M.gex<0)&(vr<1)&(M.vix_ratio_max10>=1))
rep("breadth20 <15% then >50% in 10d (thrust)", (M.br20>=0.5)&(M.br20.rolling(10).min()<=0.15))
rep("breadth20 <10%", M.br20<=0.10)
rep("credit dd60 < -2% & hy_chg5>0", (M.hy_dd60<=-0.02)&(M.hy_chg5>0))
rep("SPX dd>10% & VIX ratio back<1", (M.spx_dd<=-0.10)&(vr<1)&(M.vix_ratio_max10>=1))
rep("DIX5 >= 1y P90", M.dix_pct>=0.9)
print("--- 減碼 market-level events ---")
rep("CTA_ndx top10% & VIX 1y pct<20%", (M.cta_ndx_pct>=0.9)&(M.vix_pct<=0.2))
rep("CTA_ndx top10% & GEX pct>=80%", (M.cta_ndx_pct>=0.9)&(M.gex_pct>=0.8))
rep("VIX +30% in 5d from low base (pct<30 5d ago)", (M.vix_chg5>=np.log(1.3))&(M.vix_pct.shift(5)<=0.3))
rep("SPX close<50DMA after CTA top10% w/in 20d", (M.spx_d50<0)&(M.spx_d50.shift(1)>=0)&(M.cta_spx_pct.rolling(20).max()>=0.9))
rep("10y +40bp in 20d", M.tnx_chg20>=40)
rep("DXY +3% in 20d", M.dxy_chg20>=np.log(1.03))
rep("Oil +20% in 20d", M.oil_chg20>=np.log(1.2))
rep("Gold +8% in 20d", M.gold_chg20>=np.log(1.08))
rep("Credit hy_z20 <= -2 (widening shock)", M.hy_z20<=-2)
rep("YEN surge (jpy_z10<=-2)", M.jpy_z10<=-2)
rep("COT AM z>=1.5 (crowded long)", M.cot_eq_am_z>=1.5)
rep("Vol-control pct>=90% & rv21 up 5d", (M.volctl_pct>=0.9)&(M.rv21>M.rv21.shift(5)*1.3))
