import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
from lib import DT
exec(open("rules.py").read().split('print("=== 減碼確認')[0])
S2=pickle.load(open(DT+"/stock.pkl","rb")); Fz=S2["F"]
TOP=Fz["TOP"].reindex(C.index).astype("float64"); BOT=Fz["BOT"].reindex(C.index).astype("float64")
def cool_any(m): return cool(m)
sigs={
 "▼減碼 strong: ext15 & clim<=20%":(make("top",50,0.15)&(clim<=0.2),"top"),
 "▼減碼 regular: ext15 & clim<=35%":(make("top",50,0.15)&(clim<=0.35),"top"),
 "出 alone (ext15, any climate)":(make("top",50,0.15),"top"),
 "◆ TOP>=3 (first day, cool20)":(cool(TOP>=3),"top"),
 "▲抄底 strong: dip15 & clim>=80%":(make("bot",50,0.15)&(clim>=0.8),"bot"),
 "▲抄底 regular: dip10 & clim>=65%":(make("bot",50,0.10)&(clim>=0.65),"bot"),
 "dip→recross alone (dip10)":(make("bot",50,0.10),"bot"),
 "★ BOT>=3 (first day, cool20)":(cool(BOT>=3),"bot"),
}
P4[:]=[("2009-01-01","2017-12-31"),("2018-01-01","2026-12-31")]
for nm,(s,side) in sigs.items():
    for h in (10,20,40):
        r,ci=ev(s,side,h,boot=True)
        print(f"{nm:36s} h={h:2d} "+" | ".join(f"{p[0][2:4]}-{p[1][2:4]} n={n:4d} edge {e:+5.1f}pt [{c[0]:+.0f},{c[1]:+.0f}] Δμ {m:+.1f}%" for (n,e,m),c,p in zip(r,ci,P4)))
    # drawdown risk for top signals at 20/40
    if side=="top":
        out=[]
        for a,b in P4:
            per=(dates>=a)&(dates<=b)
            for h in (20,40):
                dd=DD[h].loc[per]; base=(dd.stack()<=np.log(0.9)).mean()*100; e=dd.where(s.loc[per]).stack()
                out.append(f"{a[2:4]}-{b[2:4]} P(dd{h}<=-10%) {(e<=np.log(0.9)).mean()*100:.0f}% vs {base:.0f}%")
        print("   "+" | ".join(out))
pickle.dump({k:v[0] for k,v in sigs.items()},open(DT+"/final_sigs.pkl","wb"))
