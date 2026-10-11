# t26(Codex v0.2 第 4.3 節):上線版「加」(穩健上漲 UTS,含修正 B)逐股證據 —— 與 t23h 同一套算法,另外列出每一檔的數字
#   每一檔:事件 = 「加」且 20 天結果已完整;至少 5 次才比較;基準 = 同一檔在穩健上漲(UTS)期間 20 天結果已完整的日子(至少 40 天)
#   比較:事件「20 天後比隔天開盤價高」的比例 > 基準比例 → 算「比自己平常好」;隔天開盤買
from t23_dip import *
from t10lib import _pm
rsi40=(R14<=40)&(R14.shift(1)>40); lob=(L<=lo)&above_n(L,lo,10)
recentCHU=X.fillna(False).astype(bool).astype(int).rolling(11,min_periods=1).max().astype(bool)
ADD=first(((rsi40|lob)&UTS&qdip&~recentCHU),10)
u20=(FR[20]>0).values.astype(float); val=~np.isnan(FR[20].values)
for per,(a,b) in [("2009–17",("2009-07-01","2017-12-31")),("2018–26",("2018-01-01","2026-12-31"))]:
    pm=_pm(a,b); ok=UTS.values&pm[:,None]&val; I0,J0=np.nonzero(ok)
    cnt=np.bincount(J0,minlength=len(cols)); sm=np.bincount(J0,weights=u20[I0,J0],minlength=len(cols)); bs=np.where(cnt>=40,sm/np.maximum(cnt,1),np.nan)
    M=ADD.values&pm[:,None]&val; I,J=np.nonzero(M); rows=[]
    for j in np.unique(J):
        s=J==j; k=int(s.sum())
        rows.append((cols[j],k,u20[I[s],j].mean()*100,bs[j]*100 if not np.isnan(bs[j]) else np.nan,int(cnt[j])))
    q=[r for r in rows if r[1]>=5 and not np.isnan(r[3])]; better=[r for r in q if r[2]>r[3]]
    print(f"\n[{per}] 有出現「加」的股票 {len(rows)} 檔;至少 5 次且基準夠(≥40 天)的 {len(q)} 檔;比自己平常好的 {len(better)} 檔 = {len(better)/len(q)*100:.0f}%")
    print(f"  事件數分布(合格的):中位數 {np.median([r[1] for r in q]):.0f} 次、最少 {min(r[1] for r in q)}、最多 {max(r[1] for r in q)}")
    print("  代號 | 加的次數 | 20天後較高 | 同股穩健上漲時平常 | 平常的天數")
    for r in sorted(q,key=lambda r:r[2]-r[3]): print(f"  {r[0]:6s} | {r[1]:3d} | {r[2]:5.1f}% | {r[3]:5.1f}% | {r[4]}")
