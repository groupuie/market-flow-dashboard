import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("wick_trim.py").read().split("def st(")[0])
tr=S2["trimraw"]; T=tr&(clim<=0.35)
F[5]=np.log(C.shift(-5)/C.shift(-1).where(False,O1)) if False else np.log(C.shift(-5)/O1)
per=(dates>="2009-01-01")
for nm,sig in (("技判出",tr),("▼減碼",T)):
    for lab,s in (("有前置長上影",sig&wk10),("沒有",sig&~wk10)):
        out=[]
        for h in (5,10,20,40):
            f=F[h].loc[per]; e=f.where(s.loc[per]).stack().dropna(); b=f.stack().dropna()
            out.append(f"{h}日後較低 {(e<0).mean()*100:.0f}%(平常{(b<0).mean()*100:.0f}) 均{e.mean()*100:+.1f}%")
        print(f"{nm} {lab:8s} n={int(s.loc[per].values.sum()):5d} | "+" | ".join(out))
