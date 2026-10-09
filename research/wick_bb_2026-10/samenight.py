# 當晚賣 vs 等隔天確認:同一批「頂K」日,比較賣價、命中、與「不賣續抱」相比少賠/少賺多少
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("sellnext.py").read().split("W=touch&(uw>=0.25)")[0])
offhi=1-C/H; r20=C/C.shift(20)-1; d20atr=(C-mid)/atr
hot=(r20>=0.30)|(d20atr>=3)|(ext>=0.25)
cr=pd.read_pickle(DT+"/climA_rank.pkl").reindex(dates); clim=pd.DataFrame(np.repeat(cr.values[:,None],C.shape[1],axis=1),index=dates,columns=C.columns)
AI=set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI".split())
conf=(C.shift(-1)<L)
maxc10=C.rolling(10).max()
def fut_max(px_shift,n=40):   # 賣出後 n 日內最高價
    return H[::-1].rolling(n,min_periods=n).max()[::-1].shift(-px_shift)
fmA=fut_max(1); fmB=fut_max(2)
flA=L[::-1].rolling(20,min_periods=20).min()[::-1].shift(-1); flB=L[::-1].rolling(19,min_periods=19).min()[::-1].shift(-2)
PER={"2007-16":("2007-01-01","2016-12-31"),"2017-26":("2017-01-01","2026-12-31")}
def report(nm,sig,cols=None):
    cols=cols or list(C.columns)
    for p,(a,b) in PER.items():
        pm=(dates>=a)&(dates<=b); s=sig.loc[pm,cols]
        ix=s.stack(); ix=ix[ix==True].index
        st=lambda X: X.loc[pm,cols].stack().reindex(ix)
        cA=st(C); cB=st(C.shift(-1)); cf=st(conf).fillna(False).astype(bool)
        hA=st(H); n=len(cA)
        out=[]
        # 賣價品質:比近10日最高收盤低多少(中位)
        dA=np.median(np.log(st(maxc10)/cA).dropna())*100; dB=np.median(np.log(st(maxc10)/cB)[cf].dropna())*100
        # 嚴格賣在頂:之後20日不再創高>2%(相對訊號K最高)且從賣價再跌≥8%
        sA=((st(fut_max(1,20))<=hA*1.02)&(st(flA)<=cA*0.92)).mean()*100
        sB=((st(fut_max(2,19)).combine(st(H.shift(-1)),np.maximum)<=hA*1.02)&(st(flB)<=cB*0.92))[cf].mean()*100
        line=f"{nm:26s} {p} n={n:4d}(隔天確認 {cf.mean()*100:.0f}%) | 賣在頂:當晚 {sA:.0f}% vs 等確認 {sB:.0f}% | 賣價比近10日最高收盤低:當晚 {dA:.1f}% vs 等確認 {dB:.1f}%"
        # 與續抱相比,平均少賠(正=賣得好)
        for h in (10,20,40):
            rA=-np.log(st(C.shift(-h))/cA); rB=(-np.log(st(C.shift(-h-1))/cB)).where(cf,0.0)
            line+=f" | {h}日 當晚{rA.mean()*100:+.1f}% 等確認{rB.mean()*100:+.1f}%"
        print(line)
base_sig=touch&hot&(offhi>=0.05)
report("頂K(離高≥5%)",base_sig)
report("頂K(離高≥7%)",touch&hot&(offhi>=0.07))
report("頂K(離高≥5%)×氣候≤35%",base_sig&(clim<=0.35))
report("頂K(離高≥5%)×氣候>35%",base_sig&(clim>0.35))
report("頂K(離高≥5%) AI股",base_sig,[c for c in C.columns if c in AI])
