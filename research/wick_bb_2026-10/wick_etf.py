import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from lib import load
rows=[]
for s in ("SPY","QQQ","SMH","SOXX","IWM","XLK"):
    d=load(s); d=d[d.index>="1999-01-01"]
    O,H,L,C=d.o,d.h,d.l,d.c
    mid=C.rolling(20).mean(); sd=C.rolling(20).std(ddof=0); up=mid+2*sd
    uw=(H-np.maximum(O,C))/(H-L).where(H>L)
    sig=(H>=up)&(uw>=1/3)
    for h in (1,3,5,10):
        f=np.log(C.shift(-h)/C)
        e=f[sig].dropna(); b=f.dropna()
        rows.append((s,h,len(e),(e<0).mean()*100,(b<0).mean()*100,e.mean()*100,b.mean()*100))
R=pd.DataFrame(rows,columns=["sym","h","n","dn","base_dn","mu","base_mu"])
pd.set_option("display.width",200)
print(R.round(2).to_string(index=False))
