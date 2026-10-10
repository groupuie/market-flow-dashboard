# t23d:「大盤也在回檔」換不同定義,結論還成立嗎?(上升趨勢裡的隨便一天 + RSI14≤40 回檔;同一檔基準;兩段 + 四段)
from t23_dip import *
from t10lib import _pm, SP, sp20, vix
SUB4=[("2009-07-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
PER=[("2009–17",("2009-07-01","2017-12-31")),("2018–26",("2018-01-01","2026-12-31"))]+[(f"四段{k+1}",ab) for k,ab in enumerate(SUB4)]
u20=(FRC[20]>0).values.astype(float); val=~np.isnan(FRC[20].values)
def B(x): return np.repeat(np.asarray(x,dtype=bool)[:,None],len(cols),axis=1)
qhi20=Q.c.rolling(20).max(); q50=Q.c.rolling(50).mean()
MK={"QQQ 在 20 日線下":B((Q.c<q20).fillna(False)),"SPY 在 20 日線下":B((SP.c<sp20).fillna(False)),
    "QQQ 離 20 日高點 ≥3%":B((Q.c/qhi20-1<=-0.03).fillna(False)),"QQQ 離 20 日高點 ≥5%":B((Q.c/qhi20-1<=-0.05).fillna(False)),
    "QQQ 在 50 日線下":B((Q.c<q50).fillna(False)),"VIX ≥ 20":B((vix>=20).fillna(False))}
st=UT.values; rsi=first(((R14<=40)&(R14.shift(1)>40)).fillna(False).astype(bool)&UT,10).values
def sb(mask,a,b):
    pm=_pm(a,b); ok=mask&pm[:,None]&val; I,J=np.nonzero(ok)
    cnt=np.bincount(J,minlength=len(cols)); sm=np.bincount(J,weights=u20[I,J],minlength=len(cols)); bs=np.full(len(cols),np.nan)
    bs[cnt>=40]=sm[cnt>=40]/cnt[cnt>=40]; return bs,I,J
for nm,mk in MK.items():
    line=f"{nm:16s}"
    for per,(a,b) in PER:
        bs_all,_,_=sb(st,a,b); _,I1,J1=sb(st&mk,a,b); _,I0,J0=sb(st&~mk,a,b)
        d1=np.nanmean(u20[I1,J1]-bs_all[J1])*100; d0=np.nanmean(u20[I0,J0]-bs_all[J0])*100
        pm=_pm(a,b); R1=np.nonzero(rsi&mk&pm[:,None]&val); R0=np.nonzero(rsi&~mk&pm[:,None]&val)
        r1=np.nanmean(u20[R1]-bs_all[R1[1]])*100; r0=np.nanmean(u20[R0]-bs_all[R0[1]])*100
        line+=f" | {per} 隨便一天 {d1:+.1f}/{d0:+.1f} 回檔 {r1:+.1f}/{r0:+.1f}"
    print(line+"   (斜線前=大盤在跌、後=大盤沒跌;都是 20 天後較高 − 同股上升趨勢基準)",flush=True)
