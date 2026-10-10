# t22d:TSM 歷來所有「使用者規則」與 頂K/減碼 的日子,之後怎麼走 + 成本調節(收盤賣、10 天內限價低 3% 買回,沒成交第 10 天買回)
import sys; sys.path.insert(0,"."); from t1x_cands import *
def runc(cond):
    c=cond.astype(int); return c.apply(lambda s: s.groupby((s==0).cumsum()).cumsum())
def first(cond,k=10):
    c=cond.fillna(False).astype(bool); return c&~c.shift(1).fillna(False).astype(int).rolling(k,min_periods=1).max().astype(bool)
sdD=C.rolling(20).std(ddof=0); UPd=S20+2*sdD
tdD=runc(C>C.shift(4)); touchD=(H>=UPd)
wk=pd.Series(dates.to_period("W-FRI"),index=dates)
Wc=C.groupby(wk.values).last(); tdW_done=runc(Wc>Wc.shift(4))
def to_days(X): return X.reindex(wk.values).set_axis(dates)
c4=to_days(Wc.shift(4)); prev=to_days(tdW_done.shift(1))
tdW=((C>c4).astype(int)*(prev.fillna(0)+1)).where(c4.notna())
S1=to_days(Wc.rolling(19).sum().shift(1)); S2=to_days((Wc**2).rolling(19).sum().shift(1))
mW=(S1+C)/20; vW=((S2+C**2)/20-mW**2).clip(lower=0); upW=mW+2*np.sqrt(vW)
cumH=H.groupby(wk.values).cummax().set_axis(dates); touchW=(cumH>=upW)
U=first((tdD>=9)&touchD&(tdW>=9)&touchW)
j=cols.index("TSM"); Cv=C.values[:,j]; Hv=H.values[:,j]; Lv=L.values[:,j]; n=len(dates)
def show(nm,s):
    print(f"\n### TSM {nm}")
    for t in np.flatnonzero(s.values[:,j]):
        if dates[t]<pd.Timestamp("2009-07-01"): continue
        P=Cv[t]; f=lambda h: f"{(Cv[t+h]/P-1)*100:+5.1f}%" if t+h<n else "  –  "
        w=Lv[t+1:t+11]; filled=np.any(w<=P*0.97) if len(w) else False
        ca="買回 −3%" if filled else (f"第10天買回 {(1-Cv[t+10]/P)*100:+.1f}%" if t+10<n else "未滿10天")
        hi=np.nanmax(Hv[t+1:t+41]) if t+1<n else np.nan; lo=np.nanmin(Lv[t+1:t+41]) if t+1<n else np.nan
        print(f"  {dates[t].date()} 收{P:8.2f} | 10天 {f(10)} 20天 {f(20)} 40天 {f(40)} | 40天內最高 {(hi/P-1)*100:+5.1f}% 最低 {(lo/P-1)*100:+5.1f}% | 成本調節:{ca}")
show("使用者規則(日+週)",U); show("頂K",TK); show("減碼",CF)
t=np.flatnonzero(dates==pd.Timestamp("2026-06-03"))[0]; k=t+1+np.nanargmin(Lv[t+1:t+41]); print("\n6/3 之後 40 天最低:",dates[k].date(),Lv[k])
