# t20b:「出」的漲多門檻 15% → 10%(TSM 這波最多只高於 50 日線 14.1%,所以就算跌破 20 日線也不會出)。準確率、強弱分級、次數比較。
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel, _pm
BIGDN=ret1<=-0.04; PRETK=anyN(TK.shift(1),20); MACD_=OILW|YDROP
PER={"2009-17":("2009-07-01","2017-12-31"),"2018-26":("2018-01-01","2026-12-31"),"近兩年":("2024-10-01","2026-12-31")}
def styrs(a,b): return C.loc[_pm(a,b)].notna().values.sum()/252
for thr in (0.15,0.10):
    d=ev(chu(thr=thr),"open"); st=samp(MACD_,d)|samp(BIGDN|PRETK,d)
    print(f"\n### 出 門檻 {thr:.0%}")
    for pn,(a,b) in PER.items():
        sel=_sel(d,20,(a,b)); f=d.f20.values; bs=base("top","open",20,(a,b)); sy=styrs(a,b)
        n_all=int(((d.date>=a)&(d.date<=b)).sum())
        g=lambda m: (np.mean(f[sel&m]<0)*100, int((sel&m).sum()))
        A,S_,W=g(np.ones(len(d),bool)),g(st),g(~st)
        print(f"  {pn}: {n_all} 次(每檔每年 {n_all/sy:.2f})| 全部 {A[0]:.1f}% | 強 {S_[0]:.1f}%(n{S_[1]}) | 灰 {W[0]:.1f}%(n{W[1]}) | 平常 {bs:.1f}%")
# 只在 10–15% 之間才會多出來的那些「出」
d10=ev(chu(thr=0.10)&~anyN(chu(thr=0.15),3),"open"); st=samp(MACD_,d10)|samp(BIGDN|PRETK,d10)
print("\n### 只有門檻降到 10% 才會多出來的「出」")
for pn,(a,b) in PER.items():
    sel=_sel(d10,20,(a,b)); f=d10.f20.values; bs=base("top","open",20,(a,b))
    print(f"  {pn}: n={int(sel.sum())} 準 {np.mean(f[sel]<0)*100:.1f}% | 強 {np.mean(f[sel&st]<0)*100:.1f}%(n{int((sel&st).sum())}) | 灰 {np.mean(f[sel&~st]<0)*100:.1f}%(n{int((sel&~st).sum())}) | 平常 {bs:.1f}%")
