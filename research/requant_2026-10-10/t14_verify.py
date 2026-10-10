# t14:最後驗證 —— (1) 參數敏感度 (2) 按回檔事件分組 (3) 與「出」重疊/互補 (4) 用另一套程式碼(不經 qlib 的 FR)重算關鍵數字
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel
M=samp
def brief(lab,d,mk,side,h=20):
    out=f"  {lab:44s}"
    for per in ("p1","p2"):
        r=hit(d,mk,side,h,per,boot=0); out+=f" | {per} n={r['n']:4d} {r['hit']:4.1f}%(差{r['hit']-r['base']:+5.1f})"
    s4=[]
    for a,b in SUB4:
        r=hit(d,mk,side,h,(a,b),boot=0); s4.append("  —" if r["n"]<10 else f"{r['hit']-r['base']:+4.0f}(n{r['n']})")
    print(out+" | 四段 "+" ".join(s4),flush=True)
qmax=Q.c.rolling(252,min_periods=60).max(); smax=SP.c.rolling(252,min_periods=60).max()
DIPRAW=BUY_BASES["深跌站回(不看資金)"][0]

print("== (1a) 買:大盤回檔門檻 / 用 SPY 代替 QQQ / 資金門檻(深跌站回)")
d=ev(DIPRAW,"open")
for th in (0.05,0.08,0.10,0.15,0.20):
    brief(f"QQQ回檔≥{th:.0%} + 資金≥35%",d,M(Q.c<=qmax*(1-th),d)&M(cr>=0.35,d),"bot")
brief("SPY回檔≥10% + 資金≥35%",d,M(SP.c<=smax*0.9,d)&M(cr>=0.35,d),"bot")
brief("QQQ回檔≥10% + 資金≥35%(40日)",d,M(Q.c<=qmax*0.9,d)&M(cr>=0.35,d),"bot",40)
brief("QQQ回檔≥10% + 資金<35%",d,M(Q.c<=qmax*0.9,d)&M(cr<0.35,d),"bot")
print("== (1b) 買:深跌定義(先跌幅 thr / 回看 / 站回哪條線)")
for thr in (0.08,0.10,0.15):
    for mx in (10,20):
        dd=ev(turn("bot",thr,ma_x=mx),"open"); brief(f"先跌≥{thr:.0%} 站回{mx}日線 + 回檔≥10% + 資金≥35%",dd,M(Q.c<=qmax*0.9,dd)&M(cr>=0.35,dd),"bot")
print("== (1c) 賣:跌幅門檻 / 頂K 回看天數(不看資金,前提:漲多後跌破20日線)")
d=ev(XR,"open")
for dn in (0.03,0.04,0.05):
    for w in (10,20,30):
        brief(f"跌≥{dn:.0%} + 前{w}天頂K",d,M(ret1<=-dn,d)&M(anyN(TK.shift(1),w),d),"top")
b=M(ret1<=-0.04,d); p=M(anyN(TK.shift(1),20),d); t=M(cr<=0.35,d)
brief("跌≥4% + 前20天頂K,資金偏緊(=出的一部分)",d,b&p&t,"top")
brief("跌≥4% + 前20天頂K,資金不緊(新增的)",d,b&p&~t,"top")
brief("跌≥4% + 前20天頂K,非AI",d,b&p&~M(AIc,d),"top")
print("== (1d) 頂K:用 SPY / QQQ 跌破 20 日線 or 50 日線")
d=ev(TK,"close")
for nm,m in (("QQQ<20日線",Q.c<q20),("QQQ<10日線",Q.c<Q.c.rolling(10).mean()),("SPY<20日線",SP.c<sp20),("QQQ 5日跌",Q.c<Q.c.shift(5))):
    brief("頂K + "+nm,d,M(m,d),"top")

print("\n== (2) 按回檔事件分組:深跌站回 + QQQ回檔≥10% + 資金≥35%;買 + 資金≥65% + 回檔≥10%")
cor=(Q.c<=qmax*0.9).reindex(dates).fillna(False).values
epi=np.zeros(len(dates),int); k=0; last=-999
for i in np.flatnonzero(cor):
    if i-last>40: k+=1
    epi[i]=k; last=i
for nm,sig,cut in (("深跌站回 + 資金≥35%",DIPRAW,0.35),("買 + 資金≥65%",BUY,0.65),("★ + 資金≥65%",STAR,0.65)):
    d=ev(sig,"open"); d["ep"]=epi[d.i.values]; d["cl"]=cr.reindex(dates).values[d.i.values]
    dd=d[(d.ep>0)&(d.cl>=cut)&d.f20.notna()]
    g=dd.groupby("ep").agg(start=("date","min"),end=("date","max"),n=("f20","size"),hit=("f20",lambda x:(x>0).mean()*100),m=("f20",lambda x:x.mean()*100),hit40=("f40",lambda x:(x>0).mean()*100))
    print(f"  {nm}:")
    for _,r in g.iterrows(): print(f"    {r.start.date()}~{r.end.date()} n={r.n:4d} 20日 {r.hit:5.1f}% 均{r.m:+6.2f}% | 40日 {r.hit40:5.1f}%")
    big=g[g.n>=10]
    print(f"    → 事件≥10筆的回檔 {len(big)} 次,其中 20日命中>50%:{(big.hit>50).sum()} 次;等權平均命中 {big.hit.mean():.1f}%;全部回檔等權 {g.hit.mean():.1f}%",flush=True)

print("\n== (3) 獨立重算(不經 qlib FR:直接用 O/C 陣列,隔天開盤進、第20天收盤出)")
Ov=O.values; Cv=C.values; n=len(dates)
def raw_hit(sig,side,a,b,entry="open",h=20):
    A=sig.reindex(index=dates,columns=cols).fillna(False).values.astype(bool)
    ii,jj=np.nonzero(A); keep=(dates[ii]>=pd.Timestamp(a))&(dates[ii]<=pd.Timestamp(b))&(ii+h<n)&(ii+1<n)
    ii,jj=ii[keep],jj[keep]
    px_in=Ov[ii+1,jj] if entry=="open" else Cv[ii,jj]; px_out=Cv[ii+h,jj]
    ok=np.isfinite(px_in)&np.isfinite(px_out); r=px_out[ok]/px_in[ok]-1
    return len(r),((r<0) if side=="top" else (r>0)).mean()*100
qcor=pd.DataFrame(np.repeat((Q.c<=qmax*0.9).reindex(dates).fillna(False).values[:,None],len(cols),axis=1),index=dates,columns=cols)
c35=pd.DataFrame(np.repeat((cr>=0.35).reindex(dates).fillna(False).values[:,None],len(cols),axis=1),index=dates,columns=cols)
c65=pd.DataFrame(np.repeat((cr>=0.65).reindex(dates).fillna(False).values[:,None],len(cols),axis=1),index=dates,columns=cols)
mac=pd.DataFrame(np.repeat((OILW|YDROP).reindex(dates).fillna(False).values[:,None],len(cols),axis=1),index=dates,columns=cols)
qb=pd.DataFrame(np.repeat((Q.c<q20).reindex(dates).fillna(False).values[:,None],len(cols),axis=1),index=dates,columns=cols)
px=(ret1<=-0.04)|anyN(TK.shift(1),20)
for nm,sig,side,ent in (("深跌站回+回檔≥10%+資金≥35%",DIPRAW&qcor&c35,"bot","open"),("買+資金≥65%+回檔≥10%",BUY&c65&qcor,"bot","open"),
                         ("出+總經+價格",X&mac&px,"top","open"),("跌≥4%+前20天頂K",XR&(ret1<=-0.04)&anyN(TK.shift(1),20),"top","open"),
                         ("頂K+QQQ<20日線(收盤賣)",TK&qb,"top","close")):
    a=raw_hit(sig,side,"2009-07-01","2017-12-31",ent); b=raw_hit(sig,side,"2018-01-01","2026-12-31",ent)
    print(f"  {nm:28s} 前半 n={a[0]:4d} {a[1]:4.1f}% | 後半 n={b[0]:4d} {b[1]:4.1f}%",flush=True)
