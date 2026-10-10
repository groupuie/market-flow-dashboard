# t19b:那「出」什麼時候才該取消?比較三種取消條件(從取消那天收盤算之後 20 日)
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel, _pm
Cv=C.values; S20v=S20.values; n=len(dates); FRCv=FRC[20].values
d=ev(X,"open"); I=d.i.values; J=d.j.values; dt=d.date.values
pk=C.rolling(20).max().values          # 出之前 20 天的最高收盤(用出當天的值 = 含當天)
def first_hit(cond):
    out=np.full(len(d),99)
    for e in range(len(d)):
        i,j=I[e],J[e]
        for k in range(1,11):
            if i+k<n and cond(i,j,k): out[e]=k; break
    return out
above=lambda t,j: (not np.isnan(S20v[t,j])) and Cv[t,j]>=S20v[t,j]
kA=first_hit(lambda i,j,k: above(i+k,j))                                   # 收盤站回 20 日線(現行)
kB=first_hit(lambda i,j,k: k>=3 and all(above(i+m,j) for m in range(k-2,k+1)))   # 連續 3 天站穩 20 日線
kC=first_hit(lambda i,j,k: Cv[i+k,j]>pk[i-1,j])                            # 收盤創出之前 20 天新高(頂部失敗)
def stat(mask,kk,per):
    a,b=PERIODS[per]; sel=mask&(dt>=np.datetime64(a))&(dt<=np.datetime64(b))
    v=FRCv[np.minimum(I[sel]+kk[sel],n-1),J[sel]]; v=v[~np.isnan(v)]
    return f"{per} n={len(v):4d} 之後20日較低 {np.mean(v<0)*100:4.1f}%(平常 {base('top','close',20,per):.1f}%)均 {np.mean(v)*100:+5.1f}%" if len(v)>=8 else f"{per} n={len(v)} —"
for lab,kk in (("A 收盤站回 20 日線(現行取消條件)",kA),("B 連續 3 天站穩 20 日線",kB),("C 收盤創出之前 20 天新高",kC)):
    m=kk<=10
    print(f"{lab:26s} 10 天內發生 {m.mean()*100:3.0f}% | 從那天收盤算:"+" | ".join(stat(m,kk,p) for p in ("p1","p2")),flush=True)
print("-- 不取消:出之後第 k 天收盤再看之後 20 日(全部出)")
for k in (1,3,5,10):
    kk=np.full(len(d),k); print(f"  第 {k:2d} 天 | "+" | ".join(stat(np.ones(len(d),bool),kk,p) for p in ("p1","p2")),flush=True)
