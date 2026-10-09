# 4) 決策樹指向「當天跌多少/離高點收多低」而不是「上影比例」→ 針對性檢驗(仍兩期驗證)
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("wick_cond.py").read().split("COND={")[0])
O1=O.shift(-1)
F={h:np.log(C.shift(-h)/O1) for h in (5,10,20)}
dd20=np.log(L[::-1].rolling(20,min_periods=20).min()[::-1].shift(-1)/O1)
AI=set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI".split())
dates=C.index; PER={"A 2007-16":("2007-01-01","2016-12-31"),"B 2017-26":("2017-01-01","2026-12-31")}
ny={k:(C[(dates>=a)&(dates<=b)].notna().values.sum()/252) for k,(a,b) in PER.items()}
dayret=C/C.shift(1)-1; offhi=1-C/H; r5=C/C.shift(5)-1
def st(mask,per,cols=None):
    a,b=PER[per]; pm=(dates>=a)&(dates<=b); cols=cols or list(C.columns); mk=mask.loc[pm,cols]
    o={"n":int(mk.values.sum()),"年頻":round(mk.values.sum()/ny[per]*len(C.columns)/len(cols),1)}
    for h in (5,10,20):
        e=F[h].loc[pm,cols].where(mk).stack().dropna(); o[f"{h}日跌%"]=round((e<0).mean()*100,1); o[f"{h}日均%"]=round(e.mean()*100,2)
    e=dd20.loc[pm,cols].where(mk).stack().dropna(); o["20日內跌≥10%"]=round((e<=np.log(0.9)).mean()*100,1)
    return o
base={p:st(C.notna(),p) for p in PER}
T={
 "平常(所有日子)":C.notna(),
 "碰上軌(任何)":touch,
 "碰上軌 & 收盤離當日高點≥3%":touch&(offhi>=0.03),
 "碰上軌 & 收盤離當日高點≥5%":touch&(offhi>=0.05),
 "碰上軌 & 當天收跌≥2%":touch&(dayret<=-0.02),
 "碰上軌 & 當天收跌≥3%":touch&(dayret<=-0.03),
 "碰上軌 & 前5日漲≥8% & 當天收跌≥2%":touch&(r5>=0.08)&(dayret<=-0.02),
 "碰上軌 & 拉離≥15% & 當天收跌≥2%":touch&(ext>=0.15)&(dayret<=-0.02),
 "對照:拉離≥15%(任何一天)":ext>=0.15,
 "對照:拉離≥15% & 當天收跌≥2%(不論有無碰軌)":(ext>=0.15)&(dayret<=-0.02),
}
rows=[]
for nm,mk in T.items():
    for p in PER: rows.append(dict(條件=nm,期間=p,**st(mk,p)))
    rows.append(dict(條件=nm,期間="B AI股",**st(mk,"B 2017-26",[c for c in C.columns if c in AI])))
R=pd.DataFrame(rows); pd.set_option("display.width",250); pd.set_option("display.max_rows",100)
print(R.to_string(index=False))
