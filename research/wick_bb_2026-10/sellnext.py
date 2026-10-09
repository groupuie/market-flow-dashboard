# 嚴格目標「隔天賣在高點」:訊號日 t 收盤(或 t+1 開盤)賣出後,
#   ① 之後 20 日最高價沒有超過 t 日最高價 2% 以上(高點已經出現);且 ② 20 日內從賣價跌 ≥8%(真的是頂)
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
from lib import DT, series, load
S=pickle.load(open(DT+"/stock.pkl","rb")); P=S["P"]; Fz=S["F"]
O,H,L,C,V=[P[k].astype("float64") for k in "OHLCV"]
dates=C.index
rng=(H-L).where(H>L); uw=(H-np.maximum(O,C))/rng
mid=C.rolling(20).mean(); sdv=C.rolling(20).std(ddof=0); up=mid+2*sdv; touch=H>=up
s50=C.rolling(50).mean(); ext=C/s50-1
tr=np.maximum(H-L,np.maximum((H-C.shift()).abs(),(L-C.shift()).abs())); atr=tr.rolling(14,min_periods=10).mean()
volr=V/V.rolling(60,min_periods=40).mean()
futH=H[::-1].rolling(20,min_periods=20).max()[::-1].shift(-1)
futL=L[::-1].rolling(20,min_periods=20).min()[::-1].shift(-1)
succ_close=((futH<=H*1.02)&(futL<=C*0.92)).astype(float).where(futH.notna())       # 今天收盤賣
# 隔天收盤賣(用隔天確認):高點沒再被超越 + 從隔天收盤跌 ≥8%
futH2=H[::-1].rolling(19,min_periods=19).max()[::-1].shift(-2); futL2=L[::-1].rolling(19,min_periods=19).min()[::-1].shift(-2)
succ_next=((np.maximum(futH2,H.shift(-1))<=H*1.02)&(futL2<=C.shift(-1)*0.92)).astype(float).where(futH2.notna())
pickle.dump({"succ_close":succ_close,"succ_next":succ_next},open(DT+"/sell_succ.pkl","wb"))
W=touch&(uw>=0.25)
per=(dates>="2007-01-01")
b_all=succ_close[per].stack().dropna().mean(); b_t=succ_close[per].where(touch[per]).stack().dropna().mean(); b_w=succ_close[per].where(W[per]).stack().dropna().mean()
print(f"「今天收盤賣=賣在頂」成功率:隨便一天 {b_all*100:.1f}% | 碰上軌 {b_t*100:.1f}% | 碰上軌+上影≥1/4 {b_w*100:.1f}%")
# 板塊/大盤同步:SOX、SMH、QQQ、SPY 當天是否也碰上軌+上影≥1/4;以及全宇宙當天出現上影碰軌的比例
def idx_wick(sym):
    d=load(sym).reindex(dates); o,h,l,c=d.o,d.h,d.l,d.c
    u=c.rolling(20).mean()+2*c.rolling(20).std(ddof=0); w=(h-np.maximum(o,c))/(h-l).where(h>l)
    return ((h>=u)&(w>=0.25)), (h>=u)
soxW,soxT=idx_wick("SMH"); qqqW,qqqT=idx_wick("QQQ"); spyW,spyT=idx_wick("SPY")
brW=(W.sum(axis=1)/C.notna().sum(axis=1))
pickle.dump({"soxW":soxW,"qqqW":qqqW,"spyW":spyW,"brW":brW,"soxT":soxT},open(DT+"/sync.pkl","wb"))
bc=lambda s: pd.DataFrame(np.repeat(s.values[:,None],C.shape[1],axis=1),index=dates,columns=C.columns)
cr=pd.read_pickle(DT+"/climA_rank.pkl").reindex(dates)
gap=O/C.shift(1)-1; dayret=C/C.shift(1)-1; offhi=1-C/H; r5=C/C.shift(5)-1; r20=C/C.shift(20)-1
d20atr=(C-mid)/atr; pctB=(C-(mid-2*sdv))/(4*sdv)
upd=(C>C.shift(1)).astype(int); nup=upd.apply(lambda c:c.groupby((c==0).cumsum()).cumsum())
hh_up=(H>H.shift(1)).astype(int); nhh=hh_up.apply(lambda c:c.groupby((c==0).cumsum()).cumsum())
COND={
 "(只有)碰上軌+上影≥1/4":C.notna(),
 "上影≥1/2":uw>=0.5,
 "收盤離高點≥5%":offhi>=0.05,
 "當天收跌(收<昨收)":dayret<0,
 "跳空≥3%開高、收在昨收之下":(gap>=0.03)&(C<C.shift(1)),
 "長K:當日振幅≥2倍ATR":(H-L)>=2*atr.shift(1),
 "爆量≥3倍":volr>=3,
 "前5日漲≥15%":r5>=0.15,
 "20日漲≥30%":r20>=0.30,
 "高於20日線≥3倍ATR":d20atr>=3,
 "拉離50日線≥25%":ext>=0.25,
 "連續創新高≥5日後":nhh.shift(1)>=5,
 "費半(SMH)同天也上影碰軌":bc(soxW),
 "QQQ同天也上影碰軌":bc(qqqW),
 "全追蹤≥10%同天上影碰軌":bc(brW>=0.10),
 "資金氣候≤20%":bc(cr<=0.20),
}
COMBO={
 "爆量≥3倍 & 收盤離高點≥5%":("爆量≥3倍","收盤離高點≥5%"),
 "前5日漲≥15% & 收跌":("前5日漲≥15%","當天收跌(收<昨收)"),
 "高於20日線≥3ATR & 收盤離高點≥5%":("高於20日線≥3倍ATR","收盤離高點≥5%"),
 "長K & 收跌":("長K:當日振幅≥2倍ATR","當天收跌(收<昨收)"),
 "費半同步 & 拉離≥25%":("費半(SMH)同天也上影碰軌","拉離50日線≥25%"),
 "全追蹤≥10%同步 & 前5日漲≥15%":("全追蹤≥10%同天上影碰軌","前5日漲≥15%"),
 "跳空反轉 & 爆量≥3倍":("跳空≥3%開高、收在昨收之下","爆量≥3倍"),
 "20日漲≥30% & 收盤離高點≥5%":("20日漲≥30%","收盤離高點≥5%"),
}
PER={"A 07-16":("2007-01-01","2016-12-31"),"B 17-26":("2017-01-01","2026-12-31")}
ny={k:(C[(dates>=a)&(dates<=b)].notna().values.sum()/252) for k,(a,b) in PER.items()}
rows=[]
def run(nm,cond):
    r={"條件(都要先有 碰上軌+上影≥1/4)":nm}
    for p,(a,b) in PER.items():
        pm=(dates>=a)&(dates<=b); sig=(W&cond).loc[pm]
        e=succ_close.loc[pm].where(sig).stack().dropna(); e2=succ_next.loc[pm].where(sig&(C.shift(-1)<L).loc[pm]).stack().dropna()
        r[p+" n"]=int(sig.values.sum()); r[p+" 每檔年"]=round(sig.values.sum()/ny[p],2); r[p+" 賣在頂%"]=round(e.mean()*100,1)
        r[p+" 隔天破低再賣:n"]=len(e2); r[p+" 隔天破低再賣:賣在頂%"]=round(e2.mean()*100,1) if len(e2) else None
    rows.append(r)
for nm,cd in COND.items(): run(nm,cd)
for nm,(x,y) in COMBO.items(): run(nm,COND[x]&COND[y])
R=pd.DataFrame(rows); pd.set_option("display.width",260); pd.set_option("display.max_rows",100)
for p,(a,b) in PER.items():
    pm=(dates>=a)&(dates<=b); print(p,"基準:碰上軌+上影≥1/4 賣在頂 %.1f%%"%(succ_close.loc[pm].where(W.loc[pm]).stack().dropna().mean()*100))
print(R.to_string(index=False))
R.to_pickle(DT+"/sellnext_R.pkl")
