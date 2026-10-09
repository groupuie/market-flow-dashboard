# 2) 上影線要配合什麼條件才準?預先列出的條件逐一比較「有上影 vs 同條件無上影」;2007–16 / 2017–26 兩期
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
from lib import DT, series
S=pickle.load(open(DT+"/stock.pkl","rb")); P=S["P"]; Fz=S["F"]
O,H,L,C,V=[P[k].astype("float64") for k in "OHLCV"]
TT=pickle.load(open(DT+"/tops_truth.pkl","rb")); near_top=TT["near_top"]
rng=(H-L).where(H>L); uw=(H-np.maximum(O,C))/rng; ibs=(C-L)/rng
mid=C.rolling(20).mean(); up=mid+2*C.rolling(20).std(ddof=0); touch=H>=up
s50=C.rolling(50).mean(); ext=C/s50-1
tr=np.maximum(H-L,np.maximum((H-C.shift()).abs(),(L-C.shift()).abs())); atr=tr.rolling(14,min_periods=10).mean()
wick_atr=(H-np.maximum(O,C))/atr
volr=V/V.rolling(60,min_periods=40).mean()
hh20=H.shift(1).rolling(20).max(); hh252=H.shift(1).rolling(252,min_periods=200).max()
d=C.diff(); g=d.clip(lower=0); l_=(-d).clip(lower=0)
rsi=100-100/(1+g.ewm(alpha=1/14,adjust=False,min_periods=14).mean()/l_.ewm(alpha=1/14,adjust=False,min_periods=14).mean().replace(0,1e-9))
tds=Fz["tds"].astype("float64").reindex(C.index)
cr=pd.read_pickle(DT+"/climA_rank.pkl").reindex(C.index)
bc=lambda s: pd.DataFrame(np.repeat(s.values[:,None],C.shape[1],axis=1),index=C.index,columns=C.columns)
clim=bc(cr); spy=series("SPY",C.index); spyweak=bc(spy<spy.rolling(20).mean())
# M 頂:最高價在前 10~60 日高點 ±3% 內,且兩高之間曾回落 ≥10%
ph=H.shift(10).rolling(50,min_periods=40).max(); pl=L.shift(1).rolling(60,min_periods=40).min()
mtop=((H/ph-1).abs()<=0.03)&(pl<=0.90*ph)
COND={
 "拉離50日線≥15%":ext>=0.15,"拉離50日線≥25%":ext>=0.25,"爆量≥2倍":volr>=2,
 "關鍵反轉(創新高但收跌)":(H>H.shift(1))&(C<C.shift(1)),
 "假突破20日高(盤中破、收回)":(H>hh20)&(C<hh20),"假突破52週高":(H>hh252)&(C<hh252),
 "跳空≥2%後收黑":(O>=C.shift(1)*1.02)&(C<O),"20日漲≥25%":(C/C.shift(20)-1)>=0.25,
 "RSI≥80":rsi>=80,"TD賣9(近3日)":tds>=9,"資金氣候≤35%":clim<=0.35,"大盤在20日線下":spyweak,
 "上影≥1倍ATR":wick_atr>=1.0,"黑K(收<開)":C<O,"收在當日低檔(IBS≤0.25)":ibs<=0.25,"M頭(第二次碰前高)":mtop,
}
COMBO={
 "拉離≥15% & 爆量≥2倍":("拉離50日線≥15%","爆量≥2倍"),"拉離≥15% & 關鍵反轉":("拉離50日線≥15%","關鍵反轉(創新高但收跌)"),
 "拉離≥25% & 爆量≥2倍":("拉離50日線≥25%","爆量≥2倍"),"假突破20日高 & 爆量≥2倍":("假突破20日高(盤中破、收回)","爆量≥2倍"),
 "假突破52週高 & 爆量≥2倍":("假突破52週高","爆量≥2倍"),"拉離≥15% & 氣候≤35%":("拉離50日線≥15%","資金氣候≤35%"),
 "跳空收黑 & 爆量≥2倍":("跳空≥2%後收黑","爆量≥2倍"),"關鍵反轉 & 爆量≥2倍":("關鍵反轉(創新高但收跌)","爆量≥2倍"),
 "TD賣9 & 拉離≥15%":("TD賣9(近3日)","拉離50日線≥15%"),"上影≥1ATR & 拉離≥15%":("上影≥1倍ATR","拉離50日線≥15%"),
 "20日漲≥25% & 關鍵反轉":("20日漲≥25%","關鍵反轉(創新高但收跌)"),"M頭 & 爆量≥2倍":("M頭(第二次碰前高)","爆量≥2倍"),
 "M頭 & 氣候≤35%":("M頭(第二次碰前高)","資金氣候≤35%"),"拉離≥15% & 大盤在20日線下":("拉離50日線≥15%","大盤在20日線下"),
}
O1=O.shift(-1)
f10=np.log(C.shift(-10)/O1); f20=np.log(C.shift(-20)/O1)
dd20=np.log(L[::-1].rolling(20,min_periods=20).min()[::-1].shift(-1)/O1)
AI=set("NVDA AMD AVGO MU SNDK WDC STX MRVL LITE COHR AAOI TSM ASML AMAT LRCX KLAC SMCI ANET ARM MPWR QCOM INTC TXN ADI ON MCHP NXPI CRDO ALAB CIEN GLW VRT DELL TER ENTG AMKR WOLF POET AEHR MXL GFS SWKS QRVO MTSI".split())
dates=C.index
PER={"A 2007-16":("2007-01-01","2016-12-31"),"B 2017-26":("2017-01-01","2026-12-31")}
ny={k:(C[(dates>=a)&(dates<=b)].notna().values.sum()/252) for k,(a,b) in PER.items()}
def stat(mask,per,cols=None):
    a,b=PER[per]; pm=(dates>=a)&(dates<=b); cols=cols or list(C.columns)
    mk=mask.loc[pm,cols]
    nt=near_top.loc[pm,cols].where(mk).stack().dropna()
    e10=f10.loc[pm,cols].where(mk).stack().dropna(); e20=f20.loc[pm,cols].where(mk).stack().dropna()
    edd=dd20.loc[pm,cols].where(mk).stack().dropna()
    return dict(n=int(mk.values.sum()),freq=mk.values.sum()/ny[per]*(len(C.columns)/len(cols)) if cols else 0,
                top=nt.mean()*100,dn10=(e10<0).mean()*100,mu10=e10.mean()*100,dn20=(e20<0).mean()*100,dd=(edd<=np.log(0.9)).mean()*100)
base={per:stat(C.notna(),per) for per in PER}
for per in PER: print(per,"平常:",{k:round(v,1) for k,v in base[per].items()})
W=(uw>=0.25)
rows=[]
def run(nm,cond):
    for per in PER:
        sw=stat(touch&W&cond,per); so=stat(touch&~W&cond,per)
        rows.append(dict(cond=nm,per=per,n=sw["n"],freq=round(sw["freq"],2),top_w=sw["top"],top_nw=so["top"],dn10_w=sw["dn10"],dn10_nw=so["dn10"],mu10_w=sw["mu10"],mu10_nw=so["mu10"],dd_w=sw["dd"],dd_nw=so["dd"]))
run("(無條件)碰上軌",C.notna())
for nm,cd in COND.items(): run(nm,cd)
for nm,(x,y) in COMBO.items(): run(nm,COND[x]&COND[y])
R=pd.DataFrame(rows)
R.to_pickle(DT+"/wick_cond.pkl")
pd.set_option("display.width",260); pd.set_option("display.max_rows",200)
for per in PER:
    print("=====",per," [_w=碰上軌+上影≥1/4+條件;_nw=碰上軌+上影<1/4+同條件]  top=落在真高點±2天%  dn10=10日後較低%  dd=20日內跌≥10%")
    print(R[R.per==per].drop(columns="per").round(1).to_string(index=False))
