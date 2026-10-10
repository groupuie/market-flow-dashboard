# t22c:「漲多就是要跌?」直接看:按 20 日漲幅 / 離 50 日線 分組的「之後較低」比例;
# 再用「同波動 × 同漲幅」雙重配對基準比 使用者規則 / 頂K / 減碼(拆開「漲很多、波動大」本身 和 訊號 的功勞)。
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
U=first((tdD>=9)&touchD&(tdW>=9)&touchW)
SIG={"使用者規則(日+週)":U,"頂K":TK,"減碼":CF}
FRC10=FRC[10].values; FRC20=FRC[20].values; FRC40=FRC[40].values
lt0=lambda v: np.where(np.isnan(v),np.nan,v<0)   # 2026-10-11 修正D:40 日未完成=NaN(不算「沒變低」)
r20=(C/C.shift(20)-1).values; e50=(C/C.rolling(50).mean()-1).values
vol=np.log(C/C.shift(1)).rolling(20).std().values
for per,(a,b) in {"2009-17":("2009-07-01","2017-12-31"),"2018-26":("2018-01-01","2026-12-31")}.items():
    pm=_pm(a,b); ok=pm[:,None]&~np.isnan(FRC20)&~np.isnan(vol)&~np.isnan(r20)&~np.isnan(e50)
    I0,J0=np.nonzero(ok)
    print(f"\n[{per}] 全部 {len(I0)} 個股票日:10天後較低 {np.mean(FRC10[I0,J0]<0)*100:.0f}% 20天 {np.mean(FRC20[I0,J0]<0)*100:.0f}%")
    print("  ① 20 日漲幅分組(收盤賣,之後較低的比例 / 20 天中位數):")
    q=np.nanquantile(r20[ok],[0.2,0.4,0.6,0.8,0.95,0.99])
    lab=["最低 20%","20–40%","40–60%","60–80%","80–95%","95–99%","最高 1%"]
    br=np.digitize(r20[I0,J0],q)
    for k in range(7):
        s=br==k; I,J=I0[s],J0[s]
        print(f"    {lab[k]:9s}(20日漲幅 {np.min(r20[I,J])*100:+6.1f}%~{np.max(r20[I,J])*100:+6.1f}%):10天後較低 {np.mean(FRC10[I,J]<0)*100:.0f}% 20天 {np.mean(FRC20[I,J]<0)*100:.0f}% 40天 {np.nanmean(lt0(FRC40[I,J]))*100:.0f}% | 20天中位數 {np.median(np.exp(FRC20[I,J])-1)*100:+.1f}%")
    print("  ② 離 50 日線:")
    for lo_,hi_ in [(-9,0),(0,0.10),(0.10,0.15),(0.15,0.25),(0.25,0.40),(0.40,99)]:
        s=(e50[I0,J0]>=lo_)&(e50[I0,J0]<hi_); I,J=I0[s],J0[s]
        print(f"    {lo_*100:+4.0f}%~{hi_*100:+4.0f}%  n={len(I):7d}:10天後較低 {np.mean(FRC10[I,J]<0)*100:.0f}% 20天 {np.mean(FRC20[I,J]<0)*100:.0f}% | 20天中位數 {np.median(np.exp(FRC20[I,J])-1)*100:+.1f}%")
    # 雙重配對:波動 10 組 × 20日漲幅 7 組
    qv=np.nanquantile(vol[ok],np.linspace(0,1,11)[1:-1]); bv=np.digitize(vol[I0,J0],qv)
    cell=bv*7+br
    base10=np.array([np.mean(FRC10[I0[cell==c],J0[cell==c]]<0) if np.any(cell==c) else np.nan for c in range(70)])
    base20=np.array([np.mean(FRC20[I0[cell==c],J0[cell==c]]<0) if np.any(cell==c) else np.nan for c in range(70)])
    base40=np.array([np.nanmean(lt0(FRC40[I0[cell==c],J0[cell==c]])) if np.any(cell==c) else np.nan for c in range(70)])
    CI=np.full(FRC20.shape,-1); CI[I0,J0]=cell
    print("  ③ 訊號 vs「同波動、同漲幅」的隨便一天:")
    for nm,s in SIG.items():
        M=s.reindex(index=dates,columns=cols).fillna(False).values&ok; I,J=np.nonzero(M); c=CI[I,J]
        print(f"    {nm:12s} n={len(I):5d} | 10天後較低 {np.mean(FRC10[I,J]<0)*100:.0f}%(配對 {np.nanmean(base10[c])*100:.0f}%) 20天 {np.mean(FRC20[I,J]<0)*100:.0f}%({np.nanmean(base20[c])*100:.0f}%) 40天 {np.nanmean(lt0(FRC40[I,J]))*100:.0f}%({np.nanmean(base40[c][~np.isnan(FRC40[I,J])])*100:.0f}%)")
