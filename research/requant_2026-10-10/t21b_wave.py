# t21b:把最有資訊的「碰上緣且收盤離高≥2%」再細看:確認版、離高 3%、短線 5/10 天方向、不同買回法(限價 −3%、回測 20 日線)
import sys; sys.path.insert(0,"."); exec(open("t21_wave.py",encoding="utf-8").read().split('def sy(per)')[0])
def sy(per): a,b=PERIODS[per]; return C.loc[_pm(a,b)].notna().values.sum()/252
C5=np.roll(Cv,-5,axis=0); C5[-5:]=np.nan; C10=np.roll(Cv,-10,axis=0); C10[-10:]=np.nan
mini=UPT&(H>=UP)&(1-C/H>=0.02)
CANDS={
 "小頂K:碰上緣+收盤離高≥2%":first(mini),
 "小頂K:離高≥3%":first(UPT&(H>=UP)&(1-C/H>=0.03)),
 "小頂K+隔天收破它的低點(隔天收盤賣)":(first(mini).shift(1).fillna(False).astype(bool))&(C<L.shift(1)),
 "上升趨勢隨便一天":UPT,
}
def lim_rt(I,J,P,x=0.03,N=10):   # 賣在 P;限價 P(1−x) 買回,N 天內沒成交就第 N 天收盤買回
    filled=mn10[I,J]<=P*(1-x) if N==10 else mn20[I,J]<=P*(1-x)
    CN=C10[I,J] if N==10 else C20[I,J]
    g=np.where(filled,1/(1-x)-1,P/CN-1); return g[~np.isnan(g)]
for per in ("p1","p2"):
    a,b=PERIODS[per]; pm=_pm(a,b)
    print(f"\n[{per}]")
    for nm,mk in CANDS.items():
        M=mk.values&pm[:,None]&~np.isnan(C20)&~np.isnan(mn20); I,J=np.nonzero(M); P=Cv[I,J]
        lo5=np.nanmean(C5[I,J]<P)*100; lo10=np.nanmean(C10[I,J]<P)*100; r10=np.nanmean(C10[I,J]/P-1)*100
        g=lim_rt(I,J,P); nb=NB["回測20日線"][I,J]; ok=nb<n; g2=P[ok]/Cv[nb[ok],J[ok]]-1; g2=g2[~np.isnan(g2)]
        print(f"  {nm:24s} n={len(P):6d} | 5天後較低 {lo5:.0f}% 10天後較低 {lo10:.0f}% 10天平均 {r10:+.2f}% | 10天內低3% {np.nanmean(mn10[I,J]<=0.97*P)*100:.0f}% 漲≥10%(20天) {np.nanmean(mx20[I,J]>=1.10*P)*100:.0f}%"
              f" | 來回(限價−3%/10天) 平均{np.mean(g)*100:+.2f}% 省到{np.mean(g>0)*100:.0f}% | 來回(回測20日線) 平均{np.mean(g2)*100:+.2f}% 中位{np.median(g2)*100:+.2f}% 省到{np.mean(g2>0)*100:.0f}%",flush=True)
# 買回點本身:上升趨勢第一次回測 20 日線之後
print("\n買回點「上升趨勢第一次回測 20 日線」本身(當天收盤買):")
for per in ("p1","p2"):
    a,b=PERIODS[per]; pm=_pm(a,b); mk=BOTS["回測20日線"]
    M=mk.values&pm[:,None]&~np.isnan(C20)&~np.isnan(mn20); I,J=np.nonzero(M); P=Cv[I,J]
    M0=UPT.values&pm[:,None]&~np.isnan(C20); I0,J0=np.nonzero(M0); P0=Cv[I0,J0]
    print(f"  [{per}] n={len(P)}(每檔每年 {len(P)/sy(per):.1f})| 10天後較高 {np.nanmean(C10[I,J]>P)*100:.0f}%(隨便一天 {np.nanmean(C10[I0,J0]>P0)*100:.0f}%)| 20天後較高 {np.nanmean(C20[I,J]>P)*100:.0f}%(隨便一天 {np.nanmean(C20[I0,J0]>P0)*100:.0f}%)| 20天內再跌≥5% {np.nanmean(mn20[I,J]<=0.95*P)*100:.0f}%(隨便一天 {np.nanmean(mn20[I0,J0]<=0.95*P0)*100:.0f}%)")
