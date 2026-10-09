import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
from lib import DT, series
exec(open("rules.py").read().split('print("=== 減碼確認')[0])
S=pickle.load(open(DT+"/prod_sigs.pkl","rb"))
M=pd.read_pickle(DT+"/market.pkl").reindex(C.index)
spx=series("^GSPC",C.index); sox=series("^SOX",C.index)
def bc(x): return pd.DataFrame(np.repeat(x.values[:,None],C.shape[1],axis=1),index=C.index,columns=C.columns)
spx_dn20=bc(spx<spx.rolling(20).mean()); sox_dn20=bc(sox<sox.rolling(20).mean())
vix_up=bc(M.vix_chg5>0); vix_dn=bc(M.vix_chg5<0)
trim=S["trimraw"]&(bc(S["clim"])<=0.35); buy=S["buyraw"]&(bc(S["clim"])>=0.80)&((C/C.rolling(50).mean()-1).rolling(20).min()<=-0.15)
dates=C.index
def ev2(sig,side):
    out=[]
    for a,b in (("2009-01-01","2017-12-31"),("2018-01-01","2026-12-31")):
        per=(dates>=a)&(dates<=b)
        r=[]
        for h in (20,40):
            f=F[h].loc[per]; base=f.stack().dropna(); e=f.where(sig.loc[per]).stack().dropna()
            hit=((e<0) if side=="top" else (e>0)).mean()*100; bh=((base<0) if side=="top" else (base>0)).mean()*100
            r.append(f"h{h} {hit:.0f}/{bh:.0f} μ{e.mean()*100:+.1f}")
        dd=DD[40].loc[per]; bdd=(dd.stack().dropna()<=np.log(0.9)).mean()*100; edd=dd.where(sig.loc[per]).stack().dropna()
        r.append(f"dd40≥10% {(edd<=np.log(0.9)).mean()*100:.0f}/{bdd:.0f}")
        out.append(f"{a[2:4]}-{b[2:4]} n={len(edd)} "+" ".join(r))
    return " | ".join(out)
print("▼ base (clim<=35%)          ", ev2(trim,"top"))
print("▼ & SPX<20d                 ", ev2(trim&spx_dn20,"top"))
print("▼ & SOX<20d                 ", ev2(trim&sox_dn20,"top"))
print("▼ & VIX rising 5d           ", ev2(trim&vix_up,"top"))
print("▲ base (dip15 & clim>=80%)  ", ev2(buy,"bot"))
print("▲ & SPX>20d                 ", ev2(buy&~spx_dn20,"bot"))
print("▲ & VIX falling 5d          ", ev2(buy&vix_dn,"bot"))
