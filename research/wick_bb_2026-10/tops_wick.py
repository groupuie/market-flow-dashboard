# 1) 驗證「回看高點都有上影線」:真高點的上影線比例 vs 一般日子(base rate)
import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
from lib import DT
S=pickle.load(open(DT+"/stock.pkl","rb")); P=S["P"]
O,H,L,C,V=[P[k].astype("float64") for k in "OHLCV"]
m=C.index>="2007-01-01"
rng=(H-L).where(H>L); uw=(H-np.maximum(O,C))/rng
up=C.rolling(20).mean()+2*C.rolling(20).std(ddof=0); touch=H>=up
# 真高點:當天最高價 = 前後各 10 日最高,且之後 20 日內從該高點跌 ≥10%
hmax=H.rolling(21,center=True,min_periods=21).max()
fut_low=L[::-1].rolling(20,min_periods=20).min()[::-1].shift(-1)
top=(H>=hmax)&(fut_low<=0.90*H)
# 大高點:前後各 20 日最高 + 之後 40 日內跌 ≥20%
hmax2=H.rolling(41,center=True,min_periods=41).max(); fl2=L[::-1].rolling(40,min_periods=40).min()[::-1].shift(-1)
top2=(H>=hmax2)&(fl2<=0.80*H)
def frac(mask,cond):
    a=cond[m&True].where(mask[m]).stack().dropna() if False else None
cnt=lambda x:int(x[m].values.sum())
print("真高點(±10日最高且20日內跌≥10%):",cnt(top),"個;每檔每年約 %.1f 次"%(cnt(top)/(C[m].notna().values.sum()/252)))
print("大高點(±20日最高且40日內跌≥20%):",cnt(top2),"個;每檔每年約 %.1f 次"%(cnt(top2)/(C[m].notna().values.sum()/252)))
valid=C.notna()&uw.notna()
for k in (0.25,1/3,0.5):
    w=(uw>=k)
    # 高點當天 / 高點當天或前後一天
    w3=w|w.shift(1,fill_value=False)|w.shift(-1,fill_value=False)
    base1=w[m&True][valid[m]].values.mean() if False else w[m].where(valid[m]).stack().dropna().mean()
    base3=w3[m].where(valid[m]).stack().dropna().mean()
    t1=w[m].where(top[m]).stack().dropna().mean(); t3=w3[m].where(top[m]).stack().dropna().mean()
    T1=w[m].where(top2[m]).stack().dropna().mean(); T3=w3[m].where(top2[m]).stack().dropna().mean()
    print(f"上影≥{k:.2f}: 高點當天有 {t1*100:.0f}%(大高點 {T1*100:.0f}%) vs 隨便一天 {base1*100:.0f}% | 高點±1天內有 {t3*100:.0f}%(大高點 {T3*100:.0f}%) vs 隨便3天 {base3*100:.0f}%")
# 反過來:有上影(碰上軌)的日子,有多少是真高點(±2天內)?
near_top=top|top.shift(1,fill_value=False)|top.shift(2,fill_value=False)|top.shift(-1,fill_value=False)|top.shift(-2,fill_value=False)
for k in (0.25,1/3,0.5):
    sig=touch&(uw>=k)
    p=near_top[m].where(sig[m]).stack().dropna().mean(); b=near_top[m].where(valid[m]).stack().dropna().mean()
    bt=near_top[m].where(touch[m]).stack().dropna().mean()
    print(f"碰上軌+上影≥{k:.2f} 的日子,落在真高點±2天內:{p*100:.1f}%(隨便一天 {b*100:.1f}%,碰上軌任何一天 {bt*100:.1f}%)")
pickle.dump({"top":top,"top2":top2,"near_top":near_top},open(DT+"/tops_truth.pkl","wb"))
