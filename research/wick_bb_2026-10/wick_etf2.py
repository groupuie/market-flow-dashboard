import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import load
syms=("SPY","QQQ","SMH","SOXX","IWM","XLK","DIA","XLF","XLE","XLV")
recs=[]
for s in syms:
    d=load(s); d=d[d.index>="1999-01-01"]
    O,H,L,C=d.o,d.h,d.l,d.c
    up=C.rolling(20).mean()+2*C.rolling(20).std(ddof=0)
    uw=(H-np.maximum(O,C))/(H-L).where(H>L)
    sig=(H>=up)&(uw>=1/3); touch=(H>=up)
    f5=np.log(C.shift(-5)/C); f3=np.log(C.shift(-3)/C)
    recs.append(pd.DataFrame({"sym":s,"sig":sig,"touch":touch,"f5":f5,"f3":f3}))
D=pd.concat(recs).dropna(subset=["f5"])
D["yr"]=D.index.year
for a,b in ((1999,2012),(2013,2026)):
    x=D[(D.yr>=a)&(D.yr<=b)]
    e=x[x.sig]; t=x[x.touch&~x.sig]
    print(f"{a}-{b}: 訊號 n={len(e)}(不同日 {e.index.nunique()}) 5日跌 {(e.f5<0).mean()*100:.1f}% vs 平常 {(x.f5<0).mean()*100:.1f}% · 碰上軌但無長上影 {(t.f5<0).mean()*100:.1f}% | 5日均 {e.f5.mean()*100:+.2f}% vs {x.f5.mean()*100:+.2f}% | 3日跌 {(e.f3<0).mean()*100:.1f}% vs {(x.f3<0).mean()*100:.1f}%")
    # date-block bootstrap of 5d down-rate difference
    e2=e.copy(); e2["blk"]=(e2.index.year*12+e2.index.month)//2
    g=e2.groupby("blk").f5.agg([("dn",lambda v:(v<0).sum()),("n","size")])
    rng=np.random.default_rng(0); bs=[]
    for _ in range(1000):
        ii=rng.integers(0,len(g),len(g)); bs.append(g.dn.values[ii].sum()/g.n.values[ii].sum()*100-(x.f5<0).mean()*100)
    print("   5日跌機率差 90% CI:",np.percentile(bs,[5,95]).round(1))
