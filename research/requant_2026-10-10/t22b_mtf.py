# t22b:接 t22。(1) TSM 兩個頂附近逐日看:使用者規則、頂K 各條件;(2) 同波動基準(頂K 多在高波動股,不能直接比);
# (3) 使用者規則 + 「確認」(5 天內收盤跌破訊號日低點)會不會變準;(4) 中位數(平均數會被少數暴漲股拉高)。
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
U=first((tdD>=9)&touchD&(tdW>=9)&touchW); D=first((tdD>=9)&touchD)
def conf(sig,days=5):
    lowS=L.where(sig).ffill(limit=days); return first(C<lowS)
SIG={"使用者規則(日+週)":U,"使用者規則 → 5天內收破訊號日低點":conf(U),
     "日K TD≥9+上緣":D,"日K TD≥9+上緣 → 5天內收破低點":conf(D),
     "頂K":TK,"減碼(頂K隔天收破低點)":CF}
# ---- 結果矩陣
FRC10=FRC[10].values; FRC20=FRC[20].values; FRC40=FRC[40].values
Cv=C.values; Lv=L.values
mn10=pd.DataFrame(Lv)[::-1].rolling(10,min_periods=10).min()[::-1].shift(-1).values
C10=np.roll(Cv,-10,axis=0); C10[-10:]=np.nan
G=np.where(mn10<=Cv*0.97,1/0.97-1,Cv/C10-1)                       # 成本調節:收盤賣,10天內限價−3%買回,沒成交第10天收盤買回
r=np.log(C/C.shift(1)); vol=r.rolling(20).std().values
def sy(a,b): return C.loc[_pm(a,b)].notna().values.sum()/252
OUT={"lo10":lambda I,J:(FRC10[I,J]<0),"lo20":lambda I,J:(FRC20[I,J]<0),"lo40":lambda I,J:(FRC40[I,J]<0),
     "save":lambda I,J:(G[I,J]>0),"g":lambda I,J:G[I,J]}
for per,(a,b) in {"2009-17":("2009-07-01","2017-12-31"),"2018-26":("2018-01-01","2026-12-31")}.items():
    pm=_pm(a,b); ok=pm[:,None]&~np.isnan(FRC20)&~np.isnan(vol)&~np.isnan(G)
    edges=np.nanquantile(vol[ok],np.linspace(0,1,11)[1:-1]); bk=np.digitize(np.nan_to_num(vol),edges)   # 10 個波動分組
    I0,J0=np.nonzero(ok); B0=bk[I0,J0]
    basek={m:np.array([np.nanmean(f(I0[B0==k],J0[B0==k]).astype(float)) for k in range(10)]) for m,f in OUT.items()}
    print(f"\n[{per}] 隨便一天:10天後較低 {np.nanmean(FRC10[I0,J0]<0)*100:.0f}% 20天 {np.nanmean(FRC20[I0,J0]<0)*100:.0f}% | 20天中位數 {np.nanmedian(np.exp(FRC20[I0,J0])-1)*100:+.1f}% 40天中位數 {np.nanmedian(np.exp(FRC40[I0,J0])-1)*100:+.1f}% | 成本調節 省到 {np.mean(G[I0,J0]>0)*100:.0f}% 平均 {np.mean(G[I0,J0])*100:+.2f}%")
    for nm,s in SIG.items():
        M=s.reindex(index=dates,columns=cols).fillna(False).values&ok; I,J=np.nonzero(M); B=bk[I,J]
        def mm(m): v=OUT[m](I,J).astype(float); return np.nanmean(v)*100, np.mean(basek[m][B])*100
        l10,b10=mm("lo10"); l20,b20=mm("lo20"); l40,b40=mm("lo40"); sv,bsv=mm("save"); g,bg=mm("g")
        md20=np.nanmedian(np.exp(FRC20[I,J])-1)*100; md40=np.nanmedian(np.exp(FRC40[I,J])-1)*100
        print(f"  {nm:30s} n={len(I):5d}(每檔每年 {len(I)/sy(a,b):.2f}) 波動分組平均 {B.mean():.1f}/9 | 10天後較低 {l10:.0f}%(同波動 {b10:.0f}%) 20天 {l20:.0f}%({b20:.0f}%) 40天 {l40:.0f}%({b40:.0f}%) | 20天中位數 {md20:+.1f}% 40天中位數 {md40:+.1f}% | 成本調節 省到 {sv:.0f}%({bsv:.0f}%) 平均 {g:+.2f}%({bg:+.2f}%)",flush=True)
# ---- TSM 逐日
j=cols.index("TSM")
tr=np.maximum(H-L,np.maximum((H-C.shift()).abs(),(L-C.shift()).abs())); atr=tr.rolling(14,min_periods=10).mean()
r20=C/C.shift(20)-1; ax=(C-S20)/atr; e50=C/C.rolling(50).mean()-1; off=1-C/H
print("\n### TSM 逐日(★=使用者規則 / K=頂K / 減=減碼);熱 = 20日漲≥30% 或 離20日線≥3ATR 或 離50日線≥25%")
for lo_,hi_ in [("2026-05-18","2026-07-24"),("2026-09-14","2026-10-09")]:
    for t in np.flatnonzero((dates>=pd.Timestamp(lo_))&(dates<=pd.Timestamp(hi_))):
        d=dates[t]; g=lambda X: X.iloc[t,j]
        hot=(g(r20)>=0.30)|(g(ax)>=3)|(g(e50)>=0.25)
        tag=("★" if U.iloc[t,j] else " ")+("K" if TK.iloc[t,j] else " ")+("減" if CF.iloc[t,j] else "  ")
        print(f"  {d.date()} {tag} 收{g(C):7.2f} 高{g(H):7.2f} 低{g(L):7.2f} | 日TD{int(g(tdD)):2d} 碰日上緣{'Y' if g(touchD) else '-'} 週TD{(int(g(tdW)) if not np.isnan(g(tdW)) else -1):2d} 碰週上緣{'Y' if g(touchW) else '-'} | 20日漲{g(r20)*100:+5.1f}% 離20日線{g(ax):4.1f}ATR 離50日線{g(e50)*100:+5.1f}% 熱{'Y' if hot else '-'} 收盤離高{g(off)*100:4.1f}%")
