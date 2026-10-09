import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("samenight.py").read().split("PER={")[0])
dix=pd.Series(np.arange(len(dates)),index=dates)
def dist(nm,sig,cols=None,a="2009-01-01",b="2026-12-31"):
    cols=cols or list(C.columns); pm=(dates>=a)&(dates<=b); s=sig.loc[pm,cols]
    ix=s.stack(); ix=ix[ix==True].index
    st=lambda X: X.loc[pm,cols].stack().reindex(ix)
    cA=st(C)
    out=f"{nm:24s} {a[:4]}-{b[:4]} n={len(ix):4d} |"
    for h in (20,40):
        r=np.log(st(C.shift(-h))/cA).dropna()     # 賣掉之後股價變化(正=賣早了)
        ben=-r
        blk=dix.reindex(r.index.get_level_values(0)).values//20
        g=pd.DataFrame({"b":blk,"v":ben.values}).groupby("b").v.agg(["sum","count"]); rng_=np.random.default_rng(0); bs=[]
        for _ in range(800):
            ii=rng_.integers(0,len(g),len(g)); bs.append(g["sum"].values[ii].sum()/g["count"].values[ii].sum()*100)
        lo,hi=np.percentile(bs,[5,95])
        out+=f" {h}日:賣得好(之後跌≥10%) {(r<=np.log(0.9)).mean()*100:.0f}% · 賣早了(之後漲≥10%) {(r>=np.log(1.1)).mean()*100:.0f}% · 平均比續抱 {ben.mean()*100:+.1f}% [{lo:+.1f},{hi:+.1f}] |"
    print(out)
S0=touch&hot&(offhi>=0.05)
for per in (("2009-01-01","2026-12-31"),("2009-01-01","2016-12-31"),("2017-01-01","2026-12-31")):
    dist("頂K 當晚賣(全部)",S0,None,*per)
    dist("頂K 當晚賣 × 氣候≤35%",S0&(clim<=0.35),None,*per)
    dist("頂K 當晚賣 AI股",S0,[c for c in C.columns if c in AI],*per)
