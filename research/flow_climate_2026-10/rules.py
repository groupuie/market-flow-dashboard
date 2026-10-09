import numpy as np, pandas as pd, pickle, warnings, itertools; warnings.filterwarnings("ignore")
from lib import DT
S=pickle.load(open(DT+"/stock.pkl","rb")); P=S["P"]; C=P["C"].astype("float64"); O=P["O"].astype("float64"); Lw=P["L"].astype("float64")
cr=pd.read_pickle(DT+"/climA_rank.pkl").reindex(C.index)
clim=pd.DataFrame(np.repeat(cr.values[:,None],C.shape[1],axis=1),index=C.index,columns=C.columns)
O1=O.shift(-1)
F={h:np.log(C.shift(-h)/O1) for h in (10,20,40)}
DD={h:np.log(Lw[::-1].rolling(h,min_periods=h).min()[::-1].shift(-1)/O1) for h in (20,40)}
AI=set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI".split())
def cool(raw,k=20):
    arr=raw.fillna(False).values.astype(bool); out=np.zeros_like(arr)
    for j in range(arr.shape[1]):
        last=-999
        for i in np.flatnonzero(arr[:,j]):
            if i-last>k: out[i,j]=True; last=i
    return pd.DataFrame(out,index=raw.index,columns=raw.columns)
def make(kind,ma_ext=50,thr=0.15,cross_ma=20,win=20):
    sx=C.rolling(ma_ext).mean(); sc=C.rolling(cross_ma).mean()
    if kind=="top":
        cond=(C/sx-1).rolling(win).max()>=thr; cr_=(C<sc)&(C.shift(1)>=sc.shift(1))
    else:
        cond=(C/sx-1).rolling(win).min()<=-thr; cr_=(C>sc)&(C.shift(1)<=sc.shift(1))
    return cool(cond&cr_)
P4=[("2009-01-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
dates=C.index; dix=pd.Series(np.arange(len(dates)),index=dates)
def ev(sig,side,h=40,ai_only=False,boot=False):
    res=[]; cis=[]
    for a,b in P4:
        per=(dates>=a)&(dates<=b)
        cols=[c for c in C.columns if (c in AI)] if ai_only else list(C.columns)
        f=F[h].loc[per,cols]; m=sig.loc[per,cols]
        base=f.stack().dropna(); e=f.stack()[m.stack().reindex(f.stack().index).fillna(False).values].dropna() if False else f.where(m).stack().dropna()
        if side=="top": hit=(e<0).mean()*100; bh=(base<0).mean()*100
        else: hit=(e>0).mean()*100; bh=(base>0).mean()*100
        res.append((len(e),hit-bh,e.mean()*100-base.mean()*100))
        if boot and len(e)>20:
            blk=(dix.reindex(e.index.get_level_values(0)).values//20)
            g=pd.DataFrame({"b":blk,"w":((e<0) if side=="top" else (e>0)).values}).groupby("b").w.agg(["sum","count"])
            rng=np.random.default_rng(0); k=len(g); bs=[]
            for _ in range(400):
                ii=rng.integers(0,k,k); bs.append(g["sum"].values[ii].sum()/g["count"].values[ii].sum()*100-bh)
            cis.append(np.percentile(bs,[5,95]))
    return res,cis
print("=== 減碼確認 ▼ = extension → first close below MA, × climate ≤ cut (edge = P(f40<0)-base, Δmean40)")
for thr,cut in itertools.product([0.10,0.15,0.20],[0.2,0.3,0.5]):
    s=make("top",50,thr)&(clim<=cut)
    r,_=ev(s,"top",40); ra,_=ev(s,"top",40,ai_only=True)
    print(f" ext>={thr:.0%} clim<={cut:.0%}: "+" | ".join(f"n{n} {e:+.0f}pt {m:+.1f}%" for n,e,m in r)+"  || AI "+" ".join(f"{e:+.0f}" for n,e,m in ra))
print("=== 抄底確認 ▲ = pullback → first close above MA, × climate ≥ cut (edge = P(f40>0)-base)")
for thr,cut in itertools.product([0.08,0.10,0.15],[0.5,0.6,0.7,0.8]):
    s=make("bot",50,thr)&(clim>=cut)
    r,_=ev(s,"bot",40); ra,_=ev(s,"bot",40,ai_only=True)
    print(f" dip>={thr:.0%} clim>={cut:.0%}: "+" | ".join(f"n{n} {e:+.0f}pt {m:+.1f}%" for n,e,m in r)+"  || AI "+" ".join(f"{e:+.0f}" for n,e,m in ra))
