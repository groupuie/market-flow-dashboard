# t21c:小頂K 在「資金偏緊」或「大盤已跌破 20 日線」時,短線有沒有比較準?
import sys; sys.path.insert(0,"."); src=open("t21b_wave.py",encoding="utf-8").read(); exec(src.split("CANDS={")[0]); exec("def lim_rt"+src.split("def lim_rt")[1].split("for per in")[0])
mini1=first(UPT&(H>=UP)&(1-C/H>=0.02))
QB=pd.DataFrame(np.repeat((Q.c<q20).reindex(dates).fillna(False).values[:,None],len(cols),axis=1),index=dates,columns=cols)
CANDS={"小頂K(全部)":mini1,"小頂K × 資金偏緊":mini1&(CL<=0.35),"小頂K × 大盤已跌破20日線":mini1&QB,"小頂K × 資金寬鬆":mini1&(CL>=0.65),
       "上升趨勢隨便一天 × 資金偏緊":UPT&(CL<=0.35),"上升趨勢隨便一天 × 大盤跌破20日線":UPT&QB}
for per in ("p1","p2"):
    a,b=PERIODS[per]; pm=_pm(a,b); print(f"\n[{per}]")
    for nm,mk in CANDS.items():
        M=mk.values&pm[:,None]&~np.isnan(C20)&~np.isnan(mn20); I,J=np.nonzero(M); P=Cv[I,J]
        g=lim_rt(I,J,P)
        print(f"  {nm:22s} n={len(P):6d} | 5天後較低 {np.nanmean(C5[I,J]<P)*100:.0f}% 10天後較低 {np.nanmean(C10[I,J]<P)*100:.0f}% 10天平均 {np.nanmean(C10[I,J]/P-1)*100:+.2f}% | 10天內低3% {np.nanmean(mn10[I,J]<=0.97*P)*100:.0f}% | 來回(限價−3%) 平均{np.mean(g)*100:+.2f}% 省到{np.mean(g>0)*100:.0f}%",flush=True)
