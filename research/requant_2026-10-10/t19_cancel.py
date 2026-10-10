# t19:使用者發現 BE 矛盾 —— 10-08 出(圖上有字),10-09 收盤站回 20 日線 → 狀態列「取消、不用動」。
#      「站回 20 日線就取消」這條規則對不對?出之後隔天(或幾天內)就站回的那些,之後還會不會跌?
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel, _pm
Cv=C.values; S20v=S20.values; n=len(dates)
d=ev(X,"open"); I=d.i.values; J=d.j.values
mac=samp(OILW|YDROP,d); px=samp((ret1<=-0.04)|anyN(TK.shift(1),20),d); strong=mac|px
# 第幾天第一次收盤站回 20 日線(1..10;沒有 = 99)
rk=np.full(len(d),99)
for e in range(len(d)):
    i,j=I[e],J[e]
    for k in range(1,11):
        if i+k<n and not np.isnan(S20v[i+k,j]) and Cv[i+k,j]>=S20v[i+k,j]: rk[e]=k; break
FRCv=FRC[20].values; FRC40=FRC[40].values
def fwd(rows,cols,h=20): 
    A=FRCv if h==20 else FRC40; v=A[rows,cols]; return v
def show(lab,mask,from_k,per):
    a,b=PERIODS[per]; dt=d.date.values
    sel=mask&(dt>=np.datetime64(a))&(dt<=np.datetime64(b))
    rows=np.minimum(I[sel]+from_k[sel],n-1); cols=J[sel]
    v=fwd(rows,cols); v=v[~np.isnan(v)]; v4=fwd(rows,cols,40); v4=v4[~np.isnan(v4)]
    bs=base("top","close",20,per)
    return f"{per} n={len(v):4d} 20日後較低 {np.mean(v<0)*100:4.1f}%(平常 {bs:.1f}%)40日 {np.mean(v4<0)*100:4.1f}% 均 {np.mean(v)*100:+5.1f}%" if len(v)>=8 else f"{per} n={len(v)} —"
print("全部「出」中:隔天就站回 %.0f%%、2–5 天內站回 %.0f%%、6–10 天 %.0f%%、10 天內都沒站回 %.0f%%"%((rk==1).mean()*100,((rk>=2)&(rk<=5)).mean()*100,((rk>=6)&(rk<=10)).mean()*100,(rk==99).mean()*100))
one=np.ones(len(d),int)
for lab,mask,fk in (("隔天就站回(從站回那天收盤算)",rk==1,rk),
                    ("2–5 天內站回(從站回那天收盤算)",(rk>=2)&(rk<=5),rk),
                    ("10 天內沒站回(從出隔天收盤算)",rk==99,one),
                    ("全部出(從出隔天收盤算)",np.ones(len(d),bool),one)):
    print(f"{lab:30s} | "+" | ".join(show(lab,mask,fk,p) for p in ("p1","p2")),flush=True)
print("-- 分強弱")
for g,gm in (("強",strong),("灰",~strong)):
    for lab,mask,fk in (("隔天就站回",rk==1,rk),("2–5 天內站回",(rk>=2)&(rk<=5),rk),("沒站回",rk==99,one)):
        print(f"{g} {lab:12s} | "+" | ".join(show(lab,gm&mask,fk,p) for p in ("p1","p2")),flush=True)
print("-- 站回之後又跌破(假突破)比例:站回後 10 天內再收破 20 日線")
rb=np.zeros(len(d),bool)
for e in np.flatnonzero(rk<=10):
    i,j,k=I[e],J[e],rk[e]
    for m in range(1,11):
        t=i+k+m
        if t<n and not np.isnan(S20v[t,j]) and Cv[t,j]<S20v[t,j]: rb[e]=True; break
print("站回的出裡,10 天內又跌破 20 日線:%.0f%%"%(rb[rk<=10].mean()*100))
for lab,mask,fk in (("站回後又跌破(從再跌破那天算)",(rk<=10)&rb,None),):
    pass
