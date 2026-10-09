import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("sellnext.py").read().split("W=touch&(uw>=0.25)")[0])
succ=pickle.load(open(DT+"/sell_succ.pkl","rb")); succ_next=succ["succ_next"]
offhi=1-C/H; r20=C/C.shift(20)-1; d20atr=(C-mid)/atr
hot=(r20>=0.30)|(d20atr>=3)|(ext>=0.25)
conf=(C.shift(-1)<L)
cr=pd.read_pickle(DT+"/climA_rank.pkl").reindex(dates); clim=pd.DataFrame(np.repeat(cr.values[:,None],C.shape[1],axis=1),index=dates,columns=C.columns)
# 賣價=隔天收盤 → 之後報酬(從 t+1 收盤到 t+1+h 收盤)、與波段頂距離
sell=C.shift(-1)
fr={h:np.log(C.shift(-1-h)/sell) for h in (5,10,20,40)}
topH=pd.concat([H,H.shift(-1)]).groupby(level=0).max() if False else np.maximum(H,H.shift(-1))
fut_max=H[::-1].rolling(40,min_periods=40).max()[::-1].shift(-2)   # 賣出後 40 日內最高
miss=np.log(fut_max/sell)                                           # 賣錯時最多少賺
AI=set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI".split())
PER={"2007-16":("2007-01-01","2016-12-31"),"2017-26":("2017-01-01","2026-12-31")}
ny={k:(C[(dates>=a)&(dates<=b)].notna().values.sum()/252) for k,(a,b) in PER.items()}
dix=pd.Series(np.arange(len(dates)),index=dates)
def evaluate(nm,sig,cols=None):
    cols=cols or list(C.columns)
    for p,(a,b) in PER.items():
        pm=(dates>=a)&(dates<=b); s=sig.loc[pm,cols]
        sc=succ_next.loc[pm,cols].where(s).stack().dropna()
        blk=dix.reindex(sc.index.get_level_values(0)).values//20
        g=pd.DataFrame({"b":blk,"y":sc.values}).groupby("b").y.agg(["sum","count"]); rng_=np.random.default_rng(0); bs=[]
        for _ in range(500):
            ii=rng_.integers(0,len(g),len(g)); bs.append(g["sum"].values[ii].sum()/g["count"].values[ii].sum()*100)
        ci=np.percentile(bs,[5,95]).round(0) if len(g)>5 else ("—","—")
        base={h:fr[h].loc[pm,cols].stack().dropna() for h in (10,20,40)}
        ev={h:fr[h].loc[pm,cols].where(s).stack().dropna() for h in (10,20,40)}
        mi=miss.loc[pm,cols].where(s).stack().dropna()
        dist=np.log(np.maximum(H,H.shift(-1)).loc[pm,cols]/sell.loc[pm,cols]).where(s).stack().dropna()
        print(f"{nm:34s} {p} n={len(sc):4d}(每檔每年 {s.values.sum()/ny[p]*len(C.columns)/len(cols):.2f}) | 賣在頂 {sc.mean()*100:.0f}% [{ci[0]},{ci[1]}] | "
              +" ".join(f"{h}日後較低 {(ev[h]<0).mean()*100:.0f}%(平常{(base[h]<0).mean()*100:.0f}) 均{ev[h].mean()*100:+.1f}%" for h in (10,20,40))
              +f" | 賣價離最高 {dist.mean()*100:.1f}% | 賣錯時之後40日最多再漲 中位 {np.median(mi[mi>0])*100 if (mi>0).any() else 0:.0f}%")
R5=touch&hot&(offhi>=0.05)
evaluate("頂K(漲多+碰上軌+離高≥5%)→隔天破低賣",R5&conf)
evaluate("  同上但只看 AI/半導體",R5&conf,[c for c in C.columns if c in AI])
evaluate("  同上 × 資金氣候≤35%",R5&conf&(clim<=0.35))
evaluate("  同上 × 資金氣候>35%",R5&conf&(clim>0.35))
evaluate("頂K 離高≥7%(更嚴)→隔天破低賣",touch&hot&(offhi>=0.07)&conf)
evaluate("頂K 不等確認(當天收盤就賣)",R5)
pickle.dump({"R5":R5,"conf":conf,"hot":hot},open(DT+"/topk.pkl","wb"))
