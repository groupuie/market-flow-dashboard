# 加:同一批 kline 用 pandas 重算(與 t23f–h 同公式,不含「前 10 根有出」那條);輸出應與 t23h_jscheck.js 完全一致(2026-10-10:8 檔一致)
import json,numpy as np,pandas as pd
q=pd.DataFrame([x[:5] for x in json.load(open('kline_QQQ.json'))['bars']],columns=['d','o','h','l','c']).set_index('d')['c'].astype(float)
qd=(q<q.rolling(20).mean()).where(q.rolling(20).mean().notna())
out={}
for s in ['TSM','NVDA','AAPL','MU','BE','AVGO','LITE','PLTR']:
    df=pd.DataFrame([x[:5] for x in json.load(open(f'kline_{s}.json'))['bars']],columns=['d','o','h','l','c']).set_index('d').astype(float)
    C,L=df.c,df.l
    S50,S100,S200=C.rolling(50).mean(),C.rolling(100).mean(),C.rolling(200).mean()
    u=(C>S200)&(S50>S200)&(S200>S200.shift(20)); ma3=(S50>S100)&(S100>S200)
    hi=C.rolling(252,min_periods=200).max(); nh=C>=hi
    UTS=u.shift(1,fill_value=False)&ma3.shift(1,fill_value=False)&(nh.astype(int).rolling(40,min_periods=1).max().shift(1).fillna(0)>0)
    d=C.diff(); g=d.clip(lower=0); l=(-d).clip(lower=0)
    ag=g.ewm(alpha=1/14,adjust=False).mean(); al=l.ewm(alpha=1/14,adjust=False).mean(); R=100-100/(1+ag/al.replace(0,np.nan))
    rsiX=(R<=40)&(R.shift(1)>40)
    lo=C.rolling(20).mean()-2*C.rolling(20).std(ddof=0)
    lob=(L<=lo)&((L>lo).astype(int).rolling(10,min_periods=10).sum().shift(1)==10)
    mk=qd.reindex(df.index)
    raw=(UTS&(rsiX|lob)&(mk==True)).fillna(False).astype(bool)
    sig=raw&~(raw.shift(1,fill_value=False).astype(int).rolling(10,min_periods=1).max()>0)
    out[s]=[f"{i}|{'R' if rsiX[i] else ''}{'L' if lob[i] else ''}" for i in df.index[sig.values]]
    out[s+'_raw']=int(raw.sum()); out[s+'_ut']=int(UTS.sum())
print(json.dumps(out))
