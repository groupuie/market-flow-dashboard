# 熱:同一批 kline_<代號>.json 用 pandas 重算(與 t22e_hot.py 同公式);輸出應與 t22e_jscheck.js 完全一致(2026-10-10:8 檔一致)
import json,sys,numpy as np,pandas as pd
out={}
for s in ['TSM','NVDA','AAPL','MU','BE','AVGO','LITE','PLTR']:
    b=json.load(open(f'kline_{s}.json'))['bars']
    df=pd.DataFrame([x[:5] for x in b],columns=['d','o','h','l','c']); d=pd.to_datetime(df.d)
    H=df.h.astype(float); C=df.c.astype(float)
    def runc(cond): c=cond.astype(int); return c.groupby((c==0).cumsum()).cumsum()
    tdD=runc(C>C.shift(4)); up=C.rolling(20).mean()+2*C.rolling(20).std(ddof=0); touch=H>=up
    wk=d.dt.to_period("W-FRI").values
    Wc=C.groupby(wk).last(); tdWd=runc(Wc>Wc.shift(4))
    td=lambda X: pd.Series(X.reindex(wk).values,index=df.index)
    c4=td(Wc.shift(4)); prev=td(tdWd.shift(1))
    tdW=((C>c4).astype(int)*(prev.fillna(0)+1)).where(c4.notna())
    S1=td(Wc.rolling(19).sum().shift(1)); S2=td((Wc**2).rolling(19).sum().shift(1))
    m=(S1+C)/20; v=((S2+C**2)/20-m**2).clip(lower=0); upW=m+2*np.sqrt(v)
    cumH=pd.Series(H.groupby(wk).cummax().values,index=df.index); touchW=cumH>=upW
    raw=((tdD>=9)&(tdD<=13)&touch&(tdW>=9)&touchW).fillna(False).astype(bool)
    sig=raw&~raw.shift(1).fillna(False).astype(int).rolling(10,min_periods=1).max().astype(bool)
    out[s]=[f"{df.d[i]}|{int(tdD[i])}|{int(tdW[i])}" for i in np.flatnonzero(sig.values)]
    out[s+'_raw']=int(raw.sum())
print(json.dumps(out))
