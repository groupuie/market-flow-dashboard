# t21:使用者要「上升通道裡的波段頂也要標」(短線/成本調節:波段頂先賣一部分、拉回再買回,核心部位續抱)。
# 只看「上升趨勢」(收盤在 50 日線上、50 日線比 10 天前高)的日子。候選「波段頂」與「買回點」各數種,
# 量:①10 天內有沒有機會比賣價低 3% 買回 ②20 天內低 5% ③20 天內漲 ≥10%(賣飛)④來回一趟:在頂賣、在下一個買回點買,省下多少成本。
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _pm
Cv,Hv,Lv=C.values,H.values,L.values; n,m=Cv.shape
UPT=((C>S50)&(S50>S50.shift(10))).fillna(False)
sd=C.rolling(20).std(ddof=0); UP=S20+2*sd; LO=S20-2*sd
tr=np.maximum(H-L,np.maximum((H-C.shift()).abs(),(L-C.shift()).abs())); ATR=tr.rolling(14,min_periods=10).mean()
rsi14=FE["rsi14"].astype(float); rsi2=FE["rsi2"].astype(float)
def runc(cond):
    c=cond.astype(int); return c.apply(lambda s: s.groupby((s==0).cumsum()).cumsum())
tds=runc(C>C.shift(4)); tdb=runc(C<C.shift(4))
def first(cond,k=5):   # 條件成立、且前 k 天都沒成立 = 一段只標第一天
    c=cond.fillna(False).astype(bool); return c&~c.shift(1).fillna(False).astype(int).rolling(k,min_periods=1).max().astype(bool)
TOPS={
 "碰布林上緣":first(UPT&(H>=UP)),
 "碰上緣且收盤離高≥2%":first(UPT&(H>=UP)&(1-C/H>=0.02)),
 "TD賣數到9":UPT&(tds==9),
 "RSI14 站上70":first(UPT&(rsi14>=70)),
 "離20日線≥2.5倍ATR":first(UPT&((C-S20)/ATR>=2.5)),
 "碰上緣且TD賣≥7":first(UPT&(H>=UP)&(tds>=7)),
}
S50up=(S50>S50.shift(10)).fillna(False)
BOTS={
 "回測20日線":first(S50up&(L<=S20)&(C.shift(1)>S20.shift(1))),
 "RSI2≤10":first(S50up&(rsi2<=10)),
 "TD買數到4":S50up&(tdb==4),
}
def fwd_min(A,h): return pd.DataFrame(A)[::-1].rolling(h,min_periods=h).min()[::-1].shift(-1).values
def fwd_max(A,h): return pd.DataFrame(A)[::-1].rolling(h,min_periods=h).max()[::-1].shift(-1).values
mn10,mn20,mx20=fwd_min(Lv,10),fwd_min(Lv,20),pd.DataFrame(Cv)[::-1].rolling(20,min_periods=20).max()[::-1].shift(-1).values
C20=np.roll(Cv,-20,axis=0); C20[-20:]=np.nan
def nextidx(B):   # 每格之後第一個買回點(30 天內),沒有 → 第 30 天
    Bv=B.values; out=np.full((n,m),-1)
    for j in range(m):
        idx=np.flatnonzero(Bv[:,j]); t=np.arange(n)
        if len(idx)==0: out[:,j]=t+30; continue
        k=np.searchsorted(idx,t,side="right")
        nb=np.where(k<len(idx),idx[np.minimum(k,len(idx)-1)],10**9)
        out[:,j]=np.where(nb-t<=30,nb,t+30)
    return out
NB={k:nextidx(v) for k,v in BOTS.items()}
def metrics(mask,per,bk):
    a,b=PERIODS[per]; pm=_pm(a,b); M=mask.values&pm[:,None]&~np.isnan(C20)&~np.isnan(mn20)
    I,J=np.nonzero(M); P=Cv[I,J]
    nb=NB[bk][I,J]; ok=nb<n; I,J,P,nb=I[ok],J[ok],P[ok],nb[ok]
    Pb=Cv[nb,J]; g=P/Pb-1; g=g[~np.isnan(g)]
    return dict(n=len(P),d3=np.nanmean(mn10[I,J]<=0.97*P)*100,d5=np.nanmean(mn20[I,J]<=0.95*P)*100,run=np.nanmean(mx20[I,J]>=1.10*P)*100,
                lo20=np.nanmean(C20[I,J]<P)*100,rt=np.nanmean(g)*100,rtmed=np.nanmedian(g)*100,rthit=np.nanmean(g>0)*100)
def sy(per): a,b=PERIODS[per]; return C.loc[_pm(a,b)].notna().values.sum()/252
bk0="回測20日線"
print("「波段頂」候選(都只看上升趨勢的日子;當天收盤賣一部分)。來回 = 之後第一個『回測20日線』買回(30 天內沒有就第 30 天買回),正 = 省下成本")
for per in ("p1","p2"):
    base_=metrics(UPT,per,bk0)
    print(f"\n[{per}] 上升趨勢隨便一天:n={base_['n']} | 10天內低3% {base_['d3']:.0f}% | 20天內低5% {base_['d5']:.0f}% | 20天內漲≥10% {base_['run']:.0f}% | 20天後較低 {base_['lo20']:.0f}% | 來回 平均{base_['rt']:+.2f}% 中位{base_['rtmed']:+.2f}% 省到 {base_['rthit']:.0f}%")
    for nm,mk in TOPS.items():
        r=metrics(mk,per,bk0)
        print(f"  {nm:16s} n={r['n']:6d}(每檔每年 {r['n']/sy(per):.1f})| 10天內低3% {r['d3']:.0f}% | 20天內低5% {r['d5']:.0f}% | 漲≥10% {r['run']:.0f}% | 20天後較低 {r['lo20']:.0f}% | 來回 平均{r['rt']:+.2f}% 中位{r['rtmed']:+.2f}% 省到 {r['rthit']:.0f}%",flush=True)
print("\n買回點換別種(波段頂固定用「碰布林上緣」)")
for per in ("p1","p2"):
    for bk in BOTS:
        r=metrics(TOPS["碰布林上緣"],per,bk); b0=metrics(UPT,per,bk)
        print(f"  [{per}] 買回={bk:8s} 來回 平均{r['rt']:+.2f}% 中位{r['rtmed']:+.2f}% 省到 {r['rthit']:.0f}% | 隨便一天賣 平均{b0['rt']:+.2f}% 省到 {b0['rthit']:.0f}%",flush=True)
