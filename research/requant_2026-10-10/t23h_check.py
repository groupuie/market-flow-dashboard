# t23h:穩健上升版「加」—— 每一檔各自看、幾檔股票會出現、MSFT/META/TSM/NVDA 2024 年後
from t23_dip import *
from t10lib import _pm
rsi40=(R14<=40)&(R14.shift(1)>40); lob=(L<=lo)&above_n(L,lo,10)
recentCHU=anyN(X.astype(bool),10).shift(1).fillna(False).astype(bool)
ADD=first(((rsi40|lob)&UTS&qdip&~recentCHU),10)
u20=(FR[20]>0).values.astype(float); val=~np.isnan(FR[20].values); O1v=O.shift(-1).values; Cv=C.values; n=len(dates)
for per,(a,b) in [("2009–17",("2009-07-01","2017-12-31")),("2018–26",("2018-01-01","2026-12-31"))]:
    pm=_pm(a,b); ok=UTS.values&pm[:,None]&val; I0,J0=np.nonzero(ok)
    cnt=np.bincount(J0,minlength=len(cols)); sm=np.bincount(J0,weights=u20[I0,J0],minlength=len(cols)); bs=np.where(cnt>=40,sm/np.maximum(cnt,1),np.nan)
    M=ADD.values&pm[:,None]&val; I,J=np.nonzero(M); better=[]
    for j in np.unique(J):
        s=J==j
        if s.sum()>=5 and not np.isnan(bs[j]): better.append(u20[I[s],j].mean()>bs[j])
    print(f"[{per}] 至少 5 次的股票 {len(better)} 檔:比自己平常好的 {np.mean(better)*100:.0f}%;出現過的股票 {len(np.unique(J))} 檔")
pm=_pm("2024-01-01","2026-12-31")
for sym in ("TSM","NVDA","AVGO","MU","AAPL","META","MSFT","AMZN","GOOGL"):
    if sym not in cols: continue
    j=cols.index(sym); ts=[t for t in np.flatnonzero(ADD[sym].values) if dates[t]>=pd.Timestamp("2024-01-01") and t+20<n]
    r=[(Cv[t+20,j]/O1v[t,j]-1)*100 for t in ts]
    print(f"  {sym:5s} {len(ts):2d} 次,20 天後較高 {sum(x>0 for x in r)} 次:"+" ".join(f"{x:+.0f}" for x in r))
