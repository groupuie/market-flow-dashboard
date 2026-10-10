# t25 補正:「加」第二筆的統計(再跌深度、掛低 5%/8% 成交率)原本在 t23g 第 (4) 段是用「上升趨勢」版(UT)算的,
# 上線版是「穩健上漲」(UTS)。這裡兩版並列(都已含修正 B:當日 + 前 10 根有出不標),隔天開盤買、20 天內。
from t23_dip import *
from t10lib import _pm
rsi40=(R14<=40)&(R14.shift(1)>40); lob=(L<=lo)&above_n(L,lo,10)
recentCHU=X.fillna(False).astype(bool).astype(int).rolling(11,min_periods=1).max().astype(bool)
u20=(FR[20]>0).values.astype(float); val=~np.isnan(FR[20].values); O1v=O.shift(-1).values; Cv=C.values; n=len(dates)
Lmin20=L[::-1].rolling(20,min_periods=20).min()[::-1].shift(-1).values
v20=np.log(C).diff().rolling(20).std().values
pm=_pm("2018-01-01","2026-12-31"); okU=UT.values&pm[:,None]&~np.isnan(v20); th=np.nanmedian(v20[okU])
print(f"2018–26 上升趨勢日的日報酬標準差中位數 {th*100:.2f}%(上線用固定門檻 2%)")
for nm,state in (("上升趨勢版(t23g 原本用的)",UT),("穩健上漲版(上線)",UTS)):
    S=first(((rsi40|lob)&state&qdip&~recentCHU),10)
    for thr_nm,thr in (("中位數門檻",th),("固定 2%",0.02)):
        M=S.values&pm[:,None]&val&~np.isnan(v20); I,J=np.nonzero(M); p1=O1v[I,J]; lw=Lmin20[I,J]; C20=Cv[np.minimum(I+20,n-1),J]; vv=v20[I,J]
        print(f"\n## {nm} · {thr_nm}(2018–26,隔天開盤買,20 天結果完整的事件)")
        for tag,m in (("穩(≤門檻)",vv<=thr),("波動大(>門檻)",vv>thr)):
            dd=lw[m]/p1[m]-1; q=np.nanpercentile(dd,[50,25]); s=f"  {tag:10s} n={m.sum():4d} 20 天後較高 {u20[I[m],J[m]].mean()*100:.0f}% | 之後最多再跌:一半 ≤{-q[0]*100:.1f}%、1/4 ≥{-q[1]*100:.1f}%"
            for X_ in (0.05,0.08):
                lim=p1[m]*(1-X_); got=lw[m]<=lim; avg=(p1[m]+np.where(got,lim,C20[m]))/2
                s+=f" | 掛低{int(X_*100)}%:成交 {np.nanmean(got)*100:.0f}% 平均成本 {np.nanmean(avg/p1[m]-1)*100:+.1f}%"
            print(s,flush=True)
