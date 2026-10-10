# t22e:上線版「熱」的確切定義 → 統計數字(給 tooltip)。
#   日K:TD 賣方連數 9–13(使用者:「TD9-13」)且 今天最高 ≥ 布林上緣(20 日、2 倍母體標準差)
#   週K:截至當天的週 TD 賣方連數 ≥9 且 本週到今天的最高 ≥ 週布林上緣(19 個完整週 + 本週到今天的收盤)
#   同一段只標第一天(前 10 根有成立過就不標)。對照:日K TD≥9(t22 的版本)。
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
tdW=((C>c4).astype(int)*(prev.fillna(0)+1)).where(c4.notna())
S1=to_days(Wc.rolling(19).sum().shift(1)); S2=to_days((Wc**2).rolling(19).sum().shift(1))
mW=(S1+C)/20; vW=((S2+C**2)/20-mW**2).clip(lower=0); upW=mW+2*np.sqrt(vW)
cumH=H.groupby(wk.values).cummax().set_axis(dates); touchW=(cumH>=upW)
SIG={"熱(上線版:日TD 9–13)":first((tdD>=9)&(tdD<=13)&touchD&(tdW>=9)&touchW),
     "t22 版(日TD≥9)":first((tdD>=9)&touchD&(tdW>=9)&touchW)}
FRC10=FRC[10].values; FRC20=FRC[20].values; FRC40=FRC[40].values; Cv=C.values; Lv=L.values
mn10=pd.DataFrame(Lv)[::-1].rolling(10,min_periods=10).min()[::-1].shift(-1).values
C10=np.roll(Cv,-10,axis=0); C10[-10:]=np.nan
G=np.where(mn10<=Cv*0.97,1/0.97-1,Cv/C10-1)
vol=np.log(C/C.shift(1)).rolling(20).std().values
def sy(a,b): return C.loc[_pm(a,b)].notna().values.sum()/252
for per,(a,b) in {"2009-17":("2009-07-01","2017-12-31"),"2018-26":("2018-01-01","2026-12-31"),"近兩年 2024-10~":("2024-10-01","2026-12-31")}.items():
    pm=_pm(a,b); ok=pm[:,None]&~np.isnan(FRC10)&~np.isnan(vol)
    qv=np.nanquantile(vol[ok],np.linspace(0,1,11)[1:-1]); bk=np.digitize(np.nan_to_num(vol),qv)
    I0,J0=np.nonzero(ok); B0=bk[I0,J0]
    b10=np.array([np.mean(FRC10[I0[B0==k],J0[B0==k]]<0) for k in range(10)])
    okG=ok&~np.isnan(G); I1,J1=np.nonzero(okG); B1=bk[I1,J1]
    bG=np.array([np.mean(G[I1[B1==k],J1[B1==k]]>0) for k in range(10)])
    print(f"\n[{per}] 隨便一天 10天後較低 {np.mean(FRC10[I0,J0]<0)*100:.0f}%")
    for nm,s in SIG.items():
        M=s.reindex(index=dates,columns=cols).fillna(False).values&ok; I,J=np.nonzero(M); Bk=bk[I,J]
        m20=~np.isnan(FRC20[I,J]); mg=~np.isnan(G[I,J])
        print(f"  {nm:18s} n={len(I):4d}(每檔每年 {len(I)/sy(a,b):.2f})| 10天後較低 {np.mean(FRC10[I,J]<0)*100:.0f}%(同波動 {np.mean(b10[Bk])*100:.0f}%)"
              f" 20天 {np.mean(FRC20[I,J][m20]<0)*100:.0f}% | 掛低3%買回成功 {np.mean(G[I,J][mg]>0)*100:.0f}%(同波動 {np.mean(bG[Bk[mg]])*100:.0f}%)")
j=cols.index("TSM"); s=SIG["熱(上線版:日TD 9–13)"]["TSM"]
print("\nTSM 熱:",[str(d.date()) for d in dates[np.flatnonzero(s.values)] if d>=pd.Timestamp("2009-07-01")])
