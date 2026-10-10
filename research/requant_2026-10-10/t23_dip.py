# t23:穩健上漲股(像 TSM)的「波段抄底 / 短線加碼」— 使用者假設 + 其他方法。只研究。
# 使用者:漲時沿布林上緣漲到 TD9–13;跌時因基本面太好跌不深 —— 日K 跌到 CTA 第二條線、或跌破布林中軌但沒到下軌,常常就開始漲;
#         週K 回檔通常只碰到週布林中軌就漲回去;反過來的 TD買9–13+下緣(日+週)很難出現。
# 上升趨勢(用「昨天收盤」判斷,避免回檔本身改變狀態):收盤 > 200日線、50日線 > 200日線、200日線比 20 天前高。
# 穩健上升:再加 50 > 100 > 200 日線 且 近 40 天內創過一年新高(收盤)。
# 進場:訊號當天收盤(碰線類 = 當天最低碰到「開盤前就知道的線價」)。
# 基準(重點):同一段期間「上升趨勢裡的隨便一天」、同一檔股票自己上升趨勢裡的隨便一天、同波動的上升趨勢日。
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _pm
def runc(cond):
    c=cond.astype(int); return c.apply(lambda s: s.groupby((s==0).cumsum()).cumsum())
def first(cond,k=10):
    c=cond.fillna(False).astype(bool); return c&~c.shift(1).fillna(False).astype(int).rolling(k,min_periods=1).max().astype(bool)
def above_n(Lo,X,n):   # 前 n 天最低價都在線上(第一次回測)
    return ((Lo>X).astype(int).rolling(n,min_periods=n).sum().shift(1)==n)
S100=C.rolling(100).mean()
u=(C>S200)&(S50>S200)&(S200>S200.shift(20)); UT=u.shift(1).fillna(False).astype(bool)
hi252=C.rolling(252,min_periods=200).max(); nh=(C>=hi252)
UTS=UT&((S50>S100)&(S100>S200)).shift(1).fillna(False).astype(bool)&nh.astype(int).rolling(40,min_periods=1).max().shift(1).fillna(0).astype(bool)
# ---- 線價(開盤前就知道)----
C1=C.shift(1)
t50=C1.rolling(49).mean(); t100=C1.rolling(99).mean(); t200=C1.rolling(199).mean(); t63=C.shift(63)   # CTA 四條煞車線(同儀表板 t50/t100/t200/t63)
m19=C1.rolling(19).mean()                                                                           # 布林中軌(今天收在這以下 = 收破中軌)
sd=C.rolling(20).std(ddof=0); mid=S20; lo=S20-2*sd
# 第二條線 = 昨天收盤以下的 CTA 線,由上往下數第二條
LV=np.stack([t50.values,t63.values,t100.values,t200.values]); c1=C1.values[None,:,:]
LVb=np.where(LV<c1,LV,np.nan); LVs=-np.sort(-np.nan_to_num(LVb,nan=-np.inf),axis=0); LVs[np.isinf(LVs)]=np.nan
sec=pd.DataFrame(LVs[1],index=dates,columns=cols); fst=pd.DataFrame(LVs[0],index=dates,columns=cols)
# ---- 週K(截至當天)----
wk=pd.Series(dates.to_period("W-FRI"),index=dates)
Wc=C.groupby(wk.values).last()
def to_days(X): return X.reindex(wk.values).set_axis(dates)
wmid=to_days(Wc.rolling(19).mean().shift(1))                     # 週中軌的觸發價 = 前 19 個完整週收盤平均
S1=to_days(Wc.rolling(19).sum().shift(1)); S2=to_days((Wc**2).rolling(19).sum().shift(1))
mW=(S1+C)/20; vW=((S2+C**2)/20-mW**2).clip(lower=0); loW=mW-2*np.sqrt(vW)
cumL=L.groupby(wk.values).cummin().set_axis(dates)
tdbW_done=runc(Wc<Wc.shift(4)); c4=to_days(Wc.shift(4)); prevB=to_days(tdbW_done.shift(1))
tdbW=((C<c4).astype(int)*(prevB.fillna(0)+1)).where(c4.notna())
tdb=runc(C<C.shift(4))
# 熱(t22e)
tdsD=runc(C>C.shift(4)); upD=S20+2*sd; cumH=H.groupby(wk.values).cummax().set_axis(dates)
upW=mW+2*np.sqrt(vW); tdW_done=runc(Wc>Wc.shift(4)); prevS=to_days(tdW_done.shift(1))
tdsW=((C>c4).astype(int)*(prevS.fillna(0)+1)).where(c4.notna())
HOT=first((tdsD>=9)&(tdsD<=13)&(H>=upD)&(tdsW>=9)&(cumH>=upW))
# ---- 其他特徵 ----
tr=np.maximum(H-L,np.maximum((H-C.shift()).abs(),(L-C.shift()).abs())); atr=tr.rolling(14,min_periods=10).mean()
def rsi(n):
    d=C.diff(); g=d.clip(lower=0); l=(-d).clip(lower=0)
    ag=g.ewm(alpha=1/n,adjust=False).mean(); al=l.ewm(alpha=1/n,adjust=False).mean(); return 100-100/(1+ag/al.replace(0,np.nan))
R2=rsi(2); R14=rsi(14)
dn3=(C<C.shift(1))&(C.shift(1)<C.shift(2))&(C.shift(2)<C.shift(3))
hi20=C.rolling(20).max(); pbk=C/hi20-1
body=(C-O).abs(); lwick=np.minimum(O,C)-L; rngd=(H-L).replace(0,np.nan)
hammer=(lwick>=2*body)&((C-L)/rngd>=0.67)
qdip=pd.DataFrame(np.repeat((Q.c<q20).values[:,None],len(cols),axis=1),index=dates,columns=cols)
touch_mid=(L<=m19)&above_n(L,m19,10)
def T(X,n=10): return (L<=X)&above_n(L,X,n)
SIG={
 # 使用者的四個想法
 "①反向熱:日TD買9–13+碰下緣+週TD買≥9+碰週下緣":(tdb>=9)&(tdb<=13)&(L<=lo)&(tdbW>=9)&(cumL<=loW),
 "①b 只看日K:TD買9–13+碰下緣":(tdb>=9)&(tdb<=13)&(L<=lo),
 "②a 碰 CTA 短線(50日)":T(t50),
 "②b 碰 CTA 動能線(63日前收盤)":T(t63),
 "②c 碰 CTA 中線(100日)":T(t100),
 "②d 碰 CTA 長線(200日)":T(t200),
 "②e 碰「價格下方第二條」CTA 線":T(sec),
 "②f 碰「價格下方第一條」CTA 線":T(fst),
 "③a 第一次碰布林中軌":touch_mid,
 "③b 收破中軌、沒到下緣(第一天)":(C<mid)&((C>mid).astype(int).rolling(5).sum().shift(1)==5)&(C>lo),
 "③c 碰中軌且收盤沒破下緣":touch_mid&(C>lo),
 "④ 第一次碰週布林中軌":(L<=wmid)&above_n(L,wmid,20),
 # 其他方法
 "⑤ 碰布林下緣":(L<=lo)&above_n(L,lo,10),
 "⑥ 日TD買 剛數到9":(tdb==9),
 "⑦ RSI2<10":(R2<10)&(R2.shift(1)>=10),
 "⑧ RSI14≤40":(R14<=40)&(R14.shift(1)>40),
 "⑨ 連跌3天":dn3,
 "⑩a 離20日高點 −5%":(pbk<=-0.05)&(pbk.shift(1)>-0.05),
 "⑩b 離20日高點 −8%":(pbk<=-0.08)&(pbk.shift(1)>-0.08),
 "⑩c 離20日高點 −10%":(pbk<=-0.10)&(pbk.shift(1)>-0.10),
 "⑪ 收盤≤中軌−1ATR":(C<=mid-atr)&(C.shift(1)>(mid-atr).shift(1)),
 "⑫ 碰中軌+長下影線(錘子)":(L<=m19)&hammer,
 "⑬ 碰中軌+量縮(<0.8倍)":touch_mid&(vr<0.8),
 "⑭a 碰中軌+大盤也回檔(QQQ<20日線)":touch_mid&qdip,
 "⑭b 碰中軌+只有個股回檔":touch_mid&~qdip,
 "⑮a 熱之後 30 天內第一次碰中軌":touch_mid&anyN(HOT,30).shift(1).fillna(False).astype(bool),
 "⑮b 熱之後 30 天內第一次碰 50 日線":T(t50)&anyN(HOT,30).shift(1).fillna(False).astype(bool),
 "⑯ 碰中軌+資金≥65%":touch_mid&(CL>=0.65),
}
# ---- 結果 ----
FRC10=FRC[10].values; FRC20=FRC[20].values; FRC40=FRC[40].values; MA20=MAEC[20].values; Cv=C.values
A10=(C[::-1].rolling(10,min_periods=10).mean()[::-1].shift(-1)/C-1).values         # 之後 10 天平均收盤 vs 買價(>0 = 買得比之後兩週便宜)
VB=np.clip(np.floor(VQ.values*10),0,9); VB=np.where(np.isnan(VB),-1,VB).astype(int)
def stat_rows(state,stname):
    for per,(a,b) in {"2009–17":("2009-07-01","2017-12-31"),"2018–26":("2018-01-01","2026-12-31"),"近兩年":("2024-10-01","2026-12-31")}.items():
        pm=_pm(a,b); ok=state.values&pm[:,None]&~np.isnan(FRC20)&~np.isnan(A10)
        I0,J0=np.nonzero(ok); yrs=len(I0)/252
        u10=FRC10[I0,J0]>0; u20=FRC20[I0,J0]>0; m40=~np.isnan(FRC40[I0,J0]); u40=FRC40[I0,J0][m40]>0
        dd=MA20[I0,J0]<=np.log(0.95); ed=A10[I0,J0]
        # 同股基準、同波動基準
        bs20=np.full(len(cols),np.nan); bs10=np.full(len(cols),np.nan)
        for j in range(len(cols)):
            s=J0==j
            if s.sum()>=50: bs20[j]=u20[s].mean(); bs10[j]=u10[s].mean()
        bv20=np.array([u20[VB[I0,J0]==k].mean() if np.any(VB[I0,J0]==k) else np.nan for k in range(10)])
        print(f"\n[{stname} · {per}] 上升趨勢裡隨便一天(收盤買):10天後較高 {u10.mean()*100:.0f}% 20天 {u20.mean()*100:.0f}% 40天 {u40.mean()*100:.0f}% | 20天中位數 {np.median(np.exp(FRC20[I0,J0])-1)*100:+.1f}% | 20天內再跌≥5% {dd.mean()*100:.0f}% | 之後10天均價 {np.mean(ed)*100:+.2f}% | 股票年 {yrs:.0f}")
        rng=np.random.default_rng(0)
        for nm,s in SIG.items():
            M=first(s.reindex(index=dates,columns=cols).fillna(False).astype(bool)&state,10).values&ok
            I,J=np.nonzero(M)
            if len(I)<15: print(f"  {nm:34s} n={len(I):4d}(太少)"); continue
            e20=FRC20[I,J]>0; e10=FRC10[I,J]>0; mm=~np.isnan(FRC40[I,J]); e40=FRC40[I,J][mm]>0
            bS=bs20[J]; okb=~np.isnan(bS); d=e20[okb].astype(float)-bS[okb]
            # 20 天區塊自助法(依事件日期分組)
            blk=I[okb]//20; ub=np.unique(blk); idx={b:np.flatnonzero(blk==b) for b in ub}; bt=[]
            for _ in range(400):
                pick=rng.choice(ub,len(ub)); ii=np.concatenate([idx[b] for b in pick]); bt.append(d[ii].mean())
            lo_,hi_=np.percentile(bt,[5,95])
            bv=np.nanmean(bv20[np.clip(VB[I,J],0,9)])
            print(f"  {nm:34s} n={len(I):4d}(每檔每年 {len(I)/yrs:.2f})| 10天 {e10.mean()*100:.0f}%(同股 {np.nanmean(bs10[J])*100:.0f}%)"
                  f" 20天 {e20.mean()*100:.0f}%(同股 {np.nanmean(bS)*100:.0f}% 同波動 {bv*100:.0f}%)差 {d.mean()*100:+.1f} [{lo_*100:+.1f},{hi_*100:+.1f}]"
                  f" 40天 {e40.mean()*100:.0f}% | 20天中位數 {np.median(np.exp(FRC20[I,J])-1)*100:+.1f}% | 再跌≥5% {np.mean(MA20[I,J]<=np.log(0.95))*100:.0f}% | 之後10天均價 {np.mean(A10[I,J])*100:+.2f}%",flush=True)
if __name__=="__main__":
    stat_rows(UT,"上升趨勢")
    stat_rows(UTS,"穩健上升(多頭排列+近40天創一年新高)")
