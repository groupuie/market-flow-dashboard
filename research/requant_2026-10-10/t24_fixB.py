# t24(Codex v0.1 修正B):「加」排除「當日 + 前 10 根」有出(原本只排除前 10 根)。
# 259 檔:新舊事件集合差異(新增/消失的日期與原因)、新版統計(隔天開盤買,20 天後較高 vs 同一檔穩健上漲時隨便一天)。
from t23_dip import *
from t10lib import _pm
SUB4=[("2009-07-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
PER=[("2009–17",("2009-07-01","2017-12-31")),("2018–26",("2018-01-01","2026-12-31")),("近兩年",("2024-10-01","2026-12-31"))]+[(f"四段{k+1}",ab) for k,ab in enumerate(SUB4)]
rsi40=(R14<=40)&(R14.shift(1)>40); lob=(L<=lo)&above_n(L,lo,10)
Xb=X.fillna(False).astype(bool)
oldCHU=anyN(Xb,10).shift(1).fillna(False).astype(bool)                       # 舊:前 10 根 [i-10, i-1]
newCHU=Xb.astype(int).rolling(11,min_periods=1).max().astype(bool)            # 新:當日 + 前 10 根 [i-10, i]
RAW=(rsi40|lob)&UTS&qdip
ADD_old=first(RAW&~oldCHU,10); ADD_new=first(RAW&~newCHU,10)
u20=(FR[20]>0).values.astype(float); val=~np.isnan(FR[20].values)
print("### 事件差異(全期 2009-07~2026-10,259 檔)")
A=ADD_old.values; Bn=ADD_new.values; pm=_pm("2009-07-01","2026-12-31")[:,None]
rem=np.argwhere(A&~Bn&pm); add=np.argwhere(Bn&~A&pm)
print(f"  舊版 {int((A&pm).sum())} 次 → 新版 {int((Bn&pm).sum())} 次;消失 {len(rem)}、新增 {len(add)};當日同時有出的舊版事件 {int((A&Xb.values&pm).sum())}")
for i,j in rem: print(f"    消失 {dates[i].date()} {cols[j]}:當日{'有' if Xb.values[i,j] else '沒有'}出")
for i,j in add:
    k=[q for q in range(max(0,i-10),i) if A[q,j]]
    print(f"    新增 {dates[i].date()} {cols[j]}:原本被 {dates[k[0]].date() if k else '?'} 的舊版「加」以 10 根去重壓住(那根因同日出被移除)")
def sbase(a,b):
    pm=_pm(a,b); ok=UTS.values&pm[:,None]&val; I,J=np.nonzero(ok)
    cnt=np.bincount(J,minlength=len(cols)); sm=np.bincount(J,weights=u20[I,J],minlength=len(cols))
    bs=np.full(len(cols),np.nan); bs[cnt>=40]=sm[cnt>=40]/cnt[cnt>=40]; return bs
print("\n### 新版統計(隔天開盤買;括號 = 同一檔穩健上漲時隨便一天;有效樣本 = 20 天結果已完整的事件)")
for nm,S in (("舊版",ADD_old),("新版",ADD_new)):
    line=f"  {nm}"
    for per,(a,b) in PER:
        pm=_pm(a,b); M=S.values&pm[:,None]; I,J=np.nonzero(M&val); miss=int((M&~val).sum()); bs=sbase(a,b); d=u20[I,J]-bs[J]
        line+=f" | {per} {u20[I,J].mean()*100:.1f}%({np.nanmean(bs[J])*100:.1f}%,{np.nanmean(d)*100:+.1f},n{len(I)},未完成{miss})"
    print(line,flush=True)
