# t23g:定案前最後檢查 ——(1)前 10 根有「出」就不標 (2)上升趨勢 vs 穩健上升(多頭排列+40 天內創一年新高)哪個好
# (3)每一檔各自看:有幾成股票「加」比它自己平常好 (4)第二筆掛低 5% 或 8%:用固定的波動門檻(前端能算)分
from t23_dip import *
from t10lib import _pm
SUB4=[("2009-07-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
PER=[("2009–17",("2009-07-01","2017-12-31")),("2018–26",("2018-01-01","2026-12-31")),("近兩年",("2024-10-01","2026-12-31"))]+[(f"四段{k+1}",ab) for k,ab in enumerate(SUB4)]
rsi40=(R14<=40)&(R14.shift(1)>40); lob=(L<=lo)&above_n(L,lo,10)
recentCHU=anyN(X.astype(bool),10).shift(1).fillna(False).astype(bool)
u20=(FR[20]>0).values.astype(float); val=~np.isnan(FR[20].values); O1v=O.shift(-1).values; Cv=C.values; n=len(dates)
Lmin20=L[::-1].rolling(20,min_periods=20).min()[::-1].shift(-1).values
v20=np.log(C).diff().rolling(20).std().values                      # 前端可算:近 20 天日報酬標準差
def sbase(state,a,b):
    pm=_pm(a,b); ok=state.values&pm[:,None]&val; I,J=np.nonzero(ok)
    cnt=np.bincount(J,minlength=len(cols)); sm=np.bincount(J,weights=u20[I,J],minlength=len(cols))
    bs=np.full(len(cols),np.nan); bs[cnt>=40]=sm[cnt>=40]/cnt[cnt>=40]; return bs
VERS={"上升趨勢 · 前10根有出也標":(UT,first(((rsi40|lob)&UT&qdip),10)),
      "上升趨勢 · 前10根有出不標(上線版)":(UT,first(((rsi40|lob)&UT&qdip&~recentCHU),10)),
      "穩健上升 · 前10根有出不標":(UTS,first(((rsi40|lob)&UTS&qdip&~recentCHU),10))}
for nm,(state,S) in VERS.items():
    line=f"{nm:26s}"
    for per,(a,b) in PER:
        pm=_pm(a,b); M=S.values&pm[:,None]&val; I,J=np.nonzero(M); bs=sbase(state,a,b); d=u20[I,J]-bs[J]
        line+=f" | {per} {u20[I,J].mean()*100:.0f}%({np.nanmean(bs[J])*100:.0f}%,{np.nanmean(d)*100:+.1f},n{len(I)})"
    pm=_pm("2018-01-01","2026-12-31"); yrs=(state.values&pm[:,None]&val).sum()/252
    print(line+f" | 每檔每個上升趨勢年 {(S.values&pm[:,None]&val).sum()/yrs:.2f} 次",flush=True)
# (3) 每一檔
state,S=VERS["上升趨勢 · 前10根有出不標(上線版)"]
for per,(a,b) in PER[:2]:
    pm=_pm(a,b); bs=sbase(state,a,b); M=S.values&pm[:,None]&val; I,J=np.nonzero(M)
    better=[];
    for j in np.unique(J):
        s=J==j
        if s.sum()>=5 and not np.isnan(bs[j]): better.append(u20[I[s],j].mean()>bs[j])
    print(f"\n[{per}] 至少 5 次的股票 {len(better)} 檔:「加」比自己平常好的 {np.mean(better)*100:.0f}%")
# (4) 固定波動門檻
pm=_pm("2018-01-01","2026-12-31"); okU=UT.values&pm[:,None]&~np.isnan(v20)
th=np.nanmedian(v20[okU]); print(f"\n上升趨勢日的日報酬標準差中位數(2018–26):{th*100:.2f}%  → 以此分「穩」與「波動大」")
M=S.values&pm[:,None]&val&~np.isnan(v20); I,J=np.nonzero(M); p1=O1v[I,J]; lw=Lmin20[I,J]; C20=Cv[np.minimum(I+20,n-1),J]; vv=v20[I,J]
for tag,m in (("穩(≤門檻)",vv<=th),("波動大(>門檻)",vv>th)):
    dd=lw[m]/p1[m]-1; q=np.nanpercentile(dd,[50,25]); s=f"  {tag:10s} n={m.sum():4d} 20 天後較高 {u20[I[m],J[m]].mean()*100:.0f}% | 之後最多再跌:一半 ≤{-q[0]*100:.1f}%、1/4 ≥{-q[1]*100:.1f}%"
    for X_ in (0.05,0.08):
        lim=p1[m]*(1-X_); got=lw[m]<=lim; avg=(p1[m]+np.where(got,lim,C20[m]))/2
        s+=f" | 掛低{int(X_*100)}%:成交 {np.nanmean(got)*100:.0f}% 平均成本 {np.nanmean(avg/p1[m]-1)*100:+.1f}%"
    print(s)
j=cols.index("TSM"); print(f"\nTSM 近 20 天日報酬標準差(2026-10-08):{v20[-1,j]*100:.2f}%" if not np.isnan(v20[-1,j]) else "")
