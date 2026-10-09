import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
from lib import DT
exec(open("rules.py").read().split('print("=== 減碼確認')[0])
# production definitions
s20=C.rolling(20).mean(); s50=C.rolling(50).mean()
ext=(C/s50-1).rolling(20).max(); dip=(C/s50-1).rolling(20).min()
dn=(C<s20)&(C.shift(1)>=s20.shift(1)); up=(C>s20)&(C.shift(1)<=s20.shift(1))
trimraw=cool(dn&(ext>=0.15)); buyraw=cool(up&(dip<=-0.10))
T_strong=trimraw&(clim<=0.20); T_reg=trimraw&(clim<=0.35)&~T_strong
B_strong=buyraw&(dip<=-0.15)&(clim>=0.80); B_reg=buyraw&(clim>=0.65)&~B_strong
pickle.dump({"T_strong":T_strong,"T_reg":T_reg,"B_strong":B_strong,"B_reg":B_reg,"trimraw":trimraw,"buyraw":buyraw,"clim":cr},open(DT+"/prod_sigs.pkl","wb"))
dates=C.index
def tab(sig,side,h):
    rows=[]
    for y in range(2009,2027):
        per=(dates.year==y)
        f=F[h].loc[per]; base=f.stack().dropna(); e=f.where(sig.loc[per]).stack().dropna()
        if side=="top": rows.append((y,len(e),(e<0).mean()*100 if len(e) else np.nan,(base<0).mean()*100,e.mean()*100 if len(e) else np.nan,base.mean()*100))
        else: rows.append((y,len(e),(e>0).mean()*100 if len(e) else np.nan,(base>0).mean()*100,e.mean()*100 if len(e) else np.nan,base.mean()*100))
    return pd.DataFrame(rows,columns=["yr","n","hit","base","mu","bmu"]).set_index("yr")
for nm,sig,side in (("▼strong",T_strong,"top"),("▼regular",T_reg,"top"),("▲strong",B_strong,"bot"),("▲regular",B_reg,"bot")):
    for h in (20,40):
        t=tab(sig,side,h)
        tot_n=t.n.sum()
        print(f"{nm} h={h}: per-year n/hit/base: "+" ".join(f"{y%100:02d}:{int(r.n)}/{r.hit:.0f}/{r.base:.0f}" for y,r in t.iterrows() if r.n>0))
    # overall + drawdown
    for a,b in (("2009-01-01","2017-12-31"),("2018-01-01","2026-12-31"),("2009-01-01","2026-12-31")):
        per=(dates>=a)&(dates<=b)
        out=[]
        for h in (10,20,40):
            f=F[h].loc[per]; base=f.stack().dropna(); e=f.where(sig.loc[per]).stack().dropna()
            hit=((e<0) if side=="top" else (e>0)).mean()*100; bh=((base<0) if side=="top" else (base>0)).mean()*100
            out.append(f"h{h}: {hit:.0f}% vs {bh:.0f}% μ {e.mean()*100:+.1f}% vs {base.mean()*100:+.1f}%")
        dd=DD[40].loc[per]; bdd=(dd.stack()<=np.log(0.9)).mean()*100; edd=dd.where(sig.loc[per]).stack()
        out.append(f"P(40日內跌≥10%) {(edd<=np.log(0.9)).mean()*100:.0f}% vs {bdd:.0f}%")
        print(f"   {a[:4]}-{b[:4]} n={int(sig.loc[per].values.sum())}: "+" | ".join(out))
nsy=(C.notna().sum(axis=0)/252).sum()
for nm,sig in (("▼strong",T_strong),("▼regular",T_reg),("▲strong",B_strong),("▲regular",B_reg)):
    print(nm,"frequency per stock-year: %.2f"%(sig.values.sum()/nsy))
