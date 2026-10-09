import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
from lib import DT
S=pickle.load(open(DT+"/stock.pkl","rb")); P=S["P"]; C=P["C"].astype("float64"); O=P["O"].astype("float64"); Lw=P["L"].astype("float64"); H=P["H"].astype("float64")
cr=pd.read_pickle(DT+"/climA_rank.pkl").reindex(C.index)
s20=C.rolling(20).mean(); s50=C.rolling(50).mean()
ext=(C/s50-1).rolling(20).max()>=0.15
cross=(C<s20)&(C.shift(1)>=s20.shift(1))
raw=(ext&cross)
# cooldown 20 days per stock
sig=raw.copy()*False
arr=raw.values; out=np.zeros_like(arr,dtype=bool)
for j in range(arr.shape[1]):
    last=-999
    for i in range(arr.shape[0]):
        if arr[i,j] and i-last>20: out[i,j]=True; last=i
sig=pd.DataFrame(out,index=C.index,columns=C.columns)
O1=O.shift(-1)
f20=np.log(C.shift(-20)/O1); f40=np.log(C.shift(-40)/O1)
lmin40=Lw[::-1].rolling(40,min_periods=40).min()[::-1].shift(-1); dd40=np.log(lmin40/O1)
# buy analog: after pullback (C was <= -10% below SMA50 within 20d) first close above SMA20
dip=(C/s50-1).rolling(20).min()<=-0.10
crossup=(C>s20)&(C.shift(1)<=s20.shift(1))
rawb=dip&crossup; arr=rawb.values; outb=np.zeros_like(arr,dtype=bool)
for j in range(arr.shape[1]):
    last=-999
    for i in range(arr.shape[0]):
        if arr[i,j] and i-last>20: outb[i,j]=True; last=i
sigb=pd.DataFrame(outb,index=C.index,columns=C.columns)
P4=[("2009-01-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
def ev(nm,mask,side):
    out=[]
    for a,b in P4:
        per=pd.Series(True,index=C.index); per=(C.index>=a)&(C.index<=b)
        base20=f20[per].stack().dropna(); base40=f40[per].stack().dropna(); bdd=dd40[per].stack().dropna()
        m=mask[per].stack(); m=m[m]
        e20=f20.stack().reindex(m.index).dropna(); e40=f40.stack().reindex(m.index).dropna(); edd=dd40.stack().reindex(m.index).dropna()
        if side=="top":
            out.append(f"{a[2:4]}-{b[2:4]} n={len(e40):4d} P(f40<0) {(e40<0).mean()*100:.0f}%({(base40<0).mean()*100:.0f}) dd40<=-10% {(edd<=np.log(0.9)).mean()*100:.0f}%({(bdd<=np.log(0.9)).mean()*100:.0f}) mu40 {e40.mean()*100:+.1f}({base40.mean()*100:+.1f})")
        else:
            out.append(f"{a[2:4]}-{b[2:4]} n={len(e40):4d} P(f40>0) {(e40>0).mean()*100:.0f}%({(base40>0).mean()*100:.0f}) P(f20>0) {(e20>0).mean()*100:.0f}%({(base20>0).mean()*100:.0f}) mu40 {e40.mean()*100:+.1f}({base40.mean()*100:+.1f})")
    print(f"{nm:34s} "+" | ".join(out))
crb=cr.values[:,None]
clim=pd.DataFrame(np.repeat(cr.values[:,None],C.shape[1],axis=1),index=C.index,columns=C.columns)
ev("出 rule (all)",sig,"top")
ev("出 & clim<=30%",sig&(clim<=0.3),"top")
ev("出 & clim>30%",sig&(clim>0.3),"top")
ev("buy: dip→cross>SMA20 (all)",sigb,"bot")
ev("buy: dip→cross & clim>=70%",sigb&(clim>=0.7),"bot")
ev("buy: dip→cross & clim<70%",sigb&(clim<0.7),"bot")
pickle.dump({"out":sig,"buy":sigb},open(DT+"/tops_sig.pkl","wb"))
