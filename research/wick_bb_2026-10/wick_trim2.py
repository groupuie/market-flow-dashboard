import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("wick_trim.py").read().split("def st(")[0])
dix=pd.Series(np.arange(len(dates)),index=dates)
tr=S2["trimraw"]; T=tr&(clim<=0.35)
AIc=[c for c in C.columns if c in AI]
def diff_ci(sig,cols=None,h=40,a="2009-01-01",b="2026-12-31",B=1000):
    cols=cols or list(C.columns); per=(dates>=a)&(dates<=b)
    f=F[h].loc[per,cols]; ww=wk10.loc[per,cols]; s=sig.loc[per,cols]
    e=f.where(s).stack().dropna(); w=ww.stack().reindex(e.index).astype(bool)
    dd=DD[40].loc[per,cols].where(s).stack().reindex(e.index)
    df=pd.DataFrame({"blk":dix.reindex(e.index.get_level_values(0)).values//20,"dn":(e<0).values,"ret":e.values,"w":w.values,"dd":(dd<=np.log(0.9)).values})
    g=df.groupby(["blk","w"]).agg(dn=("dn","sum"),n=("dn","size"),ret=("ret","sum"),dd=("dd","sum")).unstack("w").fillna(0)
    blks=g.index.values; rng=np.random.default_rng(0); out=[]
    def calc(G):
        dw=G[("dn",True)].sum()/G[("n",True)].sum(); dn=G[("dn",False)].sum()/G[("n",False)].sum()
        rw=G[("ret",True)].sum()/G[("n",True)].sum(); rn=G[("ret",False)].sum()/G[("n",False)].sum()
        xw=G[("dd",True)].sum()/G[("n",True)].sum(); xn=G[("dd",False)].sum()/G[("n",False)].sum()
        return (dw-dn)*100,(rw-rn)*100,(xw-xn)*100
    pt=calc(g)
    for _ in range(B):
        ii=rng.integers(0,len(blks),len(blks)); out.append(calc(g.iloc[ii]))
    out=np.array(out); lo=np.percentile(out,5,axis=0); hi=np.percentile(out,95,axis=0)
    return f"n有={int(g[('n',True)].sum())} n無={int(g[('n',False)].sum())} | 40日後較低 差 {pt[0]:+.1f}pt [{lo[0]:+.1f},{hi[0]:+.1f}] | 40日平均 差 {pt[1]:+.1f}% [{lo[1]:+.1f},{hi[1]:+.1f}] | 40日內跌≥10% 差 {pt[2]:+.1f}pt [{lo[2]:+.1f},{hi[2]:+.1f}]"
print("技判出 全部 2009-26:",diff_ci(tr))
print("▼減碼 全部 2009-26:",diff_ci(T))
print("技判出 AI股 2009-26:",diff_ci(tr,AIc))
print("▼減碼 AI股 2009-26:",diff_ci(T,AIc))
