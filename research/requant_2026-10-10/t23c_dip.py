# t23c:拆功勞 —— 「大盤回檔時加碼比較好」是因為大盤回檔本身(那幾天隨便買都好),還是個股回檔也有加分?
# 基準改成「同一檔、同樣上升趨勢、同樣大盤狀態(QQQ 在 20 日線下 / 上)的隨便一天」。再看候選組合的頻率、四段、TSM 每一次。
from t23_dip import *
from t10lib import _pm
rng=np.random.default_rng(2)
SUB4=[("2009-07-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
PER={"2009–17":("2009-07-01","2017-12-31"),"2018–26":("2018-01-01","2026-12-31"),"近兩年":("2024-10-01","2026-12-31")}
u20=(FRC[20]>0).values.astype(float); u40=(FRC[40]>0).values.astype(float); val=~np.isnan(FRC[20].values); val40=~np.isnan(FRC[40].values)
QD=qdip.values
def sbase(state_np,a,b,Y=u20,V=val):
    pm=_pm(a,b); ok=state_np&pm[:,None]&V; I0,J0=np.nonzero(ok); bs=np.full(len(cols),np.nan)
    cnt=np.bincount(J0,minlength=len(cols)); sm=np.bincount(J0,weights=Y[I0,J0],minlength=len(cols))
    bs[cnt>=40]=sm[cnt>=40]/cnt[cnt>=40]; return bs,ok
def ci(I,d,B=400):
    blk=I//20; ub=np.unique(blk); m={b:d[blk==b] for b in ub}
    bt=[np.concatenate([m[b] for b in rng.choice(ub,len(ub))]).mean() for _ in range(B)]; return np.percentile(bt,[5,95])
for stname,state in {"上升趨勢":UT,"穩健上升":UTS}.items():
    st=state.values
    print(f"\n######## {stname}")
    for per,(a,b) in PER.items():
        bA,okA=sbase(st&QD,a,b); bB,okB=sbase(st&~QD,a,b); ball,_=sbase(st,a,b)
        I,J=np.nonzero(okA); IB,JB=np.nonzero(okB)
        print(f"[{per}] 隨便一天 20天後較高:大盤在20日線下 {u20[I,J].mean()*100:.0f}%(天數佔 {len(I)/(len(I)+len(IB))*100:.0f}%)/ 大盤在線上 {u20[IB,JB].mean()*100:.0f}%")
for stname,state in {"上升趨勢":UT,"穩健上升":UTS}.items():
    st=state.values
    print(f"\n######## {stname}:訊號 vs「同一檔、同大盤狀態」的隨便一天(20 天後較高的差,90% CI)")
    SG={"③a 第一次碰布林中軌":touch_mid,"②a 碰 50 日線":T(t50),"②c 碰 100 日線":T(t100),"②e 碰第二條 CTA 線":T(sec),
        "④ 第一次碰週布林中軌":(L<=wmid)&above_n(L,wmid,20),"⑤ 碰布林下緣":(L<=lo)&above_n(L,lo,10),
        "⑧ RSI14≤40":(R14<=40)&(R14.shift(1)>40),"⑧' RSI14≤35":(R14<=35)&(R14.shift(1)>35)}
    for nm,s in SG.items():
        S_=first(s.fillna(False).astype(bool)&state,10).values
        line=f"  {nm:16s}"
        for per,(a,b) in PER.items():
            pm=_pm(a,b)
            for tag,mk in (("大盤也跌",QD),("只有個股",~QD)):
                bs,_=sbase(st&mk,a,b); M=S_&mk&pm[:,None]&val; I,J=np.nonzero(M); d=u20[I,J]-bs[J]; k=~np.isnan(d)
                c=ci(I[k],d[k]) if k.sum()>=20 else (np.nan,np.nan)
                line+=f" | {per}{tag} {u20[I,J].mean()*100:.0f}%({np.nanmean(d)*100:+.1f}[{c[0]*100:+.0f},{c[1]*100:+.0f}]n{len(I)})"
        print(line,flush=True)
# ---- 候選:穩健上升 + 大盤也在回檔 + 個股跌到 RSI14≤35/40 或 碰布林下緣 ----
print("\n######## 候選組合(穩健上升 + 大盤 QQQ 在 20 日線下):四段、40 天、頻率")
CAND={"RSI14≤40 且大盤也跌":((R14<=40)&(R14.shift(1)>40))&qdip,"RSI14≤35 且大盤也跌":((R14<=35)&(R14.shift(1)>35))&qdip,
      "碰布林下緣 且大盤也跌":((L<=lo)&above_n(L,lo,10))&qdip,"碰週中軌 且大盤也跌":((L<=wmid)&above_n(L,wmid,20))&qdip}
for nm,s in CAND.items():
    for stname,state in {"上升趨勢":UT,"穩健上升":UTS}.items():
        st=state.values; S_=first(s.fillna(False).astype(bool)&state,10).values; line=f"  {nm:16s}[{stname}]"
        for per,(a,b) in list(PER.items())+[(f"四段{k+1}",ab) for k,ab in enumerate(SUB4)]:
            pm=_pm(a,b); bs,okb=sbase(st,a,b); bs40,_=sbase(st,a,b,u40,val40)
            M=S_&pm[:,None]&val; I,J=np.nonzero(M); d=u20[I,J]-bs[J]
            m4=val40[I,J]; d4=u40[I,J][m4]-bs40[J][m4]
            yrs=okb.sum()/252
            line+=f" | {per} {u20[I,J].mean()*100:.0f}%({np.nanmean(d)*100:+.1f};40天{np.nanmean(d4)*100:+.1f};每檔每年{len(I)/max(yrs,1e-9):.2f})"
        print(line,flush=True)
