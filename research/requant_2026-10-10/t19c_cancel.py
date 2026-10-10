# t19c:另外兩條「取消」規則也查一次 —— 減碼:收盤漲回頂K高點以上就取消;抄底:收盤跌回 20 日線以下就先停
import sys; sys.path.insert(0,"."); from t1x_cands import *; from t10lib import _sel, _pm
Cv=C.values; Hv=H.values; S20v=S20.values; n=len(dates); FRCv=FRC[20].values
def run(lab,sig,side,cond):
    d=ev(sig,"close" if side=="top" else "open"); I=d.i.values; J=d.j.values; dt=d.date.values
    kk=np.full(len(d),99)
    for e in range(len(d)):
        i,j=I[e],J[e]
        for k in range(1,11):
            if i+k<n and cond(i,j,k): kk[e]=k; break
    def stat(mask,kv,per):
        a,b=PERIODS[per]; sel=mask&(dt>=np.datetime64(a))&(dt<=np.datetime64(b))
        v=FRCv[np.minimum(I[sel]+kv[sel],n-1),J[sel]]; v=v[~np.isnan(v)]
        g=(v<0) if side=="top" else (v>0)
        return f"{per} n={len(v):4d} 之後20日{'較低' if side=='top' else '較高'} {np.mean(g)*100:4.1f}%(平常 {base(side,'close',20,per):.1f}%)" if len(v)>=8 else f"{per} n={len(v)} —"
    m=kk<=10
    print(f"{lab} 10 天內發生 {m.mean()*100:3.0f}% | 從取消那天收盤算:"+" | ".join(stat(m,kk,p) for p in ("p1","p2")),flush=True)
    for k in (1,5,10):
        kv=np.full(len(d),k); print(f"   不取消、第 {k:2d} 天再看 | "+" | ".join(stat(np.ones(len(d),bool),kv,p) for p in ("p1","p2")),flush=True)
run("減碼:收盤漲回頂K高點以上",CF,"top",lambda i,j,k: Cv[i+k,j]>Hv[i-1,j])
run("抄底:收盤跌回 20 日線以下",BUY_BASES["抄底"][0],"bot",lambda i,j,k: (not np.isnan(S20v[i+k,j])) and Cv[i+k,j]<S20v[i+k,j])
