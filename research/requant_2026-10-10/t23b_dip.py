# t23b:接 t23。(1) 同一種回檔,「大盤也在回檔」vs「只有個股自己跌」直接比(差值 + 區塊自助法 CI + 四段期間);
# (2) RSI14 門檻敏感度 + 四段;(3) 低波動股(像 TSM 這種穩健大型股:當天波動在全體下半)子集;(4) TSM 自己 2023 年後每一次。
from t23_dip import *
from t10lib import _pm
rng=np.random.default_rng(1)
SUB4=[("2009-07-01","2013-12-31"),("2014-01-01","2018-12-31"),("2019-01-01","2022-12-31"),("2023-01-01","2026-12-31")]
PER={"2009–17":("2009-07-01","2017-12-31"),"2018–26":("2018-01-01","2026-12-31")}
u20all=(FRC[20]>0).values.astype(float); val=~np.isnan(FRC[20].values)
_SBC={}
def stockbase(state,a,b):
    k=(id(state),a,b)
    if k in _SBC: return _SBC[k]
    _SBC[k]=_sb(state,a,b); return _SBC[k]
def _sb(state,a,b):
    pm=_pm(a,b); ok=state.values&pm[:,None]&val; I0,J0=np.nonzero(ok)
    bs=np.full(len(cols),np.nan)
    for j in range(len(cols)):
        s=J0==j
        if s.sum()>=50: bs[j]=u20all[I0[s],J0[s]].mean()
    return bs
def events(sig,state,a,b):
    pm=_pm(a,b); M=first(sig.reindex(index=dates,columns=cols).fillna(False).astype(bool)&state,10).values&pm[:,None]&val
    return np.nonzero(M)
def boot_diff(I1,d1,I2,d2,B=400):
    def prep(I,d):
        blk=I//20; ub=np.unique(blk); return ub,{b:d[blk==b] for b in ub}
    u1,m1=prep(I1,d1); u2,m2=prep(I2,d2); out=[]
    for _ in range(B):
        x1=np.concatenate([m1[b] for b in rng.choice(u1,len(u1))]); x2=np.concatenate([m2[b] for b in rng.choice(u2,len(u2))])
        out.append(x1.mean()-x2.mean())
    return np.percentile(out,[5,95])
print("### (1) 同一種回檔:大盤也回檔(QQQ<20日線)vs 只有個股自己跌 —— 20 天後較高,扣掉同股上升趨勢基準")
BASES={"③a 第一次碰布林中軌":touch_mid,"②a 碰 50 日線":T(t50),"②c 碰 100 日線":T(t100),"②e 碰第二條 CTA 線":T(sec),
       "④ 第一次碰週布林中軌":(L<=wmid)&above_n(L,wmid,20),"⑤ 碰布林下緣":(L<=lo)&above_n(L,lo,10),
       "⑩b 離20日高點 −8%":(pbk<=-0.08)&(pbk.shift(1)>-0.08),"⑧ RSI14≤40":(R14<=40)&(R14.shift(1)>40)}
for stname,state in {"上升趨勢":UT,"穩健上升":UTS}.items():
    print(f"\n[{stname}]")
    for nm,s in BASES.items():
        line=f"  {nm:18s}"
        for per,(a,b) in PER.items():
            bs=stockbase(state,a,b)
            Ia,Ja=events(s&qdip,state,a,b); Ib,Jb=events(s&~qdip,state,a,b)
            da=u20all[Ia,Ja]-bs[Ja]; db=u20all[Ib,Jb]-bs[Jb]; ka=~np.isnan(da); kb=~np.isnan(db)
            ci=boot_diff(Ia[ka],da[ka],Ib[kb],db[kb])
            line+=f" | {per} 大盤也回檔 {np.mean(u20all[Ia,Ja])*100:.0f}%({np.nanmean(da)*100:+.1f},n{len(Ia)}) 只有個股 {np.mean(u20all[Ib,Jb])*100:.0f}%({np.nanmean(db)*100:+.1f},n{len(Ib)}) 差 {(np.nanmean(da)-np.nanmean(db))*100:+.1f} [{ci[0]*100:+.1f},{ci[1]*100:+.1f}]"
        sg=[]
        for a,b in SUB4:
            bs=stockbase(state,a,b); Ia,Ja=events(s&qdip,state,a,b); Ib,Jb=events(s&~qdip,state,a,b)
            sg.append((np.nanmean(u20all[Ia,Ja]-bs[Ja])-np.nanmean(u20all[Ib,Jb]-bs[Jb]))*100)
        print(line+" | 四段差 "+" ".join(f"{v:+.0f}" for v in sg),flush=True)
print("\n### (2) RSI14 往下穿門檻(上升趨勢)—— 20 天後較高 − 同股基準;四段")
for stname,state in {"上升趨勢":UT,"穩健上升":UTS}.items():
    for th in (30,35,40,45,50):
        s=(R14<=th)&(R14.shift(1)>th); line=f"  [{stname}] RSI14≤{th}"
        for per,(a,b) in list(PER.items())+[(f"四段{k+1}",ab) for k,ab in enumerate(SUB4)]:
            bs=stockbase(state,a,b); I,J=events(s,state,a,b); d=u20all[I,J]-bs[J]
            line+=f" | {per} {np.nanmean(d)*100:+.1f}(n{len(I)})"
        print(line,flush=True)
print("\n### (3) 低波動(當天波動在全體下半,像 TSM)—— 20 天後較高 − 同股基準")
LOWV=(VQ<=0.5)
for nm,s in {**BASES,"①b 日TD買9–13+碰下緣":(tdb>=9)&(tdb<=13)&(L<=lo)}.items():
    line=f"  {nm:18s}"
    for per,(a,b) in PER.items():
        bs=stockbase(UT,a,b); I,J=events(s&LOWV,UT,a,b); d=u20all[I,J]-bs[J]
        line+=f" | {per} {np.mean(u20all[I,J])*100:.0f}%(同股 {np.nanmean(bs[J])*100:.0f}%,{np.nanmean(d)*100:+.1f},n{len(I)})"
    print(line,flush=True)
print("\n### (4) TSM 2023 年後(上升趨勢裡)各訊號每一次:收盤買,之後 10/20/40 天、20 天內最多再跌")
j=cols.index("TSM"); Cv_=C.values[:,j]; Lv_=L.values[:,j]; n_=len(dates)
TS={"碰布林中軌":touch_mid,"碰 50 日線":T(t50),"碰 100 日線":T(t100),"碰第二條 CTA 線":T(sec),"碰週布林中軌":(L<=wmid)&above_n(L,wmid,20),
    "RSI14≤40":(R14<=40)&(R14.shift(1)>40),"碰布林下緣":(L<=lo)&above_n(L,lo,10)}
for nm,s in TS.items():
    M=first(s.fillna(False).astype(bool)&UT,10)[cols[j]].values
    rows=[]
    for t in np.flatnonzero(M):
        if dates[t]<pd.Timestamp("2023-01-01"): continue
        P=Cv_[t]; f=lambda h: f"{(Cv_[t+h]/P-1)*100:+5.1f}%" if t+h<n_ else "  –  "
        dd=(np.nanmin(Lv_[t+1:t+21])/P-1)*100 if t+1<n_ else np.nan
        rows.append(f"{dates[t].date()} {'大盤也跌' if qdip.values[t,j] else '只有個股'} 收{P:7.2f} 10天{f(10)} 20天{f(20)} 40天{f(40)} 再跌{dd:+.1f}%")
    print(f"  ■ {nm}({len(rows)} 次)"); [print("     "+r) for r in rows]
