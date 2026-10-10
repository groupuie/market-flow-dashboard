# t22:使用者的假設 —— 日K TD賣 9–13 + 碰布林上緣,再加 週K TD賣 ≥9 + 週K 碰布林上緣 → 抓得到 TSM 這種頂?
# 週K 一律「截至當天」計算(本週還沒收完就用到今天為止的週K),不偷看未來。當晚收盤賣。
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _pm
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
tdW=((C>c4).astype(int)*(prev.fillna(0)+1)).where(c4.notna())          # 週 TD 賣(截至當天)
S1=to_days(Wc.rolling(19).sum().shift(1)); S2=to_days((Wc**2).rolling(19).sum().shift(1))
mW=(S1+C)/20; vW=((S2+C**2)/20-mW**2).clip(lower=0); upW=mW+2*np.sqrt(vW)
cumH=H.groupby(wk.values).cummax().set_axis(dates)
touchW=(cumH>=upW)
SIG={
 "日K TD賣≥9 + 碰上緣":first((tdD>=9)&touchD),
 "日K TD賣 9–13 + 碰上緣":first((tdD>=9)&(tdD<=13)&touchD),
 "…再加 週K TD賣≥9":first((tdD>=9)&touchD&(tdW>=9)),
 "…再加 週K 碰上緣":first((tdD>=9)&touchD&touchW),
 "日+週 全部(使用者的規則)":first((tdD>=9)&touchD&(tdW>=9)&touchW),
 "只看週K:TD賣≥9 + 碰上緣":first((tdW>=9)&touchW),
 "頂K(對照,現行)":TK,
}
FRC40=FRC[40].values; FRC20=FRC[20].values; FRC10=FRC[10].values; M40=MAEC[40].values
Cv=C.values; n=len(dates); L_=L.values
mn10=pd.DataFrame(L_)[::-1].rolling(10,min_periods=10).min()[::-1].shift(-1).values
C10=np.roll(Cv,-10,axis=0); C10[-10:]=np.nan
def sy(a,b): return C.loc[_pm(a,b)].notna().values.sum()/252
def stats(mask,a,b):
    pm=_pm(a,b); M=mask.reindex(index=dates,columns=cols).fillna(False).values&pm[:,None]&~np.isnan(FRC20)
    I,J=np.nonzero(M); P=Cv[I,J]
    obs=lambda v,f: f(v[~np.isnan(v)]).mean()*100 if (~np.isnan(v)).any() else np.nan   # 2026-10-11 修正D:未完成的 40 日不算「沒跌/沒變低」
    lo10=obs(FRC10[I,J],lambda v:v<0); lo20=obs(FRC20[I,J],lambda v:v<0); lo40=obs(FRC40[I,J],lambda v:v<0)
    dd=obs(M40[I,J],lambda v:v<=np.log(0.9)); m40=np.nanmean(np.exp(FRC40[I,J])-1)*100
    g=np.where(mn10[I,J]<=P*0.97,1/0.97-1,P/C10[I,J]-1); g=g[~np.isnan(g)]
    return len(P),lo10,lo20,lo40,dd,m40,np.mean(g)*100,np.mean(g>0)*100
for per,(a,b) in {"2009-17":("2009-07-01","2017-12-31"),"2018-26":("2018-01-01","2026-12-31")}.items():
    allD=pd.DataFrame(True,index=dates,columns=cols)&C.notna()
    n0,b10,b20,b40,bdd,bm40,brt,brh=stats(allD,a,b)
    print(f"\n[{per}] 隨便一天(收盤賣):10天後較低 {b10:.0f}% 20天 {b20:.0f}% 40天 {b40:.0f}% | 40天內跌≥10% {bdd:.0f}% | 40天平均 {bm40:+.1f}% | 成本調節(限價−3%/10天)平均 {brt:+.2f}% 省到 {brh:.0f}%")
    for nm,s in SIG.items():
        k,l10,l20,l40,dd,m40,rt,rh=stats(s,a,b)
        print(f"  {nm:24s} n={k:5d}(每檔每年 {k/sy(a,b):.2f})| 10天後較低 {l10:.0f}% 20天 {l20:.0f}% 40天 {l40:.0f}% | 40天內跌≥10% {dd:.0f}% | 40天平均 {m40:+.1f}% | 成本調節 平均 {rt:+.2f}% 省到 {rh:.0f}%",flush=True)
print("\n### TSM:使用者規則(日+週全部)觸發的日子與之後")
j=cols.index("TSM"); s=SIG["日+週 全部(使用者的規則)"]["TSM"]
for t in np.flatnonzero(s.values):
    if dates[t]<pd.Timestamp("2023-01-01"): continue
    P=Cv[t,j]; f=lambda h: (Cv[t+h,j]/P-1)*100 if t+h<n else np.nan
    lo=(np.nanmin(L_[t+1:t+41,j])/P-1)*100 if t+1<n else np.nan; hi=(np.nanmax(H.values[t+1:t+41,j])/P-1)*100 if t+1<n else np.nan
    print(f"  {dates[t].date()} 收 {P:7.2f} | 10天 {f(10):+5.1f}% 20天 {f(20):+5.1f}% 40天 {f(40):+5.1f}% | 40天內最低 {lo:+5.1f}% 最高 {hi:+5.1f}%")
